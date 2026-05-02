package com.photoface.complications.floors

import android.content.Context
import android.content.SharedPreferences
import androidx.health.services.client.HealthServices
import androidx.health.services.client.PassiveListenerCallback
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.PassiveListenerConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.guava.await
import java.time.LocalDate

/**
 * Repository for accessing and caching floors climbed data.
 * Uses Health Services API when available. Returns null when no data is available.
 */
class FloorDataRepository private constructor(private val context: Context) {

    private val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _floorsFlow = MutableStateFlow<Int?>(null)
    val floorsFlow: StateFlow<Int?> = _floorsFlow

    private var healthServicesAvailable = false
    private var passiveListenerRegistered = false

    init {
        // Load cached value (null if no cached data for today)
        _floorsFlow.value = getCachedFloors()
    }

    /**
     * Get current floors climbed count, or null if no data available.
     */
    fun getFloorsClimbed(): Int? {
        return _floorsFlow.value
    }

    /**
     * Initialize Health Services passive monitoring.
     */
    suspend fun initializeHealthServices() {
        try {
            val healthClient = HealthServices.getClient(context)
            val passiveClient = healthClient.passiveMonitoringClient

            // Check if floors data type is available
            val capabilities = passiveClient.getCapabilitiesAsync().await()

            if (DataType.FLOORS_DAILY in capabilities.supportedDataTypesPassiveMonitoring) {
                healthServicesAvailable = true
                registerPassiveListener()
            } else {
                healthServicesAvailable = false
            }
        } catch (e: Exception) {
            healthServicesAvailable = false
        }
    }

    private suspend fun registerPassiveListener() {
        if (passiveListenerRegistered) return

        try {
            val healthClient = HealthServices.getClient(context)
            val passiveClient = healthClient.passiveMonitoringClient

            val config = PassiveListenerConfig.builder()
                .setDataTypes(setOf(DataType.FLOORS_DAILY))
                .build()

            passiveClient.setPassiveListenerCallback(
                config,
                object : PassiveListenerCallback {
                    override fun onNewDataPointsReceived(dataPoints: DataPointContainer) {
                        // Extract floors data
                        dataPoints.getData(DataType.FLOORS_DAILY).lastOrNull()?.let { dataPoint ->
                            val floors = dataPoint.value.toInt()
                            updateFloors(floors)
                        }
                    }
                }
            )

            passiveListenerRegistered = true
        } catch (e: Exception) {
            // Listener registration failed; data stays null until next attempt
        }
    }

    /**
     * Cleans up the passive listener registration.
     * Call when the app is truly done with floor monitoring to avoid orphaned listeners.
     */
    suspend fun shutdown() {
        if (!passiveListenerRegistered) return

        try {
            val healthClient = HealthServices.getClient(context)
            val passiveClient = healthClient.passiveMonitoringClient
            passiveClient.clearPassiveListenerCallbackAsync().await()
        } catch (_: Exception) {
            // Best-effort cleanup; ignore errors during shutdown
        } finally {
            passiveListenerRegistered = false
        }
    }

    private fun updateFloors(floors: Int) {
        _floorsFlow.value = floors
        cacheFloors(floors)

        // Request complication update
        FloorsComplicationService.requestUpdate(context)
    }

    private fun getCachedFloors(): Int? {
        val today = LocalDate.now().toString()
        val cachedDate = prefs.getString(KEY_DATE, null)

        return if (cachedDate == today && prefs.contains(KEY_FLOORS)) {
            prefs.getInt(KEY_FLOORS, 0)
        } else {
            // New day or no cached data
            null
        }
    }

    private fun cacheFloors(floors: Int) {
        prefs.edit()
            .putString(KEY_DATE, LocalDate.now().toString())
            .putInt(KEY_FLOORS, floors)
            .apply()
    }

    companion object {
        private const val PREFS_NAME = "floors_data"
        private const val KEY_FLOORS = "floors_count"
        private const val KEY_DATE = "floors_date"

        @Volatile
        private var instance: FloorDataRepository? = null

        fun getInstance(context: Context): FloorDataRepository {
            return instance ?: synchronized(this) {
                instance ?: FloorDataRepository(context.applicationContext).also {
                    instance = it
                }
            }
        }
    }
}
