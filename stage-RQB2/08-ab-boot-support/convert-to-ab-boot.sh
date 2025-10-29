#!/bin/bash
set -euo pipefail

# ============================================================================
# Convert Standard RasQberry Image to A/B Boot Variant
# ============================================================================
# This script takes a standard RasQberry image and converts it to A/B boot
# Designed to run in GitHub Actions with limited disk space
#
# Usage: convert-to-ab-boot.sh <input.img.xz> <output.img.xz>
#
# Strategy:
# - Decompress on-the-fly to loop device (no temp .img file)
# - Modify partitions while mounted
# - Compress output directly (no intermediate storage)

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.img.xz> <output.img.xz>"
    exit 1
fi

INPUT_IMAGE="$1"
OUTPUT_IMAGE="$2"

if [ ! -f "$INPUT_IMAGE" ]; then
    echo "Error: Input image not found: $INPUT_IMAGE"
    exit 1
fi

echo "=== Converting to A/B Boot Image ==="
echo "Input: $INPUT_IMAGE"
echo "Output: $OUTPUT_IMAGE"

# Decompress to temporary uncompressed image
TEMP_IMG="${INPUT_IMAGE%.xz}"
echo "Decompressing image..."
xz -d -k "$INPUT_IMAGE"

if [ ! -f "$TEMP_IMG" ]; then
    echo "Error: Decompression failed"
    exit 1
fi

echo "Image size: $(du -h "$TEMP_IMG" | cut -f1)"

# Setup loop device
echo "Setting up loop device..."
LOOP_DEV=$(sudo losetup -f --show -P "$TEMP_IMG")
echo "Loop device: $LOOP_DEV"

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    sync
    sleep 1
    sudo umount "${MOUNT_POINT}/boot/firmware" 2>/dev/null || true
    sudo umount "${MOUNT_POINT}" 2>/dev/null || true
    sudo losetup -d "$LOOP_DEV" 2>/dev/null || true
    rm -rf "$MOUNT_POINT" 2>/dev/null || true
    rm -f "$TEMP_IMG" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for partition devices
sleep 2
sudo partprobe "$LOOP_DEV"
sleep 1

# Get total device size and calculate slot sizes
DEVICE_SIZE_BYTES=$(sudo blockdev --getsize64 "$LOOP_DEV")
DEVICE_SIZE_SECTORS=$((DEVICE_SIZE_BYTES / 512))
echo "Device size: $((DEVICE_SIZE_BYTES / 1024 / 1024))MB ($DEVICE_SIZE_SECTORS sectors)"

# Get partition 1 (boot) size
P1_START=$(sudo parted "$LOOP_DEV" unit s print | grep "^ 1" | awk '{print $2}' | sed 's/s//')
P1_END=$(sudo parted "$LOOP_DEV" unit s print | grep "^ 1" | awk '{print $3}' | sed 's/s//')
P1_SIZE_SECTORS=$((P1_END - P1_START + 1))
echo "Boot partition size: $((P1_SIZE_SECTORS * 512 / 1024 / 1024))MB"

# Calculate available space for slots (device - boot - alignment overhead)
ALIGNMENT_OVERHEAD_SECTORS=8192  # ~4MB for alignment
AVAILABLE_SECTORS=$((DEVICE_SIZE_SECTORS - P1_END - ALIGNMENT_OVERHEAD_SECTORS))
AVAILABLE_MB=$((AVAILABLE_SECTORS * 512 / 1024 / 1024))

echo "Available space for slots: ${AVAILABLE_MB}MB"

# Each slot gets approximately half the available space
SLOT_SIZE_MB=$((AVAILABLE_MB / 2))
SLOT_A_SIZE_SECTORS=$((SLOT_SIZE_MB * 1024 * 1024 / 512))
SLOT_B_SIZE_SECTORS=$((SLOT_SIZE_MB * 1024 * 1024 / 512))

echo "Calculated slot sizes:"
echo "  Slot A (p2): ${SLOT_SIZE_MB}MB ($SLOT_A_SIZE_SECTORS sectors)"
echo "  Slot B (p3): ${SLOT_SIZE_MB}MB ($SLOT_B_SIZE_SECTORS sectors)"

# Get current partition info
P2_START=$(sudo parted "$LOOP_DEV" unit s print | grep "^ 2" | awk '{print $2}' | sed 's/s//')
echo "Partition 2 starts at sector: $P2_START"

# Shrink filesystem first
echo "Shrinking filesystem to ${SLOT_SIZE_MB}MB..."
sudo e2fsck -f -y "${LOOP_DEV}p2"
sudo resize2fs "${LOOP_DEV}p2" ${SLOT_SIZE_MB}M

# Resize partition 2
P2_NEW_END=$((P2_START + SLOT_A_SIZE_SECTORS - 1))
echo "Resizing partition 2 to end at sector $P2_NEW_END..."
sudo parted "$LOOP_DEV" resizepart 2 ${P2_NEW_END}s

# Create partition 3
P3_START=$((P2_NEW_END + 2048))
P3_END=$((P3_START + SLOT_B_SIZE_SECTORS - 1))
echo "Creating partition 3: sectors $P3_START to $P3_END..."
sudo parted "$LOOP_DEV" mkpart primary ext4 ${P3_START}s ${P3_END}s

# Reload partition table
sudo partprobe "$LOOP_DEV"
sleep 2

# Format partition 3
echo "Formatting Slot B partition..."
sudo mkfs.ext4 -F -L "rootfs_b" "${LOOP_DEV}p3"

# Mount and configure
MOUNT_POINT=$(mktemp -d)
sudo mount "${LOOP_DEV}p2" "$MOUNT_POINT"
sudo mount "${LOOP_DEV}p1" "$MOUNT_POINT/boot/firmware"

# Create tryboot configuration
echo "Configuring A/B boot..."
sudo tee "$MOUNT_POINT/boot/firmware/tryboot.txt" > /dev/null << 'EOF'
# RasQberry A/B Boot Tryboot Configuration
[all]
os_prefix=slot_b/
EOF

sudo tee "$MOUNT_POINT/boot/firmware/autoboot.txt" > /dev/null << 'EOF'
# RasQberry A/B Boot Autoboot Configuration
# tryboot_a_b=1 enables tryboot mode
EOF

echo "A" | sudo tee "$MOUNT_POINT/boot/firmware/current-slot" > /dev/null

# Disable filesystem expansion
echo "Disabling filesystem expansion..."
sudo rm -f "$MOUNT_POINT/usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh"
sudo mkdir -p "$MOUNT_POINT/var/lib/rasqberry-firstboot"
sudo touch "$MOUNT_POINT/var/lib/rasqberry-firstboot/01-expand-filesystem.sh.done"

# Unmount
sudo umount "$MOUNT_POINT/boot/firmware"
sudo umount "$MOUNT_POINT"
sudo losetup -d "$LOOP_DEV"

# Compress the modified image
echo "Compressing A/B boot image..."
xz -T0 -v "$TEMP_IMG"
mv "${TEMP_IMG}.xz" "$OUTPUT_IMAGE"

echo "=== A/B Boot Image Created Successfully ==="
echo "Output: $OUTPUT_IMAGE"
echo "Size: $(du -h "$OUTPUT_IMAGE" | cut -f1)"