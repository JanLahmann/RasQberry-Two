#!/bin/bash -e
# ============================================================================
# RasQberry: Generate Initramfs (Final Stage)
# ============================================================================
# Description: Restore and generate initramfs at the very end of the build
#
# This runs AFTER all packages are installed and configured, generating
# initramfs only once per kernel instead of 6+ times during package installs.
#
# Time savings: ~12 minutes per build
# ============================================================================

echo "=== Initramfs Final Generation Stage ==="

# Check if we should generate initramfs
if [ "${SKIP_INITRAMFS:-0}" = "1" ]; then
    echo "SKIP_INITRAMFS=1: Skipping initramfs generation entirely"
    echo "Image will have NO initramfs (fast build, may not boot on all hardware)"
    exit 0
fi

echo "SKIP_INITRAMFS=0: Generating initramfs for all kernels"
echo ""

# Restore the real update-initramfs and mkinitramfs commands
echo "Restoring real initramfs tools..."

if [ -f /usr/sbin/update-initramfs.real ]; then
    dpkg-divert --remove --rename /usr/sbin/update-initramfs
    echo "✓ update-initramfs restored"
else
    echo "⚠ update-initramfs.real not found (not diverted?)"
fi

if [ -f /usr/sbin/mkinitramfs.real ]; then
    dpkg-divert --remove --rename /usr/sbin/mkinitramfs
    echo "✓ mkinitramfs restored"
else
    echo "⚠ mkinitramfs.real not found (not diverted?)"
fi

echo ""
echo "Generating initramfs for all installed kernels..."
echo ""

# Find all kernel versions
KERNEL_VERSIONS=$(ls /lib/modules/)

if [ -z "$KERNEL_VERSIONS" ]; then
    echo "ERROR: No kernel modules found in /lib/modules/"
    exit 1
fi

KERNEL_COUNT=$(echo "$KERNEL_VERSIONS" | wc -l)
echo "Found $KERNEL_COUNT kernel(s) to process:"
echo "$KERNEL_VERSIONS"
echo ""

# Generate initramfs for each kernel
CURRENT=0
for KERNEL_VERSION in $KERNEL_VERSIONS; do
    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$KERNEL_COUNT] Generating initramfs for kernel: $KERNEL_VERSION"

    START_TIME=$(date +%s)

    # Generate initramfs
    update-initramfs -c -k "$KERNEL_VERSION"

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Verify it was created
    INITRD_FILE="/boot/initrd.img-${KERNEL_VERSION}"
    if [ -f "$INITRD_FILE" ]; then
        SIZE=$(du -h "$INITRD_FILE" | cut -f1)
        echo "  ✓ Created: $INITRD_FILE ($SIZE) in ${DURATION}s"
    else
        echo "  ✗ ERROR: Failed to create $INITRD_FILE"
        exit 1
    fi

    echo ""
done

echo "=== Initramfs Generation Complete ==="
echo "Total kernels processed: $KERNEL_COUNT"
echo ""
echo "Initramfs files:"
ls -lh /boot/initrd.img-* 2>/dev/null || echo "  (none found)"
echo ""

# Ensure the firmware directory has the initramfs files
# (pi-gen may expect them in /boot/firmware/)
if [ -d /boot/firmware ]; then
    echo "Copying initramfs to /boot/firmware/ (if needed)..."
    for INITRD in /boot/initrd.img-*; do
        BASENAME=$(basename "$INITRD")
        if [ ! -f "/boot/firmware/$BASENAME" ]; then
            cp "$INITRD" "/boot/firmware/"
            echo "  ✓ Copied $BASENAME to /boot/firmware/"
        else
            echo "  - $BASENAME already in /boot/firmware/"
        fi
    done
    echo ""
fi

echo "Initramfs generation stage completed successfully"