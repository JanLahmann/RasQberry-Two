#!/bin/bash
# ============================================================================
# RasQberry Firstboot Task: Expand A/B Partitions
# ============================================================================
# Purpose: Expand p5 (rootfs-a) and p6 (rootfs-b) to fill SD card
#
# This task runs only on AB-enabled images (6-partition layout)
# It expands:
#   - p5 (rootfs-a) to half of remaining SD card space
#   - p6 (rootfs-b) to fill other half of remaining space
#
# Exit codes:
#   0 = Success (expansion completed)
#   0 = Skipped (not an AB image)
#   1 = Error (expansion failed)
# ============================================================================

echo "Checking for A/B partition layout..."

# Detect root device
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
DEVICE="/dev/${ROOT_DEV}"

echo "Root partition: $ROOT_PART"
echo "Root device: $DEVICE"

# Check if this is an AB image by looking for p1 with label "config"
BOOTFS_COMMON=$(lsblk -no label "${DEVICE}p1" 2>/dev/null || lsblk -no label "${DEVICE}1" 2>/dev/null || echo "")

if [ "$BOOTFS_COMMON" != "config" ]; then
    echo "Not an A/B boot image (config partition not found)"
    echo "Skipping A/B partition expansion"
    exit 0
fi

echo "A/B boot image detected"

# Check current root partition - should be p5 for Slot A
if [[ ! "$ROOT_PART" =~ p5$ ]] && [[ ! "$ROOT_PART" =~ 5$ ]]; then
    echo "ERROR: Expected root on p5, but found: $ROOT_PART"
    echo "This task only runs when booted from Slot A (p5)"
    exit 1
fi

echo "Booted from Slot A (p5) - proceeding with expansion"

# Get device and partition sizes
DEVICE_SIZE_SECTORS=$(cat /sys/block/${ROOT_DEV}/size)
DEVICE_SIZE_GB=$((DEVICE_SIZE_SECTORS * 512 / 1024 / 1024 / 1024))

echo "SD card size: ${DEVICE_SIZE_GB}GB"

# Get current partition layout
P4_START=$(parted "$DEVICE" unit s print | grep "^ 4" | awk '{print $2}' | sed 's/s//')
P5_START=$(parted "$DEVICE" unit s print | grep "^ 5" | awk '{print $2}' | sed 's/s//')
P5_END=$(parted "$DEVICE" unit s print | grep "^ 5" | awk '{print $3}' | sed 's/s//')
P6_START=$(parted "$DEVICE" unit s print | grep "^ 6" | awk '{print $2}' | sed 's/s//')
P6_END=$(parted "$DEVICE" unit s print | grep "^ 6" | awk '{print $3}' | sed 's/s//')

P5_CURRENT_GB=$(((P5_END - P5_START) * 512 / 1024 / 1024 / 1024))
P6_CURRENT_GB=$(((P6_END - P6_START) * 512 / 1024 / 1024 / 1024))

echo "Current p5 (rootfs-a) size: ${P5_CURRENT_GB}GB"
echo "Current p6 (rootfs-b) size: ${P6_CURRENT_GB}GB"

# Check if already expanded (p5 is larger than 20GB means it's been expanded)
if [ $P5_CURRENT_GB -gt 20 ]; then
    echo "A/B partitions already expanded (p5 is ${P5_CURRENT_GB}GB)"
    exit 0
fi

# Calculate target sizes - split remaining space equally
# Leave 1GB margin for partition alignment
AVAILABLE_SPACE_GB=$((DEVICE_SIZE_GB - 2))  # Total minus boot partitions (~1.5GB) and margin
SLOT_SIZE_GB=$((AVAILABLE_SPACE_GB / 2))

echo "Target slot size: ${SLOT_SIZE_GB}GB each"

if [ $SLOT_SIZE_GB -lt 10 ]; then
    echo "ERROR: SD card too small for A/B boot (need at least 32GB)"
    echo "Available space: ${AVAILABLE_SPACE_GB}GB, need at least 20GB"
    exit 1
fi

# Calculate partition boundaries in sectors
SLOT_SIZE_SECTORS=$((SLOT_SIZE_GB * 1024 * 1024 * 1024 / 512))
P5_NEW_END=$((P5_START + SLOT_SIZE_SECTORS))
P6_NEW_END=$((P6_START + SLOT_SIZE_SECTORS))

# Make sure p6 doesn't exceed device size
if [ $P6_NEW_END -gt $((DEVICE_SIZE_SECTORS - 2048)) ]; then
    P6_NEW_END=$((DEVICE_SIZE_SECTORS - 2048))
    echo "Adjusted p6 end to fit device: sector $P6_NEW_END"
fi

echo ""
echo "=== Expanding A/B Partitions ==="
echo ""
echo "This will:"
echo "  - Expand p4 (extended) to end of device"
echo "  - Expand p5 (rootfs-a) to ${SLOT_SIZE_GB}GB"
echo "  - Expand p6 (rootfs-b) to fill remaining space"
echo ""

# Step 1: Expand p4 (extended partition) to fill device
echo "Step 1: Expanding p4 (extended partition)..."
parted "$DEVICE" resizepart 4 100%
partprobe "$DEVICE"
sleep 2

# Step 2: Expand p5 (rootfs-a)
echo "Step 2: Expanding p5 (rootfs-a) to sector ${P5_NEW_END}..."
parted "$DEVICE" resizepart 5 ${P5_NEW_END}s
partprobe "$DEVICE"
sleep 2

# Step 3: Resize p5 filesystem
echo "Step 3: Expanding p5 filesystem..."
resize2fs "$ROOT_PART"

# Step 4: Expand p6 (rootfs-b)
echo "Step 4: Expanding p6 (rootfs-b) to sector ${P6_NEW_END}..."
parted "$DEVICE" resizepart 6 ${P6_NEW_END}s
partprobe "$DEVICE"
sleep 2

# Step 5: Resize p6 filesystem
echo "Step 5: Expanding p6 filesystem..."
# Find p6 device
if [ -b "${DEVICE}p6" ]; then
    P6_PART="${DEVICE}p6"
elif [ -b "${DEVICE}6" ]; then
    P6_PART="${DEVICE}6"
else
    echo "ERROR: Cannot find p6 partition device"
    exit 1
fi

resize2fs "$P6_PART"

echo ""
echo "=== A/B Partition Expansion Complete ==="
echo ""

# Show new layout
echo "New partition layout:"
parted "$DEVICE" print

echo ""
echo "Partition sizes:"
df -h / | tail -1 | awk '{print "  p5 (rootfs-a): " $2 " (" $5 " used)"}'
df -h "$P6_PART" 2>/dev/null | tail -1 | awk '{print "  p6 (rootfs-b): " $2}' || echo "  p6 (rootfs-b): Not mounted"

echo ""
echo "A/B boot system ready!"
echo "  - Slot A (current): Ready with expanded storage"
echo "  - Slot B: Empty, ready for image installation"
echo ""