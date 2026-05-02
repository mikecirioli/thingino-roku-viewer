package com.watchman.bridge

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.watchman.bridge.data.SharedPrefsSettingsRepository

class SnoozeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settingsRepository = SharedPrefsSettingsRepository(this)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Box(contentAlignment = Alignment.Center, modifier = Modifier.padding(16.dp)) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("Snooze Alerts", style = MaterialTheme.typography.headlineSmall)
                            Spacer(modifier = Modifier.height(24.dp))
                            
                            SnoozeButton(minutes = 15) { setSnooze(it, settingsRepository) }
                            SnoozeButton(minutes = 60) { setSnooze(it, settingsRepository) }
                            SnoozeButton(minutes = 180) { setSnooze(it, settingsRepository) }
                            
                            Spacer(modifier = Modifier.height(16.dp))
                            
                            OutlinedButton(onClick = {
                                settingsRepository.setSnoozeUntil(0L)
                                Toast.makeText(applicationContext, "Snooze canceled", Toast.LENGTH_SHORT).show()
                                finish()
                            }) {
                                Text("Cancel Snooze")
                            }
                        }
                    }
                }
            }
        }
    }

    @Composable
    private fun SnoozeButton(minutes: Int, onClick: (Long) -> Unit) {
        Button(
            onClick = { onClick(System.currentTimeMillis() + minutes * 60 * 1000L) },
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
        ) {
            val label = if (minutes < 60) "$minutes minutes" else "${minutes/60} hour(s)"
            Text(label)
        }
    }

    private fun setSnooze(timestamp: Long, repo: SharedPrefsSettingsRepository) {
        repo.setSnoozeUntil(timestamp)
        val duration = (timestamp - System.currentTimeMillis()) / (1000 * 60)
        Toast.makeText(this, "Snoozed for $duration minutes", Toast.LENGTH_SHORT).show()
        finish()
    }
}
