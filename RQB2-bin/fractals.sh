#!/bin/bash
#
# RasQberry-Two: Quantum Fractals Demo
# Creates animated fractal visualizations using quantum circuits
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

echo; echo; echo "Quantum Fractals Demo"

# Check for GUI/Desktop environment
if [ -z "$DISPLAY" ]; then
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
    exit 1
fi

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables
. "/usr/config/rasqberry_env-config.sh"

DEMO_DIR="$USER_HOME/.local/bin/fractal_files"

echo "Starting Quantum Fractals Demo..."
echo "User: $USER_NAME"
echo "Demo directory: $DEMO_DIR"

# Check if demo files exist
if [ ! -f "$DEMO_DIR/fractals.py" ]; then
    echo "Error: Fractals demo not found at $DEMO_DIR"
    echo "Please ensure the demo is properly installed."
    exit 1
fi

# Ensure virtual environment is activated
if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Change to demo directory and run
cd "$DEMO_DIR" || exit 1
python3 fractals.py
EXIT_CODE=$?

cd "$USER_HOME" || exit

# Show completion message
echo
if [ $EXIT_CODE -eq 0 ]; then
    echo "Fractals demo completed successfully."
else
    echo "Fractals demo exited with errors (code: $EXIT_CODE)"
fi
echo
read -p "Press Enter to close this window..."
