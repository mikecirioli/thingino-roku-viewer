# Deployment and Testing Guide

This document outlines the standard process for deploying updated application files to the `optiplex` server and testing the functionality.

## Deployment Process

The `optiplex` server runs the application in Docker but does not host the git repository. Files must be copied from the local development machine to the server.

**Deployment Target:** `root@optiplex`
**Application Directory on Server:** `/export/homeassistant/photoframe-server/`

### Step 1: Transfer Application Files

From the local machine's project root, copy the updated files to the server using `scp`.

1.  **Copy the Python Server:**
    ```bash
    scp server/server.py root@optiplex:/export/homeassistant/photoframe-server/server.py
    ```

2.  **Copy the Web Interface:**
    ```bash
    scp web/web_ui.html root@optiplex:/export/homeassistant/photoframe-server/web/web_ui.html
    ```

3.  **Copy the Dockerfile:**
    ```bash
    scp Dockerfile root@optiplex:/export/homeassistant/photoframe-server/Dockerfile
    ```

### Step 2: Rebuild and Restart the Service

Connect to the server via SSH and run the Docker Compose command to rebuild and restart the `photoframe` service.

```bash
ssh root@optiplex "cd /export/homeassistant && docker compose up -d --build photoframe"
```

## Testing Steps

### Standard Functionality

1.  Open a web browser and navigate to `http://optiplex:8099/web`.
2.  Verify that the camera list loads correctly.
3.  Select a snapshot-based camera and confirm the image appears and updates.
4.  Select a stream-based camera and confirm the HLS or MSE video stream plays.

### Time-lapse Feature Testing

**Prerequisite:** Ensure at least one camera is configured for time-lapse snapshots in your `config.yaml` on the server at `/export/homeassistant/photoframe-server/config.yaml`.

1.  Navigate to `http://optiplex:8099/web`.
2.  Switch to the **"Time-lapse"** tab.
3.  **Verify Summary:** The page should load a summary of cameras that have captured frames, including frame counts and date ranges. (Note: You may need to wait for the configured interval to pass for the first frames to be captured after deployment).
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
