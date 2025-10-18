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
    # Check if init_resize.sh is already configured
    if grep -q "init=/usr/lib/raspi-config/init_resize.sh" "${ROOTFS_DIR}/boot/firmware/cmdline.txt"; then
        echo "init_resize.sh already present in cmdline.txt"
    else
        # Remove any existing init= parameter first
        if grep -q "init=" "${ROOTFS_DIR}/boot/firmware/cmdline.txt"; then
            echo "Removing existing init= parameter from cmdline.txt"
            sed -i 's/init=[^ ]* //g' "${ROOTFS_DIR}/boot/firmware/cmdline.txt"
        fi

        # Add init_resize.sh to the beginning of cmdline.txt
        echo "Adding init_resize.sh to cmdline.txt for first boot expansion"
        sed -i '1s/^/init=\/usr\/lib\/raspi-config\/init_resize.sh /' "${ROOTFS_DIR}/boot/firmware/cmdline.txt"
        echo "First boot expansion trigger added successfully"
    fi
else
    echo "ERROR: cmdline.txt not found at expected location"
    exit 1
fi

echo "Filesystem expansion setup completed"