# Design Doc: Critical Alert Rules & Volume Management

## Overview
This feature allows users to define specific "Rules" for incoming notifications that should be elevated to full-screen watch alarms. It also adds granular volume control to ensure these alerts (and standard alarms) are always heard.

## Data Model: `AlertRule`
```kotlin
data class AlertRule(
    val id: String,
    val senderMatch: String?,    // Null = any sender
    val keywordMatch: String?,   // Null = any text
    val volumeLevel: Int,        // 0-100 or -1 for MAX
    val overrideDnd: Boolean,
    val vibrationPattern: String, // ID of synced pattern
    val cooldownMinutes: Int = 0, // 0 = disabled, X = ignore subsequent matches for X minutes
    val activeSchedules: List<TimeWindow> = emptyList() // Arbitrary paused/active time blocks
)

data class TimeWindow(
    val startHour: Int,
    val startMinute: Int,
    val endHour: Int,
    val endMinute: Int,
    val daysOfWeek: List<Int>, // 1-7 (Monday-Sunday)
    val isBlackout: Boolean = false // true = paused during this time, false = only active during this time
)
```

## Phone Logic (The Engine)
*   **Notification Interception:** `AlarmListenerService` checks every incoming notification.
*   **Matching:** 
    *   Does the `EXTRA_TITLE` (sender) contain `senderMatch`?
    *   Does the `EXTRA_TEXT` (message) contain `keywordMatch`?
*   **Schedule Check:** If a match is found, verify the current time against any defined global blackout periods or the rule's specific `activeSchedules`. If currently in a blackout window, silently drop the event.
*   **Cooldown Check:** Verify the current time against the `lastTriggeredAt` timestamp for this specific rule. If within the `cooldownMinutes` window, silently drop the event.
*   **Sync:** If a valid match is found, send a specific `CRITICAL_ALERT` data item to the watch containing the volume and pattern settings, and update the rule's `lastTriggeredAt` timestamp.

## Watch Logic (The Enforcer)
*   **Volume Snapshot:** `AlarmActivity` uses `AudioManager` to save the current `STREAM_ALARM` or `STREAM_MUSIC` volume.
*   **Escalation:** Set volume to the rule's level.
*   **Restoration:** In `onDestroy()` or upon dismissal, set volume back to the saved snapshot.
*   **DND Management:** Temporarily set `NotificationManager.interruptionFilter` to `ALL`.

## UI Components
*   **Volume Slider:** Added to the "Personalization" card for the main Alarm Sync.
*   **Rules List:** A new section in the Phone app to Add/Edit/Delete custom alert rules.
*   **Rule Editor:** A dialog/screen to set Sender, Keyword, and Behavior.

## User Scenarios
1.  **Emergency Contact:** Rule for "Mom" + Keyword "Emergency" -> MAX Volume + Heartbeat Vibrate + DND Override.
2.  **Home Security:** Rule for "Ring" + Keyword "Person Detected" -> 50% Volume + Standard Vibrate.
3.  **Standard Alarm:** Global volume setting for all bridged phone alarms.
