#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Manager
# ============================================================================
# Description: Manage A/B boot slots for remote testing
# Usage: rq_slot_manager.sh {status|confirm|switch|rollback}
#
# Commands:
#   status    - Show current slot and boot status
#   confirm   - Confirm current slot (prevent tryboot rollback)
#   switch    - Switch to the other slot on next boot
#   rollback  - Force rollback to previous slot
#
# This utility manages the Raspberry Pi tryboot feature for A/B boot testing.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Boot configuration files
BOOT_DIR="/boot/firmware"
AUTOBOOT_TXT="${BOOT_DIR}/autoboot.txt"
TRYBOOT_TXT="${BOOT_DIR}/tryboot.txt"
CURRENT_SLOT_FILE="${BOOT_DIR}/current-slot"
SLOT_CONFIRMED_FILE="${BOOT_DIR}/slot-confirmed"

# ============================================================================
# Helper Functions
# ============================================================================

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "This command must be run as root (use sudo)"
    fi
}

# ============================================================================
# Core Functions
# ============================================================================

get_current_slot() {
    # Get the currently booted slot (A or B)

    # Check if running in tryboot mode
    if [ -f "${TRYBOOT_TXT}" ]; then
        # In tryboot mode, check which partition we're on
        local root_part
        root_part=$(findmnt / -o source -n)

        case "${root_part}" in
            *p2|*2)
                echo "A"
                ;;
            *p3|*3)
                echo "B"
                ;;
            *)
                warn "Cannot determine slot from partition: ${root_part}"
                # Fall back to current-slot file
                if [ -f "${CURRENT_SLOT_FILE}" ]; then
                    cat "${CURRENT_SLOT_FILE}"
                else
                    echo "UNKNOWN"
                fi
                ;;
        esac
    else
        # Not in A/B boot mode
        echo "SINGLE"
    fi
}

get_other_slot() {
    # Get the other slot (if current is A, return B; if B, return A)
    local current_slot="$1"

    case "${current_slot}" in
        A)
            echo "B"
            ;;
        B)
            echo "A"
            ;;
        *)
            echo "UNKNOWN"
            ;;
    esac
}

is_slot_confirmed() {
    # Check if current slot has been confirmed
    [ -f "${SLOT_CONFIRMED_FILE}" ]
}

get_root_partition() {
    # Get the current root partition device
    findmnt / -o source -n
}

get_slot_partition() {
    # Get partition device for a given slot
    local slot="$1"
    local root_dev
    root_dev=$(lsblk -no pkname "$(get_root_partition)")

    case "${slot}" in
        A)
            echo "/dev/${root_dev}p2"  # Assuming p2 is slot A
            ;;
        B)
            echo "/dev/${root_dev}p3"  # Assuming p3 is slot B
            ;;
        *)
            echo "UNKNOWN"
            ;;
    esac
}

# ============================================================================
# Command Implementations
# ============================================================================

cmd_status() {
    # Display current A/B boot status
    info "=== RasQberry A/B Boot Status ==="
    echo ""

    # Check if A/B boot is configured
    if [ ! -f "${TRYBOOT_TXT}" ]; then
        warn "A/B boot not configured (tryboot.txt not found)"
        info "This system is running in single-partition mode"
        return 0
    fi

    # Current slot
    local current_slot
    current_slot=$(get_current_slot)
    info "Current Slot: ${current_slot}"

    # Root partition
    local root_part
    root_part=$(get_root_partition)
    info "Root Partition: ${root_part}"

    # Confirmation status
    if is_slot_confirmed; then
        info "Slot Status: CONFIRMED (no rollback will occur)"
    else
        warn "Slot Status: UNCONFIRMED (will rollback if not confirmed)"
    fi

    # Slot partitions
    echo ""
    info "Slot Partitions:"
    info "  Slot A: $(get_slot_partition A)"
    info "  Slot B: $(get_slot_partition B)"

    # Boot files
    echo ""
    info "Boot Configuration Files:"
    [ -f "${AUTOBOOT_TXT}" ] && info "  autoboot.txt: EXISTS" || warn "  autoboot.txt: MISSING"
    [ -f "${TRYBOOT_TXT}" ] && info "  tryboot.txt: EXISTS" || warn "  tryboot.txt: MISSING"
    [ -f "${CURRENT_SLOT_FILE}" ] && info "  current-slot: $(cat "${CURRENT_SLOT_FILE}")" || warn "  current-slot: MISSING"

    echo ""
}

cmd_confirm() {
    # Confirm the current boot slot (prevent rollback)
    check_root

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        warn "Not in A/B boot mode, nothing to confirm"
        return 0
    fi

    if is_slot_confirmed; then
        info "Slot ${current_slot} is already confirmed"
        return 0
    fi

    # Create confirmation marker
    echo "$(date -Iseconds)" > "${SLOT_CONFIRMED_FILE}"
    echo "${current_slot}" >> "${SLOT_CONFIRMED_FILE}"

    # Update current-slot file
    echo "${current_slot}" > "${CURRENT_SLOT_FILE}"

    # Update autoboot.txt to make this slot the default
    # (Remove tryboot, set permanent boot)
    if [ -f "${AUTOBOOT_TXT}" ]; then
        sed -i '/tryboot_a_b/d' "${AUTOBOOT_TXT}" 2>/dev/null || true
    fi

    info "Slot ${current_slot} confirmed"
    info "This slot will be used for future boots"
    info "No rollback will occur"
}

cmd_switch() {
    # DEPRECATED: Use switch-to instead
    # Switch to the other slot on next boot (for backwards compatibility)
    check_root

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot switch slots"
    fi

    local other_slot
    other_slot=$(get_other_slot "${current_slot}")

    warn "Note: 'switch' is deprecated, use 'switch-to <slot>' instead"
    info "Switching to slot ${other_slot}..."

    cmd_switch_to "${other_slot}"
}

cmd_switch_to() {
    # Switch to a specific slot on next boot
    check_root

    local target_slot="$1"

    if [ -z "$target_slot" ]; then
        die "Usage: $0 switch-to {A|B}"
    fi

    case "$target_slot" in
        A|B)
            ;;
        *)
            die "Invalid slot: $target_slot (must be A or B)"
            ;;
    esac

    info "Configuring boot to Slot ${target_slot}..."

    # Set tryboot for the target slot
    mkdir -p "${BOOT_DIR}"

    # Update autoboot.txt to enable tryboot
    echo "tryboot_a_b=1" > "${AUTOBOOT_TXT}"

    # Clear confirmation (will test new slot)
    rm -f "${SLOT_CONFIRMED_FILE}"

    # Mark which slot we're trying to boot
    echo "${target_slot}" > "${BOOT_DIR}/target-slot"

    info "Next boot will try Slot ${target_slot}"
    warn "If Slot ${target_slot} fails health check, system will rollback"
    info "Reboot now to switch: sudo reboot"
}

cmd_rollback() {
    # Force rollback to the other slot (simulate failed health check)
    check_root

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot rollback"
    fi

    if is_slot_confirmed; then
        warn "Current slot is confirmed, forcing rollback anyway"
    fi

    local other_slot
    other_slot=$(get_other_slot "${current_slot}")

    warn "Forcing rollback from slot ${current_slot} to slot ${other_slot}"

    # Remove confirmation (trigger rollback)
    rm -f "${SLOT_CONFIRMED_FILE}"

    # Remove tryboot (will boot confirmed slot)
    if [ -f "${AUTOBOOT_TXT}" ]; then
        sed -i '/tryboot_a_b/d' "${AUTOBOOT_TXT}" 2>/dev/null || true
    fi

    # Update current-slot to other slot
    echo "${other_slot}" > "${CURRENT_SLOT_FILE}"

    info "Rollback configured"
    warn "System will boot into slot ${other_slot} on next reboot"
    info "Reboot now: sudo reboot"
}

cmd_promote() {
    # Promote Slot B (tested) to Slot A (stable)
    check_root

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot promote"
    fi

    # Must be running from Slot B to promote it
    if [ "${current_slot}" != "B" ]; then
        die "Can only promote from Slot B. Currently running: Slot ${current_slot}"
    fi

    # Must be confirmed (passed health checks)
    if ! is_slot_confirmed; then
        die "Slot B is not confirmed. Run health checks first or use 'confirm' command"
    fi

    warn "═══════════════════════════════════════════════════════"
    warn "  Promoting Slot B to Stable Slot A"
    warn "═══════════════════════════════════════════════════════"
    warn ""
    warn "This will:"
    warn "  1. Copy Slot B (current, tested) → Slot A (stable)"
    warn "  2. Make Slot A the default boot slot"
    warn "  3. Keep Slot B available for future testing"
    warn ""
    warn "This operation takes 10-15 minutes."
    warn ""

    read -p "Type 'PROMOTE' to confirm: " response
    if [ "$response" != "PROMOTE" ]; then
        info "Promotion cancelled"
        return 0
    fi

    # Get partition devices
    local slot_a_part
    slot_a_part=$(get_slot_partition A)
    local slot_b_part
    slot_b_part=$(get_slot_partition B)

    info "Copying Slot B ($slot_b_part) to Slot A ($slot_a_part)..."
    info "This will take several minutes..."

    # Mount both partitions
    local mount_a="/mnt/slot_a_temp"
    local mount_b="/mnt/slot_b_temp"

    mkdir -p "$mount_a" "$mount_b"

    mount "$slot_a_part" "$mount_a" || die "Failed to mount Slot A"
    mount "$slot_b_part" "$mount_b" || die "Failed to mount Slot B"

    # Copy using rsync
    info "Syncing filesystems..."
    rsync -aAXv --delete "$mount_b/" "$mount_a/" || {
        umount "$mount_a" "$mount_b"
        die "Failed to copy Slot B to Slot A"
    }

    # Unmount
    umount "$mount_a" "$mount_b"
    rmdir "$mount_a" "$mount_b"

    info "Copy complete"

    # Set Slot A as default boot
    if [ -f "${AUTOBOOT_TXT}" ]; then
        sed -i '/tryboot_a_b/d' "${AUTOBOOT_TXT}" 2>/dev/null || true
    fi

    # Mark Slot A as confirmed
    echo "$(date -Iseconds)" > "${SLOT_CONFIRMED_FILE}"
    echo "A" >> "${SLOT_CONFIRMED_FILE}"
    echo "A" > "${CURRENT_SLOT_FILE}"

    info "Slot B has been promoted to Slot A"
    info "Slot A is now the stable baseline"
    info "System will boot from Slot A by default"
    info ""
    info "Reboot to activate Slot A: sudo reboot"
}

cmd_update_stable() {
    # Update Slot A (stable) with a specific image
    check_root

    if [ $# -lt 2 ]; then
        cat << EOF
Usage: $0 update-stable <download_url> <release_tag>

Updates Slot A (stable baseline) with a specific image.
Requires explicit confirmation for safety.

Example:
  sudo $0 update-stable https://github.com/.../image.img.xz beta-2025-10-25

EOF
        exit 1
    fi

    local download_url="$1"
    local release_tag="$2"

    info "Calling update script to update Slot A..."
    info "URL: $download_url"
    info "Tag: $release_tag"

    # Call rq_update_slot.sh with --slot A --confirm
    local update_script="/usr/local/bin/rq_update_slot.sh"

    if [ ! -x "$update_script" ]; then
        die "Update script not found: $update_script"
    fi

    "$update_script" "$download_url" "$release_tag" --slot A --confirm
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat << EOF
Usage: $(basename "$0") <command> [options]

Strategy: Slot A = STABLE (protected), Slot B = TESTING (auto-updates)

Commands:
    status                          Show current slot and boot status
    confirm                         Confirm current slot (prevent rollback)
    switch-to {A|B}                 Boot specific slot on next reboot
    switch                          Switch to other slot (deprecated)
    rollback                        Force rollback to other slot
    promote                         Promote Slot B (tested) → Slot A (stable)
    update-stable <url> <tag>       Update Slot A with specific image

Examples:
    # Check status
    sudo $(basename "$0") status

    # Confirm current boot (prevent rollback)
    sudo $(basename "$0") confirm

    # Switch to specific slot for testing
    sudo $(basename "$0") switch-to B

    # Promote tested Slot B to become new stable Slot A
    sudo $(basename "$0") promote

    # Manually update stable Slot A (requires confirmation)
    sudo $(basename "$0") update-stable https://github.com/.../image.img.xz beta-2025-10-25

EOF
    exit 1
}

main() {
    if [ $# -lt 1 ]; then
        usage
    fi

    local command="$1"
    shift  # Remove command from arguments

    case "${command}" in
        status)
            cmd_status
            ;;
        confirm)
            cmd_confirm
            ;;
        switch)
            cmd_switch
            ;;
        switch-to)
            cmd_switch_to "$@"
            ;;
        rollback)
            cmd_rollback
            ;;
        promote)
            cmd_promote
            ;;
        update-stable)
            cmd_update_stable "$@"
            ;;
        *)
            die "Unknown command: ${command}"
            ;;
    esac
}

main "$@"
