# Gemini Development Log - SpeedWatcher

## Project Overview
The user requested a companion app that monitors driving speed and vibrates their Wear OS watch if they exceed a specific limit, mitigating the risk of speeding tickets.

We recognized that relying on Google Maps Roads API for dynamic speed limits would be costly and complex for an initial prototype. We decided to build the app in two phases, starting with a robust, zero-touch MVP.

## Work Done (2026-03-02)
- **Phase 1 MVP Architecture Planned & Scaffolded:**
    - Defined scope, requirements, and tech stack.
    - Scaffolded a new multi-module structure (`:speedwatcher:phone`, `:speedwatcher:wear`, `:speedwatcher:shared`) inside the `PhotoFace` monorepo.
    - Wired Gradle dependencies, including Google Play Services Location and Wearable libraries.
- **Implemented Zero-Touch Bluetooth Triggering:**
    - Created `AutoStartReceiver` in the phone module to listen for `ACTION_ACL_CONNECTED` and `ACTION_ACL_DISCONNECTED`.
    - Leveraged Android's explicit exemption allowing apps to start Foreground Services from the background in response to a paired companion device connection.
- **Implemented Fused Location Tracking Engine:**
    - Built `SpeedTrackerService` to handle high-accuracy GPS requests (`setInterval(3000)`).
    - Added logic to convert `location.getSpeed()` from meters/second to MPH.
    - Implemented a 30-second cooldown state machine to prevent continuous haptic spam when hovering at the threshold limit.
- **Implemented Wear OS Haptic Receiver:**
    - Built `AlertListenerService` extending `WearableListenerService` on the watch to catch the `/speedwatcher/alert` payload.
    - Configured a distinct rapid triple-pulse `VibrationEffect` to ensure the alert is recognizable without looking at the watch face.
- **Built Settings UI:**
    - Created a simple Jetpack Compose `MainActivity` on the phone to persist the target speed limit and the vehicle's Bluetooth MAC address using `EncryptedSharedPreferences`.

## Work Done (2026-03-11)
- **Phase 2 Implementation: Dynamic Speed Limits:**
    - Replaced the static user-defined MPH threshold with a dynamic system.
    - Implemented a "Speed Limit Mode" toggle in the phone's `MainActivity` UI, allowing users to choose between a static limit or "Use OpenStreetMap (Dynamic)" with an adjustable "Overage Tolerance (+)".
- **Implemented Overpass API Client (Fallback/Online Mode):**
    - Created `OverpassClient` to asynchronously query the OpenStreetMap Overpass API for the `maxspeed` tag of nearby roads.
    - Added consensus filter logic to `SpeedTrackerService`: Requires two identical API results at different locations to confirm a limit change, preventing "blips" when driving through intersections.
    - Implemented Dynamic Throttle scaling: The app calculates how far the user should travel in 15 seconds at their current speed, establishing a dynamic distance threshold for the next API query to optimize battery life and avoid API rate limits.
- **Implemented GraphHopper Engine (Offline Mode):**
    - Built a custom map compiler tool (`tools/graph-compiler/compile_map.sh`) using the GraphHopper 9.1 Java library to convert raw `.osm.pbf` state maps into highly optimized `graph-cache` folders.
    - Created `OfflineMapEngine` inside the Android app to perform zero-latency, offline spatial queries on the pre-compiled graph cache.
    - Wired `SpeedTrackerService` to check the offline graph first. If a match is found, no network request is made. If the coordinate is outside the loaded offline map bounds, it gracefully falls back to the Overpass API logic.
- **Implemented Metrics Logging:**
    - Created `MetricsLogger` to log a local CSV file (`speedwatcher_metrics.csv`) detailing every speed check, distance moved, time elapsed, and battery level impact. Includes an automatic 2MB size cap to prevent storage issues.

## Current State & Next Steps
- **Status:** Phase 2 MVP (Dynamic Speed Limits) is structurally complete and compiles successfully. The app supports both an offline GraphHopper engine and an online Overpass API fallback.
- **Pending (Phase 2):** The user needs to deploy the app to devices, compile a local state map via `compile_map.sh`, copy it to the phone's `Android/data/com.speedwatcher/files/graph-cache/` directory, and perform an empirical road test.

## Future Plans (Phase 3)
### 1. In-App Map Downloader
- **Goal:** Remove the need for the user to manually compile and copy map folders via ADB.
- **Implementation:** Host pre-compiled state `.zip` archives on a server (e.g., GitHub Releases or Cloudflare R2). Build a Compose UI that allows users to select their state, download the zip directly to the app's internal storage, and extract it for the `OfflineMapEngine`.

### 2. UI & UX Polish
- **Goal:** Make the app user-friendly for non-developers.
- **Implementation:** 
    - Build a proper Permission Request flow in Compose (handling the rationale for Background Location).
    - Improve the Bluetooth selection UI to show a list of paired devices names instead of requiring manual MAC address entry.
