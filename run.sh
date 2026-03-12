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

# Keep config intact (clearing causes re-launch when server pushes settings)
mkdir -p "$SCRIPT_DIR/config" "$SCRIPT_DIR/logs"

# Run the autopilot
python3 -u "$SCRIPT_DIR/src/autopilot.py"
