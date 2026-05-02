package com.speedwatcher.phone

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class PreferencesManager(context: Context) {
    private val prefs: SharedPreferences

    init {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        prefs = EncryptedSharedPreferences.create(
            context,
            "speedwatcher_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    var targetMacAddresses: Set<String>
        get() = prefs.getStringSet("target_mac_addresses", emptySet()) ?: emptySet()
        set(value) = prefs.edit().putStringSet("target_mac_addresses", value).apply()

    var speedThreshold: Int
        get() = prefs.getInt("speed_threshold", 75)
        set(value) = prefs.edit().putInt("speed_threshold", value).apply()

    var speedUnit: String
        get() = prefs.getString("speed_unit", "MPH") ?: "MPH"
        set(value) = prefs.edit().putString("speed_unit", value).apply()

    var cooldownSeconds: Int
        get() = prefs.getInt("cooldown_seconds", 30)
        set(value) = prefs.edit().putInt("cooldown_seconds", value).apply()

    var vibrationPattern: String
        get() = prefs.getString("vibration_pattern", "Rapid") ?: "Rapid"
        set(value) = prefs.edit().putString("vibration_pattern", value).apply()

    var vibrationPower: Int
        get() = prefs.getInt("vibration_power", 255)
        set(value) = prefs.edit().putInt("vibration_power", value).apply()

    var savedPresets: Set<String>
        get() = prefs.getStringSet("saved_presets", emptySet()) ?: emptySet()
        set(value) = prefs.edit().putStringSet("saved_presets", value).apply()

    var isServiceEnabled: Boolean
        get() = prefs.getBoolean("is_service_enabled", true)
        set(value) = prefs.edit().putBoolean("is_service_enabled", value).apply()

    var useDynamicLimit: Boolean
        get() = prefs.getBoolean("use_dynamic_limit", false)
        set(value) = prefs.edit().putBoolean("use_dynamic_limit", value).apply()

    var dynamicOverage: Int
        get() = prefs.getInt("dynamic_overage", 5)
        set(value) = prefs.edit().putInt("dynamic_overage", value).apply()
}
