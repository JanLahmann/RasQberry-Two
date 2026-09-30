#!/bin/bash
# RasQberry Firstboot Task: Expand Root Filesystem
# Expands the root filesystem to fill the SD card/device

echo "Expanding root filesystem..."

# Check for skip marker in bootfs (accessible from Mac/Windows)
# This allows users to disable expansion by creating a file on the boot partition
if [ -f /boot/firmware/skip-expansion ]; then
    echo "Expansion disabled: /boot/firmware/skip-expansion marker found"
    echo "This is typically used for A/B boot setup"
    exit 0
fi

# Check if expansion is needed
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
PART_END=$(parted /dev/$ROOT_DEV -ms unit s p | grep "^${ROOT_PART##*/}:" | cut -d: -f3 | sed 's/s$//')
DEV_SIZE=$(cat /sys/block/$ROOT_DEV/size)

if [ "$PART_END" -ge "$((DEV_SIZE - 1))" ]; then
    echo "Root filesystem already at maximum size"
    exit 0
fi

# Run raspi-config expansion
if raspi-config nonint do_expand_rootfs; then
    echo "Filesystem expansion configured successfully"
    # Request reboot (exit code 99)
    exit 99
else
    echo "ERROR: Failed to configure filesystem expansion"
    exit 1
fi
