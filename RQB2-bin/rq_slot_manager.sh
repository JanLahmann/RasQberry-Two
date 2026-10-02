#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Manager
# ============================================================================
# Description: Manage A/B boot slots for remote testing
# Usage: rq_slot_manager.sh {status|summary|slot-content|confirm|switch-to|rollback|promote}
#
# Commands:
#   status        - Show current slot, boot status and what each slot holds
#   summary       - The same as key=value lines, for the menu and scripts
#   slot-content  - What one slot holds: its version, or EMPTY/INCOMPLETE/...
#   confirm       - Confirm current slot (prevent rollback)
#   switch-to     - Switch to a specific slot (A or B) using tryboot
#   rollback      - Force rollback to previous slot
#   promote       - Promote Slot B to Slot A (copy)
#
# switch-to and rollback refuse a slot that holds no system (exit code 25):
# starting an empty slot hangs the Pi, and a rollback into one is permanent.
# --force skips that check.
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
BOOT_COMMON_DIR="${RQ_BOOT_COMMON_DIR:-/boot/config}"   # override: tests
AUTOBOOT_TXT="${BOOT_COMMON_DIR}/autoboot.txt"
CURRENT_SLOT_FILE="${BOOT_COMMON_DIR}/current-slot"
SLOT_CONFIRMED_FILE="${BOOT_COMMON_DIR}/slot-confirmed"

# Old paths for backwards compatibility (non-AB images)
AUTOBOOT_TXT_FALLBACK="${BOOT_DIR}/autoboot.txt"
CURRENT_SLOT_FILE_FALLBACK="${BOOT_DIR}/current-slot"
SLOT_CONFIRMED_FILE_FALLBACK="${BOOT_DIR}/slot-confirmed"

# Root of the running system (override: tests) and the promote log
RUNNING_ROOT="${RQ_RUNNING_ROOT:-/}"
PROMOTE_LOG="${RQ_PROMOTE_LOG:-/var/log/rasqberry-promote.log}"

RC_SLOT_EMPTY=25    # switch-to / rollback refused: the target holds no system

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
    # Get ROOT partition device for a given slot (shared helper, issue #229)
    local slot="$1"
    get_ab_system_partition "$slot" || echo "UNKNOWN"
}

get_boot_partition() {
    # Get BOOT partition device for a given slot (shared helper, issue #229)
    local slot="$1"
    get_ab_boot_partition "$slot" || echo "UNKNOWN"
}

# ============================================================================
# What a slot holds (R-055, R-118)
# ============================================================================
# slot_content prints one of:
#   <version>   first line of /etc/rasqberry-version of a slot with a system
#   SYSTEM      a system without a RasQberry version file
#   EMPTY       no system: the 16MB placeholder, a freshly expanded slot (an
#               empty filesystem), or a partition that cannot be mounted
#   INCOMPLETE  an update or promote into this slot was interrupted
#               (marker slot-<X>-incomplete, written by rq_update_slot.sh)
#   UNKNOWN     cannot look: not root, and the slot is not mounted anywhere

root_content() {
    # What the tree at <root> holds (see above)
    local root="${1%/}" ver=""
    # Merged /usr (bookworm and later): the init binary is a regular file
    # here, so no absolute symlink can point outside <root>
    if [ ! -f "${root}/usr/lib/systemd/systemd" ]; then
        echo "EMPTY"
        return 0
    fi
    if [ -r "${root}/etc/rasqberry-version" ]; then
        ver=$(head -1 "${root}/etc/rasqberry-version" | tr -d '[:space:]')
    fi
    echo "${ver:-SYSTEM}"
}

slot_content() {
    local slot="$1" part mnt tmp="" result
    case "$slot" in A|B) ;; *) echo "UNKNOWN"; return 0 ;; esac

    if [ -f "${BOOT_COMMON_DIR}/slot-${slot}-incomplete" ]; then
        echo "INCOMPLETE"
        return 0
    fi
    if [ "$slot" = "$(get_current_slot)" ]; then
        root_content "$RUNNING_ROOT"
        return 0
    fi

    part=$(get_slot_partition "$slot")
    # Already mounted (e.g. by the desktop automounter): look there
    mnt=$(findmnt -rn -o TARGET --source "$part" 2>/dev/null | head -1 || true)
    if [ -z "$mnt" ]; then
        if [ ! -b "$part" ]; then
            echo "EMPTY"
            return 0
        fi
        if [ "$(id -u)" -ne 0 ]; then
            echo "UNKNOWN"
            return 0
        fi
        tmp=$(mktemp -d "${TMPDIR:-/tmp}/rq-slot-${slot}.XXXXXX")
        # noload: a read-only look must not replay the journal of the slot
        if ! mount -o ro,noload "$part" "$tmp" 2>/dev/null \
            && ! mount -o ro "$part" "$tmp" 2>/dev/null; then
            rmdir "$tmp" 2>/dev/null || true
            echo "EMPTY"
            return 0
        fi
        mnt="$tmp"
    fi
    result=$(root_content "$mnt")
    if [ -n "$tmp" ]; then
        umount "$tmp" 2>/dev/null || umount -l "$tmp" 2>/dev/null || true
        rmdir "$tmp" 2>/dev/null || true
    fi
    echo "$result"
}

require_slot_system() {
    # Refuse to boot <slot> unless it holds a system (R-055): with no init
    # the kernel halts, and the Pi hangs until it is switched off and on.
    # <force> = true skips the check (expert use).
    local slot="$1" force="${2:-false}" content how
    content=$(slot_content "$slot")
    case "$content" in
        EMPTY|INCOMPLETE|UNKNOWN) ;;
        *) return 0 ;;
    esac
    if [ "$force" = true ]; then
        warn "Slot ${slot} holds no usable system (${content}) - continuing because of --force"
        return 0
    fi
    if [ "$slot" = "B" ]; then
        how="Install a system into Slot B first:
Software & Image Updates -> Slot Manager -> Install an update into Slot B."
    else
        how="Slot A gets a system when a tested Slot B is promoted:
Software & Image Updates -> Slot Manager -> PROMOTE (while running Slot B)."
    fi
    case "$content" in
        EMPTY)
            echo "ERROR: Slot ${slot} holds no system (it is empty), so the Pi cannot start from it.
Starting an empty slot leaves the Pi hanging at a black screen until it is
switched off and on. ${how}" >&2 ;;
        INCOMPLETE)
            echo "ERROR: Slot ${slot} holds an unfinished update (it was interrupted), so the Pi
cannot start from it. ${how}" >&2 ;;
        *)
            echo "ERROR: Cannot check what Slot ${slot} holds (run this as root)." >&2 ;;
    esac
    exit "$RC_SLOT_EMPTY"
}

default_boot_slot() {
    # The slot a normal (not tryboot) start boots: [all] boot_partition
    local part
    part=$(awk '/^\[/ { sec = $0 } sec == "[all]" && /^boot_partition=/ { sub(/^boot_partition=/, ""); print; exit }' \
        "${AUTOBOOT_TXT}" 2>/dev/null || true)
    case "$part" in
        2) echo "A" ;;
        3) echo "B" ;;
        *) echo "UNKNOWN" ;;
    esac
}

unmount_slot_partition() {
    # Unmount every mount of <device> (the desktop automounts the inactive
    # slot, R-146); stop if one stays busy, before anything is written
    local dev="$1" mnt
    for mnt in $(findmnt -rn -o TARGET --source "$dev" 2>/dev/null || true); do
        if umount "$mnt" 2>/dev/null; then
            info "Unmounted ${dev} from ${mnt}"
        fi
    done
    mnt=$(findmnt -rn -o TARGET --source "$dev" 2>/dev/null | head -1 || true)
    if [ -n "$mnt" ]; then
        die "${dev} is in use at ${mnt} and cannot be unmounted. Close any window or program that shows files there, then try again."
    fi
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

    # Confirmation status. Unconfirmed returns to the other slot only when a
    # normal start ([all] in autoboot.txt) points there, i.e. during a tryboot.
    local next_slot
    next_slot=$(default_boot_slot)
    if is_slot_confirmed; then
        info "Slot Status: CONFIRMED (no rollback will occur)"
    elif [ "$next_slot" != "UNKNOWN" ] && [ "$next_slot" != "$current_slot" ]; then
        warn "Slot Status: UNCONFIRMED (the next restart returns to Slot ${next_slot} unless this slot is confirmed)"
    else
        warn "Slot Status: UNCONFIRMED (stays the default; the health check confirms it after a good start)"
    fi

    # What each slot holds
    echo ""
    info "Slot Contents:"
    local slot label content
    for slot in A B; do
        label="stable"
        [ "$slot" = "B" ] && label="testing"
        content=$(slot_content "$slot")
        case "$content" in
            EMPTY)      content="empty (no system)" ;;
            INCOMPLETE) content="unfinished (an update or copy was interrupted)" ;;
            UNKNOWN)    content="unknown (run as root to look)" ;;
            SYSTEM)     content="a system without version information" ;;
        esac
        [ "$slot" = "$current_slot" ] && content="${content}  <- running"
        info "  Slot ${slot} (${label}): ${content}"
    done

    # Slot partitions
    echo ""
    info "Slot Partitions:"
    info "  Slot A: $(get_slot_partition A)"
    info "  Slot B: $(get_slot_partition B)"

    # Partition sizes
    echo ""
    info "Partition Sizes:"
    local part_a part_b part_data size_a size_b size_data
    part_a=$(get_slot_partition A)
    part_b=$(get_slot_partition B)
    part_data=$(ab_partition_by_number 7)
    size_a=$(lsblk -bno SIZE "$part_a" 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    size_b=$(lsblk -bno SIZE "$part_b" 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    size_data=$(lsblk -bno SIZE "$part_data" 2>/dev/null | awk '{printf "%.1fG", $1/1024/1024/1024}')
    info "  SYSTEM-A (${part_a}): ${size_a}"
    info "  SYSTEM-B (${part_b}): ${size_b}"
    info "  DATA (${part_data}):     ${size_data}"

    # Check if expansion needed (system-b < 1GB indicates placeholder)
    local size_b_bytes
    size_b_bytes=$(lsblk -bno SIZE "$part_b" 2>/dev/null)
    if [ "${size_b_bytes:-0}" -lt 1073741824 ]; then
        echo ""
        warn "⚠ Slot B is still the 16MB placeholder the image ships with - A/B cannot"
        warn "  be used until the partitions are expanded (needs a 64GB+ card):"
        warn "      sudo raspi-config → 0 RasQberry → Software & Image Updates → EXPAND"
        warn "  Until then Slot A stays at 10GB, which the image nearly fills, and"
        warn "  rq_update_slot.sh cannot stage a download. See docs/ab-boot.md."
        # NB: this used to also offer "sudo rq_slot_manager.sh expand". There is no
        # such command here - it would have died with "Unknown command: expand".
        # The expansion lives in RQB2_menu.sh (do_expand_ab_partitions), reached
        # through raspi-config.
    fi

    # Boot files
    echo ""
    info "Boot Configuration Files:"
    [ -f "${AUTOBOOT_TXT}" ] && info "  autoboot.txt: EXISTS" || warn "  autoboot.txt: MISSING"
    [ -f "${CURRENT_SLOT_FILE}" ] && info "  current-slot: $(cat "${CURRENT_SLOT_FILE}")" || warn "  current-slot: MISSING"

    echo ""
}

cmd_summary() {
    # Machine-readable state, one key=value per line (RQB2_menu.sh, rq_info.sh):
    #   layout     ab | single
    #   current    A | B | UNKNOWN       the running slot
    #   confirmed  yes | no              the running slot is confirmed
    #   default    A | B | UNKNOWN       the slot a normal start boots
    #   pending    A | B | (empty)       a slot switch that was requested
    #   slot_a     what Slot A holds (see slot_content)
    #   slot_b     what Slot B holds
    #   expanded   yes | no              Slot B is large enough for an image
    local current
    current=$(get_current_slot)
    if [ "$current" = "SINGLE" ]; then
        echo "layout=single"
        return 0
    fi
    echo "layout=ab"
    echo "current=${current}"
    if is_slot_confirmed; then echo "confirmed=yes"; else echo "confirmed=no"; fi
    echo "default=$(default_boot_slot)"
    local pending=""
    [ -f "${BOOT_COMMON_DIR}/target-slot" ] && pending=$(tr -d '[:space:]' < "${BOOT_COMMON_DIR}/target-slot")
    echo "pending=${pending}"
    echo "slot_a=$(slot_content A)"
    echo "slot_b=$(slot_content B)"
    local size_b
    size_b=$(lsblk -bno SIZE "$(get_slot_partition B)" 2>/dev/null | head -1 || true)
    if [ "${size_b:-0}" -ge 4294967296 ] 2>/dev/null; then
        echo "expanded=yes"
    else
        echo "expanded=no"
    fi
}

cmd_slot_content() {
    [ $# -eq 1 ] && { [ "$1" = "A" ] || [ "$1" = "B" ]; } || die "Usage: $0 slot-content {A|B}"
    slot_content "$1"
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
    local force=false

    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            A|B)
                target_slot="$1"
                ;;
            --reboot)
                do_reboot=true
                ;;
            --force)
                force=true
                ;;
            *)
                die "Invalid argument: $1"
                ;;
        esac
        shift
    done

    if [ -z "$target_slot" ]; then
        die "Usage: $0 switch-to {A|B} [--reboot] [--force]"
    fi

    local current_slot
    current_slot=$(get_current_slot)

    if [ "$current_slot" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot switch slots"
    fi

    if [ "$current_slot" = "$target_slot" ]; then
        info "Already on Slot ${target_slot}"
        return 0
    fi

    # Never send the Pi into a slot that holds no system (R-055)
    require_slot_system "$target_slot" "$force"

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

    # Mark which slot we're trying to boot and reset the retry budget
    # (rq_tryboot_retry.sh re-issues the tryboot once if the flag is lost)
    echo "${target_slot}" > "${BOOT_COMMON_DIR}/target-slot"
    echo 0 > "${BOOT_COMMON_DIR}/switch-retries"

    info "Slot ${target_slot} configured for tryboot"
    info "Current slot (${current_slot}) remains default until new slot is confirmed"

    if [ "$do_reboot" = true ]; then
        info ""
        info "Rebooting with tryboot flag..."

        # Stop automounter to prevent re-mounting during reboot
        systemctl stop udisks2 2>/dev/null && info "Stopped udisks2" || true

        # Unmount target slot partitions - automounter may have mounted them
        # which can interfere with tryboot on Pi 5
        local tgt_boot tgt_sys
        tgt_boot=$(get_boot_partition "$target_slot")
        tgt_sys=$(get_slot_partition "$target_slot")
        umount "$tgt_boot" 2>/dev/null && info "Unmounted ${tgt_boot}" || true
        umount "$tgt_sys" 2>/dev/null && info "Unmounted ${tgt_sys}" || true

        # Verify unmount succeeded
        if mount | grep -qE "^(${tgt_boot}|${tgt_sys}) " 2>/dev/null; then
            warn "Warning: target slot partitions may still be mounted"
        fi

        # Flush all buffers and drop caches - critical after partition writes
        info "Flushing buffers and caches..."
        sync
        blockdev --flushbufs "/dev/$(ab_boot_device)" 2>/dev/null || true
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

        # Wait until writeback has fully drained: a tryboot reboot issued
        # while the kernel is still flushing loses the tryboot flag and the
        # system boots the default slot instead (reproduced on Pi 4 and
        # Pi 5 directly after writing a full image to SD).
        info "Waiting for disk writeback to settle..."
        local settle_deadline=$((SECONDS + 300)) dirty_kb=0 wb_kb=0
        while [ "$SECONDS" -lt "$settle_deadline" ]; do
            sync
            dirty_kb=$(awk '/^Dirty:/ {print $2}' /proc/meminfo)
            wb_kb=$(awk '/^Writeback:/ {print $2}' /proc/meminfo)
            if [ $((dirty_kb + wb_kb)) -lt 4096 ]; then
                break
            fi
            sleep 2
        done
        info "Writeback settled (Dirty=${dirty_kb}kB Writeback=${wb_kb}kB)"
        sleep 2
        reboot '0 tryboot'
    else
        info ""
        info "To boot into Slot ${target_slot} now: sudo reboot '0 tryboot'"
        info "(or: raspi-config -> 0 RasQberry -> Software & Image Updates -> Slot Manager)"
    fi
}

cmd_rollback() {
    # Force rollback to the other slot (permanent: [all] points there)
    check_root

    local force=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --force) force=true ;;
            *) die "Invalid argument: $1" ;;
        esac
        shift
    done

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot rollback"
    fi

    local other_slot
    other_slot=$(get_other_slot "${current_slot}")

    # A rollback is permanent - into an empty slot it would leave a Pi that
    # hangs at every start (R-055)
    require_slot_system "$other_slot" "$force"

    if is_slot_confirmed; then
        warn "Current slot is confirmed, forcing rollback anyway"
    fi

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
    #   --yes  skip the typed confirmation (the menu asks in its own dialog)
    check_root

    local assume_yes=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --yes|-y) assume_yes=true ;;
            *) die "Invalid argument: $1" ;;
        esac
        shift
    done

    local current_slot
    current_slot=$(get_current_slot)

    if [ "${current_slot}" = "SINGLE" ]; then
        die "Not in A/B boot mode, cannot promote"
    fi

    # Must be running from Slot B to promote it
    if [ "${current_slot}" != "B" ]; then
        die "PROMOTE copies Slot B to Slot A, so it works only while Slot B is the running system. Currently running: Slot ${current_slot}"
    fi

    # Must be confirmed (passed health checks)
    if ! is_slot_confirmed; then
        die "Slot B is not confirmed yet. The health check confirms it shortly after a good start; or run: sudo rq_slot_manager.sh confirm"
    fi

    local version_a version_b
    version_b=$(slot_content B)
    version_a=$(slot_content A)

    info "PROMOTE: copy the running system (Slot B, ${version_b})"
    info "         to the stable Slot A (now: ${version_a})."
    info "Slot A's current contents are replaced. This takes 10-15 minutes."

    if [ "$assume_yes" != true ]; then
        # The prompt goes to stderr: it is only visible in a terminal. Without
        # one (output captured, no keyboard) it would wait invisibly (R-051).
        [ -t 0 ] && [ -t 2 ] || die "promote asks for a typed confirmation: run it in a terminal, or pass --yes"
        local response
        read -r -p "Type 'PROMOTE' to confirm: " response
        if [ "$response" != "PROMOTE" ]; then
            info "Promotion cancelled"
            return 0
        fi
    fi

    # Get partition devices
    local slot_a_part slot_b_part boot_a_part boot_b_part
    slot_a_part=$(get_slot_partition A)
    slot_b_part=$(get_slot_partition B)
    boot_a_part=$(get_boot_partition A)
    boot_b_part=$(get_boot_partition B)

    # Slot A must not be in use elsewhere (desktop automount) while it is
    # overwritten - stop now, before anything is written
    unmount_slot_partition "$slot_a_part"
    unmount_slot_partition "$boot_a_part"

    : > "$PROMOTE_LOG" 2>/dev/null || PROMOTE_LOG=/dev/null
    info "Step 1 of 2: copying the system, Slot B ($slot_b_part) -> Slot A ($slot_a_part)..."
    info "(details: $PROMOTE_LOG)"

    # Mount both system partitions
    local mount_a="/mnt/slot_a_temp"
    local mount_b="/mnt/slot_b_temp"

    mkdir -p "$mount_a" "$mount_b"

    mount "$slot_a_part" "$mount_a" || die "Failed to mount Slot A"
    mount "$slot_b_part" "$mount_b" || { umount "$mount_a"; die "Failed to mount Slot B"; }

    # From the first write until the copy has finished, Slot A holds no
    # usable system: switch-to and rollback refuse it, and the Pi keeps
    # starting from Slot B
    echo "$(date -Iseconds) promote ${version_b}" > "${BOOT_COMMON_DIR}/slot-A-incomplete"
    sync

    # Copy using rsync. Progress on a terminal; the file list never goes to
    # stdout (from the menu it used to be captured whole and overflowed the
    # result box); errors and the summary go to the log.
    local progress="--quiet"
    [ -t 1 ] && progress="--info=progress2"
    rsync -aAX --delete "$progress" --log-file="$PROMOTE_LOG" --log-file-format="" "$mount_b/" "$mount_a/" || {
        umount "$mount_a" "$mount_b"
        die "Failed to copy Slot B to Slot A (see $PROMOTE_LOG). The Pi keeps starting from Slot B."
    }

    # The copy carries Slot B's fstab - rewrite mounts for Slot A
    info "Updating fstab for Slot A..."
    local config_part data_part
    config_part=$(ab_partition_by_number 1)
    data_part=$(ab_partition_by_number 7)
    cat > "$mount_a/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
${config_part}              /boot/config    vfat    defaults          0   2
${boot_a_part}              /boot/firmware  vfat    defaults          0   2
${slot_a_part}              /               ext4    defaults,noatime  0   1
${data_part}                /data           ext4    defaults,noatime  0   2
EOF

    umount "$mount_a" "$mount_b"
    rmdir "$mount_a" "$mount_b"

    # Sync the boot partition too - kernel and /lib/modules must match
    info "Step 2 of 2: copying the boot files ($boot_b_part -> $boot_a_part)..."
    local boot_mount_a="/mnt/boot_a_temp"
    local boot_mount_b="/mnt/boot_b_temp"
    mkdir -p "$boot_mount_a" "$boot_mount_b"

    # Boot-B is normally mounted at /boot/firmware on a running Slot B; use bind-safe ro mount
    mount -o ro "$boot_b_part" "$boot_mount_b" 2>/dev/null || boot_mount_b="/boot/firmware"
    mount "$boot_a_part" "$boot_mount_a" || {
        [ "$boot_mount_b" != "/boot/firmware" ] && umount "$boot_mount_b"
        die "Failed to mount Slot A boot partition"
    }

    # VFAT supports neither ownership nor permissions - copy data+times only
    rsync -rt --delete --log-file="$PROMOTE_LOG" --log-file-format="" "$boot_mount_b/" "$boot_mount_a/" || {
        umount "$boot_mount_a"
        [ "$boot_mount_b" != "/boot/firmware" ] && umount "$boot_mount_b"
        die "Failed to copy boot partition (see $PROMOTE_LOG). The Pi keeps starting from Slot B."
    }

    # The copied cmdline.txt points at Slot B's root - fix it for Slot A
    if [ -f "$boot_mount_a/cmdline.txt" ]; then
        sed -i "s|root=[^ ]*|root=${slot_a_part}|g" "$boot_mount_a/cmdline.txt"
        info "cmdline.txt updated: root=${slot_a_part}"
    fi

    sync
    umount "$boot_mount_a"
    [ "$boot_mount_b" != "/boot/firmware" ] && umount "$boot_mount_b"
    rmdir "$boot_mount_a" /mnt/boot_b_temp 2>/dev/null || true

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
    rm -f "${BOOT_COMMON_DIR}/slot-A-incomplete"
    sync

    info "Slot B has been promoted: Slot A now holds ${version_b}."
    info "The Pi starts from Slot A from the next restart on, and Slot B"
    info "is then free for the next update."
    info ""
    info "Restart now to start Slot A: sudo reboot"
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

Strategy: Slot A = STABLE (protected), Slot B = TESTING (updates go here)

Commands:
    status                          Show current slot, boot status, slot contents
    summary                         The same as key=value lines (for scripts)
    slot-content {A|B}              What a slot holds: version, EMPTY, INCOMPLETE, ...
    confirm                         Confirm current slot (prevent rollback)
    switch-to {A|B} [--reboot] [--force]
                                    Boot specific slot on next reboot
    switch                          Switch to other slot (deprecated)
    rollback [--force]              Make the other slot the default (permanent)
    promote [--yes]                 Promote Slot B (tested) → Slot A (stable)
    update-stable <url> <tag>       Update Slot A with specific image

switch-to and rollback refuse a slot that holds no system (exit code $RC_SLOT_EMPTY);
--force skips that check.

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
        summary)
            cmd_summary
            ;;
        slot-content)
            cmd_slot_content "$@"
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
            cmd_rollback "$@"
            ;;
        promote)
            cmd_promote "$@"
            ;;
        update-stable)
            cmd_update_stable "$@"
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            die "Unknown command: ${command}"
            ;;
    esac
}

main "$@"
