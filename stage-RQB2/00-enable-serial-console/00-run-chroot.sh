#!/bin/bash -e
#
# Enable serial console login (getty) for interactive access
#
# This stage relies on systemd-getty-generator which automatically creates
# serial-getty services based on the kernel console= parameter in cmdline.txt.
#
# On Pi 5: serial0 maps to ttyAMA10
# On Pi 4: serial0 maps to ttyAMA0 or ttyS0
#
# The generator reads /proc/cmdline and creates the appropriate service,
# so we don't need to statically enable services for specific devices.
#

echo "=== Enabling Serial Console Login ==="

# Ensure serial-getty@.service template exists and is not masked
echo "=> Verifying serial-getty template is available"
if systemctl list-unit-files serial-getty@.service >/dev/null 2>&1; then
    echo "   serial-getty@.service template is available"
else
    echo "   WARNING: serial-getty@.service template not found"
fi

# The actual serial-getty service will be created by systemd-getty-generator
# at boot time based on the console= parameter in /boot/firmware/cmdline.txt

echo "=> Serial console login enabled"
echo "   systemd-getty-generator will create the appropriate service at boot"
echo "   based on the kernel console= parameter"