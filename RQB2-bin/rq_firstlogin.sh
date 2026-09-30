#!/bin/bash
# ============================================================================
# RasQberry: first-login setup checklist
# ============================================================================
# Offers the setup steps that are still pending, once, on the first interactive
# login - and says nothing at all when there is nothing to do.
#
# Called from /etc/profile.d/rasqberry-firstlogin.sh (login shells: ssh, console
# login) and, via the same file, from .bashrc (desktop terminals are non-login
# interactive shells and skip /etc/profile.d).
#
# Adding a task: give it an _applies (is it relevant to this machine?), a
# _pending (is it still undone?), a label, and a _run. Nothing else changes.
#
# Two rules learned the hard way, do not drop them:
#
#   1. Only ask where a person can answer. The image logs itself in on tty1 at
#      boot (/bin/login -f) and that shell is interactive WITH a real tty, so
#      "interactive + tty" is not enough: the LED verify used to fire there at
#      every boot, under the desktop where nobody could see it, and sat holding
#      the LED GPIO for the whole session - which made every LED demo fail with
#      "GPIO busy" against a dark panel. A person arrives on a pts.
#
#   2. Offer, never act. Expanding the partitions halves someone's SD card;
#      automatic firstboot expansion was deliberately removed (issue #142) so
#      the user decides. Same for anything added here.

set +u

ENV_FILE="/usr/config/rasqberry_environment.env"
MENU_FILE="/usr/config/RQB2_menu.sh"
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Gate: is anyone actually looking? (rule 1)
# ---------------------------------------------------------------------------
# Ask ps for the CONTROLLING terminal, not `tty` for stdin's.
#
# The hooks call us as `rq_firstlogin.sh </dev/tty >/dev/tty 2>&1`, and with
# stdin redirected from /dev/tty, `tty` reports the literal string "/dev/tty" -
# which matches no /dev/pts/* test. So a `tty`-based gate swallowed every real
# login while passing every direct invocation it was tested with. ps reads the
# controlling terminal off the process itself: "pts/N" over ssh or a desktop
# terminal, "tty1" on the boot console, however stdin happens to be plumbed.
case "$(ps -o tty= -p $$ 2>/dev/null | tr -d '[:space:]')" in
    pts/*) ;;
    *)     exit 0 ;;
esac

# --all: the "RasQberry Setup" desktop icon. Show every step that applies,
# pending ones ticked, even after "Don't ask again" or once already offered.
SHOW_ALL=false
[ "${1:-}" = "--all" ] && SHOW_ALL=true

# Asked to stop asking.
[ "$SHOW_ALL" = true ] || ! grep -q '^RQ_FIRSTLOGIN_DONE=true' "$ENV_FILE" 2>/dev/null || exit 0

command -v whiptail >/dev/null 2>&1 || exit 0

env_true() { grep -q "^$1=true" "$ENV_FILE" 2>/dev/null; }

# ---------------------------------------------------------------------------
# Task: expand the A/B partitions
# ---------------------------------------------------------------------------
# An A/B image ships Slot B and data as 16MB placeholders so the download stays
# ~12GB instead of ~120GB (convert-to-ab-boot-v3.sh). Until they are expanded
# there is nowhere to put a second system, Slot A stays 10GB - which the image
# nearly fills - and rq_update_slot.sh cannot stage a download. See
# docs/ab-boot.md.
task_expand_applies() {
    # A/B layout: p1 is the shared CONFIG partition.
    lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qi "config" || return 1
    # Expansion needs 58 GiB or more. A "64GB" card is only ~59.6 GiB (decimal
    # marketing vs binary GiB), so the old 63 GiB (67645734912) cutoff wrongly
    # refused genuine 64GB cards. 58 GiB accepts them and still rejects 32GB.
    local card
    card=$(lsblk -bno SIZE /dev/mmcblk0 2>/dev/null | head -1)
    [ "${card:-0}" -ge 62277025792 ] || return 1
    return 0
}
task_expand_pending() {
    local slot_b
    slot_b=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    [ "${slot_b:-0}" -lt 1073741824 ]
}
task_expand_label() {
    local card
    card=$(lsblk -bno SIZE /dev/mmcblk0 2>/dev/null | head -1)
    printf 'Expand A/B partitions (%sGB card; Slot B is a 16MB placeholder)' \
        "$((${card:-0} / 1024 / 1024 / 1024))"
}
task_expand_run() {
    # The expansion lives in the raspi-config menu (do_expand_ab_partitions);
    # there is no standalone script - see docs/ab-boot.md on why.
    if [ ! -r "$MENU_FILE" ]; then
        whiptail --title "Expand A/B partitions" --msgbox \
            "Could not find the RasQberry menu at:\n\n  $MENU_FILE\n\nRun it directly instead:\n\n  sudo raspi-config -> RasQberry -> AB_BOOT -> EXPAND" 12 68
        return 1
    fi
    # Run it as root, and do NOT assume we already are.
    #
    # do_expand_ab_partitions repartitions the card and logs to /var/log: it only
    # ever ran from raspi-config, which is already root, so it never had to ask.
    # We are a login shell - the user - so sourcing and calling it directly gave
    # "Permission denied" on every parted and every log write, and a dialog
    # saying expansion "may have failed" when it had not started. (No damage:
    # parted could not touch the table either.) The LED task works because the
    # wizard re-execs itself via ensure_root; this has no such thing, so sudo it
    # here. sudo -E keeps the env, and sets SUDO_USER, which the menu wants.
    sudo -E bash -c ". '$MENU_FILE' >/dev/null 2>&1; do_expand_ab_partitions"
}

# ---------------------------------------------------------------------------
# Task: verify the LED panel layout
# ---------------------------------------------------------------------------
task_led_applies() { [ -x "$BIN_DIR/rq_led_setup_wizard.sh" ]; }
task_led_pending() { ! env_true LED_LAYOUT_VERIFIED; }
task_led_label()   { printf 'Check the LED panel shows the IBM logo the right way up'; }
task_led_run()     { "$BIN_DIR/rq_led_setup_wizard.sh" --verify; }

# ---------------------------------------------------------------------------
# Optional tasks: offered once, not on every login
# ---------------------------------------------------------------------------
# expand and led stay pending until done. The ones below are preferences, so
# after the checklist has shown them once they only come back through the
# "RasQberry Setup" desktop icon (--all). Per user, no root needed.
OFFERED_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/rasqberry/firstlogin-offered"
offered()      { grep -qx "$1" "$OFFERED_FILE" 2>/dev/null; }
mark_offered() { mkdir -p "$(dirname "$OFFERED_FILE")" && { offered "$1" || echo "$1" >> "$OFFERED_FILE"; }; }

# ---------------------------------------------------------------------------
# Task: connect to a WLAN (only when there is no network at all)
# ---------------------------------------------------------------------------
task_wifi_applies() { [ -d /sys/class/net/wlan0 ] && command -v nmtui >/dev/null 2>&1; }
task_wifi_pending() { ! ip route get 1.1.1.1 >/dev/null 2>&1; }
task_wifi_label()   { printf 'Connect to a WLAN (no network connection found)'; }
task_wifi_run()     { nmtui connect || sudo nmtui connect; }

# ---------------------------------------------------------------------------
# Task: download all demos now (they otherwise install on first use)
# ---------------------------------------------------------------------------
task_demos_applies() { [ -r "$MENU_FILE" ]; }
task_demos_pending() {
    # Pending while any git-installed demo is missing
    grep -qE '^(QUANTUM_LIGHTS_OUT|QUANTUM_RASPBERRY_TIE|GROK_BLOCH|FUN_WITH_QUANTUM|QUANTUM_PARADOXES|IBM_TUTORIALS|IBM_COURSES)_INSTALLED=false' "$ENV_FILE" 2>/dev/null
}
task_demos_label()   { printf 'Download all demos now (otherwise each installs when first started)'; }
task_demos_run() {
    sudo -E bash -c ". /usr/config/rasqberry_env-config.sh >/dev/null 2>&1; . '$MENU_FILE' >/dev/null 2>&1; do_download_all_demos"
}

# ---------------------------------------------------------------------------
# Task: touch mode (only with a touchscreen attached)
# ---------------------------------------------------------------------------
# Enabling it restarts the desktop session, so it runs last (TASKS order).
task_touch_applies() {
    [ -x "$BIN_DIR/rq_touch_mode.sh" ] && grep -qiE 'touch|ft5x06|goodix|ili2' /proc/bus/input/devices 2>/dev/null
}
task_touch_pending() { [ "$("$BIN_DIR/rq_touch_mode.sh" status --quiet 2>/dev/null)" != "enabled" ]; }
task_touch_label()   { printf 'Enable touch mode (larger icons, on-screen keyboard; restarts the desktop)'; }
task_touch_run()     { "$BIN_DIR/rq_touch_mode.sh" enable; }

# How a finished step reads in the --all list
done_label() {
    case "$1" in
        wifi)   echo "network connection" ;;
        expand) echo "A/B partitions expanded" ;;
        led)    echo "LED panel checked" ;;
        demos)  echo "demos downloaded" ;;
        touch)  echo "touch mode enabled" ;;
        *)      echo "$1" ;;
    esac
}

OPTIONAL_TASKS="wifi demos touch"
is_optional() { case " $OPTIONAL_TASKS " in *" $1 "*) return 0 ;; esac; return 1; }

TASKS="wifi expand led demos touch"

# ---------------------------------------------------------------------------
# Collect what is pending
# ---------------------------------------------------------------------------
pending=""
args=()
for t in $TASKS; do
    "task_${t}_applies" 2>/dev/null || continue
    if "task_${t}_pending" 2>/dev/null; then
        if is_optional "$t" && offered "$t" && [ "$SHOW_ALL" != true ]; then
            continue
        fi
        # Required steps start ticked, optional ones unticked (rule 2)
        state=ON; is_optional "$t" && [ "$t" != wifi ] && state=OFF
        pending="$pending $t"
        args+=("$t" "$("task_${t}_label")" "$state")
    elif [ "$SHOW_ALL" = true ]; then
        args+=("$t" "Done: $(done_label "$t")" "OFF")
    fi
done

# Nothing to do: say nothing. This runs on every login.
if [ -z "$pending" ]; then
    [ "$SHOW_ALL" = true ] && whiptail --title "RasQberry setup" --msgbox \
        "All setup steps are done.\n\nEverything is also in: sudo raspi-config -> 0 RasQberry" 10 64
    exit 0
fi

for t in $pending; do is_optional "$t" && mark_offered "$t"; done
[ "$SHOW_ALL" = true ] || args+=("never" "Don't ask again" "OFF")

# ---------------------------------------------------------------------------
# Ask once
# ---------------------------------------------------------------------------
rows=$(( ${#args[@]} / 3 ))
choice=$(whiptail --title "RasQberry setup" --notags --separate-output \
    --checklist "Some setup steps are still pending.\n\nSpace to select, Enter to run them. Choose Cancel to be asked again next time." \
    $((rows + 11)) 78 "$rows" "${args[@]}" 3>&1 1>&2 2>&3) || exit 0

[ -n "$choice" ] || exit 0

for sel in $choice; do
    if [ "$sel" = "never" ]; then
        if [ -w "$ENV_FILE" ] || [ "$(id -u)" = "0" ]; then
            sed -i '/^RQ_FIRSTLOGIN_DONE=/d' "$ENV_FILE" 2>/dev/null
            echo "RQ_FIRSTLOGIN_DONE=true" >> "$ENV_FILE" 2>/dev/null
        else
            sudo sh -c "sed -i '/^RQ_FIRSTLOGIN_DONE=/d' '$ENV_FILE'; echo 'RQ_FIRSTLOGIN_DONE=true' >> '$ENV_FILE'" 2>/dev/null
        fi
        continue
    fi
    "task_${sel}_run" || true
done

exit 0
