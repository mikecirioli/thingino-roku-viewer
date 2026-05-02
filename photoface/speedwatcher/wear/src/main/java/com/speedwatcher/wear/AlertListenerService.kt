package com.speedwatcher.wear

import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService
import com.speedwatcher.shared.SpeedWatcherPaths
import org.json.JSONObject

class AlertListenerService : WearableListenerService() {

    override fun onMessageReceived(messageEvent: MessageEvent) {
        if (messageEvent.path == SpeedWatcherPaths.SPEED_ALERT) {
            Log.w("SpeedWatcherWear", "Received speed alert! Vibrating...")
            
            var patternName = "Rapid"
            var power = 255
            
            try {
                if (messageEvent.data.isNotEmpty()) {
                    val payloadString = String(messageEvent.data, Charsets.UTF_8)
                    val json = JSONObject(payloadString)
                    patternName = json.optString("pattern", "Rapid")
                    power = json.optInt("power", 255)
                }
            } catch (e: Exception) {
                Log.e("SpeedWatcherWear", "Failed to parse payload", e)
            }
            
            triggerHapticAlert(patternName, power)
        } else {
            super.onMessageReceived(messageEvent)
        }
    }

    private fun triggerHapticAlert(patternName: String, power: Int) {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vibratorManager = getSystemService(VibratorManager::class.java)
            vibratorManager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(VIBRATOR_SERVICE) as Vibrator
        }

        val timings: LongArray
        val amplitudes: IntArray
        
        when (patternName) {
            "Standard" -> {
                timings = longArrayOf(0, 300)
                amplitudes = intArrayOf(0, power)
            }
            "Heartbeat" -> {
                timings = longArrayOf(0, 100, 100, 100)
                amplitudes = intArrayOf(0, power, 0, power)
            }
            "Rapid" -> {
                timings = longArrayOf(0, 100, 100, 100, 100, 100)
                amplitudes = intArrayOf(0, power, 0, power, 0, power)
            }
            else -> {
                timings = longArrayOf(0, 100, 100, 100, 100, 100)
                amplitudes = intArrayOf(0, power, 0, power, 0, power)
            }
        }

        if (vibrator.hasAmplitudeControl()) {
            val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
            vibrator.vibrate(effect)
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(timings, -1)
        }
    }
}
