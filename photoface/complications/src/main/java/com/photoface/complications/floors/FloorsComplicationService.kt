package com.photoface.complications.floors

import com.photoface.complications.R

import android.content.ComponentName
import android.content.Intent
import android.app.PendingIntent
import android.graphics.drawable.Icon
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import kotlinx.coroutines.*

/**
 * Complication data source that provides floors climbed data.
 * This service can be used by any watch face that supports complications.
 */
class FloorsComplicationService : ComplicationDataSourceService() {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    override fun onComplicationActivated(complicationInstanceId: Int, type: ComplicationType) {
        // Called when a complication is activated
    }

    override fun onComplicationDeactivated(complicationInstanceId: Int) {
        // Called when a complication is deactivated
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        return when (type) {
            ComplicationType.SHORT_TEXT -> createShortTextData(12)
            ComplicationType.RANGED_VALUE -> createRangedValueData(12, 20)
            ComplicationType.LONG_TEXT -> createLongTextData(12)
            else -> null
        }
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        scope.launch {
            val floors = getFloorsClimbed()
            val goal = getDailyGoal()

            val data = when (request.complicationType) {
                ComplicationType.SHORT_TEXT -> {
                    if (floors != null) createShortTextData(floors)
                    else createNoDataShortText()
                }
                ComplicationType.RANGED_VALUE -> {
                    if (floors != null) createRangedValueData(floors, goal)
                    else createNoDataRangedValue(goal)
                }
                ComplicationType.LONG_TEXT -> {
                    if (floors != null) createLongTextData(floors)
                    else createNoDataLongText()
                }
                else -> null
            }

            withContext(Dispatchers.Main) {
                listener.onComplicationData(data)
            }
        }
    }

    private fun createShortTextData(floors: Int): ShortTextComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("$floors").build(),
            contentDescription = PlainComplicationText.Builder("$floors floors climbed").build()
        )
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
            )
            .build()
    }

    private fun createRangedValueData(floors: Int, goal: Int): RangedValueComplicationData {
        return RangedValueComplicationData.Builder(
            value = floors.toFloat(),
            min = 0f,
            max = goal.toFloat(),
            contentDescription = PlainComplicationText.Builder("$floors of $goal floors").build()
        )
            .setText(PlainComplicationText.Builder("$floors").build())
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
            )
            .build()
    }

    private fun createLongTextData(floors: Int): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder("$floors floors").build(),
            contentDescription = PlainComplicationText.Builder("$floors floors climbed today").build()
        )
            .setTitle(PlainComplicationText.Builder("Today").build())
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
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

    private fun createNoDataShortText(): ShortTextComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("--").build(),
            contentDescription = PlainComplicationText.Builder("No floors data available").build()
        )
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
            )
            .build()
    }

    private fun createNoDataRangedValue(goal: Int): RangedValueComplicationData {
        return RangedValueComplicationData.Builder(
            value = 0f,
            min = 0f,
            max = goal.toFloat(),
            contentDescription = PlainComplicationText.Builder("No floors data available").build()
        )
            .setText(PlainComplicationText.Builder("--").build())
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
            )
            .build()
    }

    private fun createNoDataLongText(): LongTextComplicationData {
        return LongTextComplicationData.Builder(
            text = PlainComplicationText.Builder("No data").build(),
            contentDescription = PlainComplicationText.Builder("No floors data available").build()
        )
            .setTitle(PlainComplicationText.Builder("Floors").build())
            .setTapAction(getPermissionTapAction())
            .setMonochromaticImage(
                MonochromaticImage.Builder(
                    Icon.createWithResource(this, R.drawable.ic_floors)
                ).build()
            )
            .build()
    }

    /**
     * Get floors climbed from Health Services, or null if no data available.
     */
    private fun getFloorsClimbed(): Int? {
        val repository = FloorDataRepository.getInstance(this)
        return repository.getFloorsClimbed()
    }

    /**
     * Get daily floors goal.
     */
    private fun getDailyGoal(): Int {
        // Default goal, could be made configurable
        return 10
    }

    override fun onDestroy() {
        super.onDestroy()
        scope.cancel()
    }

    companion object {
        /**
         * Request an update for all complications provided by this service.
         */
        fun requestUpdate(context: android.content.Context) {
            val component = ComponentName(context, FloorsComplicationService::class.java)
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(context, component)
                .requestUpdateAll()
        }
    }
}
