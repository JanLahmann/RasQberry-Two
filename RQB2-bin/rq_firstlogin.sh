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

# Asked to stop asking.
grep -q '^RQ_FIRSTLOGIN_DONE=true' "$ENV_FILE" 2>/dev/null && exit 0

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
    # Expansion refuses below ~63GB, so do not offer it on a small card.
    local card
    card=$(lsblk -bno SIZE /dev/mmcblk0 2>/dev/null | head -1)
    [ "${card:-0}" -ge 67645734912 ] || return 1
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
    # there is no standalone script - see docs/ab-boot.md on why. Source the
    # menu in a subshell so its functions do not leak into this shell.
    if [ ! -r "$MENU_FILE" ]; then
        whiptail --title "Expand A/B partitions" --msgbox \
            "Could not find the RasQberry menu at:\n\n  $MENU_FILE\n\nRun it directly instead:\n\n  sudo raspi-config -> RasQberry -> AB_BOOT -> EXPAND" 12 68
        return 1
    fi
    ( . "$MENU_FILE" >/dev/null 2>&1; do_expand_ab_partitions )
}

# ---------------------------------------------------------------------------
# Task: verify the LED panel layout
# ---------------------------------------------------------------------------
task_led_applies() { [ -x "$BIN_DIR/rq_led_setup_wizard.sh" ]; }
task_led_pending() { ! env_true LED_LAYOUT_VERIFIED; }
task_led_label()   { printf 'Check the LED panel shows the IBM logo the right way up'; }
task_led_run()     { "$BIN_DIR/rq_led_setup_wizard.sh" --verify; }

TASKS="expand led"

# ---------------------------------------------------------------------------
# Collect what is pending
# ---------------------------------------------------------------------------
pending=""
args=()
for t in $TASKS; do
    "task_${t}_applies" 2>/dev/null || continue
    "task_${t}_pending" 2>/dev/null || continue
    pending="$pending $t"
    args+=("$t" "$("task_${t}_label")" "ON")
done

# Nothing to do: say nothing. This runs on every login.
[ -n "$pending" ] || exit 0

args+=("never" "Don't ask again" "OFF")

# ---------------------------------------------------------------------------
# Ask once
# ---------------------------------------------------------------------------
choice=$(whiptail --title "RasQberry setup" --notags --separate-output \
    --checklist "Some setup steps are still pending.\n\nSpace to select, Enter to run them. Choose Cancel to be asked again next time." \
    16 74 4 "${args[@]}" 3>&1 1>&2 2>&3) || exit 0

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
