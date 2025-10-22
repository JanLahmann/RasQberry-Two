#!/bin/bash
set -euo pipefail

################################################################################
# fractals.sh - RasQberry Quantum Fractals Demo
#
# Description:
#   Creates animated fractal visualizations using quantum circuits
#   Requires graphical desktop environment (GUI)
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo; echo; echo "Quantum Fractals Demo"

# Check for GUI/Desktop environment
if ! check_display; then
    echo ""
    echo "=========================================="
    echo "ERROR: Graphical Desktop Required"
    echo "=========================================="
    echo ""
    echo "This demo requires a graphical desktop environment (GUI)."
    echo "It cannot run from a terminal-only session."
    echo ""
    echo "To run this demo:"
    echo "  1. Connect via VNC or use the desktop environment"
    echo "  2. Open a terminal in the desktop"
    echo "  3. Run this demo from there"
    echo ""
    echo "Or use the desktop launcher icon instead."
    echo ""
    die "No display available"
fi

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV

DEMO_DIR="$USER_HOME/.local/bin/fractal_files"

info "Starting Quantum Fractals Demo..."
debug "User: $SUDO_USER_NAME"
debug "Demo directory: $DEMO_DIR"

# Check if demo files exist
[ -f "$DEMO_DIR/fractals.py" ] || die "Fractals demo not found at $DEMO_DIR. Please ensure the demo is properly installed."

# Activate virtual environment
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Change to demo directory and run
cd "$DEMO_DIR" || die "Failed to change to demo directory"
python3 fractals.py
EXIT_CODE=$?

cd "$USER_HOME" || warn "Failed to return to home directory"

# Show completion message
echo
if [ $EXIT_CODE -eq 0 ]; then
    info "Fractals demo completed successfully"
else
    warn "Fractals demo exited with errors (code: $EXIT_CODE)"
fi
echo
read -p "Press Enter to close this window..."
