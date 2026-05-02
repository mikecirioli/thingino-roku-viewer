# SpeedWatcher

A zero-touch background companion app that utilizes Android's Fused Location Provider to monitor driving speed and triggers a haptic alert on a paired Wear OS device when a user-defined threshold is exceeded.

## Architecture (Phase 2 MVP)

SpeedWatcher is built as a multi-module Android project within the `PhotoFace` monorepo:

*   `:speedwatcher:phone` - Contains the Settings UI, Bluetooth Broadcast Receiver, Foreground Location Service, Offline Map Engine (GraphHopper), and the Overpass API fallback client.
*   `:speedwatcher:wear` - A headless Wear OS application containing a `WearableListenerService` to trigger haptics.
*   `:speedwatcher:shared` - Shared contracts and Data Layer paths.
*   `tools/graph-compiler` - A local script to download and compile raw OpenStreetMap data into a highly optimized GraphHopper cache for offline use.

## How it Works

1.  **Zero-Touch Trigger:** The phone app listens for Bluetooth connection events in the background (`ACTION_ACL_CONNECTED`).
2.  **Verification:** When a connection occurs, it checks if the connected device's MAC address matches the user's configured car.
3.  **Tracking Engine:** If there is a match, a `ForegroundService` starts. It requests high-accuracy GPS location updates every ~3 seconds.
4.  **Dynamic Speed Limits:** If enabled, the app uses the `OfflineMapEngine` to perform a zero-latency spatial lookup against a pre-compiled OpenStreetMap GraphHopper database on the device.
5.  **Online Fallback:** If the user drives into an area not covered by their downloaded offline map, the app automatically falls back to querying the Overpass API. It uses a dynamic distance throttle (scaling based on current speed) and a consensus filter (requiring two identical results) to minimize API usage and filter out intersection noise.
6.  **Threshold Breach:** If `location.getSpeed()` (converted to MPH) exceeds the active limit (static or dynamic + overage), a high-priority datagram is sent to the watch via the Wear OS Data Layer.
7.  **Haptic Feedback:** The watch receives the message in the background and immediately fires a distinct vibration pattern (e.g., Rapid, Heartbeat, Standard).
8.  **Cooldown:** A customizable cooldown timer prevents continuous vibrations if hovering around the threshold.
9.  **Auto-Shutdown:** When the car's Bluetooth disconnects (`ACTION_ACL_DISCONNECTED`), the location service is immediately terminated to preserve battery.

## Setup & Testing Instructions (MVP)

Because this is an early MVP, the complex runtime permission request flows have not yet been implemented in the UI. **You must grant permissions manually** before testing.

1.  Install the app on both your phone and watch.
2.  On your phone, open **Settings > Apps > SpeedWatcher > Permissions**.
3.  Grant the following permissions:
    *   **Location:** Must be set to **"Allow all the time"** (Crucial for the background Bluetooth trigger to start tracking).
    *   **Nearby Devices:** To allow Bluetooth MAC address reading.
    *   **Notifications:** Required for the Foreground Service.
4.  Open the SpeedWatcher app on your phone.
5.  Set your desired speed threshold.
6.  Enter the exact Bluetooth MAC address of your vehicle's infotainment system.
7.  The service will now automatically start the next time you connect to that car.
