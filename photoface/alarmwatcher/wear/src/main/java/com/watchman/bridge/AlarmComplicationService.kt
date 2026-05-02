package com.watchman.bridge

import android.content.ComponentName
import android.content.Context
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import java.text.SimpleDateFormat
import java.util.*

class AlarmComplicationService : ComplicationDataSourceService() {

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        if (type != ComplicationType.SHORT_TEXT) return null
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("07:00").build(),
            contentDescription = PlainComplicationText.Builder("Next Alarm").build()
        ).setTitle(PlainComplicationText.Builder("ALM").build())
            .build()
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val prefs = getSharedPreferences("WatchmanPrefs", Context.MODE_PRIVATE)
        val timestamp = prefs.getLong("next_alarm_time", 0L)

        val complicationData = if (timestamp > System.currentTimeMillis()) {
            val date = Date(timestamp)
            val sdf = SimpleDateFormat("HH:mm", Locale.getDefault())
            val timeStr = sdf.format(date)

            ShortTextComplicationData.Builder(
                text = PlainComplicationText.Builder(timeStr).build(),
                contentDescription = PlainComplicationText.Builder("Next Alarm: $timeStr").build()
            ).setTitle(PlainComplicationText.Builder("ALM").build())
                .build()
        } else {
            ShortTextComplicationData.Builder(
                text = PlainComplicationText.Builder("--:--").build(),
                contentDescription = PlainComplicationText.Builder("No Alarm").build()
            ).setTitle(PlainComplicationText.Builder("ALM").build())
                .build()
        }

        listener.onComplicationData(complicationData)
    }

    companion object {
        fun triggerUpdate(context: Context) {
            val componentName = ComponentName(context, AlarmComplicationService::class.java)
            ComplicationDataSourceUpdateRequester.create(context, componentName).requestUpdateAll()
        }
    }
}
