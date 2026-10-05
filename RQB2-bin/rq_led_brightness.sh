#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED brightness
# ============================================================================
# Description: Set how bright the LED panel may get. A brighter panel draws
#   more current; on a power supply that is too weak the Pi 5's LED driver
#   stalls and the panel stops (item 31). After a stall the launchers call
#   --after-stall: it says what happened and, from what the Pi reports
#   (get_throttled), whether power or heat is the likely cause; a lower
#   brightness is offered only when power may be short (#5). Nothing is
#   lowered without asking, and this menu raises it again (Jan, 2026-10-03).
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

# What the Pi itself reported (vcgencmd get_throttled, #5): power (an
# under-voltage bit: 0x1 now, 0x10000 since start-up), heat (a temperature
# bit: 0x2/0x4/0x8 now, 0x20000/0x40000/0x80000 since start-up), both or
# none - or unknown when it cannot be read. The rig's stalls came with only
# the sticky soft-temperature bit (0x80000) and a steady 5.03 V, and a lower
# brightness did not help, so the power supply is blamed only for under-voltage.
stall_cause() {
    local t v power=0 heat=0
    command -v vcgencmd >/dev/null 2>&1 || { echo unknown; return 0; }
    t=$(vcgencmd get_throttled 2>/dev/null | sed -n 's/^throttled=//p' | head -1)
    case "$t" in 0x[0-9a-fA-F]*) v=$((t)) ;; *) echo unknown; return 0 ;; esac
    (( v & 0x10001 )) && power=1
    (( v & 0xE000E )) && heat=1
    case "$power$heat" in
        11) echo both ;; 10) echo power ;; 01) echo heat ;; *) echo none ;;
    esac
}

# One line on cooling for this Pi (a Pi 5 has the Active Cooler)
cooling_advice() {
    if tr -d '\0' < /proc/device-tree/model 2>/dev/null | grep -q "Pi 5" \
            || [ "${PI_MODEL:-}" = "Pi5" ]; then
        echo "On a Pi 5, fit the Active Cooler and check that its fan runs."
    else
        echo "Give the Pi a heatsink and room for air."
    fi
}

after_stall() {
    local since="${1:-0}" found recovered text offer=1
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
    case "$(stall_cause)" in
        power)
            text="$text The Pi reported too little power.\n\nUse the official Raspberry Pi 27 W power supply, or give the LED panel its own power." ;;
        both)
            text="$text The Pi reported too little power, and it got too hot.\n\nUse the official Raspberry Pi 27 W power supply, or give the LED panel its own power. $(cooling_advice)" ;;
        heat)
            offer=0
            text="$text The Pi got too hot and slowed down (its power was fine).\n\n$(cooling_advice)" ;;
        none)
            offer=0
            text="$text The Pi reported no power or heat problem.\n\nIf it happens again, check the power supply (the official 27 W one) and the cooling." ;;
        *)
            text="$text This happens when the power supply is too weak for the LEDs, or when the Pi is too hot.\n\nUse the official Raspberry Pi 27 W power supply, or give the LED panel its own power. $(cooling_advice)" ;;
    esac
    # A lower brightness only helps when the power may be short
    [ "$(current_level)" = "low" ] && offer=0
    [ "$offer" = 1 ] && text="$text\n\nA lower brightness draws less current. Raise it again any time: RasQberry menu > LEDs > LED brightness."
    if ! { [ -t 0 ] && [ -t 1 ]; } || ! command -v whiptail >/dev/null 2>&1; then
        warn "$(printf '%b' "$text" | tr '\n' ' ' | sed 's/  */ /g')"
        return 0
    fi
    if [ "$offer" != 1 ]; then
        show_msgbox "LED panel stopped" "$text" 12 70
        return 0
    fi
    if whiptail --title "LED panel stopped" --yes-button "Lower to 0.2" \
            --no-button "Keep ${LED_DEFAULT_BRIGHTNESS:-0.4}" \
            --yesno "$(printf '%b' "$text")" "$(_rq_dialog_height "$text" 70 12)" 70; then
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
    # One line to confirm (#29): the menu used to come straight back
    local label
    case "$pick" in
        low) label="Low (0.2)" ;; medium) label="Medium (0.3)" ;;
        normal) label="Normal (0.4)" ;; bright) label="Bright (0.6)" ;;
    esac
    show_msgbox "LED brightness" "Saved: ${label}. LED demos use it from their next start." 8 64
}

case "${1:-}" in
    "")            choose ;;
    --set)         set_level "${2:-}" ;;
    --after-stall) after_stall "${2:-0}" ;;
    --show)        echo "LED_DEFAULT_BRIGHTNESS=${LED_DEFAULT_BRIGHTNESS:-0.4} LED_MAX_BRIGHTNESS=${LED_MAX_BRIGHTNESS:-1.0} level=$(current_level)" ;;
    *)             die "Usage: rq_led_brightness.sh [--set LEVEL | --after-stall EPOCH | --show]" ;;
esac
