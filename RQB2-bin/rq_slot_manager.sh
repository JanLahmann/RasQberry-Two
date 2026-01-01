#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Manager
# ============================================================================
# Description: Manage A/B boot slots for remote testing
# Usage: rq_slot_manager.sh {status|confirm|switch-to|rollback|promote}
#
# Commands:
#   status      - Show current slot and boot status
#   confirm     - Confirm current slot (prevent rollback)
#   switch-to   - Switch to a specific slot (A or B) using tryboot
#   rollback    - Force rollback to previous slot
#   promote     - Promote Slot B to Slot A (copy)
#
# Tryboot mechanism (Pi 4 and Pi 5):
#   - Uses autoboot.txt with tryboot_a_b=1 for partition-level A/B switching
#   - boot_partition_fallback provides firmware-level fallback on boot failure
#   - Health check confirms slot; unconfirmed slots auto-rollback on reboot

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Boot configuration files
# NOTE: For AB images, config partition (p1) is mounted at /boot/config
# and contains autoboot.txt. The current slot's bootfs (p2 or p3) is at /boot/firmware
BOOT_DIR="/boot/firmware"
BOOT_COMMON_DIR="/boot/config"
AUTOBOOT_TXT="${BOOT_COMMON_DIR}/autoboot.txt"
CURRENT_SLOT_FILE="${BOOT_COMMON_DIR}/current-slot"
SLOT_CONFIRMED_FILE="${BOOT_COMMON_DIR}/slot-confirmed"

# Old paths for backwards compatibility (non-AB images)
AUTOBOOT_TXT_FALLBACK="${BOOT_DIR}/autoboot.txt"
CURRENT_SLOT_FILE_FALLBACK="${BOOT_DIR}/current-slot"
SLOT_CONFIRMED_FILE_FALLBACK="${BOOT_DIR}/slot-confirmed"

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
    # AB layout: p5=Slot A, p6=Slot B (root partitions)
    # Boot partition (p2 or p3) also indicates slot

    # Check if running in AB boot mode (look for CONFIG partition)
    local root_part
    root_part=$(findmnt / -o source -n)
    local root_dev
    root_dev=$(lsblk -no pkname "$root_part")

    # Check for config partition (indicates AB image)
    local config_label
    config_label=$(lsblk -no label "/dev/${root_dev}p1" 2>/dev/null || lsblk -no label "/dev/${root_dev}1" 2>/dev/null || echo "")

    # Check for AB image (CONFIG partition label, case-insensitive)
    local label_upper
    label_upper=$(echo "$config_label" | tr '[:lower:]' '[:upper:]')
    if [ "$label_upper" = "CONFIG" ]; then
        # AB image - determine slot from root partition
        case "${root_part}" in
            *p5|*5)
                echo "A"
                ;;
            *p6|*6)
                echo "B"
                ;;
            *)
                warn "Cannot determine slot from partition: ${root_part}"
                # Fall back to current-slot file
                if [ -f "${CURRENT_SLOT_FILE}" ]; then
                    cat "${CURRENT_SLOT_FILE}"
                elif [ -f "${CURRENT_SLOT_FILE_FALLBACK}" ]; then
                    cat "${CURRENT_SLOT_FILE_FALLBACK}"
                else
                    echo "UNKNOWN"
                fi
                ;;
        esac
    else
        # Not in A/B boot mode (standard single-partition image)
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
    # Get ROOT partition device for a given slot
    # V2 layout: p5=Slot A rootfs, p6=Slot B rootfs
    local slot="$1"
    local root_dev
    root_dev=$(lsblk -no pkname "$(get_root_partition)")

    case "${slot}" in
        A)
            # Handle both mmcblk0p5 and sd5 style naming
            if [ -b "/dev/${root_dev}p5" ]; then
                echo "/dev/${root_dev}p5"
            else
                echo "/dev/${root_dev}5"
            fi
            ;;
        B)
            if [ -b "/dev/${root_dev}p6" ]; then
                echo "/dev/${root_dev}p6"
            else
                echo "/dev/${root_dev}6"
            fi
            ;;
        *)
            echo "UNKNOWN"
            ;;
    esac
}

get_boot_partition() {
    # Get BOOT partition device for a given slot
    # V2 layout: p2=Slot A bootfs, p3=Slot B bootfs
    local slot="$1"
    local root_dev
    root_dev=$(lsblk -no pkname "$(get_root_partition)")

    case "${slot}" in
        A)
            if [ -b "/dev/${root_dev}p2" ]; then
                echo "/dev/${root_dev}p2"
            else
                echo "/dev/${root_dev}2"
            fi
            ;;
        B)
            if [ -b "/dev/${root_dev}p3" ]; then
                echo "/dev/${root_dev}p3"
            else
                echo "/dev/${root_dev}3"
            fi
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

    # Check if A/B boot is configured (look for autoboot.txt in bootfs-common)
    if [ ! -f "${AUTOBOOT_TXT}" ] && [ ! -f "${AUTOBOOT_TXT_FALLBACK}" ]; then
        warn "A/B boot not configured (autoboot.txt not found)"
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

    # Partition sizes
    echo ""
    info "Partition Sizes:"
    local size_a size_b size_data
    size_a=$(lsblk -bno SIZE /dev/mmcblk0p5 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    size_b=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    size_data=$(lsblk -bno SIZE /dev/mmcblk0p7 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    info "  SYSTEM-A (p5): ${size_a}"
    info "  SYSTEM-B (p6): ${size_b}"
    info "  DATA (p7):     ${size_data}"

    # Check if expansion needed (system-b < 1GB indicates placeholder)
    local size_b_bytes
    size_b_bytes=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    if [ "${size_b_bytes:-0}" -lt 1073741824 ]; then
        echo ""
        warn "⚠ Partitions need expansion! Run: sudo raspi-config → RasQberry → AB_BOOT → EXPAND"
        warn "  Or: sudo $(basename "$0") expand"
    fi

    # Boot files
    echo ""
    info "Boot Configuration Files:"
    [ -f "${AUTOBOOT_TXT}" ] && info "  autoboot.txt: EXISTS" || warn "  autoboot.txt: MISSING"
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

    # Update autoboot.txt to make this slot the permanent default
    # This ensures normal boots (without tryboot flag) use the confirmed slot
    local confirmed_partition other_partition
    if [ "${current_slot}" = "A" ]; then
        confirmed_partition=2
        other_partition=3
    else
        confirmed_partition=3
        other_partition=2
    fi

    cat > "${AUTOBOOT_TXT}" << EOF
[all]
tryboot_a_b=1
boot_partition=${confirmed_partition}
boot_partition_fallback=${other_partition}

[tryboot]
boot_partition=${other_partition}
boot_partition_fallback=${confirmed_partition}
EOF

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
    # Switch to a specific slot on next boot using tryboot
    # The tryboot flag triggers [tryboot] section in autoboot.txt
    # If health check fails, normal reboot falls back to [all] section (confirmed slot)
    check_root

    local target_slot=""
    local do_reboot=false

    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            A|B)
                target_slot="$1"
                ;;
            --reboot)
                do_reboot=true
                ;;
            *)
                die "Invalid argument: $1"
                ;;
        esac
        shift
    done

    if [ -z "$target_slot" ]; then
        die "Usage: $0 switch-to {A|B} [--reboot]"
    fi

    local current_slot
    current_slot=$(get_current_slot)

    if [ "$current_slot" = "$target_slot" ]; then
        info "Already on Slot ${target_slot}"
        return 0
    fi

    info "Configuring tryboot to Slot ${target_slot}..."

    # Ensure boot config directory exists
    mkdir -p "${BOOT_COMMON_DIR}"

    # Determine partitions
    # v3 layout: p2=boot-a (Slot A), p3=boot-b (Slot B)
    local current_partition target_partition
    if [ "$current_slot" = "A" ]; then
        current_partition=2
        target_partition=3
    else
        current_partition=3
        target_partition=2
    fi

    # Update autoboot.txt: current slot as default, target as tryboot
    # This ensures rollback to current slot if tryboot fails
    cat > "${AUTOBOOT_TXT}" << EOF
[all]
tryboot_a_b=1
boot_partition=${current_partition}
boot_partition_fallback=${target_partition}

[tryboot]
boot_partition=${target_partition}
boot_partition_fallback=${current_partition}
EOF

    # Clear confirmation (will test new slot)
    rm -f "${SLOT_CONFIRMED_FILE}"

    # Mark which slot we're trying to boot
    echo "${target_slot}" > "${BOOT_COMMON_DIR}/target-slot"

    info "Slot ${target_slot} configured for tryboot"
    info "Current slot (${current_slot}) remains default until new slot is confirmed"

    if [ "$do_reboot" = true ]; then
        info ""
        info "Rebooting with tryboot flag..."
        # Aggressive cache flush - required after heavy I/O (dd, wget)
        # Without this, tryboot flag may not be set properly on Pi 5
        sync
        sync
        sync
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
        sleep 2
        reboot '0 tryboot'
    else
        info ""
        info "To boot into the new slot, use: AB_BOOT -> TRYBOOT_${target_slot}"
        info "If reboot returns to same slot, retry TRYBOOT_${target_slot}"
    fi
}

cmd_rollback() {
    # Force rollback to the other slot
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

    # Determine partitions
    local other_partition current_partition
    if [ "${other_slot}" = "A" ]; then
        other_partition=2
        current_partition=3
    else
        other_partition=3
        current_partition=2
    fi

    # Update autoboot.txt to boot other slot as default
    cat > "${AUTOBOOT_TXT}" << EOF
[all]
tryboot_a_b=1
boot_partition=${other_partition}
boot_partition_fallback=${current_partition}

[tryboot]
boot_partition=${current_partition}
boot_partition_fallback=${other_partition}
EOF

    # Remove confirmation
    rm -f "${SLOT_CONFIRMED_FILE}"

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

    # Set Slot A as default boot with proper tryboot config
    cat > "${AUTOBOOT_TXT}" << EOF
[all]
tryboot_a_b=1
boot_partition=2
boot_partition_fallback=3

[tryboot]
boot_partition=3
boot_partition_fallback=2
EOF

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
    local update_script="/usr/bin/rq_update_slot.sh"

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
    switch-to {A|B} [--reboot]      Boot specific slot on next reboot
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
    sudo reboot '0 tryboot'

    # Switch and reboot in one command
    sudo $(basename "$0") switch-to B --reboot

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
