package com.speedwatcher.phone

import android.content.Context
import android.util.Log
import com.google.android.gms.wearable.Wearable
import com.speedwatcher.shared.SpeedWatcherPaths
import kotlinx.coroutines.tasks.await

class WearMessenger(context: Context) {
    private val messageClient = Wearable.getMessageClient(context)
    private val nodeClient = Wearable.getNodeClient(context)

    suspend fun sendSpeedAlert(pattern: String, power: Int) {
        try {
            val payloadString = """{"pattern":"$pattern","power":$power}"""
            val payloadBytes = payloadString.toByteArray(Charsets.UTF_8)
            
            val nodes = nodeClient.connectedNodes.await()
            for (node in nodes) {
                messageClient.sendMessage(
                    node.id,
                    SpeedWatcherPaths.SPEED_ALERT,
                    payloadBytes
                ).await()
                Log.d("SpeedWatcher", "Alert sent to node: ${node.id} with $payloadString")
            }
        } catch (e: Exception) {
            Log.e("SpeedWatcher", "Failed to send alert to watch", e)
        }
    }
}
