#!/bin/bash
#
# RasQberry: Auto-installing Quantum Lights Out Demo Launcher
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

DEMO_DIR="$HOME/$REPO/Quantum-Lights-Out"

# Function to install demo
install_quantum_lights_out() {
    echo "Installing Quantum Lights Out demo..."
    
    # Remove existing incomplete directory if it exists
    if [ -d "$DEMO_DIR" ]; then
        echo "Removing existing incomplete installation..."
        rm -rf "$DEMO_DIR"
    fi
    
    # Clone the repository
    if git clone --depth 1 "$GIT_REPO_DEMO_QLO" "$DEMO_DIR"; then
        # Verify the main file exists
        if [ ! -f "$DEMO_DIR/lights_out.py" ]; then
            echo "Error: lights_out.py not found in cloned repository"
            echo "Directory contents:"
            ls -la "$DEMO_DIR"
            rm -rf "$DEMO_DIR"
            return 1
        fi
        
        # Update environment to mark as installed
        sed -i 's/QUANTUM_LIGHTS_OUT_INSTALLED=false/QUANTUM_LIGHTS_OUT_INSTALLED=true/' "$HOME/.local/config/rasqberry_environment.env"
        
        # Reload environment
        . "$HOME/.local/config/env-config.sh"
        
        echo "Quantum Lights Out demo installed successfully"
        return 0
    else
        # Clean up on failure
        rm -rf "$DEMO_DIR"
        echo "Failed to install Quantum Lights Out demo"
        echo "Please check your internet connection and try again"
        return 1
    fi
}

# Check if demo is installed
if [ ! -f "$DEMO_DIR/lights_out.py" ]; then
    echo "Quantum Lights Out demo not found. Installing..."
    if ! install_quantum_lights_out; then
        echo "Installation failed. Please try running from the RasQberry menu."
        exit 1
    fi
fi

# Activate virtual environment if available
if [ -f "$HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch the demo
echo "Launching demo from: $DEMO_DIR"
if [ ! -d "$DEMO_DIR" ]; then
    echo "Error: Demo directory does not exist: $DEMO_DIR"
    exit 1
fi

if [ ! -f "$DEMO_DIR/lights_out.py" ]; then
    echo "Error: lights_out.py not found in $DEMO_DIR"
    echo "Directory contents:"
    ls -la "$DEMO_DIR"
    exit 1
fi

cd "$DEMO_DIR" && python3 lights_out.py