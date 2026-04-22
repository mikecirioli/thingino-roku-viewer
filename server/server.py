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
  /ticker        JSON: screensaver ticker items (text from HA + camera image URLs)
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

# Geotag management
from geotag_manager import (
    GeotagDatabase,
    GeoTag,
    extract_gps_from_exif,
    extract_exif_timestamp,
    cluster_photos_by_time,
    infer_geotags_from_cluster
)
from duplicate_detector import DuplicateDetector

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
THUMBNAIL_DIR = os.environ.get("THUMBNAIL_DIR", "/data/thumbnails")
CACHE_DIR = os.environ.get("CACHE_DIR", "/data/cache")
THUMBNAIL_SIZE = 180
THUMBNAIL_SCAN_INTERVAL = 60
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# ── Timelapse Capturer ──────────────────────────────────

def _frame_to_iso(filename):
    """Convert frame filename like '2026-03-20_12-56-00.jpg' to '2026-03-20T12:56:00'."""
    base = filename.replace(".jpg", "")  # 2026-03-20_12-56-00
    date_part, time_part = base.split("_", 1)  # 2026-03-20, 12-56-00
    return date_part + "T" + time_part.replace("-", ":") + "Z"  # 2026-03-20T12:56:00Z (UTC)


class TimelapseCapturer:
    """Manages background snapshot capture for multiple cameras."""

    def __init__(self, cameras_config):
        self._cameras = cameras_config
        self._timers = {}
        self._lock = threading.Lock()
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
        self._load_saved_config()
        for name, config in self._cameras.items():
            tl_config = config.get("timelapse")
            if tl_config and tl_config.get("enabled"):
                print(f"  timelapse: starting capture for '{name}' every {tl_config.get('interval', 60)}s")
                self._capture_frame(name, tl_config)
                self._schedule_next_capture(name, tl_config)

        while True:
            time.sleep(1)

    def get_config(self, name):
        """Get timelapse config for a camera."""
        cam = self._cameras.get(name, {})
        tl = cam.get("timelapse", {})
        return {
            "enabled": bool(tl.get("enabled")),
            "interval": tl.get("interval", 60),
            "source": tl.get("source", "snapshot"),
        }

    def set_config(self, name, enabled, interval):
        """Dynamically enable/disable timelapse for a camera."""
        cam = self._cameras.get(name)
        if not cam:
            return False
        if "timelapse" not in cam:
            cam["timelapse"] = {}
        cam["timelapse"]["enabled"] = enabled
        cam["timelapse"]["interval"] = max(10, interval)

        # Cancel existing timer (lock just for timer dict access)
        with self._lock:
            old_timer = self._timers.pop(name, None)
        if old_timer:
            old_timer.cancel()

        if enabled:
            print(f"  timelapse: enabling capture for '{name}' every {interval}s")
            # Capture first frame immediately in a background thread
            threading.Thread(target=self._capture_frame, args=[name, cam["timelapse"]], daemon=True).start()
            self._schedule_next_capture(name, cam["timelapse"])
        else:
            print(f"  timelapse: disabling capture for '{name}'")

        # Persist to YAML config
        self._save_config()
        return True

    def _save_config(self):
        """Persist timelapse config to a separate file (main config is read-only)."""
        try:
            os.makedirs(TIMELAPSE_STORAGE_PATH, exist_ok=True)
            cfg_path = os.path.join(TIMELAPSE_STORAGE_PATH, "timelapse_config.json")
            tl_cfg = {}
            for name, cam in self._cameras.items():
                tl = cam.get("timelapse")
                if tl:
                    tl_cfg[name] = {
                        "enabled": tl.get("enabled", False),
                        "interval": tl.get("interval", 60),
                        "source": tl.get("source", "snapshot"),
                    }
            with open(cfg_path, "w") as f:
                json.dump(tl_cfg, f, indent=2)
        except Exception as e:
            print(f"WARNING: failed to persist timelapse config: {e}")

    def _load_saved_config(self):
        """Load persisted timelapse config and merge into camera configs."""
        cfg_path = os.path.join(TIMELAPSE_STORAGE_PATH, "timelapse_config.json")
        try:
            with open(cfg_path) as f:
                tl_cfg = json.load(f)
            for name, tl in tl_cfg.items():
                cam = self._cameras.get(name)
                if cam:
                    cam["timelapse"] = tl
                    print(f"  timelapse: restored config for '{name}' (enabled={tl.get('enabled')}, interval={tl.get('interval')}s)")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"WARNING: failed to load timelapse config: {e}")

    def _schedule_next_capture(self, name, tl_config):
        """Schedules the next snapshot for a given camera."""
        interval = tl_config.get("interval", 60)
        timer = threading.Timer(interval, self._capture_and_reschedule, args=[name, tl_config])
        with self._lock:
            self._timers[name] = timer
        timer.start()

    def _capture_and_reschedule(self, name, tl_config):
        """The function executed by the timer."""
        self._capture_frame(name, tl_config)
        # Only reschedule if still enabled
        cam = self._cameras.get(name, {})
        tl = cam.get("timelapse", {})
        if tl.get("enabled"):
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

# ── Thumbnail Generator ───────────────────────────────────

class ThumbnailGenerator:
    """Background task that generates orientation-corrected thumbnails for the photo library."""

    def __init__(self):
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"  thumbnails: generator started, output to {THUMBNAIL_DIR}")

    def _run(self):
        while True:
            try:
                self._scan()
            except Exception as e:
                print(f"WARNING: thumbnail scan failed: {e}")
            time.sleep(THUMBNAIL_SCAN_INTERVAL)

    def _scan(self):
        from PIL import Image, ImageOps
        os.makedirs(THUMBNAIL_DIR, exist_ok=True)

        photos = get_photos()
        generated = 0
        for photo_path in photos:
            thumb_name = self._thumb_name(photo_path)
            thumb_path = os.path.join(THUMBNAIL_DIR, thumb_name)
            if os.path.exists(thumb_path):
                continue
            try:
                with Image.open(photo_path) as img:
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
                    img.save(thumb_path, "JPEG", quality=50)
                generated += 1
            except Exception as e:
                print(f"WARNING: thumbnail failed for {photo_path}: {e}")

        # Clean up thumbnails for deleted photos
        photo_set = {self._thumb_name(p) for p in photos}
        try:
            for f in os.listdir(THUMBNAIL_DIR):
                if f.endswith(".jpg") and f not in photo_set:
                    os.remove(os.path.join(THUMBNAIL_DIR, f))
        except Exception:
            pass

        if generated:
            print(f"  thumbnails: generated {generated} new thumbnails")

    @staticmethod
    def _thumb_name(photo_path):
        """Deterministic thumbnail filename from original path."""
        import hashlib
        h = hashlib.md5(photo_path.encode()).hexdigest()
        return h + ".jpg"

    @staticmethod
    def thumb_path_for(photo_path):
        """Return the thumbnail path for a given photo."""
        import hashlib
        h = hashlib.md5(photo_path.encode()).hexdigest()
        return os.path.join(THUMBNAIL_DIR, h + ".jpg")


def _find_photo_by_relative(rel_path):
    """Find a photo by its path relative to PHOTO_DIR."""
    full = os.path.normpath(os.path.join(PHOTO_DIR, rel_path))
    if not full.startswith(os.path.normpath(PHOTO_DIR)):
        return None  # path traversal
    if os.path.isfile(full):
        return full
    return None


# ── Photo cache ──────────────────────────────────────────
_photo_cache = []
_cache_time = 0
_shuffled_photos = []
_photo_index = 0


def get_photos():
    """Return list of photo paths, scanning subdirectories and caching for 5 minutes."""
    global _photo_cache, _cache_time
    if time.time() - _cache_time > 300 or not _photo_cache:
        try:
            new_cache = []
            for root, _, files in os.walk(PHOTO_DIR):
                for f in files:
                    if os.path.splitext(f)[1].lower() in EXTS:
                        new_cache.append(os.path.join(root, f))
            _photo_cache = new_cache
            _cache_time = time.time()
        except OSError:
            pass
    return _photo_cache


def resize_image(path, max_w, max_h, disable_exif=False, fit="contain", crop_threshold=0):
    """Resize image with various fill modes (contain, cover, blur). Returns (bytes, content_type)."""
    try:
        import hashlib
        # 1. Check disk cache
        # Cache key based on path + all resizing parameters
        cache_key_raw = f"{path}_{max_w}_{max_h}_{disable_exif}_{fit}_{crop_threshold}"
        cache_hash = hashlib.md5(cache_key_raw.encode()).hexdigest()
        cache_ext = ".jpg" if path.lower().endswith((".jpg", ".jpeg")) else ".png"
        cache_path = os.path.join(CACHE_DIR, cache_hash + cache_ext)
        ct = "image/jpeg" if cache_ext == ".jpg" else "image/png"

        try:
            if os.path.exists(cache_path):
                # Verify source hasn't changed
                src_mtime = os.path.getmtime(path)
                cache_mtime = os.path.getmtime(cache_path)
                if cache_mtime > src_mtime:
                    with open(cache_path, "rb") as f:
                        return f.read(), ct
        except Exception as e:
            print(f"  cache: error reading {cache_path}: {e}")

        # 2. Perform resize
        from PIL import Image, ImageOps, ImageFilter
        with Image.open(path) as img:
            if not disable_exif:
                img = ImageOps.exif_transpose(img)
            
            src_w, src_h = img.size
            dst_w, dst_h = max_w, max_h
            
            # Smart Aspect Ratio Logic
            src_ratio = src_w / src_h
            dst_ratio = dst_w / dst_h
            
            # If aspect ratios are very close (within threshold), default fit to 'cover' for a better look
            if fit == "contain" and abs(src_ratio - dst_ratio) / dst_ratio < crop_threshold:
                fit = "cover"

            if fit == "cover":
                # Scale to fill the screen (crop excess)
                scale = max(dst_w / src_w, dst_h / src_h)
                new_w = int(src_w * scale)
                new_h = int(src_h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                
                # Center crop
                left = (new_w - dst_w) / 2
                top = (new_h - dst_h) / 2
                img = img.crop((left, top, left + dst_w, top + dst_h))
            elif fit == "blur":
                # Blur background fill for any aspect ratio mismatch
                # Works for portrait on landscape, wide panoramas, etc.
                src_ratio = src_w / src_h
                dst_ratio = dst_w / dst_h
                if abs(src_ratio - dst_ratio) > 0.01:
                    # 1. Create blurred background (scaled to fill)
                    bg_scale = max(dst_w / src_w, dst_h / src_h)
                    bg = img.resize((int(src_w * bg_scale), int(src_h * bg_scale)), Image.LANCZOS)
                    bg = bg.crop(((bg.width - dst_w)//2, (bg.height - dst_h)//2, (bg.width + dst_w)//2, (bg.height + dst_h)//2))
                    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

                    # 2. Scale original to fit (contain)
                    fg_scale = min(dst_w / src_w, dst_h / src_h)
                    fg_w, fg_h = int(src_w * fg_scale), int(src_h * fg_scale)
                    fg = img.resize((fg_w, fg_h), Image.LANCZOS)

                    # 3. Paste foreground on background
                    bg.paste(fg, ((dst_w - fg_w)//2, (dst_h - fg_h)//2))
                    img = bg
                else:
                    # Ratios match — just resize to fill
                    img = img.resize((dst_w, dst_h), Image.LANCZOS)
            else:
                # Default: contain (fit within bounds)
                img.thumbnail((max_w, max_h), Image.LANCZOS)
            
            buf = BytesIO()
            fmt = "JPEG" if cache_ext == ".jpg" else "PNG"
            img.save(buf, fmt, quality=85)
            data = buf.getvalue()

            # 3. Save to cache
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(cache_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                print(f"  cache: error saving {cache_path}: {e}")
            
            return data, ct
    except ImportError:
        return None, None
    except Exception as e:
        print(f"  resize: error processing {path}: {e}")
        return None, None


# ── Camera configuration ─────────────────────────────────
# Unified camera config: each camera has optional snapshot, stream, auth.
# Loaded from YAML file or legacy CAMERAS env var (JSON).

_CAMERAS = {}  # name -> {snapshot, stream, stream_type, auth: {type, username, password}}
_WEB_AUTH = None # {username, password}
_REMOTE_AUTH_SECRET = "" # shared secret for remote ?auth= access
_SETTINGS = {} # global settings (screensaver params, etc)

# Geotag database
GEOTAG_DB_PATH = os.environ.get("GEOTAG_DB_PATH", "/data/geotags/geotags.db")
geotag_db = None
duplicate_detector = None

def _load_cameras():
    """Load camera config from YAML file or CAMERAS env var."""
    global _CAMERAS, _WEB_AUTH, _REMOTE_AUTH_SECRET, _SETTINGS, HA_URL, HA_TOKEN

    # Try YAML file first
    if os.path.isfile(CAMERAS_FILE):
        try:
            import yaml
            with open(CAMERAS_FILE) as f:
                cfg = yaml.safe_load(f)
            if cfg and "cameras" in cfg:
                _CAMERAS = cfg["cameras"]
                print(f"  cameras: loaded {len(_CAMERAS)} from {CAMERAS_FILE}")
            if cfg and "web_auth" in cfg:
                _WEB_AUTH = cfg["web_auth"]
                print(f"  web auth configured from {CAMERAS_FILE}")
            if cfg and "remote_auth_secret" in cfg:
                _REMOTE_AUTH_SECRET = cfg["remote_auth_secret"]
                print(f"  remote auth secret configured from {CAMERAS_FILE}")
            if cfg and "settings" in cfg:
                _SETTINGS = cfg["settings"]
                print(f"  global settings loaded from {CAMERAS_FILE}")
            if cfg and "ha_url" in cfg and not HA_URL:
                HA_URL = cfg["ha_url"].rstrip("/")
                print(f"  ha_url configured from {CAMERAS_FILE}")
            if cfg and "ha_token" in cfg and not HA_TOKEN:
                HA_TOKEN = cfg["ha_token"]
                print(f"  ha_token configured from {CAMERAS_FILE}")
            if cfg and "cameras" in cfg:
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


def _save_cameras():
    """Save current camera config back to YAML file."""
    try:
        import yaml
        # Ensure directory exists
        os.makedirs(os.path.dirname(CAMERAS_FILE), exist_ok=True)
        
        full_cfg = {}
        if os.path.isfile(CAMERAS_FILE):
            try:
                with open(CAMERAS_FILE) as f:
                    full_cfg = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"WARNING: failed to parse existing {CAMERAS_FILE}: {e}")
        
        full_cfg["cameras"] = _CAMERAS
        full_cfg["settings"] = _SETTINGS
        if _REMOTE_AUTH_SECRET:
            full_cfg["remote_auth_secret"] = _REMOTE_AUTH_SECRET
        elif "remote_auth_secret" in full_cfg:
            del full_cfg["remote_auth_secret"]

        with open(CAMERAS_FILE, "w") as f:

            yaml.safe_dump(full_cfg, f, default_flow_style=False)
        print(f"  cameras: saved {len(_CAMERAS)} to {CAMERAS_FILE}")
        return True
    except Exception as e:
        print(f"WARNING: failed to save {CAMERAS_FILE}: {e}")
    return False


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
        """Fetch with HTTP basic or digest auth."""
        try:
            import requests
            from requests.auth import HTTPBasicAuth, HTTPDigestAuth
            
            user = auth.get("username", "")
            pw = auth.get("password", "")
            
            try:
                # Try basic auth first
                resp = requests.get(url, auth=HTTPBasicAuth(user, pw), timeout=10)
                if resp.status_code == 401:
                    # Fallback to Digest
                    resp = requests.get(url, auth=HTTPDigestAuth(user, pw), timeout=10)
                if resp.status_code == 200:
                    return resp.content
            except Exception as e:
                print(f"requests error fetching auth URL {url}: {e}")
                return None
        except ImportError:
            # Fallback to urllib if requests isn't installed
            try:
                try:
                    from urllib.request import HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler, HTTPDigestAuthHandler, build_opener
                except ImportError:
                    from urllib2 import HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler, HTTPDigestAuthHandler, build_opener

                passman = HTTPPasswordMgrWithDefaultRealm()
                passman.add_password(None, url, auth.get("username", ""), auth.get("password", ""))
                
                auth_basic = HTTPBasicAuthHandler(passman)
                auth_digest = HTTPDigestAuthHandler(passman)
                opener = build_opener(auth_basic, auth_digest)
                
                resp = opener.open(url, timeout=15)
                if resp.getcode() == 200:
                    return resp.read()
            except Exception as e:
                import traceback
                print(f"urllib error fetching auth URL {url}: {e}")
                traceback.print_exc()
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


def camera_snapshot(name, max_w=None, max_h=None, disable_exif=True, fit="contain", crop_threshold=0):
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
    if (max_w and max_h) or not disable_exif:
        return _resize_jpeg(raw, max_w, max_h, disable_exif=disable_exif, fit=fit, crop_threshold=crop_threshold)
    return raw, "image/jpeg"


def camera_info(name, remote=False):
    """Return camera info dict for /camera/<name>/info endpoint.
    When remote=True, rewrites absolute go2rtc stream URLs to relative
    paths so clients can reach streams via the same server base URL."""
    cam = _CAMERAS.get(name)
    if not cam:
        return None

    stream_url = cam.get("stream", "")

    if remote and stream_url:
        parsed = urlparse(stream_url)
        qs = parse_qs(parsed.query)
        src = qs.get("src", [None])[0]
        if src:
            stream_url = f"/api/stream.m3u8?src={src}"

    return {
        "name": name,
        "snapshot": cam.get("snapshot", ""),
        "stream": stream_url,
        "stream_type": cam.get("stream_type", "hls") if stream_url else "",
        "ptz": bool(cam.get("onvif")),
    }


def _resize_jpeg(data, max_w, max_h, disable_exif=True, fit="contain", crop_threshold=0):
    """Resize JPEG bytes. Returns (bytes, content_type)."""
    try:
        from PIL import Image, ImageOps, ImageFilter
        img = Image.open(BytesIO(data))
        if not disable_exif:
            img = ImageOps.exif_transpose(img)
        
        if max_w and max_h:
            src_w, src_h = img.size
            dst_w, dst_h = max_w, max_h
            
            # Use smart scaling if ratios are close
            src_ratio = src_w / src_h
            dst_ratio = dst_w / dst_h
            if fit == "contain" and abs(src_ratio - dst_ratio) / dst_ratio < crop_threshold:
                fit = "cover"

            if fit == "cover":
                scale = max(dst_w / src_w, dst_h / src_h)
                new_w, new_h = int(src_w * scale), int(src_h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                left = (new_w - dst_w) / 2
                top = (new_h - dst_h) / 2
                img = img.crop((left, top, left + dst_w, top + dst_h))
            elif fit == "blur":
                src_ratio = src_w / src_h
                dst_ratio = dst_w / dst_h
                if abs(src_ratio - dst_ratio) > 0.01:
                    bg_scale = max(dst_w / src_w, dst_h / src_h)
                    bg = img.resize((int(src_w * bg_scale), int(src_h * bg_scale)), Image.LANCZOS)
                    bg = bg.crop(((bg.width - dst_w)//2, (bg.height - dst_h)//2, (bg.width + dst_w)//2, (bg.height + dst_h)//2))
                    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
                    fg_scale = min(dst_w / src_w, dst_h / src_h)
                    fg_w, fg_h = int(src_w * fg_scale), int(src_h * fg_scale)
                    fg = img.resize((fg_w, fg_h), Image.LANCZOS)
                    bg.paste(fg, ((dst_w - fg_w)//2, (dst_h - fg_h)//2))
                    img = bg
                else:
                    img = img.resize((dst_w, dst_h), Image.LANCZOS)
            else:
                img.thumbnail((max_w, max_h), Image.LANCZOS)
        elif disable_exif:
            return data, "image/jpeg"

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

    def send_header(self, keyword, value):
        kl = keyword.lower()
        if kl == 'content-type':
            self._response_content_type = value
        if kl == 'cache-control':
            self._has_cache_control = True
        super().send_header(keyword, value)

    def end_headers(self):
        ctype = getattr(self, '_response_content_type', '') or ''
        has_cc = getattr(self, '_has_cache_control', False)
        ctype_lower = ctype.lower()
        if not has_cc and (('application/json' in ctype_lower) or ('text/html' in ctype_lower)):
            super().send_header('Cache-Control', 'no-cache, must-revalidate')
            super().send_header('Vary', 'Cookie')
        self._response_content_type = ''
        self._has_cache_control = False
        super().end_headers()

    def _merge_settings(self, params):
        """Merge global _SETTINGS as defaults into params."""
        for key, value in _SETTINGS.items():
            if key not in params or not params[key][0]:
                params[key] = [value]
        
        # If no fit mode is specified even after merging settings, default to 'blur'
        if "fit" not in params or not params["fit"][0]:
            params["fit"] = ["blur"]
            
        return params

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # The /login endpoint is the only one that can be accessed without prior auth.
        if path == "/login":
            self.handle_login()
            return
        if path == "/api/login":
            self.handle_api_login()
            return
        
        # For all other POST endpoints, require authorization.
        if not self._is_request_authorized():
            self.send_error(401, "Authentication Required")
            return

        # --- Authorized POST requests ---
        if path.endswith("/ptz") and path.startswith("/camera/"):
            self.handle_ptz(path)
        elif path == "/timelapse/generate":
            self.handle_timelapse_generate()
        elif path == "/timelapse/config":
            self.handle_timelapse_config_post()
        elif path == "/camera/config":
            self.handle_camera_config_post()
        elif path == "/camera/settings":
            self.handle_settings_post()
        elif path == "/library/rotate":
            self.handle_library_rotate()
        elif path == "/library/delete":
            self.handle_library_delete()
        elif path == "/library/upload":
            self.handle_library_upload()
        elif path == "/photos/geotag/import-exif":
            self.handle_geotag_import_exif()
        elif path == "/photos/geotag/auto-infer":
            self.handle_geotag_auto_infer()
        elif path == "/photos/geotag/batch-update":
            self.handle_geotag_batch_update()
        elif path == "/orientation/review":
            self.handle_orientation_review()
        elif path == "/orientation/apply-fix":
            self.handle_orientation_apply_fix()
        elif path == "/orientation/apply-all":
            self.handle_orientation_apply_all()
        elif path == "/duplicates/resolve":
            self.handle_duplicates_resolve()
        else:
            self.send_error(404)

    def handle_library_upload(self):
        """POST /library/upload — handles multipart/form-data upload of multiple photos."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "Bad content-type")
            return
        
        try:
            boundary = content_type.split("boundary=")[1].encode()
        except IndexError:
            self.send_error(400, "Missing boundary")
            return
        
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self.send_error(400, "Empty upload")
            return

        # Read the raw body
        body = self.rfile.read(content_len)
        parts = body.split(b"--" + boundary)
        
        saved_count = 0
        for part in parts:
            if not part or part == b"--\r\n" or part == b"--":
                continue
            
            # Split headers and content
            try:
                head, content = part.split(b"\r\n\r\n", 1)
                head = head.decode("utf-8", "ignore")
                
                # Check if it's a file part
                if 'filename="' not in head:
                    continue
                
                import re
                match = re.search(r'filename="([^"]+)"', head)
                if not match:
                    continue
                
                filename = match.group(1)
                ext = os.path.splitext(filename)[1].lower()
                if ext not in EXTS:
                    continue
                
                # Trim trailing CRLF
                if content.endswith(b"\r\n"):
                    content = content[:-2]
                
                # Sanitize filename
                safe_name = "".join([c for c in filename if c.isalnum() or c in ".-_"]).strip()
                if not safe_name:
                    continue
                
                # Unique filename if exists
                save_path = os.path.join(PHOTO_DIR, safe_name)
                counter = 1
                while os.path.exists(save_path):
                    name_base, name_ext = os.path.splitext(safe_name)
                    save_path = os.path.join(PHOTO_DIR, "{}_{}{}".format(name_base, counter, name_ext))
                    counter += 1
                
                with open(save_path, "wb") as f:
                    f.write(content)
                saved_count += 1
                print("  upload: saved {} as {}".format(filename, os.path.basename(save_path)))
            except Exception as e:
                print("  upload: error processing part: {}".format(e))
                continue

        # Clear photo cache to pick up new images
        global _photo_cache, _cache_time
        _photo_cache = []
        _cache_time = 0

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "saved": saved_count}).encode())

    def handle_api_login(self):
        """POST /api/login — for non-web clients like Roku."""
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len)
        try:
            data = json.loads(body)
            user = data.get('username', '')
            pwd = data.get('password', '')

            if _WEB_AUTH and user == _WEB_AUTH.get('username') and pwd == _WEB_AUTH.get('password'):
                import hashlib
                session_val = hashlib.sha256(f"{user}:{pwd}".encode()).hexdigest()
                cookie = f'session={session_val}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000'
                
                resp = json.dumps({'success': True, 'cookie': cookie}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                # Also set the cookie in the header for convenience
                self.send_header('Set-Cookie', cookie)
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(401, "Invalid credentials")

        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")

    def handle_login(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode('utf-8')
        from urllib.parse import parse_qs
        post_data = parse_qs(body)
        user = post_data.get('username', [''])[0]
        pwd = post_data.get('password', [''])[0]
        
        if _WEB_AUTH and user == _WEB_AUTH.get('username') and pwd == _WEB_AUTH.get('password'):
            import hashlib
            session = hashlib.sha256(f"{user}:{pwd}".encode()).hexdigest()
            self.send_response(302)
            self.send_header('Set-Cookie', f'session={session}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000')
            self.send_header('Location', '/web')
            self.end_headers()
        else:
            self.serve_login_page(error=True)

    def handle_camera_config_post(self):
        """POST /camera/config — update global camera configuration."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        if not isinstance(data, dict):
            self.send_error(400, "Expected JSON object")
            return

        global _CAMERAS
        _CAMERAS = data
        
        # Clear existing stream objects so they are re-initialized with new config.
        # We don't need a lock here because we're replacing the global dict reference,
        # but we should ensure the timelapse capturer is aware of the change.
        # Note: _streams is not actually a global variable, it's usually inside PhotoHandler or a local cache.
        # Looking at server.py, it's not defined at the top level. 
        # I will remove the _streams reference as it's handled per-request or via CameraStream instances.
        
        # Update active timelapse capturer if it exists
        if timelapse_capturer:
            timelapse_capturer._cameras = _CAMERAS
            # We don't have a full refresh method yet, but capturer will 
            # pick up new configs for existing cameras on next cycle.
            # New cameras won't start capturing automatically until next restart
            # or until set_config is called for them.

        if _save_cameras():
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(500, "Failed to persist configuration to file")

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
                        f_ts = _frame_to_iso(fname)
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

    def _is_request_authorized(self):
        """Check for session cookie, shared secret, or local IP address."""
        # If no auth is configured in yaml, allow all requests.
        if not _WEB_AUTH:
            return True

        # 1. Check for a valid session cookie
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            from http.cookies import SimpleCookie
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            if 'session' in cookie:
                import hashlib
                expected = hashlib.sha256(f"{_WEB_AUTH.get('username')}:{_WEB_AUTH.get('password')}".encode()).hexdigest()
                if cookie['session'].value == expected:
                    return True

        # 2. Check for ?auth=<shared_secret> query param (remote Roku access)
        if _REMOTE_AUTH_SECRET:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            auth_param = params.get('auth', [None])[0]
            if auth_param and auth_param == _REMOTE_AUTH_SECRET:
                return True

        # 3. If no cookie or secret, check if the request is from a local IP
        client_ip_str = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        if client_ip_str:
            try:
                from ipaddress import ip_address
                if ip_address(client_ip_str).is_private:
                    return True
            except (ValueError, ImportError):
                pass

        return False

    def serve_auth_verify(self):
        """Lightweight endpoint for nginx auth_request subrequests.
        Checks session cookie or Basic auth — no IP bypass.  LAN bypass is
        handled by _is_request_authorized() for direct (non-nginx) access."""
        authorized = False
        if not _WEB_AUTH:
            authorized = True
        else:
            # 1. Session cookie
            cookie_header = self.headers.get('Cookie')
            if cookie_header:
                from http.cookies import SimpleCookie
                import hashlib
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                if 'session' in cookie:
                    expected = hashlib.sha256(
                        f"{_WEB_AUTH.get('username')}:{_WEB_AUTH.get('password')}".encode()
                    ).hexdigest()
                    if cookie['session'].value == expected:
                        authorized = True

            # 2. Basic auth (used by Roku screensaver)
            if not authorized:
                import base64
                auth_header = self.headers.get('Authorization', '')
                if auth_header.startswith('Basic '):
                    try:
                        decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                        user, pwd = decoded.split(':', 1)
                        if user == _WEB_AUTH.get('username') and pwd == _WEB_AUTH.get('password'):
                            authorized = True
                    except Exception:
                        pass
        self.send_response(200 if authorized else 401)
        self.end_headers()

    def serve_login_page(self, error=False):
        html = """<!DOCTYPE html>
<html><head><title>Login</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: sans-serif; background: #222; color: #eee; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
.box { background: #333; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: center; }
input { display: block; width: 100%; margin: 10px 0; padding: 10px; box-sizing: border-box; background: #444; color: white; border: 1px solid #555; border-radius: 4px; }
button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; width: 100%; margin-top: 10px; }
button:hover { background: #0056b3; }
.error { color: #ff6b6b; margin-bottom: 10px; }
</style></head><body>
<div class="box">
  <h2>Login</h2>
  """ + ('<div class="error">Invalid credentials</div>' if error else '') + """
  <form method="POST" action="/login">
    <input type="text" name="username" placeholder="Username" required autofocus>
    <input type="password" name="password" placeholder="Password" required>
    <button type="submit">Login</button>
  </form>
</div>
</body></html>"""
        data = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Require authorization for all PUT requests
        if not self._is_request_authorized():
            self.send_error(401, "Authentication Required")
            return

        # --- Authorized PUT requests ---
        if path.startswith("/photo/") and path.endswith("/geotag"):
            self.handle_put_photo_geotag(path)
        else:
            self.send_error(404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Define which paths require authentication
        protected_prefixes = ('/web', '/random', '/camera/', '/timelapse/', '/ha/', '/library', '/ticker', '/orientation/', '/duplicates/')
        is_protected = path.startswith(protected_prefixes)
        
        # Exception: /web/ is protected, but assets inside /web/ (like logo.png) are not,
        # otherwise the login page itself wouldn't load correctly if it had external assets.
        if path.startswith('/web/'):
            is_protected = False

        # Main auth check
        if is_protected and not self._is_request_authorized():
            if path == '/web':
                # User is trying to access the main UI, show the login page.
                self.serve_login_page()
            else:
                # Unauthorized access to an API endpoint.
                self.send_error(401, "Authentication Required")
            return

        # --- Authorized or public paths ---
        if path == "/auth/verify":
            self.serve_auth_verify()
            return
        elif path == "" or path == "/index.html":
            self.serve_html()
        elif path == "/web":
            self.serve_web_ui()
        elif path == "/random":
            self.serve_random(parsed)
        elif path == "/camera/list":
            self.serve_camera_list()
        elif path == "/camera/all_info":
            self.serve_all_camera_info()
        elif path == "/camera/config":
            self.serve_camera_config()
        elif path == "/camera/settings":
            self.serve_settings()
        elif path.endswith("/info") and path.startswith("/camera/"):
            self.serve_camera_info(path)
        elif path.startswith("/camera/"):
            self.serve_camera(path, parsed)
        elif path.startswith("/frigate") and FRIGATE_URL:
            self.proxy_frigate(parsed)
        elif path == "/ticker":
            self.serve_ticker()
        elif path.startswith("/ha/"):
            self.serve_ha(path)
        elif path == "/timelapse/config":
            self.serve_timelapse_config()
        elif path == "/timelapse/summary":
            self.serve_timelapse_summary()
        elif path == "/timelapse/videos":
            self.serve_timelapse_video_list()
        elif path.startswith("/timelapse/videos/"):
            self.serve_timelapse_video(path)
        elif path == "/timelapse/frames":
            self.serve_timelapse_frames()
        elif path == "/timelapse/frame":
            self.serve_timelapse_frame()
        elif path == "/library":
            self.serve_library_list()
        elif path == "/library/thumb":
            self.serve_library_thumb(parsed)
        elif path == "/photos/geotags":
            self.serve_photos_geotags(parsed)
        elif path.startswith("/photo/") and path.endswith("/geotag"):
            self.serve_photo_geotag(path)
        elif path == "/orientation/photos":
            self.serve_orientation_photos(parsed)
        elif path == "/orientation/counts":
            self.serve_orientation_counts()
        elif path == "/orientation/thumbnail":
            self.serve_orientation_thumbnail(parsed)
        elif path == "/duplicates/groups":
            self.serve_duplicates_groups()
        elif path.startswith("/web/"):
            self.serve_web_static(path)
        elif path == "/login":
            self.serve_login_page()
        elif path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

    def serve_camera_config(self):
        """GET /camera/config — return global camera configuration."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(_CAMERAS).encode())

    def serve_settings(self):
        """GET /camera/settings — return global settings + remote_auth_secret."""
        result = dict(_SETTINGS)
        result['remote_auth_secret'] = _REMOTE_AUTH_SECRET
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def handle_settings_post(self):
        """POST /camera/settings — update global settings."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        if not isinstance(data, dict):
            self.send_error(400, "Expected JSON object")
            return

        global _SETTINGS, _REMOTE_AUTH_SECRET
        if 'remote_auth_secret' in data:
            _REMOTE_AUTH_SECRET = data.pop('remote_auth_secret', '')
        _SETTINGS = data
        if _save_cameras():
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(500, "Failed to persist configuration to file")

    def serve_timelapse_config(self):
        """GET /timelapse/config?camera=<name> — return capture config for a camera."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        camera_name = params.get("camera", [None])[0]
        if not camera_name:
            self.send_error(400, "Missing 'camera' parameter")
            return
        cfg = timelapse_capturer.get_config(camera_name)
        data = json.dumps(cfg).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_timelapse_config_post(self):
        """POST /timelapse/config — enable/disable capture for a camera."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        camera_name = data.get("camera")
        enabled = bool(data.get("enabled", False))
        interval = int(data.get("interval", 60))
        if not camera_name:
            self.send_error(400, "Missing 'camera' field")
            return
        ok = timelapse_capturer.set_config(camera_name, enabled, interval)
        result = json.dumps({"ok": ok}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

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
                    "first_snapshot_timestamp": _frame_to_iso(frames[0]),
                    "last_snapshot_timestamp": _frame_to_iso(frames[-1]),
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

    def serve_timelapse_frames(self):
        """GET /timelapse/frames?camera=<name> — return sorted list of frame timestamps."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        camera = params.get("camera", [None])[0]
        if not camera:
            self.send_error(400, "Missing camera parameter")
            return
        cam_dir = os.path.join(TIMELAPSE_STORAGE_PATH, camera)
        try:
            frames = sorted([f for f in os.listdir(cam_dir) if f.endswith(".jpg")])
        except FileNotFoundError:
            frames = []
        timestamps = [_frame_to_iso(f) for f in frames]
        data = json.dumps(timestamps).encode()
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

            # Find the closest frame by naive datetime comparison (all times are UTC)
            target_str = timestamp_str.replace("Z", "").split("+")[0].split(".")[0]
            target_ts = datetime.fromisoformat(target_str)

            def _frame_dt(f):
                return datetime.fromisoformat(_frame_to_iso(f).replace("Z", ""))

            best_frame = min(frames, key=lambda f: abs(_frame_dt(f) - target_ts))
            
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

    def serve_library_list(self):
        """GET /library — return list of photos with relative paths and thumbnail URLs, sorted by date."""
        photos = get_photos()
        # Pair each photo with its modification time
        photo_info = []
        for p in photos:
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                mtime = 0
            photo_info.append((p, mtime))
        
        # Sort by mtime descending (newest first)
        photo_info.sort(key=lambda x: x[1], reverse=True)
        
        items = []
        for p, _ in photo_info:
            rel = os.path.relpath(p, PHOTO_DIR)
            thumb_name = ThumbnailGenerator._thumb_name(p)
            has_thumb = os.path.exists(os.path.join(THUMBNAIL_DIR, thumb_name))
            items.append({
                "file": rel,
                "thumb": f"/library/thumb?file={rel}" if has_thumb else None,
            })
        data = json.dumps(items).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_library_thumb(self, parsed):
        """GET /library/thumb?file=<relative-path> — serve a thumbnail."""
        params = parse_qs(parsed.query)
        rel = params.get("file", [None])[0]
        if not rel:
            self.send_error(400, "Missing file parameter")
            return
        full = _find_photo_by_relative(rel)
        if not full:
            self.send_error(404, "Photo not found")
            return
        thumb_path = ThumbnailGenerator.thumb_path_for(full)
        if not os.path.isfile(thumb_path):
            self.send_error(404, "Thumbnail not yet generated")
            return
        try:
            with open(thumb_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "max-age=300")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_error(500, "Failed to read thumbnail")

    def handle_library_rotate(self):
        """POST /library/rotate — rotate original image 90° CW, regenerate thumbnail."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        rel = data.get("file")
        if not rel:
            self.send_error(400, "Missing file field")
            return
        full = _find_photo_by_relative(rel)
        if not full:
            self.send_error(404, "Photo not found")
            return
        try:
            from PIL import Image, ImageOps
            with Image.open(full) as img:
                img = ImageOps.exif_transpose(img)
                img = img.rotate(-90, expand=True)
                # Strip EXIF orientation since we've applied it
                exif_data = img.info.get("exif")
                if full.lower().endswith((".jpg", ".jpeg")):
                    img.save(full, "JPEG", quality=95)
                else:
                    img.save(full)
            # Regenerate thumbnail
            thumb_path = ThumbnailGenerator.thumb_path_for(full)
            with Image.open(full) as img:
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
                img.save(thumb_path, "JPEG", quality=50)
            result = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        except Exception as e:
            print(f"ERROR: rotate failed for {full}: {e}")
            self.send_error(500, f"Rotate failed: {e}")

    def handle_library_delete(self):
        """POST /library/delete — delete original photo and its thumbnail."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        rel = data.get("file")
        if not rel:
            self.send_error(400, "Missing file field")
            return
        full = _find_photo_by_relative(rel)
        if not full:
            self.send_error(404, "Photo not found")
            return
        try:
            # Delete thumbnail
            thumb_path = ThumbnailGenerator.thumb_path_for(full)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            # Delete original
            os.remove(full)
            # Invalidate photo cache
            global _photo_cache, _cache_time
            _cache_time = 0
            result = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        except Exception as e:
            print(f"ERROR: delete failed for {full}: {e}")
            self.send_error(500, f"Delete failed: {e}")

    # ── Orientation review endpoints (Phase 1+2) ─────────────

    def _orientation_json(self, payload, status=200):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_orientation_photos(self, parsed):
        """GET /orientation/photos?filter=<status>&limit=50&offset=0"""
        if geotag_db is None:
            self.send_error(503, "Geotag DB not initialized")
            return
        params = parse_qs(parsed.query)
        filter_status = (params.get("filter", ["unreviewed"])[0] or "unreviewed").lower()
        try:
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
        except ValueError:
            self.send_error(400, "limit/offset must be integers")
            return
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        try:
            rows, total = geotag_db.list_orientation_reviews(
                filter_status=filter_status, limit=limit, offset=offset
            )
        except Exception as e:
            print(f"ERROR: orientation list failed: {e}")
            self.send_error(500, f"List failed: {e}")
            return
        self._orientation_json({
            "photos": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
            "filter": filter_status,
        })

    def serve_orientation_counts(self):
        """GET /orientation/counts — counts per review status."""
        if geotag_db is None:
            self.send_error(503, "Geotag DB not initialized")
            return
        try:
            counts = geotag_db.orientation_counts()
        except Exception as e:
            print(f"ERROR: orientation counts failed: {e}")
            self.send_error(500, f"Counts failed: {e}")
            return
        self._orientation_json(counts)

    def serve_orientation_thumbnail(self, parsed):
        """GET /orientation/thumbnail?name=X&mode=raw|rendered — downsized JPEG."""
        params = parse_qs(parsed.query)
        name = params.get("name", [None])[0]
        mode = (params.get("mode", ["rendered"])[0] or "rendered").lower()
        if not name:
            self.send_error(400, "Missing 'name' parameter")
            return
        if mode not in ("raw", "rendered"):
            self.send_error(400, "mode must be 'raw' or 'rendered'")
            return

        # Resolve name: incoming is a basename; find it via photo cache.
        safe_name = os.path.basename(name)
        full = None
        for p in get_photos():
            if os.path.basename(p) == safe_name:
                full = p
                break
        if not full:
            self.send_error(404, "Photo not found")
            return

        try:
            from PIL import Image, ImageOps
        except ImportError:
            self.send_error(500, "Pillow not available")
            return

        try:
            with Image.open(full) as img:
                if mode == "rendered":
                    # Apply the same EXIF transpose the display pipeline uses.
                    img = ImageOps.exif_transpose(img)
                # 'raw' mode: no EXIF rotation — show the bytes as stored.
                img = img.convert("RGB")
                img.thumbnail((600, 600), Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, "JPEG", quality=80)
                data = buf.getvalue()
        except Exception as e:
            print(f"ERROR: orientation thumbnail failed for {full}: {e}")
            self.send_error(500, f"Thumbnail failed: {e}")
            return

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "max-age=300")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_orientation_review(self):
        """POST /orientation/review — body {filename, status}. Upsert."""
        if geotag_db is None:
            self.send_error(503, "Geotag DB not initialized")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        filename = (data.get("filename") or "").strip()
        status = (data.get("status") or "").strip().lower()
        if not filename or not status:
            self.send_error(400, "Missing filename or status")
            return
        if status not in ("correct", "needs_fix", "unsure", "unreviewed"):
            self.send_error(400, "Invalid status")
            return
        try:
            ok = geotag_db.set_orientation_review(filename, status)
        except Exception as e:
            print(f"ERROR: orientation review failed: {e}")
            self.send_error(500, f"Review failed: {e}")
            return
        if not ok:
            self.send_error(400, "Failed to set review")
            return
        self._orientation_json({
            "ok": True,
            "filename": os.path.basename(filename),
            "status": status,
        })

    def handle_orientation_apply_fix(self):
        """POST /orientation/apply-fix — bake EXIF rotation into pixel data."""
        if geotag_db is None:
            self.send_error(503, "Geotag DB not initialized")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        filename = (data.get("filename") or "").strip()
        if not filename:
            self.send_error(400, "Missing filename")
            return
        safe_name = os.path.basename(filename)
        full = None
        for p in get_photos():
            if os.path.basename(p) == safe_name:
                full = p
                break
        if not full:
            self.send_error(404, "Photo not found")
            return
        try:
            from PIL import Image, ImageOps
            with Image.open(full) as img:
                exif = img.getexif()
                orient_tag = exif.get(0x0112, 1)
                if orient_tag == 1:
                    self._orientation_json({
                        "ok": True, "skipped": True,
                        "message": "Image already has normal orientation",
                        "filename": safe_name, "status": "correct",
                    })
                    geotag_db.set_orientation_review(safe_name, "correct")
                    return
                transposed = ImageOps.exif_transpose(img)
                if full.lower().endswith((".jpg", ".jpeg")):
                    transposed.save(full, "JPEG", quality=95, exif=b"")
                else:
                    transposed.save(full)
            thumb_path = ThumbnailGenerator.thumb_path_for(full)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            with Image.open(full) as img:
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
                img.save(thumb_path, "JPEG", quality=50)
            geotag_db.set_orientation_review(safe_name, "correct")
            global _photo_cache, _cache_time
            _cache_time = 0
            print(f"  orientation: fixed {safe_name} (was tag={orient_tag})")
        except Exception as e:
            print(f"ERROR: orientation apply-fix failed for {safe_name}: {e}")
            self.send_error(500, f"Apply fix failed: {e}")
            return
        self._orientation_json({
            "ok": True, "filename": safe_name, "status": "correct",
        })

    def handle_orientation_apply_all(self):
        """POST /orientation/apply-all — bake EXIF rotation for all needs_fix photos."""
        if geotag_db is None:
            self.send_error(503, "Geotag DB not initialized")
            return
        try:
            rows, total = geotag_db.list_orientation_reviews(
                filter_status='needs_fix', limit=10000, offset=0
            )
        except Exception as e:
            self.send_error(500, f"List failed: {e}")
            return
        if not rows:
            self._orientation_json({"ok": True, "fixed": 0, "skipped": 0, "failed": 0})
            return

        from PIL import Image, ImageOps
        photos = get_photos()
        photo_map = {os.path.basename(p): p for p in photos}
        fixed = 0
        skipped = 0
        failed = 0
        for row in rows:
            name = row['filename']
            full = photo_map.get(name)
            if not full:
                failed += 1
                continue
            try:
                with Image.open(full) as img:
                    exif = img.getexif()
                    orient_tag = exif.get(0x0112, 1)
                    if orient_tag == 1:
                        geotag_db.set_orientation_review(name, "correct")
                        skipped += 1
                        continue
                    transposed = ImageOps.exif_transpose(img)
                    if full.lower().endswith((".jpg", ".jpeg")):
                        transposed.save(full, "JPEG", quality=95, exif=b"")
                    else:
                        transposed.save(full)
                thumb_path = ThumbnailGenerator.thumb_path_for(full)
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
                with Image.open(full) as img:
                    img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
                    img.save(thumb_path, "JPEG", quality=50)
                geotag_db.set_orientation_review(name, "correct")
                fixed += 1
            except Exception as e:
                print(f"ERROR: apply-all failed for {name}: {e}")
                failed += 1
        global _photo_cache, _cache_time
        _cache_time = 0
        print(f"  orientation: apply-all complete — fixed={fixed} skipped={skipped} failed={failed}")
        self._orientation_json({"ok": True, "fixed": fixed, "skipped": skipped, "failed": failed})

    # ── Duplicate detection endpoints ─────────────────────────

    def serve_duplicates_groups(self):
        """GET /duplicates/groups — list unreviewed duplicate groups"""
        if duplicate_detector is None:
            self.send_error(503, "Duplicate detector not initialized")
            return
        try:
            groups = duplicate_detector.get_unreviewed_groups()
            data = json.dumps({"groups": groups}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"ERROR: duplicates groups list failed: {e}")
            self.send_error(500, f"List failed: {e}")

    def handle_duplicates_resolve(self):
        """POST /duplicates/resolve — resolve a duplicate group"""
        if duplicate_detector is None:
            self.send_error(503, "Duplicate detector not initialized")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        group_id = data.get("group_id")
        kept_photo_id = data.get("kept_photo_id")
        deleted_photo_ids = data.get("deleted_photo_ids", [])
        if not group_id or not kept_photo_id or not deleted_photo_ids:
            self.send_error(400, "Missing group_id, kept_photo_id, or deleted_photo_ids")
            return
        try:
            success = duplicate_detector.resolve_duplicate_group(
                group_id, kept_photo_id, deleted_photo_ids
            )
            if not success:
                self.send_error(500, "Failed to resolve group")
                return
            global _photo_cache, _cache_time
            _cache_time = 0
            result = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)
        except Exception as e:
            print(f"ERROR: duplicate resolve failed: {e}")
            self.send_error(500, f"Resolve failed: {e}")

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

    def serve_ticker(self):
        """GET /ticker — return JSON array of ticker items for screensaver overlay.

        Each item has: type ("text" or "image"), content/url, source.
        Text items are pre-fetched HA data. Image items are camera snapshot URLs.
        Results cached for 120s to match HA cache TTL.
        """
        items = []

        # HA text sources
        ha_handlers = {
            "weather": ha_weather,
            "forecast": ha_forecast,
            "thermostat": ha_thermostat,
            "event": ha_next_event,
        }
        if HA_URL and HA_TOKEN:
            for source, fn in ha_handlers.items():
                try:
                    text = fn()
                    if text:
                        items.append({"type": "text", "content": text, "source": source})
                except Exception:
                    pass

        # Camera image sources — include all cameras that have snapshot capability
        # Also pre-warm the camera pollers so snapshots are ready when clients request them
        go2rtc_names = _go2rtc_streams()
        camera_names = sorted(set(list(_CAMERAS.keys()) + go2rtc_names))
        for name in camera_names:
            cam = _CAMERAS.get(name, {})
            if cam.get("snapshot") or name in go2rtc_names:
                items.append({
                    "type": "image",
                    "url": "/camera/{}?w=400&h=225".format(name),
                    "source": "camera:{}".format(name),
                })
                # Touch the stream to keep its poller alive
                with _streams_lock:
                    stream = _streams.get(name)
                    if stream is None and cam.get("snapshot"):
                        stream = CameraStream(name, cam)
                        _streams[name] = stream
                    if stream is not None:
                        stream._last_request = time.time()

        result = json.dumps({"items": items}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "max-age=120")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(result)))
        self.end_headers()
        self.wfile.write(result)

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

    def _is_remote_request(self):
        """True when the request carries a ?auth= shared secret (remote client)."""
        if not _REMOTE_AUTH_SECRET:
            return False
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        auth_param = params.get('auth', [None])[0]
        return bool(auth_param and auth_param == _REMOTE_AUTH_SECRET)

    def serve_camera_info(self, path):
        # /camera/front-door/info -> name = "front-door"
        name = path[len("/camera/"):].rsplit("/info", 1)[0]
        info = camera_info(name, remote=self._is_remote_request())
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
        params = self._merge_settings(parse_qs(parsed.query))
        max_w = int(params["w"][0]) if "w" in params else None
        max_h = int(params["h"][0]) if "h" in params else None
        # Disable EXIF transpose by default, unless noexif=0 or noexif=false is explicitly provided
        disable_exif = not (params.get("noexif", [""])[0].lower() in ["0", "false", "no"])
        fit = params.get("fit", ["contain"])[0]
        try:
            crop_threshold = float(params.get("crop_threshold", [0])[0])
        except (ValueError, IndexError):
            crop_threshold = 0
            
        data, ct = camera_snapshot(name, max_w, max_h, disable_exif=disable_exif, fit=fit, crop_threshold=crop_threshold)
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
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, 'Web UI not found')

    def serve_web_static(self, path):
        """Serve static files from /web/ directory (logo, etc)."""
        filename = path.split("/")[-1]
        # Only allow specific safe extensions
        allowed = {'.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml'}
        ext = os.path.splitext(filename)[1].lower()
        if ext not in allowed:
            self.send_error(404)
            return
        filepath = os.path.join('/web', filename)
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', allowed[ext])
            self.send_header('Cache-Control', 'max-age=3600')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def serve_html(self):
        title_div = '<div class="title">{}</div>'.format(TITLE) if TITLE else ""
        html = HTML_TEMPLATE.replace("REFRESH_PLACEHOLDER", str(REFRESH))
        html = html.replace("TITLE_PLACEHOLDER", title_div)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode())

    def _build_photo_info(self, photo_path):
        """Build 'City, Country, DD-MM-YYYY' string for screensaver overlay."""
        try:
            import sqlite3 as _sqlite3
            filename = os.path.basename(photo_path)
            parts = []
            date_str = None

            if geotag_db is not None:
                # Single DB query for both location and timestamp
                conn = _sqlite3.connect(geotag_db.db_path)
                conn.row_factory = _sqlite3.Row
                row = conn.execute('''
                    SELECT p.exif_timestamp, g.location_name
                    FROM photos p
                    LEFT JOIN geotags g ON p.id = g.photo_id
                    WHERE p.filename = ?
                ''', (filename,)).fetchone()
                conn.close()

                if row:
                    if row['location_name']:
                        loc = row['location_name']
                        # "Cologne, Köln, North Rhine-Westphalia, Germany" → "Cologne, Germany"
                        loc_parts = [p.strip() for p in loc.split(',')]
                        if len(loc_parts) >= 2:
                            parts.append(f"{loc_parts[0]}, {loc_parts[-1]}")
                        else:
                            parts.append(loc)
                    if row['exif_timestamp']:
                        dt = datetime.fromtimestamp(row['exif_timestamp'])
                        date_str = dt.strftime('%d-%m-%Y')

            # Fall back to EXIF extraction if no DB timestamp
            if not date_str:
                ts = extract_exif_timestamp(photo_path)
                if ts:
                    dt = datetime.fromtimestamp(ts)
                    date_str = dt.strftime('%d-%m-%Y')

            if date_str:
                parts.append(date_str)

            return ', '.join(parts) if parts else None
        except Exception as e:
            print(f"WARNING: _build_photo_info failed for {photo_path}: {e}")
            return None

    def serve_random(self, parsed):
        global _shuffled_photos, _photo_index
        photos = get_photos()
        if not photos:
            self.send_error(503, "No photos found in {}".format(PHOTO_DIR))
            return
            
        if not _shuffled_photos or len(_shuffled_photos) != len(photos):
            _shuffled_photos = list(photos)
            random.shuffle(_shuffled_photos)
            _photo_index = 0
            
        if _photo_index >= len(_shuffled_photos):
            random.shuffle(_shuffled_photos)
            _photo_index = 0
            
        path = _shuffled_photos[_photo_index]
        _photo_index += 1

        # Pre-compute photo info header: "City, Country, DD-MM-YYYY"
        photo_info = self._build_photo_info(path)

        params = self._merge_settings(parse_qs(parsed.query))
        if "w" in params or "h" in params:
            max_w = int(params.get("w", [1920])[0])
            max_h = int(params.get("h", [1080])[0])
            # Disable EXIF transpose by default, unless noexif=0 or noexif=false is explicitly provided
            disable_exif = not (params.get("noexif", [""])[0].lower() in ["0", "false", "no"])
            fit = params.get("fit", ["contain"])[0]
            try:
                crop_threshold = float(params.get("crop_threshold", [0])[0])
            except (ValueError, IndexError):
                crop_threshold = 0

            data, ct = resize_image(path, max_w, max_h, disable_exif=disable_exif, fit=fit, crop_threshold=crop_threshold)
            if data:
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Content-Length", str(len(data)))
                if photo_info:
                    self.send_header("X-Photo-Info", photo_info)
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
            if photo_info:
                self.send_header("X-Photo-Info", photo_info)
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(500, "Failed to read file")


    def serve_all_camera_info(self):
        """Serve a list of all cameras with their full info."""
        remote = self._is_remote_request()
        all_info = []
        for name in _CAMERAS:
            info = camera_info(name, remote=remote)
            if info:
                all_info.append(info)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(all_info).encode())

    # ---- Geotag Management Endpoints ----

    def serve_photo_geotag(self, path):
        """GET /photo/<filename>/geotag — get geotag for a photo

        Always reads coordinates from EXIF (source of truth).
        Adds metadata (source, confidence, location_name) from database if available.
        """
        # Extract filename from path: /photo/IMG_1234.jpg/geotag
        parts = path.split('/')
        if len(parts) < 3:
            self.send_error(400, "Invalid path")
            return
        filename = parts[2]

        # Check if photo exists
        photo_path = os.path.join(PHOTO_DIR, filename)
        if not os.path.isfile(photo_path):
            self.send_error(404, "Photo not found")
            return

        # Always read from EXIF (source of truth)
        geotag = extract_gps_from_exif(photo_path)

        # Add metadata from database if available
        metadata = None
        if geotag_db is not None:
            metadata = geotag_db.get_geotag_metadata(filename)

        if geotag and metadata:
            # Merge metadata into geotag
            geotag.source = metadata['source']
            geotag.confidence = metadata['confidence']
            geotag.location_name = metadata['location_name']
            geotag.updated_at = metadata['updated_at']
            geotag.updated_by = metadata['updated_by']

        response = {
            'filename': filename,
            'geotag': geotag.to_dict() if geotag else None
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_put_photo_geotag(self, path):
        """PUT /photo/<filename>/geotag — set geotag for a photo

        Writes coordinates to EXIF first (source of truth).
        Then stores metadata (source, confidence, location_name) in database.
        """
        from geotag_manager import write_gps_to_exif

        # Extract filename from path
        parts = path.split('/')
        if len(parts) < 3:
            self.send_error(400, "Invalid path")
            return
        filename = parts[2]

        # Check if photo exists
        photo_path = os.path.join(PHOTO_DIR, filename)
        if not os.path.isfile(photo_path):
            self.send_error(404, "Photo not found")
            return

        # Parse request body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Validate required fields
        if 'latitude' not in data or 'longitude' not in data:
            self.send_error(400, "Missing latitude or longitude")
            return

        # Create geotag
        geotag = GeoTag(
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            altitude=float(data['altitude']) if 'altitude' in data else None,
            location_name=data.get('location_name'),
            source='manual',
            confidence=1.0,
            updated_by='user'
        )

        # STEP 1: Write to EXIF (source of truth)
        exif_success = write_gps_to_exif(photo_path, geotag)

        if not exif_success:
            self.send_error(500, "Failed to write GPS to image EXIF. Is piexif installed?")
            return

        # STEP 2: Store metadata in database (optional)
        if geotag_db is not None:
            photo_id = geotag_db.get_photo_id(filename)
            if not photo_id:
                exif_ts = extract_exif_timestamp(photo_path)
                geotag_db.add_photo(filename, photo_path, exif_ts)
            geotag_db.set_geotag_metadata(filename, geotag)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'wrote_exif': True}).encode())

    def serve_photos_geotags(self, parsed):
        """GET /photos/geotags?status=all|complete|missing — list photos with geotag status"""
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        params = parse_qs(parsed.query)
        status = params.get('status', ['all'])[0]

        if status not in ['all', 'complete', 'missing']:
            self.send_error(400, "Invalid status parameter")
            return

        photos = geotag_db.list_photos_by_status(status)

        data = json.dumps({'photos': photos}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_import_exif(self):
        """POST /photos/geotag/import-exif — import EXIF metadata for all photos

        This doesn't modify image files - just indexes what's already there.
        Stores photos in database with their timestamps for temporal clustering.
        """
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Scan photo directory
        photos = get_photos()
        has_gps = 0
        no_gps = 0
        errors = 0

        for photo_path in photos:
            try:
                filename = os.path.basename(photo_path)

                # Add photo to database if not exists (with timestamp for clustering)
                photo_id = geotag_db.get_photo_id(filename)
                if not photo_id:
                    exif_ts = extract_exif_timestamp(photo_path)
                    geotag_db.add_photo(filename, photo_path, exif_ts)
                    photo_id = geotag_db.get_photo_id(filename)

                # Read GPS from EXIF and sync to database (EXIF is source of truth, DB caches it)
                geotag = extract_gps_from_exif(photo_path)
                if geotag:
                    # Populate database with GPS from EXIF
                    geotag.source = 'exif'
                    geotag_db.set_geotag_metadata(filename, geotag)
                    has_gps += 1
                else:
                    no_gps += 1

            except Exception as e:
                print(f"Error processing {photo_path}: {e}")
                errors += 1

        response = {
            'status': 'ok',
            'indexed': len(photos),
            'has_gps': has_gps,
            'missing_gps': no_gps,
            'errors': errors
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_auto_infer(self):
        """POST /photos/geotag/auto-infer — infer geotags using temporal clustering"""
        if geotag_db is None:
            self.send_error(503, "Geotag database not available")
            return

        # Parse request body for options
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            options = json.loads(body)
        except json.JSONDecodeError:
            options = {}

        time_window = options.get('time_window', 3600)  # 1 hour default

        # Get all photos with geotags
        photos_with_geotags = geotag_db.get_all_with_geotags()
        geotag_map = {filename: geotag for filename, _, geotag in photos_with_geotags}

        # Get photos without geotags
        photos_without = geotag_db.get_photos_without_geotags()

        # Cluster by time
        clusters = cluster_photos_by_time(photos_without, time_window)

        # Infer geotags for each cluster
        all_inferences = []
        for cluster in clusters:
            inferences = infer_geotags_from_cluster(cluster, geotag_map)
            all_inferences.extend(inferences)

        # Return suggestions (don't auto-apply)
        response = {
            'status': 'ok',
            'inferences': [
                {
                    'filename': inf['filename'],
                    'geotag': inf['geotag'].to_dict(),
                    'reason': inf['reason']
                }
                for inf in all_inferences
            ]
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_geotag_batch_update(self):
        """POST /photos/geotag/batch-update — apply geotag to multiple photos

        Writes GPS to EXIF for each photo, then stores metadata in database.
        """
        from geotag_manager import write_gps_to_exif

        # Parse request body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        # Validate required fields
        if 'filenames' not in data or 'geotag' not in data:
            self.send_error(400, "Missing filenames or geotag")
            return

        filenames = data['filenames']
        geotag_data = data['geotag']

        if 'latitude' not in geotag_data or 'longitude' not in geotag_data:
            self.send_error(400, "Missing latitude or longitude in geotag")
            return

        # Create geotag
        geotag = GeoTag(
            latitude=float(geotag_data['latitude']),
            longitude=float(geotag_data['longitude']),
            altitude=float(geotag_data['altitude']) if 'altitude' in geotag_data else None,
            location_name=geotag_data.get('location_name'),
            source=geotag_data.get('source', 'manual'),
            confidence=float(geotag_data.get('confidence', 1.0)),
            updated_by=geotag_data.get('updated_by', 'user')
        )

        # Apply to all photos
        success_count = 0
        error_count = 0

        for filename in filenames:
            photo_path = os.path.join(PHOTO_DIR, filename)
            if not os.path.isfile(photo_path):
                error_count += 1
                continue

            # STEP 1: Write to EXIF (source of truth)
            if not write_gps_to_exif(photo_path, geotag):
                error_count += 1
                continue

            # STEP 2: Store metadata in database (optional)
            if geotag_db is not None:
                photo_id = geotag_db.get_photo_id(filename)
                if not photo_id:
                    exif_ts = extract_exif_timestamp(photo_path)
                    geotag_db.add_photo(filename, photo_path, exif_ts)
                geotag_db.set_geotag_metadata(filename, geotag)

            success_count += 1

        response = {
            'status': 'ok',
            'updated': success_count,
            'errors': error_count
        }

        data = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


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
    global timelapse_capturer
    timelapse_capturer = TimelapseCapturer(_CAMERAS)
    timelapse_capturer.start()

    # Start the thumbnail generator
    thumb_gen = ThumbnailGenerator()
    thumb_gen.start()

    # Initialize geotag database and auto-index photos in background
    try:
        geotag_db = GeotagDatabase(GEOTAG_DB_PATH)
        print(f"  geotags: database initialized at {GEOTAG_DB_PATH}")

        def _index_photos_background():
            photos = get_photos()
            indexed = 0
            has_gps = 0
            for photo_path in photos:
                try:
                    filename = os.path.basename(photo_path)
                    photo_id = geotag_db.get_photo_id(filename)
                    if not photo_id:
                        exif_ts = extract_exif_timestamp(photo_path)
                        geotag_db.add_photo(filename, photo_path, exif_ts)
                        indexed += 1
                        geotag = extract_gps_from_exif(photo_path)
                        if geotag:
                            geotag.source = 'exif'
                            geotag_db.set_geotag_metadata(filename, geotag)
                            has_gps += 1
                except Exception as e:
                    print(f"  geotags: error indexing {photo_path}: {e}")
            if indexed:
                print(f"  geotags: indexed {indexed} new photos ({has_gps} with GPS)")
            else:
                print(f"  geotags: all {len(photos)} photos already indexed")

            # Backfill orientation review rows (Phase 1+2).
            try:
                inserted = geotag_db.backfill_orientation_rows(
                    os.path.basename(p) for p in photos
                )
                if inserted:
                    print(f"  orientation: backfilled {inserted} unreviewed rows")
                else:
                    print(f"  orientation: all {len(photos)} photos already have review rows")
            except Exception as e:
                print(f"  orientation: backfill failed: {e}")

            # Auto-flag photos with non-normal EXIF orientation.
            try:
                from PIL import Image
                flagged = 0
                for photo_path in photos:
                    basename = os.path.basename(photo_path)
                    row = geotag_db.get_orientation_status(basename)
                    if row and row != 'unreviewed':
                        continue
                    try:
                        with Image.open(photo_path) as img:
                            exif = img.getexif()
                            orient_tag = exif.get(0x0112, 1)
                        if orient_tag != 1:
                            geotag_db.set_orientation_review(basename, 'needs_fix')
                            flagged += 1
                    except Exception:
                        pass
                if flagged:
                    print(f"  orientation: auto-flagged {flagged} photos with non-normal EXIF orientation")
                else:
                    print(f"  orientation: no new photos to auto-flag")
            except Exception as e:
                print(f"  orientation: auto-flag failed: {e}")

        threading.Thread(target=_index_photos_background, daemon=True).start()

        # Start duplicate detector daemon
        duplicate_detector = DuplicateDetector(geotag_db, PHOTO_DIR, interval=300, batch_size=50)
        duplicate_detector.start()
    except Exception as e:
        print(f"Warning: Failed to initialize geotag database: {e}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
