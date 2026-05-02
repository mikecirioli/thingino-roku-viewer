package com.watchman.bridge

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.watchman.bridge.shared.WatchmanPaths

class FakeNotificationListenerService : NotificationListenerService() {
    private lateinit var repository: WearableRepository

    override fun onCreate() {
        super.onCreate()
        repository = WearableRepository(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        repository.close()
    }

    // This service also syncs DND back to the phone
    override fun onInterruptionFilterChanged(interruptionFilter: Int) {
        repository.updateData(WatchmanPaths.DND_STATE) {
            it.dataMap.putInt("filter", interruptionFilter)
            it.dataMap.putLong("timestamp", System.currentTimeMillis())
            // Indicate source is watch to avoid infinite loop
            it.dataMap.putBoolean("from_watch", true)
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {}
    override fun onNotificationRemoved(sbn: StatusBarNotification?) {}
}