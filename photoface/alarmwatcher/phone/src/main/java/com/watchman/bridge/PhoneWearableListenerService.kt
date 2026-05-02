package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths

import android.content.Context
import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService

class PhoneWearableListenerService : WearableListenerService() {

    private val TAG = "PhoneWearListener"

    override fun onDataChanged(dataEvents: DataEventBuffer) {
        dataEvents.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED) {
                val item = DataMapItem.fromDataItem(event.dataItem)
                when (event.dataItem.uri.path) {
                    WatchmanPaths.DND_STATE -> {
                        val fromWatch = item.dataMap.getBoolean("from_watch", false)
                        if (fromWatch) {
                            val filter = item.dataMap.getInt("filter")
                            Log.i(TAG, "Received DND state from watch: filter=$filter")
                            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
                            if (nm.isNotificationPolicyAccessGranted) {
                                if (nm.currentInterruptionFilter != filter) {
                                    nm.setInterruptionFilter(filter)
                                }
                            } else {
                                Log.w(TAG, "Cannot sync DND from watch: Notification Policy Access not granted on phone")
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onMessageReceived(messageEvent: MessageEvent) {
        Log.d(TAG, "Message received: ${messageEvent.path}")
        when (messageEvent.path) {
            WatchmanPaths.SNOOZE_ALARM -> {
                // We need to communicate with the NotificationListenerService
                // The easiest way is via a broadcast or a shared singleton
                val intent = Intent("com.watchman.bridge.REMOTE_COMMAND").apply {
                    putExtra("command", WatchmanPaths.SNOOZE_ALARM)
                    setPackage(packageName) // Crucial for Android 14+ with RECEIVER_NOT_EXPORTED
                }
                sendBroadcast(intent)
            }
            WatchmanPaths.DISMISS_ALARM -> {
                val intent = Intent("com.watchman.bridge.REMOTE_COMMAND").apply {
                    putExtra("command", WatchmanPaths.DISMISS_ALARM)
                    setPackage(packageName) // Crucial for Android 14+ with RECEIVER_NOT_EXPORTED
                }
                sendBroadcast(intent)
            }
            WatchmanPaths.DISMISS_NOTIFICATION -> {
                val key = String(messageEvent.data)
                val intent = Intent("com.watchman.bridge.REMOTE_COMMAND").apply {
                    putExtra("command", "DISMISS_NOTIFICATION")
                    putExtra("notification_key", key)
                    setPackage(packageName)
                }
                sendBroadcast(intent)
            }
            WatchmanPaths.OPEN_PHONE_APP -> {
                val vibrator = getSystemService(android.os.Vibrator::class.java)
                vibrator?.vibrate(android.os.VibrationEffect.createOneShot(50, android.os.VibrationEffect.DEFAULT_AMPLITUDE))

                val intent = Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                }
                startActivity(intent)
                Log.i(TAG, "Launching MainActivity from watch command")
            }
        }
    }
}
