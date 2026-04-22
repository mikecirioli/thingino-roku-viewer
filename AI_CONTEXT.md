# AI Context -- 3 Bad Dogs

This file provides context for AI coding assistants (Claude, Gemini, Copilot, etc.)
working on this project. Read this before making changes.

## Project Overview

Photo frame + camera viewer system with three frontends:
- **Roku app** (BrightScript SceneGraph) -- channel + screensaver
- **Web UI** (single HTML file) -- browser-based interface for all features
- **Python server** (Docker) -- backend serving photos, camera snapshots, streams, geotags, orientation review, duplicate detection, timelapse, HA data

## Architecture

```
+--------------+     +------------------+     +--------------+
|  Roku App    |---->|  Python Server   |---->|  Thingino    |
|  Web UI      |     |  (port 8099)     |     |  Cameras     |
+--------------+     +------------------+     +--------------+
       |                                            |
       |            +------------------+            |
       +----------->|  go2rtc          |<-----------+
                    |  (port 1984)     |
                    +------------------+
```

- Server proxies camera snapshots (thingino session auth, basic auth, or no auth)
- go2rtc handles live video streams (HLS, MSE WebSocket, WebRTC)
- Web UI uses **MSE WebSocket** (`/api/ws?src=<name>`) for live video -- hls.js doesn't work with go2rtc's HLS muxing
- Roku uses native Video node with HLS for streams
- nginx reverse proxy in front for HTTPS (optional, not required for LAN use)

### Authentication

Three-tier auth chain in `_is_request_authorized()`:
1. Session cookie (SHA-256 hash of `username:password`)
2. `?auth=<secret>` query param (remote Roku access, set via `remote_auth_secret` in config)
3. LAN IP bypass (private IP addresses pass without credentials)

`/auth/verify` endpoint for nginx `auth_request` subrequests (no IP bypass -- stricter).

### Remote access

When `_is_remote_request()` detects `?auth=` param, `camera_info()` rewrites absolute go2rtc stream URLs to relative paths so streams route through the same base URL the client is using.

## File Layout

```
server/
  server.py              # All server logic -- HTTP handler, camera polling, ONVIF PTZ, HA integration,
                         # timelapse, orientation review, duplicate detection, geotag API, library management
  geotag_manager.py      # GeotagDatabase class, EXIF GPS read/write, temporal clustering
  duplicate_detector.py  # DuplicateDetector class -- pHash calculation, Hamming distance, group clustering
  config.yaml.example    # Camera config reference
  Dockerfile             # python:3.12-slim + ffmpeg + Pillow + PyYAML + requests + piexif + imagehash

roku/
  source/
    Utils.brs            # buildUrl() for auth secret injection, urlEncode(), maskSecret()
  components/
    MainScene.brs/.xml   # Camera browser -- list + preview, fullscreen, PTZ mode
    ScreensaverScene.brs/.xml  # Photo frame / camera cycle screensaver with clock overlay + ticker
    SettingsView.brs/.xml      # Two-page settings UI (used by SettingsScene)
    SettingsScene.brs/.xml     # Screensaver settings entry point
    HttpTask.brs/.xml          # Async HTTP task node
    CameraListItem.brs/.xml    # Custom list item renderer
  manifest
  deploy.sh              # Deploy to single Roku dev mode device
  deploy_all.sh          # Deploy to all known Roku devices

web/
  web_ui.html            # Self-contained web UI (no build step)
```

## Key Design Decisions

### Camera sidebar entries
Each camera gets TWO sidebar entries in Live View: one for snapshot (jpg) and one for live stream (hls).
Order: all jpg entries first, then all hls entries. In Timelapse tab, one entry per camera (no suffix).

### Web UI: MSE WebSocket over hls.js
hls.js throws `fragParsingError` / `bufferAppendError` with go2rtc's HLS segments despite H.264 streams.
Solution: extract `src` param from stream URL, connect to `ws://host/api/ws?src=<name>`, use MediaSource API.

### PTZ: ONVIF SOAP with WS-Security
Server sends SOAP ContinuousMove commands with UsernameToken digest auth.
Only cameras with `onvif` config get PTZ support.

### Server Config
Config file at `/config/cameras.yaml` inside container (mounted from host).
Falls back to `CAMERAS` env var (legacy JSON format) if no YAML file.
Settings (`web_auth`, `remote_auth_secret`, `settings`) are read from and written back to the same YAML file.

### Geotag storage
GPS coordinates stored IN the image EXIF (portable). SQLite database stores management metadata only (source, confidence, location_name). Database is optional and rebuildable.

### Orientation review
On startup, server backfills orientation review rows and auto-flags photos with non-normal EXIF orientation tag. "Apply fix" uses Pillow's `exif_transpose()` to bake rotation into pixels, then strips the EXIF orientation tag.

### Duplicate detection
`DuplicateDetector` runs as a background daemon. Calculates pHash (perceptual hash) via imagehash library. Groups photos by Hamming distance < 10 (configurable). Stores groups in SQLite for review.

### Ticker endpoint
`/ticker` returns JSON array of items: HA text data (weather, forecast, thermostat, calendar) + camera snapshot URLs. Cached 120s. Used by Roku screensaver for rotating overlay content.

### Screensaver clock
Three styles: "bounce" (floating position), "fade" (crossfade in place with configurable hold time), "off". Ticker items rotate on a timer (15s bounce, configurable for fade).

## Web UI Architecture

- Seven tabs: Live View, Time-lapse, Geotags, Library, Orientation, Duplicates, Configuration
- All state in a single `state` object; all DOM refs in a single `els` object
- DOM elements mapped manually with explicit `document.getElementById()` calls
- No build system, no npm, no framework
- Autosave on capture config changes (no save button)
- localStorage persistence for UI state
- Screensaver mode built in (photo frame / camera cycle / live video with bouncing clock)
- Color theme: robin's egg blue (`#3a7ca5`) + blaze orange (`#FF6700`), white text

## Roku SceneGraph Pitfalls

These are confirmed bugs/gotchas encountered during development:

1. **`event.getNode()` returns a string (node ID)**, not the node object. Use `event.getData()` to get the observed field's value.

2. **MarkupList consumes OK/up/down keys** internally. They never reach the Scene's `onKeyEvent`. Use `observeField("itemSelected", ...)` to detect OK presses on list items.

3. **Focus must be on a leaf focusable node.** Setting `m.top.setFocus(true)` on the Scene does NOT defocus a child MarkupList. To capture d-pad keys away from a list, set focus on another node with `focusable="true"`.

4. **Hidden nodes retain focus.** Setting `visible=false` doesn't remove focus. Must explicitly call `setFocus(true)` on a different node.

5. **`getFocus()` doesn't exist** in SceneGraph. Use `hasFocus()` or track focus state manually.

6. **Dialog dismissal loses focus.** After setting `m.top.getScene().dialog = invalid`, you must manually restore focus to the desired node.

7. **Task node observer pattern:** Always observe BOTH `response` AND `error` fields. HTTP errors don't trigger the response observer -- the app just hangs waiting.

8. **Registry writes need `Flush()`** -- `sec.Write()` alone doesn't persist. Always call `sec.Flush()` after writes.

9. **RadioButtonList traps up/down keys** -- consumes them even at boundaries. Use left/right for inter-control navigation, or two-column layout for escape.

## Roku Settings

Two-page settings via `SettingsView.brs`:
- Page 1: Server URL, Auth Secret, Screensaver mode, Camera selection
- Page 2: Photo interval, Camera cycle interval, Clock style, Clock opacity

All settings stored in `roRegistrySection("settings")`. `Utils.brs` provides `buildUrl()` which reads `serverAuth` from registry and appends `?auth=<secret>` to all URLs.

## Server API Summary

### GET endpoints
| Path | Description |
|------|-------------|
| `/` | Standalone HTML photo frame |
| `/web` | Web UI |
| `/random` | Random photo (`?w=&h=`, `?noexif=1`) |
| `/camera/list` | JSON array of camera names |
| `/camera/all_info` | JSON array of camera info objects |
| `/camera/<name>` | JPEG snapshot (`?w=&h=`) |
| `/camera/<name>/info` | Single camera info JSON |
| `/camera/config` | Full camera configuration |
| `/camera/settings` | Global settings + auth secret |
| `/ticker` | Screensaver ticker items |
| `/ha/weather`, `/ha/forecast`, `/ha/event`, `/ha/thermostat` | HA data |
| `/timelapse/config` | Timelapse capture config |
| `/timelapse/summary` | Per-camera frame counts |
| `/timelapse/frames` | Frame list (`?camera=`) |
| `/timelapse/frame` | Nearest JPEG frame (`?camera=&timestamp=`) |
| `/timelapse/videos` | Generated videos |
| `/timelapse/videos/<file>` | Serve/download MP4 |
| `/library` | Photo list with thumbnails |
| `/library/thumb` | Single thumbnail (`?name=`) |
| `/photos/geotags` | Photos by geotag status (`?status=`) |
| `/photo/<name>/geotag` | Single photo geotag |
| `/orientation/photos` | Photos by review status (`?filter=&limit=&offset=`) |
| `/orientation/counts` | Counts per review status |
| `/orientation/thumbnail` | Orientation thumbnail (`?name=&mode=raw\|rendered`) |
| `/duplicates/groups` | Unreviewed duplicate groups |
| `/auth/verify` | Auth verification for nginx |
| `/login` | Login page |
| `/health` | Health check |

### POST endpoints
| Path | Description |
|------|-------------|
| `/camera/<name>/ptz` | ONVIF PTZ control |
| `/camera/settings` | Update global settings |
| `/camera/config` | Update camera config |
| `/timelapse/config` | Update timelapse config |
| `/timelapse/generate` | Generate MP4 |
| `/library/rotate` | Rotate a photo |
| `/library/delete` | Delete a photo |
| `/library/upload` | Upload photos |
| `/photos/geotag/import-exif` | Index photos for clustering |
| `/photos/geotag/auto-infer` | Run temporal clustering |
| `/photos/geotag/batch-update` | Apply geotag to multiple photos |
| `/orientation/review` | Set review status |
| `/orientation/apply-fix` | Bake EXIF rotation into pixels |
| `/orientation/apply-all` | Apply fix to all needs_fix photos |
| `/duplicates/resolve` | Resolve a duplicate group |

### PUT endpoints
| Path | Description |
|------|-------------|
| `/photo/<name>/geotag` | Set geotag for a specific photo |

## Deployment

```bash
# Server (copy to Docker host, then rebuild)
scp server/server.py server/geotag_manager.py server/duplicate_detector.py \
    root@server:/path/to/photoframe-server/
ssh root@server "cd /path/to/compose && docker compose up -d --build photoframe"

# Roku (dev mode)
cd roku
./deploy.sh <ROKU_IP> <DEV_PASSWORD>
```

Server bakes Python files into the Docker image -- `docker restart` does NOT pick up code changes. Must rebuild with `--build`.

Web UI HTML is volume-mounted -- copy and refresh browser. No rebuild needed.

## nginx Notes (optional, for HTTPS / remote access)

Do NOT use a broad `location /api/` rule -- it will intercept Home Assistant's `/api/websocket`. Use specific paths for go2rtc:
- `/api/ws` (WebSocket for MSE)
- `/api/stream.m3u8` (HLS)

For remote access, use `location /photoframe/` proxying to the server, with `auth_request /auth/verify` for authentication.

## Common Mistakes to Avoid

| Mistake | Why it breaks things |
|---------|---------------------|
| Using HLS.js for go2rtc streams | fragParsingError -- go2rtc serves MSE-compatible streams |
| Changing `els` to auto-discovered camelCase | HTML IDs are kebab-case, JS keys are manual -- mismatch crashes |
| Using `docker restart` instead of `--build` | Code baked into image not picked up |
| Changing the color theme | Robin's egg blue / blaze orange is intentional |
| Adding npm/webpack/build steps | Single-file HTML app, no build system |
| Missing timelapse volume mount | Frames and config lost on container recreate |
| Holding lock in `set_config` while calling `_schedule_next_capture` | Deadlock |
| Timestamps without `Z` suffix | Browser shows UTC as local, off by hours |
| Using camelCase camera names | All camera names must be lowercase |
| Missing `PYTHONUNBUFFERED=1` in Dockerfile | `docker logs` shows no output |
| Missing ffmpeg in Dockerfile | Timelapse video generation fails |
| Missing piexif in Dockerfile | Geotag EXIF writing fails |
| Missing imagehash in Dockerfile | Duplicate detection fails |
