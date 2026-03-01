# Device Profile (Ethan)

- Primary target: `host.docker.internal:5555`
- Fallback target: `192.168.2.104:5555` (only if host alias fails)
- Expected adb state: `device`

## Quick health checks

```bash
adb start-server
adb connect host.docker.internal:5555
adb devices -l
```

## Common commands

```bash
# Screenshot to local file
adb -s host.docker.internal:5555 exec-out screencap -p > reports/android-screen.png

# Device info
adb -s host.docker.internal:5555 shell getprop ro.product.model
adb -s host.docker.internal:5555 shell ip -4 addr

# Logs
adb -s host.docker.internal:5555 logcat -d | tail -n 200

# Install APK
adb -s host.docker.internal:5555 install -r /path/to/app.apk
```

## Troubleshooting

- `offline`/`unauthorized`: reconnect and accept prompt on device if shown.
- `cannot connect`: confirm host port 5555 open, then retry `adb connect`.
- Multiple devices: always use `-s host.docker.internal:5555`.
