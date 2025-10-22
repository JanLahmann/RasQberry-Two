#!/bin/bash
#
# RasQberry LED IBM Demo Launcher
# Simple wrapper to run the IBM-themed LED demonstration
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load environment config from centralized location
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
fi

# Set default paths if not configured
REPO="${REPO:-RasQberry-Two}"
BIN_DIR="${BIN_DIR:-$USER_HOME/.local/bin}"

# Check multiple possible locations for the script
LED_SCRIPT=""
for location in "$BIN_DIR/neopixel_spi_IBMtestFunc.py" \
                "/usr/bin/neopixel_spi_IBMtestFunc.py" \
                "$USER_HOME/$REPO/RQB2-bin/neopixel_spi_IBMtestFunc.py"; do
    if [ -f "$location" ]; then
        LED_SCRIPT="$location"
        break
    fi
done

if [ -z "$LED_SCRIPT" ]; then
    echo "Error: LED demo script not found"
    echo "Searched locations:"
    echo "  - $BIN_DIR/neopixel_spi_IBMtestFunc.py"
    echo "  - /usr/bin/neopixel_spi_IBMtestFunc.py"
    echo "  - $USER_HOME/$REPO/RQB2-bin/neopixel_spi_IBMtestFunc.py"
    echo "Press Enter to exit..."
    read
    exit 1
fi

echo "Starting LED IBM Demo..."
echo "Script location: $LED_SCRIPT"
echo

# Activate virtual environment if available
VENV_PATHS=(
    "$USER_HOME/$REPO/venv/$STD_VENV"
    "$USER_HOME/.local/venv/$STD_VENV"
    "$USER_HOME/venv/$STD_VENV"
)

for venv_path in "${VENV_PATHS[@]}"; do
    if [ -f "$venv_path/bin/activate" ]; then
        echo "Activating virtual environment: $venv_path"
        . "$venv_path/bin/activate"
        break
    fi
done

# Run the script
python3 "$LED_SCRIPT"

# Script handles its own exit prompt now
echo
read -p "Press Enter to close this window..."