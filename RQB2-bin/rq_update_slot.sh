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
    # Get the partition device for a slot
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
    # Write the image to the inactive slot partition
    local image_file="$1"
    local target_partition="$2"

    log_message "Writing image to partition: $target_partition"
    log_message "This may take 10-20 minutes..."

    # Decompress and write in one command (saves disk space)
    # dd with status=progress for feedback
    if xz -dc "$image_file" | dd of="$target_partition" bs=4M status=progress 2>&1 | tee -a "$LOG_FILE"; then
        log_message "Image written successfully"
        sync  # Ensure all data is written
        log_message "Sync complete"
    else
        die "Failed to write image to partition"
    fi
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
    log_message "System will boot into new slot and run health checks"
    log_message "If health checks fail, system will automatically rollback"

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

    # Determine target slot partition
    local target_partition
    target_partition=$(get_slot_partition "$TARGET_SLOT")
    log_message "Target partition: $target_partition"

    # Check if partition exists
    if [ ! -b "$target_partition" ]; then
        die "Target partition does not exist: $target_partition"
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

    # Write image to target slot
    write_image_to_slot "$image_file" "$target_partition"

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
