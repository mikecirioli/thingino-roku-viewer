package com.watchman.bridge.shared.data

import org.json.JSONArray
import org.json.JSONObject

data class TimeWindow(
    val startHour: Int,
    val startMinute: Int,
    val endHour: Int,
    val endMinute: Int,
    val daysOfWeek: List<Int>, // 1 = Sunday, 2 = Monday, ..., 7 = Saturday (java.util.Calendar style)
    val isBlackout: Boolean = false
) {
    fun toJson(): JSONObject {
        val json = JSONObject()
        json.put("startHour", startHour)
        json.put("startMinute", startMinute)
        json.put("endHour", endHour)
        json.put("endMinute", endMinute)
        
        val daysArray = JSONArray()
        daysOfWeek.forEach { daysArray.put(it) }
        json.put("daysOfWeek", daysArray)
        
        json.put("isBlackout", isBlackout)
        return json
    }

    companion object {
        fun fromJson(json: JSONObject): TimeWindow {
            val daysArray = json.optJSONArray("daysOfWeek")
            val days = mutableListOf<Int>()
            if (daysArray != null) {
                for (i in 0 until daysArray.length()) {
                    days.add(daysArray.getInt(i))
                }
            }
            return TimeWindow(
                startHour = json.optInt("startHour", 0),
                startMinute = json.optInt("startMinute", 0),
                endHour = json.optInt("endHour", 23),
                endMinute = json.optInt("endMinute", 59),
                daysOfWeek = days,
                isBlackout = json.optBoolean("isBlackout", false)
            )
        }
    }
}
