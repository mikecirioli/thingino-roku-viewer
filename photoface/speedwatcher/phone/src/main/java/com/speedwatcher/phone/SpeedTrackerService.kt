package com.speedwatcher.phone

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class SpeedTrackerService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var wearMessenger: WearMessenger
    private lateinit var prefs: PreferencesManager
    private lateinit var offlineMapEngine: OfflineMapEngine

    private var lastAlertTimeMs: Long = 0
    private var lastApiCallTimeMs: Long = 0
    private var lastApiLocation: android.location.Location? = null
    private var cachedSpeedLimitMph: Int? = null
    private var pendingLimitMph: Int? = null
    private var pendingLimitCount: Int = 0

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(locationResult: LocationResult) {
            val location = locationResult.lastLocation ?: return
            
            if (location.hasSpeed()) {
                // getSpeed() is in meters/second
                val speedMps = location.speed
                val unit = prefs.speedUnit
                val currentSpeed = if (unit == "KMH") speedMps * 3.6f else speedMps * 2.23694f
                
                Log.d("SpeedWatcher", "Current speed: $currentSpeed $unit")
                
                serviceScope.launch {
                    val useDynamic = prefs.useDynamicLimit
                    var threshold = prefs.speedThreshold.toFloat()

                    if (useDynamic) {
                        val offlineLimit = offlineMapEngine.getSpeedLimitMph(location.latitude, location.longitude)
                        if (offlineLimit != null) {
                            cachedSpeedLimitMph = offlineLimit
                            pendingLimitMph = null
                            pendingLimitCount = 0
                            Log.d("SpeedWatcher", "Using offline map limit: $offlineLimit mph")
                        } else {
                            val now = System.currentTimeMillis()
                            val distanceToLast = if (lastApiLocation != null) location.distanceTo(lastApiLocation!!) else Float.MAX_VALUE
                            val timeSinceLastMs = now - lastApiCallTimeMs
                            
                            // Dynamic threshold logic:
                            // Time baseline: Minimum 15 seconds between API calls to prevent spamming
                            // Speed baseline: Distance covered in 15 seconds at current speed.
                            // Max time: If we haven't checked in 120 seconds, force a check to prevent staleness.
                            val baselineTimeSeconds = 15f
                            val maxTimeMs = 120_000L
                        
                        // Avoid calculating a massive distance if moving fast, cap the multiplier if desired,
                        // but 15s at 80mph is ~536 meters, which is a reasonable gap.
                        val dynamicDistanceThreshold = (speedMps * baselineTimeSeconds).coerceAtLeast(50f) // Minimum 50m

                        val shouldUpdateCache = (timeSinceLastMs > (baselineTimeSeconds * 1000L) && distanceToLast > dynamicDistanceThreshold) 
                                                || timeSinceLastMs > maxTimeMs

                        if (shouldUpdateCache) {
                            lastApiCallTimeMs = now
                            lastApiLocation = location
                            val newLimitMph = OverpassClient.getSpeedLimitMph(location.latitude, location.longitude)
                            
                            val speedInMphForLog = speedMps * 2.23694f
                            MetricsLogger.logEvent(
                                context = this@SpeedTrackerService,
                                event = "API_CALL",
                                speedMph = speedInMphForLog,
                                distanceMoved = if (distanceToLast == Float.MAX_VALUE) 0f else distanceToLast,
                                timeElapsedSec = timeSinceLastMs / 1000f,
                                thresholdDistance = dynamicDistanceThreshold,
                                apiLimit = newLimitMph
                            )
                            
                            if (newLimitMph != null) {
                                if (newLimitMph == cachedSpeedLimitMph) {
                                    // Reset consensus if we match the current cache
                                    pendingLimitMph = null
                                    pendingLimitCount = 0
                                } else if (newLimitMph == pendingLimitMph) {
                                    pendingLimitCount++
                                    Log.d("SpeedWatcher", "Consensus count: $pendingLimitCount for $newLimitMph mph")
                                    if (pendingLimitCount >= 2) {
                                        Log.i("SpeedWatcher", "Consensus reached! Updating limit to $newLimitMph mph")
                                        cachedSpeedLimitMph = newLimitMph
                                        pendingLimitMph = null
                                        pendingLimitCount = 0
                                    }
                                } else {
                                    // First time seeing this new limit
                                    pendingLimitMph = newLimitMph
                                    pendingLimitCount = 1
                                    Log.d("SpeedWatcher", "New potential limit detected: $newLimitMph mph. Waiting for consensus...")
                                }
                            }
                        }
                    }
                } // Closing the if (useDynamic) block

                if (useDynamic) {
                    val limitMph = cachedSpeedLimitMph ?: pendingLimitMph // Use pending as a placeholder if cache is empty
                        if (limitMph != null) {
                            val limitConverted = if (unit == "KMH") limitMph * 1.60934f else limitMph.toFloat()
                            val overageConverted = if (unit == "KMH") prefs.dynamicOverage * 1.60934f else prefs.dynamicOverage.toFloat()
                            threshold = limitConverted + overageConverted
                            Log.d("SpeedWatcher", "Dynamic Limit: $limitConverted, Overage: $overageConverted, Total Threshold: $threshold")
                        } else {
                            // Fallback to static if no data found
                            Log.d("SpeedWatcher", "Dynamic limit unavailable. Falling back to static threshold: $threshold")
                        }
                    }

                    if (currentSpeed >= threshold) {
                        val now = System.currentTimeMillis()
                        val cooldownMs = prefs.cooldownSeconds * 1000L
                        
                        if (now - lastAlertTimeMs > cooldownMs) {
                            Log.w("SpeedWatcher", "Threshold exceeded! Current: $currentSpeed, Threshold: $threshold. Firing alert.")
                            lastAlertTimeMs = now
                            wearMessenger.sendSpeedAlert(prefs.vibrationPattern, prefs.vibrationPower)
                        }
                    }
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        wearMessenger = WearMessenger(this)
        prefs = PreferencesManager(this)
        MetricsLogger.initialize(this)
        
        offlineMapEngine = OfflineMapEngine()
        val graphFolder = java.io.File(getExternalFilesDir(null), "graph-cache")
        if (graphFolder.exists() && graphFolder.isDirectory) {
            serviceScope.launch {
                offlineMapEngine.loadMap(graphFolder)
            }
        }
        
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = NotificationCompat.Builder(this, "speedwatcher_channel")
            .setContentTitle("SpeedWatcher")
            .setContentText("Monitoring speed while connected to car.")
            .setSmallIcon(android.R.drawable.ic_dialog_map)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(1, notification)
        }

        startLocationUpdates()
        return START_STICKY
    }

    private fun startLocationUpdates() {
        val fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 3000L)
            .setMinUpdateIntervalMillis(2000L)
            .build()

        try {
            fusedLocationClient.requestLocationUpdates(
                locationRequest,
                locationCallback,
                Looper.getMainLooper()
            )
        } catch (e: SecurityException) {
            Log.e("SpeedWatcher", "Location permission missing", e)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        offlineMapEngine.close()
        val fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        fusedLocationClient.removeLocationUpdates(locationCallback)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            "speedwatcher_channel",
            "Speed Monitoring",
            NotificationManager.IMPORTANCE_LOW
        )
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(channel)
    }
}
