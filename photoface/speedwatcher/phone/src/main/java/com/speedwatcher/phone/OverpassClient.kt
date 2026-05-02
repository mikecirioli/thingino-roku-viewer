package com.speedwatcher.phone

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object OverpassClient {
    private const val OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

    suspend fun getSpeedLimitMph(lat: Double, lon: Double): Int? = withContext(Dispatchers.IO) {
        try {
            // way(around:30) finds ways near the point. 
            // out center gives us a single coordinate for the way to calculate distance.
            val query = "[out:json][timeout:10];way(around:30,$lat,$lon)[\"maxspeed\"];out center;"
            val encodedQuery = java.net.URLEncoder.encode(query, "UTF-8")
            val url = URL("$OVERPASS_API_URL?data=$encodedQuery")
            
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 5000
            connection.readTimeout = 5000
            
            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val response = connection.inputStream.bufferedReader().use { it.readText() }
                val json = JSONObject(response)
                val elements = json.optJSONArray("elements")
                
                if (elements != null && elements.length() > 0) {
                    var closestLimit: Int? = null
                    var minDistance = Float.MAX_VALUE

                    for (i in 0 until elements.length()) {
                        val element = elements.getJSONObject(i)
                        val center = element.optJSONObject("center") ?: continue
                        val wayLat = center.getDouble("lat")
                        val wayLon = center.getDouble("lon")
                        
                        // Calculate distance to this road's center
                        val results = FloatArray(1)
                        android.location.Location.distanceBetween(lat, lon, wayLat, wayLon, results)
                        val distance = results[0]

                        if (distance < minDistance) {
                            val tags = element.optJSONObject("tags")
                            val maxspeedStr = tags?.optString("maxspeed")
                            if (!maxspeedStr.isNullOrEmpty()) {
                                val parsed = parseMaxSpeedToMph(maxspeedStr)
                                if (parsed != null) {
                                    minDistance = distance
                                    closestLimit = parsed
                                }
                            }
                        }
                    }
                    Log.d("OverpassClient", "Closest road limit: $closestLimit at distance: $minDistance")
                    return@withContext closestLimit
                }
            } else {
                Log.e("OverpassClient", "HTTP Error: ${connection.responseCode}")
            }
        } catch (e: Exception) {
            Log.e("OverpassClient", "Error fetching speed limit", e)
        }
        return@withContext null
    }

    private fun parseMaxSpeedToMph(maxspeed: String): Int? {
        try {
            val lower = maxspeed.lowercase()
            if (lower.contains("mph")) {
                val num = lower.replace("mph", "").trim().toIntOrNull()
                if (num != null) return num
            }
            if (lower.contains("km/h") || lower.contains("kmh")) {
                val num = lower.replace("km/h", "").replace("kmh", "").trim().toIntOrNull()
                if (num != null) return (num / 1.60934).toInt()
            }
            // default is usually km/h in OSM unless specified
            val num = maxspeed.trim().toIntOrNull()
            if (num != null) {
                return (num / 1.60934).toInt()
            }
        } catch (e: Exception) {
            Log.e("OverpassClient", "Error parsing maxspeed: $maxspeed", e)
        }
        return null
    }
}
