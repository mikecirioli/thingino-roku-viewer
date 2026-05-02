# Watchman Bridge -- Code Review & Bug Analysis
**Date:** 2026-02-24
**Reviewer:** Claude (Android expert review)
**Codebase:** `/export/git/photoface/alarmwatcher/`

---

## Bug Report: Test Alarm Sync No Longer Activating Watch

### Summary

The "Test Alarm Sync" button on the phone and all message-based communication (alarm triggers, critical alerts, snooze/dismiss) fail to reach the watch. The root cause is an uncommitted change to `phone/WearableRepository.sendMessage()` that replaced reliable `nodeClient.connectedNodes` with `capabilityClient.getCapability()`.

### Root Cause

**Primary:** `wear/build.gradle.kts` (uncommitted change)

The uncommitted changes changed the wear module's `applicationId` from `com.watchman.bridge` to `com.watchman.bridge.wear`. The Wearable Data Layer requires **matching `applicationId`** across paired devices to route messages and data items. With mismatched package names, ALL communication silently fails -- messages, data items, and channel transfers are simply not delivered.

**Secondary:** `phone/src/main/java/com/watchman/bridge/WearableRepository.kt` (uncommitted change)

The committed version uses simple connected-node discovery with a retry:

```kotlin
// COMMITTED (WORKING)
var nodes = nodeClient.connectedNodes.await()
if (nodes.isEmpty()) {
    Log.w(TAG, "No nodes found for $path, retrying in 2s...")
    kotlinx.coroutines.delay(2000)
    nodes = nodeClient.connectedNodes.await()
}
```

The uncommitted working tree change replaced this with capability-based discovery which is unreliable for sideloaded builds:

```kotlin
// UNCOMMITTED (ALSO BROKEN)
val capabilityInfo = capabilityClient.getCapability(
    WEAR_CAPABILITY, CapabilityClient.FILTER_REACHABLE
).await()
val nodes = capabilityInfo.nodes
```

### Fix Applied

1. Reverted `wear/build.gradle.kts` `applicationId` back to `com.watchman.bridge`
2. Reverted `phone/WearableRepository.sendMessage()` back to `nodeClient.connectedNodes` with 2-second retry

### Impact (before fix)

ALL communication fails silently:
- `testGlobalAlarm()` / `testAlertRule()` -- test buttons don't trigger watch
- `AlarmListenerService` -- real alarm triggers (`START_ALARM`) don't reach watch
- `AlarmListenerService` -- critical alerts (`CRITICAL_ALERT`) don't reach watch
- `clearActiveIntents()` -- stop signals (`STOP_ALARM`) don't reach watch

With mismatched `applicationId`, ALL Wearable Data Layer communication fails:
- `sendMessage()` -- alarm triggers, critical alerts, snooze/dismiss, stop
- `updateData()` -- DND sync, bedtime sync, volume, vibration settings
- `sendFile()` / `ChannelClient` -- custom sound file transfers

### Fix Applied

1. Reverted `wear/build.gradle.kts` `applicationId` back to `com.watchman.bridge`
2. Reverted `phone/WearableRepository.sendMessage()` back to `nodeClient.connectedNodes` with 2-second retry
3. Verified fix on hardware -- test alarm sync and DND sync both working

### Recommended Fix (for future capability usage)

Revert `sendMessage()` to use `nodeClient.connectedNodes` with the retry logic. If capability-based discovery is desired for multi-device targeting, use it as a primary lookup with `connectedNodes` as a fallback:

```kotlin
fun sendMessage(path: String, payload: ByteArray = ByteArray(0)) {
    scope.launch {
        try {
            // Try capability-based discovery first (targets only Watchman nodes)
            var nodes = try {
                capabilityClient.getCapability(WEAR_CAPABILITY, CapabilityClient.FILTER_REACHABLE)
                    .await().nodes
            } catch (e: Exception) {
                Log.w(TAG, "Capability lookup failed, falling back to connectedNodes", e)
                emptySet()
            }

            // Fallback to all connected nodes
            if (nodes.isEmpty()) {
                Log.w(TAG, "No capable nodes for $path, falling back to connectedNodes")
                val connectedNodes = nodeClient.connectedNodes.await()
                if (connectedNodes.isEmpty()) {
                    kotlinx.coroutines.delay(2000)
                    nodes = nodeClient.connectedNodes.await().toSet()
                } else {
                    nodes = connectedNodes.toSet()
                }
            }

            if (nodes.isEmpty()) {
                Log.e(TAG, "Failed to send $path: No nodes connected")
                return@launch
            }

            nodes.forEach { node ->
                messageClient.sendMessage(node.id, path, payload).await()
                Log.d(TAG, "Sent $path to ${node.displayName}")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send $path", e)
        }
    }
}
```

---

## Full Code Review -- Issue List

### CRITICAL (Ship-blockers)

#### 1. `BuildConfig.DEBUG` hardcoded to `true` -- trial/billing completely bypassed

**File:** `phone/src/main/java/com/watchman/bridge/BuildConfig.kt:4-5`

```kotlin
object BuildConfig {
    val DEBUG = true
}
```

This custom `BuildConfig` object always returns `DEBUG = true`. Both `TrialManager.isProUser()` and `SharedPrefsSettingsRepository.isProUser()` check this flag and return `true` when set. Result: every user (including release builds) is treated as a pro user. The 72-hour trial is never enforced and billing is cosmetic.

The Android build system generates a real `BuildConfig` class, but this manual object shadows it at the source level. This was clearly a dev workaround ("Dummy BuildConfig to unblock CLI compilation") that was never reverted.

**Impact:** Entire monetization model is defeated. No user will ever see a trial expiration or need to purchase.

#### 2. Capability XML directory untracked in git

**File:** `wear/src/main/res/xml/` (git status: `??`)

The `wearable_capabilities.xml` and `wear.xml` files exist on disk but were never committed. A clean clone, CI build, or collaborator checkout will produce a watch APK without the capability declaration, breaking all capability-based lookups.

Even after the `sendMessage()` bug is fixed (reverting to `connectedNodes`), these files should be committed for future use.

**Impact:** Clean builds produce a broken watch app.

---

### HIGH

#### 3. Missing `RECEIVER_NOT_EXPORTED` on broadcast receivers (API 34 crash)

**File:** `phone/src/main/java/com/watchman/bridge/AlarmListenerService.kt:65-66`

```kotlin
registerReceiver(alarmChangeReceiver, IntentFilter(AlarmManager.ACTION_NEXT_ALARM_CLOCK_CHANGED))
registerReceiver(bedtimeReceiver, IntentFilter(Intent.ACTION_CONFIGURATION_CHANGED))
```

Starting with Android 14 (API 34 = the `targetSdk`), all dynamically registered broadcast receivers must specify `RECEIVER_EXPORTED` or `RECEIVER_NOT_EXPORTED`. The `remoteCommandReceiver` (line 67) correctly uses `RECEIVER_NOT_EXPORTED`, but these two do not. On API 34+ devices, this throws `SecurityException` and crashes `AlarmListenerService.onCreate()`.

Since `ACTION_NEXT_ALARM_CLOCK_CHANGED` is a system broadcast, `RECEIVER_EXPORTED` is needed. For `ACTION_CONFIGURATION_CHANGED`, same applies.

#### 4. `sendFile` uses `nodeClient.connectedNodes` while `sendMessage` uses capabilities

**File:** `phone/src/main/java/com/watchman/bridge/WearableRepository.kt:66`

Inconsistent node targeting between `sendMessage()` (capability-based) and `sendFile()` (connectedNodes). Sound files could be sent to a different node than alarm messages, causing the watch to receive a sound file it never gets asked to play, or vice versa.

#### 5. All wear-side tests broken -- won't compile

**File:** `wear/src/test/java/com/watchman/bridge/WatchEventProcessorTest.kt`

- Uses old 4-parameter callback signature `(String?, String?, Float?, Boolean?)` -- actual is 7 parameters
- Tests `processVibrationPattern(longArrayOf(100, 200))` -- method now takes `String?`
- Tests `processCriticalAlert` with 4-field payload -- current code expects up to 7 fields

#### 6. Phone-side test assertions stale

**File:** `phone/src/test/java/com/watchman/bridge/AlarmListenerServiceTest.kt`

- Asserts payload format `"title|text|..."` but current code sends `"title: text|..."` with 3 additional fields appended
- Constructor call for `AlertRule` in tests is missing `playDurationSeconds` and `vibrateOnly` fields

---

### MEDIUM-HIGH

#### 7. Pipe-delimited payload protocol is fragile

**Files:** `phone/.../AlarmListenerService.kt:247,260` and `wear/.../WatchEventProcessor.kt:46-63`

The critical alert protocol is `"message|volume|dnd|soundFile|duration|vibPattern|vibrateOnly"` split on `|`. Problems:
- User-generated content only sanitized for `|`, not other edge cases
- No versioning -- adding/removing fields silently breaks parsing (already happened once)
- `parts[2].toBoolean()` silently returns `false` for any non-"true" string

Should use JSON or a versioned key-value format.

#### 8. Bedtime mode detection is wrong

**File:** `phone/src/main/java/com/watchman/bridge/AlarmListenerService.kt:109-116`

`UiModeManager.nightMode` returns the system dark theme mode, NOT Digital Wellbeing "Bedtime Mode." These are different features. Bedtime Mode has no public API. Also, `ACTION_CONFIGURATION_CHANGED` fires for any config change (rotation, locale, font) -- not specifically for bedtime changes.

#### 9. Namespace collision -- phone and wear share `com.watchman.bridge`

**Files:** Both `build.gradle.kts` files: `namespace = "com.watchman.bridge"`

Both modules have the same namespace and contain identically-named classes (`WearableRepository`, `WatchmanPaths`, `MainActivity`). Can cause R class conflicts and confusion.

---

### MEDIUM

#### 10. Default ringtone doesn't loop

**File:** `wear/src/main/java/com/watchman/bridge/AlarmActivity.kt:314-318`

`MediaPlayer` path sets `isLooping = true`, but the `Ringtone` fallback plays once and stops. On API 28+, `Ringtone` has `setLooping()` but it's not called. User may sleep through the alarm.

#### 11. Second alarm silently dropped via `onNewIntent`

**File:** `wear/src/main/java/com/watchman/bridge/AlarmActivity.kt:201-205`

If a new alarm arrives while one is playing, the new intent's parameters (sound, volume, DND, message) are ignored. The old alarm's settings remain active.

#### 12. ViewModel holds Activity context (memory leak)

**File:** `phone/src/main/java/com/watchman/bridge/MainActivity.kt:213`

`LocalContext.current` passes Activity context to ViewModel. The ViewModel survives configuration changes but holds a reference to the destroyed Activity.

#### 13. Wake lock held for 10 minutes with no re-acquire

**File:** `wear/src/main/java/com/watchman/bridge/AlarmActivity.kt:84`

The wake lock may expire while the alarm is still active. `onNewIntent` doesn't re-acquire it.

#### 14. `QUERY_ALL_PACKAGES` permission likely unnecessary

**File:** `phone/src/main/AndroidManifest.xml:5`

Google Play restricts this permission. Not visibly used in the notification listener logic. May cause Play Store rejection.

#### 15. Duplicated `WatchmanPaths` across modules

**Files:** `phone/.../WatchmanPaths.kt` and `wear/.../WatchmanPaths.kt`

Identical copies. Any divergence silently breaks the app. Should be a shared module.

#### 16. `WatchListenerServiceTest` is effectively a no-op

**File:** `wear/src/test/java/com/watchman/bridge/WatchListenerServiceTest.kt`

The single test only checks `service != null`. Tests no actual behavior.

---

### LOW-MEDIUM

#### 17. Trial bypass via app data clear

Clearing app data resets `EncryptedSharedPreferences`, giving a fresh 72-hour window. The "delete and recreate" fallback in `SharedPrefsSettingsRepository.kt:20-29` makes this easier. Acceptable risk for $1.49 but worth noting.

#### 18. `AlarmActivity` exported without permission guard

**File:** `wear/src/main/AndroidManifest.xml:69`

Any watch app can launch `AlarmActivity` with arbitrary extras (volume, DND override, message).

#### 19. ProGuard/R8 disabled in release builds

**Files:** Both `build.gradle.kts`: `isMinifyEnabled = false`

Larger APK, no obfuscation, trial logic trivially reversible.

#### 20. `isClockPackage` overly broad matching

**File:** `phone/src/main/java/com/watchman/bridge/AlarmListenerService.kt:267-275`

- `pkg.contains("alarm")` matches any package with "alarm" in the name
- `com.miui.notes` is Xiaomi's Notes app, not an alarm clock
- `com.android.settings` can match system settings notifications

#### 21. AlertRules stored as `StringSet` (unordered)

**File:** `phone/src/main/java/com/watchman/bridge/data/SharedPrefsSettingsRepository.kt:83`

`SharedPreferences.getStringSet()` returns an unordered set. Rules appear in random order each app launch.

#### 22. Sensitive notification content logged at INFO level

**Files:** Multiple -- `WatchListenerService.kt:110` logs full payload including notification text.

#### 23. Data API dedup without timestamps

**Files:** `syncBedtimeMode()` and `onInterruptionFilterChanged()` don't include `updated_at` timestamp. Identical data values are silently deduplicated and the watch won't receive the event.

#### 24. `compileSdk`/`targetSdk` at 34

Should be updated to 35 for upcoming Play Store requirements.

#### 25. Deprecated complication action string

**File:** `wear/src/main/AndroidManifest.xml:85`

Uses `android.support.wearable.complications.ACTION_COMPLICATION_UPDATE_REQUEST` instead of the AndroidX equivalent.

---

## Summary Table

| # | Issue | Severity | Category |
|---|-------|----------|----------|
| BUG | `sendMessage()` changed to capability-based lookup | **CRITICAL BUG** | Regression |
| 1 | `BuildConfig.DEBUG = true` hardcoded | CRITICAL | Monetization |
| 2 | Capability XML untracked in git | CRITICAL | Build |
| 3 | Missing `RECEIVER_NOT_EXPORTED` (API 34 crash) | HIGH | Crash |
| 4 | `sendFile` vs `sendMessage` node targeting mismatch | HIGH | Reliability |
| 5 | Wear-side tests broken (won't compile) | HIGH | Tests |
| 6 | Phone-side test assertions stale | HIGH | Tests |
| 7 | Pipe-delimited payload fragility | MEDIUM-HIGH | Architecture |
| 8 | Bedtime mode detection wrong | MEDIUM-HIGH | Feature |
| 9 | Namespace collision | MEDIUM-HIGH | Build |
| 10 | Default ringtone doesn't loop | MEDIUM | Reliability |
| 11 | Second alarm silently dropped | MEDIUM | UX |
| 12 | ViewModel holds Activity context | MEDIUM | Memory |
| 13 | Wake lock not re-acquired | MEDIUM | Reliability |
| 14 | `QUERY_ALL_PACKAGES` unnecessary | MEDIUM | Play Store |
| 15 | Duplicated `WatchmanPaths` | MEDIUM | Maintenance |
| 16 | `WatchListenerServiceTest` no-op | MEDIUM | Tests |
| 17 | Trial bypass via data clear | LOW-MEDIUM | Security |
| 18 | `AlarmActivity` exported unguarded | LOW-MEDIUM | Security |
| 19 | ProGuard disabled in release | LOW-MEDIUM | Security |
| 20 | `isClockPackage` overly broad | LOW-MEDIUM | Correctness |
| 21 | AlertRules unordered (StringSet) | LOW-MEDIUM | UX |
| 22 | Sensitive data in logs | LOW-MEDIUM | Privacy |
| 23 | Data API dedup without timestamps | LOW-MEDIUM | Reliability |
| 24 | compileSdk/targetSdk outdated | LOW-MEDIUM | Compliance |
| 25 | Deprecated complication action | LOW | Maintenance |
