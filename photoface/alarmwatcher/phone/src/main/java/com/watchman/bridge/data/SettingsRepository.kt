package com.watchman.bridge.data

import com.watchman.bridge.shared.data.AlertRule



interface SettingsRepository {
    // TrialManager related
    fun getInstallTime(): Long
    fun setInstallTime(time: Long)
    fun isProUser(): Boolean
    fun setProUser(enabled: Boolean)

    // Alert Rule related
    fun getAlertRules(): List<com.watchman.bridge.shared.data.AlertRule>
    fun saveAlertRule(rule: com.watchman.bridge.shared.data.AlertRule)
    fun deleteAlertRule(id: String)

    // Other settings
    fun isHighReliabilityEnabled(): Boolean
    fun setHighReliabilityEnabled(enabled: Boolean)
    fun isGlobalCatchAllEnabled(): Boolean
    fun setGlobalCatchAllEnabled(enabled: Boolean)
    fun getAlarmVolume(): Float
    fun setAlarmVolume(volume: Float)
    fun isDndOverrideEnabled(): Boolean
    fun setDndOverrideEnabled(enabled: Boolean)

    fun getCustomSoundName(): String
    fun setCustomSoundName(name: String)

    fun getGlobalVibrationPattern(): String
    fun setGlobalVibrationPattern(pattern: String)
    fun isGlobalVibrateOnly(): Boolean
    fun setGlobalVibrateOnly(enabled: Boolean)

    fun getGlobalQuietHours(): List<com.watchman.bridge.shared.data.TimeWindow>
    fun saveGlobalQuietHours(schedules: List<com.watchman.bridge.shared.data.TimeWindow>)

    // Tile Service related
    fun isServiceGloballyEnabled(): Boolean
    fun setServiceGloballyEnabled(enabled: Boolean)
    fun getSnoozeUntil(): Long
    fun setSnoozeUntil(timestamp: Long)
}
