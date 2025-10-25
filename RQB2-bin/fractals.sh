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

# Check for fractals in system directory (preferred) or user directory (legacy)
if [ -d "/usr/bin/fractal_files" ]; then
    DEMO_DIR="/usr/bin/fractal_files"
elif [ -d "$USER_HOME/.local/bin/fractal_files" ]; then
    DEMO_DIR="$USER_HOME/.local/bin/fractal_files"
else
    die "Fractals demo not found. Expected locations:\n  - /usr/bin/fractal_files\n  - $USER_HOME/.local/bin/fractal_files"
fi

info "Starting Quantum Fractals Demo..."
debug "User: $(get_user_name)"
debug "Demo directory: $DEMO_DIR"

# Verify the fractals.py file exists
[ -f "$DEMO_DIR/fractals.py" ] || die "fractals.py not found in $DEMO_DIR"

# Activate virtual environment
activate_venv || warn "Virtual environment not available, continuing anyway..."

# Change to demo directory and run
cd "$DEMO_DIR" || die "Failed to change to demo directory"

# Run as actual user (not root) to avoid Chrome/display permission issues
# When launched from raspi-config, this ensures Chrome can access the user's display
run_as_user python3 fractals.py
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
