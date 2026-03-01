---
name: android-adb-control
description: Connect to and operate Ethan's Android emulator/device over wireless ADB from the OpenClaw container. Use when the user asks to control the Android device, take screenshots, inspect logs, run shell commands, install APKs, or automate debug steps via adb.
---

# Android ADB Control

Use this skill to operate Ethan's Android target through ADB-over-TCP with stable defaults.

## Default target

- Primary endpoint: `host.docker.internal:5555`
- Always pin device with `-s host.docker.internal:5555` to avoid cross-device mistakes.

For environment details and fallback endpoint, read `references/device-profile.md`.

## Workflow

1. Ensure ADB exists. If missing, install `android-tools-adb`.
2. Start and connect:
   - `adb start-server`
   - `adb connect host.docker.internal:5555`
3. Verify state:
   - `adb devices -l`
   - Continue only when state is `device`.
4. Execute requested action (screenshot / shell / install / logcat / automation).
5. Return concise result + artifact path when files are generated.

## High-value operations

### Screenshot

```bash
mkdir -p reports
adb -s host.docker.internal:5555 exec-out screencap -p > reports/android-screen.png
```

### Quick diagnostics

```bash
adb -s host.docker.internal:5555 shell getprop ro.product.model
adb -s host.docker.internal:5555 shell ip -4 addr
adb -s host.docker.internal:5555 logcat -d | tail -n 200
```

### Install APK

```bash
adb -s host.docker.internal:5555 install -r /path/to/app.apk
```

## Guardrails

- Do not factory-reset, wipe data, or uninstall critical apps unless user explicitly asks.
- For destructive actions, confirm intent first.
- If device is `offline`/`unauthorized`, reconnect and ask user to confirm authorization if prompted.
