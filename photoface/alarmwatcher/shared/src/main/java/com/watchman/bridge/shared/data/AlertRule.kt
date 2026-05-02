package com.watchman.bridge.shared.data

import org.json.JSONArray
import org.json.JSONObject

data class AlertRule(
    val id: String = java.util.UUID.randomUUID().toString(),
    val sender: String = "",
    val keyword: String = "",
    val volume: Float = 1.0f,
    val overrideDnd: Boolean = true,
    val vibration: String = "Standard",
    val soundName: String = "Default Ringtone",
    val playDurationSeconds: Int = -1, // -1 means until dismissed
    val vibrateOnly: Boolean = false,
    val cooldownMinutes: Int = 0, // 0 = disabled, X = ignore subsequent matches for X minutes
    val activeSchedules: List<TimeWindow> = emptyList(), // Allowed/paused times
    var lastTriggeredAt: Long = 0L // Timestamp of last alert
) {
    fun toFlattenedString(): String {
        val json = JSONObject()
        json.put("id", id)
        json.put("sender", sender)
        json.put("keyword", keyword)
        json.put("volume", volume.toDouble())
        json.put("overrideDnd", overrideDnd)
        json.put("vibration", vibration)
        json.put("soundName", soundName)
        json.put("playDurationSeconds", playDurationSeconds)
        json.put("vibrateOnly", vibrateOnly)
        json.put("cooldownMinutes", cooldownMinutes)
        json.put("lastTriggeredAt", lastTriggeredAt)
        
        val schedulesArray = JSONArray()
        activeSchedules.forEach { schedulesArray.put(it.toJson()) }
        json.put("activeSchedules", schedulesArray)
        
        return json.toString()
    }
    
    companion object {
        fun fromFlattenedString(s: String): AlertRule? {
            if (s.startsWith("{")) {
                // Try JSON parsing
                try {
                    val json = JSONObject(s)
                    val schedulesArray = json.optJSONArray("activeSchedules")
                    val schedules = mutableListOf<TimeWindow>()
                    if (schedulesArray != null) {
                        for (i in 0 until schedulesArray.length()) {
                            val scheduleJson = schedulesArray.optJSONObject(i)
                            if (scheduleJson != null) {
                                schedules.add(TimeWindow.fromJson(scheduleJson))
                            }
                        }
                    }
                    
                    return AlertRule(
                        id = json.optString("id", java.util.UUID.randomUUID().toString()),
                        sender = json.optString("sender", ""),
                        keyword = json.optString("keyword", ""),
                        volume = json.optDouble("volume", 1.0).toFloat(),
                        overrideDnd = json.optBoolean("overrideDnd", true),
                        vibration = json.optString("vibration", "Standard"),
                        soundName = json.optString("soundName", "Default Ringtone"),
                        playDurationSeconds = json.optInt("playDurationSeconds", -1),
                        vibrateOnly = json.optBoolean("vibrateOnly", false),
                        cooldownMinutes = json.optInt("cooldownMinutes", 0),
                        activeSchedules = schedules,
                        lastTriggeredAt = json.optLong("lastTriggeredAt", 0L)
                    )
                } catch (e: Exception) {
                    // Fallback to old parse if JSON fails somehow
                }
            }

            // Old Pipe-Delimited format (Backwards compatibility)
            val parts = s.split("|")
            if (parts.size < 6) return null
            return try {
                AlertRule(
                    id = parts[0],
                    sender = parts[1],
                    keyword = parts[2],
                    volume = parts[3].toFloat(),
                    overrideDnd = parts[4].toBoolean(),
                    vibration = parts[5],
                    soundName = if (parts.size > 6) parts[6] else "Default Ringtone",
                    playDurationSeconds = if (parts.size > 7) parts[7].toIntOrNull() ?: -1 else -1,
                    vibrateOnly = if (parts.size > 8) parts[8].toBoolean() else false
                )
            } catch (e: Exception) { null }
        }
    }
}
