# 3 Bad Dogs

A self-hosted photo frame and camera viewer with a Python server, Roku app, and web UI.

Built for [Thingino](https://thingino.com/) cameras but works with anything that serves a snapshot URL or HLS stream. Integrates with [go2rtc](https://github.com/AlexxIT/go2rtc) for live video and [Home Assistant](https://www.home-assistant.io/) for weather/calendar/thermostat data in the screensaver overlay.

![Web UI](docs/web-ui-screenshot.png)

## What's included

| Component | Path | Description |
|-----------|------|-------------|
| **Server** | `server/` | Python HTTP server in Docker -- photo serving, camera proxy, timelapse, geotags, orientation review, duplicate detection, HA integration |
| **Roku app** | `roku/` | BrightScript SceneGraph channel + screensaver with photo/camera modes, PTZ, and floating clock overlay |
| **Web UI** | `web/` | Single-page browser interface for all features (no build step, no npm) |

## Features

### Photo frame
- Random photo slideshow with configurable interval and crossfade
- On-the-fly resize and EXIF-aware rotation
- Geotag location display ("City, Country, DD-MM-YYYY") via `X-Photo-Info` header

### Camera support
- Snapshot proxying with thingino session auth, HTTP Basic auth, or no auth
- HLS streams via go2rtc
- MSE WebSocket live video in the web UI
- ONVIF PTZ controls (pan/tilt/zoom via SOAP with WS-Security)
- Camera discovery from go2rtc stream list

### Timelapse
- Per-camera background frame capture (configurable interval)
- Filmstrip viewer with range slider
- On-demand MP4 video generation via ffmpeg
- Video playback and download from the web UI

### Geotag management
- GPS extraction from EXIF (source of truth is always the image file)
- SQLite metadata database for source tracking, confidence, location names
- Temporal clustering algorithm for auto-inferring missing geotags
- Interactive map view with Leaflet.js in the web UI
- Batch editing and import/export

### Orientation review
- Auto-flags photos with non-normal EXIF orientation on startup
- Side-by-side raw vs. rendered thumbnail comparison
- "Apply fix" bakes the EXIF rotation into pixel data permanently
- Batch "apply all" for bulk correction

### Duplicate detection
- pHash-based perceptual hashing (imagehash library)
- Background scanning with configurable Hamming distance threshold
- Group-based review UI with resolution metadata (megapixels)
- Keep/delete workflow per duplicate group

### Photo library management
- Thumbnail grid sorted by date
- Upload, rotate, and delete photos from the web UI
- Background thumbnail generation

### Home Assistant integration
- Weather, forecast, calendar event, and thermostat data
- Ticker endpoint aggregates HA text + camera snapshots for screensaver overlay

### Authentication
Three-tier auth chain (checked in order):
1. **Session cookie** -- login via web UI with username/password (configured in `config.yaml`)
2. **Shared secret** -- `?auth=<secret>` query param for Roku and remote access
3. **LAN IP bypass** -- private IP addresses are allowed without credentials

An `/auth/verify` endpoint supports nginx `auth_request` subrequests for reverse proxy setups.

## Architecture

```
+---------------+     +------------------+     +--------------+
|  Roku App     |---->|  Python Server   |---->|  Cameras     |
|  Web Browser  |     |  (port 8099)     |     |  (thingino)  |
+---------------+     +------------------+     +--------------+
       |                                              |
       |              +------------------+            |
       +------------->|  go2rtc          |<-----------+
                      |  (port 1984)     |
                      +------------------+
```

- Server proxies camera snapshots (handles auth to cameras)
- go2rtc handles live video streams (HLS, MSE WebSocket, WebRTC)
- Web UI connects to go2rtc via MSE WebSocket (`/api/ws?src=<name>`)
- Roku uses native Video node with HLS for live streams
- Optional nginx reverse proxy in front for HTTPS and remote access

## Prerequisites

- **Server:** Docker and docker-compose
- **Roku:** A Roku device with [Developer Mode enabled](https://developer.roku.com/docs/developer-program/getting-started/developer-setup.md)
- **go2rtc:** Running instance for live video streams (optional -- snapshots work without it)

## Server setup

### 1. Create your config file

```bash
cd server
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your cameras:

```yaml
photo_dir: /media

cameras:
  # Thingino camera with snapshot and session auth
  front-door:
    snapshot: http://192.168.1.55/x/ch0.jpg
    auth:
      type: thingino
      username: admin
      password: mysecret
    timelapse:
      enabled: true
      interval: 60

  # Camera with snapshot + HLS stream + PTZ
  living-room:
    snapshot: http://192.168.1.106/x/ch0.jpg
    stream: http://go2rtc-host:1984/api/stream.m3u8?src=living-room_main
    auth:
      type: thingino
      username: admin
      password: mysecret
    onvif:
      host: 192.168.1.106
      port: 80
      username: onvif-user
      password: onvif-pass

  # Stream-only camera (no snapshot)
  camera-3:
    stream: http://go2rtc-host:1984/api/stream.m3u8?src=camera-3_main

  # Basic auth camera
  garage:
    snapshot: http://192.168.1.100/snapshot.jpg
    auth:
      type: basic
      username: admin
      password: mysecret

  # No-auth camera
  weathercam:
    snapshot: http://192.168.1.200/image.jpg

# Optional: web UI authentication
web_auth:
  username: myuser
  password: mypass

# Optional: shared secret for remote access (Roku + ?auth= param)
remote_auth_secret: some-random-string

# Optional: Home Assistant integration
ha_url: http://homeassistant:8123
ha_token: YOUR_LONG_LIVED_ACCESS_TOKEN
```

See [`config.yaml.example`](server/config.yaml.example) for all options.

### 2. Docker Compose

```yaml
services:
  photoframe:
    build: ./server
    container_name: photoframe-server
    restart: unless-stopped
    ports:
      - "8099:8099"
    volumes:
      - ./config.yaml:/config/cameras.yaml:ro    # Camera/server config
      - /path/to/your/photos:/media:ro           # Photo library
      - ./web:/web:ro                            # Web UI (live reload)
      - ./timelapse:/data/timelapse              # Timelapse frames (MUST persist)
      - ./geotags:/data/geotags                  # Geotag database
      - ./thumbnails:/data/thumbnails            # Generated thumbnails
```

**Important:** The timelapse and geotags volumes must be persistent bind mounts. Without them, captured frames and geotag data are lost on container recreate.

### 3. Start the server

```bash
docker compose up -d --build
```

The server runs on port **8099**. Verify:
- Health check: `http://<server-ip>:8099/health`
- Camera list: `http://<server-ip>:8099/camera/list`
- Web UI: `http://<server-ip>:8099/web`

### Dockerfile details

The server image is based on `python:3.12-slim` and installs:
- **ffmpeg** (apt) -- required for timelapse video generation
- **Pillow, PyYAML, requests, piexif, imagehash** (pip) -- image processing, config, geotags, duplicate detection

`server.py`, `geotag_manager.py`, and `duplicate_detector.py` are `COPY`'d into the image. Code changes require `docker compose up -d --build` (a plain `docker restart` will not pick them up). The web UI HTML is volume-mounted so browser refresh is enough after editing.

`PYTHONUNBUFFERED=1` is set so `docker logs` shows output in real time.

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHOTO_DIR` | `/media` | Directory containing photos (mount via volume) |
| `PORT` | `8099` | Server listen port |
| `REFRESH` | `30` | Photo frame HTML page refresh interval (seconds) |
| `CAMERAS_FILE` | `/config/cameras.yaml` | Path to config file |
| `GO2RTC_URL` | (empty) | go2rtc base URL for stream discovery |
| `FRIGATE_URL` | (empty) | Frigate base URL for API proxy |
| `HA_URL` | (empty) | Home Assistant URL |
| `HA_TOKEN` | (empty) | HA long-lived access token |
| `TIMELAPSE_STORAGE_PATH` | `/data/timelapse` | Where timelapse frames are stored |
| `GEOTAG_DB_PATH` | `/data/geotags/geotags.db` | SQLite geotag database path |
| `THUMBNAIL_DIR` | `/data/thumbnails` | Generated thumbnail storage |

### Camera config options

| Field | Required | Description |
|-------|----------|-------------|
| `snapshot` | No | Snapshot URL (JPEG) |
| `stream` | No | HLS stream URL (typically via go2rtc) |
| `stream_type` | No | `hls` (default if stream present) |
| `auth.type` | No | `thingino` (session auth) or `basic` (HTTP Basic) |
| `auth.username` | With auth | Camera username |
| `auth.password` | With auth | Camera password |
| `onvif.host` | No | ONVIF PTZ host |
| `onvif.port` | No | ONVIF port (default: 80) |
| `onvif.username` | With ONVIF | ONVIF credentials |
| `onvif.password` | With ONVIF | ONVIF credentials |
| `timelapse.enabled` | No | Enable background frame capture |
| `timelapse.interval` | No | Seconds between captures (default: 60) |
| `timelapse.source` | No | `snapshot` (default) or `stream` |

At least one of `snapshot` or `stream` is needed per camera. Camera names should be **all lowercase**.

## Web UI

The web interface at `/web` is a single self-contained HTML file with seven tabs:

| Tab | Description |
|-----|-------------|
| **Live View** | Camera snapshots (1fps refresh) and MSE WebSocket live video, PTZ controls for ONVIF cameras |
| **Time-lapse** | Per-camera timeline with filmstrip, video generation, playback, and download |
| **Geotags** | Interactive Leaflet map, photo grid with GPS status badges, batch editing, auto-inference |
| **Library** | Photo thumbnail grid with upload, rotate, and delete |
| **Orientation** | Review photos with non-normal EXIF rotation; apply fix individually or in batch |
| **Duplicates** | Review pHash-detected duplicate groups; keep/delete per group |
| **Configuration** | Camera settings, timelapse config, server settings, auth secret management |

The web UI also has a built-in **screensaver mode** (photo frame / camera cycle / live video) with a bouncing clock overlay, accessible via the "Start Screensaver" button.

Color theme: robin's egg blue (`#3a7ca5`) + blaze orange (`#FF6700`) with white text.

## Roku app

The Roku channel (version 2.1) installs as both an **app** and a **screensaver**.

### App -- Camera browser
- Browse all cameras in a list with live preview panel
- OK button for fullscreen view
- HLS live video for cameras with stream URLs
- D-pad PTZ controls in fullscreen (for ONVIF cameras)
- Fast-forward / rewind for zoom in/out

### Screensaver -- Two modes
- **Photo Frame** -- random photos with crossfade (configurable interval)
- **Camera Cycle** -- rotates through all cameras (configurable interval)

Both modes share a **clock overlay** with rotating ticker items (weather, calendar, thermostat, camera thumbnails) pulled from the `/ticker` endpoint. Clock style is configurable: **bounce** (floating), **fade** (crossfade in place), or **off**.

The screensaver displays geotag info ("City, Country, DD-MM-YYYY") on photos when available, read from the `X-Photo-Info` response header.

### Settings

Two pages of settings, accessible from **Roku Settings > Screensaver > 3 Bad Dogs**:

**Page 1:**
- **Server URL** -- base URL of the server (e.g. `http://192.168.1.245:8099`)
- **Auth Secret** -- shared secret for remote access (appended as `?auth=<secret>` to all requests)
- **Screensaver mode** -- photo frame, camera cycle, or live video
- **Camera** -- specific camera or "cycle all"

**Page 2:**
- **Photo interval** -- 15 / 30 / 60 / 120 seconds
- **Camera cycle interval** -- 3 / 5 / 10 / 15 seconds
- **Clock style** -- bounce / fade / off
- **Clock opacity** -- 0% / 40% / 60% / 80%

### Deploying to Roku

Single-device deploy:
```bash
cd roku
./deploy.sh <ROKU_IP> <DEV_PASSWORD>
```

Multi-device deploy (all known Rokus):
```bash
cd roku
./deploy_all.sh [PASSWORD]
```

For creating distributable packages, see the packaging section below.

### Creating a distributable package

1. Run `./package.sh` in the `roku/` directory to create a zip
2. Log into your Roku's web portal at its IP address
3. Go to the **Packager** utility
4. Upload the zip, sign with your developer key
5. Download the resulting `.pkg` file

## Remote access

For accessing the server outside your LAN (e.g., Roku at a different location):

1. Set `remote_auth_secret` in `config.yaml`
2. Set up an nginx reverse proxy with a `/photoframe/` location pointing to the server
3. Configure the Roku's **Server URL** to your external address (e.g., `https://yourdomain.com/photoframe`)
4. Set the Roku's **Auth Secret** to the same value as `remote_auth_secret`

The server automatically rewrites absolute go2rtc stream URLs to relative paths for remote clients (detected by the presence of `?auth=` in the request), so streams route correctly through the reverse proxy.

### nginx reverse proxy notes

If using nginx as a reverse proxy:

```nginx
# Photoframe server
location /photoframe/ {
    proxy_pass http://server-ip:8099/;
}

# go2rtc (MSE WebSocket for live video) -- needs WebSocket upgrade
location /api/ws {
    proxy_pass http://go2rtc-ip:1984;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
location /api/stream.m3u8 {
    proxy_pass http://go2rtc-ip:1984;
}
```

**Do NOT** use a broad `location /api/` -- it will intercept other services (e.g., Home Assistant's `/api/websocket`). Use specific paths for go2rtc only.

For auth via nginx, the server provides `/auth/verify` for use with `auth_request`:

```nginx
location /photoframe/ {
    auth_request /auth/verify;
    proxy_pass http://server-ip:8099/;
}
```

## Server API

### Core endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Standalone HTML photo frame page |
| `/web` | GET | Web UI |
| `/random` | GET | Random photo (`?w=&h=` for resize, `?noexif=1` to strip EXIF) |
| `/health` | GET | Health check |
| `/login` | GET | Login page |
| `/auth/verify` | GET | Auth verification for nginx subrequest |

### Camera endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/camera/list` | GET | JSON array of camera names |
| `/camera/all_info` | GET | JSON array of all camera info objects |
| `/camera/<name>` | GET | JPEG snapshot (`?w=&h=` for resize) |
| `/camera/<name>/info` | GET | JSON: `{name, snapshot, stream, stream_type, ptz}` |
| `/camera/<name>/ptz` | POST | ONVIF PTZ control: `{action, direction, speed}` |
| `/camera/config` | GET | Full camera configuration |
| `/camera/settings` | GET/POST | Global settings + auth secret |

### Timelapse endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/timelapse/config` | GET/POST | Timelapse capture configuration |
| `/timelapse/summary` | GET | Per-camera frame counts and time ranges |
| `/timelapse/frames` | GET | Frame list (`?camera=<name>`) |
| `/timelapse/frame` | GET | Nearest JPEG frame (`?camera=&timestamp=`) |
| `/timelapse/videos` | GET | Generated video list (`?camera=` filter) |
| `/timelapse/videos/<file>` | GET | Serve/download a timelapse MP4 |
| `/timelapse/generate` | POST | Generate MP4: `{cameras[], start_time, end_time, fps}` |

### Library endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/library` | GET | Photo list with thumbnails, sorted by date |
| `/library/thumb` | GET | Thumbnail for a photo (`?name=`) |
| `/library/rotate` | POST | Rotate a photo |
| `/library/delete` | POST | Delete a photo |
| `/library/upload` | POST | Upload new photos |

### Geotag endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/photos/geotags` | GET | Photo list by geotag status (`?status=all\|complete\|missing`) |
| `/photo/<name>/geotag` | GET/PUT | Get or set geotag for a specific photo |
| `/photos/geotag/import-exif` | POST | Index all photos for temporal clustering |
| `/photos/geotag/auto-infer` | POST | Run temporal clustering, return suggestions |
| `/photos/geotag/batch-update` | POST | Apply geotag to multiple photos |

### Orientation endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/orientation/photos` | GET | List photos by review status (`?filter=&limit=&offset=`) |
| `/orientation/counts` | GET | Count per review status |
| `/orientation/thumbnail` | GET | Thumbnail (`?name=&mode=raw\|rendered`) |
| `/orientation/review` | POST | Set review status: `{filename, status}` |
| `/orientation/apply-fix` | POST | Bake EXIF rotation into pixels for one photo |
| `/orientation/apply-all` | POST | Apply fix to all photos marked `needs_fix` |

### Duplicate endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/duplicates/groups` | GET | Unreviewed duplicate groups with photo details |
| `/duplicates/resolve` | POST | Resolve a duplicate group (keep/delete) |

### Home Assistant / ticker endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ha/weather` | GET | Current weather summary |
| `/ha/forecast` | GET | 3-day forecast |
| `/ha/event` | GET | Next calendar event |
| `/ha/thermostat` | GET | Thermostat status |
| `/ticker` | GET | JSON: screensaver ticker items (HA text + camera image URLs) |

## File layout

```
3-bad-dogs/
  server/
    server.py              # Python HTTP server (all endpoint logic)
    geotag_manager.py      # Geotag database, EXIF read/write, temporal clustering
    duplicate_detector.py  # pHash duplicate detection
    Dockerfile             # python:3.12-slim + ffmpeg + Pillow + PyYAML + piexif + imagehash
    config.yaml.example    # Config reference
  web/
    web_ui.html            # Self-contained web UI (no build step)
  roku/
    manifest               # Roku channel manifest (v2.1)
    source/
      Utils.brs            # buildUrl() with auth secret injection, helpers
    components/
      MainScene.brs/.xml        # Camera browser app
      ScreensaverScene.brs/.xml # Photo frame / camera cycle screensaver
      SettingsView.brs/.xml     # Two-page settings UI
      SettingsScene.brs/.xml    # Screensaver settings entry point
      HttpTask.brs/.xml         # Async HTTP task node
      CameraListItem.brs/.xml   # Custom list item renderer
    images/
      icon.png, splash.jpg
    deploy.sh              # Single-device deploy
    deploy_all.sh          # Multi-device deploy
  docs/
    GEOTAG_*.md            # Geotag system design and status docs
    AUTO_GEOTAG_RESEARCH.md
  DEBUGGING.md             # Roku debugging guide (telnet, deploy troubleshooting)
  DEPLOYMENT_AND_TESTING.md # Server deployment and test procedures
  AI_CONTEXT.md            # Context file for AI coding assistants
```

## Deployment

For the full deployment and testing workflow, see [DEPLOYMENT_AND_TESTING.md](DEPLOYMENT_AND_TESTING.md).

Quick version:

```bash
# Copy files to server host
scp server/server.py server/geotag_manager.py server/duplicate_detector.py \
    root@yourserver:/path/to/photoframe-server/
scp server/Dockerfile root@yourserver:/path/to/photoframe-server/Dockerfile
scp web/web_ui.html root@yourserver:/path/to/photoframe-server/web/web_ui.html

# Rebuild and restart
ssh root@yourserver "cd /path/to/compose && docker compose up -d --build photoframe"
```

Web UI changes (HTML only) don't require a rebuild -- just copy the file and refresh the browser.

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) -- Creative Commons Attribution-NonCommercial-ShareAlike 4.0

Copyright (c) 2026 Mike Cirioli
