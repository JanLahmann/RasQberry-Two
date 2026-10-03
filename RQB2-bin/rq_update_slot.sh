#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: A/B Boot Slot Updater
# ============================================================================
# Description: Download and install new RasQberry image to boot slot
# Usage: rq_update_slot.sh <download_url> <release_tag> [--slot A|B] [--sha256 SUM]
#                          [--confirm] [--allow-unverified]
#        rq_update_slot.sh --preflight [--slot A|B]
#
# Strategy:
#   Slot A: STABLE - Protected, only updated manually with --slot A --confirm,
#           or by "rq_slot_manager.sh promote" (copies a tested Slot B to A)
#   Slot B: TESTING - Default target, receives updates
#
# This script:
#   1. Downloads the new image (.img.xz)
#   2. Writes to target slot (default: Slot B)
#   3. Configures tryboot to boot the new slot
#   4. Reboots the system
#
# The health check service will validate the new boot and either confirm
# or rollback to the stable slot.
#
# --preflight runs only the checks that can refuse an update (target slot is
# the running system, target not expanded, too little free space, another
# update running), without downloading anything. The menu calls it BEFORE its
# release picker, so a user is not walked through four dialogs to an error.
# Exit codes (also used when a real update is refused):
#   0  the target slot can be updated
#   1  any other error
#   20 the target slot is the system that is running now
#   21 the target slot is not set up (the 16MB placeholder): the card is not
#      prepared yet, or runs one system (single-system mode, rq_expand_ab.sh)
#   22 not enough free space to stage the download
#   23 this card has no A/B layout
#   24 another update is already running
#   25 no SHA256 for the image, so it cannot be verified (only installed with
#      --allow-unverified)
#
# The image is always checked against a SHA256 before anything is written:
# --sha256 (the menu passes the one its release list shows), else
# ab_image_sha256 from RQB-releases.json (newest release of each stream), else
# the digest GitHub keeps for every release asset, else <url>.sha256. Older
# releases used to install unchecked (H-34).
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
DEFAULT_TARGET_SLOT="B"  # Always update Slot B by default
STABLE_SLOT="A"          # Slot A is the stable/protected slot
MIN_FREE_KB=15728640     # 15GB: the .img.xz plus the ~12GB unpacked -ab image

RC_TARGET_RUNNING=20
RC_NOT_EXPANDED=21
RC_NO_SPACE=22
RC_NOT_AB=23
RC_BUSY=24
RC_UNVERIFIED=25

# Release manifest that carries per-release checksums (extract_sha256 = SHA256 of
# the DECOMPRESSED .img). Used to verify integrity when no explicit --sha256 is
# passed. Overridable via RQB_RELEASES_URL for testing/mirrors.
RELEASES_MANIFEST_URL="${RQB_RELEASES_URL:-https://rasqberry.org/RQB-releases.json}"

# Set while an update runs, so the EXIT trap can clean up after a failure or
# an interrupt (closed terminal, Ctrl+C, dropped SSH session)
WORK_DIR=""
LOOP_DEV=""
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
    # and up to 12GB of unpacked image behind, and the next attempt then fails
    # the free-space check for no visible reason. Called under the lock, so
    # nothing here belongs to a running update.
    [ -d "$DOWNLOAD_DIR" ] || return 0
    local mnt dev raw
    for mnt in $(findmnt -rn -o TARGET 2>/dev/null | grep "^${DOWNLOAD_DIR}/" | sort -r); do
        umount "$mnt" 2>/dev/null || umount -l "$mnt" 2>/dev/null || true
    done
    for raw in "$DOWNLOAD_DIR"/extract-*/image.img; do
        [ -f "$raw" ] || continue
        for dev in $(losetup -n -O NAME -j "$raw" 2>/dev/null); do
            losetup -d "$dev" 2>/dev/null || true
        done
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
    local target_slot="$1" system_partition="$2" boot_partition="$3"

    # Never flash the slot we are running from
    local current_root
    current_root=$(findmnt / -o source -n)
    if [ "$current_root" = "$system_partition" ]; then
        if [ "$target_slot" = "$DEFAULT_TARGET_SLOT" ]; then
            refuse "$RC_TARGET_RUNNING" "Slot $target_slot is the system you are running now, so it cannot be overwritten.
Updates go into Slot B (testing). First make the running system the stable one
(Slot Manager -> PROMOTE), or restart into Slot A (Slot Manager -> Restart into
Slot A). Then install the update."
        fi
        refuse "$RC_TARGET_RUNNING" "Slot $target_slot is the system you are running now ($current_root), so it cannot be overwritten. Boot the other slot first."
    fi
    local current_boot
    current_boot=$(findmnt /boot/firmware -o source -n 2>/dev/null || echo "")
    if [ -n "$current_boot" ] && [ "$current_boot" = "$boot_partition" ]; then
        refuse "$RC_TARGET_RUNNING" "Slot $target_slot: $boot_partition is the active boot partition, so it cannot be overwritten."
    fi

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

    # Enough free space to download + decompress in DOWNLOAD_DIR
    local avail_kb
    avail_kb=$(df --output=avail "$DOWNLOAD_DIR" | tail -1 | tr -d ' ')
    if [ "${avail_kb:-0}" -lt "$MIN_FREE_KB" ]; then
        refuse "$RC_NO_SPACE" "Not enough free space to stage the update: $((avail_kb / 1024 / 1024)) GB free, $((MIN_FREE_KB / 1024 / 1024)) GB needed
(the download plus the unpacked image, in $DOWNLOAD_DIR).
Delete Docker demo images or large files you no longer need, then try again."
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
    echo "Checking the download..."
    local actual
    actual=$(sha256sum "$image_file" | awk '{print $1}')
    if [ "$actual" != "$expected" ]; then
        rm -f "$image_file"
        die "The download is damaged or not the published image (SHA256 does not match: expected $expected, got $actual). Nothing was written; try again."
    fi
    log_only "Checksum OK: $actual"
    echo "  OK"
}

fetch_github_digest() {
    # The SHA256 GitHub keeps for a release asset ("digest": "sha256:..."),
    # for https://github.com/<owner>/<repo>/releases/download/<tag>/<file>.
    # Prints nothing when the URL is not like that or GitHub has none.
    local url="$1" path owner repo tag name
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
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for a in data.get("assets") or []:
    d = a.get("digest") or ""
    if a.get("name") == sys.argv[1] and d.startswith("sha256:"):
        print(d[7:])
        break
' "$name" 2>/dev/null || true
}

resolve_image_sha256() {
    # The expected SHA256 of <url>'s .img.xz (see the header for the order);
    # prints nothing when there is none
    local url="$1" tag="$2" sum=""
    if [ -n "$SHA256_SUM" ]; then
        echo "$SHA256_SUM"
        return 0
    fi
    sum=$(fetch_release_sha256 "$tag" "$(sha_field_for "$url" image)")
    [ -n "$sum" ] || sum=$(fetch_github_digest "$url")
    [ -n "$sum" ] || sum=$(curl -sSLf --max-time 30 "${url}.sha256" 2>/dev/null | awk '{print $1}' || true)
    case "$sum" in
        *[!0-9a-fA-F]*|"") sum="" ;;
    esac
    [ "${#sum}" -eq 64 ] || sum=""
    echo "$sum" | tr '[:upper:]' '[:lower:]'
}

fetch_release_sha256() {
    # Look up a checksum field for a release tag from the release manifest
    # (RQB-releases.json). $2 = field: image_sha256 / ab_image_sha256 (the
    # COMPRESSED .img.xz) or extract_sha256 / ab_extract_sha256 (the
    # DECOMPRESSED .img). Prints the sha (empty if the manifest is unreachable,
    # the field is absent, or the tag is not a current stream head - so older
    # tags / older manifests fall through to no-verification, not an error).
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

decompress_image() {
    # Unpack <image.img.xz> into <raw.img>.
    #
    # ONLY xz's stdout may reach the image file. Its -v progress is written to
    # stderr, which stays on the terminal (a live progress line) or, without a
    # terminal, goes to the log. R-002: the old `xz -dcv ... > raw 2>&1 | tee`
    # sent stderr into the image too - xz's summary line was appended to it,
    # the checksum never matched, and every update started from the menu or a
    # terminal aborted as "corrupted or tampered" after the full download.
    local image_file="$1" raw_image="$2"
    if [ -t 2 ]; then
        xz -dcvT0 -- "$image_file" > "$raw_image"
    else
        xz -dcT0 -- "$image_file" > "$raw_image" 2>> "$LOG_FILE"
    fi
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
    if mkdir -p "$BOOT_COMMON_DIR" 2>/dev/null \
        && echo "$(date -Iseconds) $tag" > "${BOOT_COMMON_DIR}/slot-${slot}-incomplete" 2>/dev/null; then
        sync
    else
        warn "Could not write ${BOOT_COMMON_DIR}/slot-${slot}-incomplete"
    fi
}

clear_slot_incomplete() {
    local slot="$1"
    rm -f "${BOOT_COMMON_DIR}/slot-${slot}-incomplete"
    INCOMPLETE_SLOT=""
    sync
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
        if [ -n "$LOOP_DEV" ]; then
            losetup -d "$LOOP_DEV" 2>/dev/null || true
        fi
        if ! findmnt -rn -o TARGET 2>/dev/null | grep -q "^${WORK_DIR}/"; then
            rm -rf "$WORK_DIR"
        fi
    fi
    if [ "$rc" -ne 0 ] && [ -n "$IMAGE_FILE" ]; then
        rm -f "$IMAGE_FILE"
    fi
    if [ "$rc" -ne 0 ] && [ -n "$INCOMPLETE_SLOT" ]; then
        echo "Slot $INCOMPLETE_SLOT was only partly written and holds no usable system now." >&2
        echo "The running system is unchanged. Install the update again to fill Slot $INCOMPLETE_SLOT." >&2
    fi
    if [ "$rc" -ne 0 ]; then
        log_only "Update stopped (exit code $rc)"
    fi
}

write_image_to_slot() {
    # Extract and write image to target slot (both boot and system partitions)
    local image_file="$1"
    local system_partition="$2"
    local boot_partition="$3"
    local target_slot="$4"
    local expected_extract_sha="${5:-}"
    local release_tag="${6:-}"

    log_only "Installing image to Slot $target_slot"
    log_only "  System partition: $system_partition"
    log_only "  Boot partition: $boot_partition"

    # Create work directory (removed by the EXIT trap on any failure)
    WORK_DIR="${DOWNLOAD_DIR}/extract-$$"
    local work_dir="$WORK_DIR"
    mkdir -p "$work_dir"

    # Decompress image (use all CPU cores with -T0 for faster decompression)
    log_message "Step 2 of 4: unpacking the image..."
    local raw_image="${work_dir}/image.img"
    if ! decompress_image "$image_file" "$raw_image"; then
        die "Failed to decompress image"
    fi
    log_only "Decompression complete"

    # Verify the DECOMPRESSED image against extract_sha256 from RQB-releases.json
    # (the manifest only publishes the extracted-image hash, so integrity is
    # checked here, after decompression, rather than on the .img.xz).
    if [ -n "$expected_extract_sha" ]; then
        log_message "Checking the unpacked image..."
        local actual_extract_sha
        actual_extract_sha=$(sha256sum "$raw_image" | awk '{print $1}')
        if [ "$actual_extract_sha" != "$expected_extract_sha" ]; then
            die "Decompressed image checksum mismatch! expected=$expected_extract_sha actual=$actual_extract_sha - download corrupted or tampered, aborting"
        fi
        log_only "Decompressed image checksum OK: $actual_extract_sha"
        echo "  OK"
    else
        # The download itself was checked; the manifest only has this second
        # checksum for the newest release of each stream
        log_only "No extract_sha256 in RQB-releases.json for this tag - the unpacked image is not checked again"
    fi

    # The unpacked image is checked; the compressed download is not needed
    # any more - free its space before the write
    cleanup_download "$image_file"

    # Set up loop device for the image
    log_only "Setting up loop device..."
    LOOP_DEV=$(losetup -f --show -P "$raw_image") || die "Failed to set up loop device"
    local loop_dev="$LOOP_DEV"
    log_only "Loop device: $loop_dev"

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
            log_only "AB image detected (p1 label: $p1_label)"
            log_only "Using Slot A partitions as source (boot-a, system-a)"
            img_boot="${loop_dev}p2"
            img_root="${loop_dev}p5"
            ;;
        BOOTFS)
            # Standard image: p1=bootfs, p2=rootfs
            log_only "Standard image detected (p1 label: $p1_label)"
            img_boot="${loop_dev}p1"
            img_root="${loop_dev}p2"
            ;;
        *)
            die "Unknown image type: p1 label '$p1_label' (expected 'CONFIG' or 'BOOTFS')"
            ;;
    esac

    if [ ! -b "$img_boot" ] || [ ! -b "$img_root" ]; then
        die "Could not find image partitions (boot: $img_boot, root: $img_root)"
    fi

    # The image's root partition must fit into the target partition - checked
    # before anything on the target is touched
    local img_root_size target_size
    img_root_size=$(blockdev --getsize64 "$img_root")
    target_size=$(blockdev --getsize64 "$system_partition")
    if [ "$img_root_size" -gt "$target_size" ]; then
        die "Image rootfs ($((img_root_size / 1024 / 1024))MB) does not fit target partition $system_partition ($((target_size / 1024 / 1024))MB)"
    fi

    # Mount image boot partition and copy to target boot partition
    log_message "Step 3 of 4: writing Slot $target_slot (do not switch the Pi off)..."
    log_only "Copying boot files to $boot_partition..."
    local img_boot_mount="${work_dir}/img_boot"
    local tgt_boot_mount="${work_dir}/tgt_boot"
    mkdir -p "$img_boot_mount" "$tgt_boot_mount"

    mount -o ro "$img_boot" "$img_boot_mount" || die "Failed to mount image boot partition"

    # Neither target partition may stay mounted (e.g. by the desktop
    # automounter) while it is written
    unmount_target "$boot_partition"
    unmount_target "$system_partition"

    # From here on the target slot is being overwritten
    mark_slot_incomplete "$target_slot" "$release_tag"

    # Format and mount target boot partition
    mkfs.vfat -F 32 -n "boot-$(echo "$target_slot" | tr '[:upper:]' '[:lower:]')" "$boot_partition" >> "$LOG_FILE" 2>&1 \
        || die "Failed to format boot partition"

    mount "$boot_partition" "$tgt_boot_mount" || die "Failed to mount target boot partition"

    # Copy all boot files (quietly, log only on error)
    if ! cp -a "$img_boot_mount"/* "$tgt_boot_mount"/ 2>> "$LOG_FILE"; then
        die "Failed to copy boot files"
    fi

    # Update cmdline.txt for the target slot
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
    fi

    # Unmount boot partitions
    sync
    umount "$tgt_boot_mount"
    umount "$img_boot_mount"
    log_only "Boot files copied successfully"

    # Write rootfs to system partition
    log_only "Writing rootfs to $system_partition..."

    # Show progress when in terminal, quiet otherwise
    if is_terminal; then
        if ! dd if="$img_root" of="$system_partition" bs=4M status=progress; then
            die "Failed to write rootfs to partition"
        fi
    else
        if ! dd if="$img_root" of="$system_partition" bs=4M 2>> "$LOG_FILE"; then
            die "Failed to write rootfs to partition"
        fi
    fi
    log_only "Rootfs written successfully"

    # Release loop device and the unpacked image (no longer needed)
    losetup -d "$loop_dev"
    LOOP_DEV=""
    rm -f "$raw_image"

    # Check the file system and grow it to the partition. Their output goes
    # to the log; the screen gets one line (H-34). e2fsck: 0 clean, 1 errors
    # corrected, 2 corrected (reboot advised), 4 and up not corrected.
    log_message "Step 4 of 4: checking the new system and taking over your settings..."
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
        local root_part
        root_part=$(findmnt / -o source -n)
        local root_dev
        root_dev=$(lsblk -no pkname "$root_part")

        cat > "$tgt_root_mount/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/${root_dev}p1          /boot/config    vfat    defaults          0   2
${boot_partition}           /boot/firmware  vfat    defaults          0   2
${system_partition}         /               ext4    defaults,noatime  0   1
/dev/${root_dev}p7          /data           ext4    defaults,noatime,nofail  0   2
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

    local new_version
    new_version=$(head -1 "$tgt_root_mount/etc/rasqberry-version" 2>/dev/null | tr -d '[:space:]' || true)
    log_message "Slot $target_slot now holds: ${new_version:-a system without /etc/rasqberry-version}"

    # Unmount and cleanup
    sync
    umount "$tgt_root_mount"
    rm -rf "$work_dir"
    WORK_DIR=""

    clear_slot_incomplete "$target_slot"
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
    TARGET_SLOT="$DEFAULT_TARGET_SLOT"
    REQUIRE_CONFIRM=false
    SHA256_SUM=""
    ALLOW_UNVERIFIED=false

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
            --confirm)
                REQUIRE_CONFIRM=true
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

confirm_stable_update() {
    # Require explicit confirmation for Slot A (stable) updates
    if [ "$TARGET_SLOT" = "$STABLE_SLOT" ]; then
        if [ "$REQUIRE_CONFIRM" != "true" ]; then
            die "Updating Slot $STABLE_SLOT (stable) requires --confirm flag for safety"
        fi
        [ -t 0 ] || die "Updating Slot $STABLE_SLOT (stable) asks for a typed confirmation: run it in a terminal"

        warn "═══════════════════════════════════════════════════════"
        warn "  WARNING: Updating STABLE Slot $STABLE_SLOT"
        warn "═══════════════════════════════════════════════════════"
        warn ""
        warn "This will overwrite your stable/baseline image!"
        warn "Make sure you have a backup or tested image."
        warn ""

        read -r -p "Type 'UPDATE STABLE' to confirm: " response
        if [ "$response" != "UPDATE STABLE" ]; then
            die "Stable slot update cancelled"
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
    echo "Slot $TARGET_SLOT can be updated ($((avail_kb / 1024 / 1024)) GB free for the download)."
}

usage() {
    cat << EOF
Usage: $0 <download_url> <release_tag> [--slot A|B] [--sha256 SUM] [--confirm] [--allow-unverified]
       $0 --preflight [--slot A|B]

Arguments:
  download_url    URL of the A/B image (-ab.img.xz) to install
  release_tag     Release tag/version identifier

Options:
  --slot A|B      Target slot (default: B, the testing slot)
  --sha256 <sum>  Expected SHA256 of the .img.xz (else RQB-releases.json, GitHub's
                  asset digest, then <url>.sha256; without one the update is refused)
  --allow-unverified  Install an image no SHA256 can be found for (experts only)
  --confirm       Required when updating Slot A (stable)
  --preflight     Only check whether the slot can be updated (exit codes 20-24
                  explain why not); downloads nothing

Slot Strategy:
  Slot A (STABLE):  Protected baseline, requires --confirm; normally filled by
                    'rq_slot_manager.sh promote' from a tested Slot B
  Slot B (TESTING): Default target for updates; cannot be updated while it
                    is the running system (promote or switch to Slot A first)

Examples:
  # Update Slot B (default)
  $0 https://github.com/.../image-ab.img.xz beta-2025-10-25-123456

  # Update stable Slot A (requires confirmation)
  $0 https://github.com/.../image-ab.img.xz beta-2025-10-25-123456 --slot A --confirm

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

    # Safety guards: never the booted slot, size and free-space prechecks
    preflight_checks "$TARGET_SLOT" "$system_partition" "$boot_partition"

    # Confirm if updating stable slot
    confirm_stable_update

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

    # Verify download
    verify_image "$image_file"
    # Verify the COMPRESSED .img.xz EARLY - before the ~12GB decompress - so a
    # corrupt/truncated download is caught immediately (not wasted on decompress).
    verify_checksum "$image_file" "$image_sha"

    # Fetch the decompressed-image checksum from the release manifest so
    # write_image_to_slot can verify integrity after decompression.
    #
    # An A/B slot is written from the -ab image - a different file from the
    # standard one, with a different decompressed hash (ab_extract_sha256, not
    # extract_sha256). Fetching the wrong field made the post-decompress check
    # abort every A/B OTA against the standard image's hash. Detect the -ab
    # image by its URL (both slots on an A/B card use it).
    local extract_sha sha_field
    sha_field=$(sha_field_for "$download_url" extract)
    extract_sha=$(fetch_release_sha256 "$release_tag" "$sha_field")
    if [ -n "$extract_sha" ]; then
        log_only "Fetched ${sha_field} from RQB-releases.json for $release_tag"
    else
        # Only the newest release of each stream has it; never borrow the
        # standard image's hash (that was the bug). The download was checked.
        log_only "No ${sha_field} in RQB-releases.json for $release_tag - the unpacked image is not checked again"
    fi

    # Write image to target slot (both boot and system partitions)
    write_image_to_slot "$image_file" "$system_partition" "$boot_partition" "$TARGET_SLOT" "$extract_sha" "$release_tag"

    # Cleanup
    cleanup_download "$image_file"

    # Configure tryboot (no automatic reboot)
    log_only "=== Update Complete ==="
    configure_tryboot "$TARGET_SLOT"
}

# Sourcing this file (tests) only defines the functions
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
