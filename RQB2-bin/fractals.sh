#!/bin/bash
#
# RasQberry-Two: Quantum Fractals Demo
# Creates animated fractal visualizations using quantum circuits
#

echo; echo; echo "Quantum Fractals Demo"

# Load environment variables
. $HOME/.local/bin/env-config.sh

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

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
cd "$USER_HOME" || exit
