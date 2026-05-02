package com.watchman.bridge

import com.watchman.bridge.data.SettingsRepository
import com.watchman.bridge.BuildConfig // Assuming BuildConfig for context
import android.util.Log // For logging

class TrialManager(
    private val settingsRepository: SettingsRepository,
    private val timeProvider: () -> Long = { System.currentTimeMillis() },
    private val isDebug: Boolean = BuildConfig.DEBUG
) {
    private val TAG = "TrialManager"
    private val TRIAL_DURATION_MS = 3 * 24 * 60 * 60 * 1000L // 3 Days

    init {
        // Mark install time if not exists
        if (settingsRepository.getInstallTime() == 0L) {
            settingsRepository.setInstallTime(timeProvider())
        }
    }

    fun isProUser(): Boolean {
        // Always return true for debug builds so developer isn't locked out
        if (isDebug) {
            Log.d(TAG, "Debug build: Pro user bypass enabled.")
            return true
        }
        return settingsRepository.isProUser()
    }

    fun setProUser(enabled: Boolean) {
        settingsRepository.setProUser(enabled)
    }

    fun isTrialActive(): Boolean {
        if (isProUser()) return true
        val installTime = settingsRepository.getInstallTime()
        return (timeProvider() - installTime) < TRIAL_DURATION_MS
    }

    fun getRemainingHours(): Int {
        if (isProUser()) return -1
        val installTime = settingsRepository.getInstallTime()
        val elapsed = timeProvider() - installTime
        val remainingMs = TRIAL_DURATION_MS - elapsed
        return if (remainingMs < 0) 0 else (remainingMs / (1000 * 60 * 60)).toInt()
    }
}
