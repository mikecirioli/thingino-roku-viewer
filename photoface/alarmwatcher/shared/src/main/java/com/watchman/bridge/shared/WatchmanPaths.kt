package com.watchman.bridge.shared

object WatchmanPaths {
    // Commands (Messages)
    const val START_ALARM = "/START_ALARM_SOUND"
    const val STOP_ALARM = "/STOP_ALARM_SOUND"
    const val SNOOZE_ALARM = "/SNOOZE_ALARM"
    const val DISMISS_ALARM = "/DISMISS_ALARM"
    const val DISMISS_NOTIFICATION = "/dismiss_notification"
    const val OPEN_PHONE_APP = "/OPEN_PHONE_APP"
    
    // State (Data Items)
    const val DND_STATE = "/DND_SYNC"
    const val DND_OVERRIDE_PREF = "/DND_OVERRIDE"
    const val ALARM_VOLUME_PREF = "/ALARM_VOLUME"
    const val CRITICAL_ALERT = "/CRITICAL_ALERT"
    const val RULE_SOUND_FILE = "/RULE_SOUND"
    const val NEXT_ALARM_STATE = "/NEXT_ALARM"
    const val CUSTOM_SOUND_FILE = "/CUSTOM_SOUND"
    const val VIBRATION_PATTERN = "/VIBRATION_SYNC"
}
