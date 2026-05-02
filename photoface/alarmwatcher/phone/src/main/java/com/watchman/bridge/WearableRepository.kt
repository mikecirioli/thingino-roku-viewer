package com.watchman.bridge

import android.content.Context
import android.net.Uri
import android.util.Log
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext

class WearableRepository(private val context: Context) {
    private val TAG = "WearableRepo"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    
    private val messageClient = Wearable.getMessageClient(context)
    private val nodeClient = Wearable.getNodeClient(context)
    private val capabilityClient = Wearable.getCapabilityClient(context)
    private val channelClient = Wearable.getChannelClient(context)
    private val dataClient = Wearable.getDataClient(context)

    private val WEAR_CAPABILITY = "watchman_bridge_wear_app"

    fun updateData(path: String, update: (PutDataMapRequest) -> Unit) {
        scope.launch {
            try {
                val request = PutDataMapRequest.create(path)
                update(request)
                dataClient.putDataItem(request.asPutDataRequest()).await()
                Log.d(TAG, "Data updated: $path")
            } catch (e: Exception) {
                Log.e(TAG, "Data update failed: $path", e)
            }
        }
    }

    private suspend fun getTargetNodes(): Set<com.google.android.gms.wearable.Node> {
        // 1. Try capability-based discovery first (targets only Watchman nodes)
        var nodes = try {
            capabilityClient.getCapability(WEAR_CAPABILITY, com.google.android.gms.wearable.CapabilityClient.FILTER_REACHABLE)
                .await().nodes
        } catch (e: Exception) {
            Log.w(TAG, "Capability lookup failed, falling back to connectedNodes", e)
            emptySet()
        }

        // 2. Fallback to all connected nodes
        if (nodes.isEmpty()) {
            Log.w(TAG, "No capable nodes for $WEAR_CAPABILITY, falling back to connectedNodes")
            val connectedNodes = nodeClient.connectedNodes.await()
            if (connectedNodes.isEmpty()) {
                kotlinx.coroutines.delay(2000)
                nodes = nodeClient.connectedNodes.await().toSet()
            } else {
                nodes = connectedNodes.toSet()
            }
        }
        return nodes
    }

    fun sendMessage(path: String, payload: ByteArray = ByteArray(0)) {
        scope.launch {
            try {
                val nodes = getTargetNodes()

                if (nodes.isEmpty()) {
                    Log.e(TAG, "Failed to send $path: No nodes connected after retry")
                    return@launch
                }

                nodes.forEach { node ->
                    messageClient.sendMessage(node.id, path, payload).await()
                    Log.d(TAG, "Sent $path to ${node.displayName}")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send $path", e)
            }
        }
    }

    fun sendFile(path: String, uri: Uri, onComplete: (Boolean) -> Unit) {
        scope.launch {
            try {
                val nodes = getTargetNodes()
                if (nodes.isEmpty()) {
                    Log.e(TAG, "File sync failed: No nodes connected")
                    onComplete(false)
                    return@launch
                }

                var allSuccess = true
                nodes.forEach { node ->
                    try {
                        val channel = channelClient.openChannel(node.id, path).await()
                        withContext(Dispatchers.IO) {
                            val outputStream = channelClient.getOutputStream(channel).await()
                            context.contentResolver.openInputStream(uri)?.use { inputStream ->
                                inputStream.copyTo(outputStream)
                            }
                            outputStream.close()
                            channelClient.close(channel).await()
                        }
                        Log.i(TAG, "File sync successful: $path to ${node.displayName}")
                    } catch (e: Exception) {
                        Log.e(TAG, "File sync failed for node ${node.displayName}: $path", e)
                        allSuccess = false
                    }
                }
                onComplete(allSuccess)
            } catch (e: Exception) {
                Log.e(TAG, "File sync operation failed", e)
                onComplete(false)
            }
        }
    }

    fun close() {
        scope.cancel()
    }
}
