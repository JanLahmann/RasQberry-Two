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

# Ensure running as root (PWM/PIO LED drivers require GPIO access)
ensure_root "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV BIN_DIR

# Activate virtual environment if available
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Launch RasQ-LED demo
info "Starting RasQ-LED Quantum Circuit Demo..."
exec python3 "$BIN_DIR/RasQ-LED.py"
