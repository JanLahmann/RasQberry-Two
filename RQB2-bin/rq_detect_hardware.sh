#!/bin/bash
#
# RasQberry Hardware Detection Script
#
# Detects Raspberry Pi model and updates the system-wide environment file.
# This script runs at every boot via cron job to ensure PI_MODEL is always current,
# even if the SD card is moved between different Pi models.
#
# Detection logic:
#   - Pi 5: Any model string containing "Pi 5"
#   - Pi 4: Any model string containing "Pi 4"
#   - Default: Pi5 (for unknown or future models)
#
# The script updates only the PI_MODEL line in the environment file,
# preserving all other configuration values.

set -e  # Exit on error

# Environment file location (system-wide)
ENV_FILE="/usr/config/rasqberry_environment.env"

# Read Pi model from device tree
MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown")

# Detect Pi model (simple substring matching)
if [[ "$MODEL" == *"Pi 5"* ]]; then
    PI_MODEL="Pi5"
elif [[ "$MODEL" == *"Pi 4"* ]]; then
    PI_MODEL="Pi4"
else
    # Unknown or future hardware - default to Pi5
    PI_MODEL="Pi5"
fi

# Update PI_MODEL in environment file
if [ -f "$ENV_FILE" ]; then
    sed -i "s/^PI_MODEL=.*/PI_MODEL=$PI_MODEL/" "$ENV_FILE"
else
    echo "Error: Environment file not found: $ENV_FILE" >&2
    exit 1
fi

# Success (silent operation for clean boot)
exit 0
