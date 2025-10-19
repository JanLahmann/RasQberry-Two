#!/bin/bash -e
#
# Enable VNC for remote access
#

echo "Enabling VNC service..."

# Enable VNC using raspi-config
raspi-config nonint do_vnc 0

# Ensure VNC service is enabled and will start on boot
systemctl enable vncserver-x11-serviced.service

echo "VNC enabled successfully"