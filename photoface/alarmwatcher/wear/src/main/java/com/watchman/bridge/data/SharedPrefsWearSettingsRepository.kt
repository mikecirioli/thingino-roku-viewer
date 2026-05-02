package com.watchman.bridge.data

import android.app.NotificationManager
import android.content.Context
import android.util.Log
import com.watchman.bridge.AlarmComplicationService

class SharedPrefsWearSettingsRepository(private val context: Context) : WearSettingsRepository {

    private val TAG = "WearSettingsRepo"
    private val prefs = context.getSharedPreferences("WatchmanPrefs", Context.MODE_PRIVATE)

    override fun setDndOverrideEnabled(enabled: Boolean) {
        prefs.edit().putBoolean("dnd_override", enabled).apply()
    }

    override fun setAlarmVolume(volume: Float) {
        prefs.edit().putFloat("alarm_volume", volume).apply()
    }

    override fun setNextAlarmTime(timestamp: Long) {
        prefs.edit().putLong("next_alarm_time", timestamp).apply()
        AlarmComplicationService.triggerUpdate(context)
    }

    override fun setVibrateOnly(enabled: Boolean) {
        prefs.edit().putBoolean("vibrate_only", enabled).apply()
    }

    override fun setVibrationPattern(pattern: String) {
        prefs.edit().putString("vibration_pattern", pattern).apply()
    }

    override fun syncDndState(filter: Int) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        try {
            if (nm.isNotificationPolicyAccessGranted) {
                nm.setInterruptionFilter(filter)
            }
        } catch (e: Exception) {
            Log.e(TAG, "DND sync failed", e)
        }
    }
}
