#!/bin/bash -e
#
# Enable serial console login (getty) for interactive access
#

echo "=== Enabling Serial Console Login ==="

# Enable serial getty service for login prompt on serial console
# On Pi 5, serial0 maps to ttyAMA10
# On Pi 4, serial0 maps to ttyAMA0 or ttyS0
echo "=> Enabling serial-getty services"

# Enable for common serial port names
systemctl enable serial-getty@ttyAMA0.service 2>/dev/null || true
systemctl enable serial-getty@ttyAMA10.service 2>/dev/null || true
systemctl enable serial-getty@ttyS0.service 2>/dev/null || true

echo "=> Serial console login enabled"
echo "   You can now login via serial console after boot"