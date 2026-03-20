# AI Context — 3 Bad Dogs

This file provides context for AI coding assistants (Claude, Gemini, Copilot, etc.)
working on this project. Read this before making changes.

## Project Overview

Photo frame + camera viewer system with three frontends:
- **Roku app** (BrightScript SceneGraph) — channel + screensaver
- **Web UI** (single HTML file) — browser-based camera viewer
- **Python server** (Docker) — backend serving photos, camera snapshots, HLS streams, PTZ, HA data

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Roku App   │────▶│  Python Server   │────▶│  Thingino    │
│  Web UI     │     │  (port 8099)     │     │  Cameras     │
└─────────────┘     └──────────────────┘     └──────────────┘
       │                                            │
       │            ┌──────────────────┐            │
       └───────────▶│  go2rtc          │◀───────────┘
                    │  (port 1984)     │
                    └──────────────────┘
```

- Server proxies camera snapshots (a_secure_password session auth, basic auth, or no auth)
- go2rtc handles live video streams (HLS, MSE WebSocket, WebRTC)
- Web UI uses **MSE WebSocket** (`/api/ws?src=<name>`) for live video — hls.js doesn't work with go2rtc's HLS muxing
- Roku uses native Video node with HLS for streams
- nginx reverse proxy in front for HTTPS (optional, not required for LAN use)

## File Layout

```
server/
  server.py              # All server logic — HTTP handler, camera polling, ONVIF PTZ, HA integration
  config.yaml.example    # Camera config reference

roku/
  components/
    MainScene.brs/.xml   # Camera browser — list + preview, fullscreen, PTZ mode
    ScreensaverScene.brs/.xml  # Photo frame / camera cycle screensaver
    SettingsView.brs/.xml      # Settings UI (the one actually used by MainScene)
    SettingsScene.brs/.xml     # Older settings (not used, kept for reference)
    HttpTask.brs/.xml          # Async HTTP task node
    CameraListItem.brs/.xml    # Custom list item renderer
  manifest
  deploy.sh              # Deploy to Roku dev mode

web/
  web_ui.html            # Self-contained web UI (no build step)

Dockerfile               # Python 3.12 slim + ffmpeg + Pillow + PyYAML
docker-compose.yaml      # Reference compose file
```

## Key Design Decisions

### Camera List: 12 entries (not 6)
Each camera gets TWO sidebar entries: one for snapshot (jpg) and one for live stream (hls).
Order: all jpg entries first, then all hls entries. Both Roku and web UI follow this pattern.

### Web UI: MSE WebSocket over hls.js
hls.js throws `fragParsingError` / `bufferAppendError` with go2rtc's HLS segments despite H.264 streams.
Solution: extract `src` param from stream URL, connect to `ws://host/api/ws?src=<name>`, use MediaSource API.

### PTZ: ONVIF SOAP with WS-Security
Server sends SOAP ContinuousMove commands with UsernameToken digest auth.
Only cameras with `onvif` config get PTZ support. Currently only living-room.

### Server Config
Config file at `/config/cameras.yaml` inside container (mounted from host).
Falls back to `CAMERAS` env var (legacy JSON format) if no YAML file.

## Roku SceneGraph Pitfalls

These are confirmed bugs/gotchas encountered during development:

1. **`event.getNode()` returns a string (node ID)**, not the node object. Use `event.getData()` to get the observed field's value.

2. **MarkupList consumes OK/up/down keys** internally. They never reach the Scene's `onKeyEvent`. Use `observeField("itemSelected", ...)` to detect OK presses on list items.

3. **Focus must be on a leaf focusable node.** Setting `m.top.setFocus(true)` on the Scene does NOT defocus a child MarkupList. To capture d-pad keys away from a list, set focus on another node with `focusable="true"`.

4. **Hidden nodes retain focus.** Setting `visible=false` doesn't remove focus. Must explicitly call `setFocus(true)` on a different node.

5. **`getFocus()` doesn't exist** in SceneGraph. Use `hasFocus()` or track focus state manually.

6. **Dialog dismissal loses focus.** After setting `m.top.getScene().dialog = invalid`, you must manually restore focus to the desired node.

7. **Task node observer pattern:** Always observe BOTH `response` AND `error` fields. HTTP errors don't trigger the response observer — the app just hangs waiting.

8. **Registry writes need `Flush()`** — `sec.Write()` alone doesn't persist. Always call `sec.Flush()` after writes.

## Server API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/camera/list` | GET | JSON array of camera names |
| `/camera/all_info` | GET | JSON array of `{name, snapshot, stream, stream_type, ptz}` |
| `/camera/<name>` | GET | JPEG snapshot (optional `?w=&h=` resize) |
| `/camera/<name>/info` | GET | Single camera info JSON |
| `/camera/<name>/ptz` | POST | ONVIF PTZ control `{action, direction, speed}` |
| `/random` | GET | Random photo from library (optional `?w=&h=`) |
| `/ha/weather` | GET | Plain text weather from Home Assistant |
| `/ha/forecast` | GET | Plain text 3-day forecast |
| `/ha/event` | GET | Plain text next calendar event |
| `/ha/thermostat` | GET | Plain text thermostat status |
| `/web` | GET | Web UI HTML page |
| `/health` | GET | Health check |

## Deployment

```bash
# Server (on Docker host)
cd /path/to/server
docker compose up -d --build

# Roku (dev mode)
cd roku
./deploy.sh <ROKU_IP> <DEV_PASSWORD>
```

Server bakes `server.py` into the Docker image — `docker restart` does NOT pick up code changes. Must rebuild with `--build`.

## nginx Notes (optional, for HTTPS)

If using nginx as a reverse proxy, do NOT use a broad `location /api/` rule — it will intercept Home Assistant's `/api/websocket`. Instead, use specific paths for go2rtc:
- `/api/ws` (WebSocket for MSE)
- `/api/stream.m3u8` (HLS)
- `/api/streams` (stream list)
- `/api/webrtc` (WebRTC)

## Known Issues

- living-room MSE/HLS stream doesn't play in web UI (other 5 cameras work) — likely codec mismatch
- Docker layer optimization could be improved to avoid `--no-cache` rebuilds
- Logo pic not yet included in photo frame rotation
