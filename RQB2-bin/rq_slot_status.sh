#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: slot status for the taskbar indicator (#242)
# ============================================================================
# Description: Two helpers around the A/B slots that the desktop indicator
#   (rq_slot_indicator.py), System Info, the slot manager and the login
#   message share.
#
#   write           (root) Writes /run/rasqberry/slot-status: the output of
#                   `rq_slot_manager.sh summary` plus the running version, the
#                   other slot's version and each slot's stream (dev, beta,
#                   stable, unknown: rq_release_channel). As root the summary can look into the other slot,
#                   which the desktop user cannot. Key=value lines, world-
#                   readable, replaced in one step (rename). The health check
#                   runs it at every start; /run is empty after a restart.
#                   It is a snapshot: switch, confirm and rollback change
#                   files on /boot/config, which the indicator reads live.
#   failure-notice  The one sentence about a failed update or switch, if
#                   /boot/config/last-switch-failed is there:
#                   "The update of Slot B to <version> didn't work, so Slot A
#                   (<version>) is running again." when an update had written
#                   Slot B (update=yes in the notice, from the slot-B-updated
#                   hint rq_update_slot.sh leaves; a notice without update= is
#                   from an older health check and counts as an update), else
#                   "Switching to Slot B didn't work, so Slot A (<version>) is
#                   running again." Prints nothing without a notice. Quick:
#                   never mounts anything. rq_slot_indicator.py words it the
#                   same way (failure_text).
#
# Usage: rq_slot_status.sh write | failure-notice
# Environment (tests): RQ_SLOT_STATUS_FILE, RQ_BOOT_COMMON_DIR, RQ_VERSION_FILE,
#   RQ_SLOT_MANAGER

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

STATUS_FILE="${RQ_SLOT_STATUS_FILE:-/run/rasqberry/slot-status}"
CONFIG_DIR="${RQ_BOOT_COMMON_DIR:-/boot/config}"
VERSION_FILE="${RQ_VERSION_FILE:-/etc/rasqberry-version}"
MANAGER="${RQ_SLOT_MANAGER:-${SCRIPT_DIR}/rq_slot_manager.sh}"

# Value of <key> in key=value <text>
kv_of() {
    printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n 1
}

# Value of <key> in a key=value file ('' if there is none)
kv_file() {
    [ -r "$1" ] || return 0
    sed -n "s/^$2=//p" "$1" 2>/dev/null | head -n 1 || true
}

# Stream of what a slot holds, '' when it holds no version
stream_of() {
    case "$1" in
        ""|EMPTY|INCOMPLETE|UNKNOWN|SYSTEM) echo "" ;;
        *) rq_release_channel "$1" ;;
    esac
}

other_of() {
    case "$1" in A) echo B ;; B) echo A ;; *) echo "" ;; esac
}

lower() {
    echo "$1" | tr 'AB' 'ab'
}

running_version() {
    head -n 1 "$VERSION_FILE" 2>/dev/null | tr -d '[:space:]' || true
}

# The running slot from the root partition (p5 = A, p6 = B)
running_slot() {
    case "$(findmnt / -o source -n 2>/dev/null || true)" in
        *p5|*5) echo A ;;
        *p6|*6) echo B ;;
        *) echo "" ;;
    esac
}

cmd_write() {
    local summary layout version current other dir tmp
    summary=$("$MANAGER" summary 2>/dev/null) || summary=""
    layout=$(kv_of "$summary" layout)
    [ -n "$layout" ] || die "rq_slot_manager.sh summary gave no answer"
    version=$(running_version)
    dir=$(dirname "$STATUS_FILE")
    mkdir -p "$dir" || die "Cannot create $dir"
    tmp=$(mktemp "$dir/.slot-status.XXXXXX") || die "Cannot write in $dir"
    {
        echo "# RasQberry slot status (#242): rq_slot_status.sh write, $(date -Iseconds)"
        echo "# A snapshot: target-slot, slot-confirmed and autoboot.txt on /boot/config win."
        printf '%s\n' "$summary"
        echo "version=${version}"
        echo "stream=$(stream_of "$version")"
        if [ "$layout" = "ab" ]; then
            current=$(kv_of "$summary" current)
            other=$(other_of "$current")
            echo "other=${other}"
            [ -n "$other" ] && echo "other_version=$(kv_of "$summary" "slot_$(lower "$other")")"
            echo "stream_a=$(stream_of "$(kv_of "$summary" slot_a)")"
            echo "stream_b=$(stream_of "$(kv_of "$summary" slot_b)")"
        else
            echo "card_mode=standard"
        fi
    } > "$tmp" || { rm -f "$tmp"; die "Cannot write $tmp"; }
    chmod 644 "$tmp"
    mv -f "$tmp" "$STATUS_FILE"
}

cmd_failure_notice() {
    local file="${CONFIG_DIR}/last-switch-failed" failed reason new current version head update
    [ -f "$file" ] || return 0
    failed=$(kv_file "$file" slot)
    reason=$(kv_file "$file" reason)
    new=$(kv_file "$file" version)
    version=$(running_version)
    current=$(kv_file "$STATUS_FILE" current)
    case "$current" in A|B) ;; *) current=$(running_slot) ;; esac
    case "$failed" in A|B) ;; *) failed=$(other_of "$current"); failed=${failed:-B} ;; esac
    case "$current" in A|B) ;; *) current=$(other_of "$failed") ;; esac
    # The failed version: from the notice, else what that slot holds now
    if [ -z "$new" ]; then
        if [ "$failed" = "$current" ]; then
            new="$version"
        elif [ ! -f "${CONFIG_DIR}/slot-${failed}-incomplete" ]; then
            new=$(kv_file "$STATUS_FILE" "slot_$(lower "$failed")")
        fi
        case "$new" in EMPTY|INCOMPLETE|UNKNOWN|SYSTEM) new="" ;; esac
    fi
    update=$(kv_file "$file" update)
    if [ "$update" = "no" ]; then
        head="Switching to Slot ${failed}"
    else
        head="The update of Slot ${failed}${new:+ to $new}"
    fi
    if [ "$failed" = "$current" ]; then
        if [ -n "$reason" ]; then
            echo "${head} didn't work: ${reason}."
        else
            echo "${head} didn't work."
        fi
    else
        echo "${head} didn't work, so Slot ${current}${version:+ ($version)} is running again."
    fi
}

case "${1:-}" in
    write)          cmd_write ;;
    failure-notice) cmd_failure_notice ;;
    -h|--help)      sed -n '/^# Description:/,/^# Environment/p' "$0" | sed 's/^# \{0,1\}//' ;;
    *)              echo "Usage: $(basename "$0") write | failure-notice" >&2; exit 1 ;;
esac
