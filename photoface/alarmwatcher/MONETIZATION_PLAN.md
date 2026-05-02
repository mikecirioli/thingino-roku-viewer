# Monetization Plan: Watchman Bridge

## Product Strategy
*   **Price Point:** $1.49 USD (One-time Lifetime Unlock)
*   **Model:** Time-limited Full Trial (3 Days)
*   **Core Value Gate:** The Alarm Sync (Phone-to-Watch bridge)

## User Conversion Flow

### 1. The Onboarding (Day 1)
*   User installs app.
*   Welcome message: "Enjoy 3 days of full access to all features (Remote Control, Custom Tones, Sync)."
*   No payment info required upfront.

### 2. The Trial Period (Days 1-3)
*   **UI:** A small Material 3 banner at the bottom of the Phone app showing remaining time.
*   **Experience:** Full functionality. User establishes trust that the bridge works on their hardware.

### 3. The Expiration (Day 4+)
*   **The Gate:** `AlarmListenerService` checks `TrialManager`. If expired and not Pro, it stops sending signals to the watch.
*   **UI:** The Phone app shows a "Trial Expired" overlay.
*   **Message:** "You've synced [X] alarms! Keep your watch connected for just $0.99."
*   **Action:** One-tap Google Play Billing dialog.

## Technical Implementation Plan

### Phase A: The Trial Manager
*   Implement `TrialManager.kt` using `EncryptedSharedPreferences`.
*   Store `install_timestamp` securely on first launch.
*   Logic: `isTrialActive()`, `getRemainingHours()`, `isProUser()`.

### Phase B: The Alarm Guard
*   Modify `AlarmListenerService.onNotificationPosted`.
*   Before `repository.sendMessage(START_ALARM)`, check `TrialManager`.
*   Log ignored alarms due to expiration for local debugging.

### Phase C: Google Play Billing
*   Integrate `com.android.billingclient:billing`.
*   Handle connection to Google Play Store.
*   Implement "Lifetime Unlock" non-consumable product.
*   Update `isPro` flag in encrypted storage upon successful receipt validation.

### Phase D: Post-Purchase UI
*   Remove trial banners.
*   Show "Pro Active" badge in Settings.
*   Unlock all current and future features (e.g., custom vibrations, bedtime sync).
