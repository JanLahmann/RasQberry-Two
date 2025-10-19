#!/bin/bash
#
# RasQberry: Quantum Lights Out Demo Launcher
# Launches the Quantum Lights Out demo
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

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    exit 1
fi

# Use canonical path (same as menu)
DEMO_DIR="$HOME/$REPO/demos/Quantum-Lights-Out"

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/lights_out.py" ]; then
    echo "Quantum Lights Out demo not found. Installing..."
    if ! sudo raspi-config nonint do_qlo_install; then
        echo "Installation failed."
        exit 1
    fi
fi

# Activate virtual environment if available
if [ -f "$HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch the demo
echo "Launching demo from: $DEMO_DIR"
if [ ! -d "$DEMO_DIR" ]; then
    echo "Error: Demo directory does not exist: $DEMO_DIR"
    exit 1
fi

if [ ! -f "$DEMO_DIR/lights_out.py" ]; then
    echo "Error: lights_out.py not found in $DEMO_DIR"
    echo "Directory contents:"
    ls -la "$DEMO_DIR"
    exit 1
fi

cd "$DEMO_DIR" && python3 -W ignore::DeprecationWarning lights_out.py