package com.photoface.complications.floors

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.photoface.complications.worldclock.WorldClockConfigActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Main activity for PhotoFace Complications app.
 * Shows available complications and their settings.
 */
class PermissionActivity : ComponentActivity() {

    private val scope = CoroutineScope(Dispatchers.Main)

    private val requiredPermissions = arrayOf(
        Manifest.permission.ACTIVITY_RECOGNITION,
        Manifest.permission.BODY_SENSORS,
        Manifest.permission.ACCESS_COARSE_LOCATION
    )

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        if (permissions.all { it.value }) {
            onPermissionGranted()
        } else {
            Toast.makeText(
                this,
                "Permission denied. Some complications may not work.",
                Toast.LENGTH_LONG
            ).show()
        }
        showMainMenu()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Check if we already have all required permissions
        if (!hasRequiredPermissions()) {
            requestRequiredPermissions()
        } else {
            onPermissionGranted()
            showMainMenu()
        }
    }

    private fun showMainMenu() {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
            setBackgroundColor(0xFF000000.toInt())
        }

        // Title
        val title = TextView(this).apply {
            text = "PhotoFace Complications"
            textSize = 16f
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 0, 0, 16)
        }
        layout.addView(title)

        // Subtitle
        val subtitle = TextView(this).apply {
            text = "5 complications available"
            textSize = 12f
            setTextColor(0xFFAAAAAA.toInt())
            setPadding(0, 0, 0, 24)
        }
        layout.addView(subtitle)

        // World Clock Settings button
        val worldClockButton = Button(this).apply {
            text = "World Clock"
            setOnClickListener {
                startActivity(Intent(this@PermissionActivity, WorldClockConfigActivity::class.java))
            }
        }
        layout.addView(worldClockButton)

        // Info text
        val info = TextView(this).apply {
            text = "\nOther complications:\n• Floors Climbed\n• Sunrise/Sunset\n• Moon Phase (image)\n• Moon Text"
            textSize = 12f
            setTextColor(0xFF888888.toInt())
            setPadding(0, 16, 0, 0)
        }
        layout.addView(info)

        // World Clock has a config activity
        // Floors, Sunrise/Sunset, and Moon Phase work without configuration

        setContentView(layout)
    }

    private fun hasRequiredPermissions(): Boolean {
        return requiredPermissions.all { permission ->
            ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun requestRequiredPermissions() {
        permissionLauncher.launch(requiredPermissions)
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }

    private fun onPermissionGranted() {
        // Initialize Health Services
        scope.launch {
            val repository = FloorDataRepository.getInstance(this@PermissionActivity)
            repository.initializeHealthServices()

            // Request complication update
            FloorsComplicationService.requestUpdate(this@PermissionActivity)
        }
    }
}
