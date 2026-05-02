package com.watchman.bridge

import android.content.Context
import android.util.Log
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

class WearableRepository(private val context: Context) {
    private val TAG = "WearableRepo"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    
    private val messageClient = Wearable.getMessageClient(context)
    private val nodeClient = Wearable.getNodeClient(context)
    private val dataClient = Wearable.getDataClient(context)

    fun updateData(path: String, update: (com.google.android.gms.wearable.PutDataMapRequest) -> Unit) {
        scope.launch {
            try {
                val request = com.google.android.gms.wearable.PutDataMapRequest.create(path)
                update(request)
                dataClient.putDataItem(request.asPutDataRequest()).await()
                Log.d(TAG, "Data updated: $path")
            } catch (e: Exception) {
                Log.e(TAG, "Data update failed: $path", e)
            }
        }
    }

    fun sendMessage(path: String, payload: ByteArray = ByteArray(0)) {
        scope.launch {
            try {
                val nodes = nodeClient.connectedNodes.await()
                nodes.forEach { node ->
                    messageClient.sendMessage(node.id, path, payload).await()
                    Log.d(TAG, "Sent $path to ${node.displayName}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send $path", e)
            }
        }
    }

    fun close() {
        scope.cancel()
    }
}
