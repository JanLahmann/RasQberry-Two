#!/bin/bash
#
# RasQberry: RasQ-LED Quantum Circuit Demo Launcher
# Visualizes quantum circuits with entanglement patterns on LEDs
#

# Ensure HOME is set (for desktop launchers)
if [ -z "$HOME" ]; then
    HOME="/home/$(whoami)"
fi

# Load environment variables
if [ -f "$HOME/.local/config/env-config.sh" ]; then
    . "$HOME/.local/config/env-config.sh"
else
    echo "Error: Environment config not found at $HOME/.local/config/env-config.sh"
    exit 1
fi

# Activate virtual environment if available
if [ -f "$HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch RasQ-LED demo
echo "Starting RasQ-LED Quantum Circuit Demo..."
exec python3 "$BIN_DIR/RasQ-LED.py"
