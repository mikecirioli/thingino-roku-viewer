# Debugging the 3 Bad Dogs Roku App

This document outlines the process for debugging the Roku application using the provided `deploy.sh` script and the device's built-in debugging console.

## 1. Prerequisites

- **Developer Mode Enabled:** Your Roku device must be in Developer Mode. To do this, press the following sequence on your remote: `Home (3x) -> Up (2x) -> Right -> Left -> Right -> Left -> Right`. Ensure the installer is enabled.
- **Roku IP Address:** You need to know your Roku's local IP address. You can find this in `Settings > Network > About` on your Roku.
- **Developer Password:** You need the password you set when you enabled Developer Mode.

## 2. Fast Deployment for Debugging

The `roku/deploy.sh` script is the fastest way to deploy code changes to your device for testing. It zips the `roku/` directory and pushes it directly to the device, bypassing the manual packager steps.

### Usage

1. Open a terminal on your computer.
2. Navigate to the `roku/` directory of this project.
3. Run the script with your Roku's IP and password:

   ```bash
   ./deploy.sh <YOUR_ROKU_IP> <YOUR_DEV_PASSWORD>
   ```
   For example:
   ```bash
   ./deploy.sh 192.168.1.70 admin
   ```

### Understanding the Output

- **`Install Success`**: The app was successfully compiled and installed on your Roku. It should launch automatically on your TV screen.
- **`HTTP Error: 400` / `Install Failure: Compilation Failed`**: This means there is a **syntax error** in your BrightScript code (`.brs` files) or a structural error in your XML (`.xml` files). The raw output from the script will often tell you which file and line number caused the failure. This is the most common error during development.
- **`curl: (7) Failed to connect...`**: The script could not reach your Roku device at the provided IP address. Double-check the IP and ensure your computer is on the same network.

## 3. Using the Roku Debug Console (Telnet)

If the app installs successfully but then freezes, crashes, or behaves unexpectedly, you must use the Telnet debug console to see the live error messages.

### How to Connect

1. Open a terminal on your computer.
2. Connect to your Roku's IP address on **port 8085**:

   ```bash
   telnet <YOUR_ROKU_IP> 8085
   ```
   Example: `telnet 192.168.1.70 8085`

3. A blank screen with a `BrightScript Micro Debugger` prompt will appear. This window is now listening for logs from your device.

### Capturing the Error

1. Keep the `telnet` window open and visible.
2. Launch the "3 Bad Dogs" app on your Roku.
3. When the app crashes or freezes, switch back to your `telnet` window.
4. The window will now contain the **full crash log**, including:
   - The exact error message (e.g., `Interface not a member of BrightScript Component`).
   - The file path and line number where the error occurred (e.g., `pkg:/components/MainScene.brs(28)`).
   - A "Backtrace" showing the sequence of function calls that led to the crash.

This information is essential for identifying the root cause of runtime bugs. Copy and paste the full log when reporting an issue.
