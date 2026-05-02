package com.photoface.complications.moon

import java.time.LocalDate
import java.time.temporal.ChronoUnit

/**
 * Shared moon phase calculation and lookup logic.
 */
object MoonPhaseUtil {

    /**
     * Calculate moon phase for a given date.
     * Returns 0-1 where 0 = new moon, 0.25 = first quarter, 0.5 = full moon, 0.75 = last quarter
     */
    fun calculateMoonPhase(date: LocalDate): Double {
        // Known new moon: January 6, 2000
        val knownNewMoon = LocalDate.of(2000, 1, 6)
        val synodicMonth = 29.530588853 // Average days between new moons

        val daysSinceKnown = ChronoUnit.DAYS.between(knownNewMoon, date).toDouble()
        val phase = (daysSinceKnown % synodicMonth) / synodicMonth

        return if (phase < 0) phase + 1 else phase
    }

    /**
     * Get moon phase emoji based on phase value.
     * Phase 0 = new moon, 0.5 = full moon, 1 = new moon again
     */
    fun getMoonEmoji(phase: Double): String {
        return when {
            phase < 0.0625 -> "\uD83C\uDF11"  // New Moon
            phase < 0.1875 -> "\uD83C\uDF12"  // Waxing Crescent
            phase < 0.3125 -> "\uD83C\uDF13"  // First Quarter
            phase < 0.4375 -> "\uD83C\uDF14"  // Waxing Gibbous
            phase < 0.5625 -> "\uD83C\uDF15"  // Full Moon
            phase < 0.6875 -> "\uD83C\uDF16"  // Waning Gibbous
            phase < 0.8125 -> "\uD83C\uDF17"  // Last Quarter
            phase < 0.9375 -> "\uD83C\uDF18"  // Waning Crescent
            else -> "\uD83C\uDF11"             // New Moon
        }
    }

    /** Full human-readable phase name */
    fun getPhaseName(phase: Double): String {
        return when {
            phase < 0.0625 -> "New Moon"
            phase < 0.1875 -> "Waxing Crescent"
            phase < 0.3125 -> "First Quarter"
            phase < 0.4375 -> "Waxing Gibbous"
            phase < 0.5625 -> "Full Moon"
            phase < 0.6875 -> "Waning Gibbous"
            phase < 0.8125 -> "Last Quarter"
            phase < 0.9375 -> "Waning Crescent"
            else -> "New Moon"
        }
    }

    /** Short abbreviation for SHORT_TEXT display */
    fun getShortName(phase: Double): String {
        return when {
            phase < 0.0625 -> "New"
            phase < 0.1875 -> "WxCr"
            phase < 0.3125 -> "1stQ"
            phase < 0.4375 -> "WxGb"
            phase < 0.5625 -> "Full"
            phase < 0.6875 -> "WnGb"
            phase < 0.8125 -> "3rdQ"
            phase < 0.9375 -> "WnCr"
            else -> "New"
        }
    }
}
