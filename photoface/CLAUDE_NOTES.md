# Claude Code Notes for PhotoFace

## Android Emulator

**SDK Location**: `/export/android-studio-sdks/`

**Start Wear OS Emulator**:
```bash
export ANDROID_SDK_ROOT=/export/android-studio-sdks
/export/android-studio-sdks/emulator/emulator -avd Wear_OS_Large_Round -no-snapshot-load -gpu swiftshader_indirect &
```

**Important**:
- Must use `-gpu swiftshader_indirect` — without it the emulator boots but crashes shortly after, and adb loses connectivity.
- Must set `ANDROID_SDK_ROOT` so the emulator finds adb correctly.
- After launching, wait ~25 seconds for boot, then verify with `/export/android-studio-sdks/platform-tools/adb devices`.
- If adb doesn't see the device, restart the adb server: `/export/android-studio-sdks/platform-tools/adb kill-server && /export/android-studio-sdks/platform-tools/adb start-server`

**Available AVDs**:
- `Wear_OS_Large_Round` - Wear OS API 36
- `Wear_OS_4_API33` - Wear OS API 33
- `Medium_Phone_API_36.1` - Phone emulator

**List AVDs**:
```bash
/export/android-studio-sdks/emulator/emulator -list-avds
```

## Monorepo Structure

This is a monorepo containing four modules:
- **watchface/**: Main watch face (pure WFF XML, no code)
- **complications/**: Complication data sources (floors, sunrise, moon phase, world clock)
- **alarmwatcher/phone/**: Watchman Bridge phone companion — listens for alarm notifications, starred app notifications, and DND changes; forwards to watch via Wearable Data Layer API
- **alarmwatcher/wear/**: Watchman Bridge watch app — receives signals and displays alarm/alert UI, syncs DND state

## Watch Connection

Connect to physical watch via WiFi:
```bash
adb connect <watch-ip>:<port>
# Example: adb connect 192.168.1.39:46111
```

## Build & Install

```bash
# Build all modules
./gradlew assembleDebug

# Build individual modules
./gradlew :watchface:assembleDebug
./gradlew :complications:assembleDebug
./gradlew :alarmwatcher:phone:assembleDebug
./gradlew :alarmwatcher:wear:assembleDebug

# Install to watch
adb install -r watchface/build/outputs/apk/debug/watchface-debug.apk
adb install -r complications/build/outputs/apk/debug/complications-debug.apk
adb install -r alarmwatcher/wear/build/outputs/apk/debug/wear-debug.apk

# Install alarm watcher to phone (separate adb connection or USB)
adb install -r alarmwatcher/phone/build/outputs/apk/debug/phone-debug.apk
```

## Watchman Bridge Notes

**Branding**: Renamed from "Alarm Watcher" to "Watchman Bridge". Package is `com.watchman.bridge` (both modules share the same applicationId).

### Features

**1. Alarm Bridging** (original feature)
- Phone `AlarmListenerService` detects alarm notifications by checking package name (`deskclock`, `alarm`, Samsung `com.sec.android.app.clock`), notification category (`CATEGORY_ALARM`), and action labels (snooze/dismiss/stop)
- Sends empty payload to watch via path `/START_ALARM_SOUND`
- Watch `AlarmActivity` wakes screen, plays default alarm ringtone, vibrates until user taps STOP

**2. Starred Alerts** (persistent notification forwarding)
- Phone `MainActivity` lists all installed non-system apps with checkboxes (requires `QUERY_ALL_PACKAGES` permission)
- Starred app selections persisted in SharedPreferences (`WatchmanPrefs` / `starred_apps`)
- When a starred app posts a notification, `AlarmListenerService` extracts title + text and sends via `/STARRED_ALERT`
- Watch displays the notification content as a full-screen alarm with `onNewIntent()` support for rapid successive alerts

**3. Universal DND Sync** (phone → watch)
- Phone `AlarmListenerService.onInterruptionFilterChanged()` broadcasts DND state changes via `/DND_SYNC`
- Watch `WatchListenerService.syncDndState()` applies the filter via `NotificationManager.setInterruptionFilter()`
- Watch requires `ACCESS_NOTIFICATION_POLICY` permission — watch `MainActivity` guides user to grant it

### Permissions
- **Phone**: Notification Access (manual grant via Settings), `QUERY_ALL_PACKAGES`
- **Watch**: `WAKE_LOCK`, `VIBRATE`, `ACCESS_NOTIFICATION_POLICY`

### Message Paths
| Path | Payload | Direction | Description |
|------|---------|-----------|-------------|
| `/START_ALARM_SOUND` | empty | phone → watch | Trigger watch alarm UI |
| `/STOP_ALARM_SOUND` | empty | phone → watch | Remotely stop watch alarm (if dismissed on phone) |
| `/SNOOZE_ALARM` | empty | watch → phone | Remotely trigger phone snooze |
| `/DISMISS_ALARM` | empty | watch → phone | Remotely trigger phone dismiss |
| `/STARRED_ALERT` | UTF-8 `"title: text"` | phone → watch | Trigger persistent alert for starred app |
| `/DND_SYNC` | DataItem (Int) | phone → watch | Sync DND interruption filter |
| `/BEDTIME_SYNC` | DataItem (Bool) | phone → watch | Sync phone Night Mode to watch |
| `/NEXT_ALARM` | DataItem (Long) | phone → watch | Sync phone's next scheduled alarm time |
| `/CUSTOM_SOUND` | binary (MP3) | phone → watch | Transfer custom alarm audio via ChannelClient |
| `/VIBRATION_SYNC` | DataItem (LongArray) | phone → watch | Sync custom vibration patterns |

### Key Files
- `alarmwatcher/phone/.../AlarmListenerService.kt` — notification listener + action capture + remote command handler
- `alarmwatcher/phone/.../MainActivity.kt` — permission setup + starred apps + custom sound sync
- `alarmwatcher/wear/.../WatchListenerService.kt` — message router + file receiver
- `alarmwatcher/wear/.../AlarmActivity.kt` — alarm UI with SNOOZE/DISMISS + custom sound playback
- `alarmwatcher/wear/.../AlarmComplicationService.kt` — provides next alarm time to watch faces
- `alarmwatcher/GEMINI.md` — development log and roadmap
- `alarmwatcher/RESTART_CONTEXT.md` — resume context for next session
