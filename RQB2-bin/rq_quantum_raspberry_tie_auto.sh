#!/bin/bash
#
# RasQberry: Auto-installing Quantum Raspberry Tie Demo Launcher
# Automatically installs demo if missing, then launches it
#

# Ensure HOME is set (for desktop launchers)
if [ -z "$HOME" ]; then
    HOME="/home/$(whoami)"
fi

# Load environment variables
if [ -f "$HOME/.local/config/env-config.sh" ]; then
    . "$HOME/.local/config/env-config.sh"
else
    echo "Error: Environment config not found at $HOME/.local/config/env-config.sh"
    exit 1
fi

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    exit 1
fi

DEMO_DIR="$HOME/$REPO/quantum-raspberry-tie"

# Function to install demo
install_quantum_raspberry_tie() {
    echo "Installing Quantum Raspberry Tie demo..."
    
    # Clone the repository
    if git clone --depth 1 "$GIT_REPO_DEMO_QRT" "$DEMO_DIR"; then
        # Update environment to mark as installed
        sed -i 's/QUANTUM_RASPBERRY_TIE_INSTALLED=false/QUANTUM_RASPBERRY_TIE_INSTALLED=true/' "$HOME/.local/config/rasqberry_environment.env"
        
        # Reload environment
        . "$HOME/.local/config/env-config.sh"
        
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
if [ ! -f "$DEMO_DIR/quantum_raspberry_tie.py" ]; then
    echo "Quantum Raspberry Tie demo not found. Installing..."
    if ! install_quantum_raspberry_tie; then
        echo "Installation failed. Please try running from the RasQberry menu."
        exit 1
    fi
fi

# Activate virtual environment if available
if [ -f "$HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch the demo
cd "$DEMO_DIR" && python3 quantum_raspberry_tie.py