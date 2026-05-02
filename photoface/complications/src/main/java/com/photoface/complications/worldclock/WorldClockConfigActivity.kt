package com.photoface.complications.worldclock

import androidx.activity.ComponentActivity
import android.content.ComponentName
import android.content.Context
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import com.photoface.complications.R

/**
 * Configuration activity for World Clock complication.
 * Allows users to select which timezone to display.
 */
class WorldClockConfigActivity : ComponentActivity() {

    private val prefs by lazy {
        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    companion object {
        private const val PREFS_NAME = "world_clock"
        private const val KEY_TIMEZONE = "timezone"
        private const val KEY_CITY_NAME = "city_name"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(createConfigView())
    }

    private fun createConfigView(): View {
        val scrollView = ScrollView(this).apply {
            setBackgroundColor(0xFF000000.toInt())
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }

        // Title
        val title = TextView(this).apply {
            text = "World Clock"
            textSize = 18f
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 0, 0, 16)
        }
        container.addView(title)

        val currentTz = prefs.getString(KEY_TIMEZONE, "America/New_York")

        // Timezone options organized by region
        val timezones = listOf(
            TimezoneOption("America/New_York", "New York", "UTC-5/-4"),
            TimezoneOption("America/Chicago", "Chicago", "UTC-6/-5"),
            TimezoneOption("America/Denver", "Denver", "UTC-7/-6"),
            TimezoneOption("America/Los_Angeles", "Los Angeles", "UTC-8/-7"),
            TimezoneOption("America/Sao_Paulo", "São Paulo", "UTC-3"),
            TimezoneOption("Europe/London", "London", "UTC+0/+1"),
            TimezoneOption("Europe/Paris", "Paris", "UTC+1/+2"),
            TimezoneOption("Europe/Berlin", "Berlin", "UTC+1/+2"),
            TimezoneOption("Europe/Madrid", "Madrid", "UTC+1/+2"),
            TimezoneOption("Europe/Moscow", "Moscow", "UTC+3"),
            TimezoneOption("Asia/Dubai", "Dubai", "UTC+4"),
            TimezoneOption("Asia/Kolkata", "Mumbai", "UTC+5:30"),
            TimezoneOption("Asia/Singapore", "Singapore", "UTC+8"),
            TimezoneOption("Asia/Hong_Kong", "Hong Kong", "UTC+8"),
            TimezoneOption("Asia/Tokyo", "Tokyo", "UTC+9"),
            TimezoneOption("Australia/Sydney", "Sydney", "UTC+10/+11"),
        )

        for (tz in timezones) {
            val row = createOptionRow(tz, tz.zoneId == currentTz)
            row.setOnClickListener {
                selectTimezone(tz)
            }
            container.addView(row)
        }

        scrollView.addView(container)
        return scrollView
    }

    private fun createOptionRow(option: TimezoneOption, isSelected: Boolean): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 16, 16, 16)
            if (isSelected) {
                setBackgroundColor(0xFF333333.toInt())
            }
        }

        val cityText = TextView(this).apply {
            text = option.cityName
            textSize = 16f
            setTextColor(if (isSelected) 0xFF4CAF50.toInt() else 0xFFFFFFFF.toInt())
        }
        row.addView(cityText)

        val offsetText = TextView(this).apply {
            text = option.utcOffset
            textSize = 12f
            setTextColor(0xFFAAAAAA.toInt())
        }
        row.addView(offsetText)

        return row
    }

    private fun selectTimezone(option: TimezoneOption) {
        // Save selection
        prefs.edit()
            .putString(KEY_TIMEZONE, option.zoneId)
            .putString(KEY_CITY_NAME, option.cityName)
            .apply()

        // Request complication update
        val component = ComponentName(this, WorldClockComplicationService::class.java)
        ComplicationDataSourceUpdateRequester.create(this, component).requestUpdateAll()

        // Close activity
        setResult(RESULT_OK)
        finish()
    }

    data class TimezoneOption(
        val zoneId: String,
        val cityName: String,
        val utcOffset: String
    )
}
