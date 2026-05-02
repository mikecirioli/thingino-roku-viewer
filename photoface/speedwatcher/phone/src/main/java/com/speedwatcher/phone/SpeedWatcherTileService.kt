package com.speedwatcher.phone

import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.util.Log

class SpeedWatcherTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        updateTileState()
    }

    override fun onClick() {
        super.onClick()
        val prefs = PreferencesManager(this)
        val currentState = prefs.isServiceEnabled
        
        // Toggle the state
        val newState = !currentState
        prefs.isServiceEnabled = newState
        
        Log.d("SpeedWatcherTile", "Tile clicked. New state: \$newState")
        
        // Update the tile UI
        updateTileState()
        
        // If the service is currently running and we just turned it off, we should probably stop it.
        // However, the service only runs when connected to Bluetooth. 
        // If we want to actively stop it right now if it's running:
        if (!newState) {
            val serviceIntent = Intent(this, SpeedTrackerService::class.java)
            stopService(serviceIntent)
        }
    }

    private fun updateTileState() {
        val tile = qsTile ?: return
        val prefs = PreferencesManager(this)
        
        if (prefs.isServiceEnabled) {
            tile.state = Tile.STATE_ACTIVE
            tile.label = "SpeedWatcher (ON)"
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                tile.subtitle = "Monitoring enabled"
            }
        } else {
            tile.state = Tile.STATE_INACTIVE
            tile.label = "SpeedWatcher (OFF)"
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                tile.subtitle = "Monitoring disabled"
            }
        }
        tile.updateTile()
    }
}
