package com.speedwatcher.phone

import android.content.Context
import android.os.BatteryManager
import android.util.Log
import java.io.File
import java.io.FileWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object MetricsLogger {
    private var logFile: File? = null
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)

    fun initialize(context: Context) {
        val dir = File(context.getExternalFilesDir(null), "logs")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        logFile = File(dir, "speedwatcher_metrics.csv")
        
        if (!logFile!!.exists()) {
            try {
                FileWriter(logFile, true).use { writer ->
                    writer.append("Timestamp,Event,Speed_MPH,Distance_Moved_m,Time_Elapsed_s,Threshold_Distance_m,API_Limit_MPH,Battery_Level\n")
                }
            } catch (e: Exception) {
                Log.e("MetricsLogger", "Failed to create log file", e)
            }
        }
    }

    fun logEvent(
        context: Context,
        event: String,
        speedMph: Float,
        distanceMoved: Float,
        timeElapsedSec: Float,
        thresholdDistance: Float,
        apiLimit: Int?
    ) {
        if (logFile == null) return

        // Cap log file size at 2MB (2 * 1024 * 1024 bytes)
        if (logFile!!.exists() && logFile!!.length() > 2 * 1024 * 1024) {
            logFile!!.delete()
            try {
                FileWriter(logFile, true).use { writer ->
                    writer.append("Timestamp,Event,Speed_MPH,Distance_Moved_m,Time_Elapsed_s,Threshold_Distance_m,API_Limit_MPH,Battery_Level\n")
                }
            } catch (e: Exception) {
                Log.e("MetricsLogger", "Failed to recreate log file header", e)
            }
        }

        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val batteryLevel = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val timestamp = dateFormat.format(Date())
        
        val limitStr = apiLimit?.toString() ?: "NULL"

        val logLine = String.format(
            Locale.US,
            "%s,%s,%.1f,%.1f,%.1f,%.1f,%s,%d\n",
            timestamp, event, speedMph, distanceMoved, timeElapsedSec, thresholdDistance, limitStr, batteryLevel
        )

        try {
            FileWriter(logFile, true).use { writer ->
                writer.append(logLine)
            }
        } catch (e: Exception) {
            Log.e("MetricsLogger", "Failed to write to log file", e)
        }
    }
}
