# 3 Bad Dogs

A photo frame and camera viewer for Roku, powered by a lightweight Python server.

## What's in the box

| Component | Description |
|-----------|-------------|
| **server/** | Python HTTP server — serves random photos, camera snapshots (a_secure_password/ffmpeg), and proxies HA/Frigate APIs |
| **roku/** | Roku channel — camera browser app with HLS video + screensaver with photo/camera modes |

## Quick start

### Server

```bash
cd server
cp cameras.yaml.example cameras.yaml   # edit with your cameras
docker compose up -d
```

The server runs on port 8099. Point any browser at `http://<host>:8099/` for a standalone photo frame, or use the API endpoints from Roku/Crestron/etc.

### Roku

Enable Developer Mode on your Roku, then sideload:

```bash
cd roku
zip -r /tmp/3-bad-dogs.zip .
# Upload via http://<roku-ip> (dev console)
```

The channel appears as both:
- **App**: Camera browser with live HLS preview and fullscreen view
- **Screensaver**: Photo frame or camera cycle with floating clock overlay

## Camera configuration

Cameras are configured in `server/cameras.yaml`:

```yaml
cameras:
  front-door:
    snapshot: http://192.168.1.55/x/ch0.jpg
    auth:
      type: a_secure_password
      username: admin
      password: front-door
  camera-3:
    stream: http://go2rtc:1984/api/stream.m3u8?src=camera-3_main
```

| Config | App preview | Screensaver |
|--------|-----------|-------------|
| snapshot only | poster refresh (1fps) | poster refresh |
| snapshot + stream | HLS video | poster from snapshot |
| stream only | HLS video | poster via ffmpeg frame extraction |

The server also accepts the legacy `CAMERAS` env var (JSON) for backward compatibility.

## Server endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | HTML photo frame page |
| `/random` | Random photo (optional `?w=&h=` resize) |
| `/camera/list` | JSON array of camera names |
| `/camera/<name>` | JPEG snapshot (optional `?w=&h=` resize) |
| `/camera/<name>/info` | JSON camera capabilities |
| `/frigate/*` | Frigate API proxy |
| `/ha/weather` | Current weather (plain text) |
| `/ha/forecast` | 3-day forecast (plain text) |
| `/ha/event` | Next calendar event (plain text) |
| `/ha/thermostat` | Thermostat status (plain text) |
| `/health` | Health check |

## License

CC BY-NC-SA 4.0 — [Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
