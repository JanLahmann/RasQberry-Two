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
if [ -f "$USER_HOME/.local/config/env-config.sh" ]; then
    . "$USER_HOME/.local/config/env-config.sh"
else
    echo "Error: Environment config not found at $USER_HOME/.local/config/env-config.sh"
    exit 1
fi

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    exit 1
fi

DEMO_DIR="$USER_HOME/$REPO/demos/quantum-raspberry-tie"

# Function to install demo
install_quantum_raspberry_tie() {
    echo "Installing Quantum Raspberry Tie demo..."
    
    # Remove existing incomplete directory if it exists
    if [ -d "$DEMO_DIR" ]; then
        echo "Removing existing incomplete installation..."
        rm -rf "$DEMO_DIR"
    fi
    
    # Clone the repository
    if git clone --depth 1 "$GIT_REPO_DEMO_QRT" "$DEMO_DIR"; then
        # Update environment to mark as installed
        sed -i 's/QUANTUM_RASPBERRY_TIE_INSTALLED=false/QUANTUM_RASPBERRY_TIE_INSTALLED=true/' "$USER_HOME/.local/config/rasqberry_environment.env"

        # Reload environment
        . "$USER_HOME/.local/config/env-config.sh"

        echo "Quantum Raspberry Tie demo installed successfully"
        return 0
    else
        # Clean up on failure
        rm -rf "$DEMO_DIR"
        echo "Failed to install Quantum Raspberry Tie demo"
        echo "Please check your internet connection and try again"
        return 1
    fi
}

# Check if demo is installed
if [ ! -f "$DEMO_DIR/QuantumRaspberryTie.v7_1.py" ]; then
    echo "Quantum Raspberry Tie demo not found. Installing..."
    if ! install_quantum_raspberry_tie; then
        echo "Installation failed. Please try running from the RasQberry menu."
        exit 1
    fi
fi

# Activate virtual environment if available
if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Function to clean up on exit
cleanup() {
    echo
    echo "Stopping Quantum Raspberry Tie demo..."
    # Kill any remaining python processes running the demo
    pkill -f "QuantumRaspberryTie.v7_1.py" 2>/dev/null || true
    echo "Demo stopped."
}

# Set up trap to clean up on exit
trap cleanup EXIT INT TERM

# Launch the demo
echo "Starting Quantum Raspberry Tie Demo..."
echo "========================================="
echo "To stop the demo: Press Ctrl+C in this terminal"
echo "Note: Closing only the SenseHAT window will NOT stop the demo!"
echo "========================================="
echo

cd "$DEMO_DIR" && python3 QuantumRaspberryTie.v7_1.py