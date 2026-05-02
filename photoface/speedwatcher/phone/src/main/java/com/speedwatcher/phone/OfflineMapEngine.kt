package com.speedwatcher.phone

import android.content.Context
import android.util.Log
import com.graphhopper.GraphHopper
import com.graphhopper.config.Profile
import com.graphhopper.routing.ev.DecimalEncodedValue
import com.graphhopper.routing.ev.MaxSpeed
import com.graphhopper.routing.util.EdgeFilter
import java.io.File

class OfflineMapEngine {
    private var hopper: GraphHopper? = null
    private var maxSpeedEnc: DecimalEncodedValue? = null
    var isReady = false
        private set

    fun loadMap(graphFolder: File): Boolean {
        try {
            Log.d("OfflineMapEngine", "Loading map from ${graphFolder.absolutePath}")
            hopper = GraphHopper()
            hopper!!.graphHopperLocation = graphFolder.absolutePath
            
            // Basic profile mapping
            hopper!!.setProfiles(Profile("car").setCustomModel(com.graphhopper.util.CustomModel()))
            
            hopper!!.importOrLoad()
            
            maxSpeedEnc = hopper!!.encodingManager.getDecimalEncodedValue(MaxSpeed.KEY)
            isReady = true
            Log.i("OfflineMapEngine", "Map loaded successfully!")
            return true
        } catch (e: Exception) {
            Log.e("OfflineMapEngine", "Failed to load GraphHopper map", e)
            hopper = null
            isReady = false
            return false
        }
    }

    fun getSpeedLimitMph(lat: Double, lon: Double): Int? {
        if (!isReady || hopper == null || maxSpeedEnc == null) return null
        
        try {
            val locationIndex = hopper!!.locationIndex
            val snap = locationIndex.findClosest(lat, lon, EdgeFilter.ALL_EDGES)
            
            if (snap.isValid) {
                val edge = snap.closestEdge
                val speedKmh = edge.get(maxSpeedEnc)
                
                if (speedKmh != null && !speedKmh.isInfinite() && speedKmh > 0) {
                    val mph = (speedKmh / 1.60934).toInt()
                    Log.d("OfflineMapEngine", "Offline match found: $speedKmh km/h -> $mph mph")
                    return mph
                } else {
                    Log.d("OfflineMapEngine", "Offline match found, but no explicit max_speed tag.")
                }
            } else {
                Log.d("OfflineMapEngine", "No road found near coordinates in offline map.")
            }
        } catch (e: Exception) {
            Log.e("OfflineMapEngine", "Error querying offline map", e)
        }
        return null
    }
    
    fun close() {
        try {
            hopper?.close()
        } catch (e: Exception) {
            Log.e("OfflineMapEngine", "Error closing GraphHopper", e)
        }
        hopper = null
        isReady = false
    }
}
