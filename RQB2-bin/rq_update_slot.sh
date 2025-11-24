#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Updater
# ============================================================================
# Description: Download and install new RasQberry image to boot slot
# Usage: rq_update_slot.sh <download_url> <release_tag> [--slot A|B] [--confirm]
#
# Strategy:
#   Slot A: STABLE - Protected, only updated manually with --slot A --confirm
#   Slot B: TESTING - Default target, receives auto-updates
#
# This script:
#   1. Downloads the new image (.img.xz)
#   2. Writes to target slot (default: Slot B)
#   3. Configures tryboot to boot the new slot
#   4. Reboots the system
#
# The health check service will validate the new boot and either confirm
# or rollback to the stable slot.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Configuration
DOWNLOAD_DIR="/var/tmp/rasqberry-updates"
SLOT_MANAGER="/usr/local/bin/rq_slot_manager.sh"
LOG_FILE="/var/log/rasqberry-update-slot.log"
DEFAULT_TARGET_SLOT="B"  # Always update Slot B by default
STABLE_SLOT="A"          # Slot A is the stable/protected slot

# ============================================================================
# Helper Functions
# ============================================================================

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "This script must be run as root"
    fi
}

log_message() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$LOG_FILE"
}

get_target_slot() {
    # Determine which slot to write to
    # Default: Slot B (testing slot)
    # Can be overridden with --slot parameter
    local requested_slot="${1:-$DEFAULT_TARGET_SLOT}"

    case "$requested_slot" in
        A|B)
            echo "$requested_slot"
            ;;
        *)
            die "Invalid slot: $requested_slot (must be A or B)"
            ;;
    esac
}

get_slot_partition() {
    # Get the system partition device for a slot
    # v3 AB layout: p5=system-a, p6=system-b
    local slot="$1"
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    case "$slot" in
        A)
            echo "/dev/${root_dev}p5"
            ;;
        B)
            echo "/dev/${root_dev}p6"
            ;;
        *)
            die "Invalid slot: $slot"
            ;;
    esac
}

get_boot_partition() {
    # Get the boot partition device for a slot
    # v3 AB layout: p2=boot-a, p3=boot-b
    local slot="$1"
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    case "$slot" in
        A)
            echo "/dev/${root_dev}p2"
            ;;
        B)
            echo "/dev/${root_dev}p3"
            ;;
        *)
            die "Invalid slot: $slot"
            ;;
    esac
}

download_image() {
    # Download the image file
    local url="$1"
    local output_file="$2"

    log_message "Downloading image from: $url"
    log_message "Saving to: $output_file"

    # Use wget or curl
    if command -v wget >/dev/null 2>&1; then
        wget -O "$output_file" "$url" 2>&1 | tee -a "$LOG_FILE" || die "Download failed"
    elif command -v curl >/dev/null 2>&1; then
        curl -L -o "$output_file" "$url" 2>&1 | tee -a "$LOG_FILE" || die "Download failed"
    else
        die "Neither wget nor curl found"
    fi

    log_message "Download complete"
}

verify_image() {
    # Basic verification that the downloaded file is valid
    local image_file="$1"

    if [ ! -f "$image_file" ]; then
        die "Downloaded file not found: $image_file"
    fi

    local size
    size=$(stat -c%s "$image_file" 2>/dev/null || stat -f%z "$image_file" 2>/dev/null)

    if [ "$size" -lt 100000000 ]; then  # Less than 100MB is suspicious
        die "Downloaded file seems too small: $size bytes"
    fi

    # Check if it's a valid xz file
    if ! xz -t "$image_file" 2>/dev/null; then
        die "Downloaded file is not a valid xz compressed file"
    fi

    log_message "Image file verified: $size bytes"
}

write_image_to_slot() {
    # Extract and write image to target slot (both boot and system partitions)
    local image_file="$1"
    local system_partition="$2"
    local boot_partition="$3"
    local target_slot="$4"

    log_message "Installing image to Slot $target_slot"
    log_message "  System partition: $system_partition"
    log_message "  Boot partition: $boot_partition"

    # Create work directory
    local work_dir="${DOWNLOAD_DIR}/extract-$$"
    mkdir -p "$work_dir"

    # Decompress image
    log_message "Decompressing image..."
    local raw_image="${work_dir}/image.img"
    if ! xz -dc "$image_file" > "$raw_image" 2>&1; then
        rm -rf "$work_dir"
        die "Failed to decompress image"
    fi
    log_message "Decompression complete"

    # Set up loop device for the image
    log_message "Setting up loop device..."
    local loop_dev
    loop_dev=$(losetup -f --show -P "$raw_image") || {
        rm -rf "$work_dir"
        die "Failed to set up loop device"
    }
    log_message "Loop device: $loop_dev"

    # Wait for partitions to appear
    sleep 2
    partprobe "$loop_dev" 2>/dev/null || true
    sleep 1

    # Detect image type by checking partition labels
    local p1_label
    p1_label=$(lsblk -no LABEL "${loop_dev}p1" 2>/dev/null || echo "")

    # Identify source partitions based on image type
    local img_boot
    local img_root

    case "$p1_label" in
        config)
            # AB image: p1=config, p2=boot-a, p5=system-a
            log_message "AB image detected (p1 label: config)"
            log_message "Using Slot A partitions as source (boot-a, system-a)"
            img_boot="${loop_dev}p2"
            img_root="${loop_dev}p5"
            ;;
        bootfs)
            # Standard image: p1=bootfs, p2=rootfs
            log_message "Standard image detected (p1 label: bootfs)"
            img_boot="${loop_dev}p1"
            img_root="${loop_dev}p2"
            ;;
        *)
            losetup -d "$loop_dev"
            rm -rf "$work_dir"
            die "Unknown image type: p1 label '$p1_label' (expected 'config' or 'bootfs')"
            ;;
    esac

    if [ ! -b "$img_boot" ] || [ ! -b "$img_root" ]; then
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Could not find image partitions (boot: $img_boot, root: $img_root)"
    fi

    # Mount image boot partition and copy to target boot partition
    log_message "Copying boot files to $boot_partition..."
    local img_boot_mount="${work_dir}/img_boot"
    local tgt_boot_mount="${work_dir}/tgt_boot"
    mkdir -p "$img_boot_mount" "$tgt_boot_mount"

    mount -o ro "$img_boot" "$img_boot_mount" || {
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to mount image boot partition"
    }

    # Format and mount target boot partition
    mkfs.vfat -F 32 -n "boot-${target_slot,,}" "$boot_partition" >> "$LOG_FILE" 2>&1 || {
        umount "$img_boot_mount"
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to format boot partition"
    }

    mount "$boot_partition" "$tgt_boot_mount" || {
        umount "$img_boot_mount"
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to mount target boot partition"
    }

    # Copy all boot files
    cp -a "$img_boot_mount"/* "$tgt_boot_mount"/ 2>&1 | tee -a "$LOG_FILE" || {
        umount "$tgt_boot_mount"
        umount "$img_boot_mount"
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to copy boot files"
    }

    # Update cmdline.txt for the target slot
    log_message "Updating cmdline.txt for Slot $target_slot..."
    if [ -f "$tgt_boot_mount/cmdline.txt" ]; then
        # Clean up cmdline.txt:
        # - Replace root partition reference
        # - Remove firstboot init (not needed for slot updates)
        # - Remove quiet/splash for better debugging
        # - Remove leading whitespace
        sed -i "s|root=[^ ]*|root=${system_partition}|g" "$tgt_boot_mount/cmdline.txt"
        sed -i 's| init=[^ ]*||g' "$tgt_boot_mount/cmdline.txt"
        sed -i 's| splash||g' "$tgt_boot_mount/cmdline.txt"
        sed -i 's| plymouth.ignore-serial-consoles||g' "$tgt_boot_mount/cmdline.txt"
        sed -i 's| quiet||g' "$tgt_boot_mount/cmdline.txt"
        sed -i 's|^ *||g' "$tgt_boot_mount/cmdline.txt"
        log_message "cmdline.txt updated: root=${system_partition}"
        log_message "Removed: init, splash, plymouth, quiet"
    fi

    # Unmount boot partitions
    sync
    umount "$tgt_boot_mount"
    umount "$img_boot_mount"
    log_message "Boot files copied successfully"

    # Write rootfs to system partition
    log_message "Writing rootfs to $system_partition..."
    log_message "This may take 10-20 minutes..."

    if dd if="$img_root" of="$system_partition" bs=4M status=progress 2>&1 | tee -a "$LOG_FILE"; then
        log_message "Rootfs written successfully"
    else
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to write rootfs to partition"
    fi

    # Release loop device (no longer needed)
    losetup -d "$loop_dev"

    # Resize filesystem to fill partition
    log_message "Resizing filesystem..."
    e2fsck -f -y "$system_partition" >> "$LOG_FILE" 2>&1 || true
    resize2fs "$system_partition" >> "$LOG_FILE" 2>&1 || warn "Could not resize filesystem"

    # Mount and update fstab
    log_message "Updating fstab for Slot $target_slot..."
    local tgt_root_mount="${work_dir}/tgt_root"
    mkdir -p "$tgt_root_mount"

    mount "$system_partition" "$tgt_root_mount" || {
        rm -rf "$work_dir"
        die "Failed to mount target root partition"
    }

    # Update fstab for v3 AB layout
    if [ -f "$tgt_root_mount/etc/fstab" ]; then
        local root_part
        root_part=$(findmnt / -o source -n)
        local root_dev
        root_dev=$(lsblk -no pkname "$root_part")

        cat > "$tgt_root_mount/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/${root_dev}p1          /boot/config    vfat    defaults          0   2
${boot_partition}           /boot/firmware  vfat    defaults          0   2
${system_partition}         /               ext4    defaults,noatime  0   1
/dev/${root_dev}p7          /data           ext4    defaults,noatime  0   2
EOF
        log_message "fstab updated for Slot $target_slot"
    fi

    # Unmount and cleanup
    sync
    umount "$tgt_root_mount"
    rm -rf "$work_dir"

    log_message "Image installation complete"
}

cleanup_download() {
    # Remove downloaded image file
    local image_file="$1"

    if [ -f "$image_file" ]; then
        log_message "Cleaning up downloaded file: $image_file"
        rm -f "$image_file" || warn "Could not remove downloaded file"
    fi
}

configure_tryboot() {
    # Configure tryboot to boot into the specified slot
    local target_slot="$1"

    log_message "Configuring tryboot to boot Slot $target_slot..."

    if [ ! -x "$SLOT_MANAGER" ]; then
        die "Slot manager not found: $SLOT_MANAGER"
    fi

    "$SLOT_MANAGER" switch-to "$target_slot" 2>&1 | tee -a "$LOG_FILE" || die "Failed to configure tryboot"

    log_message "Tryboot configured for Slot $target_slot"
}

reboot_system() {
    # Reboot the system to activate the new slot
    log_message "Rebooting system to activate new slot..."
    log_message "System will boot into Slot ${TARGET_SLOT}"

    sync

    # Give a few seconds for logs to flush
    sleep 2

    reboot
}

# ============================================================================
# Main
# ============================================================================

parse_arguments() {
    # Parse command line arguments
    TARGET_SLOT="$DEFAULT_TARGET_SLOT"
    REQUIRE_CONFIRM=false

    # Shift past URL and tag to get to optional parameters
    shift 2

    while [ $# -gt 0 ]; do
        case "$1" in
            --slot)
                TARGET_SLOT="$2"
                shift 2
                ;;
            --confirm)
                REQUIRE_CONFIRM=true
                shift
                ;;
            *)
                warn "Unknown parameter: $1"
                shift
                ;;
        esac
    done
}

confirm_stable_update() {
    # Require explicit confirmation for Slot A (stable) updates
    if [ "$TARGET_SLOT" = "$STABLE_SLOT" ]; then
        if [ "$REQUIRE_CONFIRM" != "true" ]; then
            die "Updating Slot $STABLE_SLOT (stable) requires --confirm flag for safety"
        fi

        warn "═══════════════════════════════════════════════════════"
        warn "  WARNING: Updating STABLE Slot $STABLE_SLOT"
        warn "═══════════════════════════════════════════════════════"
        warn ""
        warn "This will overwrite your stable/baseline image!"
        warn "Make sure you have a backup or tested image."
        warn ""

        read -p "Type 'UPDATE STABLE' to confirm: " response
        if [ "$response" != "UPDATE STABLE" ]; then
            die "Stable slot update cancelled"
        fi
    fi
}

main() {
    check_root

    if [ $# -lt 2 ]; then
        cat >&2 << EOF
Usage: $0 <download_url> <release_tag> [--slot A|B] [--confirm]

Arguments:
  download_url    URL to download the image from
  release_tag     Release tag/version identifier

Options:
  --slot A|B      Target slot (default: B for testing)
  --confirm       Required when updating Slot A (stable)

Slot Strategy:
  Slot A (STABLE):  Protected baseline, requires --confirm
  Slot B (TESTING): Default target for auto-updates

Examples:
  # Auto-update to Slot B (default)
  $0 https://github.com/.../image.img.xz dev-remote01-2025-10-25-123456

  # Manual test in Slot B
  $0 https://github.com/.../image.img.xz dev-remote01-2025-10-25-123456 --slot B

  # Update stable Slot A (requires confirmation)
  $0 https://github.com/.../image.img.xz beta-2025-10-25-123456 --slot A --confirm

EOF
        exit 1
    fi

    local download_url="$1"
    local release_tag="$2"

    # Parse optional arguments
    parse_arguments "$@"

    log_message "=== RasQberry A/B Boot Slot Update ==="
    log_message "Download URL: $download_url"
    log_message "Release Tag: $release_tag"
    log_message "Target Slot: $TARGET_SLOT"

    # Confirm if updating stable slot
    confirm_stable_update

    # Create download directory
    mkdir -p "$DOWNLOAD_DIR"

    # Determine target slot partitions
    local system_partition
    local boot_partition
    system_partition=$(get_slot_partition "$TARGET_SLOT")
    boot_partition=$(get_boot_partition "$TARGET_SLOT")
    log_message "Target system partition: $system_partition"
    log_message "Target boot partition: $boot_partition"

    # Check if partitions exist
    if [ ! -b "$system_partition" ]; then
        die "Target system partition does not exist: $system_partition"
    fi
    if [ ! -b "$boot_partition" ]; then
        die "Target boot partition does not exist: $boot_partition"
    fi

    # Download image
    local image_file="${DOWNLOAD_DIR}/rasqberry-${release_tag}.img.xz"

    if [ -f "$image_file" ]; then
        log_message "Image file already exists, removing old download"
        rm -f "$image_file"
    fi

    download_image "$download_url" "$image_file"

    # Verify download
    verify_image "$image_file"

    # Write image to target slot (both boot and system partitions)
    write_image_to_slot "$image_file" "$system_partition" "$boot_partition" "$TARGET_SLOT"

    # Cleanup
    cleanup_download "$image_file"

    # Configure tryboot to boot the new slot
    configure_tryboot "$TARGET_SLOT"

    # Reboot
    log_message "=== Update Complete ==="
    log_message "Rebooting in 5 seconds..."
    sleep 5

    reboot_system
}

main "$@"
