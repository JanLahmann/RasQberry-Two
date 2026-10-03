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
#   The user stays "rasqberry": its home holds the demos, the Python
#   environment and the desktop settings, which a rename would break. Imager's
#   call to userconf goes to rq_imager_userconf.sh, which applies the password
#   to rasqberry and logs a different requested name instead of renaming.
#
# Usage: rq_imager_firstrun.sh boot
#        rq_imager_firstrun.sh patch FILE    (patch one firstrun.sh; tests)
#
# Environment (tests): RQ_FW_DIR (/boot/firmware), RQ_AB_CONFIG_DIR
#   (/boot/config), RQ_BOOT_DIR (/boot), RQ_PROC_CMDLINE (/proc/cmdline),
#   RQ_IMAGER_LOG, RQ_IMAGER_REBOOT (command that restarts the Pi)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

FW_DIR="${RQ_FW_DIR:-/boot/firmware}"
CONFIG_DIR="${RQ_AB_CONFIG_DIR:-/boot/config}"
BOOT_DIR="${RQ_BOOT_DIR:-/boot}"
PROC_CMDLINE="${RQ_PROC_CMDLINE:-/proc/cmdline}"
LOG_FILE="${RQ_IMAGER_LOG:-/var/log/rasqberry-imager.log}"
USERCONF_WRAPPER="/usr/bin/rq_imager_userconf.sh"
MARK="# RasQberry: patched by rq_imager_firstrun.sh"
RUN_ARGS="systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"

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
    # Keep the user: userconf would rename uid 1000 (to "pi" when Imager has
    # an SSH key but no user name)
    sed -i "s|/usr/lib/userconf-pi/userconf|${USERCONF_WRAPPER}|g" "$f"
    if ! grep -qF "$MARK" "$f"; then
        # after the first line (#!/bin/sh or #!/bin/bash)
        sed -i "1a $MARK" "$f"
    fi
}

# Imager's own cmdline.txt entries, from a cmdline.txt it wrote or appended to
imager_regdom() {
    grep -o 'cfg80211\.ieee80211_regdom=[A-Za-z][A-Za-z]' "$1" 2>/dev/null | tail -n 1 || true
}

# A/B: Imager wrote to CONFIG (partition 1), which the Pi does not boot from
move_from_config() {
    local cfg_run="$CONFIG_DIR/firstrun.sh" regdom cmd
    log "Imager's customisation is on the CONFIG partition (A/B image): moving it to $FW_DIR"
    cp "$cfg_run" "$FW_DIR/firstrun.sh"
    rm -f "$cfg_run"
    patch_firstrun "$FW_DIR/firstrun.sh"

    regdom=""
    if [ -f "$CONFIG_DIR/cmdline.txt" ]; then
        regdom=$(imager_regdom "$CONFIG_DIR/cmdline.txt")
        # Imager made this file (CONFIG has none) or appended to it; the boot
        # does not read it. Keep whatever is left without Imager's entries.
        sed -i -e 's| *systemd\.run.*||' -e 's| *cfg80211\.ieee80211_regdom=[^ ]*||g' "$CONFIG_DIR/cmdline.txt"
        if ! grep -q '[^[:space:]]' "$CONFIG_DIR/cmdline.txt"; then
            rm -f "$CONFIG_DIR/cmdline.txt"
        fi
    fi

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
    ${RQ_IMAGER_REBOOT:-systemctl reboot --force}
}

cmd_boot() {
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
    elif grep -q 'systemd\.run=' "$PROC_CMDLINE" 2>/dev/null; then
        log "Applying Imager's customisation in this start"
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
