#!/bin/bash
# CodeTantra Solution Grabber Launcher

# Ensure we are in the project root
cd "$(dirname "$0")"

# Check for xclip
if ! command -v xclip &> /dev/null; then
    echo "❌ Error: xclip is not installed. Please run: sudo apt install xclip"
    exit 1
fi

# Run the grabber
python3 src/solution_grabber.py "$@"
