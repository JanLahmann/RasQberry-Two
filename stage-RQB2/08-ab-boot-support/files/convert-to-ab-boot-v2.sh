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

# Console configuration from environment (default: production settings)
CONSOLE_TYPE="${CONSOLE_TYPE:-hdmi}"
BOOT_VERBOSITY="${BOOT_VERBOSITY:-splash}"

echo "Console configuration: CONSOLE_TYPE=${CONSOLE_TYPE}, BOOT_VERBOSITY=${BOOT_VERBOSITY}"

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

# Configure UART based on CONSOLE_TYPE
echo "Step 7a: Configuring UART on both boot partitions..."
for BOOTFS in "${MOUNT_DIR}/bootfs-a" "${MOUNT_DIR}/bootfs-b"; do
    if [ -f "${BOOTFS}/config.txt" ]; then
        if [ "$CONSOLE_TYPE" = "serial" ]; then
            # Enable UART for serial console
            if ! grep -q "^enable_uart=1" "${BOOTFS}/config.txt"; then
                echo "" >> "${BOOTFS}/config.txt"
                echo "# Enable UART for serial console (GPIO 14/15)" >> "${BOOTFS}/config.txt"
                echo "enable_uart=1" >> "${BOOTFS}/config.txt"
                echo "  Added enable_uart=1 to $(basename ${BOOTFS})/config.txt"
            else
                echo "  enable_uart already set in $(basename ${BOOTFS})/config.txt"
            fi
        else
            # HDMI mode: remove UART setting if present
            if grep -q "^enable_uart=" "${BOOTFS}/config.txt"; then
                sed -i '/^enable_uart=/d' "${BOOTFS}/config.txt"
                echo "  Removed enable_uart from $(basename ${BOOTFS})/config.txt (HDMI mode)"
            else
                echo "  UART not configured in $(basename ${BOOTFS})/config.txt (HDMI mode)"
            fi
        fi
    fi
done
echo ""

# Remove initramfs lines from config.txt (Method 7: belt-and-suspenders)
# This ensures bootloader doesn't try to load initramfs even if files exist
# AB boot uses direct kernel mount with rootwait, no initramfs needed
echo "Step 7b: Removing initramfs configuration from boot partitions..."
for BOOTFS in "${MOUNT_DIR}/bootfs-a" "${MOUNT_DIR}/bootfs-b"; do
    if [ -f "${BOOTFS}/config.txt" ]; then
        # Remove any initramfs loading lines
        if grep -q "^initramfs " "${BOOTFS}/config.txt"; then
            sed -i '/^initramfs /d' "${BOOTFS}/config.txt"
            echo "  Removed 'initramfs' line from $(basename ${BOOTFS})/config.txt"
        fi
        # Remove auto_initramfs setting
        if grep -q "^auto_initramfs=" "${BOOTFS}/config.txt"; then
            sed -i '/^auto_initramfs=/d' "${BOOTFS}/config.txt"
            echo "  Removed 'auto_initramfs' line from $(basename ${BOOTFS})/config.txt"
        fi
    fi
done
# Also remove any initramfs files that might have been copied
for BOOTFS in "${MOUNT_DIR}/bootfs-a" "${MOUNT_DIR}/bootfs-b"; do
    rm -f "${BOOTFS}"/initrd* "${BOOTFS}"/initramfs* 2>/dev/null || true
done
echo "  Initramfs configuration removed - using direct kernel boot with rootwait"
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
# Add mmc_block.use_blk_mq=y if not already present (required for AB boot with initramfs)
if ! grep -q "mmc_block.use_blk_mq" "${MOUNT_DIR}/bootfs-a/cmdline.txt"; then
    sed -i 's/$/ mmc_block.use_blk_mq=y/' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
fi

# Configure console based on CONSOLE_TYPE
if [ "$CONSOLE_TYPE" = "serial" ]; then
    # Serial mode: ensure serial console is present and primary (last in list)
    if ! grep -q "console=serial0" "${MOUNT_DIR}/bootfs-a/cmdline.txt"; then
        sed -i 's/console=tty1/console=tty1 console=serial0,115200/' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    fi
    # Ensure serial is last (primary)
    sed -i 's/console=serial0,115200 console=tty1/console=tty1 console=serial0,115200/g' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    echo "  Serial console configured as primary"
else
    # HDMI mode: remove serial console if present
    sed -i 's/ *console=serial0,[0-9]*//g' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    echo "  HDMI console configured as primary"
fi

# Configure boot verbosity based on BOOT_VERBOSITY
if [ "$BOOT_VERBOSITY" = "verbose" ]; then
    # Verbose mode: remove quiet, splash, plymouth settings
    sed -i 's/ quiet / /g; s/ splash / /g; s/ plymouth.ignore-serial-consoles / /g' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    sed -i 's/ quiet$//; s/ splash$//; s/ plymouth.ignore-serial-consoles$//' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    echo "  Verbose boot enabled"
else
    # Splash mode: ensure quiet/splash/plymouth are present
    if ! grep -q " quiet" "${MOUNT_DIR}/bootfs-a/cmdline.txt"; then
        sed -i 's/$/ quiet/' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    fi
    if ! grep -q " splash" "${MOUNT_DIR}/bootfs-a/cmdline.txt"; then
        sed -i 's/$/ splash/' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    fi
    if ! grep -q "plymouth.ignore-serial-consoles" "${MOUNT_DIR}/bootfs-a/cmdline.txt"; then
        sed -i 's/$/ plymouth.ignore-serial-consoles/' "${MOUNT_DIR}/bootfs-a/cmdline.txt"
    fi
    echo "  Splash boot enabled"
fi

echo "Updated: ${MOUNT_DIR}/bootfs-a/cmdline.txt"
grep "root=" "${MOUNT_DIR}/bootfs-a/cmdline.txt"
echo ""

# Update cmdline.txt on p3 to use device path for rootfs-b (p6)
echo "Step 10: Updating cmdline.txt on p3 for rootfs-b (/dev/mmcblk0p6)..."
sed -i "s|root=[^ ]*|root=/dev/mmcblk0p6|g" "${MOUNT_DIR}/bootfs-b/cmdline.txt"
# Add mmc_block.use_blk_mq=y if not already present (required for AB boot with initramfs)
if ! grep -q "mmc_block.use_blk_mq" "${MOUNT_DIR}/bootfs-b/cmdline.txt"; then
    sed -i 's/$/ mmc_block.use_blk_mq=y/' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
fi

# Configure console based on CONSOLE_TYPE
if [ "$CONSOLE_TYPE" = "serial" ]; then
    # Serial mode: ensure serial console is present and primary (last in list)
    if ! grep -q "console=serial0" "${MOUNT_DIR}/bootfs-b/cmdline.txt"; then
        sed -i 's/console=tty1/console=tty1 console=serial0,115200/' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    fi
    # Ensure serial is last (primary)
    sed -i 's/console=serial0,115200 console=tty1/console=tty1 console=serial0,115200/g' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    echo "  Serial console configured as primary"
else
    # HDMI mode: remove serial console if present
    sed -i 's/ *console=serial0,[0-9]*//g' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    echo "  HDMI console configured as primary"
fi

# Configure boot verbosity based on BOOT_VERBOSITY
if [ "$BOOT_VERBOSITY" = "verbose" ]; then
    # Verbose mode: remove quiet, splash, plymouth settings
    sed -i 's/ quiet / /g; s/ splash / /g; s/ plymouth.ignore-serial-consoles / /g' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    sed -i 's/ quiet$//; s/ splash$//; s/ plymouth.ignore-serial-consoles$//' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    echo "  Verbose boot enabled"
else
    # Splash mode: ensure quiet/splash/plymouth are present
    if ! grep -q " quiet" "${MOUNT_DIR}/bootfs-b/cmdline.txt"; then
        sed -i 's/$/ quiet/' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    fi
    if ! grep -q " splash" "${MOUNT_DIR}/bootfs-b/cmdline.txt"; then
        sed -i 's/$/ splash/' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    fi
    if ! grep -q "plymouth.ignore-serial-consoles" "${MOUNT_DIR}/bootfs-b/cmdline.txt"; then
        sed -i 's/$/ plymouth.ignore-serial-consoles/' "${MOUNT_DIR}/bootfs-b/cmdline.txt"
    fi
    echo "  Splash boot enabled"
fi

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

# Verify initramfs has been removed (we're using direct kernel boot)
echo "Step 14: Verifying initramfs configuration..."

# Check that initramfs files were removed in Step 7b
BOOTFS_A_INITRD=$(ls "${MOUNT_DIR}/bootfs-a"/initrd.img-* "${MOUNT_DIR}/bootfs-a"/initramfs* 2>/dev/null | head -1 || true)
BOOTFS_B_INITRD=$(ls "${MOUNT_DIR}/bootfs-b"/initrd.img-* "${MOUNT_DIR}/bootfs-b"/initramfs* 2>/dev/null | head -1 || true)

if [ -n "$BOOTFS_A_INITRD" ] || [ -n "$BOOTFS_B_INITRD" ]; then
    echo "WARNING: Initramfs files still present after removal attempt"
    echo "  bootfs-a: ${BOOTFS_A_INITRD:-none}"
    echo "  bootfs-b: ${BOOTFS_B_INITRD:-none}"
    echo "Removing remaining initramfs files..."
    rm -f "${MOUNT_DIR}/bootfs-a"/initrd* "${MOUNT_DIR}/bootfs-a"/initramfs* 2>/dev/null || true
    rm -f "${MOUNT_DIR}/bootfs-b"/initrd* "${MOUNT_DIR}/bootfs-b"/initramfs* 2>/dev/null || true
fi

# Verify config.txt doesn't have initramfs lines
for BOOTFS in "${MOUNT_DIR}/bootfs-a" "${MOUNT_DIR}/bootfs-b"; do
    if grep -q "^initramfs " "${BOOTFS}/config.txt" 2>/dev/null; then
        echo "ERROR: ${BOOTFS}/config.txt still contains initramfs line!"
        grep "^initramfs " "${BOOTFS}/config.txt"
        exit 1
    fi
done

echo "✓ Initramfs configuration verified:"
echo "  - No initramfs files in boot partitions"
echo "  - No initramfs lines in config.txt"
echo "  - Using direct kernel boot with rootwait"
echo ""

# Unmount all
echo "Step 15: Unmounting partitions..."
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
echo "Step 16: Detaching loop devices..."
losetup -d "$OUTPUT_LOOP"
losetup -d "$INPUT_LOOP"
echo ""

# Verify output
echo "Step 17: Verifying output image..."
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
echo "AB Boot features enabled:"
echo "  ✓ Direct kernel boot with rootwait (no initramfs)"
echo "  ✓ Device path boot (root=/dev/mmcblk0p5)"
echo "  ✓ Automatic partition expansion on first boot"
echo "  ✓ A/B slot switching via tryboot mechanism"
echo ""
echo "Next steps:"
echo "  1. Compress with highest compression: xz -9 -T0 $OUTPUT_IMG"
echo "     (Target: <2GB compressed size)"
echo "  2. Flash to SD card"
echo "  3. On first boot, p5 and p6 will expand to fill SD card"
echo ""