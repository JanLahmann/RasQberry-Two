#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: A/B card layout - two systems, or one system on a small card
# ============================================================================
# Description: The A/B image ships Slot A as 10 GiB and Slot B and DATA as
#   small placeholders, so the download stays ~12 GB (convert-to-ab-boot-v3.sh).
#   This script turns that into a layout that fits the card it landed on:
#
#   dual    card of 58 GiB or more (a "64GB" card is ~59.6 GiB):
#           Slot A 45% / Slot B 45% / DATA 10% of the space after the boot
#           partitions. Slot A is grown in place, Slot B and DATA are new.
#   single  smaller card: one system. Slot A grows to the card minus DATA
#           (10%); Slot B stays a 16 MiB placeholder, so the partition numbers
#           (and every fstab) stay the same. There is no second slot: a new
#           release means writing the new image to a card.
#
#   It runs automatically on the first boot of a freshly written card
#   (rasqberry-ab-layout.service -> "firstboot"), unless the CONFIG partition
#   holds the opt-out file "no-auto-expand" (or "no-auto-expand.txt"). The
#   converter writes /boot/config/ab-layout = "pending" into new images; cards
#   written before that never change by themselves. The menu ("Software &
#   Image Updates") runs the same code by hand.
#
# Usage: rq_expand_ab.sh status                 key=value facts and the mode
#        rq_expand_ab.sh mode                   just the mode
#        rq_expand_ab.sh explain [--update]     what the mode means, for dialogs
#        rq_expand_ab.sh plan [--dual|--single] [--text]
#        rq_expand_ab.sh apply [--dual|--single] --yes      (root)
#        rq_expand_ab.sh firstboot [--dry-run]               (root; boot service)
#
# Modes: standard        not an A/B card
#        dual            two usable slots (Slot B is 1 GiB or more)
#        dual-pending    58 GiB+ card, still the shipped placeholders
#        single          Slot A grown to use the card, Slot B a placeholder
#        single-pending  card under 58 GiB, still the shipped 10 GiB Slot A
#
# Environment overrides (tests and the loop-device lab):
#   RQ_AB_DISK          whole-disk device (default: the disk holding /)
#   RQ_AB_CONFIG_DIR    the CONFIG partition's mount point (default /boot/config)
#   RQ_AB_LOG           log file (default /var/log/rasqberry-expand.log)
#   RQ_AB_IS_AB, RQ_AB_CARD_BYTES, RQ_AB_SLOT_A_BYTES, RQ_AB_SLOT_B_BYTES,
#   RQ_AB_DATA_BYTES, RQ_AB_P5_START_MIB, RQ_AB_P5_END_MIB   fake facts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# ============================================================================
# CONFIGURATION (the converter header and docs/ab-boot.md quote these)
# ============================================================================

AB_MIN_DUAL_BYTES=62277025792        # 58 GiB: genuine 64GB cards (~59.6 GiB) qualify
AB_DATA_PERCENT=10                   # DATA = 10% of the space after the boot partitions
AB_FIXED_MIB=1536                    # CONFIG + BOOT-A + BOOT-B
AB_PLACEHOLDER_MIB=16                # Slot B placeholder in single mode
AB_GAP_MIB=2                         # room for the EBR before each logical partition
AB_SLOT_B_EXPANDED_BYTES=1073741824  # Slot B of 1 GiB or more = expanded
AB_SLOT_A_SHIPPED_MAX_BYTES=11274289152  # 10.5 GiB: above this Slot A was grown
AB_DATA_MAX_COPY_BYTES=536870912     # copy a placeholder /data aside only up to 512 MiB

CONFIG_DIR="${RQ_AB_CONFIG_DIR:-/boot/config}"
STATE_FILE="$CONFIG_DIR/ab-layout"
LOG_FILE="${RQ_AB_LOG:-/var/log/rasqberry-expand.log}"

# ============================================================================
# FACTS
# ============================================================================

ab_disk() {
    if [ -n "${RQ_AB_DISK:-}" ]; then
        echo "$RQ_AB_DISK"
        return
    fi
    local root parent
    root=$(findmnt -n -o SOURCE / 2>/dev/null || true)
    parent=$(lsblk -no PKNAME "$root" 2>/dev/null | head -1 || true)
    [ -n "$parent" ] && echo "/dev/$parent" || echo "/dev/mmcblk0"
}

# Partition N of the disk: mmcblk0p5, loop3p5, nvme0n1p5, but sda5
part_dev() {
    local disk
    disk=$(ab_disk)
    case "$disk" in
        *[0-9]) echo "${disk}p$1" ;;
        *)      echo "${disk}$1" ;;
    esac
}

dev_size() { blockdev --getsize64 "$1" 2>/dev/null || lsblk -bdno SIZE "$1" 2>/dev/null || echo 0; }

fact_is_ab() {
    if [ -n "${RQ_AB_IS_AB:-}" ]; then
        [ "$RQ_AB_IS_AB" = "1" ]
        return
    fi
    local label
    label=$(lsblk -no LABEL "$(part_dev 1)" 2>/dev/null | head -1 || true)
    # No udev data (early boot, containers): ask the filesystem itself
    [ -n "$label" ] || label=$(blkid -s LABEL -o value "$(part_dev 1)" 2>/dev/null || true)
    [ "$(echo "$label" | tr '[:lower:]' '[:upper:]')" = "CONFIG" ]
}

fact_card_bytes()   { echo "${RQ_AB_CARD_BYTES:-$(dev_size "$(ab_disk)")}"; }
fact_slot_a_bytes() { echo "${RQ_AB_SLOT_A_BYTES:-$(dev_size "$(part_dev 5)")}"; }
fact_slot_b_bytes() { echo "${RQ_AB_SLOT_B_BYTES:-$(dev_size "$(part_dev 6)")}"; }
fact_data_bytes()   { echo "${RQ_AB_DATA_BYTES:-$(dev_size "$(part_dev 7)")}"; }

# Start/end of p5 in MiB, from sysfs (always 512-byte sectors)
part_sysfs() { echo "/sys/class/block/$(basename "$(part_dev "$1")")"; }
fact_p5_start_mib() {
    if [ -n "${RQ_AB_P5_START_MIB:-}" ]; then echo "$RQ_AB_P5_START_MIB"; return; fi
    echo $(( $(cat "$(part_sysfs 5)/start") / 2048 ))
}
fact_p5_end_mib() {
    if [ -n "${RQ_AB_P5_END_MIB:-}" ]; then echo "$RQ_AB_P5_END_MIB"; return; fi
    local s n
    s=$(cat "$(part_sysfs 5)/start"); n=$(cat "$(part_sysfs 5)/size")
    echo $(( (s + n) / 2048 ))
}

optout_present() {
    [ -e "$CONFIG_DIR/no-auto-expand" ] || [ -e "$CONFIG_DIR/no-auto-expand.txt" ]
}

state_value() {
    [ -f "$STATE_FILE" ] || { echo none; return; }
    local v
    v=$(grep -v '^[[:space:]]*#' "$STATE_FILE" | tr -d '[:space:]' | head -c 32)
    echo "${v:-none}"
}

# ============================================================================
# DECISIONS (pure: facts in, answer out - tests/unit/test_expand_ab.py)
# ============================================================================

# decide_mode <is_ab 0|1> <card> <slot_a> <slot_b>
decide_mode() {
    local is_ab="$1" card="$2" a="$3" b="$4"
    if [ "$is_ab" != "1" ]; then echo standard
    elif [ "$b" -ge "$AB_SLOT_B_EXPANDED_BYTES" ]; then echo dual
    elif [ "$a" -gt "$AB_SLOT_A_SHIPPED_MAX_BYTES" ]; then echo single
    elif [ "$card" -ge "$AB_MIN_DUAL_BYTES" ]; then echo dual-pending
    else echo single-pending
    fi
}

# firstboot_action <mode> <state> <optout 0|1>  ->  dual | single | none:<why>
firstboot_action() {
    local mode="$1" state="$2" optout="$3"
    case "$state" in
        # A run that was cut off (power, crash): finish it, whatever the
        # partition sizes look like now and whatever the opt-out says
        resume-dual)   echo dual; return ;;
        resume-single) echo single; return ;;
    esac
    if [ "$state" != "pending" ]; then echo "none:not-pending"
    elif [ "$optout" = "1" ]; then echo "none:opt-out"
    else
        case "$mode" in
            dual-pending)   echo dual ;;
            single-pending) echo single ;;
            dual|single)    echo "none:already-$mode" ;;
            *)              echo "none:$mode" ;;
        esac
    fi
}

# plan_layout <dual|single> <card_bytes> <p5_start_mib>
# Prints: a_end b_start b_end data_start data_mib system_mib (MiB; data runs to 100%)
plan_layout() {
    local how="$1" card_mib=$(( $2 / 1048576 )) p5_start="$3"
    local avail=$(( card_mib - AB_FIXED_MIB ))
    local data_mib=$(( avail * AB_DATA_PERCENT / 100 ))
    local a_end b_start b_end data_start system_mib
    case "$how" in
        dual)
            # Same arithmetic as the menu's do_expand_ab_partitions had
            # (hardware-verified on 119 GB and 238 GB cards).
            system_mib=$(( (avail - data_mib) / 2 ))
            a_end=$(( p5_start + system_mib ))
            b_start=$(( a_end + AB_GAP_MIB ))
            b_end=$(( b_start + system_mib ))
            data_start=$(( b_end + AB_GAP_MIB ))
            ;;
        single)
            data_start=$(( card_mib - data_mib ))
            b_end=$(( data_start - AB_GAP_MIB ))
            b_start=$(( b_end - AB_PLACEHOLDER_MIB ))
            a_end=$(( b_start - AB_GAP_MIB ))
            system_mib=$(( a_end - p5_start ))
            ;;
        *) return 2 ;;
    esac
    echo "$a_end $b_start $b_end $data_start $(( card_mib - data_start )) $system_mib"
}

# ============================================================================
# WORDS (decimal GB, the menu's visible labels - R-095)
# ============================================================================

gb()  { awk -v b="${1:-0}" 'BEGIN { printf "%.0f", b / 1e9 }'; }
gb1() { awk -v b="${1:-0}" 'BEGIN { printf "%.1f", b / 1e9 }'; }
MENU_PATH="sudo raspi-config -> 0 RasQberry -> Software & Image Updates"

explain_mode() {
    local mode="$1" card="$2" a="$3" b="$4" data="$5" update="${6:-}"
    case "$mode" in
        dual)
            [ -n "$update" ] && return 0
            echo "This card holds two systems: Slot A ($(gb1 "$a") GB) and Slot B ($(gb1 "$b") GB),"
            echo "plus a $(gb1 "$data") GB data partition shared by both."
            echo "Updates install into the system you are not using; if the new one does"
            echo "not start, the Pi goes back to the one that worked."
            ;;
        dual-pending)
            echo "This $(gb "$card") GB card is big enough for two systems, but it has not"
            echo "been prepared yet: Slot B is still the 16 MB placeholder, so there is"
            echo "nowhere to install an update."
            optout_present && echo "(Automatic preparation is off: no-auto-expand is on the CONFIG partition.)"
            echo ""
            echo "Prepare it with: $MENU_PATH"
            echo "  -> Prepare the card for A/B updates"
            echo "It takes a few minutes and keeps everything on Slot A."
            ;;
        single)
            echo "This $(gb "$card") GB card is smaller than 64 GB, so it runs ONE system:"
            echo "Slot A uses the card ($(gb1 "$a") GB) plus a $(gb1 "$data") GB data partition."
            echo "There is no second system to install updates into."
            echo ""
            echo "To get a new RasQberry release, write the new image to a card with"
            echo "Raspberry Pi Imager (rasqberry.org/latest/). That erases this card:"
            echo "copy your files (the Shared folder, ~/.qiskit) to another computer first."
            echo "A 64 GB or larger card gets two systems and updates from the menu."
            ;;
        single-pending)
            echo "This $(gb "$card") GB card is smaller than 64 GB, so it can only run ONE"
            echo "system, and right now only $(gb "$a") GB of it is used."
            optout_present && echo "(Automatic setup is off: no-auto-expand is on the CONFIG partition.)"
            echo ""
            echo "Use the whole card with: $MENU_PATH"
            echo "  -> Use the whole card"
            echo "It takes a minute and keeps everything."
            [ -n "$update" ] && echo "" && echo "Updates: write the new image to a card (copy your files first)."
            ;;
        *)
            echo "This is the standard image: one system on the card."
            ;;
    esac
    return 0
}

# ============================================================================
# COMMANDS
# ============================================================================

collect_facts() {
    IS_AB=0
    fact_is_ab && IS_AB=1
    CARD=$(fact_card_bytes)
    if [ "$IS_AB" = "1" ]; then
        SLOT_A=$(fact_slot_a_bytes); SLOT_B=$(fact_slot_b_bytes); DATA=$(fact_data_bytes)
    else
        SLOT_A=0; SLOT_B=0; DATA=0
    fi
    MODE=$(decide_mode "$IS_AB" "$CARD" "$SLOT_A" "$SLOT_B")
}

cmd_status() {
    collect_facts
    local optout=0
    optout_present && optout=1
    cat <<EOF
mode=$MODE
layout=$([ "$IS_AB" = "1" ] && echo ab || echo standard)
disk=$(ab_disk)
card_bytes=$CARD
card_gb=$(gb "$CARD")
slot_a_bytes=$SLOT_A
slot_b_bytes=$SLOT_B
data_bytes=$DATA
min_dual_bytes=$AB_MIN_DUAL_BYTES
state=$(state_value)
optout=$optout
EOF
}

cmd_explain() {
    collect_facts
    explain_mode "$MODE" "$CARD" "$SLOT_A" "$SLOT_B" "$DATA" "${1:-}"
}

# Which layout to make: an explicit --dual/--single wins, else the card decides
pick_how() {
    local want="${1:-}"
    case "$want" in
        --dual)   echo dual ;;
        --single) echo single ;;
        "")       [ "$CARD" -ge "$AB_MIN_DUAL_BYTES" ] && echo dual || echo single ;;
        *)        die "Unknown option: $want (use --dual or --single)" ;;
    esac
}

check_plan() {
    # <how> -> sets A_END B_START B_END DATA_START DATA_MIB SYSTEM_MIB P5_START P5_END
    local how="$1"
    if [ "$how" = "dual" ] && [ "$CARD" -lt "$AB_MIN_DUAL_BYTES" ]; then
        die "This $(gb "$CARD") GB card is too small for two systems (64 GB or larger needed)."
    fi
    P5_START=$(fact_p5_start_mib)
    P5_END=$(fact_p5_end_mib)
    read -r A_END B_START B_END DATA_START DATA_MIB SYSTEM_MIB < <(plan_layout "$how" "$CARD" "$P5_START")
    if [ "$A_END" -lt "$P5_END" ]; then
        die "Slot A would have to shrink (ends at ${P5_END} MiB, plan ${A_END} MiB): card too small."
    fi
}

cmd_plan() {
    local want="" text=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --text) text=true ;;
            *) want="$1" ;;
        esac
        shift
    done
    collect_facts
    [ "$IS_AB" = "1" ] || die "Not an A/B card"
    local how
    how=$(pick_how "$want")
    check_plan "$how"
    local slot_b_mib=$(( B_END - B_START ))
    if $text; then
        echo "Card: $(gb "$CARD") GB"
        echo ""
        if [ "$how" = "dual" ]; then
            echo "  Slot A:  $(gb1 $(( (A_END - P5_START) * 1048576 ))) GB  (grows; your system stays as it is)"
            echo "  Slot B:  $(gb1 $(( slot_b_mib * 1048576 ))) GB  (new and empty until you install an update)"
        else
            echo "  Slot A:  $(gb1 $(( (A_END - P5_START) * 1048576 ))) GB  (grows; your system stays as it is)"
            echo "  Slot B:  none (this card runs one system)"
        fi
        echo "  Data:    $(gb1 $(( DATA_MIB * 1048576 ))) GB  (Shared folder, Wi-Fi, ~/.qiskit, LED settings)"
        echo ""
        echo "This cannot be undone. Do not switch off the Pi while it runs."
    else
        echo "how=$how"
        echo "p5_start_mib=$P5_START"
        echo "p5_end_mib=$P5_END"
        echo "slot_a_end_mib=$A_END"
        echo "slot_b_start_mib=$B_START"
        echo "slot_b_end_mib=$B_END"
        echo "data_start_mib=$DATA_START"
        echo "data_mib=$DATA_MIB"
        echo "system_mib=$SYSTEM_MIB"
    fi
}

# ----------------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------------

STEP=0
STEPS=7
DATA_BACKUP="${RQ_AB_DATA_BACKUP:-/var/lib/rasqberry/data-before-expand}"

# The whole new table as sfdisk input: p1-p3 as they are, p4 to the end of
# the card, p5 grown to the plan, p6 and p7 where the plan puts them.
new_table() {
    local disk="$1" dump sectors p4_start p5_start
    dump=$(sfdisk -d "$disk") || return 1
    sectors=$(( CARD / 512 ))
    p4_start=$(echo "$dump" | sed -n "s|^$(part_dev 4) *: *start= *\([0-9]*\),.*|\1|p")
    p5_start=$(echo "$dump" | sed -n "s|^$(part_dev 5) *: *start= *\([0-9]*\),.*|\1|p")
    [ -n "$p4_start" ] && [ -n "$p5_start" ] || return 1
    echo "$dump" | sed -n '/^label:/p; /^label-id:/p'
    echo "unit: sectors"
    echo ""
    echo "$dump" | awk -v a="$(part_dev 1)" -v b="$(part_dev 2)" -v c="$(part_dev 3)" '$1 == a || $1 == b || $1 == c'
    echo "$(part_dev 4) : start=$p4_start, size=$(( sectors - p4_start )), type=f"
    echo "$(part_dev 5) : start=$p5_start, size=$(( A_END * 2048 - p5_start )), type=83"
    echo "$(part_dev 6) : start=$(( B_START * 2048 )), size=$(( (B_END - B_START) * 2048 )), type=83"
    echo "$(part_dev 7) : start=$(( DATA_START * 2048 )), size=$(( sectors - DATA_START * 2048 )), type=83"
}
progress() {
    STEP=$((STEP + 1))
    printf '  [%s/%s] %s\n' "$STEP" "$STEPS" "$1"
    echo "Step $STEP: $1" >> "$LOG_FILE"
    if [ "${RQ_AB_PLYMOUTH:-0}" = "1" ] && command -v plymouth >/dev/null 2>&1; then
        plymouth display-message --text="Preparing the SD card ($STEP/$STEPS) - do not switch off" 2>/dev/null || true
    fi
}

logrun() {
    # Run a command with its output in the log; stop on failure. An explicit
    # die, not set -e: firstboot runs apply inside "( ... ) || rc=$?", where
    # bash ignores errexit.
    echo "+ $*" >> "$LOG_FILE"
    "$@" >> "$LOG_FILE" 2>&1 || die "Failed: $* (see $LOG_FILE)"
}

wait_for_part() {
    local dev="$1"
    for _ in $(seq 1 50); do
        [ -b "$dev" ] && return 0
        sleep 0.2
    done
    return 1
}

mountpoints_of() { findmnt -rn -S "$1" -o TARGET 2>/dev/null || true; }

cmd_apply() {
    local want="" yes=false
    while [ $# -gt 0 ]; do
        case "$1" in
            --yes) yes=true ;;
            *) want="$1" ;;
        esac
        shift
    done
    [ "$(id -u)" -eq 0 ] || die "Run as root (sudo)"
    $yes || die "Repartitions the card: pass --yes (the menu asks first)"

    collect_facts
    [ "$IS_AB" = "1" ] || die "Not an A/B card"
    local state
    state=$(state_value)
    case "$MODE" in
        # Sizes say "done" - unless a run was cut off after the table write
        dual|single) [ "${state#resume-}" != "$state" ] \
                         || die "Nothing to do: this card is already set up ($MODE)" ;;
    esac
    local how
    how=$(pick_how "$want")
    check_plan "$how"

    local disk p5 p6 p7
    disk=$(ab_disk); p5=$(part_dev 5); p6=$(part_dev 6); p7=$(part_dev 7)
    mkdir -p "$(dirname "$LOG_FILE")"
    {
        echo "=== A/B card layout: $how, $(date) ==="
        echo "disk=$disk card=$CARD p5=${P5_START}-${P5_END}MiB plan: a_end=$A_END b=${B_START}-${B_END} data=${DATA_START}-100% (${DATA_MIB}MiB)"
    } >> "$LOG_FILE"

    # From here on an interruption is finished by the next boot
    # (rasqberry-ab-layout.service), which reads this state.
    write_state "resume-$how"

    # Keep what is on the placeholder DATA (LED settings) and free p6/p7.
    # A fixed place on Slot A, so a run that was interrupted finds it again.
    progress "Saving the small data partition and unmounting it..."
    local data_mounts="" backup="$DATA_BACKUP"
    data_mounts=$(mountpoints_of "$p7")
    if [ -n "$data_mounts" ]; then
        local used first
        first=$(echo "$data_mounts" | head -1)
        used=$(df -B1 --output=used "$first" | tail -1 | tr -d ' ')
        used=${used:-0}
        [ "${used:-0}" -le "$AB_DATA_MAX_COPY_BYTES" ] \
            || die "The data partition holds $(gb1 "$used") GB - copy it off first."
        mkdir -p "$backup"
        cp -a "$first/." "$backup/" 2>> "$LOG_FILE" || true
        rm -rf "$backup/lost+found"
        local m
        while IFS= read -r m; do
            [ -n "$m" ] && logrun umount "$m"
        done <<< "$(echo "$data_mounts" | sort -r)"
    fi
    local m6
    while IFS= read -r m6; do
        [ -n "$m6" ] && logrun umount "$m6"
    done <<< "$(mountpoints_of "$p6")"

    # 2-4. The new partition table, written in ONE sfdisk call. p1-p5 keep
    # their starts; p4 and p5 grow, p6 and p7 are placed anew. Not parted:
    # parted -s refuses to resize the extended partition while Slot A (inside
    # it) is mounted - it only worked on the Pi because the root shows up as
    # /dev/root there and parted cannot tell it is busy. One write instead of
    # six also shortens the window in which a power cut leaves half a table
    # (and "pending" stays until the end, so the next boot finishes the job).
    progress "Writing the new partition table..."
    local table
    table=$(new_table "$disk") || die "Could not read the partition table of $disk"
    echo "$table" >> "$LOG_FILE"
    # The kernel is told partition by partition (a whole re-read is refused
    # while Slot A is mounted): forget the old p6/p7 (unmounted above) ...
    local n
    for n in 7 6; do
        [ -b "$(part_dev "$n")" ] && logrun partx -d --nr "$n" "$disk"
    done
    echo "$table" | logrun sfdisk --no-reread --no-tell-kernel -q "$disk"

    # ... grow p5 in place (allowed while mounted) and add the new p6/p7
    progress "Telling the kernel about the new partitions..."
    logrun partx -u --nr 5 "$disk"
    logrun partx -a --nr 6:7 "$disk"
    command -v udevadm >/dev/null 2>&1 && udevadm settle >> "$LOG_FILE" 2>&1 || true
    wait_for_part "$p6" || die "$p6 did not appear - see $LOG_FILE"
    wait_for_part "$p7" || die "$p7 did not appear - see $LOG_FILE"
    [ "$(cat "$(part_sysfs 5)/size")" -eq $(( A_END * 2048 - $(cat "$(part_sysfs 5)/start") )) ] \
        || die "The kernel did not take Slot A's new size - the next start finishes this"

    # Grow the Slot A filesystem (online when it is the running system)
    progress "Growing the Slot A filesystem..."
    if [ -n "$(mountpoints_of "$p5")" ]; then
        logrun resize2fs "$p5"
    else
        e2fsck -f -y "$p5" >> "$LOG_FILE" 2>&1 || true
        logrun resize2fs "$p5"
    fi

    # Filesystems
    progress "Formatting $([ "$how" = dual ] && echo "Slot B and " || true)the data partition..."
    logrun mkfs.ext4 -F -q -L SYSTEM-B "$p6"
    logrun mkfs.ext4 -F -q -L DATA "$p7"

    # Slot B skeleton (as the converter makes it) and the data structure
    progress "Preparing the new partitions..."
    local tmp
    tmp=$(mktemp -d)
    if mount "$p6" "$tmp" 2>> "$LOG_FILE"; then
        mkdir -p "$tmp/boot/config" "$tmp/boot/firmware" "$tmp/data" "$tmp/etc"
        cat > "$tmp/etc/fstab" << 'EOF'
proc                        /proc           proc    defaults          0   0
/dev/mmcblk0p1              /boot/config    vfat    defaults          0   2
/dev/mmcblk0p3              /boot/firmware  vfat    defaults          0   2
/dev/mmcblk0p6              /               ext4    defaults,noatime  0   1
/dev/mmcblk0p7              /data           ext4    defaults,noatime,nofail  0   2
EOF
        umount "$tmp"
    fi
    local data_dir="$tmp"
    if echo "$data_mounts" | grep -qx /data; then
        data_dir=/data
    elif [ -n "$data_mounts" ]; then
        data_dir=$(echo "$data_mounts" | head -1)
    elif [ -z "${RQ_AB_DISK:-}" ] && findmnt --fstab -n /data >/dev/null 2>&1; then
        # Finishing an interrupted run: /data could not be mounted at boot
        # (no filesystem yet) - mount it now, for the rest of this boot
        data_dir=/data
        data_mounts=/data
    fi
    mkdir -p "$data_dir"
    logrun mount "$p7" "$data_dir"
    mkdir -p "$data_dir/home" "$data_dir/rasqberry"
    local restored=false
    if [ -d "$backup" ]; then
        if cp -a "$backup/." "$data_dir/" 2>> "$LOG_FILE"; then
            restored=true
        else
            warn "Could not restore all of the old data partition (copy in $backup)"
        fi
    fi
    # Mounted again only where it was (normally /data); not the automounter's
    [ -n "$data_mounts" ] || umount "$data_dir"
    rmdir "$tmp" 2>/dev/null || true

    # Remember the layout on CONFIG (read by the menu, first login, updater);
    # only then drop the copy of the old data
    progress "Recording the layout..."
    write_state "$how"
    $restored && rm -rf "$backup"
    echo "=== done ===" >> "$LOG_FILE"
    # Run by hand on a running system: put the Shared folder, ~/.qiskit and
    # the Wi-Fi profiles on the new DATA now (at first boot the carry-over
    # service does it right after this).
    if [ -z "${RQ_AB_DISK:-}" ] && [ "${RQ_AB_PLYMOUTH:-0}" != "1" ] && [ -x "$SCRIPT_DIR/rq_carry_over.sh" ]; then
        "$SCRIPT_DIR/rq_carry_over.sh" link >> "$LOG_FILE" 2>&1 || warn "Could not set up the Shared folder on /data (see $LOG_FILE)"
    fi
    echo ""
    explain_mode "$how" "$CARD" "$(fact_slot_a_bytes)" "$(fact_slot_b_bytes)" "$(fact_data_bytes)"
}

write_state() {
    [ -d "$CONFIG_DIR" ] || return 0
    cat > "$STATE_FILE.tmp" << EOF
$1
# RasQberry A/B card layout (rq_expand_ab.sh, $(date '+%Y-%m-%d %H:%M')).
#   pending  a freshly written card: set up on its first start
#   dual     two systems (Slot A and Slot B) - updates go into the other one
#   single   card smaller than 64GB: one system uses the whole card
#   resume-* a set-up that was interrupted: the next start finishes it
# To stop a NEW card from being set up automatically, create an empty file
# named no-auto-expand next to this one before its first start.
EOF
    mv -f "$STATE_FILE.tmp" "$STATE_FILE"
}

# ----------------------------------------------------------------------------
# firstboot (rasqberry-ab-layout.service)
# ----------------------------------------------------------------------------

cmd_firstboot() {
    local dry=false
    [ "${1:-}" = "--dry-run" ] && dry=true
    collect_facts
    local optout=0 state action
    optout_present && optout=1
    state=$(state_value)
    action=$(firstboot_action "$MODE" "$state" "$optout")
    echo "rq_expand_ab: mode=$MODE state=$state optout=$optout -> $action"
    $dry && return 0

    case "$action" in
        none:already-*)
            write_state "$MODE"
            return 0 ;;
        none:*)
            return 0 ;;
    esac

    [ "$(id -u)" -eq 0 ] || die "Run as root"
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "=== first boot: $action ($(date)) ===" >> "$LOG_FILE"
    echo "RasQberry: preparing the SD card on its first start ($action). This takes"
    echo "a few minutes. Do not switch off the Pi."
    local rc=0
    ( RQ_AB_PLYMOUTH=1 cmd_apply "--$action" --yes ) || rc=$?
    if command -v plymouth >/dev/null 2>&1; then
        plymouth display-message --text="" 2>/dev/null || true
    fi
    if [ "$rc" -ne 0 ]; then
        # The state stays pending / resume-*: the next boot tries again.
        echo "rq_expand_ab: first-boot layout FAILED (rc=$rc), see $LOG_FILE" >&2
        return "$rc"
    fi
    # The device settings are saved again on the new DATA (#290)
    if [ -x /usr/bin/rq_device_settings.sh ] && [ -z "${RQ_AB_DISK:-}" ]; then
        /usr/bin/rq_device_settings.sh save >> "$LOG_FILE" 2>&1 || true
    fi
    return 0
}

usage() {
    sed -n '/^# Usage:/,/^# Modes:/p' "$0" | sed 's/^# \{0,1\}//' | grep -v '^Modes:' >&2
    exit 2
}

main() {
    local cmd="${1:-}"
    [ $# -gt 0 ] && shift
    case "$cmd" in
        status)    cmd_status ;;
        mode)      collect_facts; echo "$MODE" ;;
        explain)   cmd_explain "${1:-}" ;;
        plan)      cmd_plan "$@" ;;
        apply)     cmd_apply "$@" ;;
        firstboot) cmd_firstboot "$@" ;;
        decide)    decide_mode "$@" ;;                       # tests
        action)    firstboot_action "$@" ;;                  # tests
        layout)    plan_layout "$@" ;;                       # tests
        *)         usage ;;
    esac
}

main "$@"
