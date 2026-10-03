#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_ibm_demo.sh - RasQberry LED IBM Demo Launcher
#
# Description:
#   Simple wrapper to run the IBM-themed LED demonstration
#   Displays IBM logo and animations on LED strip
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Ensure running as root (PWM/PIO drivers require GPIO access)
ensure_root "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR STD_VENV

# Check multiple possible locations for the script. Uses the colourful rainbow
# rq_led_ibm_logo.py (procedural I=green/B=red/M=blue + per-row rainbow), now
# glyph-flipped to render upright on the top-origin xy canvas. (The PIL-based
# demo_led_ibm_logo.py renders a flat blue block-letter PNG and is kept as a
# fallback only.)
LED_SCRIPT=""
for location in "$BIN_DIR/rq_led_ibm_logo.py" \
                "/usr/bin/rq_led_ibm_logo.py" \
                "$USER_HOME/$REPO/RQB2-bin/rq_led_ibm_logo.py" \
                "$BIN_DIR/demo_led_ibm_logo.py" \
                "/usr/bin/demo_led_ibm_logo.py"; do
    if [ -f "$location" ]; then
        LED_SCRIPT="$location"
        break
    fi
done

[ -n "$LED_SCRIPT" ] || die "LED demo script not found. Searched:\n  - $BIN_DIR/rq_led_ibm_logo.py\n  - /usr/bin/rq_led_ibm_logo.py\n  - $USER_HOME/$REPO/RQB2-bin/rq_led_ibm_logo.py"

# The panel must be free (R-162), and is cleared when the window is closed
# or the demo stopped (R-158)
led_panel_ready || exit 0
rq_led_clear_on_exit

info "Starting LED IBM Demo..."
debug "Script location: $LED_SCRIPT"
echo

# Activate virtual environment if available
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Run the script. It stops with Enter or Ctrl+C, and the window closes with
# it (one Enter, not a second "close this window" prompt); an error keeps the
# window open (rq_hold_on_error.sh).
python3 "$LED_SCRIPT"
