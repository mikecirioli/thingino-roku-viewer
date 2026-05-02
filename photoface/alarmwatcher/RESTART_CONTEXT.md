# Restart Context: Watchman Bridge

## Current State (2026-02-24)
- **Architecture:** Hybrid sync engine verified. Persistent state (DND, Bedtime, Volume) on Data API; Alarms and Critical Alerts on Message API for 100% reliability.
- **Modern UI:** Material 3 / Compose UI fully polished on both devices.
- **Verified v1.21:**
    1. All v1.20 features (Playback Duration, Samsung Compatibility, Android 14+ Fixes, Smart Watch UI).
    2. **Test Alarm Buttons:** Added "Test Alarm Sync" (global) and "Test Rule on Watch" (per-rule) to phone UI.
    3. **Global Vibration Controls:** Added Vibrate Only toggle and Vibration Pattern selector to global alarm settings.
    4. **Ongoing Notification Filter:** Skips ongoing notifications (call timers, media players, navigation) to prevent false alerts.
    5. **Payload Sanitization:** Pipe characters in notification content are sanitized to prevent payload parsing corruption.
    6. **EncryptedSharedPreferences Recovery:** Auto-deletes and recreates corrupted encrypted prefs instead of crashing.

### Bugs Fixed (2026-02-24)
- **CRITICAL: `applicationId` mismatch broke ALL phone-watch communication.** The wear module's `applicationId` was changed from `com.watchman.bridge` to `com.watchman.bridge.wear`. The Wearable Data Layer requires matching `applicationId` across paired devices. Reverted.
- **`sendMessage()` regression.** Phone's `WearableRepository.sendMessage()` was changed from `nodeClient.connectedNodes` (with 2s retry) to `capabilityClient.getCapability()` which is unreliable for sideloaded/debug builds. Reverted.
- **Stale tests.** `WatchEventProcessorTest` used old 4-param callback (now 7-param) and old `processVibrationPattern(LongArray)` signature (now `String?`). `AlarmListenerServiceTest` asserted old payload format. Both fixed.

### Known Issues (from code review)
- **CRITICAL:** `BuildConfig.DEBUG = true` hardcoded in `BuildConfig.kt` -- trial/billing bypassed for ALL builds including release. Must be removed before Play Store submission.
- **CRITICAL:** `wear/src/main/res/xml/` directory is untracked in git. Must be committed.
- **HIGH:** Missing `RECEIVER_NOT_EXPORTED` on `alarmChangeReceiver` and `bedtimeReceiver` in `AlarmListenerService` -- will crash on API 34+.
- **MEDIUM-HIGH:** Bedtime mode detection syncs dark theme, not actual Digital Wellbeing Bedtime Mode.
- See `/export/claude_notes/watchman-bridge-review-2026-02-24.md` for the full 25-item review.

## IMPORTANT: applicationId Must Match
**Phone:** `com.watchman.bridge` | **Watch:** `com.watchman.bridge`
The Wearable Data Layer silently drops ALL communication (messages, data items, channels) if these don't match. Never change one without the other.

## Immediate Next Steps
1. Fix `BuildConfig.kt` -- remove the hardcoded object, let Gradle generate it.
2. Commit `wear/src/main/res/xml/` to git.
3. Add `RECEIVER_EXPORTED` flag to system broadcast receivers in `AlarmListenerService`.
4. Address remaining review items (see review doc).

## Future Considerations
1. **Phone Battery Sync:** Add a complication to show phone juice on the watch.
2. **"The Leash":** Alerts for phone full charge or connection loss.
3. **Structured Payloads:** Replace pipe-delimited protocol with JSON for forward compatibility.
