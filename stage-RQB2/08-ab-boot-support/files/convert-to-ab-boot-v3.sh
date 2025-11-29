#!/bin/bash
# ============================================================================
# RasQberry A/B Boot Image Converter v3
# ============================================================================
# Purpose: Convert a standard RasQberry image to 7-partition A/B layout
#
# Key improvements over v2:
#   - Small initial image (~12GB) for fast download
#   - Partitions expand via raspi-config on 64GB+ SD cards
#
# Input: Standard RasQberry .img file (uncompressed, 2 partitions)
# Output: AB-ready .img file (7 partitions with extended partition)
#
# Partition Layout Created:
#   p1: CONFIG        512MB   FAT32   (autoboot.txt, config.txt)
#   p2: BOOT-A        512MB   FAT32   (boot files for Slot A)
#   p3: BOOT-B        512MB   FAT32   (boot files for Slot B)
#   p4: extended      (rest)
#     p5: SYSTEM-A    10GB    ext4    (rootfs Slot A)
#     p6: SYSTEM-B    16MB    ext4    (rootfs Slot B, placeholder)
#     p7: DATA        16MB    ext4    (user data, placeholder)
#
# Expansion (via raspi-config, requires 64GB+ SD card):
#   data:     10% of available space
#   system-a: 45% of available space
#   system-b: 45% of available space
#
# Usage: ./convert-to-ab-boot-v3.sh <input.img> <output.img>
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

echo "=== RasQberry A/B Boot Image Converter v3 ==="
echo ""
echo "Input:  $INPUT_IMG"
echo "Output: $OUTPUT_IMG"
echo ""

# ============================================================================
# Configuration
# ============================================================================

# Partition sizes in MB
CONFIG_SIZE_MB=512
BOOT_A_SIZE_MB=512
BOOT_B_SIZE_MB=512
SYSTEM_A_SIZE_MB=10240   # 10GB for initial RasQberry system
SYSTEM_B_SIZE_MB=16      # 16MB placeholder (expands via raspi-config)
DATA_SIZE_MB=16          # 16MB placeholder (expands via raspi-config)

# Calculate total image size
TOTAL_SIZE_MB=$((CONFIG_SIZE_MB + BOOT_A_SIZE_MB + BOOT_B_SIZE_MB + SYSTEM_A_SIZE_MB + SYSTEM_B_SIZE_MB + DATA_SIZE_MB + 16))

echo "Target image size: ${TOTAL_SIZE_MB}MB (~$((TOTAL_SIZE_MB / 1024))GB)"
echo ""

# ============================================================================
# Step 1: Create output image file
# ============================================================================
echo "Step 1: Creating output image file (${TOTAL_SIZE_MB}MB)..."
dd if=/dev/zero of="$OUTPUT_IMG" bs=1M count="$TOTAL_SIZE_MB" status=none
echo "Created ${TOTAL_SIZE_MB}MB image file"
echo ""

# ============================================================================
# Step 2: Create partition table
# ============================================================================
echo "Step 2: Creating partition layout..."

# Create MBR partition table
parted -s "$OUTPUT_IMG" mklabel msdos

# Create partitions
# p1: config (primary)
parted -s "$OUTPUT_IMG" mkpart primary fat32 1MiB $((CONFIG_SIZE_MB + 1))MiB

# p2: boot-a (primary)
BOOT_A_START=$((CONFIG_SIZE_MB + 1))
BOOT_A_END=$((BOOT_A_START + BOOT_A_SIZE_MB))
parted -s "$OUTPUT_IMG" mkpart primary fat32 ${BOOT_A_START}MiB ${BOOT_A_END}MiB

# p3: boot-b (primary)
BOOT_B_START=${BOOT_A_END}
BOOT_B_END=$((BOOT_B_START + BOOT_B_SIZE_MB))
parted -s "$OUTPUT_IMG" mkpart primary fat32 ${BOOT_B_START}MiB ${BOOT_B_END}MiB

# p4: extended (contains logical partitions)
EXTENDED_START=${BOOT_B_END}
parted -s "$OUTPUT_IMG" mkpart extended ${EXTENDED_START}MiB 100%

# p5: system-a (logical)
SYSTEM_A_START=$((EXTENDED_START + 1))
SYSTEM_A_END=$((SYSTEM_A_START + SYSTEM_A_SIZE_MB))
parted -s "$OUTPUT_IMG" mkpart logical ext4 ${SYSTEM_A_START}MiB ${SYSTEM_A_END}MiB

# p6: system-b (logical)
SYSTEM_B_START=$((SYSTEM_A_END + 1))
SYSTEM_B_END=$((SYSTEM_B_START + SYSTEM_B_SIZE_MB))
parted -s "$OUTPUT_IMG" mkpart logical ext4 ${SYSTEM_B_START}MiB ${SYSTEM_B_END}MiB

# p7: data (logical)
DATA_START=$((SYSTEM_B_END + 1))
parted -s "$OUTPUT_IMG" mkpart logical ext4 ${DATA_START}MiB 100%

# Set boot flag on p1
parted -s "$OUTPUT_IMG" set 1 boot on

echo "Partition layout created:"
parted "$OUTPUT_IMG" print
echo ""

# ============================================================================
# Step 3: Set up loop devices
# ============================================================================
echo "Step 3: Setting up loop devices..."
OUTPUT_LOOP=$(losetup -fP --show "$OUTPUT_IMG")
INPUT_LOOP=$(losetup -fP --show "$INPUT_IMG")

echo "Output loop: $OUTPUT_LOOP"
echo "Input loop:  $INPUT_LOOP"

# Wait for partition devices to appear
sleep 2
echo ""

# ============================================================================
# Step 4: Format partitions
# ============================================================================
echo "Step 4: Formatting partitions..."

mkfs.vfat -F 32 -n "CONFIG" "${OUTPUT_LOOP}p1"
mkfs.vfat -F 32 -n "BOOT-A" "${OUTPUT_LOOP}p2"
mkfs.vfat -F 32 -n "BOOT-B" "${OUTPUT_LOOP}p3"
mkfs.ext4 -F -L "SYSTEM-A" "${OUTPUT_LOOP}p5"
mkfs.ext4 -F -L "SYSTEM-B" "${OUTPUT_LOOP}p6"
mkfs.ext4 -F -L "DATA" "${OUTPUT_LOOP}p7"

echo "Filesystems created"
echo ""

# ============================================================================
# Step 5: Mount partitions
# ============================================================================
echo "Step 5: Mounting partitions..."
MOUNT_DIR=$(mktemp -d)
mkdir -p "${MOUNT_DIR}"/{config,boot-a,boot-b,system-a,system-b,data,input-boot,input-root}

mount "${OUTPUT_LOOP}p1" "${MOUNT_DIR}/config"
mount "${OUTPUT_LOOP}p2" "${MOUNT_DIR}/boot-a"
mount "${OUTPUT_LOOP}p3" "${MOUNT_DIR}/boot-b"
mount "${OUTPUT_LOOP}p5" "${MOUNT_DIR}/system-a"
mount "${OUTPUT_LOOP}p6" "${MOUNT_DIR}/system-b"
mount "${OUTPUT_LOOP}p7" "${MOUNT_DIR}/data"

mount "${INPUT_LOOP}p1" "${MOUNT_DIR}/input-boot"
mount "${INPUT_LOOP}p2" "${MOUNT_DIR}/input-root"
echo ""

# ============================================================================
# Step 6: Copy boot files
# ============================================================================
echo "Step 6: Copying boot files to boot-a..."
rsync -aAX "${MOUNT_DIR}/input-boot/" "${MOUNT_DIR}/boot-a/"

echo "Step 7: Copying boot files to boot-b..."
rsync -aAX "${MOUNT_DIR}/boot-a/" "${MOUNT_DIR}/boot-b/"
echo ""

# ============================================================================
# Step 8: Create config partition contents
# ============================================================================
echo "Step 8: Creating config partition contents..."

# Create autoboot.txt
cat > "${MOUNT_DIR}/config/autoboot.txt" << 'EOF'
[all]
tryboot_a_b=1
boot_partition=2

[tryboot]
boot_partition=3
EOF

# Create empty config.txt (required by Pi 5 firmware)
touch "${MOUNT_DIR}/config/config.txt"

# Copy bootcode.bin for older Pi models
if [ -f "${MOUNT_DIR}/boot-a/bootcode.bin" ]; then
    cp "${MOUNT_DIR}/boot-a/bootcode.bin" "${MOUNT_DIR}/config/"
fi

echo "Created autoboot.txt:"
cat "${MOUNT_DIR}/config/autoboot.txt"
echo ""

# ============================================================================
# Step 9: Update cmdline.txt
# ============================================================================
echo "Step 9: Updating cmdline.txt..."

# Read original cmdline.txt and preserve parameters
ORIG_CMDLINE=$(cat "${MOUNT_DIR}/boot-a/cmdline.txt")
echo "  Original cmdline: $ORIG_CMDLINE"

# Remove parameters we'll be updating or that are incompatible with AB boot
# Note: init= is removed because standard firstboot script is incompatible with AB layout
PRESERVED_PARAMS=$(echo "$ORIG_CMDLINE" | sed \
    -e 's/console=[^ ]*//g' \
    -e 's/root=[^ ]*//g' \
    -e 's/rootfstype=[^ ]*//g' \
    -e 's/fsck\.repair=[^ ]*//g' \
    -e 's/rootwait//g' \
    -e 's/quiet//g' \
    -e 's/splash//g' \
    -e 's/plymouth\.ignore-serial-consoles//g' \
    -e 's/init=[^ ]*//g' \
    -e 's/  */ /g' \
    -e 's/^ *//' \
    -e 's/ *$//')

echo "  Preserved params: $PRESERVED_PARAMS"

# Build console configuration based on CONSOLE_TYPE
if [ "$CONSOLE_TYPE" = "serial" ]; then
    # Serial mode: serial0 last = serial primary
    CONSOLE_CONFIG="console=tty1 console=serial0,115200"
    echo "  Console: serial (primary)"
else
    # HDMI mode: tty1 last = HDMI primary
    CONSOLE_CONFIG="console=serial0,115200 console=tty1"
    echo "  Console: hdmi (primary)"
fi

# Build boot options based on BOOT_VERBOSITY
if [ "$BOOT_VERBOSITY" = "verbose" ]; then
    BOOT_OPTIONS=""
    echo "  Verbosity: verbose"
else
    BOOT_OPTIONS=" quiet splash plymouth.ignore-serial-consoles"
    echo "  Verbosity: splash"
fi

# cmdline.txt for slot A (use device paths for reliability)
if [ -n "$PRESERVED_PARAMS" ]; then
    CMDLINE_A="${CONSOLE_CONFIG} root=/dev/mmcblk0p5 rootfstype=ext4 fsck.repair=yes rootwait${BOOT_OPTIONS} ${PRESERVED_PARAMS}"
else
    CMDLINE_A="${CONSOLE_CONFIG} root=/dev/mmcblk0p5 rootfstype=ext4 fsck.repair=yes rootwait${BOOT_OPTIONS}"
fi
echo "$CMDLINE_A" > "${MOUNT_DIR}/boot-a/cmdline.txt"

# cmdline.txt for slot B
if [ -n "$PRESERVED_PARAMS" ]; then
    CMDLINE_B="${CONSOLE_CONFIG} root=/dev/mmcblk0p6 rootfstype=ext4 fsck.repair=yes rootwait${BOOT_OPTIONS} ${PRESERVED_PARAMS}"
else
    CMDLINE_B="${CONSOLE_CONFIG} root=/dev/mmcblk0p6 rootfstype=ext4 fsck.repair=yes rootwait${BOOT_OPTIONS}"
fi
echo "$CMDLINE_B" > "${MOUNT_DIR}/boot-b/cmdline.txt"

echo "boot-a cmdline.txt:"
cat "${MOUNT_DIR}/boot-a/cmdline.txt"
echo "boot-b cmdline.txt:"
cat "${MOUNT_DIR}/boot-b/cmdline.txt"
echo ""

# ============================================================================
# Step 9a: Configure UART in config.txt
# ============================================================================
echo "Step 9a: Configuring UART..."

for BOOT_PART in "${MOUNT_DIR}/boot-a" "${MOUNT_DIR}/boot-b"; do
    if [ -f "${BOOT_PART}/config.txt" ]; then
        if [ "$CONSOLE_TYPE" = "serial" ]; then
            # Enable UART for serial console
            if ! grep -q "^enable_uart=1" "${BOOT_PART}/config.txt"; then
                echo "" >> "${BOOT_PART}/config.txt"
                echo "# Enable UART for serial console (GPIO 14/15)" >> "${BOOT_PART}/config.txt"
                echo "enable_uart=1" >> "${BOOT_PART}/config.txt"
                echo "  Added enable_uart=1 to $(basename ${BOOT_PART})/config.txt"
            fi
        else
            # HDMI mode: remove UART setting if present
            if grep -q "^enable_uart=" "${BOOT_PART}/config.txt"; then
                sed -i '/^enable_uart=/d' "${BOOT_PART}/config.txt"
                echo "  Removed enable_uart from $(basename ${BOOT_PART})/config.txt"
            fi
        fi
    fi
done
echo ""

# ============================================================================
# Step 10: Remove initramfs configuration
# ============================================================================
echo "Step 10: Removing initramfs configuration..."

for BOOT_PART in "${MOUNT_DIR}/boot-a" "${MOUNT_DIR}/boot-b"; do
    if [ -f "${BOOT_PART}/config.txt" ]; then
        sed -i '/^auto_initramfs=/d' "${BOOT_PART}/config.txt"
        sed -i '/^initramfs /d' "${BOOT_PART}/config.txt"
    fi
    rm -f "${BOOT_PART}"/initrd* "${BOOT_PART}"/initramfs* 2>/dev/null || true
done

echo "Initramfs disabled (using direct kernel boot)"
echo ""

# ============================================================================
# Step 11: Copy rootfs
# ============================================================================
echo "Step 11: Copying rootfs to system-a... (this will take several minutes)"
rsync -aAX "${MOUNT_DIR}/input-root/" "${MOUNT_DIR}/system-a/"
echo "Rootfs copy complete"
echo ""

# ============================================================================
# Step 12: Update fstab
# ============================================================================
echo "Step 12: Updating fstab..."

# Create mount points
mkdir -p "${MOUNT_DIR}/system-a/boot/config"
mkdir -p "${MOUNT_DIR}/system-a/data"

# fstab for slot A (use device paths for reliability)
cat > "${MOUNT_DIR}/system-a/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/mmcblk0p1              /boot/config    vfat    defaults          0   2
/dev/mmcblk0p2              /boot/firmware  vfat    defaults          0   2
/dev/mmcblk0p5              /               ext4    defaults,noatime  0   1
/dev/mmcblk0p7              /data           ext4    defaults,noatime  0   2
EOF

echo "system-a fstab:"
cat "${MOUNT_DIR}/system-a/etc/fstab"
echo ""

# ============================================================================
# Step 13: Prepare system-b (minimal structure)
# ============================================================================
echo "Step 13: Preparing system-b..."

mkdir -p "${MOUNT_DIR}/system-b"/{boot/config,boot/firmware,data,etc}

# fstab for slot B (use device paths for reliability)
cat > "${MOUNT_DIR}/system-b/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/mmcblk0p1              /boot/config    vfat    defaults          0   2
/dev/mmcblk0p3              /boot/firmware  vfat    defaults          0   2
/dev/mmcblk0p6              /               ext4    defaults,noatime  0   1
/dev/mmcblk0p7              /data           ext4    defaults,noatime  0   2
EOF

echo "system-b prepared"
echo ""

# ============================================================================
# Step 14: Initialize data partition
# ============================================================================
echo "Step 14: Initializing data partition..."
mkdir -p "${MOUNT_DIR}/data"/{home,var/log}
echo ""

# ============================================================================
# Step 15: Unmount and cleanup
# ============================================================================
echo "Step 15: Unmounting partitions..."

sync

umount "${MOUNT_DIR}/config"
umount "${MOUNT_DIR}/boot-a"
umount "${MOUNT_DIR}/boot-b"
umount "${MOUNT_DIR}/system-a"
umount "${MOUNT_DIR}/system-b"
umount "${MOUNT_DIR}/data"
umount "${MOUNT_DIR}/input-boot"
umount "${MOUNT_DIR}/input-root"

rmdir "${MOUNT_DIR}"/{config,boot-a,boot-b,system-a,system-b,data,input-boot,input-root}
rmdir "${MOUNT_DIR}"

losetup -d "$OUTPUT_LOOP"
losetup -d "$INPUT_LOOP"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "=== Conversion Complete ==="
echo ""
echo "AB-ready image created: $OUTPUT_IMG"
echo "Size: $(du -h "$OUTPUT_IMG" | cut -f1)"
echo ""
echo "Partition layout:"
echo "  p1: CONFIG      (${CONFIG_SIZE_MB}MB)   - autoboot.txt, config.txt"
echo "  p2: BOOT-A      (${BOOT_A_SIZE_MB}MB)   - boot files for Slot A"
echo "  p3: BOOT-B      (${BOOT_B_SIZE_MB}MB)   - boot files for Slot B"
echo "  p5: SYSTEM-A    (${SYSTEM_A_SIZE_MB}MB) - rootfs Slot A"
echo "  p6: SYSTEM-B    (${SYSTEM_B_SIZE_MB}MB) - rootfs Slot B (placeholder)"
echo "  p7: DATA        (${DATA_SIZE_MB}MB)     - user data (placeholder)"
echo ""
echo "Next steps:"
echo "  1. Compress: xz -9 -T0 $OUTPUT_IMG"
echo "  2. Flash to SD card (64GB+ recommended)"
echo "  3. Boot and use raspi-config to expand partitions"
echo "     (Expansion available on 64GB+ SD cards)"
echo ""