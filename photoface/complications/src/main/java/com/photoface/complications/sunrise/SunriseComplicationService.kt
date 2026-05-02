package com.photoface.complications.sunrise

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.app.PendingIntent
import com.photoface.complications.floors.PermissionActivity
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.drawable.Icon
import android.location.Location
import android.location.LocationManager
import androidx.core.content.ContextCompat
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import com.photoface.complications.R
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.*

/**
 * Complication data source that provides sunrise and sunset times.
 * Uses astronomical calculations - no API needed.
 * Requires location permission; shows "No location" when unavailable.
 */
class SunriseComplicationService : ComplicationDataSourceService() {

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        return when (type) {
            ComplicationType.SHORT_TEXT -> createShortTextData("6:42", true)
            ComplicationType.LONG_TEXT -> createLongTextData("6:42", "17:35")
            else -> null
        }
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val location = getLastKnownLocation()

        if (location == null) {
            val data = when (request.complicationType) {
                ComplicationType.SHORT_TEXT -> createNoLocationShortText()
                ComplicationType.LONG_TEXT -> createNoLocationLongText()
                else -> null
            }
            listener.onComplicationData(data)
            return
        }

        val (sunrise, sunset) = calculateSunTimes(
            location.latitude,
            location.longitude,
            LocalDate.now()
        )

        val now = LocalTime.now()
        val isBeforeSunset = now.isBefore(sunset)
        val nextEvent = if (now.isBefore(sunrise)) sunrise else if (isBeforeSunset) sunset else sunrise
        val isSunrise = now.isBefore(sunrise) || !isBeforeSunset

        val timeFormatter = DateTimeFormatter.ofPattern("H:mm")

        val data = when (request.complicationType) {
            ComplicationType.SHORT_TEXT -> createShortTextData(nextEvent.format(timeFormatter), isSunrise)
            ComplicationType.LONG_TEXT -> createLongTextData(
                sunrise.format(timeFormatter),
                sunset.format(timeFormatter)
            )
            else -> null
        }

        listener.onComplicationData(data)
    }

    private fun createShortTextData(time: String, isSunrise: Boolean): ShortTextComplicationData {
        val icon = if (isSunrise) R.drawable.ic_sunrise else R.drawable.ic_sunset
        val desc = if (isSunrise) "Sunrise at $time" else "Sunset at $time"

        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder(time).build(),
            contentDescription = PlainComplicationText.Builder(desc).build()
        )
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, icon)).build()
            )
            .build()
    }

    private fun createLongTextData(sunrise: String, sunset: String): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder("↑$sunrise  ↓$sunset").build(),
            contentDescription = PlainComplicationText.Builder("Sunrise $sunrise, Sunset $sunset").build()
        )
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, R.drawable.ic_sunrise)).build()
            )
            .build()
    }


    private fun getPermissionTapAction(): PendingIntent {
        val intent = Intent(this, PermissionActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    private fun createNoLocationShortText(): ShortTextComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("--:--").build(),
            contentDescription = PlainComplicationText.Builder("No location available for sunrise/sunset").build()
        )
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, R.drawable.ic_sunrise)).build()
            )
            .build()
    }

    private fun createNoLocationLongText(): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder("No location").build(),
            contentDescription = PlainComplicationText.Builder("No location available for sunrise/sunset").build()
        )
            .setMonochromaticImage(
                MonochromaticImage.Builder(Icon.createWithResource(this, R.drawable.ic_sunrise)).build()
            )
            .build()
    }

    private fun getLastKnownLocation(): Location? {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
            != PackageManager.PERMISSION_GRANTED) {
            return null
        }

        val locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        return locationManager.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)
    }

    /**
     * Calculate sunrise and sunset times using the NOAA solar calculator algorithm.
     */
    private fun calculateSunTimes(lat: Double, lon: Double, date: LocalDate): Pair<LocalTime, LocalTime> {
        val dayOfYear = date.dayOfYear

        // Fractional year (radians)
        val gamma = 2 * PI / 365 * (dayOfYear - 1 + 0.5)

        // Equation of time (minutes)
        val eqTime = 229.18 * (0.000075 + 0.001868 * cos(gamma) - 0.032077 * sin(gamma)
                - 0.014615 * cos(2 * gamma) - 0.040849 * sin(2 * gamma))

        // Solar declination (radians)
        val decl = 0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma) -
                0.006758 * cos(2 * gamma) + 0.000907 * sin(2 * gamma) -
                0.002697 * cos(3 * gamma) + 0.00148 * sin(3 * gamma)

        // Hour angle (degrees)
        val latRad = Math.toRadians(lat)
        val zenith = Math.toRadians(90.833) // Official sunrise/sunset

        val cosHa = (cos(zenith) / (cos(latRad) * cos(decl)) - tan(latRad) * tan(decl))
            .coerceIn(-1.0, 1.0)
        val ha = Math.toDegrees(acos(cosHa))

        // Get timezone offset
        val zoneOffset = ZoneId.systemDefault().rules.getOffset(date.atStartOfDay(ZoneId.systemDefault()).toInstant())
        val tzOffsetMinutes = zoneOffset.totalSeconds / 60.0

        // Sunrise and sunset in minutes from midnight UTC
        val sunriseMinutes = 720 - 4 * (lon + ha) - eqTime + tzOffsetMinutes
        val sunsetMinutes = 720 - 4 * (lon - ha) - eqTime + tzOffsetMinutes

        return Pair(
            minutesToLocalTime(sunriseMinutes),
            minutesToLocalTime(sunsetMinutes)
        )
    }

    private fun minutesToLocalTime(minutes: Double): LocalTime {
        val normalizedMinutes = ((minutes % 1440) + 1440) % 1440
        val hours = (normalizedMinutes / 60).toInt()
        val mins = (normalizedMinutes % 60).toInt()
        return LocalTime.of(hours.coerceIn(0, 23), mins.coerceIn(0, 59))
    }

    companion object {
        fun requestUpdate(context: Context) {
            val component = ComponentName(context, SunriseComplicationService::class.java)
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(context, component)
                .requestUpdateAll()
        }
    }
}
