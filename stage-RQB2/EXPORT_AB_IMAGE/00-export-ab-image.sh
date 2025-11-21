#!/bin/bash -e
# ============================================================================
# RasQberry A/B Boot Image Export
# ============================================================================
# Creates a 7-partition A/B boot image directly from pi-gen rootfs
#
# Partition Layout:
#   p1: config      256MB   FAT32   (autoboot.txt, config.txt)
#   p2: boot-a      256MB   FAT32   (kernel, dtb, cmdline for slot A)
#   p3: boot-b      256MB   FAT32   (kernel, dtb, cmdline for slot B)
#   p4: extended    (rest)
#     p5: system-a  16GB    ext4    (rootfs slot A)
#     p6: system-b  16GB    ext4    (rootfs slot B)
#     p7: data      64MB    ext4    (user data, expands on first boot)
#
# Uses deterministic UUIDs so PARTUUID is stable across builds
# ============================================================================

# Partition sizes in MB
CONFIG_SIZE_MB=256
BOOT_A_SIZE_MB=256
BOOT_B_SIZE_MB=256
SYSTEM_A_SIZE_MB=16384   # 16GB for full RasQberry system
SYSTEM_B_SIZE_MB=16384   # 16GB for slot B
DATA_SIZE_MB=64

# Deterministic disk ID for PARTUUID base
# PARTUUIDs will be: deadbeef-01, deadbeef-02, etc.
DISK_ID="deadbeef"

# Deterministic filesystem UUIDs
UUID_SYSTEM_A="deadbeef-0000-0000-0000-000000000005"
UUID_SYSTEM_B="deadbeef-0000-0000-0000-000000000006"
UUID_DATA="deadbeef-0000-0000-0000-000000000007"

# Calculate total image size
TOTAL_SIZE_MB=$((CONFIG_SIZE_MB + BOOT_A_SIZE_MB + BOOT_B_SIZE_MB + SYSTEM_A_SIZE_MB + SYSTEM_B_SIZE_MB + DATA_SIZE_MB + 16))

IMG_FILE="${STAGE_WORK_DIR}/${IMG_FILENAME}${IMG_SUFFIX}.img"

echo "=== RasQberry A/B Boot Image Export ==="
echo "Image file: ${IMG_FILE}"
echo "Total size: ${TOTAL_SIZE_MB}MB"
echo ""

# ============================================================================
# Step 1: Create and partition the image file
# ============================================================================
echo "Step 1: Creating ${TOTAL_SIZE_MB}MB image file..."

rm -f "${IMG_FILE}"
truncate -s "${TOTAL_SIZE_MB}M" "${IMG_FILE}"

# Create MBR partition table with fixed disk ID
echo "Creating partition table with disk ID 0x${DISK_ID}..."
parted -s "${IMG_FILE}" mklabel msdos

# Set the disk ID for deterministic PARTUUIDs
# sfdisk can set the disk-id on an existing partition table
echo "label-id: 0x${DISK_ID}" | sfdisk --no-reread "${IMG_FILE}" 2>/dev/null || true

# Create partitions
# p1: config (primary)
parted -s "${IMG_FILE}" mkpart primary fat32 1MiB $((CONFIG_SIZE_MB + 1))MiB

# p2: boot-a (primary)
BOOT_A_START=$((CONFIG_SIZE_MB + 1))
BOOT_A_END=$((BOOT_A_START + BOOT_A_SIZE_MB))
parted -s "${IMG_FILE}" mkpart primary fat32 ${BOOT_A_START}MiB ${BOOT_A_END}MiB

# p3: boot-b (primary)
BOOT_B_START=${BOOT_A_END}
BOOT_B_END=$((BOOT_B_START + BOOT_B_SIZE_MB))
parted -s "${IMG_FILE}" mkpart primary fat32 ${BOOT_B_START}MiB ${BOOT_B_END}MiB

# p4: extended (contains logical partitions)
EXTENDED_START=${BOOT_B_END}
parted -s "${IMG_FILE}" mkpart extended ${EXTENDED_START}MiB 100%

# p5: system-a (logical)
SYSTEM_A_START=$((EXTENDED_START + 1))
SYSTEM_A_END=$((SYSTEM_A_START + SYSTEM_A_SIZE_MB))
parted -s "${IMG_FILE}" mkpart logical ext4 ${SYSTEM_A_START}MiB ${SYSTEM_A_END}MiB

# p6: system-b (logical)
SYSTEM_B_START=$((SYSTEM_A_END + 1))
SYSTEM_B_END=$((SYSTEM_B_START + SYSTEM_B_SIZE_MB))
parted -s "${IMG_FILE}" mkpart logical ext4 ${SYSTEM_B_START}MiB ${SYSTEM_B_END}MiB

# p7: data (logical)
DATA_START=$((SYSTEM_B_END + 1))
parted -s "${IMG_FILE}" mkpart logical ext4 ${DATA_START}MiB 100%

# Set boot flag on p1 (config partition)
parted -s "${IMG_FILE}" set 1 boot on

echo "Partition layout:"
parted -s "${IMG_FILE}" print
echo ""

# ============================================================================
# Step 2: Set up loop device and format partitions
# ============================================================================
echo "Step 2: Setting up loop device and formatting partitions..."

LOOP_DEV=$(losetup -fP --show "${IMG_FILE}")
echo "Loop device: ${LOOP_DEV}"

# Wait for partition devices to appear
sleep 2

# Format partitions with deterministic IDs
echo "Formatting p1 (config) as FAT32..."
mkfs.vfat -F 32 -n "config" "${LOOP_DEV}p1"

echo "Formatting p2 (boot-a) as FAT32..."
mkfs.vfat -F 32 -n "boot-a" "${LOOP_DEV}p2"

echo "Formatting p3 (boot-b) as FAT32..."
mkfs.vfat -F 32 -n "boot-b" "${LOOP_DEV}p3"

echo "Formatting p5 (system-a) as ext4 with UUID ${UUID_SYSTEM_A}..."
mkfs.ext4 -F -L "system-a" -U "${UUID_SYSTEM_A}" "${LOOP_DEV}p5"

echo "Formatting p6 (system-b) as ext4 with UUID ${UUID_SYSTEM_B}..."
mkfs.ext4 -F -L "system-b" -U "${UUID_SYSTEM_B}" "${LOOP_DEV}p6"

echo "Formatting p7 (data) as ext4 with UUID ${UUID_DATA}..."
mkfs.ext4 -F -L "data" -U "${UUID_DATA}" "${LOOP_DEV}p7"

echo ""

# ============================================================================
# Step 3: Mount partitions and copy files
# ============================================================================
echo "Step 3: Mounting partitions..."

MOUNT_DIR=$(mktemp -d)
mkdir -p "${MOUNT_DIR}"/{config,boot-a,boot-b,system-a,system-b,data}

mount "${LOOP_DEV}p1" "${MOUNT_DIR}/config"
mount "${LOOP_DEV}p2" "${MOUNT_DIR}/boot-a"
mount "${LOOP_DEV}p3" "${MOUNT_DIR}/boot-b"
mount "${LOOP_DEV}p5" "${MOUNT_DIR}/system-a"
mount "${LOOP_DEV}p6" "${MOUNT_DIR}/system-b"
mount "${LOOP_DEV}p7" "${MOUNT_DIR}/data"

echo "Mounted all partitions"
echo ""

# ============================================================================
# Step 4: Copy boot files from pi-gen
# ============================================================================
echo "Step 4: Copying boot files..."

# Source directories from pi-gen
BOOT_SRC="${ROOTFS_DIR}/boot/firmware"
ROOT_SRC="${ROOTFS_DIR}"

# Copy boot files to boot-a
echo "Copying boot files to boot-a..."
rsync -aAX "${BOOT_SRC}/" "${MOUNT_DIR}/boot-a/"

# Copy boot files to boot-b (identical copy)
echo "Copying boot files to boot-b..."
rsync -aAX "${MOUNT_DIR}/boot-a/" "${MOUNT_DIR}/boot-b/"

echo ""

# ============================================================================
# Step 5: Create config partition contents
# ============================================================================
echo "Step 5: Creating config partition contents..."

# Create autoboot.txt for tryboot mechanism
cat > "${MOUNT_DIR}/config/autoboot.txt" << 'EOF'
[all]
tryboot_a_b=1
boot_partition=2

[tryboot]
boot_partition=3
EOF

# Create empty config.txt (required by Pi 5 firmware)
touch "${MOUNT_DIR}/config/config.txt"

# Copy bootcode.bin for older Pi models (if exists)
if [ -f "${MOUNT_DIR}/boot-a/bootcode.bin" ]; then
    cp "${MOUNT_DIR}/boot-a/bootcode.bin" "${MOUNT_DIR}/config/"
    echo "Copied bootcode.bin to config partition"
fi

echo "Created autoboot.txt:"
cat "${MOUNT_DIR}/config/autoboot.txt"
echo ""

# ============================================================================
# Step 6: Update cmdline.txt for each slot
# ============================================================================
echo "Step 6: Updating cmdline.txt..."

# cmdline.txt for slot A (boots from system-a / p5)
cat > "${MOUNT_DIR}/boot-a/cmdline.txt" << EOF
console=serial0,115200 console=tty1 root=PARTUUID=${DISK_ID}-05 rootfstype=ext4 fsck.repair=yes rootwait
EOF

# cmdline.txt for slot B (boots from system-b / p6)
cat > "${MOUNT_DIR}/boot-b/cmdline.txt" << EOF
console=serial0,115200 console=tty1 root=PARTUUID=${DISK_ID}-06 rootfstype=ext4 fsck.repair=yes rootwait
EOF

echo "boot-a cmdline.txt:"
cat "${MOUNT_DIR}/boot-a/cmdline.txt"
echo ""
echo "boot-b cmdline.txt:"
cat "${MOUNT_DIR}/boot-b/cmdline.txt"
echo ""

# ============================================================================
# Step 7: Handle initramfs
# ============================================================================
echo "Step 7: Handling initramfs..."

# Remove initramfs settings from config.txt (we boot directly with PARTUUID)
for BOOT_PART in "${MOUNT_DIR}/boot-a" "${MOUNT_DIR}/boot-b"; do
    if [ -f "${BOOT_PART}/config.txt" ]; then
        sed -i '/^auto_initramfs=/d' "${BOOT_PART}/config.txt"
        sed -i '/^initramfs /d' "${BOOT_PART}/config.txt"
    fi
    # Remove initramfs files
    rm -f "${BOOT_PART}"/initrd* "${BOOT_PART}"/initramfs* 2>/dev/null || true
done

echo "Removed initramfs configuration (using direct kernel boot with PARTUUID)"
echo ""

# ============================================================================
# Step 8: Copy rootfs to system-a
# ============================================================================
echo "Step 8: Copying rootfs to system-a... (this will take a few minutes)"

# Copy rootfs excluding boot (already copied)
rsync -aAX --exclude '/boot/firmware/*' "${ROOT_SRC}/" "${MOUNT_DIR}/system-a/"

echo "Rootfs copied to system-a"
echo ""

# ============================================================================
# Step 9: Update fstab for slot A
# ============================================================================
echo "Step 9: Updating fstab..."

# Create mount point for config partition
mkdir -p "${MOUNT_DIR}/system-a/boot/config"

# Update fstab for slot A
cat > "${MOUNT_DIR}/system-a/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
PARTUUID=${DISK_ID}-01      /boot/config    vfat    defaults          0   2
PARTUUID=${DISK_ID}-02      /boot/firmware  vfat    defaults          0   2
PARTUUID=${DISK_ID}-05      /               ext4    defaults,noatime  0   1
PARTUUID=${DISK_ID}-07      /data           ext4    defaults,noatime  0   2
EOF

# Create mount point for data
mkdir -p "${MOUNT_DIR}/system-a/data"

echo "system-a fstab:"
cat "${MOUNT_DIR}/system-a/etc/fstab"
echo ""

# ============================================================================
# Step 10: Prepare system-b (empty, will be populated during OTA)
# ============================================================================
echo "Step 10: Preparing system-b..."

# Create minimal directory structure for system-b
mkdir -p "${MOUNT_DIR}/system-b"/{boot/config,boot/firmware,data,etc}

# Create fstab for slot B
cat > "${MOUNT_DIR}/system-b/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
PARTUUID=${DISK_ID}-01      /boot/config    vfat    defaults          0   2
PARTUUID=${DISK_ID}-03      /boot/firmware  vfat    defaults          0   2
PARTUUID=${DISK_ID}-06      /               ext4    defaults,noatime  0   1
PARTUUID=${DISK_ID}-07      /data           ext4    defaults,noatime  0   2
EOF

echo "system-b prepared (minimal structure)"
echo ""

# ============================================================================
# Step 11: Initialize data partition
# ============================================================================
echo "Step 11: Initializing data partition..."

# Create standard directories on data partition
mkdir -p "${MOUNT_DIR}/data"/{home,var/log}

echo "Data partition initialized"
echo ""

# ============================================================================
# Step 12: Cleanup and unmount
# ============================================================================
echo "Step 12: Unmounting partitions..."

sync

umount "${MOUNT_DIR}/config"
umount "${MOUNT_DIR}/boot-a"
umount "${MOUNT_DIR}/boot-b"
umount "${MOUNT_DIR}/system-a"
umount "${MOUNT_DIR}/system-b"
umount "${MOUNT_DIR}/data"

rmdir "${MOUNT_DIR}"/{config,boot-a,boot-b,system-a,system-b,data}
rmdir "${MOUNT_DIR}"

losetup -d "${LOOP_DEV}"

echo ""
echo "=== A/B Boot Image Export Complete ==="
echo ""
echo "Image: ${IMG_FILE}"
echo "Size: $(du -h "${IMG_FILE}" | cut -f1)"
echo ""
echo "Partition layout:"
echo "  p1: config      (${CONFIG_SIZE_MB}MB)   - autoboot.txt, config.txt"
echo "  p2: boot-a      (${BOOT_A_SIZE_MB}MB)   - kernel, dtb, cmdline for slot A"
echo "  p3: boot-b      (${BOOT_B_SIZE_MB}MB)   - kernel, dtb, cmdline for slot B"
echo "  p5: system-a    (${SYSTEM_A_SIZE_MB}MB) - rootfs slot A"
echo "  p6: system-b    (${SYSTEM_B_SIZE_MB}MB) - rootfs slot B (empty)"
echo "  p7: data        (${DATA_SIZE_MB}MB)     - user data (expands on firstboot)"
echo ""
echo "Disk ID: 0x${DISK_ID}"
echo "PARTUUIDs:"
echo "  config:   ${DISK_ID}-01"
echo "  boot-a:   ${DISK_ID}-02"
echo "  boot-b:   ${DISK_ID}-03"
echo "  system-a: ${DISK_ID}-05"
echo "  system-b: ${DISK_ID}-06"
echo "  data:     ${DISK_ID}-07"
echo ""
