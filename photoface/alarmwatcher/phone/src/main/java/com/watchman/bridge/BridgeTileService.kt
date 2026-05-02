package com.watchman.bridge

import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.text.format.DateUtils
import com.watchman.bridge.data.SharedPrefsSettingsRepository

class BridgeTileService : TileService() {

    private lateinit var settingsRepository: SharedPrefsSettingsRepository
    private val handler = Handler(Looper.getMainLooper())
    private var isListening = false

    private val updateRunnable = object : Runnable {
        override fun run() {
            if (isListening) {
                updateTile()
                handler.postDelayed(this, 1000) // Update every second to show countdown
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        settingsRepository = SharedPrefsSettingsRepository(this)
    }

    override fun onStartListening() {
        isListening = true
        handler.post(updateRunnable)
    }

    override fun onStopListening() {
        isListening = false
        handler.removeCallbacks(updateRunnable)
    }

    override fun onClick() {
        val isEnabled = settingsRepository.isServiceGloballyEnabled()
        if (!isEnabled) {
            settingsRepository.setServiceGloballyEnabled(true)
            settingsRepository.setSnoozeUntil(0L) // Clear any old snooze
        } else {
            val intent = Intent(this, SnoozeActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivityAndCollapse(intent)
        }
        updateTile()
    }

    private fun updateTile() {
        val tile = qsTile ?: return
        val isEnabled = settingsRepository.isServiceGloballyEnabled()
        val snoozeUntil = settingsRepository.getSnoozeUntil()
        val isSnoozed = snoozeUntil > System.currentTimeMillis()

        if (!isEnabled) {
            tile.state = Tile.STATE_INACTIVE
            tile.label = "Bridge Off"
            tile.subtitle = "Tap to enable"
        } else if (isSnoozed) {
            tile.state = Tile.STATE_UNAVAILABLE
            tile.label = "Snoozed"
            val remaining = snoozeUntil - System.currentTimeMillis()
            tile.subtitle = "Ends in ${DateUtils.formatElapsedTime(remaining / 1000)}"
        } else {
            tile.state = Tile.STATE_ACTIVE
            tile.label = "Bridge Active"
            tile.subtitle = "Tap to snooze"
        }
        tile.updateTile()
    }
}
