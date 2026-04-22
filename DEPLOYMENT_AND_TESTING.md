# Deployment and Testing Guide

This document outlines the standard process for deploying updated application files to the server and testing functionality.

## Deployment Process

The server runs the application in Docker but does not host the git repository. Files must be copied from the local development machine to the server.

### Step 1: Transfer Application Files

From the local machine's project root, copy the updated files to the server using `scp`.

1.  **Copy the Python server files:**
    ```bash
    scp server/server.py root@yourserver:/path/to/photoframe-server/server.py
    scp server/geotag_manager.py root@yourserver:/path/to/photoframe-server/geotag_manager.py
    scp server/duplicate_detector.py root@yourserver:/path/to/photoframe-server/duplicate_detector.py
    ```

2.  **Copy the Web Interface:**
    ```bash
    scp web/web_ui.html root@yourserver:/path/to/photoframe-server/web/web_ui.html
    ```

3.  **Copy the Dockerfile (if changed):**
    ```bash
    scp server/Dockerfile root@yourserver:/path/to/photoframe-server/Dockerfile
    ```

### Step 2: Rebuild and Restart the Service

Connect to the server via SSH and run the Docker Compose command to rebuild and restart the service.

```bash
ssh root@yourserver "cd /path/to/compose && docker compose up -d --build photoframe"
```

**Important:** `docker restart` does NOT pick up code changes -- `server.py`, `geotag_manager.py`, and `duplicate_detector.py` are baked into the Docker image. You must use `docker compose up -d --build`.

The web UI HTML is volume-mounted, so changes to `web_ui.html` only require copying the file and refreshing the browser (no rebuild needed).

## Testing Steps

### Standard Functionality

1.  Open a web browser and navigate to `http://yourserver:8099/web`.
2.  Verify that the camera list loads correctly.
3.  Select a snapshot-based camera and confirm the image appears and updates.
4.  Select a stream-based camera and confirm the MSE WebSocket video stream plays.

### Time-lapse Feature Testing

**Prerequisite:** Ensure at least one camera is configured for time-lapse snapshots in your `config.yaml`.

1.  Navigate to `http://yourserver:8099/web`.
2.  Switch to the **"Time-lapse"** tab.
3.  **Verify Summary:** The page should load a summary of cameras that have captured frames, including frame counts and date ranges.
4.  **Generate a Video:**
    *   Select at least one camera.
    *   Use the timeline slider to select a time window.
    *   Set a desired FPS.
    *   Click "Generate Video".
5.  **Verify Playback:**
    *   A status message should appear, followed by a video player.
    *   Confirm the generated time-lapse video plays correctly in the browser.
    *   Confirm you can download the video using the download link.
    *   Confirm the new video appears in the "Previous Videos" list.

### Geotag Feature Testing

1.  Switch to the **"Geotags"** tab.
2.  **Verify Map:** The Leaflet map should load and display pins for geotagged photos.
3.  **Verify Photo Grid:** Photos should appear with GPS status badges (green for geotagged, red for missing).
4.  **Test Import:** Click "Import EXIF" to index photos. Verify the count of indexed/geotagged/missing photos.
5.  **Test Auto-Infer:** Run auto-inference and verify suggestions appear with confidence scores.

### Orientation Feature Testing

1.  Switch to the **"Orientation"** tab.
2.  **Verify Listing:** Photos flagged with non-normal EXIF orientation should appear.
3.  **Test Thumbnails:** Click a photo to see raw vs. rendered thumbnail comparison.
4.  **Test Apply Fix:** Apply a fix to one photo and verify it updates to "correct" status.

### Duplicates Feature Testing

1.  Switch to the **"Duplicates"** tab.
2.  **Verify Groups:** Duplicate groups should appear with photo thumbnails and distance info.
3.  **Test Resolution:** Mark a group as reviewed (keep/delete) and verify it disappears from the unreviewed list.

### Library Feature Testing

1.  Switch to the **"Library"** tab.
2.  **Verify Grid:** Photo thumbnails should load, sorted by date (newest first).
3.  **Test Upload:** Upload a test photo and verify it appears in the grid.
4.  **Test Rotate/Delete:** Rotate and delete a test photo, verify changes take effect.

### Configuration Tab Testing

1.  Switch to the **"Configuration"** tab.
2.  Verify camera settings load correctly.
3.  Test updating timelapse capture settings (changes should autosave).

### Screensaver Testing

1.  Click "Start Screensaver" in the web UI.
2.  Verify photos cycle with crossfade.
3.  Verify the bouncing clock overlay appears.
4.  Click anywhere to exit screensaver mode.

### Authentication Testing

1.  If `web_auth` is configured, open the web UI in a private/incognito window.
2.  Verify the login page appears.
3.  Log in with the configured credentials and verify access.
4.  Test that API endpoints return 401 without credentials.

### Quick API Verification

```bash
# Health check
curl http://yourserver:8099/health

# Camera list
curl http://yourserver:8099/camera/list

# Check container logs for errors
ssh root@yourserver "docker logs --tail 50 photoframe-server"

# Verify geotag database initialized
ssh root@yourserver "docker logs photoframe-server | grep geotag"

# Verify orientation auto-flagging ran
ssh root@yourserver "docker logs photoframe-server | grep orientation"

# Verify duplicate detector started
ssh root@yourserver "docker logs photoframe-server | grep duplicates"
```
