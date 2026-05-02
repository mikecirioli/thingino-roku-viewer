package com.watchman.bridge.data

interface WearSettingsRepository {
    fun setDndOverrideEnabled(enabled: Boolean)
    fun setAlarmVolume(volume: Float)
    fun setNextAlarmTime(timestamp: Long)
    fun setVibrateOnly(enabled: Boolean)
    fun setVibrationPattern(pattern: String)
    
    fun syncDndState(filter: Int)
}
