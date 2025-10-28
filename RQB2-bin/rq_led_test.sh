#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_test.sh - RasQberry LED Test Utility Launcher
#
# Description:
#   Interactive LED strip testing with configurable parameters
#   Supports both manual testing and automated parameter scanning
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Ensure running as root (PWM/PIO drivers require GPIO access)
ensure_root "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV BIN_DIR

# Activate virtual environment if available
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Change to home directory to avoid permission issues with lgpio temp files
cd "$USER_HOME" || cd /tmp

# Launch LED test utility
info "Starting LED Test Utility..."
exec python3 "$BIN_DIR/rq_led_test.py" "$@"