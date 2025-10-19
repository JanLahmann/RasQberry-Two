#!/bin/bash -e

# This script shrinks the root partition to enable automatic filesystem expansion
# on first boot. Pi-gen creates images with root partition already at full size,
# which prevents the raspberrypi-sys-mods firstboot script from expanding it.

echo "Shrinking root partition to enable automatic expansion on first boot"

IMG_FILE="${STAGE_WORK_DIR}/${IMG_FILENAME}${IMG_SUFFIX}.img"

# Unmount the image
unmount_image "${IMG_FILE}"

# Get the current image info
CURRENT_SIZE=$(stat -c%s "${IMG_FILE}")
echo "Current image size: $((CURRENT_SIZE / 1024 / 1024)) MB"

# We'll shrink the root partition to about 2/3 of current size
# This leaves room for expansion while keeping the compressed image reasonable
TARGET_ROOT_SIZE=$((CURRENT_SIZE * 2 / 3))

# Alignment for partition boundaries (8MB)
ALIGN="$((8 * 1024 * 1024))"
TARGET_ROOT_SIZE=$(((TARGET_ROOT_SIZE / ALIGN) * ALIGN))

# Get boot partition size (512MB)
BOOT_SIZE="$((512 * 1024 * 1024))"
BOOT_PART_START=$((ALIGN))
BOOT_PART_SIZE=$(((BOOT_SIZE + ALIGN - 1) / ALIGN * ALIGN))
ROOT_PART_START=$((BOOT_PART_START + BOOT_PART_SIZE))

# New image size = boot + smaller root partition
NEW_IMG_SIZE=$((ROOT_PART_START + TARGET_ROOT_SIZE))

echo "New image size: $((NEW_IMG_SIZE / 1024 / 1024)) MB"
echo "Space for expansion: $(((CURRENT_SIZE - NEW_IMG_SIZE) / 1024 / 1024)) MB"

# Create loop device for the image
ensure_next_loopdev
LOOP_DEV="$(losetup --show --find --partscan "${IMG_FILE}")"
ensure_loopdev_partitions "$LOOP_DEV"

ROOT_DEV="${LOOP_DEV}p2"

# Check and shrink the ext4 filesystem first
echo "Checking and shrinking root filesystem..."
e2fsck -f -y "$ROOT_DEV" || true

# Calculate target filesystem size in 4K blocks
FS_BLOCK_SIZE=4096
TARGET_FS_BLOCKS=$((TARGET_ROOT_SIZE / FS_BLOCK_SIZE))

# Shrink the filesystem
resize2fs "$ROOT_DEV" "${TARGET_FS_BLOCKS}"

# Detach loop device
losetup -d "$LOOP_DEV"

# Update the partition table
echo "Updating partition table..."
ROOT_PART_END=$((ROOT_PART_START + TARGET_ROOT_SIZE - 1))

parted --script "${IMG_FILE}" unit B resizepart 2 "${ROOT_PART_END}"

# Truncate the image file to new size
truncate -s "${NEW_IMG_SIZE}" "${IMG_FILE}"

echo "Root partition shrunk successfully"
echo "Firstboot will expand to full device size on first boot"

# Remount the image for subsequent stages
ensure_next_loopdev
LOOP_DEV="$(losetup --show --find --partscan "${IMG_FILE}")"
ensure_loopdev_partitions "$LOOP_DEV"

BOOT_DEV="${LOOP_DEV}p1"
ROOT_DEV="${LOOP_DEV}p2"

mount -v "$ROOT_DEV" "${ROOTFS_DIR}" -t ext4
mount -v "$BOOT_DEV" "${ROOTFS_DIR}/boot/firmware" -t vfat

echo "Image remounted and ready for subsequent export stages"
