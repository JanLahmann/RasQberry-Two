#!/bin/bash -e

echo "Checking filesystem expansion configuration"

# Verify that pi-gen's firstboot mechanism is in place
# The bookworm-arm64 branch uses init=/usr/lib/raspberrypi-sys-mods/firstboot
# which handles filesystem expansion automatically on first boot

if [ -f "${ROOTFS_DIR}/boot/firmware/cmdline.txt" ]; then
    if grep -q "init=/usr/lib/raspberrypi-sys-mods/firstboot" "${ROOTFS_DIR}/boot/firmware/cmdline.txt"; then
        echo "Filesystem expansion already configured via firstboot mechanism"
    else
        echo "WARNING: Expected firstboot init parameter not found in cmdline.txt"
        echo "Current cmdline.txt contents:"
        cat "${ROOTFS_DIR}/boot/firmware/cmdline.txt"
    fi
else
    echo "ERROR: cmdline.txt not found at expected location"
    exit 1
fi

echo "Filesystem expansion check completed"