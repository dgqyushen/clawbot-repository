# ADB Connect Skill

Connect to Android emulators or devices via ADB (Android Debug Bridge) from within Docker/container environments.

## Usage

### Quick Connect

```bash
# Connect to default port 5555 and take screenshot
openclaw skill adb-connect

# Connect to custom port
openclaw skill adb-connect --port 5556

# Connect without screenshot
openclaw skill adb-connect --no-screenshot
```

### Direct Script Usage

```bash
bash ~/.openclaw/workspace/skills/adb-connect/scripts/connect.sh [PORT] [SCREENSHOT_PATH]

# Examples:
bash scripts/connect.sh              # Default port 5555, screenshot to /tmp/android_screenshot.png
bash scripts/connect.sh 5556         # Port 5556
bash scripts/connect.sh 5555 /tmp/my.png   # Custom screenshot path
```

## What It Does

1. **Auto-installs ADB** if not present (requires apt)
2. **Auto-detects host address** from container:
   - `host.docker.internal` (Docker Desktop)
   - `172.17.0.1` (Linux docker0 gateway)
   - `localhost` (host network mode)
3. **Connects to emulator** via `adb connect`
4. **Takes screenshot** (optional) and saves to specified path

## Requirements

- Android emulator with ADB over network enabled (`adb tcpip 5555`)
- Container must have network access to host
- apt-based system (Debian/Ubuntu) for auto-install

## Output

On success:
```
✓ 连接成功: host.docker.internal:5555
✓ 截图已保存: /tmp/android_screenshot.png
```

On failure:
```
✗ 所有连接尝试失败
[设备列表]
```

## Common Ports

| Emulator | Default ADB Port |
|----------|-----------------|
| Android Studio Emulator | 5555 |
| BlueStacks | 5555 or 5565 |
| 夜神模拟器 | 62001 |
| 雷电模拟器 | 5555 |
| 网易MuMu | 7555 |

## Troubleshooting

### Connection refused
- Ensure emulator has ADB over network: `adb tcpip 5555`
- Check firewall/Windows Defender

### Device unauthorized
- Check emulator screen for RSA key fingerprint dialog
- Click "Allow" to authorize debugging

### Container cannot reach host
- Docker Desktop: use `host.docker.internal`
- Linux: ensure docker0 bridge is accessible
- Alternative: run container with `--network host`