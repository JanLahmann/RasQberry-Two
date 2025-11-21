#!/bin/bash
# ============================================================================
# RasQberry Firstboot Task: Expand Data Partition
# ============================================================================
# Purpose: Expand p7 (data) to fill remaining SD card space
#
# In the new A/B layout:
#   - p5 (system-a) and p6 (system-b) are fixed size (4GB each)
#   - Only p7 (data) needs expansion
#
# This keeps system partitions stable and only grows user data space.
#
# Exit codes:
#   0 = Success (expansion completed or skipped)
#   1 = Error (expansion failed)
# ============================================================================

echo "Checking for A/B partition layout..."

# Detect root device
ROOT_PART=$(findmnt / -o source -n)
ROOT_DEV=$(lsblk -no pkname "$ROOT_PART")
DEVICE="/dev/${ROOT_DEV}"

echo "Root partition: $ROOT_PART"
echo "Root device: $DEVICE"

# Check if this is the new A/B layout by looking for p1 with label "config"
CONFIG_LABEL=$(lsblk -no label "${DEVICE}p1" 2>/dev/null || lsblk -no label "${DEVICE}1" 2>/dev/null || echo "")

if [ "$CONFIG_LABEL" != "config" ]; then
    # Also check for old-style "bootfs-cmn" label
    if [ "$CONFIG_LABEL" = "bootfs-cmn" ]; then
        echo "Old-style A/B layout detected (bootfs-cmn)"
        echo "This script is for the new layout - skipping"
        exit 0
    fi
    echo "Not an A/B boot image (config partition not found)"
    echo "Skipping data partition expansion"
    exit 0
fi

echo "A/B boot image detected (new layout)"

# Find p7 partition
if [ -b "${DEVICE}p7" ]; then
    P7_PART="${DEVICE}p7"
elif [ -b "${DEVICE}7" ]; then
    P7_PART="${DEVICE}7"
else
    echo "ERROR: Cannot find p7 (data) partition"
    exit 1
fi

# Check if p7 exists and has "data" label
DATA_LABEL=$(lsblk -no label "$P7_PART" 2>/dev/null || echo "")
if [ "$DATA_LABEL" != "data" ]; then
    echo "WARNING: p7 doesn't have 'data' label (found: '$DATA_LABEL')"
    echo "Skipping expansion"
    exit 0
fi

echo "Data partition: $P7_PART"

# Get device and partition sizes
DEVICE_SIZE_SECTORS=$(cat /sys/block/${ROOT_DEV}/size)
DEVICE_SIZE_GB=$((DEVICE_SIZE_SECTORS * 512 / 1024 / 1024 / 1024))

echo "SD card size: ${DEVICE_SIZE_GB}GB"

# Get current p7 info
P7_START=$(parted "$DEVICE" unit s print | grep "^ 7" | awk '{print $2}' | sed 's/s//')
P7_END=$(parted "$DEVICE" unit s print | grep "^ 7" | awk '{print $3}' | sed 's/s//')

if [ -z "$P7_START" ] || [ -z "$P7_END" ]; then
    echo "ERROR: Could not get p7 partition boundaries"
    exit 1
fi

P7_CURRENT_MB=$(((P7_END - P7_START) * 512 / 1024 / 1024))

echo "Current p7 (data) size: ${P7_CURRENT_MB}MB"

# Check if already expanded (p7 is larger than 1GB means it's been expanded)
if [ $P7_CURRENT_MB -gt 1024 ]; then
    echo "Data partition already expanded (${P7_CURRENT_MB}MB)"
    exit 0
fi

# Calculate new end - leave 2048 sectors margin
P7_NEW_END=$((DEVICE_SIZE_SECTORS - 2048))

echo ""
echo "=== Expanding Data Partition ==="
echo ""
echo "This will:"
echo "  - Expand p4 (extended) to end of device"
echo "  - Expand p7 (data) to fill remaining space"
echo ""

# Step 1: Expand p4 (extended partition) to fill device
echo "Step 1: Expanding p4 (extended partition)..."
parted "$DEVICE" resizepart 4 100%
partprobe "$DEVICE"
sleep 2

# Step 2: Expand p7 (data)
echo "Step 2: Expanding p7 (data) to sector ${P7_NEW_END}..."
parted "$DEVICE" resizepart 7 ${P7_NEW_END}s
partprobe "$DEVICE"
sleep 2

# Step 3: Resize p7 filesystem
echo "Step 3: Expanding p7 filesystem..."
resize2fs "$P7_PART"

echo ""
echo "=== Data Partition Expansion Complete ==="
echo ""

# Show result
P7_NEW_END_ACTUAL=$(parted "$DEVICE" unit s print | grep "^ 7" | awk '{print $3}' | sed 's/s//')
P7_NEW_SIZE_GB=$(((P7_NEW_END_ACTUAL - P7_START) * 512 / 1024 / 1024 / 1024))

echo "Data partition (p7) expanded to ${P7_NEW_SIZE_GB}GB"

# Show partition layout
echo ""
echo "Partition layout:"
parted "$DEVICE" print

# Show disk usage
echo ""
echo "Disk usage:"
df -h "$P7_PART" | tail -1 | awk '{print "  p7 (data): " $2 " total, " $4 " available"}'

echo ""
echo "A/B boot system ready!"
echo "  - System partitions: Fixed size (4GB each)"
echo "  - Data partition: Expanded to fill SD card"
echo ""