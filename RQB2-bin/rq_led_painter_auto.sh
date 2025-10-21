#!/bin/bash
# RasQberry: Auto-installing LED-Painter Demo Launcher
# Ensures demo is installed before launching

# Ensure HOME is set correctly
export HOME=${HOME:-/home/rasqberry}

# Source environment configuration
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
else
    # Fallback defaults
    REPO="RasQberry-Two"
    BIN_DIR="$HOME/$REPO/RQB2-bin"
fi

# Execute the main launcher script
exec "$BIN_DIR/rq_led_painter.sh"
