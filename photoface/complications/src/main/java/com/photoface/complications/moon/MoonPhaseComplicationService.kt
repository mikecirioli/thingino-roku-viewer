package com.photoface.complications.moon

import android.content.ComponentName
import android.content.Context
import android.graphics.*
import android.graphics.drawable.Icon
import androidx.wear.watchface.complications.data.*
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import java.time.LocalDate
import kotlin.math.*

/**
 * Moon phase complication that renders a textured moon graphic (SMALL_IMAGE).
 * Draws a cratered lunar surface, then overlays the shadow terminator for the current phase.
 * Size is configurable via MoonPhaseConfigActivity (Small/Medium/Large).
 */
class MoonPhaseComplicationService : ComplicationDataSourceService() {

    private var cachedPhase: Double? = null
    private var cachedScale: Float? = null
    private var cachedBitmap: Bitmap? = null

    private val prefs by lazy {
        getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        if (type != ComplicationType.SMALL_IMAGE) return null
        val phase = 0.4
        return createSmallImageData(phase, MoonPhaseUtil.getPhaseName(phase), SCALE_LARGE)
    }

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationRequestListener
    ) {
        val data = if (request.complicationType == ComplicationType.SMALL_IMAGE) {
            val phase = MoonPhaseUtil.calculateMoonPhase(LocalDate.now())
            val scale = when (prefs.getString(KEY_SIZE, SIZE_LARGE)) {
                SIZE_SMALL -> SCALE_SMALL
                SIZE_MEDIUM -> SCALE_MEDIUM
                else -> SCALE_LARGE
            }
            createSmallImageData(phase, MoonPhaseUtil.getPhaseName(phase), scale)
        } else null

        listener.onComplicationData(data)
    }

    private fun createSmallImageData(
        phase: Double,
        phaseName: String,
        scale: Float
    ): SmallImageComplicationData {
        val bitmap = renderMoonBitmap(phase, BITMAP_SIZE, scale)
        val icon = Icon.createWithBitmap(bitmap)

        return SmallImageComplicationData.Builder(
            smallImage = SmallImage.Builder(icon, SmallImageType.PHOTO).build(),
            contentDescription = PlainComplicationText.Builder(phaseName).build()
        ).build()
    }

    private fun renderMoonBitmap(phase: Double, size: Int, scale: Float): Bitmap {
        cachedBitmap?.let { cached ->
            if (cachedPhase == phase && cachedScale == scale) return cached
        }

        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        val cx = size / 2f
        val cy = size / 2f
        val radius = size * scale / 2f

        // Clip to circle for all subsequent drawing
        canvas.save()
        val clipPath = Path().apply { addCircle(cx, cy, radius, Path.Direction.CW) }
        canvas.clipPath(clipPath)

        // 1. Draw the full lit lunar surface (base + craters)
        drawLunarSurface(canvas, cx, cy, radius)

        // 2. Overlay shadow for the dark portion
        if (phase < 0.01 || phase > 0.99) {
            // New moon: cover everything
            val darkPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = 0xFF0a0a14.toInt()
                style = Paint.Style.FILL
            }
            canvas.drawCircle(cx, cy, radius, darkPaint)
        } else if (phase < 0.49 || phase > 0.51) {
            // Partial phase: draw shadow over the dark side
            drawPhaseShadow(canvas, phase, cx, cy, radius)
        }
        // else: full moon — no shadow needed

        canvas.restore()

        // Rim on top of everything
        val rimPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = max(1f, radius * 0.015f)
            color = 0x33BBBBBB.toInt()
        }
        canvas.drawCircle(cx, cy, radius, rimPaint)

        cachedPhase = phase
        cachedScale = scale
        cachedBitmap = bitmap
        return bitmap
    }

    /**
     * Draw a textured lunar surface with maria (dark plains) and craters.
     * Positions are normalized to radius so it scales cleanly.
     */
    private fun drawLunarSurface(canvas: Canvas, cx: Float, cy: Float, radius: Float) {
        // Base surface: warm gray with spherical shading
        val basePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = RadialGradient(
                cx - radius * 0.15f, cy - radius * 0.15f, radius * 1.3f,
                intArrayOf(0xFFE8E0C8.toInt(), 0xFFC8C0A8.toInt(), 0xFFADA590.toInt()),
                floatArrayOf(0f, 0.6f, 1f),
                Shader.TileMode.CLAMP
            )
            style = Paint.Style.FILL
        }
        canvas.drawCircle(cx, cy, radius, basePaint)

        // Maria (dark lunar seas) — broad darker regions
        val mariaPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.FILL
        }

        // Mare Imbrium (upper left)
        mariaPaint.color = 0x28504838.toInt()
        canvas.drawOval(
            RectF(
                cx - radius * 0.55f, cy - radius * 0.65f,
                cx + radius * 0.1f, cy - radius * 0.1f
            ), mariaPaint
        )

        // Mare Serenitatis (upper right)
        mariaPaint.color = 0x24504838.toInt()
        canvas.drawOval(
            RectF(
                cx + radius * 0.05f, cy - radius * 0.55f,
                cx + radius * 0.5f, cy - radius * 0.1f
            ), mariaPaint
        )

        // Mare Tranquillitatis (center right)
        mariaPaint.color = 0x26504838.toInt()
        canvas.drawOval(
            RectF(
                cx + radius * 0.05f, cy - radius * 0.2f,
                cx + radius * 0.55f, cy + radius * 0.25f
            ), mariaPaint
        )

        // Oceanus Procellarum (large area left)
        mariaPaint.color = 0x20504838.toInt()
        canvas.drawOval(
            RectF(
                cx - radius * 0.7f, cy - radius * 0.3f,
                cx - radius * 0.05f, cy + radius * 0.45f
            ), mariaPaint
        )

        // Mare Nubium (lower center)
        mariaPaint.color = 0x22504838.toInt()
        canvas.drawOval(
            RectF(
                cx - radius * 0.35f, cy + radius * 0.2f,
                cx + radius * 0.15f, cy + radius * 0.6f
            ), mariaPaint
        )

        // Craters — circles with a bright rim and darker interior
        drawCrater(canvas, cx, cy, radius, -0.25f, -0.55f, 0.12f)  // Copernicus
        drawCrater(canvas, cx, cy, radius, 0.35f, 0.4f, 0.14f)     // Tycho
        drawCrater(canvas, cx, cy, radius, -0.45f, 0.3f, 0.08f)    // Kepler
        drawCrater(canvas, cx, cy, radius, 0.15f, -0.35f, 0.06f)   // Small crater
        drawCrater(canvas, cx, cy, radius, -0.1f, 0.55f, 0.07f)    // Small crater south
        drawCrater(canvas, cx, cy, radius, 0.4f, -0.15f, 0.05f)    // Tiny crater right
        drawCrater(canvas, cx, cy, radius, -0.55f, -0.2f, 0.06f)   // Aristarchus
        drawCrater(canvas, cx, cy, radius, 0.2f, 0.15f, 0.04f)     // Tiny crater center
        drawCrater(canvas, cx, cy, radius, -0.35f, 0.6f, 0.05f)    // Tiny crater lower left
        drawCrater(canvas, cx, cy, radius, 0.5f, 0.1f, 0.07f)      // Crater right edge
        drawCrater(canvas, cx, cy, radius, -0.15f, 0.05f, 0.09f)   // Center-left crater
        drawCrater(canvas, cx, cy, radius, 0.3f, -0.5f, 0.05f)     // Upper right small
    }

    /**
     * Draw a single crater at normalized position with bright rim and dark interior.
     */
    private fun drawCrater(
        canvas: Canvas,
        cx: Float, cy: Float, radius: Float,
        nx: Float, ny: Float, // normalized position (-1..1 relative to radius)
        nRadius: Float         // normalized crater radius
    ) {
        val craterCx = cx + nx * radius
        val craterCy = cy + ny * radius
        val craterR = nRadius * radius

        // Dark interior
        val interiorPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            shader = RadialGradient(
                craterCx, craterCy, craterR,
                intArrayOf(0x30202018.toInt(), 0x18302820.toInt()),
                floatArrayOf(0f, 1f),
                Shader.TileMode.CLAMP
            )
            style = Paint.Style.FILL
        }
        canvas.drawCircle(craterCx, craterCy, craterR, interiorPaint)

        // Bright rim (upper-left highlight simulating light from upper-left)
        val rimPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = max(1f, craterR * 0.2f)
            shader = SweepGradient(
                craterCx, craterCy,
                intArrayOf(
                    0x30FFFFFF.toInt(), // top: bright
                    0x08FFFFFF.toInt(), // right: dim
                    0x00000000,         // bottom: invisible
                    0x18FFFFFF.toInt(), // left: medium
                    0x30FFFFFF.toInt()  // back to top
                ),
                floatArrayOf(0f, 0.25f, 0.5f, 0.75f, 1f)
            )
        }
        canvas.drawCircle(craterCx, craterCy, craterR, rimPaint)
    }

    /**
     * Overlay the shadow for the unlit portion of the moon.
     * Uses the same terminator arc geometry but draws the DARK side.
     */
    private fun drawPhaseShadow(
        canvas: Canvas,
        phase: Double,
        cx: Float,
        cy: Float,
        radius: Float
    ) {
        val shadowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = 0xF00a0a14.toInt()
            style = Paint.Style.FILL
        }

        val terminatorWidth = radius * abs(cos(2.0 * PI * phase)).toFloat()
        val moonRect = RectF(cx - radius, cy - radius, cx + radius, cy + radius)
        val terminatorRect = RectF(
            cx - terminatorWidth, cy - radius,
            cx + terminatorWidth, cy + radius
        )

        val path = Path()

        if (phase < 0.5) {
            // Waxing: LEFT side is dark
            // Left semicircle: bottom (90°) clockwise to top (270°)
            path.arcTo(moonRect, 90f, 180f, true)
            // Terminator back to bottom
            if (phase < 0.25) {
                // Most of left is dark, terminator curves right
                path.arcTo(terminatorRect, 270f, 180f)
            } else {
                // Less dark, terminator curves left
                path.arcTo(terminatorRect, 270f, -180f)
            }
        } else {
            // Waning: RIGHT side is dark
            // Right semicircle: top (270°) clockwise to bottom (90°)
            path.arcTo(moonRect, 270f, 180f, true)
            // Terminator back to top
            if (phase < 0.75) {
                // Less dark, terminator curves right
                path.arcTo(terminatorRect, 90f, -180f)
            } else {
                // Most of right is dark, terminator curves left
                path.arcTo(terminatorRect, 90f, 180f)
            }
        }

        path.close()
        canvas.drawPath(path, shadowPaint)

        // Soft edge along the terminator for realism
        val edgePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeWidth = radius * 0.06f
            color = 0x400a0a14.toInt()
        }
        // Re-trace just the terminator arc portion for the soft edge
        val edgePath = Path()
        if (phase < 0.5) {
            if (phase < 0.25) {
                edgePath.arcTo(terminatorRect, 270f, 180f, true)
            } else {
                edgePath.arcTo(terminatorRect, 270f, -180f, true)
            }
        } else {
            if (phase < 0.75) {
                edgePath.arcTo(terminatorRect, 90f, -180f, true)
            } else {
                edgePath.arcTo(terminatorRect, 90f, 180f, true)
            }
        }
        canvas.drawPath(edgePath, edgePaint)
    }

    companion object {
        private const val BITMAP_SIZE = 192
        private const val PREFS_NAME = "moon_phase"
        private const val KEY_SIZE = "size"
        const val SIZE_SMALL = "small"
        const val SIZE_MEDIUM = "medium"
        const val SIZE_LARGE = "large"
        private const val SCALE_SMALL = 0.45f
        private const val SCALE_MEDIUM = 0.65f
        private const val SCALE_LARGE = 0.85f

        fun requestUpdate(context: Context) {
            val component = ComponentName(context, MoonPhaseComplicationService::class.java)
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(context, component)
                .requestUpdateAll()
        }
    }
}
