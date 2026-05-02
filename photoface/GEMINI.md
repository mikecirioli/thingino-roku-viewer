# Gemini Development Log - PhotoFace Monorepo

## Work Done (2026-03-08)
- **Watchface Polishing:**
    - Implemented a 6-tier "Fitness Ring" color ramp for Steps (#FF5252 -> #FF9800 -> #FFEB3B -> #8BC34A -> #2E7D32 -> #00E5FF).
    - Optimized AOD power consumption by consolidating Shadow Hand `<AnalogClock>` elements and deactivating `<Sweep>` ticks in AMBIENT mode.
    - Added graceful degradation for missing Heart Rate and Step sensors (displays `--` instead of 0 or crashing).
    - Updated tap actions to use brand-agnostic system targets (`CALENDAR`, `HEALTH_HEART_RATE`) for better compatibility with non-Samsung watches.
    - Replaced abstract dot icons for "Label Size" with new physical vector SVG icons displaying scalable "A" text.
- **Complications Polishing:**
    - Added "Tap-to-Fix" logic to Moon, Sunrise, and Floors complications. Tapping a "No Data" or "No Permission" state now automatically launches the `PermissionActivity`.
- **Documentation & Release Planning:**
    - Created `RELEASE_PLAN.md` with full marketing copy, screenshot checklists, and pre-release verification steps.
    - Documented the known "Photo Selection Amnesia" platform bug in the Samsung Galaxy Wearable app in both `README.md` and `RELEASE_PLAN.md`.
    - Included a **Developer Note** for the Play Store listing to proactively manage user expectations regarding the photo picker behavior.

## Known Issues & Technical Quirks
- **AOD Freezing / Blanking (WFF Runtime Bug):** When the watch enters a deep sleep state, the AOD may occasionally fail to render complex variants and get stuck or go blank. This is a known OS-level bug in the Samsung WFF engine. Toggling AOD off/on in settings restores it. Addressed via Play Store disclaimer; no code fix available.
- **Floor Count Stalling on Deep Sleep:** The `FloorsComplicationService` relies on Health Services `PassiveMonitoringClient`. If the application process is killed by the OS during memory optimization/deep sleep, background updates stall because the callback is destroyed. Tapping the complication re-launches the process and resumes updates. A proper fix requires an `ACTION_BOOT_COMPLETED` broadcast receiver to re-register the listener implicitly, but the tap-to-wake behavior is acceptable for the current release.

## Current State & Next Steps
- **Watchface Status:** Feature-complete and optimized. Ready for Play Store screenshot gathering and asset submission.
- **Complications Status:** Robust and verified. Ready for release.
- **Upcoming:** Proceed with screenshot capture and final submission of the Watchface and Complications Suite.
