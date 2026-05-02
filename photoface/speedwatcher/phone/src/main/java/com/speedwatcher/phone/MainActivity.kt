package com.speedwatcher.phone

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import org.json.JSONObject

@OptIn(ExperimentalMaterial3Api::class)
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = PreferencesManager(this)

        setContent {
            var speedThreshold by remember { mutableStateOf(prefs.speedThreshold) }
            var speedUnit by remember { mutableStateOf(prefs.speedUnit) }
            var useDynamicLimit by remember { mutableStateOf(prefs.useDynamicLimit) }
            var dynamicOverage by remember { mutableStateOf(prefs.dynamicOverage) }
            var cooldownSeconds by remember { mutableStateOf(prefs.cooldownSeconds) }
            var vibrationPattern by remember { mutableStateOf(prefs.vibrationPattern) }
            var vibrationPower by remember { mutableStateOf(prefs.vibrationPower.toFloat()) }
            var targetMacs by remember { mutableStateOf(prefs.targetMacAddresses) }
            var savedPresets by remember { mutableStateOf(prefs.savedPresets) }
            
            val context = LocalContext.current
            val coroutineScope = rememberCoroutineScope()
            
            val pairedDevices = remember { mutableStateListOf<Pair<String, String>>() }

            LaunchedEffect(Unit) {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED) {
                    val bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
                    val bluetoothAdapter = bluetoothManager.adapter
                    try {
                        bluetoothAdapter?.bondedDevices?.forEach { device ->
                            pairedDevices.add(Pair(device.name ?: "Unknown Device", device.address))
                        }
                    } catch (e: SecurityException) {}
                }
            }
            
            var showPresetDialog by remember { mutableStateOf(false) }
            var newPresetName by remember { mutableStateOf("") }

            if (showPresetDialog) {
                AlertDialog(
                    onDismissRequest = { showPresetDialog = false },
                    title = { Text("Save Preset") },
                    text = {
                        OutlinedTextField(
                            value = newPresetName,
                            onValueChange = { newPresetName = it },
                            label = { Text("Preset Name") }
                        )
                    },
                    confirmButton = {
                        TextButton(onClick = {
                            if (newPresetName.isNotBlank()) {
                                val presetJson = JSONObject()
                                presetJson.put("name", newPresetName)
                                presetJson.put("speed", speedThreshold)
                                presetJson.put("unit", speedUnit)
                                presetJson.put("cooldown", cooldownSeconds)
                                presetJson.put("pattern", vibrationPattern)
                                presetJson.put("power", vibrationPower.toInt())
                                
                                val updatedPresets = savedPresets.toMutableSet()
                                updatedPresets.removeAll { JSONObject(it).optString("name") == newPresetName }
                                updatedPresets.add(presetJson.toString())
                                
                                savedPresets = updatedPresets
                                prefs.savedPresets = updatedPresets
                            }
                            showPresetDialog = false
                        }) { Text("Save") }
                    },
                    dismissButton = {
                        TextButton(onClick = { showPresetDialog = false }) { Text("Cancel") }
                    }
                )
            }

            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    Box(modifier = Modifier.fillMaxSize()) {
                        LazyColumn(
                            modifier = Modifier.padding(16.dp),
                            contentPadding = PaddingValues(bottom = 80.dp) // Space for Save button
                        ) {
                            item {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(text = "SpeedWatcher MVP", style = MaterialTheme.typography.headlineMedium)
                                    var isEnabled by remember { mutableStateOf(prefs.isServiceEnabled) }
                                    Switch(
                                        checked = isEnabled,
                                        onCheckedChange = {
                                            isEnabled = it
                                            prefs.isServiceEnabled = it
                                            if (!it) {
                                                context.stopService(android.content.Intent(context, SpeedTrackerService::class.java))
                                            }
                                            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                                                android.service.quicksettings.TileService.requestListeningState(
                                                    context,
                                                    android.content.ComponentName(context, SpeedWatcherTileService::class.java)
                                                )
                                            }
                                        }
                                    )
                                }
                                Spacer(modifier = Modifier.height(24.dp))
                            }

                            // PRESETS
                            if (savedPresets.isNotEmpty()) {
                                item {
                                    Text("Load Preset", style = MaterialTheme.typography.titleMedium)
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                                        savedPresets.mapNotNull { 
                                            try { JSONObject(it) } catch(e:Exception){ null } 
                                        }.sortedBy { it.optString("name") }.forEach { preset ->
                                            ElevatedFilterChip(
                                                selected = false,
                                                onClick = {
                                                    speedThreshold = preset.optInt("speed", 75)
                                                    speedUnit = preset.optString("unit", "MPH")
                                                    cooldownSeconds = preset.optInt("cooldown", 30)
                                                    vibrationPattern = preset.optString("pattern", "Rapid")
                                                    vibrationPower = preset.optInt("power", 255).toFloat()
                                                    
                                                    prefs.speedThreshold = speedThreshold
                                                    prefs.speedUnit = speedUnit
                                                    prefs.cooldownSeconds = cooldownSeconds
                                                    prefs.vibrationPattern = vibrationPattern
                                                    prefs.vibrationPower = vibrationPower.toInt()
                                                },
                                                label = { Text(preset.optString("name")) },
                                                modifier = Modifier.padding(end = 8.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(16.dp))
                                }
                            }

                            // SPEED LIMIT SETTINGS
                            item {
                                Text("Speed Limit Mode", style = MaterialTheme.typography.titleMedium)
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Switch(
                                        checked = useDynamicLimit,
                                        onCheckedChange = { useDynamicLimit = it }
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text("Use OpenStreetMap (Dynamic)")
                                }
                                
                                if (useDynamicLimit) {
                                    Text("Overage Tolerance (+)", style = MaterialTheme.typography.titleSmall)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        IconButton(
                                            onClick = { dynamicOverage -= 1 },
                                            modifier = Modifier.size(48.dp)
                                        ) {
                                            Icon(Icons.Default.Remove, "Decrease")
                                        }
                                        Text("$dynamicOverage", style = MaterialTheme.typography.displayMedium, modifier = Modifier.padding(horizontal = 16.dp))
                                        IconButton(
                                            onClick = { dynamicOverage += 1 },
                                            modifier = Modifier.size(48.dp)
                                        ) {
                                            Icon(Icons.Default.Add, "Increase")
                                        }
                                    }
                                } else {
                                    Text("Target Speed Limit", style = MaterialTheme.typography.titleSmall)
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        IconButton(
                                            onClick = { speedThreshold -= 5 },
                                            modifier = Modifier.size(48.dp)
                                        ) {
                                            Icon(Icons.Default.Remove, "Decrease")
                                        }
                                        Text("$speedThreshold", style = MaterialTheme.typography.displayMedium, modifier = Modifier.padding(horizontal = 16.dp))
                                        IconButton(
                                            onClick = { speedThreshold += 5 },
                                            modifier = Modifier.size(48.dp)
                                        ) {
                                            Icon(Icons.Default.Add, "Increase")
                                        }
                                    }
                                }
                                
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    RadioButton(selected = speedUnit == "MPH", onClick = { speedUnit = "MPH" })
                                    Text("MPH")
                                    Spacer(modifier = Modifier.width(16.dp))
                                    RadioButton(selected = speedUnit == "KMH", onClick = { speedUnit = "KMH" })
                                    Text("KM/H")
                                }
                                Spacer(modifier = Modifier.height(16.dp))
                            }

                            // SNOOZE/COOLDOWN
                            item {
                                Text("Snooze Between Alerts: $cooldownSeconds seconds", style = MaterialTheme.typography.titleMedium)
                                Spacer(modifier = Modifier.height(8.dp))
                                Slider(
                                    value = cooldownSeconds.toFloat(),
                                    onValueChange = { cooldownSeconds = it.toInt() },
                                    valueRange = 5f..120f,
                                    steps = 22
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                            }

                            // VIBRATION SETTINGS
                            item {
                                Text("Vibration Pattern", style = MaterialTheme.typography.titleMedium)
                                Spacer(modifier = Modifier.height(8.dp))
                                var expandedPattern by remember { mutableStateOf(false) }
                                ExposedDropdownMenuBox(
                                    expanded = expandedPattern,
                                    onExpandedChange = { expandedPattern = !expandedPattern }
                                ) {
                                    OutlinedTextField(
                                        value = vibrationPattern,
                                        onValueChange = {},
                                        readOnly = true,
                                        modifier = Modifier.menuAnchor().fillMaxWidth(),
                                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expandedPattern) }
                                    )
                                    ExposedDropdownMenu(expanded = expandedPattern, onDismissRequest = { expandedPattern = false }) {
                                        listOf("Rapid", "Standard", "Heartbeat").forEach { pat ->
                                            DropdownMenuItem(
                                                text = { Text(pat) },
                                                onClick = { vibrationPattern = pat; expandedPattern = false }
                                            )
                                        }
                                    }
                                }
                                Spacer(modifier = Modifier.height(16.dp))

                                Text("Vibration Power: ${vibrationPower.toInt()}", style = MaterialTheme.typography.titleMedium)
                                Spacer(modifier = Modifier.height(8.dp))
                                Slider(
                                    value = vibrationPower,
                                    onValueChange = { vibrationPower = it },
                                    valueRange = 10f..255f
                                )
                                Spacer(modifier = Modifier.height(24.dp))
                            }

                            // TARGET DEVICES
                            item {
                                Text("Target Car Bluetooth Devices", style = MaterialTheme.typography.titleMedium)
                                if (pairedDevices.isEmpty()) {
                                    Text("No paired devices found.", color = MaterialTheme.colorScheme.error)
                                }
                            }
                            items(pairedDevices) { device ->
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Checkbox(
                                        checked = targetMacs.contains(device.second),
                                        onCheckedChange = { checked ->
                                            val newMacs = targetMacs.toMutableSet()
                                            if (checked) newMacs.add(device.second) else newMacs.remove(device.second)
                                            targetMacs = newMacs
                                            prefs.targetMacAddresses = newMacs
                                        }
                                    )
                                    Text(device.first, modifier = Modifier.padding(start = 8.dp))
                                }
                            }

                            item {
                                Spacer(modifier = Modifier.height(24.dp))
                                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                    OutlinedButton(onClick = { 
                                        newPresetName = ""
                                        showPresetDialog = true 
                                    }) {
                                        Text("Save as Preset")
                                    }
                                    Button(onClick = {
                                        coroutineScope.launch {
                                            WearMessenger(context).sendSpeedAlert(vibrationPattern, vibrationPower.toInt())
                                        }
                                    }) {
                                        Text("Test Watch Alert")
                                    }
                                }
                                Spacer(modifier = Modifier.height(32.dp))
                            }

                            item {
                                Image(
                                    painter = painterResource(id = R.drawable.logo_3dog),
                                    contentDescription = "3 Dog Productions Logo",
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 16.dp)
                                        .height(60.dp),
                                    contentScale = ContentScale.Fit
                                )
                            }
                        }

                        // Floating Save Button at bottom
                        Box(modifier = Modifier.fillMaxSize().padding(16.dp), contentAlignment = Alignment.BottomCenter) {
                            Button(
                                onClick = {
                                    prefs.speedThreshold = speedThreshold
                                    prefs.speedUnit = speedUnit
                                    prefs.useDynamicLimit = useDynamicLimit
                                    prefs.dynamicOverage = dynamicOverage
                                    prefs.cooldownSeconds = cooldownSeconds
                                    prefs.vibrationPattern = vibrationPattern
                                    prefs.vibrationPower = vibrationPower.toInt()
                                    prefs.targetMacAddresses = targetMacs
                                    (context as Activity).finish()
                                },
                                modifier = Modifier.fillMaxWidth().height(56.dp)
                            ) {
                                Text("Save & Close")
                            }
                        }
                    }
                }
            }
        }
    }
}
