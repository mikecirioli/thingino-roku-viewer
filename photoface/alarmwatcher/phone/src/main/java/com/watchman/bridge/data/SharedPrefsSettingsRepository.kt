package com.watchman.bridge.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.watchman.bridge.shared.data.AlertRule
import com.watchman.bridge.BuildConfig // Assuming BuildConfig for context
import android.util.Log // For logging
import java.io.File

class SharedPrefsSettingsRepository(
    private val context: Context,
    private val isDebug: Boolean = BuildConfig.DEBUG
) : SettingsRepository {

    private val TAG = "SharedPrefsSettingsRepo"

    // Encrypted SharedPreferences for sensitive data (TrialManager related)
    private val encryptedPrefs: SharedPreferences by lazy {
        try {
            createEncryptedPrefs()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load encrypted prefs, likely due to corruption. Deleting and recreating.", e)
            // Attempt to delete the corrupted file. This is a best-effort approach.
            val prefsFile = File(context.filesDir.parent, "shared_prefs/WatchmanEncryptedPrefs.xml")
            if (prefsFile.exists()) {
                prefsFile.delete()
            }
            // Now, try creating it again. If this fails, the app will crash, but it's our best shot.
            createEncryptedPrefs()
        }
    }

    private fun createEncryptedPrefs(): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            "WatchmanEncryptedPrefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    // Regular SharedPreferences for other settings (Alert Rules, Toggles)
    private val regularPrefs: SharedPreferences by lazy {
        context.getSharedPreferences("WatchmanPrefs", Context.MODE_PRIVATE)
    }

    // --- TrialManager related ---
    override fun getInstallTime(): Long {
        return encryptedPrefs.getLong("INSTALL_KEY", 0L)
    }

    override fun setInstallTime(time: Long) {
        encryptedPrefs.edit().putLong("INSTALL_KEY", time).apply()
    }

    override fun isProUser(): Boolean {
        // Developer "Pro" bypass for debug builds
        if (isDebug) {
            Log.d(TAG, "Debug build: Pro user bypass enabled.")
            return true
        }
        return encryptedPrefs.getBoolean("PRO_KEY", false)
    }

    override fun setProUser(enabled: Boolean) {
        encryptedPrefs.edit().putBoolean("PRO_KEY", enabled).apply()
    }

    // --- Alert Rule related ---
    override fun getAlertRules(): List<AlertRule> {
        val saved = regularPrefs.getStringSet("alert_rules", emptySet()) ?: emptySet()
        return saved.mapNotNull { AlertRule.fromFlattenedString(it) }
    }

    override fun saveAlertRule(rule: AlertRule) {
        val currentRules = getAlertRules().toMutableList()
        // Remove existing rule if it has the same ID, then add the new/updated rule
        currentRules.removeIf { it.id == rule.id }
        currentRules.add(rule)
        regularPrefs.edit().putStringSet("alert_rules", currentRules.map { it.toFlattenedString() }.toSet()).apply()
    }

    override fun deleteAlertRule(id: String) {
        val currentRules = getAlertRules().toMutableList()
        currentRules.removeIf { it.id == id }
        regularPrefs.edit().putStringSet("alert_rules", currentRules.map { it.toFlattenedString() }.toSet()).apply()
    }

    // --- Other settings ---
    override fun isHighReliabilityEnabled(): Boolean {
        return regularPrefs.getBoolean("KEY_HIGH_RELIABILITY", false)
    }

    override fun setHighReliabilityEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("KEY_HIGH_RELIABILITY", enabled).apply()
    }

    override fun isGlobalCatchAllEnabled(): Boolean {
        return regularPrefs.getBoolean("KEY_GLOBAL_CATCH_ALL", false)
    }

    override fun setGlobalCatchAllEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("KEY_GLOBAL_CATCH_ALL", enabled).apply()
    }

    override fun getAlarmVolume(): Float {
        return regularPrefs.getFloat("KEY_ALARM_VOLUME", 0.5f) // Default to 0.5f
    }

    override fun setAlarmVolume(volume: Float) {
        regularPrefs.edit().putFloat("KEY_ALARM_VOLUME", volume).apply()
    }

    override fun isDndOverrideEnabled(): Boolean {
        return regularPrefs.getBoolean("KEY_DND_OVERRIDE", false)
    }

    override fun setDndOverrideEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("KEY_DND_OVERRIDE", enabled).apply()
    }

    override fun getCustomSoundName(): String {
        return regularPrefs.getString("KEY_CUSTOM_SOUND_NAME", "Default Ringtone") ?: "Default Ringtone"
    }

    override fun setCustomSoundName(name: String) {
        regularPrefs.edit().putString("KEY_CUSTOM_SOUND_NAME", name).apply()
    }

    override fun getGlobalVibrationPattern(): String {
        return regularPrefs.getString("KEY_GLOBAL_VIBRATION_PATTERN", "Standard") ?: "Standard"
    }

    override fun setGlobalVibrationPattern(pattern: String) {
        regularPrefs.edit().putString("KEY_GLOBAL_VIBRATION_PATTERN", pattern).apply()
    }

    override fun isGlobalVibrateOnly(): Boolean {
        return regularPrefs.getBoolean("KEY_GLOBAL_VIBRATE_ONLY", false)
    }

    override fun setGlobalVibrateOnly(enabled: Boolean) {
        regularPrefs.edit().putBoolean("KEY_GLOBAL_VIBRATE_ONLY", enabled).apply()
    }

    override fun getGlobalQuietHours(): List<com.watchman.bridge.shared.data.TimeWindow> {
        val saved = regularPrefs.getString("global_quiet_hours", null) ?: return emptyList()
        return try {
            val array = org.json.JSONArray(saved)
            val list = mutableListOf<com.watchman.bridge.shared.data.TimeWindow>()
            for (i in 0 until array.length()) {
                list.add(com.watchman.bridge.shared.data.TimeWindow.fromJson(array.getJSONObject(i)))
            }
            list
        } catch (e: Exception) { emptyList() }
    }

    override fun saveGlobalQuietHours(schedules: List<com.watchman.bridge.shared.data.TimeWindow>) {
        val array = org.json.JSONArray()
        schedules.forEach { array.put(it.toJson()) }
        regularPrefs.edit().putString("global_quiet_hours", array.toString()).apply()
    }

    override fun isServiceGloballyEnabled(): Boolean {
        return regularPrefs.getBoolean("KEY_SERVICE_ENABLED", true)
    }

    override fun setServiceGloballyEnabled(enabled: Boolean) {
        regularPrefs.edit().putBoolean("KEY_SERVICE_ENABLED", enabled).apply()
    }

    override fun getSnoozeUntil(): Long {
        return regularPrefs.getLong("KEY_SNOOZE_UNTIL", 0L)
    }

    override fun setSnoozeUntil(timestamp: Long) {
        regularPrefs.edit().putLong("KEY_SNOOZE_UNTIL", timestamp).apply()
    }
}
