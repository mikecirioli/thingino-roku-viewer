package com.speedwatcher.phone

import android.bluetooth.BluetoothDevice
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class AutoStartReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action ?: return
        @Suppress("DEPRECATION")
        val device: BluetoothDevice? = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
        
        val prefs = PreferencesManager(context)
        if (!prefs.isServiceEnabled || prefs.targetMacAddresses.isEmpty()) {
            return
        }

        if (prefs.targetMacAddresses.contains(device?.address)) {
            Log.d("SpeedWatcher", "Target BT device $action: ${device?.address}")
            if (action == BluetoothDevice.ACTION_ACL_CONNECTED) {
                val serviceIntent = Intent(context, SpeedTrackerService::class.java)
                context.startForegroundService(serviceIntent)
            } else if (action == BluetoothDevice.ACTION_ACL_DISCONNECTED) {
                val serviceIntent = Intent(context, SpeedTrackerService::class.java)
                context.stopService(serviceIntent)
            }
        }
    }
}
