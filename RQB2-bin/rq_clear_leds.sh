#!/bin/bash
set -euo pipefail

################################################################################
# rq_clear_leds.sh - RasQberry Clear All LEDs
#
# Description:
#   Turns off all LEDs on the LED panel. A program that still holds the panel
#   (a demo left running, the IP scroll at start-up) is named first, and
#   stopped if you agree; a failed clear is reported as a failure (R-148).
#
# Usage:
#   rq_clear_leds.sh            clear; in a terminal, ask before stopping a holder
#   rq_clear_leds.sh --stop     stop whatever holds the panel, then clear
#   rq_clear_leds.sh --holders  list the programs holding the panel ("PID name"
#                               lines); exit 0 if there are any, 1 if none
#                               (the RasQberry menu asks this)
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Ensure running as root (PWM/PIO drivers require GPIO access)
ensure_root "$@"

# Load environment
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV BIN_DIR

MODE="ask"
case "${1:-}" in
    --stop)    MODE="stop" ;;
    --holders) MODE="holders" ;;
    "")        ;;
    *)         die "Usage: rq_clear_leds.sh [--stop|--holders]" ;;
esac

# Started from the desktop icon, the window closes when we exit: keep a
# failure readable.
fail() {
    echo "ERROR: $*" >&2
    if [ "$MODE" = "ask" ] && [ -t 0 ] && [ -t 1 ]; then
        echo
        read -r -p "Press Enter to close this window..." _ || true
    fi
    exit 1
}

HOLDERS=$(led_holders)

if [ "$MODE" = "holders" ]; then
    [ -n "$HOLDERS" ] || exit 1
    echo "$HOLDERS"
    exit 0
fi

if [ -n "$HOLDERS" ]; then
    if [ "$MODE" = "ask" ]; then
        echo "The LED panel is in use by:"
        echo "$HOLDERS" | sed 's/^[0-9]* /  /'
        if ! { [ -t 0 ] && [ -t 1 ]; }; then
            fail "Not cleared: stop that program first (rq_clear_leds.sh --stop stops it)."
        fi
        read -r -p "Stop it and turn the LEDs off? [Y/n] " answer || answer="n"
        case "$answer" in
            [nN]*) fail "Not cleared: the program still uses the LED panel." ;;
        esac
    fi
    stop_led_holders "$HOLDERS"
fi

# Activate virtual environment (required for LED utilities)
activate_venv || fail "The RasQberry Python environment is missing, so the LEDs cannot be cleared."

LED_SCRIPT=$(find_led_script "turn_off_LEDs.py") || fail "turn_off_LEDs.py not found."

# turn_off_LEDs.py exits 1 when the panel could not be cleared ("GPIO busy").
# One more try after a moment: a program that just ended may still hold it.
if python3 "$LED_SCRIPT" || { sleep 1; python3 "$LED_SCRIPT"; }; then
    echo "All LEDs are off."
    # The desktop icon's window closes when this ends: keep the line long
    # enough to be read (#29: "Clear All LEDs runs silently"; 2 s were too
    # short, user test 2026-10-07)
    if [ "$MODE" = "ask" ] && [ -t 0 ] && [ -t 1 ]; then
        echo "This window closes in a few seconds (Enter closes it now)."
        read -r -t "${RQ_CLEAR_LEDS_PAUSE:-8}" _ || true
    fi
else
    fail "The LEDs could not be cleared (see the message above)."
fi
