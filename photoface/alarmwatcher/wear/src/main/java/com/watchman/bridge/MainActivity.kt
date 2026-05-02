package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.material3.*
import com.google.android.horologist.annotations.ExperimentalHorologistApi
import com.google.android.horologist.compose.layout.AppScaffold
import com.google.android.horologist.compose.layout.ScalingLazyColumn
import com.google.android.horologist.compose.layout.rememberColumnState

class MainActivity : ComponentActivity() {

    private var hasDndAccess by mutableStateOf(false)
    private var hasNotificationPermission by mutableStateOf(false)
    private var isDndOverrideEnabled by mutableStateOf(false)
    private lateinit var repository: WearableRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repository = WearableRepository(this)

        setContent {
            MaterialTheme {
                WatchMainScreen(hasDndAccess, hasNotificationPermission, isDndOverrideEnabled, repository)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        repository.close()
    }

    override fun onResume() {
        super.onResume()
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        hasDndAccess = nm.isNotificationPolicyAccessGranted
        
        hasNotificationPermission = if (android.os.Build.VERSION.SDK_INT >= 33) {
            checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        } else {
            true
        }

        val prefs = getSharedPreferences("WatchmanPrefs", Context.MODE_PRIVATE)
        isDndOverrideEnabled = prefs.getBoolean("dnd_override", false)
    }
}

@OptIn(ExperimentalHorologistApi::class)
@Composable
fun WatchMainScreen(hasDndAccess: Boolean, hasNotificationPermission: Boolean, isDndOverrideEnabled: Boolean, repository: WearableRepository) {
    val context = LocalContext.current
    val columnState = rememberColumnState()

    val permissionLauncher = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        // onResume will update the state
    }

    AppScaffold {
        ScalingLazyColumn(
            columnState = columnState,
            modifier = Modifier.fillMaxSize()
        ) {
            item {
                Text(
                    text = "Watchman Bridge",
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
            }

            // Status: Notification Permission (API 33+)
            if (android.os.Build.VERSION.SDK_INT >= 33) {
                item {
                    if (hasNotificationPermission) {
                        StatusCard(
                            title = "Notifications: OK",
                            subtitle = "Watch can show alerts",
                            color = Color(0xFF4CAF50),
                            onClick = {}
                        )
                    } else {
                        StatusCard(
                            title = "Notifications: MISSING",
                            subtitle = "Tap to grant permission",
                            color = Color.Red,
                            onClick = {
                                permissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                            }
                        )
                    }
                }
            }

            // Status: DND Access (Permission)
            // Samsung devices (Wear OS 4+) silently grant this permission at install but break the API check,
            // causing it to always return false. We hide the card entirely on Samsung to prevent confusion.
            val isSamsung = android.os.Build.MANUFACTURER.equals("samsung", ignoreCase = true)
            
            if (!isSamsung) {
                item {
                    if (hasDndAccess) {
                        StatusCard(
                            title = "DND Permission: OK",
                            subtitle = "Watch can override silence",
                            color = Color(0xFF4CAF50),
                            onClick = {}
                        )
                    } else {
                        StatusCard(
                            title = "DND Permission: MISSING",
                            subtitle = "Tap to grant access",
                            color = Color.Red,
                            onClick = {
                                try {
                                    // Correct DND access screen
                                    val intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
                                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                    }
                                    context.startActivity(intent)
                                    android.widget.Toast.makeText(context, "Grant 'Watchman Bridge' DND access", android.widget.Toast.LENGTH_LONG).show()
                                } catch (e: Exception) {
                                    // Fallback to App Info page on Galaxy Watches
                                    try {
                                        val fallbackIntent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                            data = android.net.Uri.fromParts("package", context.packageName, null)
                                        }
                                        context.startActivity(fallbackIntent)
                                        android.widget.Toast.makeText(context, "Scroll down to 'Permissions' and allow 'Do not disturb'", android.widget.Toast.LENGTH_LONG).show()
                                    } catch (e2: Exception) {
                                        android.widget.Toast.makeText(context, "Could not open Settings", android.widget.Toast.LENGTH_SHORT).show()
                                    }
                                }
                            }
                        )
                    }
                }
            }

            // Status: DND Override (Phone Setting)
            item {
                StatusCard(
                    title = "Phone Override: ${if (isDndOverrideEnabled) "ON" else "OFF"}",
                    subtitle = if (isDndOverrideEnabled) "Alarms will ring in DND" else "Silence is respected",
                    color = if (isDndOverrideEnabled) Color(0xFF4CAF50) else Color.Gray,
                    onClick = {}
                )
            }

            if (isDndOverrideEnabled && !hasDndAccess && !isSamsung) {
                item {
                    Text(
                        text = "Warning: Phone wants to override DND, but Watch doesn't have permission!",
                        color = Color.Red,
                        style = MaterialTheme.typography.bodySmall,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(12.dp)
                    )
                }
            }

            item {
                Button(
                    onClick = { 
                        repository.sendMessage(WatchmanPaths.OPEN_PHONE_APP)
                        // Add a small toast or visual feedback
                    },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color.DarkGray)
                ) {
                    Text("Open Phone App", style = MaterialTheme.typography.labelSmall)
                }
            }

            item {
                Text(
                    text = "Syncs alarms and DND from your phone.",
                    style = MaterialTheme.typography.bodySmall,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                )
            }
        }
    }
}

@Composable
fun StatusCard(title: String, subtitle: String, color: Color, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.15f)),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(title, color = color, style = MaterialTheme.typography.labelMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            Text(subtitle, color = color.copy(alpha = 0.8f), style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
        }
    }
}
