#!/bin/bash
# RasQberry: Auto-installing LED-Painter Demo Launcher
# Ensures demo is installed before launching

# Ensure HOME is set correctly
export HOME=${HOME:-/home/rasqberry}

# Execute the main launcher script (both scripts are in /usr/bin)
exec /usr/bin/rq_led_painter.sh
