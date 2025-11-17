#!/bin/bash
# ============================================================================
# RasQberry A/B Boot Image Converter v2
# ============================================================================
# Purpose: Convert a standard RasQberry image to 6-partition A/B layout
#
# Input: Standard RasQberry .img file (uncompressed, 2 partitions)
# Output: AB-ready .img file (6 partitions with extended partition)
#
# Partition Layout Created:
#   p1: bootfs-common    512MB   primary   FAT32   (autoboot.txt, config.txt, bootcode.bin)
#   p2: bootfs-a         512MB   primary   FAT32   (boot files from input)
#   p3: bootfs-b         512MB   primary   FAT32   (copy of p2)
#   p4: extended         (rest)  extended  -
#     p5: rootfs-a       ~8GB    logical   ext4    (rootfs from input)
#     p6: rootfs-b       16MB    logical   ext4    (empty placeholder)
#
# Usage: ./convert-to-ab-boot-v2.sh <input.img> <output.img>
# ============================================================================

set -euo pipefail

# Check arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.img> <output.img>"
    echo ""
    echo "Converts a standard RasQberry image to A/B boot layout"
    exit 1
fi

INPUT_IMG="$1"
OUTPUT_IMG="$2"

# Verify input exists
if [ ! -f "$INPUT_IMG" ]; then
    echo "ERROR: Input image not found: $INPUT_IMG"
    exit 1
fi

# Verify output doesn't exist
if [ -f "$OUTPUT_IMG" ]; then
    echo "ERROR: Output image already exists: $OUTPUT_IMG"
    exit 1
fi

echo "=== RasQberry A/B Boot Image Converter v2 ==="
echo ""
echo "Input:  $INPUT_IMG"
echo "Output: $OUTPUT_IMG"
echo ""

# Calculate image sizes
BOOTFS_COMMON_SIZE_MB=512
BOOTFS_A_SIZE_MB=512
BOOTFS_B_SIZE_MB=512
ROOTFS_A_SIZE_MB=8192  # 8GB for rootfs-a
ROOTFS_B_SIZE_MB=16    # 16MB placeholder for rootfs-b

TOTAL_SIZE_MB=$((BOOTFS_COMMON_SIZE_MB + BOOTFS_A_SIZE_MB + BOOTFS_B_SIZE_MB + ROOTFS_A_SIZE_MB + ROOTFS_B_SIZE_MB + 100))
echo "Target image size: ${TOTAL_SIZE_MB}MB (~$(($TOTAL_SIZE_MB / 1024))GB)"
echo ""

# Create output image file
echo "Step 1: Creating output image file (${TOTAL_SIZE_MB}MB)..."
dd if=/dev/zero of="$OUTPUT_IMG" bs=1M count="$TOTAL_SIZE_MB" status=none
echo "Created ${TOTAL_SIZE_MB}MB image file"
echo ""

# Partition the output image with MBR + extended partition
echo "Step 2: Creating partition layout..."
echo ""
parted -s "$OUTPUT_IMG" mklabel msdos

# Create 3 primary partitions
parted -s "$OUTPUT_IMG" mkpart primary fat32 1MiB $((BOOTFS_COMMON_SIZE_MB + 1))MiB
parted -s "$OUTPUT_IMG" mkpart primary fat32 $((BOOTFS_COMMON_SIZE_MB + 1))MiB $((BOOTFS_COMMON_SIZE_MB + BOOTFS_A_SIZE_MB + 1))MiB
parted -s "$OUTPUT_IMG" mkpart primary fat32 $((BOOTFS_COMMON_SIZE_MB + BOOTFS_A_SIZE_MB + 1))MiB $((BOOTFS_COMMON_SIZE_MB + BOOTFS_A_SIZE_MB + BOOTFS_B_SIZE_MB + 1))MiB

# Create extended partition containing logical partitions
EXTENDED_START=$((BOOTFS_COMMON_SIZE_MB + BOOTFS_A_SIZE_MB + BOOTFS_B_SIZE_MB + 1))
parted -s "$OUTPUT_IMG" mkpart extended ${EXTENDED_START}MiB 100%

# Create logical partitions inside extended
ROOTFS_A_START=$((EXTENDED_START + 1))
ROOTFS_A_END=$((ROOTFS_A_START + ROOTFS_A_SIZE_MB))
ROOTFS_B_START=$((ROOTFS_A_END + 1))

parted -s "$OUTPUT_IMG" mkpart logical ext4 ${ROOTFS_A_START}MiB ${ROOTFS_A_END}MiB
parted -s "$OUTPUT_IMG" mkpart logical ext4 ${ROOTFS_B_START}MiB 100%

# Set boot flag on p1
parted -s "$OUTPUT_IMG" set 1 boot on

echo "Partition layout created:"
parted "$OUTPUT_IMG" print
echo ""

# Set up loop devices
echo "Step 3: Setting up loop devices..."
OUTPUT_LOOP=$(losetup -fP --show "$OUTPUT_IMG")
INPUT_LOOP=$(losetup -fP --show "$INPUT_IMG")

echo "Output loop: $OUTPUT_LOOP"
echo "Input loop:  $INPUT_LOOP"
echo ""

# Format partitions
echo "Step 4: Formatting partitions..."
mkfs.vfat -F 32 -n "bootfs-cmn" "${OUTPUT_LOOP}p1"
mkfs.vfat -F 32 -n "bootfs-a" "${OUTPUT_LOOP}p2"
mkfs.vfat -F 32 -n "bootfs-b" "${OUTPUT_LOOP}p3"
mkfs.ext4 -F -L rootfs_a "${OUTPUT_LOOP}p5"
mkfs.ext4 -F -L rootfs_b "${OUTPUT_LOOP}p6"
echo ""

# Verify ext4 labels were set correctly
echo "Verifying ext4 filesystem labels..."
LABEL_P5=$(e2label "${OUTPUT_LOOP}p5" 2>/dev/null || echo "FAILED")
LABEL_P6=$(e2label "${OUTPUT_LOOP}p6" 2>/dev/null || echo "FAILED")
echo "  p5 label: ${LABEL_P5}"
echo "  p6 label: ${LABEL_P6}"
if [ "$LABEL_P5" != "rootfs_a" ] || [ "$LABEL_P6" != "rootfs_b" ]; then
    echo "ERROR: Filesystem labels not set correctly!"
    exit 1
fi
echo ""

# Mount partitions
echo "Step 5: Mounting partitions..."
MOUNT_DIR=$(mktemp -d)
mkdir -p "${MOUNT_DIR}"/{bootfs-common,bootfs-a,bootfs-b,rootfs-a,rootfs-b,input-boot,input-root}

mount "${OUTPUT_LOOP}p1" "${MOUNT_DIR}/bootfs-common"
mount "${OUTPUT_LOOP}p2" "${MOUNT_DIR}/bootfs-a"
mount "${OUTPUT_LOOP}p3" "${MOUNT_DIR}/bootfs-b"
mount "${OUTPUT_LOOP}p5" "${MOUNT_DIR}/rootfs-a"
mount "${OUTPUT_LOOP}p6" "${MOUNT_DIR}/rootfs-b"

mount "${INPUT_LOOP}p1" "${MOUNT_DIR}/input-boot"
mount "${INPUT_LOOP}p2" "${MOUNT_DIR}/input-root"
echo ""

# Copy boot files from input to p2 (bootfs-a)
echo "Step 6: Copying boot files to p2 (bootfs-a)..."
rsync -aAX "${MOUNT_DIR}/input-boot/" "${MOUNT_DIR}/bootfs-a/"
echo ""

# Copy boot files to p3 (bootfs-b) - exact copy of p2
echo "Step 7: Copying boot files to p3 (bootfs-b)..."
rsync -aAX "${MOUNT_DIR}/bootfs-a/" "${MOUNT_DIR}/bootfs-b/"
echo ""

# Use device paths for boot (survive dd/flash and work with standard initramfs)
echo "Step 8: Configuring boot to use device paths..."

# Device paths (/dev/mmcblk0pX) are stable across dd/flash operations because they
# are based on partition table structure, not disk signatures or UUIDs.
# The standard Raspberry Pi initramfs supports device paths but may not support LABELs.

echo "Using device paths for boot (survive dd/flash):"
echo "  p1: /dev/mmcblk0p1 (bootfs-common)"
echo "  p2: /dev/mmcblk0p2 (bootfs Slot A)"
echo "  p3: /dev/mmcblk0p3 (bootfs Slot B)"
echo "  p5: /dev/mmcblk0p5 (rootfs Slot A)"
echo "  p6: /dev/mmcblk0p6 (rootfs Slot B)"
echo ""

# Update cmdline.txt on p2 to use device path for rootfs-a (p5)
echo "Step 9: Updating cmdline.txt on p2 for rootfs-a (/dev/mmcblk0p5)..."
# Replace any root= parameter with /dev/mmcblk0p5
sed -i "s|root=[^ ]*|root=/dev/mmcblk0p5|g" "${MOUNT_DIR}/bootfs-a/cmdline.txt"
echo "Updated: ${MOUNT_DIR}/bootfs-a/cmdline.txt"
grep "root=" "${MOUNT_DIR}/bootfs-a/cmdline.txt"
echo ""

# Update cmdline.txt on p3 to use device path for rootfs-b (p6)
echo "Step 10: Updating cmdline.txt on p3 for rootfs-b (/dev/mmcblk0p6)..."
sed -i "s|root=[^ ]*|root=/dev/mmcblk0p6|g" "${MOUNT_DIR}/bootfs-b/cmdline.txt"
echo "Updated: ${MOUNT_DIR}/bootfs-b/cmdline.txt"
grep "root=" "${MOUNT_DIR}/bootfs-b/cmdline.txt"
echo ""

# Create autoboot.txt and config.txt on p1 (bootfs-common)
echo "Step 11: Creating boot files on p1 (bootfs-common)..."

# Create autoboot.txt
cat > "${MOUNT_DIR}/bootfs-common/autoboot.txt" << 'EOF'
# RasQberry A/B Boot Configuration
# This file controls which boot partition the firmware uses

[all]
# Enable A/B boot support
tryboot_a_b=1

# Default boot partition (Slot A)
boot_partition=2

[tryboot]
# Tryboot partition (Slot B)
boot_partition=3
EOF

# Create empty config.txt (required by firmware for autoboot to work)
touch "${MOUNT_DIR}/bootfs-common/config.txt"

# Create skip-expansion marker to prevent firstboot expansion on AB images
# AB images already have correctly-sized p5/p6 partitions that expand at runtime
touch "${MOUNT_DIR}/bootfs-common/skip-expansion"

# Copy bootcode.bin for older Pi models (if it exists in source)
if [ -f "${MOUNT_DIR}/input-boot/bootcode.bin" ]; then
    cp "${MOUNT_DIR}/input-boot/bootcode.bin" "${MOUNT_DIR}/bootfs-common/"
    echo "Copied bootcode.bin for older Pi models"
fi

echo "Created autoboot.txt:"
cat "${MOUNT_DIR}/bootfs-common/autoboot.txt"
echo "Created empty config.txt"
echo "Created skip-expansion marker (prevents filesystem expansion on AB images)"
echo ""

# Copy rootfs from input to p5 (rootfs-a)
echo "Step 12: Copying rootfs to p5 (rootfs-a)... (this will take several minutes)"
rsync -aAX "${MOUNT_DIR}/input-root/" "${MOUNT_DIR}/rootfs-a/"
echo "Rootfs copy complete"
echo ""

# Update /etc/fstab on p5 (rootfs-a) with device paths
echo "Step 13: Updating /etc/fstab on rootfs-a with device paths..."
cat > "${MOUNT_DIR}/rootfs-a/etc/fstab" << 'EOF'
proc               /proc                 proc    defaults          0       0
/dev/mmcblk0p1     /boot/firmware-common vfat    defaults          0       2
/dev/mmcblk0p2     /boot/firmware        vfat    defaults          0       2
/dev/mmcblk0p5     /                     ext4    defaults,noatime  0       1
EOF

# Create mount point for bootfs-common
mkdir -p "${MOUNT_DIR}/rootfs-a/boot/firmware-common"

echo "Updated fstab:"
cat "${MOUNT_DIR}/rootfs-a/etc/fstab"
echo ""

# p6 (rootfs-b) stays empty - it's a placeholder that will be expanded and populated at firstboot

# Unmount all
echo "Step 14: Unmounting partitions..."
umount "${MOUNT_DIR}/bootfs-common"
umount "${MOUNT_DIR}/bootfs-a"
umount "${MOUNT_DIR}/bootfs-b"
umount "${MOUNT_DIR}/rootfs-a"
umount "${MOUNT_DIR}/rootfs-b"
umount "${MOUNT_DIR}/input-boot"
umount "${MOUNT_DIR}/input-root"

rmdir "${MOUNT_DIR}"/{bootfs-common,bootfs-a,bootfs-b,rootfs-a,rootfs-b,input-boot,input-root}
rmdir "${MOUNT_DIR}"
echo ""

# Detach loop devices
echo "Step 15: Detaching loop devices..."
losetup -d "$OUTPUT_LOOP"
losetup -d "$INPUT_LOOP"
echo ""

# Verify output
echo "Step 16: Verifying output image..."
OUTPUT_SIZE=$(du -h "$OUTPUT_IMG" | cut -f1)
echo "Output image size: $OUTPUT_SIZE"
echo ""

echo "=== Conversion Complete ==="
echo ""
echo "AB-ready image created: $OUTPUT_IMG"
echo ""
echo "Partition layout:"
echo "  p1: bootfs-common (512MB, FAT32) - autoboot.txt, config.txt, bootcode.bin"
echo "  p2: bootfs-a (512MB, FAT32) - boot files for Slot A"
echo "  p3: bootfs-b (512MB, FAT32) - boot files for Slot B"
echo "  p4: extended partition"
echo "    p5: rootfs-a (~8GB, ext4) - full RasQberry system"
echo "    p6: rootfs-b (16MB, ext4) - placeholder, will expand at firstboot"
echo ""
echo "Next steps:"
echo "  1. Compress with highest compression: xz -9 -T0 $OUTPUT_IMG"
echo "     (Target: <2GB compressed size)"
echo "  2. Flash to SD card"
echo "  3. On first boot, p5 and p6 will expand to fill SD card"
echo ""