package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths

import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.ChannelClient
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import java.io.File

import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.watchman.bridge.data.SharedPrefsWearSettingsRepository
import com.watchman.bridge.data.WearSettingsRepository

class WatchListenerService : WearableListenerService() {

    private val TAG = "WatchListener"
    private lateinit var repository: WearSettingsRepository
    private lateinit var processor: WatchEventProcessor

    override fun onCreate() {
        super.onCreate()
        repository = SharedPrefsWearSettingsRepository(this)
        processor = WatchEventProcessor(
            repository = repository,
            startActivityCallback = { key, soundFile, message, volume, dnd, playDurationSeconds, vibrationPattern, vibrateOnly ->
                val intent = Intent(this, AlarmActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    key?.let { putExtra("key", it) }
                    soundFile?.let { putExtra("sound_file", it) }
                    message?.let { putExtra("message", it) }
                    volume?.let { putExtra("rule_volume", it) }
                    dnd?.let { putExtra("rule_dnd", it) }
                    playDurationSeconds?.let { putExtra("play_duration_seconds", it) }
                    vibrationPattern?.let { putExtra("rule_vibration_pattern", it) }
                    vibrateOnly?.let { putExtra("rule_vibrate_only", it) }
                }
                startActivity(intent)
            },
            sendBroadcastCallback = { action ->
                sendBroadcast(Intent(action))
            }
        )
    }

    override fun onDataChanged(dataEvents: DataEventBuffer) {
        dataEvents.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED) {
                Log.d(TAG, "Data changed from node: ${event.dataItem.uri.host}")
                
                val item = DataMapItem.fromDataItem(event.dataItem)
                when (event.dataItem.uri.path) {
                    WatchmanPaths.DND_STATE -> {
                        val fromWatch = item.dataMap.getBoolean("from_watch", false)
                        if (!fromWatch) {
                            processor.processDndState(item.dataMap.getInt("filter"))
                        }
                    }
                    WatchmanPaths.DND_OVERRIDE_PREF -> {
                        processor.processDndOverride(item.dataMap.getBoolean("enabled"))
                    }
                    WatchmanPaths.ALARM_VOLUME_PREF -> {
                        processor.processAlarmVolume(item.dataMap.getFloat("volume"))
                    }
                    WatchmanPaths.NEXT_ALARM_STATE -> {
                        processor.processNextAlarmTime(item.dataMap.getLong("timestamp"))
                    }
                    WatchmanPaths.VIBRATION_PATTERN -> {
                        if (item.dataMap.containsKey("pattern_name")) {
                            processor.processVibrationPattern(item.dataMap.getString("pattern_name"))
                        }
                        if (item.dataMap.containsKey("vibrate_only")) {
                            processor.processVibrateOnly(item.dataMap.getBoolean("vibrate_only"))
                        }
                    }
                }
            }
        }
    }

    override fun onChannelOpened(channel: ChannelClient.Channel) {
        if (channel.path.startsWith(WatchmanPaths.RULE_SOUND_FILE)) {
            val fileName = channel.path.substringAfterLast("/")
            val file = File(filesDir, fileName)
            Wearable.getChannelClient(this).receiveFile(channel, android.net.Uri.fromFile(file), false)
        } else if (channel.path == WatchmanPaths.CUSTOM_SOUND_FILE) {
            val file = File(filesDir, "custom_alarm.mp3")
            Wearable.getChannelClient(this).receiveFile(channel, android.net.Uri.fromFile(file), false)
        }
    }

    override fun onInputClosed(channel: ChannelClient.Channel, closeReason: Int, appSpecificErrorCode: Int) {
        Log.i(TAG, "Input closed for channel: ${channel.path}")
    }

    override fun onMessageReceived(messageEvent: MessageEvent) {
        Log.d(TAG, "Message received: ${messageEvent.path} from ${messageEvent.sourceNodeId}")
        when (messageEvent.path) {
            WatchmanPaths.START_ALARM -> {
                Log.i(TAG, "Processing START_ALARM")
                processor.processStartAlarm()
            }
            WatchmanPaths.STOP_ALARM -> {
                Log.i(TAG, "Processing STOP_ALARM")
                processor.processStopAlarm()
            }
            WatchmanPaths.CRITICAL_ALERT -> {
                val payload = String(messageEvent.data, Charsets.UTF_8)
                Log.i(TAG, "Processing CRITICAL_ALERT with payload: $payload")
                processor.processCriticalAlert(payload)
            }
            else -> {
                Log.w(TAG, "Unknown message path: ${messageEvent.path}")
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
    }
}
