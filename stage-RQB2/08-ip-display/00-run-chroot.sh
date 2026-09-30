#!/bin/bash -e
#
# Install IP display service for boot-time LED display
# This service displays the device's IP address on the LED matrix for 30 seconds at boot

# Install netifaces package in the virtual environment
# Uses wheel cache from Qiskit stage for faster installation
VENV_PATH="/home/rasqberry/RasQberry-Two/venv/RQB2"
WHEEL_DIR="/tmp/wheels"

if [ -d "$VENV_PATH" ]; then
    echo "Installing netifaces in virtual environment..."
    # Use wheel cache if available (populated by 03-install-qiskit)
    if [ -d "$WHEEL_DIR" ] && [ -n "$(ls -A $WHEEL_DIR/*.whl 2>/dev/null)" ]; then
        echo "Using wheel cache for fast install..."
        "$VENV_PATH/bin/pip3" install --prefer-binary --find-links="$WHEEL_DIR" netifaces
    else
        echo "No wheel cache - installing from PyPI..."
        "$VENV_PATH/bin/pip3" install --use-pep517 netifaces
    fi
else
    echo "WARNING: Virtual environment not found at $VENV_PATH"
    echo "netifaces will need to be installed manually"
fi

# Create systemd service file
# /etc/systemd/system/rasqberry-ip-display.service is installed from RQB2-system/ by 01-deploy-files (#294)

# Enable the service to run at boot
# rasqberry-ip-display.service is enabled by 01-deploy-files (RQB2-system/enabled-units.txt)

echo "IP display service installed and enabled"