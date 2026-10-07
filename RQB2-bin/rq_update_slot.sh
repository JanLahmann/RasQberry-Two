#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Updater
# ============================================================================
# Description: Download a RasQberry A/B image and install it into the other slot
# Usage: rq_update_slot.sh <download_url> <release_tag> [--slot A|B] [--sha256 SUM]
#                          [--allow-unverified] [--allow-downgrade]
#                          [--force-replace-safe-slot]
#        rq_update_slot.sh --preflight [--slot A|B]
#
# Update model (ping-pong, Jan 2026-10-04): an update always goes into the
# slot that is NOT running, A or B alike (--slot can only name that slot).
#   1. Downloads the new image (.img.xz) to /var/tmp/rasqberry-updates
#   2. Checks its SHA256 and that its partitions fit the other slot
#   3. Unpacks it straight into the other slot (R-052: rq_stream_image.py,
#      one pass, no unpacked copy on the running system) and checks the
#      SHA256 of the unpacked image
#   4. Takes over this system's settings and restarts into it on trial (tryboot)
# The health check confirms a good start, which makes the new slot the start
# slot; otherwise the Pi goes back to the slot that was running. The old slot
# stays as the way back (rq_slot_manager.sh switch-to / rollback).
#
# Jan's guard: at least one slot keeps a beta or stable system.
# rq_slot_manager.sh plan-update says what an update would replace. Installing
# a lower release channel, or an older beta/stable release, than the slot
# holds is a downgrade; replacing the only beta/stable system on the card
# (the running slot holds none) is the last safe slot. In a terminal the
# script asks (y/N for a downgrade, a typed REPLACE for the last safe slot);
# without one it refuses unless --allow-downgrade / --force-replace-safe-slot
# say so. The menu asks in its own dialogs and passes these options.
#
# --preflight runs only the checks that can refuse an update (target slot is
# the running system, target not expanded, too little free space, another
# update running, running slot still on trial), without downloading anything.
# The menu calls it BEFORE its release picker, so a user is not walked through
# four dialogs to an error. The release is not known yet, so it asks for 3.0 GB
# free (a 2.5 GB download plus 0.5 GB); the update itself asks for the size of
# its download plus 0.5 GB.
# Exit codes (also used when a real update is refused):
#   0  the target slot can be updated
#   1  any other error
#   20 the target slot is the system that is running now
#   21 the target slot is not set up (the 16MB placeholder): the card is not
#      prepared yet, or runs one system (single-system mode, rq_expand_ab.sh)
#   22 not enough free space for the download (the .img.xz plus 0.5 GB)
#   23 this card has no A/B layout
#   24 another update is already running
#   25 no SHA256 for the image, so it cannot be verified (only installed with
#      --allow-unverified)
#   26 a downgrade (lower release channel, or an older beta/stable release)
#      that was not confirmed (--allow-downgrade)
#   27 the target holds the card's only beta or stable system, and replacing
#      it was not confirmed (--force-replace-safe-slot)
#   28 the running slot is still on trial, or the next restart starts the
#      other slot: restart or wait first
#
# The image is always checked against a SHA256 before anything is written:
# --sha256 (the menu passes the one its release list shows), else
# ab_image_sha256 from RQB-releases.json (newest release of each stream), else
# the digest GitHub keeps for every release asset, else <url>.sha256. Older
# releases used to install unchecked (H-34). The unpacked image is checked
# too, against ab_extract_sha256 when RQB-releases.json has it: its SHA256 is
# computed while it is written, so a mismatch leaves the slot marked
# incomplete (below) and nothing is switched.
#
# While a slot is being written, ${BOOT_COMMON_DIR}/slot-<X>-incomplete exists;
# rq_slot_manager.sh refuses to switch or roll back to a slot marked like that.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Configuration (RQ_* overrides are for tests)
DOWNLOAD_DIR="${RQ_UPDATE_DIR:-/var/tmp/rasqberry-updates}"
SLOT_MANAGER="/usr/bin/rq_slot_manager.sh"
LOG_FILE="${RQ_UPDATE_LOG:-/var/log/rasqberry-update-slot.log}"
LOCK_FILE="${RQ_UPDATE_LOCK:-/run/lock/rasqberry-update-slot.lock}"
BOOT_COMMON_DIR="${RQ_BOOT_COMMON_DIR:-/boot/config}"
# Free space in DOWNLOAD_DIR: the download plus a margin. The image is
# unpacked straight into the target slot (R-052), so only the .img.xz is
# staged here, not the ~12 GB unpacked image (which needed 15 GB free).
SPACE_MARGIN_BYTES=500000000        # 0.5 GB to spare while the update runs
DEFAULT_DOWNLOAD_BYTES=2500000000   # when the size is not known (--preflight); the -ab.img.xz is about 1.7-2.1 GB

RC_TARGET_RUNNING=20
RC_NOT_EXPANDED=21
RC_NO_SPACE=22
RC_NOT_AB=23
RC_BUSY=24
RC_UNVERIFIED=25
RC_DOWNGRADE=26
RC_LAST_SAFE_SLOT=27
RC_NOT_SETTLED=28

# Release manifest that carries per-release checksums (extract_sha256 = SHA256 of
# the DECOMPRESSED .img). Used to verify integrity when no explicit --sha256 is
# passed. Overridable via RQB_RELEASES_URL for testing/mirrors.
RELEASES_MANIFEST_URL="${RQB_RELEASES_URL:-https://rasqberry.org/RQB-releases.json}"

# Set while an update runs, so the EXIT trap can clean up after a failure or
# an interrupt (closed terminal, Ctrl+C, dropped SSH session)
WORK_DIR=""
IMAGE_FILE=""
INCOMPLETE_SLOT=""

# ============================================================================
# Helper Functions
# ============================================================================

# rq_common.sh's die, plus a line in the log: the menu runs this script in
# the user's terminal, and the log is what is left after the screen scrolls.
die() {
    echo "ERROR: $*" >&2
    log_only "ERROR: $*"
    exit 1
}

# Like die, with one of the RC_* exit codes the menu understands
refuse() {
    local rc="$1"; shift
    echo "ERROR: $*" >&2
    log_only "REFUSED ($rc): $*"
    exit "$rc"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "ERROR: $(basename "$0") needs root: run it with sudo." >&2
        exit 1
    fi
}

# A timestamped line in the log only. The redirection of stderr comes first:
# written the other way round, a run without root printed "Permission
# denied" for the log before its own message (item 24).
log_only() {
    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; } 2>/dev/null || true
}

# The screen gets the plain text, the log the timestamped line (H-34: the
# progress screen was the raw log)
log_message() {
    echo "$1"
    log_only "$1"
}

is_terminal() {
    # Check if stdout is connected to a terminal
    # Returns 0 (true) if terminal, 1 (false) otherwise
    [ -t 1 ]
}

get_target_slot() {
    # Check a --slot value (A or B); the preflight refuses the running slot
    local requested_slot="${1:-}"

    case "$requested_slot" in
        A|B)
            echo "$requested_slot"
            ;;
        *)
            die "Invalid slot: $requested_slot (must be A or B)"
            ;;
    esac
}

other_slot() {
    if [ "$1" = "A" ]; then echo "B"; else echo "A"; fi
}

default_target_slot() {
    # The slot that is not running (ping-pong); B when the running slot is
    # not one of the two (no A/B layout: resolve_target_partitions refuses)
    local root
    root=$(findmnt / -o source -n 2>/dev/null || true)
    if [ -n "$root" ] && [ "$root" = "$(get_ab_system_partition A 2>/dev/null)" ]; then
        echo "B"
    elif [ -n "$root" ] && [ "$root" = "$(get_ab_system_partition B 2>/dev/null)" ]; then
        echo "A"
    else
        echo "B"
    fi
}

# Slot -> partition resolution comes from rq_common.sh:
# get_ab_system_partition / get_ab_boot_partition (label-based, issue #229)

acquire_lock() {
    # One update at a time. The lock is held until this process (or the slot
    # manager it execs into for the reboot) exits.
    command -v flock >/dev/null 2>&1 || return 0
    mkdir -p "$(dirname "$LOCK_FILE")"
    exec 9>"$LOCK_FILE"
    flock -n 9 || refuse "$RC_BUSY" "Another update is already running. Wait until it has finished."
}

remove_stale_downloads() {
    # A run that was killed (closed terminal, power cut) leaves its download
    # (and mount points) behind, and the next attempt then fails the
    # free-space check for no visible reason. Called under the lock, so
    # nothing here belongs to a running update.
    [ -d "$DOWNLOAD_DIR" ] || return 0
    local mnt
    for mnt in $(findmnt -rn -o TARGET 2>/dev/null | grep "^${DOWNLOAD_DIR}/" | sort -r); do
        umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
    done
    if findmnt -rn -o TARGET 2>/dev/null | grep -q "^${DOWNLOAD_DIR}/"; then
        warn "Leftovers of an earlier update in $DOWNLOAD_DIR are still mounted - not removing them"
        return 0
    fi
    if compgen -G "$DOWNLOAD_DIR/extract-*" >/dev/null || compgen -G "$DOWNLOAD_DIR/rasqberry-*.img.xz" >/dev/null; then
        log_message "Removing leftovers of an earlier, unfinished update in $DOWNLOAD_DIR"
        rm -rf "$DOWNLOAD_DIR"/extract-* "$DOWNLOAD_DIR"/rasqberry-*.img.xz
    fi
}

preflight_checks() {
    # Safety checks before any destructive action. Each refusal has its own
    # exit code (see the header) so the menu can explain what to do.
    # <download_bytes>: the size of the .img.xz, when known
    local target_slot="$1" system_partition="$2" boot_partition="$3" download_bytes="${4:-}"

    # Never flash the slot we are running from: updates go into the other one
    local current_root running
    running=$(other_slot "$target_slot")
    current_root=$(findmnt / -o source -n)
    if [ "$current_root" = "$system_partition" ]; then
        refuse "$RC_TARGET_RUNNING" "Slot $target_slot is the system you are running now, so it cannot be overwritten.
Updates go into the other system, Slot $running: leave out --slot, or use --slot $running."
    fi
    local current_boot
    current_boot=$(findmnt /boot/firmware -o source -n 2>/dev/null || echo "")
    if [ -n "$current_boot" ] && [ "$current_boot" = "$boot_partition" ]; then
        refuse "$RC_TARGET_RUNNING" "Slot $target_slot: $boot_partition is the active boot partition, so it cannot be overwritten."
    fi

    # The running slot must be settled: on trial, the target is the way back
    running_slot_settled "$running" "$target_slot"

    # Target partition must be expanded (factory Slot B is a 16MB placeholder)
    local part_size
    part_size=$(blockdev --getsize64 "$system_partition" 2>/dev/null || echo 0)
    if [ "$part_size" -lt 4294967296 ]; then  # < 4GB cannot hold any image
        # Say why, for this card (R-006): not prepared yet, or a small card
        # running one system (single-system mode) - not "expand first" on a
        # card where expanding is impossible. rq_expand_ab.sh knows which;
        # the exit code stays RC_NOT_EXPANDED, so the menu can explain it.
        local card_mode why=""
        card_mode=$("${SCRIPT_DIR}/rq_expand_ab.sh" mode 2>/dev/null || true)
        case "$card_mode" in
            dual-pending|single|single-pending)
                why=$("${SCRIPT_DIR}/rq_expand_ab.sh" explain --update 2>/dev/null || true) ;;
        esac
        # rq_expand_ab.sh says it for this card; repeating "no second
        # system" above it, with the placeholder's size, only confused (item 24)
        [ -n "$why" ] || why="Slot $target_slot is not set up yet, so there is nowhere to install an update.
Prepare the card first (two systems need a card of 64 GB or more):
sudo raspi-config -> 0 RasQberry -> Software & Image Updates -> Prepare the card for A/B updates"
        log_only "Slot $target_slot partition is $((part_size / 1024 / 1024)) MiB (not set up)"
        refuse "$RC_NOT_EXPANDED" "$why"
    fi

    # Enough free space for the download in DOWNLOAD_DIR
    check_free_space "$download_bytes"
}

required_free_kb() {
    # KB that must be free in DOWNLOAD_DIR: the .img.xz (<bytes>, else
    # DEFAULT_DOWNLOAD_BYTES) plus SPACE_MARGIN_BYTES
    local bytes="${1:-}"
    case "$bytes" in
        ""|0|*[!0-9]*) bytes=$DEFAULT_DOWNLOAD_BYTES ;;
    esac
    echo $(( (bytes + SPACE_MARGIN_BYTES + 1023) / 1024 ))
}

kb_as_gb() {
    awk -v k="${1:-0}" 'BEGIN { printf "%.1f GB", k * 1024 / 1000000000 }'
}

check_free_space() {
    # Refuse (RC_NO_SPACE) unless the download of <bytes> (empty: not known)
    # fits into DOWNLOAD_DIR with the margin to spare
    local need_kb avail_kb
    need_kb=$(required_free_kb "${1:-}")
    avail_kb=$(df --output=avail "$DOWNLOAD_DIR" | tail -1 | tr -d ' ')
    if [ "${avail_kb:-0}" -lt "$need_kb" ]; then
        refuse "$RC_NO_SPACE" "Not enough free space for the update: $(kb_as_gb "$avail_kb") free, $(kb_as_gb "$need_kb") needed
(the download plus 0.5 GB to spare, in $DOWNLOAD_DIR).
Delete Docker demo images or large files you no longer need, then try again."
    fi
    log_only "Free space: $avail_kb KB, $need_kb KB needed"
}

running_slot_settled() {
    # Refuse (RC_NOT_SETTLED) while <running> is on trial - the health check
    # has not confirmed it yet, and <target> is the way back - or while the
    # next restart would start <target> (a rollback waiting for its restart).
    # Overwriting the target then could leave the Pi without a working system.
    local running="$1" target="$2" autoboot="${BOOT_COMMON_DIR}/autoboot.txt" pending="" default=""
    [ -f "$autoboot" ] || return 0
    # braces: a missing file is normal, and its redirect error must not reach the screen
    pending=$( { tr -d '[:space:]' < "${BOOT_COMMON_DIR}/target-slot"; } 2>/dev/null || true)
    case "$(awk '/^\[/ { sec = $0 } sec == "[all]" && /^boot_partition=/ { sub(/^boot_partition=/, ""); print; exit }' "$autoboot" 2>/dev/null)" in
        2) default="A" ;;
        3) default="B" ;;
    esac
    if [ ! -f "${BOOT_COMMON_DIR}/slot-confirmed" ] && [ "$pending" = "$running" ]; then
        refuse "$RC_NOT_SETTLED" "Slot $running, the system you are running, is still on trial: the health check makes it the start slot a few minutes after a good start. Until then Slot $target is the way back, so it is not overwritten. Try again in a few minutes."
    fi
    if [ -n "$default" ] && [ "$default" != "$running" ]; then
        refuse "$RC_NOT_SETTLED" "The next restart starts Slot $default, not Slot $running that is running now. Restart first, then install the update."
    fi
}

verify_checksum() {
    # Check <image_file> against <expected> SHA256 (resolve_image_sha256 found
    # it before the download). Empty only with --allow-unverified.
    local image_file="$1" expected="${2:-}"
    if [ -z "$expected" ]; then
        warn "No SHA256 for this image (--allow-unverified): not checked"
        log_only "WARNING: image installed without checksum verification"
        return 0
    fi
    local actual
    actual=$(sha256sum "$image_file" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        rm -f "$image_file"
        die "The download is damaged or not the published image (SHA256 does not match: expected $expected, got $actual). Nothing was written; try again."
    fi
    log_only "Checksum OK: $actual"
}

fetch_github_asset() {
    # <field> of a release asset as GitHub lists it, for
    # https://github.com/<owner>/<repo>/releases/download/<tag>/<file>:
    # "digest" (the SHA256 GitHub keeps, "sha256:..." without the prefix) or
    # "size" (bytes). Prints nothing when the URL is not like that or GitHub
    # has none.
    local url="$1" field="$2" path owner repo tag name
    case "$url" in
        https://github.com/*/*/releases/download/*/*) ;;
        *) return 0 ;;
    esac
    path=${url#https://github.com/}
    owner=${path%%/*}; path=${path#*/}
    repo=${path%%/*}; path=${path#*/releases/download/}
    tag=${path%%/*}; name=${path#*/}
    curl -sSLf --max-time 30 -H "Accept: application/vnd.github+json" \
        "${RQ_GITHUB_API:-https://api.github.com}/repos/${owner}/${repo}/releases/tags/${tag}" 2>/dev/null \
        | python3 -c '
import json, sys
name, field = sys.argv[1], sys.argv[2]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for a in data.get("assets") or []:
    if a.get("name") != name:
        continue
    value = a.get(field)
    if field == "digest" and isinstance(value, str) and value.startswith("sha256:"):
        print(value[7:])
    elif field == "size" and isinstance(value, int) and value > 0:
        print(value)
    break
' "$name" "$field" 2>/dev/null || true
}

resolve_image_sha256() {
    # The expected SHA256 of <url>'s .img.xz (see the header for the order);
    # prints nothing when there is none
    local url="$1" tag="$2" sum=""
    if [ -n "$SHA256_SUM" ]; then
        echo "$SHA256_SUM"
        return 0
    fi
    sum=$(fetch_release_field "$tag" "$(sha_field_for "$url" image)")
    [ -n "$sum" ] || sum=$(fetch_github_asset "$url" digest)
    [ -n "$sum" ] || sum=$(curl -sSLf --max-time 30 "${url}.sha256" 2>/dev/null | awk '{print $1}' || true)
    case "$sum" in
        *[!0-9a-fA-F]*|"") sum="" ;;
    esac
    [ "${#sum}" -eq 64 ] || sum=""
    echo "$sum" | tr '[:upper:]' '[:lower:]'
}

fetch_release_field() {
    # Look up a field for a release tag in the release manifest
    # (RQB-releases.json). $2 = field: image_sha256 / ab_image_sha256 (the
    # COMPRESSED .img.xz), extract_sha256 / ab_extract_sha256 (the
    # DECOMPRESSED .img) or image_download_size / ab_image_download_size.
    # Prints the value (empty if the manifest is unreachable, the field is
    # absent, or the tag is not a current stream head - so older tags / older
    # manifests fall through to the next source, not an error).
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

sha_field_for() {
    # Manifest field holding the checksum of <url>'s image: the -ab image (the
    # only one a slot can take) has its own ab_* fields. <kind> is "image"
    # (the .img.xz) or "extract" (the unpacked .img). Using the standard
    # image's field for an -ab download aborted every OTA with a false
    # "corrupted or tampered" error.
    local url="$1" kind="$2"
    case "$url" in
        *-ab.img.xz|*-ab.img) echo "ab_${kind}_sha256" ;;
        *) echo "${kind}_sha256" ;;
    esac
}

size_field_for() {
    # Manifest field holding the download size of <url>'s image (see sha_field_for)
    case "$1" in
        *-ab.img.xz) echo "ab_image_download_size" ;;
        *) echo "image_download_size" ;;
    esac
}

resolve_download_size() {
    # Size in bytes of <url>'s .img.xz: RQB-releases.json (newest release of
    # each stream), else GitHub's asset list; empty when neither has it (the
    # free-space check then assumes DEFAULT_DOWNLOAD_BYTES)
    local url="$1" tag="$2" size=""
    size=$(fetch_release_field "$tag" "$(size_field_for "$url")")
    case "$size" in ""|0|*[!0-9]*) size=$(fetch_github_asset "$url" size) ;; esac
    case "$size" in ""|0|*[!0-9]*) size="" ;; esac
    echo "$size"
}

download_image() {
    # Download the image file
    local url="$1"
    local output_file="$2"

    log_only "Downloading image from: $url"
    log_only "Saving to: $output_file"

    # Use wget or curl - show progress bar when in terminal, quiet otherwise.
    # The progress goes to the screen only (stderr), not through tee into
    # the log: a pipe would turn wget's bar into thousands of log lines.
    if command -v wget >/dev/null 2>&1; then
        if is_terminal; then
            # -q --show-progress: the bar only, not the redirects to
            # GitHub's long signed download URLs
            if ! wget -q --show-progress --progress=bar:force -O "$output_file" "$url"; then
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
            if ! curl -fL --progress-bar -o "$output_file" "$url"; then
                die "Download failed"
            fi
        else
            # Silent for non-terminal
            if ! curl -fsSL -o "$output_file" "$url" 2>> "$LOG_FILE"; then
                die "Download failed"
            fi
        fi
    else
        die "Neither wget nor curl found"
    fi

    log_only "Download complete"
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

    log_only "Image file verified: $size bytes"
}

run_streamer() {
    # rq_stream_image.py <args> (R-052: unpacks the image straight into the
    # slot), with the running system's root and boot partitions as --forbid:
    # whatever it is asked, it never writes them - a second guard behind
    # preflight_checks. A mounted target is refused by the kernel too (O_EXCL).
    # Its stderr stays on the terminal: the progress line and its errors.
    local helper="${SCRIPT_DIR}/rq_stream_image.py" root_src boot_src
    [ -f "$helper" ] || helper=/usr/bin/rq_stream_image.py
    [ -f "$helper" ] || die "rq_stream_image.py is missing: the update cannot be written into the slot."
    root_src=$(findmnt / -o source -n 2>/dev/null || true)
    boot_src=$(findmnt /boot/firmware -o source -n 2>/dev/null || true)
    python3 "$helper" --log "$LOG_FILE" ${root_src:+--forbid "$root_src"} ${boot_src:+--forbid "$boot_src"} "$@"
}

probe_image() {
    # Step 2: does the image fit <slot>? rq_stream_image.py --probe reads the
    # partition table and the start of the boot and system partitions (about
    # 1.5 GB of the unpacked A/B image: seconds, not minutes) and writes
    # nothing. It runs before the slot is touched, as the old updater checked
    # the unpacked image before its first write.
    local image_file="$1" system_partition="$2" boot_partition="$3" slot="$4"
    if ! run_streamer "$image_file" --boot "$boot_partition" --root "$system_partition" --probe >/dev/null; then
        log_only "rq_stream_image.py --probe refused the image for Slot $slot"
        echo "Nothing was written: Slot $slot is unchanged." >&2
        exit 1
    fi
}

stream_into_slot() {
    # Step 3: unpack <image_file> straight into <boot_partition> and
    # <system_partition> of <slot> (R-052): one pass, no unpacked copy on the
    # running system. The SHA256 of the unpacked image is computed on the way
    # and compared with <expected_extract_sha> (when published) at the end.
    # From here on the slot is marked incomplete. Once writing began, a failure
    # leaves it marked, so it is never switched to, and nothing is switched.
    local image_file="$1" system_partition="$2" boot_partition="$3" slot="$4"
    local expected="${5:-}" tag="${6:-}" rc=0 was_incomplete=false
    [ -e "${BOOT_COMMON_DIR}/slot-${slot}-incomplete" ] && was_incomplete=true
    mark_slot_incomplete "$slot" "$tag"
    run_streamer "$image_file" --boot "$boot_partition" --root "$system_partition" \
        ${expected:+--extract-sha256 "$expected"} >/dev/null || rc=$?
    case "$rc" in
        0)
            # (no expected sum: the manifest only has it for the newest
            # release of each stream; the download itself was checked)
            if [ -n "$expected" ]; then
                echo "  Unpacked image checked: OK"
            fi
            ;;
        2|3)
            # Refused before the first byte was written: the slot is as it was
            [ "$was_incomplete" = true ] || clear_slot_incomplete "$slot"
            log_only "Nothing was written to Slot $slot (rq_stream_image.py exit $rc)"
            echo "Nothing was written to Slot $slot." >&2
            exit 1
            ;;
        *)
            # 4: stopped while writing, 5: the unpacked image's SHA256 does not
            # match. The slot stays marked incomplete (the EXIT trap says so).
            log_only "Writing Slot $slot stopped (rq_stream_image.py exit $rc)"
            exit 1
            ;;
    esac
}

unmount_target() {
    # Unmount every mount of <device>. The desktop automounts the inactive
    # slot (R-146); writing a mounted filesystem would corrupt it, so an
    # unmount that fails stops the update instead of being ignored.
    local dev="$1" mnt
    for mnt in $(findmnt -rn -o TARGET --source "$dev" 2>/dev/null); do
        log_only "Unmounting $dev from $mnt..."
        umount "$mnt" 2>> "$LOG_FILE" || true
    done
    mnt=$(findmnt -rn -o TARGET --source "$dev" 2>/dev/null | head -1 || true)
    if [ -n "$mnt" ]; then
        die "$dev is in use at $mnt and cannot be unmounted. Close any window or program that shows files there, then try again."
    fi
}

mark_slot_incomplete() {
    # From the first write on, the target slot holds no usable system until
    # the update has finished: say so where both slots can see it
    local slot="$1" tag="$2"
    INCOMPLETE_SLOT="$slot"
    rm -f "${BOOT_COMMON_DIR}/slot-${slot}-updated" 2>/dev/null || true
    if mkdir -p "$BOOT_COMMON_DIR" 2>/dev/null \
        && echo "$(date -Iseconds) $tag" > "${BOOT_COMMON_DIR}/slot-${slot}-incomplete" 2>/dev/null; then
        sync
    else
        warn "Could not write ${BOOT_COMMON_DIR}/slot-${slot}-incomplete"
    fi
}

mark_slot_updated() {
    # <slot> now holds a system this update wrote, not started yet. If its
    # first start fails, the health check records update=yes in
    # last-switch-failed: "The update of Slot X to <version> didn't work"
    # rather than "Switching to Slot X didn't work". rq_slot_manager.sh
    # confirm removes it after a good start; the next update rewrites it.
    local slot="$1" version="$2" tag="$3"
    printf 'version=%s\ntag=%s\ntime=%s\n' "$version" "$tag" "$(date '+%Y-%m-%d %H:%M:%S')" \
        > "${BOOT_COMMON_DIR}/slot-${slot}-updated" 2>/dev/null \
        || warn "Could not write ${BOOT_COMMON_DIR}/slot-${slot}-updated"
}

clear_slot_incomplete() {
    local slot="$1"
    rm -f "${BOOT_COMMON_DIR}/slot-${slot}-incomplete"
    INCOMPLETE_SLOT=""
    sync
}

refresh_slot_status() {
    # /run/rasqberry/slot-status says what each slot held at start-up: System
    # Info, the menu and the taskbar badge (which re-reads it when it changes)
    # showed the old contents of the updated slot until the next restart.
    # Write it again now that the slot holds the new system. Never fails the
    # update.
    local writer="${RQ_SLOT_STATUS:-${SCRIPT_DIR}/rq_slot_status.sh}" t=""
    [ -x "$writer" ] || return 0
    command -v timeout >/dev/null 2>&1 && t="timeout 60"
    $t "$writer" write >> "$LOG_FILE" 2>&1 || log_only "Could not refresh the slot status"
}

cleanup_on_exit() {
    # EXIT trap: after a failure or an interrupt, remove what this run left
    # behind. (A successful run ends in exec, which does not run this.)
    local rc=$?
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        local mnt
        for mnt in $(findmnt -rn -o TARGET 2>/dev/null | grep "^${WORK_DIR}/" | sort -r); do
            umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
        done
        if ! findmnt -rn -o TARGET 2>/dev/null | grep -q "^${WORK_DIR}/"; then
            rm -rf "$WORK_DIR"
        fi
    fi
    if [ "$rc" -ne 0 ] && [ -n "$IMAGE_FILE" ]; then
        rm -f "$IMAGE_FILE"
    fi
    if [ "$rc" -ne 0 ] && [ -n "$INCOMPLETE_SLOT" ]; then
        echo "Slot $INCOMPLETE_SLOT holds no usable system now: the update did not finish." >&2
        echo "The running system is unchanged. Install the update again to fill Slot $INCOMPLETE_SLOT." >&2
    fi
    if [ "$rc" -ne 0 ]; then
        log_only "Update stopped (exit code $rc)"
    fi
}

write_image_to_slot() {
    # Write the image into the target slot (boot and system partitions), then
    # make it this slot's system: label, cmdline.txt, fstab, settings
    local image_file="$1"
    local system_partition="$2"
    local boot_partition="$3"
    local target_slot="$4"
    local expected_extract_sha="${5:-}"
    local release_tag="${6:-}"

    log_only "Installing image to Slot $target_slot"
    log_only "  System partition: $system_partition"
    log_only "  Boot partition: $boot_partition"

    # Mount points (removed by the EXIT trap on any failure)
    WORK_DIR="${DOWNLOAD_DIR}/extract-$$"
    local work_dir="$WORK_DIR"
    mkdir -p "$work_dir"

    # Neither target partition may stay mounted (e.g. by the desktop
    # automounter) while it is written
    unmount_target "$boot_partition"
    unmount_target "$system_partition"

    log_message "Step 3 of 4: unpacking the image into Slot $target_slot (do not switch the Pi off)..."
    stream_into_slot "$image_file" "$system_partition" "$boot_partition" "$target_slot" \
        "$expected_extract_sha" "$release_tag"

    # Written and checked: the download is not needed any more
    cleanup_download "$image_file"

    log_message "Step 4 of 4: checking the new system, taking over your settings, restarting into Slot $target_slot..."

    # The boot partition is the image's BOOT-A as it is: give it this slot's
    # label and a volume ID of its own (as mkfs.vfat did when the files were
    # copied). The label is not needed to start (the partition number is),
    # so a failure is a warning only.
    local boot_label="BOOT-${target_slot}"
    fatlabel "$boot_partition" "$boot_label" >> "$LOG_FILE" 2>&1 \
        || warn "Could not set the label of $boot_partition to $boot_label"
    fatlabel -i -r "$boot_partition" >> "$LOG_FILE" 2>&1 \
        || log_only "Could not give $boot_partition a new volume ID"

    # Update cmdline.txt for the target slot
    local tgt_boot_mount="${work_dir}/tgt_boot"
    mkdir -p "$tgt_boot_mount"
    mount "$boot_partition" "$tgt_boot_mount" || die "Failed to mount target boot partition"
    log_only "Updating cmdline.txt for Slot $target_slot..."
    if [ -f "$tgt_boot_mount/cmdline.txt" ]; then
        # Point root= at the target slot and drop a first-boot init= (not
        # needed for a slot update). Everything else stays as the image has
        # it: 'quiet splash' gives the RasQberry boot screen on release images,
        # and a dev image is built verbose anyway (R-142).
        sed -i "s|root=[^ ]*|root=${system_partition}|g" "$tgt_boot_mount/cmdline.txt"
        sed -i 's| init=[^ ]*||g' "$tgt_boot_mount/cmdline.txt"
        sed -i 's|^ *||g' "$tgt_boot_mount/cmdline.txt"
        # A kernel that cannot start must reboot (back to the working slot),
        # not hang (R-054). Images from the converter carry it; older ones not.
        grep -q 'panic=' "$tgt_boot_mount/cmdline.txt" || sed -i 's|$| panic=10|' "$tgt_boot_mount/cmdline.txt"
        log_only "cmdline.txt updated: root=${system_partition}"
    else
        warn "The new boot partition has no cmdline.txt"
    fi
    sync
    umount "$tgt_boot_mount"

    # Check the file system and grow it to the partition. Their output goes
    # to the log; the screen gets one line (H-34). e2fsck: 0 clean, 1 errors
    # corrected, 2 corrected (reboot advised), 4 and up not corrected.
    local fsck_rc=0
    e2fsck -f -y "$system_partition" >> "$LOG_FILE" 2>&1 || fsck_rc=$?
    case "$fsck_rc" in
        0) log_only "e2fsck: clean" ;;
        1|2|3) echo "  File system check: small errors corrected (details in $LOG_FILE)" ;;
        *) warn "File system check reported errors it could not correct (exit $fsck_rc, see $LOG_FILE)" ;;
    esac
    resize2fs "$system_partition" >> "$LOG_FILE" 2>&1 || warn "Could not resize filesystem"

    # Set correct label for the target slot
    local system_label="SYSTEM-${target_slot}"
    log_only "Setting filesystem label to ${system_label}..."
    e2label "$system_partition" "$system_label" >> "$LOG_FILE" 2>&1 || warn "Could not set filesystem label"

    # Mount and update fstab
    log_only "Updating fstab for Slot $target_slot..."
    local tgt_root_mount="${work_dir}/tgt_root"
    mkdir -p "$tgt_root_mount"

    mount "$system_partition" "$tgt_root_mount" || die "Failed to mount target root partition"

    # Update fstab for v3 AB layout
    if [ -f "$tgt_root_mount/etc/fstab" ]; then
        # CONFIG and DATA by the shared helper: mmcblk0p1 on an SD card,
        # sda1 on USB (the old "/dev/<disk>p1" was wrong there)
        local config_part data_part
        config_part=$(ab_partition_by_number 1)
        data_part=$(ab_partition_by_number 7)

        cat > "$tgt_root_mount/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
${config_part}              /boot/config    vfat    defaults          0   2
${boot_partition}           /boot/firmware  vfat    defaults          0   2
${system_partition}         /               ext4    defaults,noatime  0   1
${data_part}                /data           ext4    defaults,noatime,nofail  0   2
EOF
        log_only "fstab updated for Slot $target_slot"
    fi

    # Keep this device's SSH host key and authorized_keys in the new slot, so
    # ssh neither refuses the changed host key nor falls back to a password
    # (#275). A failure here must not fail the update.
    local carrier="${SCRIPT_DIR:-/usr/bin}/rq_carry_ssh_identity.sh"
    [ -x "$carrier" ] || carrier=/usr/bin/rq_carry_ssh_identity.sh
    if [ -x "$carrier" ]; then
        "$carrier" "$tgt_root_mount" >> "$LOG_FILE" 2>&1 || warn "Could not carry over the SSH identity"
    else
        warn "rq_carry_ssh_identity.sh not found - the new slot gets a new SSH host key"
    fi

    # Everything else that makes the Pi yours (Wi-Fi, password, hostname,
    # locale, ~/Shared, ~/.qiskit, ~/My-Quantum-Programs) is taken over by the
    # NEW system on its first start: rq_carry_over.sh boot, run by
    # rasqberry-carry-over.service, pulls from this slot (R-053). Images from
    # the converter carry the marker; set it for any image that has the
    # script, so the pull also happens when an image was built without it.
    if [ -x "$tgt_root_mount/usr/bin/rq_carry_over.sh" ]; then
        mkdir -p "$tgt_root_mount/var/lib/rasqberry"
        [ -e "$tgt_root_mount/var/lib/rasqberry/carry-over-pending" ] \
            || date -Iseconds > "$tgt_root_mount/var/lib/rasqberry/carry-over-pending"
        log_only "Slot $target_slot takes over this system's settings on its first start (rq_carry_over.sh)"
    else
        warn "The new system has no rq_carry_over.sh: Wi-Fi, password and hostname are not carried over"
    fi
    # A renamed user (#319): the new system takes the name over on its first
    # start (rq_carry_over.sh -> rq_user_rename.sh). A release from before
    # that keeps "rasqberry", with the image's default password.
    local me tgt_user
    me=$(getent passwd 1000 2>/dev/null | cut -d: -f1 || true)
    tgt_user=$(awk -F: '$3 == 1000 { print $1; exit }' "$tgt_root_mount/etc/passwd" 2>/dev/null || true)
    if [ -n "$me" ] && [ -n "$tgt_user" ] && [ "$me" != "$tgt_user" ] \
        && [ ! -x "$tgt_root_mount/usr/bin/rq_user_rename.sh" ]; then
        warn "The new system cannot use the user name '$me': it starts with the user '$tgt_user' and the published default password"
    fi

    local new_version
    new_version=$(head -1 "$tgt_root_mount/etc/rasqberry-version" 2>/dev/null | tr -d '[:space:]' || true)
    log_message "Slot $target_slot now holds: ${new_version:-a system without /etc/rasqberry-version}"

    # Unmount and cleanup
    sync
    umount "$tgt_root_mount"
    rm -rf "$work_dir"
    WORK_DIR=""

    mark_slot_updated "$target_slot" "${new_version:-$release_tag}" "$release_tag"
    clear_slot_incomplete "$target_slot"
    refresh_slot_status
    log_only "Image installation complete"
}

cleanup_download() {
    # Remove downloaded image file
    local image_file="$1"

    if [ -f "$image_file" ]; then
        log_only "Cleaning up downloaded file: $image_file"
        rm -f "$image_file" || warn "Could not remove downloaded file"
    fi
    IMAGE_FILE=""
}

configure_tryboot() {
    # Configure tryboot to the specified slot (no reboot)
    local target_slot="$1"

    log_only "Configuring tryboot to boot Slot $target_slot..."

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
    # Parse the optional arguments (after URL and tag, or after --preflight)
    TARGET_SLOT=$(default_target_slot)
    SHA256_SUM=""
    ALLOW_UNVERIFIED=false
    ALLOW_DOWNGRADE=false
    FORCE_REPLACE_SAFE=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --slot)
                TARGET_SLOT=$(get_target_slot "${2:-}")
                shift 2
                ;;
            --sha256)
                SHA256_SUM="$2"
                shift 2
                ;;
            --allow-downgrade)
                ALLOW_DOWNGRADE=true
                shift
                ;;
            --force-replace-safe-slot)
                FORCE_REPLACE_SAFE=true
                shift
                ;;
            --allow-unverified)
                ALLOW_UNVERIFIED=true
                shift
                ;;
            *)
                warn "Unknown parameter: $1"
                shift
                ;;
        esac
    done
}

# Value of <key> in plan-update output <plan>
plan_value() {
    printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n 1
}

ask_in_terminal() {
    [ -t 0 ] && [ -t 2 ]
}

enforce_update_guard() {
    # Jan's guard (see the header): rq_slot_manager.sh plan-update says what
    # installing <tag> would replace. Asks in a terminal; without one it
    # refuses unless --allow-downgrade / --force-replace-safe-slot say so.
    local tag="$1" planner plan target holds t_stream t_version r_holds r_stream r_version
    local n_stream downgrade last_safe msg answer
    planner="${SCRIPT_DIR}/rq_slot_manager.sh"
    [ -x "$planner" ] || planner="$SLOT_MANAGER"
    plan=$("${RQ_SLOT_PLANNER:-$planner}" plan-update "$tag" 2>&1) \
        || die "Could not check what the update would replace (rq_slot_manager.sh plan-update): $plan"
    log_only "plan-update: $(printf '%s' "$plan" | tr '\n' ';')"
    target=$(plan_value "$plan" target)
    [ "$target" = "$TARGET_SLOT" ] \
        || die "The update would go into Slot $TARGET_SLOT, but the other system is Slot ${target:-?}. Nothing was changed."
    holds=$(plan_value "$plan" target_holds)
    t_stream=${holds%% *}; t_version=${holds#* }
    r_holds=$(plan_value "$plan" running_holds)
    r_stream=${r_holds%% *}; r_version=${r_holds#* }
    n_stream=$(plan_value "$plan" new); n_stream=${n_stream%% *}
    downgrade=$(plan_value "$plan" downgrade)
    last_safe=$(plan_value "$plan" last_safe_slot)

    case "$downgrade" in
        stream) msg="Slot $target holds $t_version ($t_stream). $tag ($n_stream) comes from a less tested release channel, so installing it is a downgrade." ;;
        older)  msg="Slot $target holds $t_version ($t_stream). $tag is older, so installing it is a downgrade." ;;
        *)      msg="" ;;
    esac
    if [ -n "$msg" ] && [ "$ALLOW_DOWNGRADE" != true ]; then
        if ask_in_terminal; then
            warn "$msg"
            read -r -p "Install it anyway? [y/N] " answer
            case "$answer" in
                y|Y|yes|Yes|YES) log_only "Downgrade confirmed in the terminal" ;;
                *) refuse "$RC_DOWNGRADE" "Not installed: nothing was changed." ;;
            esac
        else
            refuse "$RC_DOWNGRADE" "$msg Nothing was changed. To install it anyway: --allow-downgrade."
        fi
    fi

    if [ "$last_safe" = "yes" ] && [ "$FORCE_REPLACE_SAFE" != true ]; then
        msg="Slot $target holds $t_version ($t_stream), the only beta or stable system on this card: Slot $(other_slot "$target"), running now, holds $r_version ($r_stream). If the update of Slot $target doesn't work, no beta or stable system is left to go back to.
Safer: switch to Slot $target first (sudo rq_slot_manager.sh switch-to $target --reboot), then install the update into Slot $(other_slot "$target")."
        if ask_in_terminal; then
            warn "$msg"
            read -r -p "Type REPLACE to overwrite Slot $target anyway: " answer
            if [ "$answer" = "REPLACE" ]; then
                log_only "Replacing the last beta or stable system confirmed in the terminal"
            else
                refuse "$RC_LAST_SAFE_SLOT" "Not installed: nothing was changed."
            fi
        else
            refuse "$RC_LAST_SAFE_SLOT" "$msg
Nothing was changed. To overwrite it anyway: --force-replace-safe-slot."
        fi
    fi
}

resolve_target_partitions() {
    # Sets SYSTEM_PARTITION / BOOT_PARTITION for TARGET_SLOT (shared
    # helpers from rq_common.sh); refuses on a card without A/B layout
    SYSTEM_PARTITION=$(get_ab_system_partition "$TARGET_SLOT")
    BOOT_PARTITION=$(get_ab_boot_partition "$TARGET_SLOT")
    if [ ! -b "$SYSTEM_PARTITION" ] || [ ! -b "$BOOT_PARTITION" ]; then
        refuse "$RC_NOT_AB" "This card has no Slot $TARGET_SLOT (expected $SYSTEM_PARTITION and $BOOT_PARTITION): it does not use the A/B layout. To move to a new release, write the new image to a card."
    fi
}

run_preflight() {
    # --preflight: only the checks, nothing is downloaded or written
    check_root
    parse_arguments "$@"
    resolve_target_partitions
    mkdir -p "$DOWNLOAD_DIR"
    acquire_lock
    remove_stale_downloads
    preflight_checks "$TARGET_SLOT" "$SYSTEM_PARTITION" "$BOOT_PARTITION"
    local avail_kb
    avail_kb=$(df --output=avail "$DOWNLOAD_DIR" | tail -1 | tr -d ' ')
    echo "Slot $TARGET_SLOT can be updated ($(kb_as_gb "$avail_kb") free for the download)."
}

usage() {
    cat << EOF
Usage: $0 <download_url> <release_tag> [--slot A|B] [--sha256 SUM] [--allow-unverified]
          [--allow-downgrade] [--force-replace-safe-slot]
       $0 --preflight [--slot A|B]

Installs an A/B image into the slot that is not running, then restarts into it
on trial. A good start makes it the start slot; the other slot stays as the
way back.

Arguments:
  download_url    URL of the A/B image (-ab.img.xz) to install
  release_tag     Release tag/version identifier

Options:
  --slot A|B      Target slot (default: the one not running; the running slot
                  is refused)
  --sha256 <sum>  Expected SHA256 of the .img.xz (else RQB-releases.json, GitHub's
                  asset digest, then <url>.sha256; without one the update is refused)
  --allow-unverified  Install an image no SHA256 can be found for (experts only)
  --allow-downgrade   Install a lower release channel, or an older beta/stable
                  release, than the target holds (else: asked, or exit 26)
  --force-replace-safe-slot  Overwrite the card's only beta or stable system
                  (else: a typed REPLACE, or exit 27)
  --preflight     Only check whether the slot can be updated (exit codes 20-24
                  and 28 explain why not); downloads nothing. Needs
                  $(kb_as_gb "$(required_free_kb)") free in $DOWNLOAD_DIR (the download
                  plus 0.5 GB; the image is unpacked straight into the slot)

Example:
  sudo $0 https://github.com/.../image-ab.img.xz beta-2025-10-25-123456

EOF
}

main() {
    case "${1:-}" in
        --preflight)
            shift
            run_preflight "$@"
            return 0
            ;;
        -h|--help)
            usage
            return 0
            ;;
    esac

    check_root

    if [ $# -lt 2 ]; then
        usage >&2
        exit 1
    fi

    local download_url="$1"
    local release_tag="$2"

    # Parse optional arguments
    shift 2
    parse_arguments "$@"

    log_only "=== RasQberry A/B Boot Slot Update ==="
    log_only "Download URL: $download_url"
    log_only "Release Tag: $release_tag"
    log_only "Target Slot: $TARGET_SLOT"

    # Determine target slot partitions
    resolve_target_partitions
    local system_partition="$SYSTEM_PARTITION"
    local boot_partition="$BOOT_PARTITION"
    log_only "Target system partition: $system_partition"
    log_only "Target boot partition: $boot_partition"

    # Create download directory, one update at a time, no leftovers
    mkdir -p "$DOWNLOAD_DIR"
    acquire_lock
    trap cleanup_on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    remove_stale_downloads

    # The size of the download, for the free-space check (only the .img.xz
    # is staged: the image is unpacked straight into the slot)
    local download_bytes
    download_bytes=$(resolve_download_size "$download_url" "$release_tag")
    log_only "Download size: ${download_bytes:-not known}"

    # Safety guards: never the booted slot, size and free-space prechecks
    preflight_checks "$TARGET_SLOT" "$system_partition" "$boot_partition" "$download_bytes"

    # Jan's guard: downgrades and the last beta or stable system (asks or refuses)
    enforce_update_guard "$release_tag"

    # The checksum is found BEFORE the download: an image that cannot be
    # verified is refused without fetching 2 GB first
    local image_sha
    image_sha=$(resolve_image_sha256 "$download_url" "$release_tag")
    if [ -z "$image_sha" ] && [ "$ALLOW_UNVERIFIED" != true ]; then
        refuse "$RC_UNVERIFIED" "No checksum (SHA256) is published for $release_tag, so the download could not be verified. Nothing was changed. Choose a newer release."
    fi
    log_only "Expected SHA256 of the image: ${image_sha:-none (--allow-unverified)}"

    # mount would print "your fstab has been modified" for every mount below
    # when the clock was behind at start-up (H-34)
    rq_refresh_fstab_view

    # Download image
    local image_file="${DOWNLOAD_DIR}/rasqberry-${release_tag}.img.xz"
    IMAGE_FILE="$image_file"

    if [ -f "$image_file" ]; then
        log_only "Image file already exists, removing old download"
        rm -f "$image_file"
    fi

    log_message "Step 1 of 4: downloading $(basename "$download_url")..."
    download_image "$download_url" "$image_file"

    # Verify the COMPRESSED .img.xz before anything is written, then check
    # that its partitions fit the slot (reads the start of the image only)
    verify_image "$image_file"
    log_message "Step 2 of 4: checking the download..."
    verify_checksum "$image_file" "$image_sha"
    probe_image "$image_file" "$system_partition" "$boot_partition" "$TARGET_SLOT"
    echo "  OK"

    # Fetch the decompressed-image checksum from the release manifest:
    # rq_stream_image.py computes it while it writes and compares at the end.
    #
    # An A/B slot is written from the -ab image - a different file from the
    # standard one, with a different decompressed hash (ab_extract_sha256, not
    # extract_sha256). Fetching the wrong field made the post-decompress check
    # abort every A/B OTA against the standard image's hash. Detect the -ab
    # image by its URL (both slots on an A/B card use it).
    local extract_sha sha_field
    sha_field=$(sha_field_for "$download_url" extract)
    extract_sha=$(fetch_release_field "$release_tag" "$sha_field")
    if [ -n "$extract_sha" ]; then
        log_only "Fetched ${sha_field} from RQB-releases.json for $release_tag"
    else
        # Only the newest release of each stream has it; never borrow the
        # standard image's hash (that was the bug). The download was checked.
        log_only "No ${sha_field} in RQB-releases.json for $release_tag - the unpacked image is not checked again"
    fi

    # Write image to target slot (both boot and system partitions)
    write_image_to_slot "$image_file" "$system_partition" "$boot_partition" "$TARGET_SLOT" "$extract_sha" "$release_tag"

    # Configure tryboot (no automatic reboot)
    log_only "=== Update Complete ==="
    configure_tryboot "$TARGET_SLOT"
}

# Sourcing this file (tests) only defines the functions
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
