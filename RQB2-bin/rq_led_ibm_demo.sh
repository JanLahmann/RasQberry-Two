#!/bin/bash
#
# RasQberry LED IBM Demo Launcher
# Simple wrapper to run the IBM-themed LED demonstration
#

# Set up environment
export HOME="${HOME:-/home/rasqberry}"
RQB2_CONFDIR="${RQB2_CONFDIR:-.local/config}"

# Try to load environment config
ENV_CONFIG="$HOME/$RQB2_CONFDIR/env-config.sh"
if [ -f "$ENV_CONFIG" ]; then
    . "$ENV_CONFIG"
fi

# Set default paths if not configured
REPO="${REPO:-RasQberry-Two}"
BIN_DIR="$HOME/$REPO/RQB2-bin"

# Check if script exists
LED_SCRIPT="$BIN_DIR/neopixel_spi_IBMtestFunc.py"
if [ ! -f "$LED_SCRIPT" ]; then
    echo "Error: LED demo script not found at $LED_SCRIPT"
    echo "Expected location: $LED_SCRIPT"
    echo "Press Enter to exit..."
    read
    exit 1
fi

echo "Starting LED IBM Demo..."
echo "Script location: $LED_SCRIPT"
echo "Press Ctrl+C to stop the demo"
echo

# Change to script directory and run
cd "$BIN_DIR"
python3 neopixel_spi_IBMtestFunc.py

echo
echo "Demo completed. Press Enter to exit..."
read