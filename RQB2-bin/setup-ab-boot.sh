#!/bin/bash
# ============================================================================
# RasQberry A/B Boot Setup Script
# ============================================================================
# Purpose: Convert a standard RasQberry installation to A/B boot configuration
#
# Prerequisites:
# - Standard RasQberry image burned to large SD card (64GB+ recommended)
# - Filesystem expansion disabled on first boot (create marker file)
# - System booted and running from Slot A
#
# What this script does:
# 1. Expands current partition (Slot A) to half of SD card
# 2. Creates second partition (Slot B) in remaining space
# 3. Configures boot files for A/B operation
#
# Usage: sudo ./setup-ab-boot.sh
# ============================================================================

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

echo "=== RasQberry A/B Boot Setup ==="
echo
echo "This script will:"
echo "  1. Expand Slot A to half of your SD card"
echo "  2. Create Slot B partition in the other half"
echo "  3. Configure A/B boot system"
echo
echo "WARNING: This will repartition your SD card!"
echo

# Get confirmation
read -p "Continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Setup cancelled."
    exit 0
fi

# Detect root device
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
DEVICE="/dev/${ROOT_DEV}"

echo
echo "Root partition: $ROOT_PART"
echo "Root device: $DEVICE"

# Get device size
DEVICE_SIZE_SECTORS=$(cat /sys/block/${ROOT_DEV}/size)
DEVICE_SIZE_GB=$((DEVICE_SIZE_SECTORS * 512 / 1024 / 1024 / 1024))

echo "Device size: ${DEVICE_SIZE_GB}GB"

if [ $DEVICE_SIZE_GB -lt 32 ]; then
    echo "Error: Device too small for A/B boot (minimum 32GB recommended)"
    exit 1
fi

# Calculate slot sizes (each gets roughly half, leaving some margin)
SLOT_SIZE_GB=$((DEVICE_SIZE_GB / 2 - 2))  # Leave 2GB margin

echo
echo "Configuration:"
echo "  Slot A (current): ${SLOT_SIZE_GB}GB"
echo "  Slot B (new): ${SLOT_SIZE_GB}GB"
echo

# Check current partition layout
echo "Current partition layout:"
parted "$DEVICE" print

# Get partition 2 info
P2_START=$(parted "$DEVICE" unit s print | grep "^ 2" | awk '{print $2}' | sed 's/s//')
P2_END=$(parted "$DEVICE" unit s print | grep "^ 2" | awk '{print $3}' | sed 's/s//')
P2_CURRENT_GB=$(((P2_END - P2_START) * 512 / 1024 / 1024 / 1024))

echo
echo "Partition 2 current size: ${P2_CURRENT_GB}GB"

# Step 1: Resize partition 2 to target size
SLOT_SIZE_SECTORS=$((SLOT_SIZE_GB * 1024 * 1024 * 1024 / 512))
P2_NEW_END=$((P2_START + SLOT_SIZE_SECTORS))

echo
echo "Step 1: Resizing partition 2 (Slot A) to ${SLOT_SIZE_GB}GB..."

if [ $P2_CURRENT_GB -lt $SLOT_SIZE_GB ]; then
    echo "  Expanding partition 2..."
    parted "$DEVICE" resizepart 2 ${P2_NEW_END}s

    echo "  Expanding filesystem..."
    resize2fs "$ROOT_PART"

    echo "  Slot A expanded successfully"
elif [ $P2_CURRENT_GB -gt $SLOT_SIZE_GB ]; then
    echo "  ERROR: Partition 2 is larger than target size!"
    echo "  Current size: ${P2_CURRENT_GB}GB"
    echo "  Target size: ${SLOT_SIZE_GB}GB"
    echo
    echo "  Cannot shrink mounted filesystem. Please:"
    echo "  1. Start over with fresh image"
    echo "  2. Ensure filesystem expansion was disabled on first boot"
    exit 1
else
    echo "  Partition 2 already at target size, skipping resize"
fi

# Reload partition table
partprobe "$DEVICE"
sleep 2

# Step 2: Create partition 3 (Slot B)
echo
echo "Step 2: Creating partition 3 (Slot B)..."

# Check if partition 3 already exists
if parted "$DEVICE" print | grep -q "^ 3"; then
    echo "  Partition 3 already exists, skipping creation"
else
    P3_START=$((P2_NEW_END + 2048))  # 1MB alignment

    echo "  Creating partition starting at sector ${P3_START}..."
    parted "$DEVICE" mkpart primary ext4 ${P3_START}s 100%

    # Reload and wait for device
    partprobe "$DEVICE"
    sleep 2

    echo "  Formatting partition 3..."
    mkfs.ext4 -F -L "rootfs_b" "${DEVICE}p3" || mkfs.ext4 -F -L "rootfs_b" "${DEVICE}3"

    echo "  Slot B created successfully"
fi

# Step 3: Configure A/B boot files
echo
echo "Step 3: Configuring A/B boot files..."

BOOT_DIR="/boot/firmware"

# Create tryboot configuration
cat > "${BOOT_DIR}/tryboot.txt" << 'EOF'
# RasQberry A/B Boot Tryboot Configuration
# This config is used when booting into Slot B (tryboot mode)
[all]
os_prefix=slot_b/
EOF

# Create autoboot configuration
cat > "${BOOT_DIR}/autoboot.txt" << 'EOF'
# RasQberry A/B Boot Autoboot Configuration
# This is the normal boot configuration for Slot A
[all]
# No os_prefix - boots from root of partition 2
EOF

# Set current slot marker
echo "A" > "${BOOT_DIR}/current-slot"

echo "  Boot configuration files created"

# Step 4: Summary
echo
echo "=== A/B Boot Setup Complete ==="
echo
echo "Partition layout:"
parted "$DEVICE" print
echo
echo "Next steps:"
echo "  1. System is running in Slot A (stable baseline)"
echo "  2. To test Slot B, download a new image:"
echo "     wget <image-url>"
echo "     sudo bash -c 'xz -dc image.img.xz | dd of=${DEVICE}p3 bs=4M status=progress'"
echo "  3. Reboot to Slot B:"
echo "     sudo reboot-to-slot-b"
echo "  4. Health check will run (60 seconds to verify)"
echo "  5. If healthy: Slot B becomes default"
echo "     If unhealthy: System rolls back to Slot A"
echo
echo "A/B boot is now active!"