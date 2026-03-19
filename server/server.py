#!/usr/bin/env python3
# Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
# https://creativecommons.org/licenses/by-nc-sa/4.0/
"""
3 Bad Dogs — Photo & Camera Server

Minimal HTTP server that serves random photos, camera snapshots
(a_secure_password or ffmpeg-from-stream), and optional HA/Frigate proxying.

Endpoints:
  /              HTML page — full-screen photo frame with auto-refresh and clock overlay
  /random        Returns a random image file (JPEG/PNG/WebP) with proper content-type
  /random?w=1280&h=800  Resize on the fly (requires Pillow)
  /camera/list   JSON array of available camera names
  /camera/<name> JPEG snapshot (optional ?w=&h= resize)
  /camera/<name>/info  JSON: {name, snapshot, stream, stream_type, ptz}
  /camera/<name>/ptz   POST: PTZ control (ONVIF) — {action, direction, speed}
  /ha/weather    Plain text: current weather summary
  /ha/forecast   Plain text: 3-day forecast
  /ha/event      Plain text: next calendar event
  /ha/thermostat Plain text: thermostat status
  /health        Health check

Configuration:
  All settings are read from config.yaml (default: /config/config.yaml).
  Environment variables override config.yaml values for backward compatibility.

  See config.yaml.example for all available options.

Usage:
  docker run -v /path/to/config.yaml:/config/config.yaml:ro \\
             -v /path/to/photos:/media:ro \\
             -p 8099:8099 3-bad-dogs-server
"""

import os
import sys
import random
import mimetypes
import json
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from io import BytesIO

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, Request, URLError

CONFIG_FILE = os.environ.get("CONFIG_FILE", "/config/config.yaml")

# Defaults — overridden by config.yaml, then by env vars
PHOTO_DIR = "/media"
PORT = 8099
REFRESH = 30
TITLE = ""
CAMERA_IDLE = 30
HA_URL = ""
HA_TOKEN = ""
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# ── Photo cache ──────────────────────────────────────────
_photo_cache = []
_cache_mtime = 0


def get_photos():
    """Return list of photo paths, refreshing if directory has changed."""
    global _photo_cache, _cache_mtime
    try:
        stat = os.stat(PHOTO_DIR)
        if stat.st_mtime != _cache_mtime or not _photo_cache:
            _cache_mtime = stat.st_mtime
            _photo_cache = [
                os.path.join(PHOTO_DIR, f)
                for f in os.listdir(PHOTO_DIR)
                if os.path.splitext(f)[1].lower() in EXTS
            ]
    except OSError:
        pass
    return _photo_cache


def resize_image(path, max_w, max_h):
    """Resize image to fit within max_w x max_h. Returns (bytes, content_type)."""
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            buf = BytesIO()
            fmt = "JPEG" if path.lower().endswith((".jpg", ".jpeg")) else "PNG"
            img.save(buf, fmt, quality=85)
            ct = "image/jpeg" if fmt == "JPEG" else "image/png"
            return buf.getvalue(), ct
    except ImportError:
        return None, None


# ── Camera configuration ─────────────────────────────────
# Unified camera config: each camera has optional snapshot, stream, auth.
# Loaded from YAML file or legacy CAMERAS env var (JSON).

_CAMERAS = {}  # name -> {snapshot, stream, stream_type, auth: {type, username, password}}


def _load_config():
    """Load config from YAML file, with env var overrides."""
    global PHOTO_DIR, PORT, REFRESH, TITLE
    global CAMERA_IDLE, HA_URL, HA_TOKEN, _CAMERAS, _cameras_lower

    cfg = {}

    # Also try legacy cameras.yaml path for backward compat
    for path in [CONFIG_FILE, "/config/cameras.yaml"]:
        if os.path.isfile(path):
            try:
                import yaml
                with open(path) as f:
                    cfg = yaml.safe_load(f) or {}
                print(f"  config: loaded from {path}")
                break
            except ImportError:
                print("WARNING: PyYAML not installed, cannot read config")
            except Exception as e:
                print(f"WARNING: failed to parse {path}: {e}")
            break

    # Apply config.yaml values (env vars override)
    PHOTO_DIR = os.environ.get("PHOTO_DIR", cfg.get("photo_dir", PHOTO_DIR))
    PORT = int(os.environ.get("PORT", cfg.get("port", PORT)))
    REFRESH = int(os.environ.get("REFRESH", cfg.get("refresh", REFRESH)))
    TITLE = os.environ.get("TITLE", cfg.get("title", TITLE))
    CAMERA_IDLE = int(os.environ.get("CAMERA_IDLE", cfg.get("camera_idle", CAMERA_IDLE)))
    HA_URL = os.environ.get("HA_URL", cfg.get("ha_url", HA_URL)).rstrip("/")
    HA_TOKEN = os.environ.get("HA_TOKEN", cfg.get("ha_token", HA_TOKEN))

    # Load cameras from config
    if cfg.get("cameras"):
        _CAMERAS = cfg["cameras"]
        _cameras_lower = {k.lower(): k for k in _CAMERAS}
        print(f"  cameras: {len(_CAMERAS)} configured")
        return

    # Fall back to CAMERAS env var (legacy JSON format)
    cameras_env = os.environ.get("CAMERAS", "")
    if cameras_env:
        try:
            legacy = json.loads(cameras_env)
            for name, cam in legacy.items():
                _CAMERAS[name] = {
                    "snapshot": "http://{}/x/ch0.jpg".format(cam["ip"]),
                    "auth": {
                        "type": "a_secure_password",
                        "username": cam.get("user", "admin"),
                        "password": cam.get("pass", ""),
                    }
                }
            print(f"  cameras: loaded {len(_CAMERAS)} from CAMERAS env var (legacy)")
        except json.JSONDecodeError:
            print("WARNING: CAMERAS env var is not valid JSON, ignoring")
    _cameras_lower = {k.lower(): k for k in _CAMERAS}



# ── Camera streams ───────────────────────────────────────

class CameraStream:
    """Polls a camera for live JPEG frames.

    Supports two snapshot sources:
      1. Direct HTTP snapshot URL (a_secure_password /x/ch0.jpg with session auth, or basic auth)
      2. ffmpeg extraction from an HLS/RTSP stream (for stream-only cameras)
    """

    def __init__(self, name, config):
        self.name = name
        self._config = config
        self._session = None
        self._frame = None
        self._lock = threading.Lock()
        self._last_request = 0
        self._running = False

    def get_frame(self):
        """Return the latest JPEG frame, starting the poller if needed."""
        self._last_request = time.time()
        if not self._running:
            self._start()
            for _ in range(50):  # wait up to 5s for first frame
                time.sleep(0.1)
                with self._lock:
                    if self._frame is not None:
                        return self._frame
        with self._lock:
            return self._frame

    def _start(self):
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _poll_loop(self):
        """Continuously fetch frames until idle timeout."""
        while self._running:
            if time.time() - self._last_request > CAMERA_IDLE:
                self._running = False
                with self._lock:
                    self._frame = None
                return
            raw = self._fetch_frame()
            if raw:
                with self._lock:
                    self._frame = raw

    def _fetch_frame(self):
        """Fetch a single JPEG frame from the best available source."""
        snapshot_url = self._config.get("snapshot")
        auth = self._config.get("auth", {})
        auth_type = auth.get("type", "")

        if snapshot_url:
            if auth_type == "a_secure_password":
                return self._fetch_a_secure_password(snapshot_url, auth)
            elif auth_type == "basic":
                return self._fetch_basic_auth(snapshot_url, auth)
            else:
                return self._fetch_url(snapshot_url)

        # No snapshot URL — try ffmpeg from stream
        stream_url = self._config.get("stream")
        if stream_url:
            return self._fetch_ffmpeg(stream_url)

        return None

    def _fetch_a_secure_password(self, snapshot_url, auth):
        """Fetch snapshot with a_secure_password session auth."""
        ip = self._extract_host(snapshot_url)
        if not self._session:
            if not self._login_a_secure_password(ip, auth):
                return None
        raw = self._fetch_with_session(snapshot_url)
        if raw:
            return raw
        # Session expired — retry
        if self._login_a_secure_password(ip, auth):
            return self._fetch_with_session(snapshot_url)
        return None

    def _login_a_secure_password(self, ip, auth):
        """Get a a_secure_password session cookie."""
        try:
            url = "http://{}/x/login.cgi".format(ip)
            body = json.dumps({
                "username": auth.get("username", "admin"),
                "password": auth.get("password", "")
            }, separators=(',', ':')).encode()
            req = Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=5)
            cookie = resp.headers.get("Set-Cookie", "")
            for part in cookie.split(";"):
                part = part.strip()
                if part.startswith("a_secure_password_session="):
                    self._session = part.split("=", 1)[1]
                    return True
        except Exception:
            pass
        return False

    def _fetch_with_session(self, url):
        """Fetch URL with a_secure_password session cookie."""
        req = Request(url)
        req.add_header("Cookie", "a_secure_password_session=" + (self._session or ""))
        try:
            resp = urlopen(req, timeout=5)
            if resp.status == 200:
                return resp.read()
        except Exception:
            pass
        return None

    def _fetch_basic_auth(self, url, auth):
        """Fetch with HTTP basic auth."""
        import base64
        creds = base64.b64encode("{}:{}".format(
            auth.get("username", ""), auth.get("password", "")
        ).encode()).decode()
        req = Request(url)
        req.add_header("Authorization", "Basic " + creds)
        try:
            resp = urlopen(req, timeout=5)
            if resp.status == 200:
                return resp.read()
        except Exception:
            pass
        return None

    def _fetch_url(self, url):
        """Fetch URL with no auth."""
        try:
            resp = urlopen(url, timeout=5)
            if resp.status == 200:
                return resp.read()
        except Exception:
            pass
        return None

    def _fetch_ffmpeg(self, stream_url):
        """Extract a single JPEG frame from a stream using ffmpeg."""
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", stream_url,
                    "-frames:v", "1",
                    "-f", "image2", "-c:v", "mjpeg",
                    "-q:v", "3",
                    "pipe:1"
                ],
                capture_output=True, timeout=10
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_host(url):
        """Extract host:port from a URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.hostname or ""


_streams = {}
_streams_lock = threading.Lock()

# Case-insensitive camera name lookup
_cameras_lower = {}  # populated by _load_config()


def _resolve_camera(name):
    """Resolve camera name (case-insensitive). Returns (canonical_name, config) or (None, None)."""
    cam = _CAMERAS.get(name)
    if cam:
        return name, cam
    canonical = _cameras_lower.get(name.lower())
    if canonical:
        return canonical, _CAMERAS[canonical]
    return None, None


def camera_snapshot(name, max_w=None, max_h=None):
    """Get latest frame for a camera. Returns (jpeg_bytes, content_type)."""
    name, cam = _resolve_camera(name)
    if not cam:
        return None, None
    with _streams_lock:
        stream = _streams.get(name)
        if stream is None:
            stream = CameraStream(name, cam)
            _streams[name] = stream

    raw = stream.get_frame()
    if raw is None:
        return None, None
    if max_w and max_h:
        return _resize_jpeg(raw, max_w, max_h)
    return raw, "image/jpeg"


def camera_info(name):
    """Return camera info dict for /camera/<name>/info endpoint."""
    name, cam = _resolve_camera(name)
    if not cam:
        return None
    return {
        "name": name,
        "snapshot": bool(cam.get("snapshot")),
        "stream": cam.get("stream", ""),
        "stream_type": cam.get("stream_type", "hls") if cam.get("stream") else "",
        "ptz": bool(cam.get("onvif")),
    }


def _resize_jpeg(data, max_w, max_h):
    """Resize JPEG bytes. Returns (bytes, content_type)."""
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        if img.width <= max_w and img.height <= max_h:
            return data, "image/jpeg"
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        return data, "image/jpeg"


# ── ONVIF PTZ ─────────────────────────────────────────────
# Raw SOAP implementation — no external dependencies.
# Supports ContinuousMove (pan/tilt/zoom) and Stop.
# WSSE UsernameToken (Digest) authentication.

import hashlib
import base64
from datetime import datetime, timezone

_PTZ_NS = "http://www.onvif.org/ver20/ptz/wsdl"
_MEDIA_NS = "http://www.onvif.org/ver10/media/wsdl"
_SCHEMA_NS = "http://www.onvif.org/ver10/schema"
_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
_WSSE_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
_WSU_NS = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
_PASSWORD_TYPE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest"


def _wsse_header(username, password):
    """Build WSSE UsernameToken (Digest) SOAP header."""
    nonce_raw = os.urandom(16)
    nonce_b64 = base64.b64encode(nonce_raw).decode()
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    digest_raw = hashlib.sha1(nonce_raw + created.encode() + password.encode()).digest()
    digest_b64 = base64.b64encode(digest_raw).decode()
    return """<wsse:Security xmlns:wsse="{wsse}" xmlns:wsu="{wsu}">
      <wsse:UsernameToken>
        <wsse:Username>{user}</wsse:Username>
        <wsse:Password Type="{ptype}">{digest}</wsse:Password>
        <wsse:Nonce>{nonce}</wsse:Nonce>
        <wsu:Created>{created}</wsu:Created>
      </wsse:UsernameToken>
    </wsse:Security>""".format(
        wsse=_WSSE_NS, wsu=_WSU_NS, user=username,
        ptype=_PASSWORD_TYPE, digest=digest_b64,
        nonce=nonce_b64, created=created
    )


def _soap_envelope(header_xml, body_xml):
    """Wrap header + body in a SOAP envelope."""
    return """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="{soap}">
  <s:Header>{header}</s:Header>
  <s:Body>{body}</s:Body>
</s:Envelope>""".format(soap=_SOAP_NS, header=header_xml, body=body_xml)


class OnvifPtz:
    """ONVIF PTZ controller using raw SOAP calls."""

    def __init__(self, host, port, username, password):
        self._host = host
        self._port = port
        self._user = username
        self._pass = password
        self._profile_token = None

    def _url(self, service):
        return "http://{}:{}/onvif/{}".format(self._host, self._port, service)

    def _call(self, service, body_xml):
        """Send a SOAP request, return response body text."""
        header = _wsse_header(self._user, self._pass)
        envelope = _soap_envelope(header, body_xml)
        data = envelope.encode("utf-8")
        req = Request(self._url(service), data=data, method="POST")
        req.add_header("Content-Type", "application/soap+xml; charset=utf-8")
        try:
            resp = urlopen(req, timeout=5)
            return resp.read().decode("utf-8")
        except Exception as e:
            return None

    def _get_profile_token(self):
        """Fetch the first media profile token."""
        if self._profile_token:
            return self._profile_token
        body = '<trt:GetProfiles xmlns:trt="{}"/>'.format(_MEDIA_NS)
        resp = self._call("media_service", body)
        if not resp:
            return None
        # Simple XML parse — find first token attribute
        import re
        m = re.search(r'<[^>]*Profiles[^>]*\btoken="([^"]+)"', resp)
        if m:
            self._profile_token = m.group(1)
            return self._profile_token
        return None

    def continuous_move(self, pan=0.0, tilt=0.0, zoom=0.0):
        """Start continuous pan/tilt/zoom movement."""
        token = self._get_profile_token()
        if not token:
            return False
        body = """<tptz:ContinuousMove xmlns:tptz="{ptz}" xmlns:tt="{schema}">
          <tptz:ProfileToken>{token}</tptz:ProfileToken>
          <tptz:Velocity>
            <tt:PanTilt x="{pan}" y="{tilt}"/>
            <tt:Zoom x="{zoom}"/>
          </tptz:Velocity>
        </tptz:ContinuousMove>""".format(
            ptz=_PTZ_NS, schema=_SCHEMA_NS, token=token,
            pan=pan, tilt=tilt, zoom=zoom
        )
        return self._call("ptz_service", body) is not None

    def stop(self):
        """Stop all PTZ movement."""
        token = self._get_profile_token()
        if not token:
            return False
        body = """<tptz:Stop xmlns:tptz="{ptz}">
          <tptz:ProfileToken>{token}</tptz:ProfileToken>
          <tptz:PanTilt>true</tptz:PanTilt>
          <tptz:Zoom>true</tptz:Zoom>
        </tptz:Stop>""".format(ptz=_PTZ_NS, token=token)
        return self._call("ptz_service", body) is not None

    def move(self, direction, speed=0.5):
        """Convenience: start moving in a named direction."""
        dirs = {
            "left":     (-speed, 0, 0),
            "right":    (speed, 0, 0),
            "up":       (0, speed, 0),
            "down":     (0, -speed, 0),
            "zoomIn":   (0, 0, speed),
            "zoomOut":  (0, 0, -speed),
        }
        vals = dirs.get(direction)
        if not vals:
            return False
        return self.continuous_move(*vals)


_ptz_controllers = {}
_ptz_lock = threading.Lock()


def get_ptz(name):
    """Get or create an OnvifPtz controller for a camera. Returns None if no ONVIF config."""
    name, cam = _resolve_camera(name)
    if not cam:
        return None
    onvif = cam.get("onvif")
    if not onvif:
        return None
    with _ptz_lock:
        ctrl = _ptz_controllers.get(name)
        if ctrl is None:
            ctrl = OnvifPtz(
                onvif.get("host", ""),
                onvif.get("port", 80),
                onvif.get("username", "admin"),
                onvif.get("password", ""),
            )
            _ptz_controllers[name] = ctrl
        return ctrl


def handle_ptz(name, body):
    """Handle a PTZ command. body is parsed JSON: {action, direction, speed}."""
    ctrl = get_ptz(name)
    if not ctrl:
        return False, "No ONVIF config for camera: {}".format(name)
    action = body.get("action", "")
    if action == "move":
        direction = body.get("direction", "")
        speed = float(body.get("speed", 0.5))
        ok = ctrl.move(direction, speed)
        return ok, "" if ok else "Move failed"
    elif action == "stop":
        ok = ctrl.stop()
        return ok, "" if ok else "Stop failed"
    else:
        return False, "Unknown action: {}".format(action)


# ── HA data cache ─────────────────────────────────────────

_ha_cache = {}
_ha_cache_ttl = 120
_ha_lock = threading.Lock()


def _ha_get(path):
    """GET from HA REST API. Returns parsed JSON or None."""
    if not HA_URL or not HA_TOKEN:
        return None
    url = HA_URL + path
    req = Request(url)
    req.add_header("Authorization", "Bearer " + HA_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        resp = urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception:
        return None


def _ha_post(path, body, return_response=False):
    """POST to HA REST API. Returns parsed JSON or None."""
    if not HA_URL or not HA_TOKEN:
        return None
    url = HA_URL + path
    if return_response:
        url += "?return_response"
    data = json.dumps(body).encode()
    req = Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + HA_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        resp = urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception:
        return None


def _cached(key, fetch_fn):
    """Return cached text or call fetch_fn to refresh."""
    with _ha_lock:
        entry = _ha_cache.get(key)
        if entry and (time.time() - entry["ts"]) < _ha_cache_ttl:
            return entry["text"]
    text = fetch_fn() or ""
    with _ha_lock:
        _ha_cache[key] = {"text": text, "ts": time.time()}
    return text


def ha_weather():
    def fetch():
        data = _ha_get("/api/states/weather.forecast_home")
        if not data:
            return ""
        a = data.get("attributes", {})
        temp = a.get("temperature")
        unit = a.get("temperature_unit", "\u00b0F")
        cond = (data.get("state", "") or "").replace("-", " ").replace("_", " ").title()
        humid = a.get("humidity")
        parts = []
        if temp is not None:
            parts.append("{}{}".format(round(temp), unit))
        if cond:
            parts.append(cond)
        if humid is not None:
            parts.append("{}% humidity".format(humid))
        return "  \u00b7  ".join(parts)
    return _cached("weather", fetch)


def ha_forecast():
    def fetch():
        data = _ha_post("/api/services/weather/get_forecasts", {
            "type": "daily",
            "entity_id": "weather.forecast_home"
        }, return_response=True)
        if not data:
            return ""
        forecasts = []
        resp = data.get("service_response", data.get("response", data))
        for v in (resp.values() if isinstance(resp, dict) else []):
            if isinstance(v, dict) and "forecast" in v:
                forecasts = v["forecast"]
                break
        if not forecasts:
            return ""
        days = forecasts[:3]
        parts = []
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for d in days:
            dt = d.get("datetime", "")
            try:
                from datetime import datetime
                dn = day_names[datetime.fromisoformat(dt.replace("Z", "+00:00")).weekday()]
            except Exception:
                dn = "?"
            hi = round(d.get("temperature", 0))
            lo = round(d.get("templow", 0))
            parts.append("{} {}/{}".format(dn, hi, lo))
        return "  \u00b7  ".join(parts)
    return _cached("forecast", fetch)


def ha_thermostat():
    def fetch():
        data = _ha_get("/api/states/climate.upper_level")
        if not data:
            return ""
        a = data.get("attributes", {})
        current = a.get("current_temperature")
        action = a.get("hvac_action", data.get("state", ""))
        target = a.get("temperature")
        if target is None:
            hi = a.get("target_temp_high")
            lo = a.get("target_temp_low")
            if hi is not None and lo is not None:
                target = "{}-{}".format(round(lo), round(hi))
        else:
            target = str(round(target))
        parts = []
        if current is not None:
            parts.append("{}\u00b0".format(round(current)))
        if action:
            parts.append(action.replace("_", " ").title())
        if target and data.get("state") != "off":
            parts.append("Set: {}\u00b0".format(target))
        return "  \u00b7  ".join(parts)
    return _cached("thermostat", fetch)


def ha_next_event():
    def fetch():
        if not HA_URL or not HA_TOKEN:
            return ""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        calendars = [
            "calendar.home",
            "calendar.mikecirioli_gmail_com",
            "calendar.birthdays",
            "calendar.mcirioli_cloudbees_com",
        ]
        best = None
        best_start = None
        for cal in calendars:
            state = _ha_get("/api/states/" + cal)
            if not state or state.get("state") == "unavailable":
                continue
            data = _ha_post("/api/services/calendar/get_events", {
                "entity_id": cal,
                "duration": {"days": 7}
            }, return_response=True)
            if not data:
                continue
            resp = data.get("service_response", data.get("response", data))
            events = []
            for v in (resp.values() if isinstance(resp, dict) else []):
                if isinstance(v, dict) and "events" in v:
                    events = v["events"]
                    break
            for ev in events:
                st = ev.get("start")
                if not st:
                    continue
                try:
                    if "T" in st:
                        evt_dt = datetime.fromisoformat(st.replace("Z", "+00:00"))
                    else:
                        evt_dt = datetime.fromisoformat(st + "T00:00:00+00:00")
                except Exception:
                    continue
                if evt_dt < now:
                    continue
                if best_start is None or evt_dt < best_start:
                    best_start = evt_dt
                    best = ev
        if not best:
            return ""
        title = best.get("summary", best.get("title", ""))
        diff = best_start - now
        total_min = int(diff.total_seconds() / 60)
        if total_min < 60:
            prefix = "In {}min".format(total_min)
        elif total_min < 1440:
            h = total_min // 60
            m = total_min % 60
            prefix = "In {}h{}".format(h, " {}m".format(m) if m else "")
        else:
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            prefix = day_names[best_start.weekday()]
        return "{}  \u00b7  {}".format(prefix, title)
    return _cached("event", fetch)


# ── HTML template ─────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Photo Frame</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #000; overflow: hidden; width: 100vw; height: 100vh; }
  #photo {
    width: 100vw; height: 100vh;
    object-fit: contain;
    opacity: 0;
    transition: opacity 1.5s ease;
  }
  #photo.visible { opacity: 1; }
  .overlay {
    position: fixed;
    color: #fff; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    text-align: right; z-index: 10;
    text-shadow: 0 2px 8px rgba(0,0,0,0.8);
    background: rgba(0,0,0,0.35);
    padding: 16px 24px;
    border-radius: 14px;
  }
  .overlay .clock { font-size: 36px; font-weight: 300; }
  .overlay .date { font-size: 16px; opacity: 0.8; margin-top: 2px; }
  .overlay .title { font-size: 14px; opacity: 0.6; margin-top: 6px; }
  .overlay .weather { margin-top: 8px; font-size: 14px; opacity: 0.85; }
  .overlay .weather .temp { font-size: 20px; font-weight: 400; }
  .overlay .forecast { margin-top: 6px; font-size: 12px; opacity: 0.7; }
  .overlay .forecast span { margin-left: 10px; }
</style>
</head>
<body>
<img id="photo" alt="">
<div class="overlay" id="overlay">
  <div class="clock" id="clock"></div>
  <div class="date" id="date"></div>
  TITLE_PLACEHOLDER
  <div class="weather" id="weather" style="display:none"></div>
  <div class="forecast" id="forecast" style="display:none"></div>
</div>
<script>
  var REFRESH = REFRESH_PLACEHOLDER;
  var photo = document.getElementById('photo');
  var overlay = document.getElementById('overlay');
  var BLANK = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

  function getParam(name) {
    var m = location.search.match(new RegExp('[?&]' + name + '=([^&]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }
  var HA_URL = getParam('ha_url') || '';
  var HA_TOKEN = getParam('token') || '';
  var WEATHER_ENTITY = getParam('weather') || 'weather.forecast_home';

  function loadPhoto() {
    photo.classList.remove('visible');
    setTimeout(function() {
      photo.onload = function() { photo.classList.add('visible'); };
      photo.onerror = function() { setTimeout(loadPhoto, 5000); };
      photo.src = '/random?t=' + Date.now();
    }, 1600);
  }

  function updateClock() {
    var now = new Date();
    document.getElementById('clock').textContent =
      now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('date').textContent =
      now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
  }

  var bx = 40, by = 40, bdx = 1, bdy = 0.7;
  setInterval(function() {
    var ow = overlay.offsetWidth || 200;
    var oh = overlay.offsetHeight || 150;
    var maxX = window.innerWidth - ow - 20;
    var maxY = window.innerHeight - oh - 20;
    bx += bdx; by += bdy;
    if (bx <= 20 || bx >= maxX) bdx = -bdx;
    if (by <= 20 || by >= maxY) bdy = -bdy;
    bx = Math.max(20, Math.min(bx, maxX));
    by = Math.max(20, Math.min(by, maxY));
    overlay.style.left = bx + 'px';
    overlay.style.top = by + 'px';
  }, 1000);

  function fetchWeather() {
    if (!HA_URL || !HA_TOKEN) return;
    var headers = { 'Authorization': 'Bearer ' + HA_TOKEN, 'Content-Type': 'application/json' };
    fetch(HA_URL + '/api/states/' + WEATHER_ENTITY, { headers: headers })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var a = data.attributes || {};
        var weatherEl = document.getElementById('weather');
        weatherEl.innerHTML = '<span class="temp">' + Math.round(a.temperature || 0) + '&deg;</span> ' + (data.state || '');
        weatherEl.style.display = 'block';
      })
      .catch(function() {});
    fetch(HA_URL + '/api/services/weather/get_forecasts', {
      method: 'POST', headers: headers,
      body: JSON.stringify({ type: 'daily', entity_id: WEATHER_ENTITY })
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var forecasts = (data && data[WEATHER_ENTITY] && data[WEATHER_ENTITY].forecast) || [];
        if (forecasts.length === 0) return;
        var days = forecasts.slice(0, 3);
        var html = '';
        var dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        for (var i = 0; i < days.length; i++) {
          var d = new Date(days[i].datetime);
          var hi = Math.round(days[i].temperature || 0);
          var lo = Math.round(days[i].templow || 0);
          html += '<span>' + dayNames[d.getDay()] + ' ' + hi + '/' + lo + '&deg;</span>';
        }
        var forecastEl = document.getElementById('forecast');
        forecastEl.innerHTML = html;
        forecastEl.style.display = 'block';
      })
      .catch(function() {});
  }

  loadPhoto();
  setInterval(loadPhoto, REFRESH * 1000);
  updateClock();
  setInterval(updateClock, 30000);
  fetchWeather();
  setInterval(fetchWeather, 300000);
</script>
</body>
</html>"""


# ── HTTP handler ──────────────────────────────────────────

class PhotoHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        """Handle CORS preflight for POST endpoints."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.endswith("/ptz") and path.startswith("/camera/"):
            self.handle_ptz_request(path)
        else:
            self.send_error(404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/index.html":
            self.serve_html()
        elif path == "/random":
            self.serve_random(parsed)
        elif path == "/camera/list":
            self.serve_camera_list()
        elif path.endswith("/info") and path.startswith("/camera/"):
            self.serve_camera_info(path)
        elif path.startswith("/camera/"):
            self.serve_camera(path, parsed)
        elif path.startswith("/ha/"):
            self.serve_ha(path)
        elif path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

    def serve_ha(self, path):
        handlers = {
            "/ha/weather": ha_weather,
            "/ha/forecast": ha_forecast,
            "/ha/thermostat": ha_thermostat,
            "/ha/event": ha_next_event,
        }
        fn = handlers.get(path)
        if not fn:
            self.send_error(404)
            return
        if not HA_URL or not HA_TOKEN:
            self.send_error(503, "HA_URL/HA_TOKEN not configured")
            return
        text = fn()
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_camera_list(self):
        names = sorted(_CAMERAS.keys())
        data = json.dumps(names).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_camera_info(self, path):
        # /camera/front-door/info -> name = "front-door"
        name = path[len("/camera/"):].rsplit("/info", 1)[0]
        info = camera_info(name)
        if not info:
            self.send_error(404, "Camera not found: {}".format(name))
            return
        data = json.dumps(info).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_ptz_request(self, path):
        """Handle POST /camera/<name>/ptz — PTZ control."""
        name = path[len("/camera/"):].rsplit("/ptz", 1)[0]
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            raw = self.rfile.read(content_len)
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
        else:
            body = {}
        ok, err = handle_ptz(name, body)
        if ok:
            resp = json.dumps({"ok": True}).encode()
            self.send_response(200)
        else:
            resp = json.dumps({"ok": False, "error": err}).encode()
            self.send_response(400 if "Unknown" in err else 502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def serve_camera(self, path, parsed):
        name = path[len("/camera/"):]
        if not name:
            self.send_error(400, "Missing camera name")
            return
        params = parse_qs(parsed.query)
        max_w = int(params["w"][0]) if "w" in params else None
        max_h = int(params["h"][0]) if "h" in params else None
        data, ct = camera_snapshot(name, max_w, max_h)
        if not data:
            self.send_error(502, "Failed to fetch snapshot for {}".format(name))
            return
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_html(self):
        title_div = '<div class="title">{}</div>'.format(TITLE) if TITLE else ""
        html = HTML_TEMPLATE.replace("REFRESH_PLACEHOLDER", str(REFRESH))
        html = html.replace("TITLE_PLACEHOLDER", title_div)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_random(self, parsed):
        photos = get_photos()
        if not photos:
            self.send_error(503, "No photos found in {}".format(PHOTO_DIR))
            return
        path = random.choice(photos)
        params = parse_qs(parsed.query)
        if "w" in params or "h" in params:
            max_w = int(params.get("w", [1280])[0])
            max_h = int(params.get("h", [800])[0])
            data, ct = resize_image(path, max_w, max_h)
            if data:
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Cache-Control", "no-cache, no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(500, "Failed to read file")


if __name__ == "__main__":
    _load_config()
    photos = get_photos()
    print(f"3-bad-dogs server: {len(photos)} photos in {PHOTO_DIR}, port {PORT}, refresh {REFRESH}s")
    if not photos:
        print(f"WARNING: no images found in {PHOTO_DIR}", file=sys.stderr)
    if _CAMERAS:
        print(f"  cameras: {', '.join(sorted(_CAMERAS.keys()))}")
        for name, cam in _CAMERAS.items():
            has_snap = "snapshot" if cam.get("snapshot") else ""
            has_stream = "stream" if cam.get("stream") else ""
            sources = " + ".join(filter(None, [has_snap, has_stream]))
            print(f"    {name}: {sources}")
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(("0.0.0.0", PORT), PhotoHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
