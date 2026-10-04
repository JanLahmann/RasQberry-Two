#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Manager
# ============================================================================
# Description: Manage the two systems (Slot A, Slot B) of an A/B card
# Usage: rq_slot_manager.sh {status|summary|slot-content|plan-update|confirm|switch-to|rollback}
#
# Update model (ping-pong, Jan 2026-10-04): an update always goes into the
# slot that is NOT running (rq_update_slot.sh). Its trial start (tryboot) and
# the health check make it the start slot; the other slot stays as the way
# back (switch-to / rollback). Neither slot is special.
#
# Commands:
#   status        - Show current slot, boot status and what each slot holds
#   summary       - The same as key=value lines, for the menu and scripts
#   slot-content  - What one slot holds: its version, or EMPTY/INCOMPLETE/...
#   plan-update   - Where an update would go and what the guard says about it
#   confirm       - Confirm current slot (prevent rollback)
#   switch-to     - Switch to a specific slot (A or B) using tryboot; leaves
#                   target-slot, switch-retries and switch-requested (when it
#                   was asked for, by this slot's clock) on /boot/config
#   rollback      - Force rollback to previous slot
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

# Root of the running system (override: tests)
RUNNING_ROOT="${RQ_RUNNING_ROOT:-/}"

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
#   INCOMPLETE  an update into this slot was interrupted
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
    how="Install a system into Slot ${slot} first: Software & Image Updates ->
Slot Manager -> Install an update into the other system (Slot ${slot})."
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

# ============================================================================
# Planning an update: the target slot and Jan's guard (ping-pong)
# ============================================================================
# The guard keeps at least one slot at beta or stable. The release stream of
# a version or release tag (the tags of rq_ab_releases.sh; a stable release is
# tagged v1.2.3, its /etc/rasqberry-version says 1.2.3):
#   development-*, dev-*      dev      rank 0
#   beta-*                    beta     rank 1
#   v1.2.3, 1.2.3, stable-*   stable   rank 2
#   anything else             unknown  (ranks like dev, never counts as safe)
# A downgrade installs a lower stream than the target slot holds, or an older
# release of the same beta or stable stream (dev over dev never warns). The
# target is the last safe slot when it holds beta or stable and the running
# slot does not.

version_stream() {
    rq_release_channel "$1"     # rq_common.sh: the one shell copy of the rule
}

# The stream of a slot_content value: none for a slot without a system
content_stream() {
    case "$1" in
        EMPTY|INCOMPLETE)  echo none ;;
        SYSTEM|UNKNOWN|"") echo unknown ;;
        *)                 version_stream "$1" ;;
    esac
}

stream_rank() {
    case "$1" in
        stable) echo 2 ;;
        beta)   echo 1 ;;
        *)      echo 0 ;;
    esac
}

is_safe_stream() {
    [ "$1" = "beta" ] || [ "$1" = "stable" ]
}

stream_noun() {
    case "$1" in
        stable) echo "stable release" ;;
        beta)   echo "beta release" ;;
        dev)    echo "development build" ;;
        *)      echo "system of unknown origin" ;;
    esac
}

# True when release <a> is older than release <b> of the same stream: beta
# tags compare by their date and time, stable ones by version number
version_older() {
    local a="$1" b="$2"
    a=${a#beta-}; a=${a#stable-}; a=${a#v}
    b=${b#beta-}; b=${b#stable-}; b=${b#v}
    [ "$a" != "$b" ] || return 1
    [ "$(printf '%s\n%s\n' "$a" "$b" | sort -V | head -n 1)" = "$a" ]
}

# "<stream> <version>" for a slot_content value. Without a version the second
# word says why: empty, unfinished, system (no version file), unknown
holds_text() {
    case "$1" in
        EMPTY)      echo "none empty" ;;
        INCOMPLETE) echo "none unfinished" ;;
        SYSTEM)     echo "unknown system" ;;
        UNKNOWN|"") echo "unknown unknown" ;;
        *)          echo "$(version_stream "$1") $1" ;;
    esac
}

# A slot_content value for people: "beta-2026-10-03-095636 (beta)"
content_words() {
    local stream
    case "$1" in
        EMPTY)      echo "empty (no system)" ;;
        INCOMPLETE) echo "unfinished (an update was interrupted)" ;;
        UNKNOWN|"") echo "unknown (run as root to look)" ;;
        SYSTEM)     echo "a system without version information" ;;
        *)
            stream=$(version_stream "$1")
            if [ "$stream" = "unknown" ]; then echo "$1"; else echo "$1 ($stream)"; fi ;;
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
    local slot content notes
    for slot in A B; do
        content=$(content_words "$(slot_content "$slot")")
        notes=""
        [ "$slot" = "$current_slot" ] && notes="running"
        [ "$slot" = "$next_slot" ] && notes="${notes:+$notes, }start slot"
        info "  Slot ${slot}: ${content}${notes:+  <- ${notes}}"
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

    # Placeholder Slot B: say what this card can do (not prepared yet, or a
    # small card running one system) - rq_expand_ab.sh decides (R-006)
    local size_b_bytes
    size_b_bytes=$(lsblk -bno SIZE "$part_b" 2>/dev/null)
    if [ "${size_b_bytes:-0}" -lt 1073741824 ]; then
        echo ""
        "${SCRIPT_DIR}/rq_expand_ab.sh" explain 2>/dev/null | sed 's/^/  /' \
            || warn "Slot B is still the 16MB placeholder (see docs/ab-boot.md)"
    fi

    # A trial boot that failed and was rolled back (rq_health_check.py, R-054),
    # in the words System Info and the taskbar indicator use (#242)
    if [ -f "${BOOT_COMMON_DIR}/last-switch-failed" ]; then
        echo ""
        warn "$("${SCRIPT_DIR}/rq_slot_status.sh" failure-notice 2>/dev/null || echo "The last update or switch didn't work.")"
        sed -n 's/^reason=/    Reason: /p; s/^time=/    When: /p' "${BOOT_COMMON_DIR}/last-switch-failed" >&2
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
    #   card_mode  dual | dual-pending | single | single-pending  (rq_expand_ab.sh
    #              mode): single = one system on a card under 64GB (R-006)
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
    local card_mode=""
    [ -x "${SCRIPT_DIR}/rq_expand_ab.sh" ] && card_mode=$("${SCRIPT_DIR}/rq_expand_ab.sh" mode 2>/dev/null || true)
    echo "card_mode=${card_mode:-unknown}"
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

    # The update written into this slot (rq_update_slot.sh) has started well:
    # a later failed switch to it is a switch, not an update
    rm -f "${BOOT_COMMON_DIR}/slot-${current_slot}-updated"

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

    # When the switch was asked for, by this slot's clock: it is set (NTP),
    # the trial slot's is often not yet when its health check runs - there is
    # no RTC, and fake-hwclock starts it at that slot's last shutdown, which
    # can be hours or weeks ago. A failed trial is dated by this (time= in
    # last-switch-failed, rq_health_check.py). rq_update_slot.sh comes here
    # too, right before its restart.
    local requested_epoch requested_time
    read -r requested_epoch requested_time <<< "$(date '+%s %Y-%m-%d %H:%M:%S')"
    printf 'slot=%s\ntime=%s\nepoch=%s\n' "$target_slot" "$requested_time" "$requested_epoch" \
        > "${BOOT_COMMON_DIR}/switch-requested" \
        || warn "Could not write ${BOOT_COMMON_DIR}/switch-requested"

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
        info "(or: sudo raspi-config -> 0 RasQberry -> Software & Image Updates -> Slot Manager -> Switch to Slot ${target_slot})"
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

cmd_plan_update() {
    # plan-update <release-tag>: where an update goes and what the guard says,
    # as key=value lines (RQB2_menu.sh and rq_update_slot.sh use them):
    #   target=A|B                       the slot that is not running
    #   running=A|B
    #   target_holds=<stream> <version>  stream: dev|beta|stable|unknown|none;
    #   running_holds=<stream> <version> version, or empty|unfinished|system
    #   new=<stream> <release-tag>
    #   downgrade=none|stream|older
    #   last_safe_slot=yes|no
    #   advice=<one line for the user>
    [ $# -eq 1 ] && [ -n "$1" ] || die "Usage: $(basename "$0") plan-update <release-tag>"
    local tag="$1" current target t_content r_content t_stream r_stream n_stream
    local downgrade=none last_safe=no advice

    current=$(get_current_slot)
    case "$current" in
        A|B) ;;
        *) die "This card has no A/B layout, so there is no other slot to install into" ;;
    esac
    target=$(get_other_slot "$current")
    t_content=$(slot_content "$target")
    r_content=$(slot_content "$current")
    [ "$t_content" != "UNKNOWN" ] || die "Cannot check what Slot ${target} holds: run this as root"
    t_stream=$(content_stream "$t_content")
    r_stream=$(content_stream "$r_content")
    n_stream=$(version_stream "$tag")

    case "$t_stream" in
        none|unknown) ;;
        *)
            if [ "$(stream_rank "$n_stream")" -lt "$(stream_rank "$t_stream")" ]; then
                downgrade=stream
            elif [ "$n_stream" = "$t_stream" ] && is_safe_stream "$n_stream" \
                && version_older "$tag" "$t_content"; then
                downgrade=older
            fi ;;
    esac
    if is_safe_stream "$t_stream" && ! is_safe_stream "$r_stream"; then
        last_safe=yes
    fi

    if [ "$last_safe" = "yes" ]; then
        advice="Slot ${target} holds the only beta or stable system on this card. Safer: switch to Slot ${target} first, then install into Slot ${current}."
    elif [ "$downgrade" = "stream" ]; then
        advice="Slot ${target} holds a $(stream_noun "$t_stream") (${t_content}); ${tag} is a $(stream_noun "$n_stream"), so this is a downgrade."
    elif [ "$downgrade" = "older" ]; then
        advice="${tag} is older than ${t_content} in Slot ${target}, so this is a downgrade."
    elif [ "$t_stream" = "none" ]; then
        advice="Slot ${target} holds no system yet. Slot ${current} stays as it is."
    else
        advice="Slot ${target} is replaced. Slot ${current} stays as it is, to go back to."
    fi

    echo "target=${target}"
    echo "running=${current}"
    echo "target_holds=$(holds_text "$t_content")"
    echo "running_holds=$(holds_text "$r_content")"
    echo "new=${n_stream} ${tag}"
    echo "downgrade=${downgrade}"
    echo "last_safe_slot=${last_safe}"
    echo "advice=${advice}"
}

# ============================================================================
# Main
# ============================================================================

usage() {
    cat << EOF
Usage: $(basename "$0") <command> [options]

Updates go into the slot that is not running (rq_update_slot.sh). A good trial
start makes it the start slot; the other slot stays as the way back.

Commands:
    status                          Show current slot, boot status, slot contents
    summary                         The same as key=value lines (for scripts)
    slot-content {A|B}              What a slot holds: version, EMPTY, INCOMPLETE, ...
    plan-update <release-tag>       Where an update would go, and its warnings
                                    (key=value: target, downgrade, last_safe_slot, ...)
    confirm                         Confirm current slot (prevent rollback)
    switch-to {A|B} [--reboot] [--force]
                                    Boot specific slot on next reboot
    switch                          Switch to other slot (deprecated)
    rollback [--force]              Make the other slot the default (permanent)

switch-to and rollback refuse a slot that holds no system (exit code $RC_SLOT_EMPTY);
--force skips that check.

Examples:
    # Check status
    sudo $(basename "$0") status

    # Confirm current boot (prevent rollback)
    sudo $(basename "$0") confirm

    # Try Slot B on its next start (trial start)
    sudo $(basename "$0") switch-to B
    sudo reboot '0 tryboot'

    # Switch and reboot in one command
    sudo $(basename "$0") switch-to B --reboot

    # What installing a release would do
    sudo $(basename "$0") plan-update beta-2026-10-03-095636

EOF
    exit 1
}

main() {
    if [ $# -lt 1 ]; then
        usage
    fi
    # --help prints the usage (it was "Unknown command: --help", R-107)
    case "$1" in -h|--help|help) usage 2>&1; exit 0 ;; esac

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
        plan-update)
            cmd_plan_update "$@"
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
