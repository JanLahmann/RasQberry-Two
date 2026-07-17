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
SLOT_MANAGER="/usr/bin/rq_slot_manager.sh"
LOG_FILE="/var/log/rasqberry-update-slot.log"
DEFAULT_TARGET_SLOT="B"  # Always update Slot B by default
STABLE_SLOT="A"          # Slot A is the stable/protected slot

# Release manifest that carries per-release checksums (extract_sha256 = SHA256 of
# the DECOMPRESSED .img). Used to verify integrity when no explicit --sha256 is
# passed. Overridable via RQB_RELEASES_URL for testing/mirrors.
RELEASES_MANIFEST_URL="${RQB_RELEASES_URL:-https://rasqberry.org/RQB-releases.json}"

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

is_terminal() {
    # Check if stdout is connected to a terminal
    # Returns 0 (true) if terminal, 1 (false) otherwise
    [ -t 1 ]
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

# Slot -> partition resolution comes from rq_common.sh:
# get_ab_system_partition / get_ab_boot_partition (label-based, issue #229)

preflight_checks() {
    # Safety checks before any destructive action
    local target_slot="$1" system_partition="$2" boot_partition="$3"

    # Never flash the slot we are running from
    local current_root
    current_root=$(findmnt / -o source -n)
    if [ "$current_root" = "$system_partition" ]; then
        die "Refusing to flash Slot $target_slot: it is the currently booted system ($current_root). Boot the other slot first."
    fi
    local current_boot
    current_boot=$(findmnt /boot/firmware -o source -n 2>/dev/null || echo "")
    if [ -n "$current_boot" ] && [ "$current_boot" = "$boot_partition" ]; then
        die "Refusing to flash Slot $target_slot: $boot_partition is the active boot partition."
    fi

    # Target partition must be expanded (factory Slot B is a 16MB placeholder)
    local part_size
    part_size=$(blockdev --getsize64 "$system_partition" 2>/dev/null || echo 0)
    if [ "$part_size" -lt 4294967296 ]; then  # < 4GB cannot hold any image
        die "Slot $target_slot partition is too small ($((part_size / 1024 / 1024))MB). Run partition expansion first: raspi-config -> RasQberry -> AB_BOOT -> EXPAND"
    fi

    # Enough free space to download + decompress in DOWNLOAD_DIR
    local avail_kb
    avail_kb=$(df --output=avail "$DOWNLOAD_DIR" | tail -1)
    if [ "${avail_kb:-0}" -lt 15728640 ]; then  # < 15GB (xz + ~10GB raw image)
        die "Not enough free space in $DOWNLOAD_DIR ($((avail_kb / 1024 / 1024))GB free, 15GB needed)"
    fi
}

verify_checksum() {
    # Verify the downloaded image against a SHA256 checksum.
    # Uses --sha256 argument if given, else tries <url>.sha256 alongside
    # the image. Skips with a warning if no checksum is available.
    local image_file="$1" url="$2" expected="${3:-}"

    if [ -z "$expected" ]; then
        local sum_url="${url}.sha256"
        expected=$(curl -sSLf --max-time 30 "$sum_url" 2>/dev/null | awk '{print $1}' || true)
        if [ -z "$expected" ]; then
            warn "No SHA256 checksum available for this release - skipping verification"
            log_message "WARNING: image installed without checksum verification"
            return 0
        fi
        log_message "Fetched checksum from $sum_url"
    fi

    log_message "Verifying SHA256 checksum..."
    local actual
    actual=$(sha256sum "$image_file" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        rm -f "$image_file"
        die "Checksum mismatch! expected=$expected actual=$actual - download corrupted or tampered, aborting"
    fi
    log_message "Checksum OK: $actual"
}

fetch_release_sha256() {
    # Look up a checksum field for a release tag from the release manifest
    # (RQB-releases.json). $2 = field: image_sha256 (the COMPRESSED .img.xz) or
    # extract_sha256 (the DECOMPRESSED .img). Prints the sha (empty if the manifest
    # is unreachable, the field is absent, or the tag is not a current stream head -
    # so older tags / older manifests fall through to no-verification, not an error).
    local tag="$1" field="$2"
    curl -sSLf --max-time 30 "$RELEASES_MANIFEST_URL" 2>/dev/null | python3 -c '
import json, sys
tag, field = sys.argv[1], sys.argv[2]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for stream in (data.get("streams") or {}).values():
    if isinstance(stream, dict) and stream.get("tag") == tag:
        print(stream.get(field, "") or "")
        break
' "$tag" "$field" 2>/dev/null || true
}

download_image() {
    # Download the image file
    local url="$1"
    local output_file="$2"

    log_message "Downloading image from: $url"
    log_message "Saving to: $output_file"

    # Use wget or curl - show progress bar when in terminal, quiet otherwise
    if command -v wget >/dev/null 2>&1; then
        if is_terminal; then
            # Show progress bar in terminal
            if ! wget --progress=bar:force -O "$output_file" "$url" 2>&1 | tee -a "$LOG_FILE"; then
                die "Download failed"
            fi
        else
            # Non-verbose for non-terminal (logs, systemd)
            if ! wget -nv -O "$output_file" "$url" 2>> "$LOG_FILE"; then
                die "Download failed"
            fi
        fi
    elif command -v curl >/dev/null 2>&1; then
        if is_terminal; then
            # Show progress bar in terminal
            if ! curl -L --progress-bar -o "$output_file" "$url" 2>&1 | tee -a "$LOG_FILE"; then
                die "Download failed"
            fi
        else
            # Silent for non-terminal
            if ! curl -sSL -o "$output_file" "$url" 2>> "$LOG_FILE"; then
                die "Download failed"
            fi
        fi
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

    log_message "Image file verified: $size bytes"
}

write_image_to_slot() {
    # Extract and write image to target slot (both boot and system partitions)
    local image_file="$1"
    local system_partition="$2"
    local boot_partition="$3"
    local target_slot="$4"
    local expected_extract_sha="${5:-}"

    log_message "Installing image to Slot $target_slot"
    log_message "  System partition: $system_partition"
    log_message "  Boot partition: $boot_partition"

    # Create work directory
    local work_dir="${DOWNLOAD_DIR}/extract-$$"
    mkdir -p "$work_dir"

    # Decompress image (use all CPU cores with -T0 for faster decompression)
    log_message "Decompressing image (multi-threaded)..."
    local raw_image="${work_dir}/image.img"
    if is_terminal; then
        # Show progress in terminal (-v for verbose)
        if ! xz -dcvT0 "$image_file" > "$raw_image" 2>&1 | tee -a "$LOG_FILE"; then
            rm -rf "$work_dir"
            die "Failed to decompress image"
        fi
    else
        # Quiet for non-terminal
        if ! xz -dcT0 "$image_file" > "$raw_image" 2>> "$LOG_FILE"; then
            rm -rf "$work_dir"
            die "Failed to decompress image"
        fi
    fi
    log_message "Decompression complete"

    # Verify the DECOMPRESSED image against extract_sha256 from RQB-releases.json
    # (the manifest only publishes the extracted-image hash, so integrity is
    # checked here, after decompression, rather than on the .img.xz).
    if [ -n "$expected_extract_sha" ]; then
        log_message "Verifying decompressed image against RQB-releases.json checksum..."
        local actual_extract_sha
        actual_extract_sha=$(sha256sum "$raw_image" | awk '{print $1}')
        if [ "$actual_extract_sha" != "$expected_extract_sha" ]; then
            rm -rf "$work_dir"
            die "Decompressed image checksum mismatch! expected=$expected_extract_sha actual=$actual_extract_sha - download corrupted or tampered, aborting"
        fi
        log_message "Decompressed image checksum OK: $actual_extract_sha"
    else
        warn "No extract_sha256 in RQB-releases.json for this tag - installing without decompressed-image verification"
    fi

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

    # Normalize label to uppercase for comparison (FAT labels are case-insensitive)
    local p1_label_upper
    p1_label_upper=$(echo "$p1_label" | tr '[:lower:]' '[:upper:]')

    case "$p1_label_upper" in
        CONFIG)
            # AB image: p1=config, p2=boot-a, p5=system-a
            log_message "AB image detected (p1 label: $p1_label)"
            log_message "Using Slot A partitions as source (boot-a, system-a)"
            img_boot="${loop_dev}p2"
            img_root="${loop_dev}p5"
            ;;
        BOOTFS)
            # Standard image: p1=bootfs, p2=rootfs
            log_message "Standard image detected (p1 label: $p1_label)"
            img_boot="${loop_dev}p1"
            img_root="${loop_dev}p2"
            ;;
        *)
            losetup -d "$loop_dev"
            rm -rf "$work_dir"
            die "Unknown image type: p1 label '$p1_label' (expected 'CONFIG' or 'BOOTFS')"
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

    # Unmount target boot partition if mounted (e.g., by desktop automounter)
    if mountpoint -q "$boot_partition" 2>/dev/null || mount | grep -q "$boot_partition"; then
        log_message "Unmounting $boot_partition (was auto-mounted)..."
        umount "$boot_partition" 2>> "$LOG_FILE" || true
    fi

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

    # Copy all boot files (quietly, log only on error)
    if ! cp -a "$img_boot_mount"/* "$tgt_boot_mount"/ 2>> "$LOG_FILE"; then
        umount "$tgt_boot_mount"
        umount "$img_boot_mount"
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Failed to copy boot files"
    fi

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

    # Unmount target system partition if mounted
    if mountpoint -q "$system_partition" 2>/dev/null || mount | grep -q "$system_partition"; then
        log_message "Unmounting $system_partition (was mounted)..."
        umount "$system_partition" 2>> "$LOG_FILE" || true
    fi

    # The image's root partition must fit into the target partition
    local img_root_size target_size
    img_root_size=$(blockdev --getsize64 "$img_root")
    target_size=$(blockdev --getsize64 "$system_partition")
    if [ "$img_root_size" -gt "$target_size" ]; then
        losetup -d "$loop_dev"
        rm -rf "$work_dir"
        die "Image rootfs ($((img_root_size / 1024 / 1024))MB) does not fit target partition $system_partition ($((target_size / 1024 / 1024))MB)"
    fi

    # Write rootfs to system partition
    log_message "Writing rootfs to $system_partition..."
    log_message "This may take 10-20 minutes..."

    # Show progress when in terminal, quiet otherwise
    if is_terminal; then
        if ! dd if="$img_root" of="$system_partition" bs=4M status=progress 2>&1 | tee -a "$LOG_FILE"; then
            losetup -d "$loop_dev"
            rm -rf "$work_dir"
            die "Failed to write rootfs to partition"
        fi
    else
        if ! dd if="$img_root" of="$system_partition" bs=4M 2>> "$LOG_FILE"; then
            losetup -d "$loop_dev"
            rm -rf "$work_dir"
            die "Failed to write rootfs to partition"
        fi
    fi
    log_message "Rootfs written successfully"

    # Release loop device (no longer needed)
    losetup -d "$loop_dev"

    # Resize filesystem to fill partition
    log_message "Resizing filesystem..."
    e2fsck -f -y "$system_partition" >> "$LOG_FILE" 2>&1 || true
    resize2fs "$system_partition" >> "$LOG_FILE" 2>&1 || warn "Could not resize filesystem"

    # Set correct label for the target slot
    local system_label="SYSTEM-${target_slot}"
    log_message "Setting filesystem label to ${system_label}..."
    e2label "$system_partition" "$system_label" >> "$LOG_FILE" 2>&1 || warn "Could not set filesystem label"

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
    # Configure tryboot to the specified slot (no reboot)
    local target_slot="$1"

    log_message "Configuring tryboot to boot Slot $target_slot..."

    if [ ! -x "$SLOT_MANAGER" ]; then
        die "Slot manager not found: $SLOT_MANAGER"
    fi

    # Wait for I/O to settle
    sync
    sleep 5

    # Configure and reboot via slot manager (handles unmounting)
    exec "$SLOT_MANAGER" switch-to "$target_slot" --reboot
}

# ============================================================================
# Main
# ============================================================================

parse_arguments() {
    # Parse command line arguments
    TARGET_SLOT="$DEFAULT_TARGET_SLOT"
    REQUIRE_CONFIRM=false
    SHA256_SUM=""

    # Shift past URL and tag to get to optional parameters
    shift 2

    while [ $# -gt 0 ]; do
        case "$1" in
            --slot)
                TARGET_SLOT="$2"
                shift 2
                ;;
            --sha256)
                SHA256_SUM="$2"
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
  --sha256 <sum>  Expected SHA256 of the .img.xz (else <url>.sha256 is tried)
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

    # Determine target slot partitions (shared helpers from rq_common.sh)
    local system_partition
    local boot_partition
    system_partition=$(get_ab_system_partition "$TARGET_SLOT")
    boot_partition=$(get_ab_boot_partition "$TARGET_SLOT")
    log_message "Target system partition: $system_partition"
    log_message "Target boot partition: $boot_partition"

    # Check if partitions exist
    if [ ! -b "$system_partition" ]; then
        die "Target system partition does not exist: $system_partition"
    fi
    if [ ! -b "$boot_partition" ]; then
        die "Target boot partition does not exist: $boot_partition"
    fi

    # Safety guards: never the booted slot, size and free-space prechecks
    preflight_checks "$TARGET_SLOT" "$system_partition" "$boot_partition"

    # Download image
    local image_file="${DOWNLOAD_DIR}/rasqberry-${release_tag}.img.xz"

    if [ -f "$image_file" ]; then
        log_message "Image file already exists, removing old download"
        rm -f "$image_file"
    fi

    download_image "$download_url" "$image_file"

    # Verify download
    verify_image "$image_file"
    # Verify the COMPRESSED .img.xz EARLY - before the ~9GB decompress - so a
    # corrupt/truncated download is caught immediately (not wasted on decompress).
    # An explicit --sha256 wins; otherwise use image_sha256 from the manifest.
    if [ -n "$SHA256_SUM" ]; then
        verify_checksum "$image_file" "$download_url" "$SHA256_SUM"
    else
        local image_sha
        image_sha=$(fetch_release_sha256 "$release_tag" image_sha256)
        if [ -n "$image_sha" ]; then
            log_message "Verifying compressed image against image_sha256 from RQB-releases.json"
            verify_checksum "$image_file" "$download_url" "$image_sha"
        fi
    fi

    # Fetch the decompressed-image checksum from the release manifest so
    # write_image_to_slot can verify integrity after decompression.
    #
    # An A/B slot is written from the -ab image - a different file from the
    # standard one, with a different decompressed hash (ab_extract_sha256, not
    # extract_sha256). Fetching the wrong field made the post-decompress check
    # abort every A/B OTA against the standard image's hash. Detect the -ab
    # image by its URL (both slots on an A/B card use it).
    local extract_sha sha_field="extract_sha256"
    case "$download_url" in
        *-ab.img.xz|*-ab.img) sha_field="ab_extract_sha256" ;;
    esac
    extract_sha=$(fetch_release_sha256 "$release_tag" "$sha_field")
    if [ -n "$extract_sha" ]; then
        log_message "Fetched ${sha_field} from RQB-releases.json for $release_tag"
    elif [ "$sha_field" = "ab_extract_sha256" ]; then
        # Older manifests predate the ab_* fields. Fall back to writing WITHOUT
        # the post-decompress check (with a warning), rather than silently
        # borrowing the standard hash - which was the bug.
        warn "No ab_extract_sha256 in RQB-releases.json for $release_tag (older manifest?) - writing without decompressed-image verification"
    fi

    # Write image to target slot (both boot and system partitions)
    write_image_to_slot "$image_file" "$system_partition" "$boot_partition" "$TARGET_SLOT" "$extract_sha"

    # Cleanup
    cleanup_download "$image_file"

    # Configure tryboot (no automatic reboot)
    log_message "=== Update Complete ==="
    configure_tryboot "$TARGET_SLOT"
}

main "$@"
