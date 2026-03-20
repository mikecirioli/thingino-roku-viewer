# GEMINI_HINT.md — Critical Context for AI Assistants

This file exists because a previous AI session broke the web UI by rewriting it from scratch instead of extending the existing code. Read this carefully before making changes.

## Golden Rules

1. **DO NOT rewrite files from scratch.** Always read the existing code first and make targeted additions.
2. **DO NOT change the color theme.** The app uses a robin's egg blue / blaze orange theme (`--bg-color: #3a7ca5`, `--accent-color: #FF6700`). Do not change it.
3. **DO NOT remove existing features.** The web UI has: screensaver mode, PTZ controls, settings modal, MSE WebSocket streaming, timelapse filmstrip, and localStorage persistence. All must be preserved.
4. **DO NOT use generic element auto-discovery patterns.** The DOM elements are manually mapped in the `els` object with explicit `document.getElementById()` calls. Keep it that way.
5. **Test your JS mentally.** If you reference `els.someProperty`, make sure that exact key exists in the `els` object.
6. **Camera names are all lowercase.** Do not use camelCase for camera names in config or code.

## Architecture Overview

### Server (`server/server.py`)
- Pure Python HTTP server (no framework), runs in Docker
- Camera config loaded from `/config/cameras.yaml` (YAML) or `CAMERAS` env var (legacy JSON)
- `CameraStream` class handles snapshot polling with thingino session auth, basic auth, or no auth
- `TimelapseCapturer` class runs background frame capture in a daemon thread
  - Config persisted to `/data/timelapse/timelapse_config.json` (cameras.yaml is read-only)
  - Captures first frame immediately when enabled, then schedules periodic captures
  - IMPORTANT: `set_config()` must NOT hold `self._lock` when calling `_schedule_next_capture()` — this caused a deadlock
- ONVIF PTZ via raw SOAP with WS-Security UsernameToken digest auth
- HA integration for weather/calendar/thermostat data
- All timestamps are UTC; `_frame_to_iso()` appends `Z` suffix so browsers convert to local time

### Web UI (`web/web_ui.html`)
- Single HTML file, no build system, no npm
- Uses go2rtc **MSE WebSocket** for live video (NOT HLS — HLS had fragParsingError issues)
- MSE flow: `MediaSource` -> WebSocket to `/api/ws?src=<name>` -> first text message has codec -> `addSourceBuffer` -> binary messages are media segments
- HLS.js is loaded as a fallback only for non-go2rtc streams
- **Live View tab**: Sidebar shows cameras with (jpg) and (hls) entries separately
- **Time-lapse tab**: Sidebar shows one entry per camera (no jpg/hls suffix), filmstrip of actual frames sampled evenly, range slider, video generation
- Screensaver mode: photo frame / camera cycle / live video with bouncing clock overlay
- All state in a single `state` object; all DOM refs in a single `els` object
- Autosave on capture config changes (no save button)

### Key URL patterns
- go2rtc streams are proxied through nginx: `/api/ws?src=<name>` -> go2rtc at 192.168.1.207:1984
- Camera snapshots: `/camera/<name>` (server fetches from thingino with auth)
- Timelapse API: `/timelapse/summary`, `/timelapse/frames?camera=X`, `/timelapse/videos`, `/timelapse/generate`, `/timelapse/frame?camera=X&timestamp=T`, `/timelapse/config`

## Docker Configuration

### Required Volume Mounts

The photoframe container needs these volumes in the docker-compose.yaml on optiplex (`/export/homeassistant/docker-compose.yaml`):

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
      - ./media/ciriolisaver:/media:ro                             # Photo library (read-only)
      - ./photoframe-server/web:/web:ro                            # Web UI HTML (read-only, live reload)
      - ./photoframe-server/timelapse:/data/timelapse              # Timelapse frames + config (read-write, MUST persist)
      - ./photoframe-server/logs:/logs                             # Server logs
      - ./photoframe-server/packages:/packages:ro                  # Extra packages
```

**CRITICAL**: The timelapse volume (`/data/timelapse`) MUST be a persistent bind mount. Without it, all captured frames and timelapse config are lost on container recreate.

### Dockerfile Requirements

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow PyYAML
COPY server.py /app/server.py
WORKDIR /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8099
CMD ["python3", "server.py"]
```

Key points:
- **ffmpeg** is required for timelapse video generation
- **PYTHONUNBUFFERED=1** is required so `docker logs` shows output in real time
- server.py is COPY'd (baked in) — changes require `docker compose up -d --build`
- web_ui.html is volume-mounted — changes are live on browser refresh

### Network Access

**Simple (direct access on internal network):** No reverse proxy needed. Just expose port 8099 and access the server directly:

```
http://<server-ip>:8099/web       # Web UI
http://<server-ip>:8099/camera/list  # API
```

All endpoints (`/camera/*`, `/timelapse/*`, `/web/*`, `/ha/*`) are served by the single photoframe container on port 8099. go2rtc MSE WebSocket streams connect directly from the browser to go2rtc (configured in the web UI as `/api/ws?src=<name>`).

**With nginx reverse proxy:** If you run nginx in front (e.g. for TLS, auth, or routing multiple services on port 80/443), you need location blocks for each backend:

```nginx
# Photoframe server
location /web { proxy_pass http://<server-ip>:8099; }
location /camera/ { proxy_pass http://<server-ip>:8099; }
location /timelapse/ { proxy_pass http://<server-ip>:8099; }
location /ha/ { proxy_pass http://<server-ip>:8099; }
location /health { proxy_pass http://<server-ip>:8099; }

# go2rtc (MSE WebSocket for live video) — needs WebSocket upgrade
location /api/ws { proxy_pass http://<go2rtc-ip>:1984; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
location /api/stream.m3u8 { proxy_pass http://<go2rtc-ip>:1984; }
```

IMPORTANT: Do NOT use a broad `location /api/` — it will intercept other services (e.g. Home Assistant's `/api/websocket`). Use specific paths.

## Deployment and Testing

### Prerequisites
- Development machine with the repo at `/export/git/3-bad-dogs/`
- Deploy target: `root@optiplex` (SSH access required)
- Server app directory on optiplex: `/export/homeassistant/photoframe-server/`
- Docker compose file: `/export/homeassistant/docker-compose.yaml` (NOT the one in photoframe-server/)
- The Dockerfile is in `server/Dockerfile` in the repo, deployed to `photoframe-server/Dockerfile` on optiplex

### Step-by-Step Deployment

1. **Copy changed files to optiplex:**

```bash
# From repo root (/export/git/3-bad-dogs/)
scp server/server.py root@optiplex:/export/homeassistant/photoframe-server/server.py
scp web/web_ui.html root@optiplex:/export/homeassistant/photoframe-server/web/web_ui.html
```

If the Dockerfile changed:
```bash
scp server/Dockerfile root@optiplex:/export/homeassistant/photoframe-server/Dockerfile
```

2. **Rebuild and restart the container:**

```bash
ssh root@optiplex "cd /export/homeassistant && docker compose up -d --build photoframe"
```

IMPORTANT: `docker restart` does NOT pick up code changes. You MUST use `docker compose up -d --build`.

3. **Verify the deploy:**

```bash
# Health check
curl http://optiplex:8099/health

# Camera list (should return JSON array of lowercase camera names)
curl http://optiplex:8099/camera/list

# Check container logs for errors
ssh root@optiplex "docker logs --tail 50 photoframe-server"
```

### Testing the Web UI

1. Open `http://optiplex:8099/web` in a browser
2. **Camera list**: Should show 6 cameras (armory, backyard, critter, frontporch, gatetown, pancam)
3. **Live View tab**: Sidebar shows (jpg) and (hls) entries = 12 sidebar items
4. **Snapshot mode**: Click a (jpg) entry, image should appear and refresh every second
5. **Stream mode**: Click a (hls) entry, MSE WebSocket video should start playing
6. **PTZ**: Select pancam, PTZ d-pad should appear. Press and hold arrows to pan.
7. **Time-lapse tab**: Sidebar simplifies to 6 entries (no jpg/hls suffix). Click a camera to see filmstrip, timeline, and video list.
8. **Screensaver**: Click "Start Screensaver", photos should cycle with bouncing clock overlay.
9. **Settings**: Click "Settings", change screensaver mode, save.

### Testing Timelapse Specifically

```bash
# Check if frames are being captured
ssh root@optiplex "ls /export/homeassistant/photoframe-server/timelapse/gatetown/ | tail -5"

# Check server logs for capture messages
ssh root@optiplex "docker logs --tail 20 photoframe-server | grep timelapse"

# Test frame list endpoint
curl http://optiplex:8099/timelapse/frames?camera=gatetown
```

### Quick Web UI Test (no deploy needed)

For fast iteration on the web UI HTML only (no server.py changes):

```bash
scp web/web_ui.html root@optiplex:/export/homeassistant/photoframe-server/web/web_ui.html
```

Then just refresh the browser — no container rebuild needed.

## Common Mistakes to Avoid

| Mistake | Why it breaks things |
|---------|---------------------|
| Using HLS.js for go2rtc streams | fragParsingError — go2rtc serves MSE-compatible streams, not standard HLS |
| Changing `els` to auto-discovered camelCase | HTML IDs are kebab-case, JS object keys are manually named — mismatch crashes everything |
| Removing the screensaver/PTZ/settings code | Users depend on these features |
| Using `docker restart` instead of `docker compose up --build` | Code changes baked into image are not picked up |
| Changing the color theme | The robin's egg blue/blaze orange theme is intentional |
| Adding npm/webpack/build steps | This is a single-file HTML app, no build system |
| Missing timelapse volume mount | Frames and config lost on container recreate |
| Missing nginx `/timelapse/` location | All timelapse API calls return 404 |
| Holding lock in `set_config` while calling `_schedule_next_capture` | Deadlock — both methods acquire `self._lock` |
| Timestamps without `Z` suffix | Browser shows UTC times as local, off by hours |
| Using camelCase camera names | All camera names must be lowercase |
| Missing `PYTHONUNBUFFERED=1` in Dockerfile | `docker logs` shows no output |
| Missing `ffmpeg` in Dockerfile | Timelapse video generation fails |

## File Layout

```
3-bad-dogs/
  server/
    server.py          # Python HTTP server (baked into Docker image)
    Dockerfile         # Docker build (python:3.12-slim + ffmpeg + Pillow + PyYAML)
    config.yaml.example
    docker-compose.yaml  # Reference only — actual compose is on optiplex
  web/
    web_ui.html        # Web interface (volume-mounted, not baked into image)
    logo.png           # 3 Bad Dogs logo (favicon + header)
  roku/
    ...                # Roku BrightScript app (separate deploy via deploy.sh)
  GEMINI_HINT.md       # This file
```

## Network Topology

```
Browser -> nginx (reverse proxy on optiplex)
  /web         -> photoframe container :8099
  /camera/*    -> photoframe container :8099
  /timelapse/* -> photoframe container :8099
  /api/ws      -> go2rtc (inside Frigate) on 192.168.1.207:1984
  /api/stream* -> go2rtc on 192.168.1.207:1984

Cameras (thingino) -> photoframe server fetches snapshots with session auth
go2rtc (Frigate)   -> MSE WebSocket streams proxied through nginx
```
