# GEMINI_HINT.md -- Critical Context for AI Assistants

This file exists because a previous AI session broke the web UI by rewriting it from scratch instead of extending the existing code. Read this carefully before making changes.

## Golden Rules

1. **DO NOT rewrite files from scratch.** Always read the existing code first and make targeted additions.
2. **DO NOT change the color theme.** The app uses a robin's egg blue / blaze orange theme (`--bg-color: #3a7ca5`, `--accent-color: #FF6700`). Do not change it.
3. **DO NOT remove existing features.** The web UI has: screensaver mode, PTZ controls, settings/config tabs, MSE WebSocket streaming, timelapse filmstrip, geotag map, orientation review, duplicate detection, library management, and localStorage persistence. All must be preserved.
4. **DO NOT use generic element auto-discovery patterns.** The DOM elements are manually mapped in the `els` object with explicit `document.getElementById()` calls. Keep it that way.
5. **Test your JS mentally.** If you reference `els.someProperty`, make sure that exact key exists in the `els` object.
6. **Camera names are all lowercase.** Do not use camelCase for camera names in config or code.

## Architecture Overview

### Server (`server/server.py`)
- Pure Python HTTP server (no framework), runs in Docker
- Camera config loaded from `/config/cameras.yaml` (YAML) or `CAMERAS` env var (legacy JSON)
- `CameraStream` class handles snapshot polling with thingino session auth, basic auth, or no auth
- `TimelapseCapturer` class runs background frame capture in a daemon thread
  - Config persisted to `/data/timelapse/timelapse_config.json` (cameras.yaml is read-only for timelapse state)
  - Captures first frame immediately when enabled, then schedules periodic captures
  - IMPORTANT: `set_config()` must NOT hold `self._lock` when calling `_schedule_next_capture()` -- deadlock
- `ThumbnailGenerator` class generates orientation-corrected thumbnails in background
- `DuplicateDetector` class runs pHash-based duplicate detection as a background daemon
- `GeotagDatabase` (from `geotag_manager.py`) manages EXIF GPS read/write, SQLite metadata, temporal clustering
- ONVIF PTZ via raw SOAP with WS-Security UsernameToken digest auth
- HA integration for weather/calendar/thermostat data
- `/ticker` endpoint aggregates HA text + camera snapshot URLs for screensaver overlay
- All timestamps are UTC; `_frame_to_iso()` appends `Z` suffix so browsers convert to local time
- Authentication: session cookie, shared secret (`?auth=`), or LAN IP bypass
- `/auth/verify` endpoint for nginx `auth_request` subrequests

### Web UI (`web/web_ui.html`)
- Single HTML file, no build system, no npm
- Seven tabs: Live View, Time-lapse, Geotags, Library, Orientation, Duplicates, Configuration
- Uses go2rtc **MSE WebSocket** for live video (NOT HLS -- HLS had fragParsingError issues)
- MSE flow: `MediaSource` -> WebSocket to `/api/ws?src=<name>` -> first text message has codec -> `addSourceBuffer` -> binary messages are media segments
- HLS.js is loaded as a fallback only for non-go2rtc streams
- **Live View tab**: Sidebar shows cameras with (jpg) and (hls) entries separately
- **Time-lapse tab**: Sidebar shows one entry per camera (no jpg/hls suffix), filmstrip of actual frames sampled evenly, range slider, video generation
- **Geotags tab**: Interactive Leaflet map, photo grid with GPS status badges, batch editing, auto-inference review
- **Library tab**: Photo thumbnail grid sorted by date, upload, rotate, delete
- **Orientation tab**: Review photos with non-normal EXIF rotation, side-by-side raw/rendered thumbnails, apply fix
- **Duplicates tab**: Review pHash duplicate groups with photo details and resolution info
- **Configuration tab**: Camera settings, timelapse config, server settings, auth secret management
- Screensaver mode: photo frame / camera cycle / live video with bouncing clock overlay
- All state in a single `state` object; all DOM refs in a single `els` object
- Autosave on capture config changes (no save button)

### Key URL patterns
- go2rtc streams are proxied through nginx: `/api/ws?src=<name>` -> go2rtc at port 1984
- Camera snapshots: `/camera/<name>` (server fetches from camera with auth)
- Timelapse API: `/timelapse/summary`, `/timelapse/frames?camera=X`, `/timelapse/videos`, `/timelapse/generate`, `/timelapse/frame?camera=X&timestamp=T`, `/timelapse/config`
- Geotag API: `/photos/geotags`, `/photo/<name>/geotag`, `/photos/geotag/import-exif`, `/photos/geotag/auto-infer`, `/photos/geotag/batch-update`
- Orientation API: `/orientation/photos`, `/orientation/counts`, `/orientation/thumbnail`, `/orientation/review`, `/orientation/apply-fix`, `/orientation/apply-all`
- Duplicates API: `/duplicates/groups`, `/duplicates/resolve`
- Library API: `/library`, `/library/thumb`, `/library/rotate`, `/library/delete`, `/library/upload`

## Docker Configuration

### Required Volume Mounts

The photoframe container needs these volumes in docker-compose.yaml:

```yaml
services:
  photoframe:
    build: ./photoframe-server
    container_name: photoframe-server
    restart: unless-stopped
    ports:
      - "8099:8099"
    volumes:
      - ./photoframe-server/config.yaml:/config/cameras.yaml:ro   # Camera config (read-only)
      - ./media/photos:/media:ro                                   # Photo library (read-only)
      - ./photoframe-server/web:/web:ro                            # Web UI HTML (read-only, live reload)
      - ./photoframe-server/timelapse:/data/timelapse              # Timelapse frames + config (read-write, MUST persist)
      - ./photoframe-server/geotags:/data/geotags                  # Geotag database (read-write, MUST persist)
      - ./photoframe-server/thumbnails:/data/thumbnails            # Generated thumbnails (read-write)
```

**CRITICAL**: The timelapse volume (`/data/timelapse`) and geotags volume (`/data/geotags`) MUST be persistent bind mounts. Without them, captured frames, timelapse config, and geotag metadata are lost on container recreate.

### Dockerfile Requirements

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow PyYAML requests piexif imagehash
COPY server.py geotag_manager.py duplicate_detector.py /app/
WORKDIR /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8099
CMD ["python3", "server.py"]
```

Key points:
- **ffmpeg** is required for timelapse video generation
- **piexif** is required for writing GPS data to EXIF (geotag management)
- **imagehash** is required for pHash-based duplicate detection
- **requests** is required for HA integration and reverse geocoding
- **PYTHONUNBUFFERED=1** is required so `docker logs` shows output in real time
- server.py, geotag_manager.py, duplicate_detector.py are COPY'd (baked in) -- changes require `docker compose up -d --build`
- web_ui.html is volume-mounted -- changes are live on browser refresh

### Network Access

**Simple (direct access on internal network):** No reverse proxy needed. Just expose port 8099 and access the server directly:

```
http://<server-ip>:8099/web       # Web UI
http://<server-ip>:8099/camera/list  # API
```

All endpoints are served by the single photoframe container on port 8099. go2rtc MSE WebSocket streams connect directly from the browser to go2rtc.

**With nginx reverse proxy:** If you run nginx in front (e.g. for TLS, auth, or routing multiple services on port 80/443), you need location blocks for each backend:

```nginx
# Photoframe server
location /web { proxy_pass http://<server-ip>:8099; }
location /camera/ { proxy_pass http://<server-ip>:8099; }
location /timelapse/ { proxy_pass http://<server-ip>:8099; }
location /ha/ { proxy_pass http://<server-ip>:8099; }
location /library { proxy_pass http://<server-ip>:8099; }
location /orientation/ { proxy_pass http://<server-ip>:8099; }
location /duplicates/ { proxy_pass http://<server-ip>:8099; }
location /photos/ { proxy_pass http://<server-ip>:8099; }
location /photo/ { proxy_pass http://<server-ip>:8099; }
location /ticker { proxy_pass http://<server-ip>:8099; }
location /health { proxy_pass http://<server-ip>:8099; }

# go2rtc (MSE WebSocket for live video) -- needs WebSocket upgrade
location /api/ws { proxy_pass http://<go2rtc-ip>:1984; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
location /api/stream.m3u8 { proxy_pass http://<go2rtc-ip>:1984; }
```

IMPORTANT: Do NOT use a broad `location /api/` -- it will intercept other services (e.g. Home Assistant's `/api/websocket`). Use specific paths.

For remote access with auth, use `auth_request /auth/verify` in the nginx location blocks.

## Deployment and Testing

### Prerequisites
- Development machine with the repo
- Deploy target: server host with SSH access
- Docker compose on the server host
- The Dockerfile is in `server/Dockerfile` in the repo

### Step-by-Step Deployment

1. **Copy changed files to server:**

```bash
# From repo root
scp server/server.py server/geotag_manager.py server/duplicate_detector.py \
    root@server:/path/to/photoframe-server/
scp web/web_ui.html root@server:/path/to/photoframe-server/web/web_ui.html
```

If the Dockerfile changed:
```bash
scp server/Dockerfile root@server:/path/to/photoframe-server/Dockerfile
```

2. **Rebuild and restart the container:**

```bash
ssh root@server "cd /path/to/compose && docker compose up -d --build photoframe"
```

IMPORTANT: `docker restart` does NOT pick up code changes. You MUST use `docker compose up -d --build`.

3. **Verify the deploy:**

```bash
# Health check
curl http://server:8099/health

# Camera list (should return JSON array of lowercase camera names)
curl http://server:8099/camera/list

# Check container logs for errors
ssh root@server "docker logs --tail 50 photoframe-server"
```

### Testing the Web UI

1. Open `http://server:8099/web` in a browser
2. **Live View tab**: Sidebar shows (jpg) and (hls) entries per camera
3. **Snapshot mode**: Click a (jpg) entry, image should appear and refresh
4. **Stream mode**: Click a (hls) entry, MSE WebSocket video should play
5. **PTZ**: Select a PTZ camera, PTZ d-pad should appear
6. **Time-lapse tab**: Camera list, filmstrip, video generation
7. **Geotags tab**: Map loads, photo grid shows GPS status badges
8. **Library tab**: Photo thumbnails sorted by date
9. **Orientation tab**: Photos flagged with non-normal EXIF appear
10. **Duplicates tab**: Duplicate groups with photo details
11. **Configuration tab**: Camera and timelapse settings
12. **Screensaver**: Click "Start Screensaver", photos should cycle

### Quick Web UI Test (no deploy needed)

For fast iteration on the web UI HTML only:

```bash
scp web/web_ui.html root@server:/path/to/photoframe-server/web/web_ui.html
```

Then just refresh the browser -- no container rebuild needed.

## Common Mistakes to Avoid

| Mistake | Why it breaks things |
|---------|---------------------|
| Using HLS.js for go2rtc streams | fragParsingError -- go2rtc serves MSE-compatible streams, not standard HLS |
| Changing `els` to auto-discovered camelCase | HTML IDs are kebab-case, JS object keys are manually named -- mismatch crashes everything |
| Removing existing features | Users depend on all tabs and screensaver mode |
| Using `docker restart` instead of `docker compose up --build` | Code changes baked into image are not picked up |
| Changing the color theme | The robin's egg blue/blaze orange theme is intentional |
| Adding npm/webpack/build steps | This is a single-file HTML app, no build system |
| Missing timelapse volume mount | Frames and config lost on container recreate |
| Missing geotags volume mount | Geotag metadata lost on container recreate |
| Holding lock in `set_config` while calling `_schedule_next_capture` | Deadlock -- both methods acquire `self._lock` |
| Timestamps without `Z` suffix | Browser shows UTC times as local, off by hours |
| Using camelCase camera names | All camera names must be lowercase |
| Missing `PYTHONUNBUFFERED=1` in Dockerfile | `docker logs` shows no output |
| Missing `ffmpeg` in Dockerfile | Timelapse video generation fails |
| Missing `piexif` in Dockerfile | Geotag EXIF writing fails |
| Missing `imagehash` in Dockerfile | Duplicate detection fails |
| Missing `requests` in Dockerfile | HA integration and reverse geocoding fail |

## File Layout

```
3-bad-dogs/
  server/
    server.py              # Python HTTP server (all endpoint logic)
    geotag_manager.py      # Geotag database, EXIF GPS read/write, temporal clustering, orientation review
    duplicate_detector.py  # pHash duplicate detection daemon
    Dockerfile             # Docker build (python:3.12-slim + ffmpeg + pip deps)
    config.yaml.example    # Config reference
  web/
    web_ui.html            # Web interface (volume-mounted, not baked into image)
  roku/
    source/
      Utils.brs            # buildUrl() with auth secret injection
    components/            # BrightScript SceneGraph components
    deploy.sh              # Single-device deploy
    deploy_all.sh          # Multi-device deploy
  docs/
    GEOTAG_*.md            # Geotag system design and status docs
```
