# Thingino Roku Viewer

A photo frame and camera viewer for Roku, powered by a lightweight Docker server (formerly 3 Bad Dogs).

Works great with [Thingino](https://thingino.com/) cameras — snapshot, HLS live video, and PTZ controls all supported out of the box.

![Web UI](docs/web-ui-screenshot.png)

## What's included

| Component | Description |
|-----------|-------------|
| **server/** | Docker-based Python server — serves random photos, camera snapshots, HLS streams, and ONVIF PTZ |
| **roku/** | Roku channel — camera browser app + screensaver with photo/camera/video modes |

## Prerequisites

- **Server:** `docker` and `docker-compose` must be installed.
- **Roku:** A Roku device with [Developer Mode enabled](https://developer.roku.com/docs/developer-program/getting-started/developer-setup.md). You will need the device's IP address and the developer password.

## Server setup

### 1. Create your config file

```bash
cd server
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your settings:

```yaml
# Path to your photo library (mounted into the container)
photo_dir: /media

cameras:
  # Thingino camera with snapshot
  front-door:
    snapshot: http://192.168.1.55/x/ch0.jpg
    auth:
      type: thingino
      username: admin
      password: front-door

  # Camera with snapshot + HLS stream + PTZ
  living-room:
    snapshot: http://192.168.1.106/x/ch0.jpg
    stream: http://192.168.1.207:1984/api/stream.m3u8?src=living-room_main
    auth:
      type: thingino
      username: admin
      password: password456
    onvif:
      host: 192.168.1.106
      port: 80
      username: thingino
      password: thingino

  # Stream-only camera (HLS live video, no snapshot)
  camera-3:
    stream: http://go2rtc:1984/api/stream.m3u8?src=camera-3_main
```

See [`config.yaml.example`](server/config.yaml.example) for all options.

### 2. Update docker-compose.yaml

Edit `docker-compose.yaml` and set the path to your photo library:

```yaml
services:
  thingino-roku-viewer:
    build: .
    container_name: thingino-roku-viewer-server
    restart: unless-stopped
    ports:
      - "8099:8099"
    volumes:
      - ./config.yaml:/config/config.yaml:ro
      - /path/to/your/photos:/media:ro    # <-- your photo library
```

### 3. Start the server

```bash
docker compose up -d
```

That's it. The server runs on port **8099**.

Verify it's working:
- Photo frame: `http://<server-ip>:8099/`
- Camera list: `http://<server-ip>:8099/camera/list`
- Health check: `http://<server-ip>:8099/health`

## Roku app

<!-- TODO: Add Roku channel install instructions once published -->

### Development / Sideloading

The included `deploy.sh` script is the fastest way to compile, package, and deploy the channel to your Roku for development.

1.  Navigate to the `roku/` directory.
2.  Run the script with your Roku's IP address and developer password:

```bash
cd roku
./deploy.sh <YOUR_ROKU_IP> <YOUR_DEV_PASSWORD>
```

The channel will be installed and launched on your device automatically. For more advanced debugging, see [`DEBUGGING.md`](DEBUGGING.md).

### Creating a Distributable Package

To create a pre-built package that can be installed on any Roku device, you need to sign it with your developer key.

1.  **Generate the package zip:**
    Run the `package.sh` script to bundle the application.

    ```bash
    cd roku
    ./package.sh
    ```
    This will create a `thingino-roku-viewer.zip` file inside the `roku/dist/` directory.

2.  **Sign the package:**
    -   Log into your Roku device's web portal by visiting its IP address in your browser.
    -   Navigate to the **Packager** utility.
    -   Upload the `thingino-roku-viewer.zip` file created by the script.
    -   Select your developer key and enter your password. If you don't have a key, the utility will help you generate one.
    -   Click **Package** to sign the application.
    -   Download the resulting `.pkg` file. This file can be distributed and sideloaded onto any Roku device.

### Features

The channel installs as both an **app** and a **screensaver**:

**App** — Camera browser with live preview
- Browse all cameras in a list with live preview panel
- OK button for fullscreen view
- HLS live video for cameras with stream URLs
- D-pad PTZ controls in fullscreen (for cameras with ONVIF)
- Fast-forward / rewind for zoom in/out

**Screensaver** — Three modes (configurable in settings)
- **Photo Frame** — random photos with crossfade (configurable interval)
- **Camera Cycle** — rotates through all cameras (configurable interval)
- **Live Video** — single HLS camera stream (for cameras with stream URLs)
- Floating clock overlay with weather, calendar, and thermostat data

### Settings

Open the screensaver settings from **Roku Settings > Screensaver > Thingino Roku Viewer**:

- **Server URL** — point to your Thingino Roku Viewer server (default: `http://192.168.1.245:8099`)
- **Screensaver mode** — photo frame, camera cycle, single camera, or live video
- **Photo interval** — 15 / 30 / 60 / 120 seconds
- **Camera cycle interval** — 3 / 5 / 10 / 15 seconds

## Camera support

| Config | App preview | Screensaver |
|--------|-------------|-------------|
| snapshot only | poster refresh (1fps) | poster refresh |
| snapshot + stream | HLS live video | poster from snapshot |
| stream only | HLS live video | HLS live video |

**Auth types:**
- `thingino` — session-based auth (POST to `/x/login.cgi`)
- `basic` — HTTP Basic auth
- No auth — just provide the snapshot/stream URL

**PTZ:** Add an `onvif` block to any camera for pan/tilt/zoom controls in the Roku app's fullscreen view.

## Server API

| Endpoint | Description |
|----------|-------------|
| `/` | HTML photo frame page (standalone) |
| `/random` | Random photo (`?w=&h=` for resize) |
| `/camera/list` | JSON array of camera names |
| `/camera/<name>` | JPEG snapshot (`?w=&h=` for resize) |
| `/camera/<name>/info` | JSON: `{name, snapshot, stream, stream_type, ptz}` |
| `/camera/<name>/ptz` | POST: `{action, direction, speed}` (ONVIF) |
| `/ha/weather` | Current weather (requires HA config) |
| `/ha/forecast` | 3-day forecast (requires HA config) |
| `/ha/event` | Next calendar event (requires HA config) |
| `/ha/thermostat` | Thermostat status (requires HA config) |
| `/health` | Health check |

## Optional: Home Assistant integration

Add HA credentials to `config.yaml` to enable weather, calendar, and thermostat data in the screensaver overlay:

```yaml
ha_url: http://192.168.1.245:8123
ha_token: YOUR_LONG_LIVED_ACCESS_TOKEN
```

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — Creative Commons Attribution-NonCommercial-ShareAlike 4.0

Copyright (c) 2026 Mike Cirioli
