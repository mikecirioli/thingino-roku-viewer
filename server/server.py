#!/usr/bin/env python3
# Copyright (c) 2026 Mike Cirioli. Licensed under CC BY-NC-SA 4.0.
# https://creativecommons.org/licenses/by-nc-sa/4.0/
"""
3 Bad Dogs — Photo & Camera Server

Minimal HTTP server that serves random photos, camera snapshots
(thingino session auth or basic auth), and optional HA/Frigate proxying.

Endpoints:
  /              HTML page — full-screen photo frame with auto-refresh and clock overlay
  /random        Returns a random image file (JPEG/PNG/WebP) with proper content-type
  /random?w=1280&h=800  Resize on the fly (requires Pillow)
  /camera/list   JSON array of available camera names
  /camera/<name> JPEG snapshot (optional ?w=&h= resize)
  /camera/<name>/info  JSON: {name, snapshot, stream, stream_type}
  /frigate/*     Proxy to Frigate API (requires FRIGATE_URL env var, adds CORS headers)
  /ha/weather    Plain text: current weather summary
  /ha/forecast   Plain text: 3-day forecast
  /ha/event      Plain text: next calendar event
  /ha/thermostat Plain text: thermostat status
  /health        Health check

Camera configuration (in order of precedence):
  1. cameras.yaml file (CAMERAS_FILE env var, default: /config/cameras.yaml)
  2. CAMERAS env var (JSON object, backward compatible)

cameras.yaml format:
  cameras:
    front-door:
      snapshot: http://192.168.1.55/x/ch0.jpg
      auth:
        type: thingino          # "thingino" or "basic"
        username: admin
        password: front-door
    camera-3:
      stream: http://192.168.1.207:1984/api/stream.m3u8?src=camera-3_main
      stream_type: hls          # "hls" (default if stream present)
    living-room:
      snapshot: http://192.168.1.106/x/ch0.jpg
      stream: http://go2rtc:1984/api/stream.m3u8?src=living-room_main
      auth:
        type: thingino
        username: admin
        password: password456

Environment variables:
  PHOTO_DIR      Directory containing images (default: /media)
  PORT           Listen port (default: 8099)
  REFRESH        Seconds between photo changes on the HTML page (default: 30)
  TITLE          Page title / overlay text (default: empty)
  CAMERAS_FILE   Path to cameras.yaml (default: /config/cameras.yaml)
  CAMERAS        JSON object of thingino cameras (legacy, backward compat)
  CAMERA_IDLE    Seconds with no requests before closing a camera stream (default: 30)
  FRIGATE_URL    Frigate base URL for proxy (e.g. http://frigate:5000)
  GO2RTC_URL     go2rtc base URL for camera list discovery (e.g. http://go2rtc:1984)
  HA_URL         Home Assistant URL (e.g. http://homeassistant:8123)
  HA_TOKEN       Long-lived access token for HA REST API

Usage:
  python3 server.py
  docker run -v /path/to/photos:/media -p 8099:8099 3-bad-dogs-server
"""

import os
import sys
import random
import mimetypes
import json
import time
import threading
import subprocess
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from io import BytesIO

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, Request, URLError

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/media")
PORT = int(os.environ.get("PORT", "8099"))
REFRESH = int(os.environ.get("REFRESH", "30"))
TITLE = os.environ.get("TITLE", "")
CAMERAS_FILE = os.environ.get("CAMERAS_FILE", "/config/cameras.yaml")
FRIGATE_URL = os.environ.get("FRIGATE_URL", "")
GO2RTC_URL = os.environ.get("GO2RTC_URL", "").rstrip("/")
CAMERA_IDLE = int(os.environ.get("CAMERA_IDLE", "30"))
HA_URL = os.environ.get("HA_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
TIMELAPSE_STORAGE_PATH = os.environ.get("TIMELAPSE_STORAGE_PATH", "/data/timelapse")
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# ── Timelapse Capturer ──────────────────────────────────

class TimelapseCapturer:
    """Manages background snapshot capture for multiple cameras."""

    def __init__(self, cameras_config):
        self._cameras = cameras_config
        self._timers = {}
        self._thread = None

    def start(self):
        """Start the background capture thread."""
        if self._thread is not None:
            return
        print("  timelapse: starting capture service")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Main loop to schedule and trigger camera snapshots."""
        for name, config in self._cameras.items():
            tl_config = config.get("timelapse")
            if tl_config and tl_config.get("enabled"):
                self._schedule_next_capture(name, tl_config)
        
        # Keep thread alive to manage timers
        while True:
            time.sleep(1)

    def _schedule_next_capture(self, name, tl_config):
        """Schedules the next snapshot for a given camera."""
        interval = tl_config.get("interval", 60)
        timer = threading.Timer(interval, self._capture_and_reschedule, args=[name, tl_config])
        self._timers[name] = timer
        timer.start()

    def _capture_and_reschedule(self, name, tl_config):
        """The function executed by the timer."""
        self._capture_frame(name, tl_config)
        self._schedule_next_capture(name, tl_config)

    def _capture_frame(self, name, tl_config):
        """Fetches and saves a single frame for a camera."""
        source = tl_config.get("source", "snapshot")
        cam_config = self._cameras.get(name, {})
        
        print(f"  timelapse: capturing frame for '{name}' (source: {source})")

        raw_frame = None
        if source == "stream":
            stream_url = cam_config.get("stream")
            if stream_url:
                raw_frame = self._fetch_ffmpeg(stream_url)
        else: # Default to snapshot
            snapshot_url = cam_config.get("snapshot")
            if snapshot_url:
                # Use a temporary CameraStream instance to leverage its auth logic
                stream = CameraStream(name, cam_config)
                raw_frame = stream._fetch_frame()

        if raw_frame:
            self._save_frame(name, raw_frame)

    def _save_frame(self, name, frame_bytes):
        """Saves a frame to the disk."""
        try:
            cam_path = os.path.join(TIMELAPSE_STORAGE_PATH, name)
            os.makedirs(cam_path, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = os.path.join(cam_path, f"{timestamp}.jpg")
            with open(filename, "wb") as f:
                f.write(frame_bytes)
        except Exception as e:
            print(f"WARNING: timelapse failed to save frame for '{name}': {e}")

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
        except Exception as e:
            print(f"WARNING: ffmpeg capture failed for '{stream_url}': {e}")
        return None

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


def _load_cameras():
    """Load camera config from YAML file or CAMERAS env var."""
    global _CAMERAS

    # Try YAML file first
    if os.path.isfile(CAMERAS_FILE):
        try:
            import yaml
            with open(CAMERAS_FILE) as f:
                cfg = yaml.safe_load(f)
            if cfg and "cameras" in cfg:
                _CAMERAS = cfg["cameras"]
                print(f"  cameras: loaded {len(_CAMERAS)} from {CAMERAS_FILE}")
                return
        except ImportError:
            print("WARNING: PyYAML not installed, cannot read cameras.yaml")
        except Exception as e:
            print(f"WARNING: failed to parse {CAMERAS_FILE}: {e}")

    # Fall back to CAMERAS env var (legacy JSON format)
    cameras_env = os.environ.get("CAMERAS", "")
    if cameras_env:
        try:
            legacy = json.loads(cameras_env)
            # Convert legacy format: {name: {ip, user, pass}} -> unified format
            for name, cam in legacy.items():
                _CAMERAS[name] = {
                    "snapshot": "http://{}/x/ch0.jpg".format(cam["ip"]),
                    "auth": {
                        "type": "thingino",
                        "username": cam.get("user", "admin"),
                        "password": cam.get("pass", ""),
                    }
                }
            print(f"  cameras: loaded {len(_CAMERAS)} from CAMERAS env var (legacy)")
        except json.JSONDecodeError:
            print("WARNING: CAMERAS env var is not valid JSON, ignoring")


def _go2rtc_streams():
    """Fetch stream names from go2rtc, return list of base camera names."""
    if not GO2RTC_URL:
        return []
    try:
        resp = urlopen(GO2RTC_URL + "/api/streams", timeout=5)
        data = json.loads(resp.read())
        names = set()
        for key in data:
            base = key.rsplit("_main", 1)[0].rsplit("_sub", 1)[0]
            names.add(base)
        return sorted(names)
    except Exception:
        return []


# ── Camera streams ───────────────────────────────────────

class CameraStream:
    """Polls a camera for live JPEG frames.

    Supports snapshot sources:
      - Direct HTTP snapshot URL (thingino /x/ch0.jpg with session auth, or basic auth)
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
            if auth_type == "thingino":
                return self._fetch_thingino(snapshot_url, auth)
            elif auth_type == "basic":
                return self._fetch_basic_auth(snapshot_url, auth)
            else:
                return self._fetch_url(snapshot_url)

        return None

    def _fetch_thingino(self, snapshot_url, auth):
        """Fetch snapshot with thingino session auth."""
        ip = self._extract_host(snapshot_url)
        if not self._session:
            if not self._login_thingino(ip, auth):
                return None
        raw = self._fetch_with_session(snapshot_url)
        if raw:
            return raw
        # Session expired — retry
        if self._login_thingino(ip, auth):
            return self._fetch_with_session(snapshot_url)
        return None

    def _login_thingino(self, ip, auth):
        """Get a thingino session cookie."""
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
                if part.startswith("thingino_session="):
                    self._session = part.split("=", 1)[1]
                    return True
        except Exception:
            pass
        return False

    def _fetch_with_session(self, url):
        """Fetch URL with thingino session cookie."""
        req = Request(url)
        req.add_header("Cookie", "thingino_session=" + (self._session or ""))
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

    @staticmethod
    def _extract_host(url):
        """Extract host:port from a URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.hostname or ""


_streams = {}
_streams_lock = threading.Lock()


def camera_snapshot(name, max_w=None, max_h=None):
    """Get latest frame for a camera. Returns (jpeg_bytes, content_type)."""
    cam = _CAMERAS.get(name)
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
    cam = _CAMERAS.get(name)
    if not cam:
        return None
    
    stream_url = cam.get("stream", "")

    return {
        "name": name,
        "snapshot": cam.get("snapshot", ""),
        "stream": stream_url,
        "stream_type": cam.get("stream_type", "hls") if stream_url else "",
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

def _onvif_ptz(cam_config, action, direction, speed=1.0):
    """Send ONVIF PTZ command to a camera. Returns True on success."""
    onvif = cam_config.get("onvif")
    if not onvif:
        return False

    host = onvif.get("host", "")
    port = onvif.get("port", 80)
    user = onvif.get("username", "")
    passwd = onvif.get("password", "")

    if not host:
        return False

    # Map direction to ONVIF velocity vectors
    velocity_map = {
        "up":       (0, speed, 0),
        "down":     (0, -speed, 0),
        "left":     (-speed, 0, 0),
        "right":    (speed, 0, 0),
        "zoomIn":   (0, 0, speed),
        "zoomOut":  (0, 0, -speed),
    }
    vx, vy, vz = velocity_map.get(direction, (0, 0, 0))

    if action == "stop":
        soap_body = '''<ContinuousMove xmlns="http://www.onvif.org/ver20/ptz/wsdl">
            <ProfileToken>000</ProfileToken>
            <Velocity><PanTilt x="0" y="0" xmlns="http://www.onvif.org/ver10/schema"/>
            <Zoom x="0" xmlns="http://www.onvif.org/ver10/schema"/></Velocity>
        </ContinuousMove>'''
    else:
        soap_body = '''<ContinuousMove xmlns="http://www.onvif.org/ver20/ptz/wsdl">
            <ProfileToken>000</ProfileToken>
            <Velocity><PanTilt x="{}" y="{}" xmlns="http://www.onvif.org/ver10/schema"/>
            <Zoom x="{}" xmlns="http://www.onvif.org/ver10/schema"/></Velocity>
        </ContinuousMove>'''.format(vx, vy, vz)

    # Build SOAP envelope with WS-Security UsernameToken
    import hashlib, base64
    from datetime import datetime, timezone
    nonce_raw = os.urandom(16)
    nonce_b64 = base64.b64encode(nonce_raw).decode()
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest_raw = hashlib.sha1(nonce_raw + created.encode() + passwd.encode()).digest()
    digest_b64 = base64.b64encode(digest_raw).decode()

    envelope = '''<?xml version="1.0" encoding="utf-8"?>
    <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
      <s:Header>
        <Security xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
          <UsernameToken>
            <Username>{user}</Username>
            <Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</Password>
            <Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce}</Nonce>
            <Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">{created}</Created>
          </UsernameToken>
        </Security>
      </s:Header>
      <s:Body>{body}</s:Body>
    </s:Envelope>'''.format(user=user, digest=digest_b64, nonce=nonce_b64, created=created, body=soap_body)

    try:
        url = "http://{}:{}/onvif/ptz_service".format(host, port)
        data = envelope.encode("utf-8")
        req = Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/soap+xml; charset=utf-8")
        resp = urlopen(req, timeout=5)
        return resp.status == 200
    except Exception as e:
        print("ONVIF PTZ error: {}".format(e))
        return False


class PhotoHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.endswith("/ptz") and path.startswith("/camera/"):
            self.handle_ptz(path)
        elif path == "/timelapse/generate":
            self.handle_timelapse_generate()
        else:
            self.send_error(404)

    def handle_timelapse_generate(self):
        """Handle a request to generate a new timelapse video."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        cameras = data.get("cameras", [])
        start_time_str = data.get("start_time")
        end_time_str = data.get("end_time")
        fps = int(data.get("fps", 10))

        if not cameras or not start_time_str or not end_time_str:
            self.send_error(400, "Missing required parameters")
            return

        # --- Frame filtering and collection ---
        all_frames = []
        for cam_name in cameras:
            cam_dir = os.path.join(TIMELAPSE_STORAGE_PATH, cam_name)
            try:
                for fname in os.listdir(cam_dir):
                    if fname.endswith(".jpg"):
                        # Filename format: YYYY-MM-DD_HH-MM-SS.jpg
                        # Compare as strings for simplicity
                        f_ts = fname.replace("_", " ").replace(".jpg", "")
                        if start_time_str <= f_ts <= end_time_str:
                            all_frames.append(os.path.join(cam_dir, fname))
            except FileNotFoundError:
                continue # Camera directory may not exist
        
        if not all_frames:
            self.send_error(404, "No frames found in the specified time range")
            return
            
        all_frames.sort()

        # --- FFmpeg execution ---
        video_dir = os.path.join(TIMELAPSE_STORAGE_PATH, "videos")
        os.makedirs(video_dir, exist_ok=True)
        
        start_ts_str = os.path.basename(all_frames[0]).replace('.jpg', '')
        end_ts_str = os.path.basename(all_frames[-1]).replace('.jpg', '')
        output_filename = f"{start_ts_str}-to-{end_ts_str}-timelapse.mp4"
        output_path = os.path.join(video_dir, output_filename)
        
        # Create a temporary file with the list of input frames
        input_list_path = os.path.join(video_dir, "input_list.txt")
        with open(input_list_path, "w") as f:
            for frame_path in all_frames:
                f.write(f"file '{frame_path}'\n")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", input_list_path,
                    "-r", str(fps),
                    "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                    output_path
                ],
                check=True, capture_output=True, timeout=300 # 5 min timeout
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"ERROR: ffmpeg failed: {e.stderr.decode() if e.stderr else e}")
            self.send_error(500, "Failed to generate video")
            return
        finally:
            os.remove(input_list_path)

        # --- Respond with success ---
        result = json.dumps({"video_url": f"/timelapse/videos/{output_filename}"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)


    def handle_ptz(self, path):
        name = path[len("/camera/"):].rsplit("/ptz", 1)[0]
        cam = _CAMERAS.get(name)
        if not cam:
            self.send_error(404, "Camera not found: {}".format(name))
            return
        if not cam.get("onvif"):
            self.send_error(400, "Camera {} has no PTZ".format(name))
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        action = data.get("action", "move")
        direction = data.get("direction", "stop")
        speed = float(data.get("speed", 1.0))

        ok = _onvif_ptz(cam, action, direction, speed)
        result = json.dumps({"ok": ok}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/index.html":
            self.serve_html()
        elif path == "/web":
            self.serve_web_ui()
        elif path == "/random":
            self.serve_random(parsed)
        elif path == "/camera/list":
            self.serve_camera_list()
        elif path == "/camera/all_info":
            self.serve_all_camera_info()
        elif path.endswith("/info") and path.startswith("/camera/"):
            self.serve_camera_info(path)
        elif path.startswith("/camera/"):
            self.serve_camera(path, parsed)
        elif path.startswith("/frigate") and FRIGATE_URL:
            self.proxy_frigate(parsed)
        elif path.startswith("/ha/"):
            self.serve_ha(path)
        elif path == "/timelapse/summary":
            self.serve_timelapse_summary()
        elif path == "/timelapse/videos":
            self.serve_timelapse_video_list()
        elif path.startswith("/timelapse/videos/"):
            self.serve_timelapse_video(path)
        elif path == "/timelapse/frame":
            self.serve_timelapse_frame()
        elif path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

    def serve_timelapse_summary(self):
        """Serve a summary of available timelapse frames for each camera."""
        summary = []
        try:
            for cam_name in os.listdir(TIMELAPSE_STORAGE_PATH):
                cam_dir = os.path.join(TIMELAPSE_STORAGE_PATH, cam_name)
                if not os.path.isdir(cam_dir):
                    continue
                
                frames = sorted([f for f in os.listdir(cam_dir) if f.endswith(".jpg")])
                if not frames:
                    continue

                summary.append({
                    "camera_name": cam_name,
                    "frame_count": len(frames),
                    "first_snapshot_timestamp": frames[0].replace("_", " ").replace(".jpg", ""),
                    "last_snapshot_timestamp": frames[-1].replace("_", " ").replace(".jpg", ""),
                })
        except FileNotFoundError:
            pass # No timelapse data yet, return empty list
        except Exception as e:
            print(f"ERROR: failed to generate timelapse summary: {e}")
            self.send_error(500, "Failed to generate timelapse summary")
            return

        data = json.dumps(summary).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_timelapse_video_list(self):
        """Serve a list of generated timelapse videos with metadata."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        filter_camera = params.get("camera", [None])[0]

        videos = []
        video_dir = os.path.join(TIMELAPSE_STORAGE_PATH, "videos")
        try:
            for filename in sorted(os.listdir(video_dir), reverse=True):
                if not filename.endswith(".mp4"):
                    continue

                if filter_camera and not filename.startswith(filter_camera):
                    # A simple filter assuming filenames might be prefixed with cam name in future
                    # For now, we parse the generated filenames
                    try:
                        # Placeholder for future camera-specific filtering if needed
                        pass
                    except:
                        pass
                
                file_path = os.path.join(video_dir, filename)
                try:
                    # Use ffprobe to get metadata
                    probe = subprocess.run(
                        [
                            "ffprobe", "-v", "error",
                            "-show_entries", "format=duration,size",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            file_path
                        ],
                        capture_output=True, text=True, check=True
                    )
                    duration_str, size_str = probe.stdout.strip().split('\n')
                    
                    videos.append({
                        "filename": filename,
                        "size_mb": round(int(size_str) / (1024 * 1024), 2),
                        "duration_seconds": float(duration_str)
                    })
                except Exception as e:
                    print(f"WARNING: Could not probe video '{filename}': {e}")

        except FileNotFoundError:
            pass # No videos yet
        
        data = json.dumps(videos).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_timelapse_video(self, path):
        """Serve a single timelapse video file."""
        filename = path.split("/")[-1]
        file_path = os.path.join(TIMELAPSE_STORAGE_PATH, "videos", filename)

        if not os.path.isfile(file_path):
            self.send_error(404, "Video not found")
            return
        
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"ERROR: failed to serve video '{file_path}': {e}")
            self.send_error(500, "Failed to serve video")

    def serve_timelapse_frame(self):
        """Serve the closest frame to a given timestamp for a camera."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        camera_name = params.get("camera", [None])[0]
        timestamp_str = params.get("timestamp", [None])[0]

        if not camera_name or not timestamp_str:
            self.send_error(400, "Missing 'camera' or 'timestamp' parameter")
            return

        cam_dir = os.path.join(TIMELAPSE_STORAGE_PATH, camera_name)
        try:
            frames = sorted([f for f in os.listdir(cam_dir) if f.endswith(".jpg")])
            if not frames:
                self.send_error(404, "No frames found for camera")
                return

            # Find the closest frame. Filenames are like 'YYYY-MM-DD_HH-MM-SS.jpg'
            # The requested timestamp is ISO format. We can do a string comparison.
            target_ts = timestamp_str.replace("T", " ").split(".")[0]
            
            # This is a simple linear search. For huge numbers of files, a binary search would be better,
            # but for thousands of frames this will be fast enough.
            best_frame = min(frames, key=lambda f: abs(datetime.fromisoformat(f.replace("_", " ").replace(".jpg","")) - datetime.fromisoformat(target_ts)))
            
            frame_path = os.path.join(cam_dir, best_frame)
            with open(frame_path, "rb") as f:
                data = f.read()
            
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        except FileNotFoundError:
            self.send_error(404, "No frames found for camera")
        except Exception as e:
            print(f"ERROR: failed to serve frame: {e}")
            self.send_error(500, "Failed to serve frame")

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
        names = sorted(set(list(_CAMERAS.keys()) + _go2rtc_streams()))
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

    def proxy_frigate(self, parsed):
        downstream = parsed.path[len("/frigate"):]
        if not downstream:
            downstream = "/"
        url = FRIGATE_URL + downstream
        if parsed.query:
            url += "?" + parsed.query
        try:
            req = Request(url)
            resp = urlopen(req, timeout=10)
            data = resp.read()
            ct = resp.headers.get("Content-Type", "application/octet-stream")
            self.send_response(resp.status)
            self.send_header("Content-Type", ct)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, "Frigate proxy error: {}".format(e))

    def serve_web_ui(self):
        try:
            with open('/web/web_ui.html', 'r') as f:
                html = f.read()
            data = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, 'Web UI not found')

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


    def serve_all_camera_info(self):
        """Serve a list of all cameras with their full info."""
        all_info = []
        for name in _CAMERAS:
            info = camera_info(name)
            if info:
                all_info.append(info)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(all_info).encode())


if __name__ == "__main__":
    _load_cameras()
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
    if GO2RTC_URL:
        cams = _go2rtc_streams()
        print(f"  go2rtc: {len(cams)} cameras via {GO2RTC_URL}")

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(("0.0.0.0", PORT), PhotoHandler)

    # Start the timelapse capture service if configured
    timelapse_capturer = TimelapseCapturer(_CAMERAS)
    timelapse_capturer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
