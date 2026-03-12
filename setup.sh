#!/bin/bash
# CodeTantra Autopilot — Setup Script
# Run once to install all dependencies

set -e

echo "╔═══════════════════════════════════════╗"
echo "║  CodeTantra Autopilot — Setup         ║"
echo "╚═══════════════════════════════════════╝"
echo

# Check root
if [ "$EUID" -eq 0 ]; then
    echo "⚠ Don't run as root. Use a normal user."
    exit 1
fi

# System packages
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip xdotool xclip espeak-ng > /dev/null 2>&1
echo "  ✓ System packages installed"

# Python packages
echo "[2/5] Installing Python packages..."
pip3 install --break-system-packages -q frida-tools evdev google-generativeai 2>/dev/null || \
pip3 install -q frida-tools evdev google-generativeai
echo "  ✓ Python packages installed"

# uinput module
echo "[3/5] Setting up uinput..."
sudo modprobe uinput 2>/dev/null || true
sudo chmod 666 /dev/uinput 2>/dev/null || true
if [ -w /dev/uinput ]; then
    echo "  ✓ uinput ready"
else
    echo "  ⚠ uinput not writable. Run: sudo modprobe uinput && sudo chmod 666 /dev/uinput"
fi

# Allow ptrace for Frida
echo "[4/5] Configuring kernel for Frida..."
sudo sysctl -w kernel.yama.ptrace_scope=0 > /dev/null 2>&1
echo "  ✓ ptrace_scope set to 0"

# Check app binary
echo "[5/5] Checking app binary..."
if [ -f "app/opt/CodeTantra SEA/codetantra-sea" ]; then
    echo "  ✓ App binary found"
    chmod +x "app/opt/CodeTantra SEA/codetantra-sea"
else
    echo "  ⚠ App binary not found in app/"
    echo "    Extract: dpkg-deb -x codetantra-sea_*.deb app/"
fi

# Create runtime dirs
mkdir -p logs config

echo
echo "════════════════════════════════════════"
echo "✅ Setup complete!"
echo
echo "Next steps:"
echo "  1. export GEMINI_API_KEY='your-key'"
echo "  2. ./run.sh"
echo "════════════════════════════════════════"
