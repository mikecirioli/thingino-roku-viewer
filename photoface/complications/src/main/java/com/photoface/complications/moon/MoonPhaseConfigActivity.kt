package com.photoface.complications.moon

import android.content.ComponentName
import android.content.Context
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester

/**
 * Configuration activity for Moon Phase complication.
 * Allows users to select the display size of the moon graphic.
 */
class MoonPhaseConfigActivity : ComponentActivity() {

    private val prefs by lazy {
        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    companion object {
        private const val PREFS_NAME = "moon_phase"
        private const val KEY_SIZE = "size"
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

        val title = TextView(this).apply {
            text = "Moon Size"
            textSize = 18f
            setTextColor(0xFFFFFFFF.toInt())
            setPadding(0, 0, 0, 16)
        }
        container.addView(title)

        val currentSize = prefs.getString(KEY_SIZE, MoonPhaseComplicationService.SIZE_LARGE)

        val options = listOf(
            SizeOption(MoonPhaseComplicationService.SIZE_LARGE, "Large", "Full complication area"),
            SizeOption(MoonPhaseComplicationService.SIZE_MEDIUM, "Medium", "Centered with margin"),
            SizeOption(MoonPhaseComplicationService.SIZE_SMALL, "Small", "Compact centered"),
        )

        for (option in options) {
            val row = createOptionRow(option, option.id == currentSize)
            row.setOnClickListener {
                selectSize(option)
            }
            container.addView(row)
        }

        scrollView.addView(container)
        return scrollView
    }

    private fun createOptionRow(option: SizeOption, isSelected: Boolean): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 16, 16, 16)
            if (isSelected) {
                setBackgroundColor(0xFF333333.toInt())
            }
        }

        val nameText = TextView(this).apply {
            text = option.label
            textSize = 16f
            setTextColor(if (isSelected) 0xFF4CAF50.toInt() else 0xFFFFFFFF.toInt())
        }
        row.addView(nameText)

        val descText = TextView(this).apply {
            text = option.description
            textSize = 12f
            setTextColor(0xFFAAAAAA.toInt())
        }
        row.addView(descText)

        return row
    }

    private fun selectSize(option: SizeOption) {
        prefs.edit()
            .putString(KEY_SIZE, option.id)
            .apply()

        val component = ComponentName(this, MoonPhaseComplicationService::class.java)
        ComplicationDataSourceUpdateRequester.create(this, component).requestUpdateAll()

        setResult(RESULT_OK)
        finish()
    }

    data class SizeOption(
        val id: String,
        val label: String,
        val description: String
    )
}
