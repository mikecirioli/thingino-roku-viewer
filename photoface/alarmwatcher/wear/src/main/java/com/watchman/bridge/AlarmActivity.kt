package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Bundle
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Snooze
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import android.view.InputDevice
import androidx.wear.compose.material3.*
import com.google.android.horologist.annotations.ExperimentalHorologistApi
import com.google.android.horologist.compose.layout.AppScaffold
import java.io.File

class AlarmActivity : ComponentActivity() {

    data class AlertItem(
        val key: String,
        val message: String,
        val soundFile: String?,
        val volume: Float,
        val dnd: Boolean,
        val duration: Int,
        val vibration: String,
        val vibrateOnly: Boolean,
        val timestamp: Long = System.currentTimeMillis()
    )

    private var mediaPlayer: MediaPlayer? = null
    private var ringtone: Ringtone? = null
    private var vibrator: Vibrator? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private lateinit var repository: WearableRepository
    private var originalDndFilter: Int? = null
    private var originalVolume: Int? = null
    private lateinit var audioManager: AudioManager
    private val TAG = "AlarmActivity"
    
    // Aggregator State
    private val activeAlerts = mutableStateListOf<AlertItem>()

    private val autoDismissHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val autoDismissRunnable = Runnable {
        Log.i(TAG, "Auto-dismissing alarm after duration elapsed")
        dismissAll()
    }

    private val finishReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            stopPlayback()
            finish()
        }
    }

    @OptIn(ExperimentalHorologistApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repository = WearableRepository(this)
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

        if (android.os.Build.VERSION.SDK_INT >= 33) {
            registerReceiver(finishReceiver, IntentFilter("com.watchman.bridge.FINISH_ALARM"), RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(finishReceiver, IntentFilter("com.watchman.bridge.FINISH_ALARM"))
        }

        setShowWhenLocked(true)
        setTurnScreenOn(true)

        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.SCREEN_BRIGHT_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP, "Watchman:WakeLock")
        wakeLock?.acquire(10 * 60 * 1000L)

        // Capture initial alert
        addAlertFromIntent(intent)
        updatePlayback()

        setContent {
            MaterialTheme {
                AppScaffold {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.Black),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                            modifier = Modifier.fillMaxSize().padding(24.dp)
                        ) {
                            // Message Display (Aggregator View)
                            Box(
                                modifier = Modifier.weight(1f),
                                contentAlignment = Alignment.Center
                            ) {
                                if (activeAlerts.size > 1) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text(
                                            text = "${activeAlerts.size} Alerts Active",
                                            style = MaterialTheme.typography.titleSmall,
                                            color = Color.Yellow,
                                            fontWeight = FontWeight.Bold
                                        )
                                        Spacer(modifier = Modifier.height(4.dp))
                                        Text(
                                            text = activeAlerts.lastOrNull()?.message ?: "",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = Color.White,
                                            textAlign = TextAlign.Center,
                                            maxLines = 3,
                                            modifier = Modifier.verticalScroll(rememberScrollState())
                                        )
                                    }
                                } else {
                                    Text(
                                        text = activeAlerts.firstOrNull()?.message ?: "ALARM!",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color.White,
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier.verticalScroll(rememberScrollState())
                                    )
                                }
                            }
                            
                            Spacer(modifier = Modifier.height(12.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceEvenly,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                // SNOOZE
                                Button(
                                    onClick = { snoozeAll() },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4CAF50)),
                                    modifier = Modifier.size(64.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Snooze,
                                        contentDescription = "Snooze",
                                        modifier = Modifier.size(32.dp),
                                        tint = Color.Black
                                    )
                                }

                                // DISMISS
                                Button(
                                    onClick = { dismissAll() },
                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF44336)),
                                    modifier = Modifier.size(64.dp)
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Close,
                                        contentDescription = "Stop",
                                        modifier = Modifier.size(32.dp),
                                        tint = Color.White
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onKeyDown(keyCode: Int, event: android.view.KeyEvent?): Boolean {
        return when (keyCode) {
            android.view.KeyEvent.KEYCODE_STEM_1 -> {
                dismissAll()
                true
            }
            android.view.KeyEvent.KEYCODE_NAVIGATE_NEXT, 
            android.view.KeyEvent.KEYCODE_NAVIGATE_PREVIOUS -> {
                snoozeAll()
                true
            }
            else -> super.onKeyDown(keyCode, event)
        }
    }

    override fun onGenericMotionEvent(event: android.view.MotionEvent?): Boolean {
        if (event?.action == android.view.MotionEvent.ACTION_SCROLL && 
            (event.source and android.view.InputDevice.SOURCE_ROTARY_ENCODER) == android.view.InputDevice.SOURCE_ROTARY_ENCODER) {
            snoozeAll()
            return true
        }
        return super.onGenericMotionEvent(event)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        addAlertFromIntent(intent)
        updatePlayback()
    }

    private fun addAlertFromIntent(intent: Intent) {
        val message = intent.getStringExtra("message") ?: "ALARM!"
        val key = intent.getStringExtra("key") ?: message
        
        // Prevent duplicate alerts with exact same key
        if (activeAlerts.any { it.key == key }) return

        val prefs = getSharedPreferences("WatchmanPrefs", Context.MODE_PRIVATE)
        
        activeAlerts.add(AlertItem(
            key = key,
            message = message,
            soundFile = intent.getStringExtra("sound_file"),
            volume = if (intent.hasExtra("rule_volume")) intent.getFloatExtra("rule_volume", 1.0f) else prefs.getFloat("alarm_volume", 1.0f),
            dnd = if (intent.hasExtra("rule_dnd")) intent.getBooleanExtra("rule_dnd", false) else prefs.getBoolean("dnd_override", false),
            duration = intent.getIntExtra("play_duration_seconds", -1),
            vibration = if (intent.hasExtra("rule_vibration_pattern")) intent.getStringExtra("rule_vibration_pattern") ?: "Standard" else prefs.getString("vibration_pattern", "Standard") ?: "Standard",
            vibrateOnly = if (intent.hasExtra("rule_vibrate_only")) intent.getBooleanExtra("rule_vibrate_only", false) else prefs.getBoolean("vibrate_only", false)
        ))
    }

    private fun updatePlayback() {
        Log.i(TAG, "Updating playback for ${activeAlerts.size} active alerts")
        if (activeAlerts.isEmpty()) {
            stopPlayback()
            finish()
            return
        }

        // 1. Determine "Winner" for settings
        // Highest volume wins
        val maxVolumeAlert = activeAlerts.maxBy { it.volume }
        // Any DND override wins
        val anyDndOverride = activeAlerts.any { it.dnd }
        // Any sound allowed wins (if all are vibrate only, then we stay silent)
        val allVibrateOnly = activeAlerts.all { it.vibrateOnly }

        // Apply DND
        if (anyDndOverride) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            if (nm.isNotificationPolicyAccessGranted && originalDndFilter == null) {
                originalDndFilter = nm.currentInterruptionFilter
                nm.setInterruptionFilter(android.app.NotificationManager.INTERRUPTION_FILTER_ALL)
            }
        }

        // Apply Volume
        if (originalVolume == null) {
            originalVolume = audioManager.getStreamVolume(AudioManager.STREAM_ALARM)
        }
        val maxStreamVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
        audioManager.setStreamVolume(AudioManager.STREAM_ALARM, (maxStreamVolume * maxVolumeAlert.volume).toInt(), 0)

        // Start/Update Sound
        if (!allVibrateOnly) {
            // Prefer the sound file of the highest-priority (loudest) alert
            val soundToPlay = maxVolumeAlert.soundFile ?: "custom_alarm.mp3"
            startSound(soundToPlay)
        } else {
            stopSoundOnly()
        }

        // Start Vibration
        // Use pattern of the loudest alert
        startVibration(maxVolumeAlert.vibration)

        // Handle Auto-Dismiss (use shortest duration > 0)
        autoDismissHandler.removeCallbacks(autoDismissRunnable)
        val shortestDuration = activeAlerts.filter { it.duration > 0 }.minByOrNull { it.duration }
        shortestDuration?.let {
            autoDismissHandler.postDelayed(autoDismissRunnable, it.duration * 1000L)
        }
    }

    private fun startSound(fileName: String) {
        // If already playing this file, do nothing
        if (mediaPlayer?.isPlaying == true || ringtone?.isPlaying == true) {
            // Note: In a more complex version we might check if fileName changed
            return 
        }

        val customFile = File(filesDir, fileName)
        if (customFile.exists()) {
            try {
                mediaPlayer?.stop()
                mediaPlayer?.release()
                mediaPlayer = MediaPlayer().apply {
                    setDataSource(customFile.absolutePath)
                    setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build())
                    isLooping = true
                    prepare()
                    start()
                }
            } catch (e: Exception) {
                playDefaultRingtone()
            }
        } else {
            playDefaultRingtone()
        }
    }

    private fun playDefaultRingtone() {
        if (ringtone?.isPlaying == true) return
        val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM) ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
        ringtone = RingtoneManager.getRingtone(applicationContext, uri)
        ringtone?.audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build()
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            ringtone?.isLooping = true
        }
        ringtone?.play()
    }

    private fun startVibration(patternName: String) {
        vibrator?.cancel()
        vibrator = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S) {
            (getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as android.os.VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION") getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        if (vibrator?.hasVibrator() == true) {
            val pattern = when (patternName) {
                "Heartbeat" -> longArrayOf(0, 200, 200, 200, 800)
                "Rapid" -> longArrayOf(0, 150, 100, 150, 100)
                else -> longArrayOf(0, 1000, 500, 1000, 500)
            }
            vibrator?.vibrate(VibrationEffect.createWaveform(pattern, 0))
        }
    }

    private fun snoozeAll() {
        repository.sendMessage(WatchmanPaths.SNOOZE_ALARM)
        stopPlayback()
        finish()
    }

    private fun dismissAll() {
        // Send dismissal for any active critical notifications
        activeAlerts.forEach {
            repository.sendMessage(WatchmanPaths.DISMISS_NOTIFICATION, it.key.toByteArray())
        }
        // Also send the generic dismiss for any potential stock alarm
        repository.sendMessage(WatchmanPaths.DISMISS_ALARM)
        stopPlayback()
        finish()
    }

    private fun stopSoundOnly() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
        ringtone?.stop()
        ringtone = null
    }

    private fun stopPlayback() {
        autoDismissHandler.removeCallbacks(autoDismissRunnable)
        stopSoundOnly()
        vibrator?.cancel()
        
        originalVolume?.let { audioManager.setStreamVolume(AudioManager.STREAM_ALARM, it, 0) }
        originalDndFilter?.let { 
            (getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager).setInterruptionFilter(it)
        }
        
        if (wakeLock?.isHeld == true) wakeLock?.release()
        activeAlerts.clear()
    }

    override fun onDestroy() {
        super.onDestroy()
        try { unregisterReceiver(finishReceiver) } catch (e: Exception) {}
        stopPlayback()
        repository.close()
    }
}
