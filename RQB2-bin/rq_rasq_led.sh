#!/bin/bash
set -euo pipefail

################################################################################
# rq_rasq_led.sh - RasQberry RasQ-LED Quantum Circuit Demo Launcher
#
# Description:
#   Visualizes quantum circuits with entanglement patterns on LEDs
#   Simple launcher for the RasQ-LED Python script
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Root for the panel check, the Pi 4 renderer and clearing; the LED program
# itself runs as the user in a sandbox (rq_led_as_user)
ensure_root "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV BIN_DIR

# Another program on the LED panel? Name it and offer to stop it (R-162)
led_panel_ready || exit 0

# Activate virtual environment if available
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Launch RasQ-LED demo
info "Starting RasQ-LED Quantum Circuit Demo..."
# Not exec: the EXIT trap clears the panel when the window is closed (R-158)
rq_led_clear_on_exit
rq_led_user_prepare
rq_run_in_front rq_led_as_user python3 "$BIN_DIR/RasQ-LED.py"
