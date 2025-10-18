#!/bin/bash
#
# RasQberry: RasQ-LED Quantum Circuit Demo Launcher
# Visualizes quantum circuits with entanglement patterns on LEDs
#

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables
if [ -f "$USER_HOME/.local/config/env-config.sh" ]; then
    . "$USER_HOME/.local/config/env-config.sh"
else
    echo "Error: Environment config not found at $USER_HOME/.local/config/env-config.sh"
    exit 1
fi

# Activate virtual environment if available
if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch RasQ-LED demo
echo "Starting RasQ-LED Quantum Circuit Demo..."
exec python3 "$BIN_DIR/RasQ-LED.py"
