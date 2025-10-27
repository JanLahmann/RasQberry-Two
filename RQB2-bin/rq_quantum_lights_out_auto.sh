#!/bin/bash
#
# RasQberry: Quantum Lights Out Demo Launcher
# Launches the Quantum Lights Out demo
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Ensure running as root (PWM/PIO LED drivers require GPIO access)
ensure_root "$@"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV MARKER_QLO

# Demo configuration
DEMO_NAME="Quantum-Lights-Out"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")

# Check if demo is installed, auto-install if missing
if [ ! -f "$DEMO_DIR/$MARKER_QLO" ]; then
    info "Quantum Lights Out demo not found. Installing..."
    install_demo_raspiconfig do_qlo_install || die "Installation failed"
fi

# Activate virtual environment
activate_venv || warn "Virtual environment not available"

# Launch the demo
info "Launching demo from: $DEMO_DIR"
ensure_demo_dir "$DEMO_NAME" >/dev/null || die "Demo directory not found"

if [ ! -f "$DEMO_DIR/$MARKER_QLO" ]; then
    die "$MARKER_QLO not found in $DEMO_DIR"
fi

cd "$DEMO_DIR" || die "Cannot change to demo directory"

echo ""
echo "Quantum Lights Out Demo"
echo "======================="
echo "Press Ctrl+C or 'q' in the game to exit"
echo ""

# Run the demo and capture exit status
python3 -W ignore::DeprecationWarning lights_out.py
EXIT_CODE=$?

# Show friendly exit message
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "Demo finished successfully."
else
    echo "Demo exited with code: $EXIT_CODE"
fi
echo ""
echo "Press Enter to close this window..."
read
