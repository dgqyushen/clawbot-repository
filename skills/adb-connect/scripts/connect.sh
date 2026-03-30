#!/bin/bash
# Android Debug Bridge (ADB) Connection Script
# Auto-detects and connects to Android emulator/device

set -e

PORT=${1:-5555}
SCREENSHOT_PATH=${2:-/tmp/android_screenshot.png}

echo "=== ADB Android Connection ==="
echo "Target Port: $PORT"
echo ""

# Check if adb is installed
if ! command -v adb &> /dev/null; then
    echo "ADB not found. Installing..."
    apt-get update -qq && apt-get install -y -qq android-tools-adb > /dev/null 2>&1
fi

# Try multiple connection methods
declare -a HOSTS=("host.docker.internal" "172.17.0.1" "localhost")
CONNECTED=false

for HOST in "${HOSTS[@]}"; do
    echo "[尝试] Connecting to $HOST:$PORT..."
    if adb connect "$HOST:$PORT" 2>&1 | grep -q "connected\|already connected"; then
        echo "✓ 连接成功: $HOST:$PORT"
        CONNECTED=true
        break
    fi
done

if [ "$CONNECTED" = false ]; then
    echo "✗ 所有连接尝试失败"
    adb devices
    exit 1
fi

# Show device status
echo ""
echo "=== 设备状态 ==="
adb devices -l | grep -v "List of devices"

# Take screenshot if requested
if [ -n "$SCREENSHOT_PATH" ]; then
    echo ""
    echo "=== 截取屏幕 ==="
    adb shell screencap -p /sdcard/screenshot_tmp.png
    adb pull /sdcard/screenshot_tmp.png "$SCREENSHOT_PATH"
    echo "✓ 截图已保存: $SCREENSHOT_PATH"
fi

echo ""
echo "=== 连接完成 ==="