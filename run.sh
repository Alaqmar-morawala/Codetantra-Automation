#!/bin/bash
# CodeTantra Autopilot — Run Script
# Single command to launch the autopilot

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check API key
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not set"
    echo "  Run: export GEMINI_API_KEY='your-key'"
    exit 1
fi

# Ensure kernel allows Frida
sudo sysctl -w kernel.yama.ptrace_scope=0 > /dev/null 2>&1

# Ensure uinput is ready
sudo modprobe uinput 2>/dev/null || true
sudo chmod 666 /dev/uinput 2>/dev/null || true

# Prevent screen blanking
xset s off -dpms 2>/dev/null || true

# Check for first-run initialization
APP_BIN="$SCRIPT_DIR/app/opt/CodeTantra SEA/codetantra-sea"
FIRST_RUN_FLAG="$SCRIPT_DIR/.first_run_done"

if [ ! -f "$FIRST_RUN_FLAG" ] && [ -f "$APP_BIN" ]; then
    echo "[!] First run detected. Initializing app natively for 8 seconds..."
    "$APP_BIN" --no-sandbox > /dev/null 2>&1 &
    APP_PID=$!
    sleep 8
    kill -9 $APP_PID 2>/dev/null || true
    touch "$FIRST_RUN_FLAG"
    echo "[!] Initialization complete. Starting autopilot..."
fi

# Keep config intact (clearing causes re-launch when server pushes settings)
mkdir -p "$SCRIPT_DIR/config" "$SCRIPT_DIR/logs"

# Run the autopilot
python3 -u "$SCRIPT_DIR/src/autopilot.py"
