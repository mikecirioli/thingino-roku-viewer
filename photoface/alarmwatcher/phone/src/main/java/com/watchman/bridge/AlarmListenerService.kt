package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths
import com.watchman.bridge.shared.data.AlertRule
import com.watchman.bridge.shared.data.TimeWindow

import android.app.AlarmManager
import android.app.Notification
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.google.android.gms.wearable.Wearable
import com.watchman.bridge.data.SettingsRepository
import com.watchman.bridge.data.SharedPrefsSettingsRepository

class AlarmListenerService : NotificationListenerService() {

    private val TAG = "AlarmListenerService"
    private lateinit var repository: WearableRepository
    private lateinit var trialManager: TrialManager
    private lateinit var settingsRepository: SettingsRepository // New dependency

    private var activeSnoozeIntent: PendingIntent? = null
    private var activeDismissIntent: PendingIntent? = null

    private var lastGlobalAlertTimestamp: Long = 0
    private val processedNotificationKeys = mutableSetOf<String>()


    private val alarmChangeReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (trialManager.isTrialActive()) syncNextAlarm()
        }
    }

    private val remoteCommandReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val command = intent?.getStringExtra("command")
            Log.d(TAG, "Remote command received: $command")
            when (command) {
                WatchmanPaths.SNOOZE_ALARM -> {
                    activeSnoozeIntent?.send()
                    clearActiveIntents()
                }
                WatchmanPaths.DISMISS_ALARM -> {
                    activeDismissIntent?.send()
                    clearActiveIntents()
                }
                "DISMISS_NOTIFICATION" -> {
                    val key = intent.getStringExtra("notification_key")
                    if (key != null) {
                        cancelNotification(key)
                        processedNotificationKeys.remove(key)
                        Log.d(TAG, "Remotely dismissed notification with key: $key")
                    }
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        repository = WearableRepository(this)
        settingsRepository = SharedPrefsSettingsRepository(applicationContext) // Initialize settings repository
        trialManager = TrialManager(settingsRepository) // Pass settings repository to TrialManager

        val isReliabilityMode = settingsRepository.isHighReliabilityEnabled() // Use settingsRepository
        if (isReliabilityMode) startHighReliabilityMode()

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(alarmChangeReceiver, IntentFilter(AlarmManager.ACTION_NEXT_ALARM_CLOCK_CHANGED), Context.RECEIVER_EXPORTED)
            registerReceiver(remoteCommandReceiver, IntentFilter("com.watchman.bridge.REMOTE_COMMAND"), Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(alarmChangeReceiver, IntentFilter(AlarmManager.ACTION_NEXT_ALARM_CLOCK_CHANGED))
            registerReceiver(remoteCommandReceiver, IntentFilter("com.watchman.bridge.REMOTE_COMMAND"))
        }

        if (trialManager.isTrialActive()) {
            syncNextAlarm()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        unregisterReceiver(alarmChangeReceiver)
        unregisterReceiver(remoteCommandReceiver)
        repository.close()
    }

    private fun startHighReliabilityMode() {
        val channelId = "watchman_reliability"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val channel = android.app.NotificationChannel(channelId, "Service Reliability", android.app.NotificationManager.IMPORTANCE_LOW)
            nm.createNotificationChannel(channel)
        }

        val notification = android.app.Notification.Builder(this, channelId)
            .setContentTitle("Watchman Bridge Active")
            .setContentText("High reliability mode is keeping the connection alive.")
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setOngoing(true)
            .build()

        startForeground(1001, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val command = intent?.getStringExtra("action")
        if (command == "START_RELIABILITY") startHighReliabilityMode()
        else if (command == "STOP_RELIABILITY") stopForeground(STOP_FOREGROUND_REMOVE)

        return super.onStartCommand(intent, flags, startId)
    }

    private fun syncNextAlarm() {
        val alarmManager = getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val timestamp = alarmManager.nextAlarmClock?.triggerTime ?: 0L
        repository.updateData(WatchmanPaths.NEXT_ALARM_STATE) {
            it.dataMap.putLong("timestamp", timestamp)
            it.dataMap.putLong("updated_at", System.currentTimeMillis())
        }
    }

    private fun clearActiveIntents() {
        activeSnoozeIntent = null
        activeDismissIntent = null
        repository.sendMessage(WatchmanPaths.STOP_ALARM)
    }

    override fun onInterruptionFilterChanged(interruptionFilter: Int) {
        if (trialManager.isTrialActive()) {
            repository.updateData(WatchmanPaths.DND_STATE) {
                it.dataMap.putInt("filter", interruptionFilter)
                it.dataMap.putLong("timestamp", System.currentTimeMillis())
            }
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        processedNotificationKeys.remove(sbn.key)
        if (isClockPackage(sbn.packageName)) {
            clearActiveIntents()
        }
    }

    private fun notifyTrialExpired() {
        // Prevent spamming the user on every single notification if it's not a critical rule
        // We will throttle this by storing the last notification time in a quick preference, or just relying on the system to de-dupe identical notifications
        val channelId = "watchman_trial"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val channel = android.app.NotificationChannel(
                channelId,
                "Trial Status",
                android.app.NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Alerts about trial expiration and account status"
            }
            nm.createNotificationChannel(channel)
        }

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)

        val notification = android.app.Notification.Builder(this, channelId)
            .setContentTitle("Watchman Bridge Trial Expired")
            .setContentText("Alarms and alerts are no longer syncing to your watch. Tap to unlock lifetime access.")
            .setSmallIcon(android.R.drawable.ic_dialog_alert) // Built-in warning icon
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        nm.notify(1002, notification)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!settingsRepository.isServiceGloballyEnabled()) {
            Log.d(TAG, "Service is globally disabled. Ignoring notification.")
            return
        }

        val snoozeUntil = settingsRepository.getSnoozeUntil()
        if (snoozeUntil > System.currentTimeMillis()) {
            Log.d(TAG, "Service is snoozed. Ignoring notification.")
            return
        }

        if (processedNotificationKeys.contains(sbn.key)) {
            Log.d(TAG, "Ignoring already processed notification: ${sbn.key}")
            return
        }

        val packageName = sbn.packageName
        val notification = sbn.notification

        val isAlarmPackage = isClockPackage(packageName)
        val isAlarmCategory = notification.category == Notification.CATEGORY_ALARM
        val isRinging = notification.fullScreenIntent != null || sbn.isOngoing

        if (isAlarmCategory && isRinging && isAlarmPackage) {
            if (!trialManager.isTrialActive()) {
                Log.w(TAG, "Trial expired. Suppressing alarm bridge.")
                notifyTrialExpired()
                return
            }

            notification.actions?.forEach { action ->
                val title = action.title.toString().lowercase()
                val semanticAction = action.semanticAction
                val intentAction = ""

                val isSnooze = semanticAction == Notification.Action.SEMANTIC_ACTION_MUTE ||
                               title.contains("snooze") || title.contains("later") || title.contains("repeat")

                val isDismiss = semanticAction == Notification.Action.SEMANTIC_ACTION_ARCHIVE ||
                                semanticAction == Notification.Action.SEMANTIC_ACTION_MARK_AS_READ ||
                                title.contains("dismiss") || title.contains("stop") || title.contains("off") || title.contains("close") || title.contains("done")

                if (isSnooze) {
                    activeSnoozeIntent = action.actionIntent
                    Log.d(TAG, "Captured SNOOZE intent from: $title")
                } else if (isDismiss) {
                    activeDismissIntent = action.actionIntent
                    Log.d(TAG, "Captured DISMISS intent from: $title")
                }
            }
            repository.sendMessage(WatchmanPaths.START_ALARM)
            return
        }

        // Rule Matching Engine

        // Skip ongoing notifications to prevent constant alerting from call timers, media players, or navigation
        if (sbn.isOngoing) {
            return
        }

        val isGlobalCatchAll = settingsRepository.isGlobalCatchAllEnabled() // Use settingsRepository
        val rules = settingsRepository.getAlertRules() // Use settingsRepository

        val title = notification.extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()
            ?: notification.tickerText?.toString() ?: ""
        val text = notification.extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""
        val bigText = notification.extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString() ?: ""
        val summaryText = notification.extras.getCharSequence(Notification.EXTRA_SUMMARY_TEXT)?.toString() ?: ""

        val contentCombined = "$title $text $bigText $summaryText".lowercase()

        // 0. Check Global Quiet Hours
        val globalSchedules = settingsRepository.getGlobalQuietHours()
        if (!isScheduleActive(globalSchedules)) {
            Log.d(TAG, "Notification suppressed by Global Quiet Hours.")
            return
        }

        // Guard rules with Trial
        if (!trialManager.isTrialActive()) {
            val isRuleMatch = isGlobalCatchAll || rules.any { rule ->
                (rule.sender.isEmpty() || title.lowercase().contains(rule.sender.lowercase())) &&
                (rule.keyword.isEmpty() || contentCombined.contains(rule.keyword.lowercase())) &&
                (rule.sender.isNotEmpty() || rule.keyword.isNotEmpty())
            }
            if (isRuleMatch) {
                Log.w(TAG, "Trial expired. Suppressing critical alert.")
                notifyTrialExpired()
            }
            return
        }

        // Sanitize to prevent pipe character breaking our data layer payload
        val safeTitle = title.replace("|", "-")
        val safeText = text.replace("|", "-")

        // 1. Check Global Catch-all first
        if (isGlobalCatchAll) {
            val now = System.currentTimeMillis()
            if (now - lastGlobalAlertTimestamp < 10000) { // 10-second cooldown
                Log.d(TAG, "Global Catch-all suppressed by cooldown.")
                return
            }
            lastGlobalAlertTimestamp = now
            processedNotificationKeys.add(sbn.key)

            Log.i(TAG, "Global Catch-all Match! Sending alert for key: ${sbn.key}")
            val payload = org.json.JSONObject()
            payload.put("key", sbn.key) // Include the key for remote dismissal
            payload.put("message", "$safeTitle: $safeText")
            payload.put("volume", settingsRepository.getAlarmVolume().toDouble())
            payload.put("overrideDnd", settingsRepository.isDndOverrideEnabled())
            payload.put("soundFile", "custom_alarm.mp3")
            payload.put("playDurationSeconds", -1)
            payload.put("vibrationPattern", settingsRepository.getGlobalVibrationPattern())
            payload.put("vibrateOnly", settingsRepository.isGlobalVibrateOnly())
            repository.sendMessage(WatchmanPaths.CRITICAL_ALERT, payload.toString().toByteArray())
            return
        }

        // 2. Check Specific Rules
        rules.forEach { rule ->
            val senderMatch = rule.sender.isEmpty() || title.lowercase().contains(rule.sender.lowercase())
            val keywordMatch = rule.keyword.isEmpty() || contentCombined.contains(rule.keyword.lowercase())

            if (senderMatch && keywordMatch && (rule.sender.isNotEmpty() || rule.keyword.isNotEmpty())) {
                if (!isScheduleActive(rule.activeSchedules)) {
                    Log.d(TAG, "Rule '${rule.id}' matched but is outside active schedule or inside blackout.")
                    return@forEach
                }

                if (isCooldownActive(rule)) {
                    Log.d(TAG, "Rule '${rule.id}' matched but is in cooldown period.")
                    return@forEach
                }

                Log.i(TAG, "Rule Match! Sending specific alert.")

                // Update rule's lastTriggeredAt timestamp and save it back
                rule.lastTriggeredAt = System.currentTimeMillis()
                settingsRepository.saveAlertRule(rule)
                processedNotificationKeys.add(sbn.key)

                val watchFileName = "rule_${rule.soundName.replace("[^a-zA-Z0-9.-]".toRegex(), "_")}"

                val payload = org.json.JSONObject()
                payload.put("key", sbn.key) // Include the key for remote dismissal
                payload.put("message", "$safeTitle: $safeText")
                payload.put("volume", rule.volume.toDouble())
                payload.put("overrideDnd", rule.overrideDnd)
                payload.put("soundFile", watchFileName)
                payload.put("playDurationSeconds", rule.playDurationSeconds)
                payload.put("vibrationPattern", rule.vibration)
                payload.put("vibrateOnly", rule.vibrateOnly)

                repository.sendMessage(WatchmanPaths.CRITICAL_ALERT, payload.toString().toByteArray())
                return
            }
        }
    }

    private fun isScheduleActive(schedules: List<com.watchman.bridge.shared.data.TimeWindow>): Boolean {
        if (schedules.isEmpty()) return true

        val calendar = java.util.Calendar.getInstance()
        val currentDay = calendar.get(java.util.Calendar.DAY_OF_WEEK)
        val currentHour = calendar.get(java.util.Calendar.HOUR_OF_DAY)
        val currentMinute = calendar.get(java.util.Calendar.MINUTE)
        val currentTotalMinutes = currentHour * 60 + currentMinute

        var insideAnyActiveWindow = false
        var insideAnyBlackoutWindow = false

        for (window in schedules) {
            if (!window.daysOfWeek.contains(currentDay)) continue

            val startTotal = window.startHour * 60 + window.startMinute
            val endTotal = window.endHour * 60 + window.endMinute
            
            val isInsideTime = if (startTotal <= endTotal) {
                currentTotalMinutes in startTotal..endTotal
            } else {
                currentTotalMinutes >= startTotal || currentTotalMinutes <= endTotal
            }

            if (isInsideTime) {
                if (window.isBlackout) insideAnyBlackoutWindow = true
                else insideAnyActiveWindow = true
            }
        }
        
        if (insideAnyBlackoutWindow) return false
        if (insideAnyActiveWindow) return true
        
        val hasOnlyBlackouts = schedules.all { it.isBlackout }
        return hasOnlyBlackouts
    }

    private fun isCooldownActive(rule: com.watchman.bridge.shared.data.AlertRule): Boolean {
        if (rule.cooldownMinutes <= 0) return false
        val now = System.currentTimeMillis()
        val cooldownMillis = rule.cooldownMinutes * 60 * 1000L
        return (now - rule.lastTriggeredAt) < cooldownMillis
    }

    private fun isClockPackage(pkg: String): Boolean {
        return pkg.contains("deskclock") || 
               pkg.contains("alarm") || 
               pkg == "com.sec.android.app.clock" || // Samsung
               pkg == "com.samsung.android.app.clockpack" || // Samsung LockScreen/AOD Alarms
               pkg == "com.oneplus.deskclock" ||    // OnePlus
               pkg == "com.miui.notes" ||           // Xiaomi Notes/Alerts
               pkg == "com.android.settings"        // Some system alerts
    }
}
