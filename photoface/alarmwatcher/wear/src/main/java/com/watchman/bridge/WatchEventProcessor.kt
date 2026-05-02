package com.watchman.bridge

import com.watchman.bridge.data.WearSettingsRepository

class WatchEventProcessor(
    private val repository: WearSettingsRepository,
    private val startActivityCallback: (key: String?, soundFile: String?, message: String?, volume: Float?, dnd: Boolean?, playDurationSeconds: Int?, vibrationPattern: String?, vibrateOnly: Boolean?) -> Unit,
    private val sendBroadcastCallback: (action: String) -> Unit
) {
    fun processDndState(filter: Int) {
        repository.syncDndState(filter)
    }

    fun processDndOverride(enabled: Boolean) {
        repository.setDndOverrideEnabled(enabled)
    }

    fun processAlarmVolume(volume: Float) {
        repository.setAlarmVolume(volume)
    }

    fun processNextAlarmTime(timestamp: Long) {
        repository.setNextAlarmTime(timestamp)
    }

    fun processVibrateOnly(enabled: Boolean) {
        repository.setVibrateOnly(enabled)
    }

    fun processVibrationPattern(patternName: String?) {
        repository.setVibrationPattern(patternName ?: "Standard")
    }

    fun processStartAlarm() {
        startActivityCallback(null, "custom_alarm.mp3", null, null, null, null, null, null)
    }

    fun processStopAlarm() {
        sendBroadcastCallback("com.watchman.bridge.FINISH_ALARM")
    }

    fun processCriticalAlert(payload: String) {
        if (payload.trimStart().startsWith("{")) {
            try {
                val json = org.json.JSONObject(payload)
                val key = json.optString("key", null)
                val message = json.optString("message", "")
                if (message.isEmpty()) return

                val volume = json.optDouble("volume", 1.0).toFloat()
                val dnd = json.optBoolean("overrideDnd", false)
                val soundFile = json.optString("soundFile", "custom_alarm.mp3")
                val playDurationSeconds = json.optInt("playDurationSeconds", -1)
                val vibrationPattern = json.optString("vibrationPattern", "Standard")
                val vibrateOnly = json.optBoolean("vibrateOnly", false)

                startActivityCallback(key, soundFile, message, volume, dnd, playDurationSeconds, vibrationPattern, vibrateOnly)
                return
            } catch (e: Exception) {
                // Ignore JSON parsing errors and fall back
            }
        }

        val parts = payload.split("|")
        // A valid payload must have at least the message, volume, and DND flag.
        if (parts.size < 3) {
            return
        }

        val message = parts[0]
        val volume = parts[1].toFloatOrNull() ?: 1.0f
        val dnd = parts[2].toBoolean()

        // Safely parse optional parameters that may not exist in all versions or test payloads
        val soundFile = parts.getOrNull(3) ?: "custom_alarm.mp3"
        val playDurationSeconds = parts.getOrNull(4)?.toIntOrNull() ?: -1
        val vibrationPattern = parts.getOrNull(5) ?: "Standard"
        val vibrateOnly = parts.getOrNull(6)?.toBoolean() ?: false

        startActivityCallback(null, soundFile, message, volume, dnd, playDurationSeconds, vibrationPattern, vibrateOnly)
    }
}
