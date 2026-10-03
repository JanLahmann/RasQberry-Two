#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED brightness
# ============================================================================
# Description: Set how bright the LED panel may get. A brighter panel draws
#   more current; on a power supply that is too weak the Pi 5's LED driver
#   stalls and the panel stops (item 31). After a stall the launchers call
#   --after-stall: it says what happened and offers a lower brightness. Nothing
#   is lowered without asking, and this menu raises it again (Jan, 2026-10-03).
# Usage:
#   rq_led_brightness.sh                      choose a level (whiptail menu)
#   rq_led_brightness.sh --set LEVEL          set a level: low, medium, normal, bright
#   rq_led_brightness.sh --after-stall EPOCH  the panel stalled since EPOCH (date +%s)?
#                                             then explain and offer a lower level
#   rq_led_brightness.sh --show               print the current setting
# The level sets LED_DEFAULT_BRIGHTNESS (what demos use) and LED_MAX_BRIGHTNESS
# (the limit, also for demos that pick their own brightness).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

load_rqb2_env

# Notes written by rq_led_utils.py when the panel stalled (one per user id)
STALL_PREFIX="${RQ_LED_STALL_PREFIX:-/var/tmp/rasqberry-led-stall-}"

# level -> "default limit"
level_values() {
    case "$1" in
        low)    echo "0.2 0.2" ;;
        medium) echo "0.3 0.3" ;;
        normal) echo "0.4 1.0" ;;
        bright) echo "0.6 1.0" ;;
        *) return 1 ;;
    esac
}

# The level the current settings match ("" when set by hand)
current_level() {
    local d="${LED_DEFAULT_BRIGHTNESS:-0.4}" m="${LED_MAX_BRIGHTNESS:-1.0}" l
    for l in low medium normal bright; do
        [ "$(level_values "$l")" = "$d $m" ] && { echo "$l"; return 0; }
    done
    echo ""
}

set_level() {
    local values
    values=$(level_values "$1") || die "Unknown level: $1 (low, medium, normal or bright)"
    # shellcheck disable=SC2086
    set -- $values
    update_env_var LED_DEFAULT_BRIGHTNESS "$1" || die "Could not save the LED brightness."
    update_env_var LED_MAX_BRIGHTNESS "$2" || die "Could not save the LED brightness limit."
    info "LED brightness: $1${2:+ (limit $2)}"
}

# Newest stall note at or after EPOCH: prints "TIME RECOVERED"
newest_stall() {
    local since="$1" f t r best=0 best_r=""
    for f in "$STALL_PREFIX"*; do
        [ -f "$f" ] || continue
        t=$(sed -n 's/^time=//p' "$f" | head -1)
        r=$(sed -n 's/^recovered=//p' "$f" | head -1)
        case "$t" in ''|*[!0-9]*) continue ;; esac
        if [ "$t" -ge "$since" ] && [ "$t" -gt "$best" ]; then
            best="$t"; best_r="$r"
        fi
    done
    [ "$best" -gt 0 ] || return 1
    echo "$best ${best_r:-no}"
}

# Pi 5: restart the LED driver (rp1-pio) while nothing uses the panel. For a
# stall that reopening it from the demo did not cure; on the rig, unbind and
# bind gave a fresh /dev/pio0 and a working panel without a reboot.
reset_pio_driver() {
    local drv="${RQ_PIO_DRIVER_DIR:-/sys/bus/platform/drivers/rp1-pio}" dev
    [ -d "$drv" ] || return 1
    dev=$(ls -d "$drv"/*.pio 2>/dev/null | head -1)
    [ -n "$dev" ] || return 1
    dev=$(basename "$dev")
    fuser /dev/pio0 >/dev/null 2>&1 && return 1
    _rq_as_root sh -c 'echo "$1" > "$2/unbind" && echo "$1" > "$2/bind"' _ "$dev" "$drv" 2>/dev/null
}

after_stall() {
    local since="${1:-0}" found recovered text
    case "$since" in ''|*[!0-9]*) since=0 ;; esac
    found=$(newest_stall "$since") || return 0
    recovered="${found#* }"
    if [ "$recovered" = "yes" ]; then
        text="The LED panel stalled during the demo and was restarted."
    elif reset_pio_driver; then
        text="The LED panel stopped during the demo: its driver did not respond, and it has been restarted now."
    else
        text="The LED panel stopped during the demo: its driver did not respond. If it stays dark, restart the Pi."
    fi
    text="$text This happens when the power supply is too weak for the LEDs.\n\nUse the official Raspberry Pi 27 W power supply, or give the LED panel its own power.\n\nA lower brightness draws less current. Raise it again any time: RasQberry menu > LEDs > LED brightness."
    if ! { [ -t 0 ] && [ -t 1 ]; } || ! command -v whiptail >/dev/null 2>&1; then
        warn "$(printf '%b' "$text" | tr '\n' ' ' | sed 's/  */ /g')"
        return 0
    fi
    local cur="${LED_DEFAULT_BRIGHTNESS:-0.4}"
    if [ "$(current_level)" = "low" ]; then
        show_msgbox "LED panel stopped" "$text" 16 70
        return 0
    fi
    if whiptail --title "LED panel stopped" --yes-button "Lower to 0.2" --no-button "Keep $cur" \
            --yesno "$(printf '%b' "$text")" 17 70; then
        set_level low
    fi
    return 0
}

choose() {
    local cur pick
    cur=$(current_level)
    pick=$(whiptail --title "LED brightness" --notags --default-item "${cur:-normal}" --menu \
"How bright may the LED panel get? Now: ${LED_DEFAULT_BRIGHTNESS:-0.4}$([ "${LED_MAX_BRIGHTNESS:-1.0}" != "1.0" ] && echo " (limit ${LED_MAX_BRIGHTNESS})")

A brighter panel draws more current. If the panel stops with a weak power supply, choose Low." \
        16 72 4 \
        low    "Low (0.2): for a weak power supply" \
        medium "Medium (0.3)" \
        normal "Normal (0.4, as shipped)" \
        bright "Bright (0.6): needs the 27 W supply" \
        3>&1 1>&2 2>&3) || return 0
    set_level "$pick"
}

case "${1:-}" in
    "")            choose ;;
    --set)         set_level "${2:-}" ;;
    --after-stall) after_stall "${2:-0}" ;;
    --show)        echo "LED_DEFAULT_BRIGHTNESS=${LED_DEFAULT_BRIGHTNESS:-0.4} LED_MAX_BRIGHTNESS=${LED_MAX_BRIGHTNESS:-1.0} level=$(current_level)" ;;
    *)             die "Usage: rq_led_brightness.sh [--set LEVEL | --after-stall EPOCH | --show]" ;;
esac
