#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/tmp/openclaw-gateway.log"
PATTERN="openclaw gateway run"

echo "[1/4] Stopping existing gateway process (if any)..."
PIDS=$(pgrep -f "$PATTERN" || true)
if [[ -n "${PIDS}" ]]; then
  echo "$PIDS" | xargs -r kill
  sleep 1

  # Force kill if still alive
  STILL=$(pgrep -f "$PATTERN" || true)
  if [[ -n "${STILL}" ]]; then
    echo "$STILL" | xargs -r kill -9
  fi
  echo "Stopped old gateway process(es)."
else
  echo "No running gateway process found."
fi

echo "[2/4] Starting gateway in background..."
nohup openclaw gateway run > "$LOG_FILE" 2>&1 &
NEW_PID=$!

echo "[3/4] Waiting for startup..."
sleep 2

echo "[4/4] Verifying health..."
if openclaw gateway health >/dev/null 2>&1; then
  echo "✅ Gateway restarted successfully. PID=${NEW_PID}"
  echo "Log: ${LOG_FILE}"
  exit 0
else
  echo "❌ Gateway health check failed."
  echo "Recent log output:"
  tail -n 80 "$LOG_FILE" || true
  exit 1
fi
