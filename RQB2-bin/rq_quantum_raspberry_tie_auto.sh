#!/bin/bash
#
# RasQberry: Auto-installing Quantum Raspberry Tie Demo Launcher
# Automatically installs demo if missing, then launches it
#

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
else
    echo "Error: Environment config not found at /usr/config/rasqberry_env-config.sh"
    exit 1
fi

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    exit 1
fi

DEMO_DIR="$USER_HOME/$REPO/demos/quantum-raspberry-tie"

# Check if demo is installed, auto-install if missing
# (check for both old and new versions of the main file)
if [ ! -f "$DEMO_DIR/QuantumRaspberryTie.qk1.py" ] && [ ! -f "$DEMO_DIR/QuantumRaspberryTie.v7_1.py" ]; then
    echo "Quantum Raspberry Tie demo not found. Installing..."
    if ! sudo raspi-config nonint do_rasp_tie_install; then
        echo "Installation failed."
        exit 1
    fi
fi

# Activate virtual environment if available
if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Variable to track the Python process
PYTHON_PID=""

# Function to clean up on exit
cleanup() {
    echo
    echo "Stopping Quantum Raspberry Tie demo..."

    # Kill the Python process if it's still running
    if [ -n "$PYTHON_PID" ] && kill -0 "$PYTHON_PID" 2>/dev/null; then
        kill "$PYTHON_PID" 2>/dev/null || true
        sleep 0.5

        # Force kill if still running
        if kill -0 "$PYTHON_PID" 2>/dev/null; then
            kill -9 "$PYTHON_PID" 2>/dev/null || true
        fi
    fi

    # Also kill any remaining python processes running the demo
    pkill -f "QuantumRaspberryTie.v7_1.py" 2>/dev/null || true

    echo "Demo stopped."
}

# Set up trap to clean up on exit
trap cleanup EXIT INT TERM

# Launch the demo
echo "Starting Quantum Raspberry Tie Demo..."
echo "========================================="

cd "$DEMO_DIR" || exit 1

# Run the demo in background
python3 QuantumRaspberryTie.v7_1.py &
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