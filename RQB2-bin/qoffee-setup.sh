#!/bin/bash
set -euo pipefail

################################################################################
# qoffee-setup.sh - RasQberry Qoffee-Maker Setup
#
# Description:
#   Installs Docker and configures Qoffee-Maker demo
#   Handles Docker installation, user permissions, networking
#   Clones repository and creates configuration file
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Qoffee-Maker Setup ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR GIT_REPO_DEMO_QOFFEE

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"

################################################################################
# Docker installation check
################################################################################

# Check if Docker is already installed
if command -v docker &> /dev/null; then
    info "Docker is already installed (version: $(docker --version | cut -d' ' -f3 | tr -d ','))"
    DOCKER_INSTALLED=true
else
    info "Docker is not installed"
    DOCKER_INSTALLED=false
fi

################################################################################
# Install Docker if needed
################################################################################

if [ "$DOCKER_INSTALLED" = false ]; then
    echo
    info "Qoffee-Maker requires Docker to run"
    echo
    echo "Installation details:"
    echo "  - Download size: ~100-150 MB"
    echo "  - Installation time: 5-10 minutes"
    echo "  - Requires: Active internet connection"
    echo "  - Disk space needed: ~200 MB"
    echo

    # Prompt for confirmation
    if ! show_yesno "Install Docker?" \
        "Qoffee-Maker requires Docker Engine.\n\nInstall Docker now?\n\n• Size: ~100-150 MB download\n• Time: 5-10 minutes\n• Requires internet connection\n\nDocker containers are known to occasionally cause\nnetwork conflicts with AutoHotspot configurations."; then
        info "Installation cancelled by user"
        exit 1
    fi

    echo
    info "Installing Docker Engine..."
    info "This may take several minutes. Please be patient."
    echo

    # Download Docker installation script
    info "[1/4] Downloading Docker installation script..."
    if ! curl -fsSL https://get.docker.com -o /tmp/get-docker.sh; then
        show_msgbox "Installation Error" "Failed to download Docker installation script.\n\nPlease check your internet connection and try again."
        rm -f /tmp/get-docker.sh
        die "Failed to download Docker installation script"
    fi

    # Install Docker using official script
    info "[2/4] Installing Docker Engine (this takes a few minutes)..."
    if ! sh /tmp/get-docker.sh; then
        show_msgbox "Installation Error" "Docker installation failed.\n\nPlease check the terminal output for error details."
        rm -f /tmp/get-docker.sh
        die "Docker installation failed"
    fi

    # Add user to docker group
    info "[3/4] Configuring Docker permissions..."
    usermod -aG docker "$SUDO_USER_NAME"

    # Enable Docker service
    info "[4/4] Enabling Docker service..."
    systemctl enable docker

    # Clean up
    rm -f /tmp/get-docker.sh

    echo
    echo "✓ Docker installed successfully!"
    echo

    # Re-exec script with docker group active (avoids need to logout/login)
    # The 'sg' command starts a new shell with the docker group active,
    # so we can continue setup immediately without requiring user logout
    info "Activating Docker group permissions..."
    if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        # Use sg to run this script with docker group active
        exec sg docker -c "$0 $*"
    fi
fi

################################################################################
# Docker permissions check
################################################################################

# Check if user is in docker group (according to /etc/group)
if ! groups "$SUDO_USER_NAME" | grep -q docker; then
    warn "User '$SUDO_USER_NAME' is not in the docker group"
    info "Adding user to docker group..."
    usermod -aG docker "$SUDO_USER_NAME"

    # Re-exec with docker group active
    info "Activating Docker group permissions..."
    if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$0 $*"
    fi
fi

# Check if docker group is active in current session
# This handles the case where user was added to docker group previously
# but hasn't logged out/in yet. We use 'sg' to activate it immediately.
if ! groups | grep -q docker; then
    info "Docker group not active in current session"
    info "Activating Docker group permissions..."
    if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$0 $*"
    fi
fi

################################################################################
# Docker networking configuration
################################################################################

# Configure Docker networking (required for Qoffee-Maker)
info "Configuring Docker networking..."
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf 2>/dev/null; then
    sed -i "s/.*net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/g" /etc/sysctl.conf 2>/dev/null || \
        echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf > /dev/null
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    info "Docker networking configured"
fi

################################################################################
# Clone Qoffee-Maker repository
################################################################################

# Clone Qoffee-Maker repository if needed
# Check for marker file (qoffee.ipynb) to verify successful installation
if [ ! -f "$DEMO_DIR/qoffee.ipynb" ]; then
    echo
    info "Cloning Qoffee-Maker repository..."

    if ! clone_demo "$GIT_REPO_DEMO_QOFFEE" "$DEMO_DIR"; then
        # Clean up incomplete directory and show error
        rm -rf "$DEMO_DIR"
        show_msgbox "Clone Error" "Failed to clone Qoffee-Maker repository.\n\nPlease check your internet connection."
        die "Failed to clone Qoffee-Maker repository"
    fi
    info "Qoffee-Maker repository cloned"
else
    info "Qoffee-Maker repository already exists"

    # Update repository
    info "Updating Qoffee-Maker repository..."
    cd "$DEMO_DIR" && git pull --quiet origin main 2>/dev/null || true
    cd "$USER_HOME" || die "Failed to return to home directory"
fi

################################################################################
# Create configuration file
################################################################################

# Create .env configuration file if needed
ENV_FILE="$DEMO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo
    info "Creating configuration file..."

    # Check if env-template exists
    if [ -f "$DEMO_DIR/env-template" ]; then
        cp "$DEMO_DIR/env-template" "$ENV_FILE"
    else
        # Create default .env if template missing
        cat > "$ENV_FILE" << 'ENVEOF'
# Home Connect API Configuration
# Register at: https://developer.home-connect.com/
HOMECONNECT_API_URL=https://simulator.home-connect.com/
HOMECONNECT_CLIENT_ID=your_client_id_here
HOMECONNECT_CLIENT_SECRET=your_client_secret_here
HOMECONNECT_REDIRECT_URL=http://localhost:8887/auth/callback
DEVICE_HA_ID=

# IBM Quantum API Key
# Get your key at: https://quantum-computing.ibm.com/account
IBMQ_API_KEY=your_ibmq_api_key_here

# Jupyter Token (change for security)
JUPYTER_TOKEN=super-secret-token
ENVEOF
    fi

    # Fix ownership to user (not root)
    fix_ownership "$ENV_FILE" "$SUDO_USER_NAME"

    info "Configuration file created: $ENV_FILE"
    echo
    warn "CONFIGURATION REQUIRED!"
    echo
    echo "Before using Qoffee-Maker, you must configure:"
    echo "  1. Home Connect Developer Account"
    echo "     → https://developer.home-connect.com/"
    echo "  2. IBM Quantum Account"
    echo "     → https://quantum-computing.ibm.com/account"
    echo
    echo "Edit: $ENV_FILE"
    echo

    if show_yesno "Edit Configuration?" \
        "Configuration file created at:\n$ENV_FILE\n\nYou need to add your API credentials:\n• Home Connect Client ID & Secret\n• IBM Quantum API Key\n\nWould you like to edit it now?"; then
        ${EDITOR:-nano} "$ENV_FILE"
    fi
else
    info "Configuration file exists: $ENV_FILE"
fi

################################################################################
# Complete setup
################################################################################

echo
echo "=== Setup Complete ==="
echo
echo "Qoffee-Maker is ready to use!"
echo "You can now run it from:"
echo "  • RasQberry menu → Quantum Demos → Qoffee-Maker"
echo "  • Desktop shortcut"
echo "  • Command line: $BIN_DIR/qoffee-maker.sh"
echo

# Update environment variable
update_env_var "QOFFEE_MAKER_INSTALLED" "true"

exit 0
