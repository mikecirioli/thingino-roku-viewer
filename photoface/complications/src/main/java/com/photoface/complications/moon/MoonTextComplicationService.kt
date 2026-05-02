package com.photoface.complications.moon

import android.content.ComponentName
import android.content.Context
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import java.time.LocalDate

/**
 * Moon phase complication that displays the phase as text (SHORT_TEXT/LONG_TEXT).
 * For image-based display, see MoonPhaseComplicationService.
 */
class MoonTextComplicationService : ComplicationDataSourceService() {

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        val phase = 0.4
        val phaseName = MoonPhaseUtil.getPhaseName(phase)
        val shortName = MoonPhaseUtil.getShortName(phase)

        return when (type) {
            ComplicationType.SHORT_TEXT -> createShortTextData(shortName, phaseName)
            ComplicationType.LONG_TEXT -> createLongTextData(phaseName)
            else -> null
        }
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val phase = MoonPhaseUtil.calculateMoonPhase(LocalDate.now())
        val phaseName = MoonPhaseUtil.getPhaseName(phase)
        val shortName = MoonPhaseUtil.getShortName(phase)

        val data = when (request.complicationType) {
            ComplicationType.SHORT_TEXT -> createShortTextData(shortName, phaseName)
            ComplicationType.LONG_TEXT -> createLongTextData(phaseName)
            else -> null
        }

        listener.onComplicationData(data)
    }

    private fun createShortTextData(shortName: String, phaseName: String): ShortTextComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder(shortName).build(),
            contentDescription = PlainComplicationText.Builder(phaseName).build()
        ).build()
    }

    private fun createLongTextData(phaseName: String): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder(phaseName).build(),
            contentDescription = PlainComplicationText.Builder(phaseName).build()
        ).build()
    }

    companion object {
        fun requestUpdate(context: Context) {
            val component = ComponentName(context, MoonTextComplicationService::class.java)
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(context, component)
                .requestUpdateAll()
        }
    }
}
