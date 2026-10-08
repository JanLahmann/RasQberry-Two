#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: apply Raspberry Pi Imager's OS customisation (firstrun.sh)
# ============================================================================
# Description: Raspberry Pi Imager (init_format "systemd") writes its OS
#   customisation - Wi-Fi, keyboard and time zone, SSH key, password,
#   hostname - as firstrun.sh into the FIRST FAT partition and appends
#   " systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot
#   systemd.unit=kernel-command-line.target" to its cmdline.txt. Raspberry Pi
#   OS bookworm makes that work with its initramfs (imager_fixup: /boot/ ->
#   /boot/firmware/). RasQberry images have no initramfs (feedback 37/41), and
#   on the A/B image the first FAT partition is CONFIG, which the Pi does not
#   boot from - so without this script the customisation was silently lost.
#
#   boot  (rasqberry-imager-firstrun.service, early in every start; does
#         nothing without a firstrun.sh)
#     A/B image: Imager wrote to CONFIG -> move firstrun.sh to this slot's
#       boot partition, add Imager's cmdline.txt entries there, restart.
#     Both images: point firstrun.sh and cmdline.txt at /boot/firmware, and
#       give this start the /boot/firstrun.sh it was told to run.
#     firstrun.sh runs once (kernel-command-line.service), removes itself and
#     its cmdline.txt entries, and restarts the Pi.
#
#   First start only: Imager's customisation belongs to a newly written card.
#   An A/B card that has started before (see AB_HISTORY) never applies it:
#   a leftover firstrun.sh - typically on CONFIG since the card was written,
#   as images before this one never used it - is set aside and the Pi is not
#   restarted for it. Applied by the first start of an updated Slot B, it
#   restarted the trial into Slot A and set the old settings again (rig,
#   2026-10-03). The standard image has no updates in place: unchanged.
#
#   Restarts never change the slot that runs (restart_pi): a plain restart
#   during an A/B trial (tryboot) starts the default slot and ends the trial.
#
#   The user name: Imager's call to userconf goes to rq_imager_userconf.sh,
#   which renames rasqberry to the name typed in Imager with
#   rq_user_rename.sh (home /home/<name>, the venv's paths, autologin, sudo,
#   services; #319) and then applies the password. When the rename is not
#   possible the user stays rasqberry. Raspberry Pi Connect (Imager 2.x) is
#   set up for uid 1000 - under the name it has by then, which comes later
#   in firstrun.sh than the user part.
#
# Usage: rq_imager_firstrun.sh boot
#        rq_imager_firstrun.sh patch FILE    (patch one firstrun.sh; tests)
#
# Environment (tests): RQ_FW_DIR (/boot/firmware), RQ_AB_CONFIG_DIR
#   (/boot/config), RQ_BOOT_DIR (/boot), RQ_PROC_CMDLINE (/proc/cmdline),
#   RQ_IMAGER_LOG, RQ_IMAGER_STATE (/var/lib/rasqberry), RQ_DT_BOOTLOADER_DIR
#   (/proc/device-tree/chosen/bootloader), RQ_IMAGER_REBOOT (command that
#   restarts the Pi; gets "0 tryboot" during a trial)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

FW_DIR="${RQ_FW_DIR:-/boot/firmware}"
CONFIG_DIR="${RQ_AB_CONFIG_DIR:-/boot/config}"
BOOT_DIR="${RQ_BOOT_DIR:-/boot}"
PROC_CMDLINE="${RQ_PROC_CMDLINE:-/proc/cmdline}"
LOG_FILE="${RQ_IMAGER_LOG:-/var/log/rasqberry-imager.log}"
IGNORED_DIR="${RQ_IMAGER_STATE:-/var/lib/rasqberry}/imager-ignored"
# This system started with Imager's customisation ("imager" in the first
# start's usage count, rq_umami_event.py)
APPLIED_MARK="${RQ_IMAGER_STATE:-/var/lib/rasqberry}/imager-customised"
DT_TRYBOOT="${RQ_DT_BOOTLOADER_DIR:-/proc/device-tree/chosen/bootloader}/tryboot"
USERCONF_WRAPPER="/usr/bin/rq_imager_userconf.sh"
MARK="# RasQberry: patched by rq_imager_firstrun.sh"
RUN_ARGS="systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
# What the A/B code leaves on CONFIG once a card has run: an update or a
# slot switch writes target-slot (and removes slot-confirmed); the health
# check confirms a good start (slot-confirmed, current-slot); a rollback
# writes current-slot. A newly written card - also one written again - has
# none of them until its first full start.
AB_HISTORY="target-slot slot-confirmed current-slot"

log() {
    echo "rq_imager_firstrun: $*"
    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; } 2>/dev/null || true
}

# Make one firstrun.sh fit this image; safe to run again
patch_firstrun() {
    local f="$1"
    # Paths: /boot is /boot/firmware on bookworm (what imager_fixup does), so
    # the script removes itself and its cmdline.txt entries for real - else
    # it would run again at every start
    sed -i -e 's|/boot/firstrun\.sh|/boot/firmware/firstrun.sh|g' \
           -e 's|/boot/cmdline\.txt|/boot/firmware/cmdline.txt|g' "$f"
    # The user: our wrapper renames uid 1000 itself, with everything the
    # image ties to its name and home (userconf only renames the account, and
    # to "pi" when Imager has an SSH key but no user name)
    sed -i "s|/usr/lib/userconf-pi/userconf|${USERCONF_WRAPPER}|g" "$f"
    # Raspberry Pi Connect: Imager 2.x gives its sign-in token to the name
    # typed in Imager ("pi" without one): TARGET_USER="NAME" and a
    # TARGET_HOME="/home/NAME" fallback. The user may have kept another name
    # (no password typed, or the rename was not possible), so the token and
    # the user services go to uid 1000 under the name it has when the Connect
    # part runs - after the user part: the typed name once it was renamed.
    # Imager 1.8.x writes no Connect part: nothing to change.
    sed -i -e 's@^TARGET_USER=.*$@TARGET_USER=$(getent passwd 1000 | cut -d: -f1); [ -n "$TARGET_USER" ] || TARGET_USER=rasqberry@' \
           -e 's@^\(if \[ -z "\$TARGET_HOME" \] || \[ ! -d "\$TARGET_HOME" \]; then TARGET_HOME=\)".*"; fi$@\1"/home/$TARGET_USER"; fi@' "$f"
    if ! grep -qF "$MARK" "$f"; then
        # after the first line (#!/bin/sh or #!/bin/bash)
        sed -i "1a $MARK" "$f"
    fi
}

# Imager's own cmdline.txt entries, from a cmdline.txt it wrote or appended to
imager_regdom() {
    grep -o 'cfg80211\.ieee80211_regdom=[A-Za-z][A-Za-z]' "$1" 2>/dev/null | tail -n 1 || true
}

is_ab_card() { [ -f "$CONFIG_DIR/autoboot.txt" ]; }

# The A/B card has started before: prints the first AB_HISTORY marker found
ab_history() {
    local m
    for m in $AB_HISTORY; do
        if [ -e "$CONFIG_DIR/$m" ]; then
            echo "$m"
            return 0
        fi
    done
    return 1
}

# Did the firmware start this system with the tryboot flag (an A/B trial)?
# chosen/bootloader/tryboot is a 32-bit big-endian number. Firmware that does
# not report it: a pending switch that is not confirmed yet counts as a trial.
this_start_is_tryboot() {
    local hex
    hex=$(od -An -tx1 "$DT_TRYBOOT" 2>/dev/null | tr -d ' \n' || true)
    case "$hex" in
        "")         [ -f "$CONFIG_DIR/target-slot" ] && [ ! -e "$CONFIG_DIR/slot-confirmed" ] ;;
        *[1-9a-f]*) return 0 ;;
        *)          return 1 ;;
    esac
}

# Restart into the system that runs now. During an A/B trial a plain restart
# starts the default slot instead and ends the trial (rig, 2026-10-03), so a
# trial restarts with "0 tryboot", as rq_slot_manager.sh and
# rq_tryboot_retry.sh do. Never a plain restart on a trial.
restart_pi() {
    local reboot_cmd="${RQ_IMAGER_REBOOT:-systemctl reboot --force}"
    sync
    if is_ab_card && this_start_is_tryboot; then
        log "Restarting with tryboot: the trial of this slot goes on"
        $reboot_cmd "0 tryboot"
    else
        $reboot_cmd
    fi
}

# Imager made CONFIG/cmdline.txt (CONFIG has none) or appended to it; the
# boot does not read it. Prints Imager's Wi-Fi country from it, then removes
# Imager's entries (and the file when nothing else is left).
take_config_cmdline() {
    local f="$CONFIG_DIR/cmdline.txt"
    [ -f "$f" ] || return 0
    imager_regdom "$f"
    sed -i -e 's| *systemd\.run.*||' -e 's| *cfg80211\.ieee80211_regdom=[^ ]*||g' "$f"
    if ! grep -q '[^[:space:]]' "$f"; then
        rm -f "$f"
    fi
}

# A leftover firstrun.sh goes off the FAT partitions, which every user can
# read (it holds the Wi-Fi key and the password hash): root only under
# $IGNORED_DIR, for reference. Removed when that fails. Prints where it went.
set_aside() {
    local f="$1" from="$2" dest
    dest="$IGNORED_DIR/firstrun.sh.$from.$(date '+%Y%m%d-%H%M%S')"
    if mkdir -p "$IGNORED_DIR" 2>/dev/null && chmod 700 "$IGNORED_DIR" 2>/dev/null \
        && mv -f "$f" "$dest" 2>/dev/null; then
        chmod 600 "$dest" 2>/dev/null || true
        echo "$dest"
    else
        rm -f "$f"
        echo "removed"
    fi
}

# An A/B card that has started before ($1: the marker that says so). Not for
# this start: set Imager's files aside, no restart for them - except when
# this very start was told to run firstrun.sh (systemd.run= in
# /proc/cmdline): without it, it would stop at kernel-command-line.target.
ignore_leftovers() {
    local why="$1" f from moved="" armed=false
    if grep -q 'systemd\.run=[^ ]*firstrun\.sh' "$PROC_CMDLINE" 2>/dev/null; then
        armed=true
    fi
    for from in config boot; do
        if [ "$from" = config ]; then f="$CONFIG_DIR/firstrun.sh"; else f="$FW_DIR/firstrun.sh"; fi
        [ -f "$f" ] || continue
        moved="${moved:+$moved, }$f -> $(set_aside "$f" "$from")"
    done
    take_config_cmdline >/dev/null
    if grep -q 'systemd\.run=[^ ]*firstrun\.sh' "$FW_DIR/cmdline.txt" 2>/dev/null; then
        sed -i 's| *systemd\.run=.*||' "$FW_DIR/cmdline.txt"
    fi
    sync
    log "Not applied: Raspberry Pi Imager's customisation (${moved:-nothing left to move}) - it is for the first start of a newly written card, and this card has started before (CONFIG/$why)"
    $armed || return 0
    if grep -q 'systemd\.run=[^ ]*firstrun\.sh' "$FW_DIR/cmdline.txt" 2>/dev/null; then
        log "WARNING: could not remove it from $FW_DIR/cmdline.txt - not restarting"
        return 0
    fi
    log "This start was set to run it: restarting without it"
    restart_pi
}

mark_applied() {
    { mkdir -p "$(dirname "$APPLIED_MARK")" && date '+%Y-%m-%d %H:%M:%S' > "$APPLIED_MARK"; } 2>/dev/null || true
}

# A/B: Imager wrote to CONFIG (partition 1), which the Pi does not boot from
move_from_config() {
    local cfg_run="$CONFIG_DIR/firstrun.sh" regdom cmd
    log "Imager's customisation is on the CONFIG partition (A/B image): moving it to $FW_DIR"
    cp "$cfg_run" "$FW_DIR/firstrun.sh"
    rm -f "$cfg_run"
    patch_firstrun "$FW_DIR/firstrun.sh"

    regdom=$(take_config_cmdline)

    # This slot's cmdline.txt: Imager's Wi-Fi country, then the one-time run
    # at the end (firstrun.sh removes " systemd.run" and everything after it)
    cmd=$(tr -d '\n' < "$FW_DIR/cmdline.txt" | sed -e 's| *systemd\.run.*||')
    if [ -n "$regdom" ]; then
        if printf '%s' "$cmd" | grep -q 'cfg80211\.ieee80211_regdom='; then
            cmd=$(printf '%s' "$cmd" | sed "s|cfg80211\.ieee80211_regdom=[^ ]*|${regdom}|")
        else
            cmd="$cmd $regdom"
        fi
    fi
    printf '%s %s\n' "$cmd" "$RUN_ARGS" > "$FW_DIR/cmdline.txt"
    sync
    log "Restarting to apply it"
    restart_pi
}

cmd_boot() {
    local history
    if is_ab_card && history=$(ab_history); then
        ignore_leftovers "$history"
        return 0
    fi
    # From here: the standard image, or the first start of a new A/B card
    if [ -f "$CONFIG_DIR/firstrun.sh" ] && [ -f "$FW_DIR/cmdline.txt" ]; then
        move_from_config
        return 0
    fi
    [ -f "$FW_DIR/firstrun.sh" ] || return 0

    patch_firstrun "$FW_DIR/firstrun.sh"
    # Later starts (should this one be interrupted) run it from where it is
    if grep -q 'systemd\.run=/boot/firstrun\.sh' "$FW_DIR/cmdline.txt" 2>/dev/null; then
        sed -i 's|systemd\.run=/boot/firstrun\.sh|systemd.run=/boot/firmware/firstrun.sh|' "$FW_DIR/cmdline.txt"
    fi
    # This start was told to run /boot/firstrun.sh, which bookworm keeps at
    # /boot/firmware: a stand-in that removes itself
    if grep -q 'systemd\.run=/boot/firstrun\.sh' "$PROC_CMDLINE" 2>/dev/null; then
        cat > "$BOOT_DIR/firstrun.sh" <<'EOF'
#!/bin/sh
# RasQberry: runs Raspberry Pi Imager's customisation from the boot partition
rm -f /boot/firstrun.sh
exec /bin/bash /boot/firmware/firstrun.sh
EOF
        chmod 755 "$BOOT_DIR/firstrun.sh"
        log "Applying Imager's customisation in this start (/boot/firmware/firstrun.sh)"
        mark_applied
    elif grep -q 'systemd\.run=' "$PROC_CMDLINE" 2>/dev/null; then
        log "Applying Imager's customisation in this start"
        mark_applied
    elif ! grep -q 'systemd\.run=' "$FW_DIR/cmdline.txt" 2>/dev/null; then
        log "WARNING: $FW_DIR/firstrun.sh is there, but cmdline.txt does not run it - left alone"
    fi
    sync
}

case "${1:-}" in
    boot)  cmd_boot ;;
    patch) [ -n "${2:-}" ] && [ -f "$2" ] || die "Usage: $(basename "$0") patch FILE"
           patch_firstrun "$2" ;;
    *)     echo "Usage: $(basename "$0") boot | patch FILE" >&2; exit 2 ;;
esac
