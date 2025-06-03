#!/bin/bash
#
# RasQberry Desktop File Trust Script
# Ensures all RasQberry desktop files are trusted on first login
#

DESKTOP_DIR="$HOME/Desktop"
MARKER_FILE="$HOME/.rasqberry-desktop-trusted"

# Exit if already run
if [ -f "$MARKER_FILE" ]; then
    exit 0
fi

# Wait for desktop to be fully loaded
sleep 5

# Trust all RasQberry desktop files
for desktop_file in composer.desktop grok-bloch.desktop grok-bloch-web.desktop \
                   quantum-fractals.desktop quantum-lights-out.desktop \
                   quantum-raspberry-tie.desktop led-ibm-demo.desktop; do
    if [ -f "$DESKTOP_DIR/$desktop_file" ]; then
        # Set executable
        chmod +x "$DESKTOP_DIR/$desktop_file"
        # Mark as trusted
        gio set "$DESKTOP_DIR/$desktop_file" metadata::trusted true 2>/dev/null || true
        # Touch to update modification time
        touch "$DESKTOP_DIR/$desktop_file"
    fi
done

# Create marker file
touch "$MARKER_FILE"

# Restart PCManFM to reload desktop
pcmanfm --desktop-off
sleep 1
pcmanfm --desktop --profile LXDE-pi &