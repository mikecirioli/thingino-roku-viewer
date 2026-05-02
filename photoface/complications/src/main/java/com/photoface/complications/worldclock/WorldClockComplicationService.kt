package com.photoface.complications.worldclock

import android.content.ComponentName
import android.content.Context
import android.graphics.drawable.Icon
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import com.photoface.complications.R
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * Complication data source that displays time in a selected timezone.
 * User can configure the timezone via WorldClockConfigActivity.
 */
class WorldClockComplicationService : ComplicationDataSourceService() {

    private val prefs by lazy {
        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        return when (type) {
            ComplicationType.SHORT_TEXT -> createShortTextData("14:30", "Tokyo")
            ComplicationType.LONG_TEXT -> createLongTextData("14:30", "Tokyo")
            else -> null
        }
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val tzId = prefs.getString(KEY_TIMEZONE, DEFAULT_TIMEZONE) ?: DEFAULT_TIMEZONE
        val cityName = prefs.getString(KEY_CITY_NAME, "New York") ?: "New York"

        val zoneId = try {
            ZoneId.of(tzId)
        } catch (e: Exception) {
            ZoneId.of(DEFAULT_TIMEZONE)
        }

        val now = ZonedDateTime.now(zoneId)
        val timeFormatter = DateTimeFormatter.ofPattern("H:mm")
        val timeStr = now.format(timeFormatter)

        val data = when (request.complicationType) {
            ComplicationType.SHORT_TEXT -> createShortTextData(timeStr, cityName)
            ComplicationType.LONG_TEXT -> createLongTextData(timeStr, cityName)
            else -> null
        }

        listener.onComplicationData(data)
    }

    private fun createShortTextData(time: String, city: String): ShortTextComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder(time).build(),
            contentDescription = PlainComplicationText.Builder("$city: $time").build()
        )
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, R.drawable.ic_world_clock)).build()
            )
            .setTitle(PlainComplicationText.Builder(city).build())
            .build()
    }

    private fun createLongTextData(time: String, city: String): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder("$city $time").build(),
            contentDescription = PlainComplicationText.Builder("$city time: $time").build()
        )
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, R.drawable.ic_world_clock)).build()
            )
            .build()
    }

    companion object {
        private const val PREFS_NAME = "world_clock"
        private const val KEY_TIMEZONE = "timezone"
        private const val KEY_CITY_NAME = "city_name"
        private const val DEFAULT_TIMEZONE = "America/New_York"

        fun requestUpdate(context: Context) {
            val component = ComponentName(context, WorldClockComplicationService::class.java)
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(context, component)
                .requestUpdateAll()
        }
    }
}
