# PhotoFace - Galaxy Watch 7 Watch Face

A highly customizable analog watch face with photo backgrounds, parallax motion effects, and configurable edge arc data displays.

## Features

### Photo Background
- **Multiple photo selection** - Choose photos from your phone gallery
- **Auto-rotation** - Photos cycle every 3 wakes or on tap
- **Parallax motion effect** - Photo shifts based on watch tilt (accelerometer)
- **Configurable parallax strength** - Off, Subtle, Medium, Strong
- **Photo tint overlay** - None, Light, Medium, Heavy darkening for readability

### Configurable Quadrant Widgets
Each of the 4 edge quadrants can display ANY of these widgets:

| Widget | Display | Data |
|--------|---------|------|
| **Battery** | Arc + dot + percentage | Battery level |
| **Steps** | Arc + dot + count | Daily steps |
| **Heart Rate** | Arc + dot + BPM | Current heart rate |
| **Date** | Curved text | Day, date, month |
| **None** | Empty | - |

Default layout:
| Position | Default Widget |
|----------|----------------|
| Top-Left (9-12 o'clock) | Battery |
| Top-Right (12-3 o'clock) | Date |
| Bottom-Right (3-6 o'clock) | Steps |
| Bottom-Left (6-9 o'clock) | Heart Rate |

Each widget includes:
- Gray background track showing full range (for arc widgets)
- Colored fill arc showing current value
- White indicator dot with colored center
- Text label with data value

### Customizable Tap Actions
Each quadrant can launch a different app when tapped:
- None (use built-in widget action)
- Battery Status
- Health / Heart Rate
- Calendar
- Settings
- Phone
- Messages
- Music Player
- Alarm

### Analog Clock Hands
Four hand styles with preview icons:
- **Classic** - Rounded rectangle with center accent line
- **Tapered** - Pointed/triangular shape
- **Dauphine** - Diamond shape with center line
- **Block** - Thick rectangle

Hand features:
- **Drop shadows** - 12px offset for depth effect
- **8 color options** - White, Silver, Gold, Blue, Red, Green, Orange, Pink

### Optional Second Hand
- Toggle on/off in settings
- Matches selected hand style automatically
- Smooth sweep motion (15fps)
- Hidden in Always-On Display mode

### Arc Thickness Options
| Size | Arc Stroke | Indicator Dot |
|------|------------|---------------|
| Thin | 6px | Small |
| Medium (default) | 10px | Medium |
| Thick | 14px | Large |

### Label Size Options
| Size | Arc Labels | Date Text |
|------|------------|-----------|
| Small | 16px | 14px |
| **Medium** (default) | **20px** | **18px** |
| Large | 24px | 22px |
| X-Large | 28px | 26px |

### Hour Markers
- None (default)
- 4 Marks (12, 3, 6, 9 o'clock)
- 12 Marks (every hour)

### Always-On Display (AOD)
- Black background (battery efficient)
- Gray clock hands only
- No second hand, photo, arcs, or data displays

## All Configuration Options (22 total)

| Setting | Options | Default |
|---------|---------|---------|
| **Photo Settings** | | |
| Photos | Multiple selection | - |
| Photo Motion | Off, Subtle, Medium, Strong | Medium |
| Photo Tint | None, Light, Medium, Heavy | None |
| **Hand Settings** | | |
| Hand Style | Classic, Tapered, Dauphine, Block | Classic |
| Hand Color | 8 colors | White |
| Second Hand | Off, On | Off |
| **Widget Settings** | | |
| Top-Left Widget | Battery, Steps, Heart, Date, None | Battery |
| Top-Right Widget | Battery, Steps, Heart, Date, None | Date |
| Bottom-Right Widget | Battery, Steps, Heart, Date, None | Steps |
| Bottom-Left Widget | Battery, Steps, Heart, Date, None | Heart Rate |
| Top-Left Tap | None + 8 apps | None |
| Top-Right Tap | None + 8 apps | None |
| Bottom-Right Tap | None + 8 apps | None |
| Bottom-Left Tap | None + 8 apps | None |
| Battery Color | 8 colors | Green |
| Steps Color | 8 colors | Orange |
| Heart Rate Color | 8 colors | Blue |
| Date Color | 8 colors | Purple |
| Arc Thickness | Thin, Medium, Thick | Medium |
| Hour Markers | None, 4 Marks, 12 Marks | None |
| Label Size | Small, Medium, Large, X-Large | Medium |

## Watchman Bridge

A companion app that bridges phone alarm notifications to the watch. When your phone alarm fires, the watch plays an audio alert and vibrates.

### Features

*   **Two-Way Remote Control:** Snooze or Dismiss your phone's stock alarm directly from your wrist.
*   **Next Alarm Sync:** Syncs your phone's next scheduled alarm time to your watch for use in complications.
*   **Custom Alarm Tones:** Select any MP3 on your phone and sync it to the watch to use as your alarm sound.
*   **Custom Vibration Patterns:** Pick from multiple vibration rhythms (Standard, Heartbeat, Rapid) to personalize your alerts.
*   **Universal DND & Bedtime Sync:** Automatically syncs Do Not Disturb and Night Mode state between your phone and watch.
*   **Starred Alerts:** "Star" specific apps (PagerDuty, Baby Monitor, etc.) to trigger a persistent alarm-style alert on your watch.

### How It Works

1. **Phone** (`alarmwatcher/phone`) — a `NotificationListenerService` detects alarm notifications (stock Android, Samsung Clock, etc.) and sends a message to the watch via the Wearable Data Layer API
2. **Watch** (`alarmwatcher/wear`) — receives the message and launches an activity that plays the default alarm sound and vibrates until you tap **STOP**

### Setup

1. Install both APKs (phone and watch)
2. Open Watchman Bridge on the phone and tap **Enable Notification Access**
3. Grant the permission in Android Settings
4. That's it — the next time a phone alarm fires, the watch will alert

## Building

### Prerequisites

1. **Android Studio** (Arctic Fox or newer)
2. **Android SDK 34** and Build Tools

### Build & Install

```bash
cd /export/git/photoface

# Build everything
./gradlew assembleDebug

# Or build individual modules
./gradlew :watchface:assembleDebug
./gradlew :complications:assembleDebug
./gradlew :alarmwatcher:phone:assembleDebug
./gradlew :alarmwatcher:wear:assembleDebug

# Connect to watch (enable Wireless Debugging on watch first)
adb connect <watch-ip>:<port>

# Install watch face and complications (to watch)
adb install -r watchface/build/outputs/apk/debug/watchface-debug.apk
adb install -r complications/build/outputs/apk/debug/complications-debug.apk

# Install Watchman Bridge (to watch)
adb install -r alarmwatcher/wear/build/outputs/apk/debug/wear-debug.apk

# Install Watchman Bridge (to phone — use a second adb connection or USB)
adb install -r alarmwatcher/phone/build/outputs/apk/debug/phone-debug.apk
```

### Enable ADB on Galaxy Watch 7

1. **Settings -> About Watch -> Software** -> tap Build Number 7 times
2. **Settings -> Developer Options -> ADB debugging -> ON**
3. **Settings -> Developer Options -> Wireless debugging -> ON**
4. Tap "Wireless debugging" text to see IP and port
5. May need to "Pair new device" first

### Testing with Emulator

```bash
# Launch emulator
/export/android-studio-sdks/emulator/emulator -avd Wear_OS_Large_Round &

# Install watch modules on emulator
adb -s emulator-5554 install -r watchface/build/outputs/apk/debug/watchface-debug.apk
adb -s emulator-5554 install -r complications/build/outputs/apk/debug/complications-debug.apk
adb -s emulator-5554 install -r alarmwatcher/wear/build/outputs/apk/debug/wear-debug.apk
```

## Project Structure

```
photoface/
├── watchface/                              # Watch face (pure WFF, no code)
│   ├── src/main/
│   │   ├── AndroidManifest.xml
│   │   └── res/
│   │       ├── xml/                        # WFF watch face definition & metadata
│   │       ├── drawable/                   # Hand SVGs, color/style icons
│   │       ├── font/                       # DSEG7 digital font
│   │       └── values/                     # String resources
│   └── build.gradle.kts
├── complications/                          # Complication data sources (Kotlin)
│   ├── src/main/
│   │   ├── AndroidManifest.xml
│   │   └── java/com/photoface/complications/
│   │       ├── floors/                     # Climbed floors complication
│   │       ├── sunrise/                    # Sunrise/sunset complication
│   │       ├── moon/                       # Moon phase complication (image + text)
│   │       ├── worldclock/                 # World clock complication
│   │       └── common/                     # Shared utilities
│   └── build.gradle.kts
├── alarmwatcher/                           # Watchman Bridge feature
│   ├── GEMINI.md                           # Development log & roadmap
│   ├── phone/                              # Phone companion app (Kotlin)
│   │   ├── src/main/
│   │   │   ├── AndroidManifest.xml
│   │   │   └── java/com/watchman/bridge/
│   │   │       ├── MainActivity.kt         # Setup UI for notification access
│   │   │       └── AlarmListenerService.kt # Notification listener + watch sync
│   │   └── build.gradle.kts
│   └── wear/                               # Watch app (Kotlin)
│       ├── src/main/
│       │   ├── AndroidManifest.xml
│       │   └── java/com/watchman/bridge/
│       │       ├── WatchListenerService.kt # Receives messages from phone
│       │       └── AlarmActivity.kt        # Alarm UI with sound + vibration
│       └── build.gradle.kts
├── build.gradle.kts                        # Root build config (AGP 9.0.0, Kotlin 2.2.10)
├── settings.gradle.kts                     # Module includes
└── gradle.properties
```

## Technical Details

- **Format**: Watch Face Format (WFF) v4
- **Min SDK**: 33 (Wear OS 4)
- **Target SDK**: 34 (Wear OS 5)
- **No code**: Pure XML resource bundle (`hasCode="false"`)
- **PhotosConfiguration**: Multiple photo selection with auto-rotation
- **Gyro element**: Accelerometer-based parallax on Group wrapper
- **Nested ListConfiguration**: Widget type + label size configurability

### Required Permissions
```xml
<uses-permission android:name="android.permission.ACTIVITY_RECOGNITION" />
<uses-permission android:name="android.permission.BODY_SENSORS" />
```

## Key Implementation Patterns

### Parallax Motion
Gyro element must be on a Group wrapper, not directly on PartImage:
```xml
<Group x="-60" y="-60" width="570" height="570">
  <Gyro x="[ACCELEROMETER_ANGLE_X]" y="[ACCELEROMETER_ANGLE_Y]" />
  <PartImage ...><Photos .../></PartImage>
</Group>
```

### Hand Shadows
Duplicate hand elements with offset position and tintColor:
```xml
<!-- Shadow -->
<HourHand x="225" y="137" tintColor="#99000000">
  <Variant mode="AMBIENT" target="alpha" value="0"/>
</HourHand>
<!-- Main hand -->
<HourHand x="213" y="125" tintColor="[CONFIGURATION.handColor]">
  <Variant mode="AMBIENT" target="tintColor" value="#FF888888"/>
</HourHand>
```

### Tap Actions
Using WFF system shortcuts:
```xml
<Group x="0" y="0" width="160" height="160">
  <Launch target="BATTERY_STATUS"/>
  <PartDraw ...><Ellipse><Fill color="#00000000"/></Ellipse></PartDraw>
</Group>
```

Available targets: `BATTERY_STATUS`, `HEALTH_HEART_RATE`, `CALENDAR`, `SETTINGS`, `PHONE`, `MESSAGE`, `MUSIC_PLAYER`, `ALARM`

### Health Data Sources
```
[BATTERY_PERCENT]  - Battery percentage (0-100)
[STEP_COUNT]       - Daily step count
[STEP_GOAL]        - User's step goal
[HEART_RATE]       - Current heart rate BPM
[DAY]              - Day of month
[DAY_OF_WEEK_S]    - Short day name (e.g., "Tue")
[MONTH_S]          - Short month name (e.g., "Jan")
```

### Arc Progress Scaling
```xml
<Arc startAngle="270" endAngle="360" ...>
  <Transform target="endAngle" value="270 + ([BATTERY_PERCENT] * 90 / 100)"/>
</Arc>
```

## Troubleshooting

### Photo selection not "remembered" in settings
Due to a known platform bug in the Samsung Galaxy Wearable phone app, previously selected photos are not highlighted when you re-open the customization menu. 
- **The photos ARE saved on the watch.** They will continue to cycle correctly.
- **To add/remove photos:** You must re-select the entire batch of photos you want active and tap "Save."

### Customization screen takes a long time to load
Because of the complexity of the high-res 3D parallax layers and the gallery integration (WFF PhotosConfiguration), the Samsung Wearable app may take 5-10 seconds to fully parse and display the "Customize" menu. This is normal behavior for photo-heavy faces.

### Watch not detected
```bash
adb kill-server
adb start-server
adb connect <watch-ip>:<port>
```

### Watch face not appearing in picker
Ensure AndroidManifest.xml includes the watch face service with proper intent-filter.

### Parallax not working
- Gyro must be on Group, not PartImage
- Image must be larger than display (e.g., 570x570 for 450x450)
- Group must be offset negatively (e.g., x="-60" y="-60")

### Configuration changes not appearing
Full uninstall/reinstall required:
```bash
adb uninstall com.mcirioli.photoface
adb install watchface/build/outputs/apk/debug/watchface-debug.apk
```

### Steps/Heart rate showing 0
- Grant health permissions: Settings -> Apps -> PhotoFace -> Permissions
- Use `[STEP_COUNT]` and `[STEP_GOAL]` (not `[STEPS]`)

### AOD shows blank screen
- Ensure hands have `<Variant mode="AMBIENT" target="tintColor" value="#FF888888"/>`
- Check that shadows have `<Variant mode="AMBIENT" target="alpha" value="0"/>`

## License

Personal use. Modify freely.
