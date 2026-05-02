package com.watchman.bridge

import com.watchman.bridge.shared.WatchmanPaths
import com.watchman.bridge.shared.data.AlertRule
import com.watchman.bridge.shared.data.TimeWindow

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.PowerManager
import android.provider.ContactsContract
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.BatteryAlert
import androidx.compose.material.icons.filled.BatteryFull
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContactPage
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.MusicNote
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material.icons.filled.VerifiedUser
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color as ComposeColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel

import com.watchman.bridge.R
import com.watchman.bridge.data.SettingsRepository
import com.watchman.bridge.data.SharedPrefsSettingsRepository

data class AppItem(val label: String, val packageName: String)

class MainViewModel(
    val settingsRepository: SettingsRepository,
    val wearableRepository: WearableRepository,
    val trialManager: TrialManager,
    private val context: Context
) : ViewModel() {
    var isNotificationEnabled by mutableStateOf(false)
    var isDndAccessGranted by mutableStateOf(false)
    var isBatteryOptimized by mutableStateOf(true)
    var customSoundName by mutableStateOf("Default Ringtone")
    var isDndOverrideEnabled by mutableStateOf(false)
    var alarmVolume by mutableFloatStateOf(1.0f)
    var isGlobalCatchAllEnabled by mutableStateOf(false)
    var isHighReliabilityEnabled by mutableStateOf(false)
    var globalVibrationPattern by mutableStateOf("Standard")
    var globalVibrateOnly by mutableStateOf(false)
    var globalQuietHours by mutableStateOf<List<TimeWindow>>(emptyList())
    var alertRules by mutableStateOf<List<AlertRule>>(emptyList())
    
    var isTrialActive by mutableStateOf(true)
    var remainingHours by mutableIntStateOf(72)
    var isPro by mutableStateOf(false)

    var billingManager: BillingManager? = null
        private set

    fun initializeBilling() {
        billingManager = BillingManager(context, trialManager) {
            isPro = true
            isTrialActive = true
            refreshStatus()
        }
        billingManager?.startConnection()
        refreshStatus()
    }

    fun startPurchase(activity: android.app.Activity) {
        billingManager?.launchPurchaseFlow(activity)
    }

    fun refreshStatus() {
        isTrialActive = trialManager.isTrialActive()
        remainingHours = trialManager.getRemainingHours()
        isPro = trialManager.isProUser()

        isNotificationEnabled = NotificationManagerCompat.getEnabledListenerPackages(context).contains(context.packageName)
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
        isDndAccessGranted = nm.isNotificationPolicyAccessGranted
        
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        isBatteryOptimized = !pm.isIgnoringBatteryOptimizations(context.packageName)
        customSoundName = settingsRepository.getCustomSoundName()
        isDndOverrideEnabled = settingsRepository.isDndOverrideEnabled()
        alarmVolume = settingsRepository.getAlarmVolume()
        isGlobalCatchAllEnabled = settingsRepository.isGlobalCatchAllEnabled()
        isHighReliabilityEnabled = settingsRepository.isHighReliabilityEnabled()
        globalVibrationPattern = settingsRepository.getGlobalVibrationPattern()
        globalVibrateOnly = settingsRepository.isGlobalVibrateOnly()
        globalQuietHours = settingsRepository.getGlobalQuietHours()
        loadRules()
    }

    private fun loadRules() {
        alertRules = settingsRepository.getAlertRules()
    }

    fun saveRule(rule: AlertRule) {
        settingsRepository.saveAlertRule(rule)
        alertRules = settingsRepository.getAlertRules()
    }

    fun deleteRule(id: String) {
        settingsRepository.deleteAlertRule(id)
        alertRules = settingsRepository.getAlertRules()
    }

    fun updateGlobalQuietHours(schedules: List<TimeWindow>) {
        globalQuietHours = schedules
        settingsRepository.saveGlobalQuietHours(schedules)
    }

    fun updateHighReliability(enabled: Boolean) {
        isHighReliabilityEnabled = enabled
        settingsRepository.setHighReliabilityEnabled(enabled)
        val intent = Intent(context, AlarmListenerService::class.java).apply {
            putExtra("action", if (enabled) "START_RELIABILITY" else "STOP_RELIABILITY")
        }
        context.startService(intent)
    }

    fun updateGlobalCatchAll(enabled: Boolean) {
        isGlobalCatchAllEnabled = enabled
        settingsRepository.setGlobalCatchAllEnabled(enabled)
    }

    fun updateGlobalVibrateOnly(enabled: Boolean) {
        globalVibrateOnly = enabled
        settingsRepository.setGlobalVibrateOnly(enabled)
        wearableRepository.updateData(WatchmanPaths.VIBRATION_PATTERN) {
            it.dataMap.putBoolean("vibrate_only", enabled)
            it.dataMap.putString("pattern_name", globalVibrationPattern)
        }
    }

    fun updateGlobalVibrationPattern(pattern: String) {
        globalVibrationPattern = pattern
        settingsRepository.setGlobalVibrationPattern(pattern)
        wearableRepository.updateData(WatchmanPaths.VIBRATION_PATTERN) {
            it.dataMap.putString("pattern_name", pattern)
            it.dataMap.putBoolean("vibrate_only", globalVibrateOnly)
        }
    }

    fun updateAlarmVolume(volume: Float) {
        alarmVolume = volume
        settingsRepository.setAlarmVolume(volume)
        wearableRepository.updateData(WatchmanPaths.ALARM_VOLUME_PREF) {
            it.dataMap.putFloat("volume", volume)
        }
    }

    fun updateDndOverride(enabled: Boolean) {
        isDndOverrideEnabled = enabled
        settingsRepository.setDndOverrideEnabled(enabled)
        wearableRepository.updateData(WatchmanPaths.DND_OVERRIDE_PREF) {
            it.dataMap.putBoolean("enabled", enabled)
        }
    }

    fun requestRebind() {
        val pm = context.packageManager
        val componentName = android.content.ComponentName(context, AlarmListenerService::class.java)
        pm.setComponentEnabledSetting(componentName, PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP)
        pm.setComponentEnabledSetting(componentName, PackageManager.COMPONENT_ENABLED_STATE_ENABLED, PackageManager.DONT_KILL_APP)
    }

    fun testGlobalAlarm() {
        val payload = org.json.JSONObject()
        payload.put("message", "Test: Watch Connection")
        payload.put("volume", alarmVolume.toDouble())
        payload.put("overrideDnd", isDndOverrideEnabled)
        payload.put("soundFile", "custom_alarm.mp3")
        payload.put("playDurationSeconds", -1)
        payload.put("vibrationPattern", globalVibrationPattern)
        payload.put("vibrateOnly", globalVibrateOnly)
        wearableRepository.sendMessage(WatchmanPaths.CRITICAL_ALERT, payload.toString().toByteArray())
    }

    fun testAlertRule(rule: AlertRule) {
        val watchFileName = "rule_${rule.soundName.replace("[^a-zA-Z0-9.-]".toRegex(), "_")}"
        val payload = org.json.JSONObject()
        payload.put("message", "Test Rule: ${rule.sender}")
        payload.put("volume", rule.volume.toDouble())
        payload.put("overrideDnd", rule.overrideDnd)
        payload.put("soundFile", watchFileName)
        payload.put("playDurationSeconds", rule.playDurationSeconds)
        payload.put("vibrationPattern", rule.vibration)
        payload.put("vibrateOnly", rule.vibrateOnly)
        wearableRepository.sendMessage(WatchmanPaths.CRITICAL_ALERT, payload.toString().toByteArray())
    }

    class Factory(
        private val settingsRepository: SettingsRepository,
        private val wearableRepository: WearableRepository,
        private val trialManager: TrialManager,
        private val context: Context
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(MainViewModel::class.java)) {
                return MainViewModel(settingsRepository, wearableRepository, trialManager, context) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}

class MainActivity : ComponentActivity() {
    private lateinit var wearableRepository: WearableRepository
    private lateinit var viewModel: MainViewModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settingsRepository = SharedPrefsSettingsRepository(applicationContext)
        wearableRepository = WearableRepository(this)
        val trialManager = TrialManager(settingsRepository)

        setContent {
            viewModel = viewModel(
                factory = MainViewModel.Factory(settingsRepository, wearableRepository, trialManager, LocalContext.current)
            )
            LaunchedEffect(Unit) {
                viewModel.initializeBilling()
            }

            MaterialTheme(
                colorScheme = if (android.os.Build.VERSION.SDK_INT >= 31) dynamicLightColorScheme(LocalContext.current) else lightColorScheme()
            ) {
                MainScreen(viewModel)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::viewModel.isInitialized) {
            viewModel.refreshStatus()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        wearableRepository.close()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(viewModel: MainViewModel) {
    val context = LocalContext.current
    var selectedTab by remember { mutableIntStateOf(0) }
    var showRuleDialog by remember { mutableStateOf<AlertRule?>(null) }
    
    val pickMainAudioLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let { 
            val fileName = getFileName(context, it)
            viewModel.settingsRepository.setCustomSoundName(fileName)
            Toast.makeText(context, "Syncing sound to watch...", Toast.LENGTH_SHORT).show()
            viewModel.wearableRepository.sendFile(WatchmanPaths.CUSTOM_SOUND_FILE, it) { success ->
                (context as ComponentActivity).runOnUiThread {
                    val msg = if (success) "Sound synced!" else "Sync failed"
                    Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                    viewModel.refreshStatus()
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        viewModel.refreshStatus()
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    val title = when(selectedTab) {
                        0 -> "Dashboard"
                        1 -> "Alert Rules"
                        else -> "Settings"
                    }
                    Text(title, fontWeight = FontWeight.Bold) 
                },
                actions = {
                    if (selectedTab == 0) {
                        IconButton(onClick = { 
                            viewModel.requestRebind()
                            Toast.makeText(context, "Service Refreshed", Toast.LENGTH_SHORT).show()
                        }) {
                            Icon(Icons.Default.Refresh, contentDescription = "Refresh Service")
                        }
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    icon = { Icon(Icons.Default.NotificationsActive, null) },
                    label = { Text("Status") },
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.List, null) },
                    label = { Text("Rules") },
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, null) },
                    label = { Text("Settings") },
                    selected = selectedTab == 2,
                    onClick = { selectedTab = 2 }
                )
            }
        },
        floatingActionButton = {
            if (selectedTab == 1) {
                FloatingActionButton(onClick = { showRuleDialog = AlertRule() }) {
                    Icon(Icons.Default.Add, contentDescription = "Add Rule")
                }
            }
        }
    ) { padding ->
        Box(modifier = Modifier.padding(padding).fillMaxSize()) {
            when (selectedTab) {
                0 -> StatusTab(viewModel)
                1 -> RulesTab(viewModel) { showRuleDialog = it }
                2 -> SettingsTab(viewModel, pickMainAudioLauncher)
            }
        }

        if (showRuleDialog != null) {
            RuleEditorDialog(
                rule = showRuleDialog!!,
                viewModel = viewModel,
                onDismiss = { showRuleDialog = null },
                onSave = { 
                    viewModel.saveRule(it)
                    showRuleDialog = null
                }
            )
        }
    }
}

@Composable
fun StatusTab(viewModel: MainViewModel) {
    val context = LocalContext.current
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            androidx.compose.foundation.Image(
                painter = painterResource(id = R.drawable.logo_3dog),
                contentDescription = "3 Bad Dogs Logo",
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 32.dp)
                    .height(180.dp),
                contentScale = ContentScale.Fit
            )
        }

        if (!viewModel.isPro) {
            item {
                TrialBanner(viewModel.remainingHours) {
                    viewModel.startPurchase(context as android.app.Activity)
                }
            }
        }

        if (viewModel.isBatteryOptimized) {
            item {
                BatteryWarningBanner {
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:${context.packageName}")
                    }
                    context.startActivity(intent)
                }
            }
        }

        item {
            StatusCard(
                title = if (viewModel.isNotificationEnabled) "Listener Active" else "Listener Disabled",
                subtitle = if (viewModel.isNotificationEnabled) "Watching for phone alarms" else "Tap to enable notification access",
                icon = if (viewModel.isNotificationEnabled) Icons.Default.Check else Icons.Default.Info,
                color = if (viewModel.isNotificationEnabled) ComposeColor(0xFF4CAF50) else MaterialTheme.colorScheme.error,
                onClick = { if (!viewModel.isNotificationEnabled) context.startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")) }
            )
        }

        item {
            StatusCard(
                title = if (viewModel.isDndAccessGranted) "DND Sync Active" else "DND Sync Disabled",
                subtitle = if (viewModel.isDndAccessGranted) "Can sync DND to watch" else "Tap to grant DND access",
                icon = if (viewModel.isDndAccessGranted) Icons.Default.Check else Icons.Default.Warning,
                color = if (viewModel.isDndAccessGranted) ComposeColor(0xFF4CAF50) else MaterialTheme.colorScheme.error,
                onClick = { if (!viewModel.isDndAccessGranted) context.startActivity(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)) }
            )
        }

        item {
            OutlinedButton(
                onClick = { viewModel.testGlobalAlarm() },
                modifier = Modifier.fillMaxWidth().height(56.dp).padding(top = 8.dp)
            ) {
                Icon(Icons.Default.NotificationsActive, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Test Watch Connection")
            }
        }
        
        item { Spacer(modifier = Modifier.height(24.dp)) }
    }
}

@Composable
fun RulesTab(viewModel: MainViewModel, onEditRule: (AlertRule) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { Spacer(Modifier.height(8.dp)) }
        
        item {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("Master Catch-all", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("Every phone notification triggers watch alarm", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(
                    checked = viewModel.isGlobalCatchAllEnabled,
                    onCheckedChange = { viewModel.updateGlobalCatchAll(it) }
                )
            }
        }

        if (viewModel.isGlobalCatchAllEnabled) {
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Info, null, tint = MaterialTheme.colorScheme.error)
                        Text(
                            "Catch-all is active. Specific rules below are bypassed.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            modifier = Modifier.padding(start = 12.dp)
                        )
                    }
                }
            }
        }

        item { SectionHeader("Specific Triggers") }

        if (viewModel.alertRules.isEmpty()) {
            item {
                Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                    Text("No rules yet. Tap + to add one.", color = ComposeColor.Gray)
                }
            }
        }

        items(viewModel.alertRules) { rule ->
            val isDisabled = viewModel.isGlobalCatchAllEnabled
            RuleCard(
                rule = rule, 
                isDisabled = isDisabled,
                onDelete = { viewModel.deleteRule(rule.id) },
                onClick = { if (!isDisabled) onEditRule(rule) }
            )
        }
        
        item { Spacer(modifier = Modifier.height(80.dp)) }
    }
}

@Composable
fun SettingsTab(viewModel: MainViewModel, pickMainAudioLauncher: androidx.activity.result.ActivityResultLauncher<String>) {
    val context = LocalContext.current
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { SectionHeader("Alarm Audio & Vibration") }

        item {
            ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text("Default Alarm Sound", style = MaterialTheme.typography.titleSmall)
                    Text(viewModel.customSoundName, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(onClick = { pickMainAudioLauncher.launch("audio/*") }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                        Text("Change Audio File")
                    }
                    
                    HorizontalDivider(Modifier.padding(vertical = 16.dp), 0.5.dp, MaterialTheme.colorScheme.outlineVariant)
                    
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Override Watch DND", style = MaterialTheme.typography.bodyLarge)
                            Text("Ring even if watch is silenced", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(viewModel.isDndOverrideEnabled, { viewModel.updateDndOverride(it) })
                    }

                    HorizontalDivider(Modifier.padding(vertical = 16.dp), 0.5.dp, MaterialTheme.colorScheme.outlineVariant)

                    Text("Watch Volume (${(viewModel.alarmVolume * 100).toInt()}%)", style = MaterialTheme.typography.bodyLarge)
                    Slider(viewModel.alarmVolume, { viewModel.updateAlarmVolume(it) })
                    
                    HorizontalDivider(Modifier.padding(vertical = 16.dp), 0.5.dp, MaterialTheme.colorScheme.outlineVariant)

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Vibrate Only", style = MaterialTheme.typography.bodyLarge)
                            Text("No sound playback on watch", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(viewModel.globalVibrateOnly, { viewModel.updateGlobalVibrateOnly(it) })
                    }
                }
            }
        }

        item { SectionHeader("Automation") }

        item {
            var showGlobalQuietHoursDialog by remember { mutableStateOf(false) }
            StatusCard(
                title = "Global Quiet Hours",
                subtitle = if (viewModel.globalQuietHours.isEmpty()) "Notifications always sync" else "${viewModel.globalQuietHours.size} schedules active",
                icon = Icons.Default.Bedtime,
                color = if (viewModel.globalQuietHours.isNotEmpty()) MaterialTheme.colorScheme.primary else ComposeColor.Gray,
                onClick = { showGlobalQuietHoursDialog = true }
            )
            if (showGlobalQuietHoursDialog) {
                QuietHoursDialog(
                    initialSchedules = viewModel.globalQuietHours,
                    onDismiss = { showGlobalQuietHoursDialog = false },
                    onSave = { 
                        viewModel.updateGlobalQuietHours(it)
                        showGlobalQuietHoursDialog = false
                    }
                )
            }
        }

        item { SectionHeader("Advanced & Reliability") }

        item {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.VerifiedUser, null, tint = MaterialTheme.colorScheme.primary)
                    Column(Modifier.padding(start = 16.dp).weight(1f)) {
                        Text("High Reliability Mode", style = MaterialTheme.typography.titleSmall)
                        Text("Prevents system from killing the bridge on Samsung/OnePlus/Xiaomi.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(viewModel.isHighReliabilityEnabled, { viewModel.updateHighReliability(it) })
                }
            }
        }

        item {
            OutlinedCard(
                onClick = {
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:${context.packageName}")
                    }
                    context.startActivity(intent)
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (!viewModel.isBatteryOptimized) Icons.Default.BatteryFull else Icons.Default.BatteryAlert,
                        null,
                        tint = if (!viewModel.isBatteryOptimized) ComposeColor(0xFF4CAF50) else ComposeColor(0xFFFF9800)
                    )
                    Column(Modifier.padding(start = 16.dp)) {
                        Text("Battery Optimization", style = MaterialTheme.typography.titleSmall)
                        Text("Status: ${if (viewModel.isBatteryOptimized) "Optimized (May fail)" else "Unrestricted (Best)"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        
        item { Spacer(modifier = Modifier.height(24.dp)) }
    }
}

@Composable
fun TrialBanner(hoursLeft: Int, onUnlockClick: () -> Unit) {
    val color = if (hoursLeft < 12) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    Card(
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Timer, null, tint = color)
            Column(Modifier.padding(start = 16.dp).weight(1f)) {
                Text(if (hoursLeft > 0) "Trial ends in $hoursLeft hours" else "Trial expired", fontWeight = FontWeight.Bold, color = color)
                Text("Unlock lifetime access for $1.49", style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onUnlockClick) {
                Text("Unlock")
            }
        }
    }
}

@Composable
fun BatteryWarningBanner(onFixClick: () -> Unit) {
    val color = ComposeColor(0xFFFF9800) // Orange
    Card(
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.BatteryAlert, null, tint = color)
            Column(Modifier.padding(start = 16.dp).weight(1f)) {
                Text("Reliability Warning", fontWeight = FontWeight.Bold, color = color)
                Text("Battery optimization may kill the bridge. Tap to disable.", style = MaterialTheme.typography.bodySmall)
            }
            Button(onClick = onFixClick, colors = ButtonDefaults.buttonColors(containerColor = color)) {
                Text("Fix")
            }
        }
    }
}

@Composable
fun StatusCard(title: String, subtitle: String, icon: ImageVector, color: ComposeColor, onClick: () -> Unit) {
    ElevatedCard(modifier = Modifier.fillMaxWidth().clickable { onClick() }) {
        Row(Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = CircleShape, color = color.copy(alpha = 0.1f), modifier = Modifier.size(48.dp)) {
                Box(contentAlignment = Alignment.Center) { Icon(icon, null, tint = color) }
            }
            Column(Modifier.padding(start = 16.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun SectionHeader(text: String) {
    Text(text = text, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp, bottom = 4.dp))
}

@Composable
fun RuleCard(rule: AlertRule, isDisabled: Boolean, onDelete: () -> Unit, onClick: () -> Unit) {
    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(enabled = !isDisabled) { onClick() }
            .alpha(if (isDisabled) 0.4f else 1.0f),
        colors = CardDefaults.outlinedCardColors()
    ) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(if (rule.sender.isNotEmpty()) "From: ${rule.sender}" else "Any Sender", fontWeight = FontWeight.Bold)
                if (rule.keyword.isNotEmpty()) Text("Contains: ${rule.keyword}", style = MaterialTheme.typography.bodySmall)
                Text("Sound: ${rule.soundName}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                val durationText = if (rule.playDurationSeconds == -1) "Forever" else "${rule.playDurationSeconds}s"
                Text("Vol: ${(rule.volume * 100).toInt()}% | DND: ${if (rule.overrideDnd) "ON" else "OFF"} | Duration: $durationText | Vib: ${rule.vibration} ${if (rule.vibrateOnly) "(Only)" else ""}", style = MaterialTheme.typography.bodySmall, color = ComposeColor.Gray)
            }
            IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, null, tint = ComposeColor.Gray) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RuleEditorDialog(rule: AlertRule, viewModel: MainViewModel, onDismiss: () -> Unit, onSave: (AlertRule) -> Unit) {
    val context = LocalContext.current
    var sender by remember { mutableStateOf(rule.sender) }
    var keyword by remember { mutableStateOf(rule.keyword) }
    var volume by remember { mutableFloatStateOf(rule.volume) }
    var dnd by remember { mutableStateOf(rule.overrideDnd) }
    var soundName by remember { mutableStateOf(rule.soundName) }
    var vibration by remember { mutableStateOf(rule.vibration) }
    var vibrateOnly by remember { mutableStateOf(rule.vibrateOnly) }
    var untilDismissed by remember { mutableStateOf(rule.playDurationSeconds == -1) }
    var playDurationSeconds by remember { mutableIntStateOf(if (rule.playDurationSeconds == -1) 30 else rule.playDurationSeconds) }
    var cooldownMinutes by remember { mutableIntStateOf(rule.cooldownMinutes) }
    var activeSchedules by remember { mutableStateOf(rule.activeSchedules) }

    val contactPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickContact()) { uri: Uri? ->
        uri?.let {
            context.contentResolver.query(it, null, null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val nameIndex = c.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)
                    if (nameIndex >= 0) sender = c.getString(nameIndex)
                }
            }
        }
    }

    val ruleSoundPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        uri?.let {
            val name = getFileName(context, it)
            soundName = name
            Toast.makeText(context, "Syncing rule sound...", Toast.LENGTH_SHORT).show()
            val watchFileName = "rule_${name.replace("[^a-zA-Z0-9.-]".toRegex(), "_")}"
            viewModel.wearableRepository.sendFile("${WatchmanPaths.RULE_SOUND_FILE}/$watchFileName", it) { success ->
                (context as ComponentActivity).runOnUiThread {
                    val msg = if (success) "Rule sound synced!" else "Rule sound sync failed"
                    Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (rule.sender.isEmpty() && rule.keyword.isEmpty()) "New Rule" else "Edit Rule") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = sender, 
                    onValueChange = { sender = it }, 
                    label = { Text("Sender") }, 
                    modifier = Modifier.fillMaxWidth(),
                    trailingIcon = {
                        IconButton(onClick = { contactPicker.launch(null) }) {
                            Icon(Icons.Default.ContactPage, "Pick Contact")
                        }
                    }
                )
                OutlinedTextField(value = keyword, onValueChange = { keyword = it }, label = { Text("Keyword") }, modifier = Modifier.fillMaxWidth())
                
                HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)
                
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.clickable { ruleSoundPicker.launch("audio/*") }) {
                    Icon(Icons.Default.MusicNote, null, tint = MaterialTheme.colorScheme.primary)
                    Column(Modifier.padding(start = 12.dp)) {
                        Text("Custom Sound", style = MaterialTheme.typography.bodyMedium)
                        Text(soundName, style = MaterialTheme.typography.bodySmall, color = ComposeColor.Gray)
                    }
                }

                Text("Volume: ${(volume * 100).toInt()}%", style = MaterialTheme.typography.bodySmall)
                Slider(value = volume, onValueChange = { volume = it })

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = dnd, onCheckedChange = { dnd = it })
                    Text("Override Watch DND")
                }

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = vibrateOnly, onCheckedChange = { vibrateOnly = it })
                    Text("Vibrate Only (No Sound)")
                }

                var expandRuleVibration by remember { mutableStateOf(false) }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Pattern: ", style = MaterialTheme.typography.bodyMedium)
                    Box {
                        OutlinedButton(onClick = { expandRuleVibration = true }) {
                            Text(vibration)
                        }
                        DropdownMenu(expanded = expandRuleVibration, onDismissRequest = { expandRuleVibration = false }) {
                            listOf("Standard", "Heartbeat", "Rapid").forEach { pattern ->
                                DropdownMenuItem(
                                    text = { Text(pattern) },
                                    onClick = { 
                                        vibration = pattern
                                        expandRuleVibration = false 
                                    }
                                )
                            }
                        }
                    }
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

                Text("Playback Duration", style = MaterialTheme.typography.labelLarge)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = untilDismissed, onCheckedChange = { untilDismissed = it })
                    Text("Play until dismissed")
                }
                if (!untilDismissed) {
                    Column(modifier = Modifier.padding(start = 12.dp)) {
                        Text("Stop after: $playDurationSeconds seconds", style = MaterialTheme.typography.bodySmall)
                        Slider(
                            value = playDurationSeconds.toFloat(),
                            onValueChange = { playDurationSeconds = it.toInt() },
                            valueRange = 1f..60f,
                            steps = 59
                        )
                    }
                }

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

                Text("Rule Constraints", style = MaterialTheme.typography.labelLarge)
                
                Column {
                    Text("Cooldown: ${if (cooldownMinutes == 0) "Disabled" else "$cooldownMinutes minutes"}", style = MaterialTheme.typography.bodySmall)
                    Slider(
                        value = cooldownMinutes.toFloat(),
                        onValueChange = { cooldownMinutes = it.toInt() },
                        valueRange = 0f..60f,
                        steps = 11
                    )
                }

                SectionHeader("Active Schedules")
                Text("If schedules are set, the rule only runs during these times.", style = MaterialTheme.typography.bodySmall)
                TimeWindowList(
                    schedules = activeSchedules,
                    onSchedulesChanged = { activeSchedules = it },
                    defaultIsBlackout = false
                )

                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)
                
                OutlinedButton(
                    onClick = {
                        val finalDuration = if (untilDismissed) -1 else playDurationSeconds
                        viewModel.testAlertRule(rule.copy(sender = sender, keyword = keyword, volume = volume, overrideDnd = dnd, soundName = soundName, playDurationSeconds = finalDuration, vibration = vibration, vibrateOnly = vibrateOnly, cooldownMinutes = cooldownMinutes, activeSchedules = activeSchedules))
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.NotificationsActive, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Test Rule on Watch")
                }
            }
        },
        confirmButton = {
            Button(
                enabled = sender.isNotEmpty() || keyword.isNotEmpty(),
                onClick = { 
                    val finalDuration = if (untilDismissed) -1 else playDurationSeconds
                    onSave(rule.copy(sender = sender, keyword = keyword, volume = volume, overrideDnd = dnd, soundName = soundName, playDurationSeconds = finalDuration, vibration = vibration, vibrateOnly = vibrateOnly, cooldownMinutes = cooldownMinutes, activeSchedules = activeSchedules)) 
                }
            ) {
                Text("Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuietHoursDialog(initialSchedules: List<TimeWindow>, onDismiss: () -> Unit, onSave: (List<TimeWindow>) -> Unit) {
    var schedules by remember { mutableStateOf(initialSchedules) }
    
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Global Quiet Hours") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(16.dp), modifier = Modifier.fillMaxWidth()) {
                Text("During these times, NO notifications will be bridged to the watch.", style = MaterialTheme.typography.bodySmall)
                
                TimeWindowList(
                    schedules = schedules,
                    onSchedulesChanged = { schedules = it },
                    defaultIsBlackout = true
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(schedules) }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TimeWindowList(schedules: List<TimeWindow>, onSchedulesChanged: (List<TimeWindow>) -> Unit, defaultIsBlackout: Boolean) {
    val context = LocalContext.current
    
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        schedules.forEachIndexed { index, window ->
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        val startTime = String.format("%02d:%02d", window.startHour, window.startMinute)
                        val endTime = String.format("%02d:%02d", window.endHour, window.endMinute)
                        Text("$startTime - $endTime", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                        
                        val days = if (window.daysOfWeek.size == 7) "Every day" 
                                  else if (window.daysOfWeek.containsAll(listOf(2,3,4,5,6)) && window.daysOfWeek.size == 5) "Weekdays"
                                  else window.daysOfWeek.joinToString(", ") { dayNum ->
                                      when(dayNum) {
                                          1 -> "Sun"; 2 -> "Mon"; 3 -> "Tue"; 4 -> "Wed"; 5 -> "Thu"; 6 -> "Fri"; 7 -> "Sat"; else -> ""
                                      }
                                  }
                        Text(days, style = MaterialTheme.typography.bodySmall)
                    }
                    IconButton(onClick = {
                        val newList = schedules.toMutableList()
                        newList.removeAt(index)
                        onSchedulesChanged(newList)
                    }) {
                        Icon(Icons.Default.Close, null, modifier = Modifier.size(16.dp))
                    }
                }
            }
        }
        
        OutlinedButton(
            onClick = {
                val calendar = java.util.Calendar.getInstance()
                val hour = calendar.get(java.util.Calendar.HOUR_OF_DAY)
                val minute = calendar.get(java.util.Calendar.MINUTE)
                
                android.app.TimePickerDialog(context, { _, h, m ->
                    android.app.TimePickerDialog(context, { _, eh, em ->
                        val newWindow = TimeWindow(
                            startHour = h,
                            startMinute = m,
                            endHour = eh,
                            endMinute = em,
                            daysOfWeek = listOf(1, 2, 3, 4, 5, 6, 7),
                            isBlackout = defaultIsBlackout
                        )
                        onSchedulesChanged(schedules + newWindow)
                    }, (h + 8) % 24, m, true).apply { 
                        setTitle("End Time")
                        show() 
                    }
                }, hour, minute, true).apply { 
                    setTitle("Start Time")
                    show() 
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Default.Add, null)
            Spacer(Modifier.width(8.dp))
            Text("Add Time Window")
        }
    }
}

private fun getFileName(context: Context, uri: Uri): String {
    var name = "unknown_file"
    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val nameIndex = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
        if (nameIndex >= 0 && cursor.moveToFirst()) name = cursor.getString(nameIndex)
    }
    return name
}
