#!/bin/bash -e
#
# Install IP display service for boot-time LED display
# This service displays the device's IP address on the LED matrix for 30 seconds at boot

# Install netifaces package in the virtual environment
VENV_PATH="/home/${FIRST_USER_NAME}/RasQberry-Two/venv/RQB2"

if [ -d "$VENV_PATH" ]; then
    echo "Installing netifaces in virtual environment..."
    "$VENV_PATH/bin/pip3" install --use-pep517 netifaces
    # pip ran as root: give the venv back to the user, or later user-level
    # installs (catalog demos) trip over root-owned files
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$VENV_PATH"
else
    echo "WARNING: Virtual environment not found at $VENV_PATH"
    echo "netifaces will need to be installed manually"
fi

# Create systemd service file
# /etc/systemd/system/rasqberry-ip-display.service is installed from RQB2-system/ by 01-deploy-files (#294)

# Enable the service to run at boot
# rasqberry-ip-display.service is enabled by 01-deploy-files (RQB2-system/enabled-units.txt)

echo "IP display service installed and enabled"