#!/bin/bash -e

echo "Enabling filesystem expansion on first boot"

# Enable the init_resize.sh script to run on first boot
# This should normally be done by base pi-gen stages, but appears to be missing

# Ensure the expansion script exists
if [ ! -f "${ROOTFS_DIR}/usr/lib/raspi-config/init_resize.sh" ]; then
    echo "ERROR: init_resize.sh not found - base pi-gen stages may be incomplete"
    exit 1
fi

# Add init_resize.sh to cmdline.txt for first boot expansion
if [ -f "${ROOTFS_DIR}/boot/firmware/cmdline.txt" ]; then
    # Check if init= is already present
    if ! grep -q "init=" "${ROOTFS_DIR}/boot/firmware/cmdline.txt"; then
        echo "Adding init_resize.sh to cmdline.txt for first boot expansion"
        sed -i '1s/^/init=\/usr\/lib\/raspi-config\/init_resize.sh /' "${ROOTFS_DIR}/boot/firmware/cmdline.txt"
        echo "First boot expansion trigger added successfully"
    else
        echo "init= parameter already present in cmdline.txt"
    fi
else
    echo "ERROR: cmdline.txt not found at expected location"
    exit 1
fi

echo "Filesystem expansion setup completed"