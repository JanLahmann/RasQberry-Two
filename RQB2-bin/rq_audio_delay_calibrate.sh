#!/bin/bash
set -euo pipefail
# ============================================================================
# RasQberry: Calibrate the sound delay with a tick and a flash
# ============================================================================
# Description: Four ticks in a quickening rhythm and the LED panel flashes with them.
#   The user changes the delay until both come together, and Enter saves it
#   as RQ_AUDIO_DELAY_MS (the LEDs of demos with sound wait that long for a
#   Bluetooth speaker). RasQberry menu: Desktop Settings > Sound delay.
# Usage: rq_audio_delay_calibrate.sh   (in a terminal window)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Root for the panel check, the Pi 4 renderer, clearing and saving; the tick
# and the flash run as the user in the LED sandbox (rq_led_as_user)
ensure_root "$@"

load_rqb2_env
verify_env_vars USER_HOME BIN_DIR

rq_demo_header "Sound delay"

# The tick has to be heard: the default output, as for a demo with sound
rc=0
out=$(rq_audio_output) || rc=$?
if [ "$rc" -eq 1 ]; then
    echo "No sound output found. $RQ_SPEAKER_HINT"
    exit 0
elif [ "$rc" -eq 0 ]; then
    info "The tick plays on: $out (turn the speaker on and the volume up)."
    if rq_audio_on_jack; then
        warn "This is the headphone jack, which uses the same hardware as the LED panel: with the LEDs on, the sound can stop until the Pi restarts. A wired speaker needs no delay anyway; calibrate with the Bluetooth speaker you use."
    fi
fi
echo

led_panel_ready || exit 0
rq_led_clear_on_exit

# The value comes back in a file the user can write. Removed however the
# script ends: Ctrl+C ends it through rq_led_clear_on_exit's INT trap.
result=$(mktemp /tmp/rq-audio-delay.XXXXXX)
trap '_ad_rc=$?; rm -f "$result"; _rq_led_on_exit "$_ad_rc"' EXIT
chown "$(get_user_name)" "$result" 2>/dev/null || true

activate_venv || warn "Virtual environment not available, continuing anyway..."
rq_led_user_prepare
rc=0
rq_run_in_front rq_led_as_user python3 "$BIN_DIR/rq_audio_delay_calibrate.py" \
    --start "$(rq_audio_delay_ms)" --out "$result" || rc=$?

value=$(tr -dc '0-9' < "$result" 2>/dev/null || true)
rm -f "$result"
# 0: saved or cancelled (no value), 130: Ctrl+C; anything else is an error
case "$rc" in
    0|130) ;;
    *) die "The calibration stopped with an error; the sound delay stays as it was." ;;
esac
if [ "$rc" -eq 0 ] && [ -n "$value" ]; then
    RQ_AUDIO_DELAY_MS="$value"
    value=$(rq_audio_delay_ms)
    update_env_var RQ_AUDIO_DELAY_MS "$value" || die "The sound delay could not be saved."
    info "Demos with sound now use a sound delay of $value ms."
fi
