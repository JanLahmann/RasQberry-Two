#!/bin/bash -e
# stage-RQB2/00-configure-initramfs/00-run-chroot.sh
# Configure initramfs based on SKIP_INITRAMFS variable from stage config

echo "Checking SKIP_INITRAMFS configuration..."

# Source the configuration file (same approach as qiskit stage)
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config
    echo "Configuration loaded, SKIP_INITRAMFS=${SKIP_INITRAMFS}"
else
    echo "WARNING: stage config file not found, defaulting SKIP_INITRAMFS to 0"
    SKIP_INITRAMFS="0"
fi

# Check if we should skip initramfs
if [ "${SKIP_INITRAMFS}" = "1" ]; then
    echo "SKIP_INITRAMFS=1 detected, applying standard Raspberry Pi disable method..."
    
    # Method 1: Configure raspberrypi-kernel to skip initramfs
    mkdir -p /etc/default
    cat > /etc/default/raspberrypi-kernel <<'EOF'
# Disable initramfs generation - configured by RasQberry build
INITRD=No
EOF

    # Method 2: Create kernel postinst hook for extra safety
    mkdir -p /etc/kernel/postinst.d
    cat > /etc/kernel/postinst.d/00-skip-initramfs <<'EOF'
#!/bin/sh
# RasQberry: Skip initramfs when configured

# Source the config
[ -r /etc/default/raspberrypi-kernel ] && . /etc/default/raspberrypi-kernel

# Check if we should skip initramfs
if [ "$INITRD" = "No" ]; then
    echo "Skipping initramfs generation (INITRD=No via RasQberry config)"
    # Remove any existing initramfs to save space
    rm -f /boot/initrd* /boot/initramfs* 2>/dev/null || true
    # Exit successfully to prevent other scripts from running
    exit 0
fi
EOF
    chmod +x /etc/kernel/postinst.d/00-skip-initramfs

    # Method 3: Configure raspi-firmware for newer systems
    if [ -d /boot/firmware ] || [ -f /usr/lib/raspi-firmware/update ]; then
        mkdir -p /etc/default
        cat > /etc/default/raspi-firmware <<'EOF'
# Don't copy initramfs files to boot partition
INITRAMFS=no
EOF
    fi

    # Method 4: Divert update-initramfs for packages that call it directly
    if command -v update-initramfs >/dev/null 2>&1; then
        dpkg-divert --add --rename --divert /usr/sbin/update-initramfs.real /usr/sbin/update-initramfs
        cat > /usr/sbin/update-initramfs <<'EOF'
#!/bin/sh
echo "Skipping update-initramfs (disabled by RasQberry SKIP_INITRAMFS=1)"
exit 0
EOF
        chmod +x /usr/sbin/update-initramfs
    fi

    # Method 5: Also divert mkinitramfs
    if command -v mkinitramfs >/dev/null 2>&1; then
        dpkg-divert --add --rename --divert /usr/sbin/mkinitramfs.real /usr/sbin/mkinitramfs
        cat > /usr/sbin/mkinitramfs <<'EOF'
#!/bin/sh
echo "Skipping mkinitramfs (disabled by RasQberry SKIP_INITRAMFS=1)"
exit 0
EOF
        chmod +x /usr/sbin/mkinitramfs
    fi

    # Method 6: Remove any initramfs files that might already exist
    rm -f /boot/initrd* /boot/initramfs* 2>/dev/null || true

    echo "Standard Raspberry Pi initramfs disable method applied successfully"
    
else
    echo "SKIP_INITRAMFS not set to 1 (value: '${SKIP_INITRAMFS}'), initramfs will be generated normally"
    
    # Ensure the default behavior is enabled
    if [ -f /etc/default/raspberrypi-kernel ]; then
        # Remove any INITRD=No line to allow normal generation
        sed -i '/^INITRD=No/d' /etc/default/raspberrypi-kernel 2>/dev/null || true
    fi
    
    # Check if diversions exist and remove them
    if dpkg-divert --list | grep -q update-initramfs; then
        echo "Removing update-initramfs diversion to allow normal operation"
        dpkg-divert --remove --rename /usr/sbin/update-initramfs
    fi
    if dpkg-divert --list | grep -q mkinitramfs; then
        echo "Removing mkinitramfs diversion to allow normal operation"
        dpkg-divert --remove --rename /usr/sbin/mkinitramfs
    fi
fi