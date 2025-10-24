#!/bin/bash
#
# RasQberry: Auto-installing Quantum Raspberry Tie Demo Launcher
# Automatically installs demo if missing, then launches it
#

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

# Demo configuration
DEMO_NAME="quantum-raspberry-tie"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")

# Variable to track the Python process
PYTHON_PID=""

# Function to clean up on exit
cleanup() {
    echo
    info "Stopping Quantum Raspberry Tie demo..."

    # Kill the Python process if it's still running
    if [ -n "$PYTHON_PID" ] && kill -0 "$PYTHON_PID" 2>/dev/null; then
        kill "$PYTHON_PID" 2>/dev/null || true
        sleep 0.5

        # Force kill if still running
        if kill -0 "$PYTHON_PID" 2>/dev/null; then
            kill -9 "$PYTHON_PID" 2>/dev/null || true
        fi
    fi

    # Use common cleanup for remaining processes and LEDs
    default_demo_cleanup "QuantumRaspberryTie.v7_1.py"

    echo "Demo stopped."
}

# Set up trap to clean up on exit
setup_cleanup_trap cleanup

# Check if demo is installed, auto-install if missing
# (check for both old and new versions of the main file)
if [ ! -f "$DEMO_DIR/QuantumRaspberryTie.qk1.py" ] && [ ! -f "$DEMO_DIR/QuantumRaspberryTie.v7_1.py" ]; then
    info "Quantum Raspberry Tie demo not found. Installing..."
    install_demo_raspiconfig do_rasp_tie_install || die "Installation failed"
fi

# Activate virtual environment
activate_venv || warn "Virtual environment not available"

# Launch the demo
echo "Starting Quantum Raspberry Tie Demo..."
echo "========================================="

cd "$DEMO_DIR" || die "Cannot change to demo directory"

# Run the demo in background with default backend (local Aer simulator)
# The script requires a backend argument, use -b:aer for local simulation
python3 QuantumRaspberryTie.v7_1.py -b:aer &
PYTHON_PID=$!

echo "Demo is running (PID: $PYTHON_PID)"
echo ""
echo "To stop the demo:"
echo "  - Press 'q' and Enter"
echo "  - Or just press Enter"
echo "  - Or press Ctrl+C"
echo ""
echo "Note: Closing only the SenseHAT window will NOT stop the demo!"
echo "========================================="
echo ""

# Wait for user input to quit
while kill -0 "$PYTHON_PID" 2>/dev/null; do
    read -t 1 -n 1 key 2>/dev/null
    if [ $? -eq 0 ]; then
        # User pressed a key
        if [ "$key" = "q" ] || [ "$key" = "" ]; then
            echo ""
            echo "Stop requested by user..."
            break
        fi
    fi
done

# Check if process is still running
if kill -0 "$PYTHON_PID" 2>/dev/null; then
    # Process still running, user wants to quit
    echo "Stopping demo..."
    EXIT_CODE=0
else
    # Process already exited
    wait "$PYTHON_PID"
    EXIT_CODE=$?
fi

# Show exit status
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "Demo finished successfully."
else
    echo "Demo exited with code: $EXIT_CODE"
fi
echo ""
echo "Press Enter to close this window..."
read
