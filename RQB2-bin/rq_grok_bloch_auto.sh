#!/bin/bash
#
# RasQberry: Auto-installing Grok Bloch Sphere Demo Launcher
# Automatically installs demo if missing, then launches it
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

# Set BIN_DIR if not already set by env-config.sh
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
DEMO_DIR="$HOME/$REPO/demos/grok-bloch"

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Grok Bloch demo not found. Installing..."
    if ! sudo raspi-config nonint do_grok_bloch_install; then
        echo "Installation failed."
        exit 1
    fi
fi

# Launch the demo using the existing launcher
exec "$BIN_DIR/rq_grok_bloch.sh"