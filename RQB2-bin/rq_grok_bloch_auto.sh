#!/bin/bash
#
# RasQberry: Auto-installing Grok Bloch Sphere Demo Launcher
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

DEMO_DIR="$HOME/$REPO/demos/grok-bloch"

# Function to install demo (based on menu system)
install_grok_bloch() {
    echo "Installing Grok Bloch demo..."
    
    # Create demo directory
    mkdir -p "$DEMO_DIR"
    
    # Clone the repository
    if git clone --depth 1 "$GIT_REPO_DEMO_GROK_BLOCH" "$DEMO_DIR"; then
        # Update environment to mark as installed
        sed -i 's/GROK_BLOCH_INSTALLED=false/GROK_BLOCH_INSTALLED=true/' "$HOME/.local/config/rasqberry_environment.env"
        
        # Reload environment
        . "$HOME/.local/config/env-config.sh"
        
        echo "Grok Bloch demo installed successfully"
        return 0
    else
        # Clean up on failure
        rm -rf "$DEMO_DIR"
        echo "Failed to install Grok Bloch demo"
        echo "Please check your internet connection and try again"
        return 1
    fi
}

# Check if demo is installed
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Grok Bloch demo not found. Installing..."
    if ! install_grok_bloch; then
        echo "Installation failed. Please try running from the RasQberry menu."
        exit 1
    fi
fi

# Launch the demo using the existing launcher
exec "$BIN_DIR/rq_grok_bloch.sh"