#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Install Image to A/B Boot Slot
# ============================================================================
# Description: Install a standard RasQberry image to an A/B boot slot
# Usage: rq_install_image_to_slot.sh <image.img.xz> <slot>
#
# This script properly installs a standard 2-partition RasQberry image
# into an A/B boot slot by extracting boot and rootfs and rsyncing them
# to the correct partitions.
#
# NOTE: This does NOT use 'dd' which would create nested partition tables.
# Instead, it extracts the image contents and copies them to the target slot.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# ============================================================================
# Configuration
# ============================================================================

TEMP_DIR="/tmp/rq-image-install-$$"
TEMP_IMG="${TEMP_DIR}/image.img"
LOOP_DEVICE=""
MOUNT_DIR="${TEMP_DIR}/mounts"

# ============================================================================
# Cleanup Handler
# ============================================================================

cleanup() {
    local exit_code=$?

    echo ""
    info "Cleaning up..."

    # Unmount everything
    umount "${MOUNT_DIR}/target-boot" 2>/dev/null || true
    umount "${MOUNT_DIR}/target-root" 2>/dev/null || true
    umount "${MOUNT_DIR}/source-boot" 2>/dev/null || true
    umount "${MOUNT_DIR}/source-root" 2>/dev/null || true

    # Detach loop device
    if [ -n "$LOOP_DEVICE" ]; then
        losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi

    # Remove temp directory
    rm -rf "$TEMP_DIR"

    if [ $exit_code -eq 0 ]; then
        echo ""
        info "Cleanup complete"
    else
        echo ""
        warn "Cleanup complete (script exited with error code $exit_code)"
    fi
}

trap cleanup EXIT

# ============================================================================
# Validation Functions
# ============================================================================

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "This script must be run as root (use sudo)"
    fi
}

check_ab_system() {
    # Check if this is an AB boot system
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    local bootfs_common_label
    bootfs_common_label=$(lsblk -no label "/dev/${root_dev}p1" 2>/dev/null || lsblk -no label "/dev/${root_dev}1" 2>/dev/null || echo "")

    if [ "$bootfs_common_label" != "bootfs-cmn" ]; then
        die "This system does not have A/B boot configured (bootfs-common not found)"
    fi
}

check_disk_space() {
    # Check if there's enough temp space for decompressed image
    local available_kb
    available_kb=$(df /tmp | tail -1 | awk '{print $4}')
    local available_gb=$((available_kb / 1024 / 1024))

    if [ $available_gb -lt 10 ]; then
        die "Not enough space in /tmp (need 10GB, have ${available_gb}GB)"
    fi

    info "Temporary space available: ${available_gb}GB"
}

# ============================================================================
# Partition Helper Functions
# ============================================================================

get_slot_partitions() {
    # Get boot and root partition devices for a slot
    local slot="$1"
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    case "${slot}" in
        A)
            BOOT_PART="/dev/${root_dev}p2"
            ROOT_PART="/dev/${root_dev}p5"
            [ -b "$BOOT_PART" ] || BOOT_PART="/dev/${root_dev}2"
            [ -b "$ROOT_PART" ] || ROOT_PART="/dev/${root_dev}5"
            ;;
        B)
            BOOT_PART="/dev/${root_dev}p3"
            ROOT_PART="/dev/${root_dev}p6"
            [ -b "$BOOT_PART" ] || BOOT_PART="/dev/${root_dev}3"
            [ -b "$ROOT_PART" ] || ROOT_PART="/dev/${root_dev}6"
            ;;
        *)
            die "Invalid slot: $slot (must be A or B)"
            ;;
    esac

    # Verify partitions exist
    if [ ! -b "$BOOT_PART" ]; then
        die "Boot partition not found: $BOOT_PART"
    fi

    if [ ! -b "$ROOT_PART" ]; then
        die "Root partition not found: $ROOT_PART"
    fi

    info "Target partitions for Slot $slot:"
    info "  Boot: $BOOT_PART"
    info "  Root: $ROOT_PART"
}

# ============================================================================
# Installation Functions
# ============================================================================

decompress_image() {
    local image_file="$1"

    info "Decompressing image..."
    info "Source: $image_file"
    info "Destination: $TEMP_IMG"

    if [[ "$image_file" == *.xz ]]; then
        xz -dc "$image_file" > "$TEMP_IMG" || die "Failed to decompress image"
    elif [[ "$image_file" == *.gz ]]; then
        gzip -dc "$image_file" > "$TEMP_IMG" || die "Failed to decompress image"
    elif [[ "$image_file" == *.img ]]; then
        cp "$image_file" "$TEMP_IMG" || die "Failed to copy image"
    else
        die "Unknown image format (expected .img, .img.xz, or .img.gz)"
    fi

    local img_size
    img_size=$(du -h "$TEMP_IMG" | cut -f1)
    info "Decompressed image size: $img_size"
}

mount_source_image() {
    info "Mounting source image..."

    # Set up loop device
    LOOP_DEVICE=$(losetup -fP --show "$TEMP_IMG")
    info "Loop device: $LOOP_DEVICE"

    # Wait for partition devices to appear
    sleep 2
    partprobe "$LOOP_DEVICE" 2>/dev/null || true
    sleep 1

    # Mount source partitions
    mkdir -p "${MOUNT_DIR}/source-boot" "${MOUNT_DIR}/source-root"

    # Determine partition naming (p1/p2 vs 1/2)
    local boot_part="${LOOP_DEVICE}p1"
    local root_part="${LOOP_DEVICE}p2"

    if [ ! -b "$boot_part" ]; then
        boot_part="${LOOP_DEVICE}1"
        root_part="${LOOP_DEVICE}2"
    fi

    mount "$boot_part" "${MOUNT_DIR}/source-boot" || die "Failed to mount source boot partition"
    mount "$root_part" "${MOUNT_DIR}/source-root" || die "Failed to mount source root partition"

    info "Source image mounted:"
    info "  Boot: $boot_part"
    info "  Root: $root_part"
}

mount_target_partitions() {
    info "Mounting target slot partitions..."

    mkdir -p "${MOUNT_DIR}/target-boot" "${MOUNT_DIR}/target-root"

    mount "$BOOT_PART" "${MOUNT_DIR}/target-boot" || die "Failed to mount target boot partition"
    mount "$ROOT_PART" "${MOUNT_DIR}/target-root" || die "Failed to mount target root partition"

    info "Target partitions mounted"
}

clear_target_partitions() {
    info "Clearing target partitions..."

    # Clear boot partition
    rm -rf "${MOUNT_DIR}/target-boot"/* 2>/dev/null || true

    # Clear root partition
    rm -rf "${MOUNT_DIR}/target-root"/* 2>/dev/null || true

    info "Target partitions cleared"
}

copy_boot_files() {
    info "Copying boot files..."

    rsync -aAX --info=progress2 \
        "${MOUNT_DIR}/source-boot/" \
        "${MOUNT_DIR}/target-boot/" \
        || die "Failed to copy boot files"

    info "Boot files copied successfully"
}

copy_rootfs() {
    info "Copying root filesystem..."
    info "This will take several minutes..."

    rsync -aAX --info=progress2 \
        "${MOUNT_DIR}/source-root/" \
        "${MOUNT_DIR}/target-root/" \
        || die "Failed to copy root filesystem"

    info "Root filesystem copied successfully"
}

update_boot_config() {
    local slot="$1"

    info "Updating boot configuration for Slot $slot..."

    # Update cmdline.txt to point to correct root partition
    if [ -f "${MOUNT_DIR}/target-boot/cmdline.txt" ]; then
        sed -i "s|root=/dev/mmcblk0p2|root=$ROOT_PART|g" "${MOUNT_DIR}/target-boot/cmdline.txt"
        info "Updated cmdline.txt: root=$ROOT_PART"
    else
        warn "cmdline.txt not found in boot partition"
    fi
}

update_fstab() {
    local slot="$1"

    info "Updating /etc/fstab for Slot $slot..."

    # Update fstab to mount correct partitions
    if [ -f "${MOUNT_DIR}/target-root/etc/fstab" ]; then
        cat > "${MOUNT_DIR}/target-root/etc/fstab" << EOF
proc            /proc           proc    defaults          0       0
$BOOT_PART      /boot/firmware  vfat    defaults          0       2
$ROOT_PART      /               ext4    defaults,noatime  0       1
EOF
        info "Updated /etc/fstab"
        cat "${MOUNT_DIR}/target-root/etc/fstab"
    else
        warn "/etc/fstab not found in root filesystem"
    fi
}

# ============================================================================
# Main Installation Process
# ============================================================================

install_image_to_slot() {
    local image_file="$1"
    local target_slot="$2"

    echo ""
    info "═══════════════════════════════════════════════════════"
    info "  Installing Image to Slot $target_slot"
    info "═══════════════════════════════════════════════════════"
    echo ""

    # Verify image exists
    if [ ! -f "$image_file" ]; then
        die "Image file not found: $image_file"
    fi

    info "Image: $image_file"
    info "Target Slot: $target_slot"
    echo ""

    # Get target partition devices
    get_slot_partitions "$target_slot"
    echo ""

    # Create temp directory
    mkdir -p "$TEMP_DIR"

    # Step 1: Decompress image
    echo ""
    info "Step 1/7: Decompressing image"
    decompress_image "$image_file"

    # Step 2: Mount source image
    echo ""
    info "Step 2/7: Mounting source image"
    mount_source_image

    # Step 3: Mount target partitions
    echo ""
    info "Step 3/7: Mounting target partitions"
    mount_target_partitions

    # Step 4: Clear target partitions
    echo ""
    info "Step 4/7: Clearing target partitions"
    clear_target_partitions

    # Step 5: Copy boot files
    echo ""
    info "Step 5/7: Copying boot files"
    copy_boot_files

    # Step 6: Copy root filesystem
    echo ""
    info "Step 6/7: Copying root filesystem"
    copy_rootfs

    # Step 7: Update configuration
    echo ""
    info "Step 7/7: Updating configuration"
    update_boot_config "$target_slot"
    update_fstab "$target_slot"

    echo ""
    info "═══════════════════════════════════════════════════════"
    info "  Installation Complete!"
    info "═══════════════════════════════════════════════════════"
    echo ""
    info "Slot $target_slot is now ready with the new image"
    echo ""
}

# ============================================================================
# Usage and Main
# ============================================================================

usage() {
    cat << EOF
Usage: $(basename "$0") <image.img.xz> <slot>

Install a standard RasQberry image to an A/B boot slot.

Arguments:
    image.img.xz    Path to compressed or uncompressed image file
                    Supports: .img, .img.xz, .img.gz

    slot            Target slot (A or B)

Example:
    sudo $(basename "$0") rasqberry-2025-01-15.img.xz B

This will:
  1. Decompress the image to /tmp
  2. Extract boot and rootfs from the image
  3. Copy them to Slot B partitions (p3 and p6)
  4. Update cmdline.txt and fstab for the new slot

Requires:
  - A/B boot system (bootfs-common must exist)
  - At least 10GB free space in /tmp
  - Root privileges (use sudo)

EOF
    exit 1
}

main() {
    if [ $# -ne 2 ]; then
        usage
    fi

    local image_file="$1"
    local target_slot="$2"

    # Validate slot
    case "$target_slot" in
        A|B)
            ;;
        *)
            die "Invalid slot: $target_slot (must be A or B)"
            ;;
    esac

    # Pre-flight checks
    check_root
    check_ab_system
    check_disk_space

    # Perform installation
    install_image_to_slot "$image_file" "$target_slot"

    echo ""
    info "Next steps:"
    info "  1. Switch to Slot $target_slot: sudo rq_slot_manager.sh switch-to $target_slot"
    info "  2. Reboot to test: sudo reboot"
    info "  3. Health check will validate the new image"
    info "  4. Confirm if successful: sudo rq_slot_manager.sh confirm"
    echo ""
}

main "$@"