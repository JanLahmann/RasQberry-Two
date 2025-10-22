#!/bin/bash
#
# RasQberry: Clear All LEDs
# Turns off all NeoPixel LEDs
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load environment config from centralized location
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
fi

# Set default paths if not configured
BIN_DIR="${BIN_DIR:-$USER_HOME/.local/bin}"

# Check multiple possible locations for the script
CLEAR_SCRIPT=""
for location in "$BIN_DIR/turn_off_LEDs.py" \
                "/usr/bin/turn_off_LEDs.py" \
                "$USER_HOME/.local/bin/turn_off_LEDs.py"; do
    if [ -f "$location" ]; then
        CLEAR_SCRIPT="$location"
        break
    fi
done

if [ -z "$CLEAR_SCRIPT" ]; then
    echo "Error: LED clear script not found"
    echo "Press Enter to exit..."
    read
    exit 1
fi

echo "Clearing all LEDs..."

# Activate virtual environment if available
VENV_PATHS=(
    "$USER_HOME/$REPO/venv/$STD_VENV"
    "$USER_HOME/.local/venv/$STD_VENV"
    "$USER_HOME/venv/$STD_VENV"
)

for venv_path in "${VENV_PATHS[@]}"; do
    if [ -f "$venv_path/bin/activate" ]; then
        . "$venv_path/bin/activate"
        break
    fi
done

# Run the clear script
python3 "$CLEAR_SCRIPT"

echo "All LEDs cleared."