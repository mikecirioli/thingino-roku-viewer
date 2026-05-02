# PhotoFace Project Release Plan

## Release Order
1. **PhotoFace Watchface** (Standalone WFF v4 watch face)
2. **PhotoFace Complications** (Free suite of Wear OS complications)
3. **SpeedWatcher** (Speed warning companion app)
4. **Watchman Bridge** (Notification/Alarm bridge companion app)

---

## 1. PhotoFace Watchface - Play Store Checklist

### Pre-Release Verification
- [ ] **Settings Icons:** Verify every configuration option in the watch face customization menu has a clear, visually distinct icon (e.g., hand styles, widget positions, colors).
- [ ] **Graceful Degradation:** Verify missing sensors (Heart Rate, Steps) properly default to the `--` UI without crashing.
- [ ] **AOD Mode:** Ensure Always-On Display renders only the gray hands and uses a pure black background to pass Play Store battery requirements.

### Screenshots & Video Required
1. **Preview Video (YouTube):** A short 10-15 second video demonstrating the 3D parallax motion effect by tilting the watch. (Provide YouTube URL in Play Console).
2. **Hero Shot:** The watch face with a vibrant photo, Classic hands, and all 4 edge widgets active.
3. **Customization - Hands:** A split image showing the 4 different hand styles (Classic, Tapered, Dauphine, Block).
4. **Customization - Colors:** The watch face demonstrating a few of the 8 different theme colors.
5. **Parallax Effect:** An angled lifestyle static shot emphasizing the depth/parallax motion of the background.
6. **AOD Mode:** A shot of the Always-On Display state to show battery efficiency.
7. **Settings UI:** A screenshot of the Wear OS customization menu showing the clean layout and icons.

### Known Limitations (Platform Bugs)
*   **Photo Selection Amnesia:** Due to a current bug in the Samsung Galaxy Wearable phone app, previously selected photos are not "remembered" when you re-open the customization menu. 
    *   *Behavior:* The watch correctly saves and cycles through all photos you select. However, if you want to add or remove photos later, you must re-select the entire desired set in the phone app before hitting "Save."
    *   *Status:* This is a platform-level issue with the Samsung companion app and does not affect the watch face's performance on the wrist.

### Marketing Text (Updated with Developer Note)
**App Title:** PhotoFace: Parallax Watch Face
**Short Description:** A highly customizable analog watch face with your photos and 3D parallax motion.
**Full Description:**
PhotoFace brings your wrist to life. Combine your favorite memories with a premium analog timepiece featuring a stunning 3D parallax motion effect that shifts as you move your wrist. 

**Key Features:**
* **3D Parallax Photos:** Select multiple photos from your gallery that shift dynamically with your movement. Adjust the parallax strength (Off, Subtle, Medium, Strong) to your liking.
* **Auto-Cycling & Tints:** Photos automatically cycle every 3 wakes or on tap. Add a tint overlay (Light, Medium, Heavy) to ensure your clock hands always remain readable.
* **4 Custom Edge Widgets:** Fully configure the four corners of your watch to display exactly what matters to you: Battery, Steps, Heart Rate, Date, or leave them clean and empty. 
* **Quick Launch Taps:** Assign custom app shortcuts (Calendar, Health, Battery, Music Player, Alarm, etc.) to any of the four quadrants for instant access.
* **Ultimate Customization:** Choose from 4 distinct watch hand styles (Classic, Tapered, Dauphine, Block) with realistic drop shadows, 8 vibrant color themes, adjustable arc thickness, scalable label sizes, and optional hour markers.
* **Sweeping Second Hand:** Toggle an optional, smooth-sweeping second hand (15fps) that perfectly matches your chosen hand style.
* **Battery Optimized:** Built natively on the latest Watch Face Format (WFF) v4 with a minimal, pure-black Always-On Display (AOD) to maximize your battery life.

**Note on Customization:** Due to the high-quality 3D parallax layers and photo gallery integration, the customization screen in the Wearable app may take a few seconds to load initially. Please be patient while your photos are prepared!

**Developer Note:** We are aware of a minor issue in the Samsung Galaxy Wearable app where previously selected photos are not highlighted when re-opening the settings menu. Rest assured, your photos are saved on the watch! To update your photo list, simply re-select your desired images and tap Save.

### Technical Details (For Play Console)
- **Category:** Watch faces
- **Tags:** Analog, Photo, Custom, Utility
- **Format:** Watch Face Format (WFF) v4 (No companion app required).
- **Permissions:** `ACTIVITY_RECOGNITION` (Steps), `BODY_SENSORS` (Heart Rate).
- **Pricing:** Paid (or Free with IAP depending on monetization plan).

---

## 2. PhotoFace Complications - Play Store Checklist

### Pre-Release Verification
- [ ] **Complication Icons:** Ensure the launcher icon and the preview icons in the complication picker are high-resolution and clearly depict the function (Moon, Sunrise, Floors, Globe).
- [ ] **Permissions Flow:** Verify that complications requiring permissions (Location for Sunrise/Sunset, Activity Recognition for Floors) gracefully prompt the user or show a "Tap to grant permission" state if denied.

### Screenshots Required
1. **Hero Shot:** A clean, minimal stock watch face loaded with all four of our custom complications.
2. **Moon Phase Focus:** A close-up of the moon phase complication showing the precise icon and text.
3. **World Clock Focus:** A shot showing multiple world clocks configured for different time zones.
4. **Health/Activity Focus:** A shot highlighting the Floors Climbed and Sunrise/Sunset widgets.
5. **Picker UI:** A screenshot showing our complications listed neatly in the Wear OS complication selection menu.

### Marketing Text
**App Title:** PhotoFace Complications Suite
**Short Description:** Add Moon Phases, World Clocks, Sunrise times, and Floors to any watch face.
**Full Description:**
Upgrade your favorite Wear OS watch face with the PhotoFace Complications Suite. This free utility pack adds highly requested data points to your wrist, compatible with any watch face that supports standard Wear OS complications.

**Included Complications:**
* **Moon Phase:** Track the current lunar cycle with precise iconography and descriptions (Supports Image and Text formats).
* **Sunrise & Sunset:** Know exactly when the light will change in your current location. Uses astronomical calculations without requiring an internet connection.
* **World Clocks:** Keep track of multiple time zones at a glance. Supports configuring multiple distinct complication slots for different cities (e.g., London, Tokyo, Madrid).
* **Floors Climbed:** Monitor your elevation goals natively, pulling data directly from Health Services on your watch.

Seamless, battery-efficient, and designed to match the native aesthetic of Wear OS 4 and 5. Includes a robust permission flow so your watch face never crashes on missing data.

### Technical Details (For Play Console)
- **Category:** Tools / Watch Apps
- **Tags:** Utilities, Time, Health
- **Format:** Standard Wear OS App (Complication Data Source Services).
- **Permissions:** `ACCESS_COARSE_LOCATION` (Sunrise/Sunset), `ACTIVITY_RECOGNITION` (Floors).
- **Pricing:** Free.

---

## 3. SpeedWatcher - Play Store Checklist

### Pre-Release Verification
- [ ] **Offline Maps:** Ensure the map compilation script works locally (GraphHopper) and the fallback Overpass API functions reliably.
- [ ] **Branding:** Verify the new "3 Bad Dogs" logo is integrated into the settings UI.
- [ ] **Background Execution:** Confirm the service correctly auto-starts when connecting to the target Bluetooth MAC address.

### Marketing Text
**App Title:** SpeedWatcher: Wear OS Speed Alerts
**Short Description:** Get discreet haptic speed warnings on your watch while driving.
**Developer:** 3 Bad Dogs Productions

### Technical Details
- **Category:** Auto & Vehicles / Watch Apps
- **Tags:** Speedometer, GPS, Safety, Driving
- **Format:** Companion App (Phone + Wear OS).
- **Permissions:** `ACCESS_FINE_LOCATION`, `ACCESS_BACKGROUND_LOCATION`, `BLUETOOTH_CONNECT`.

---

## 4. Watchman Bridge - Play Store Checklist

### Pre-Release Verification
- [ ] **UX Redesign:** Verify the new 3-tab navigation (Status, Rules, Settings) simplifies the user experience.
- [ ] **Debouncing & Duplicate Filtering:** Test that persistent notifications do not re-trigger the watch, and rapid bursts are properly throttled by the 10-second cooldown.
- [ ] **Quick Settings & Snooze:** Verify the new Quick Settings tile accurately reflects service state and successfully snoozes alerts.
- [ ] **Branding:** Ensure the "3 Bad Dogs" logo is prominent on the main Status dashboard.

### Marketing Text
**App Title:** Watchman Bridge: Custom Alerts
**Short Description:** Filter, customize, and sync critical phone notifications to your watch.
**Developer:** 3 Bad Dogs Productions

### Technical Details
- **Category:** Tools / Productivity
- **Tags:** Notifications, Automation, Alarms
- **Format:** Companion App (Phone + Wear OS).
- **Permissions:** `BIND_NOTIFICATION_LISTENER_SERVICE`, `ACCESS_NOTIFICATION_POLICY`.
- **Pricing:** Freemium (3-Day Trial -> $1.49 Lifetime Unlock).

