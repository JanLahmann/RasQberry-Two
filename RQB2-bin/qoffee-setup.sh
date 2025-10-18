#!/bin/bash
#
# RasQberry-Two: Qoffee-Maker Setup
# Installs Docker and configures Qoffee-Maker demo
#

echo
echo "=== Qoffee-Maker Setup ==="
echo

# Load environment variables
. "$HOME/.local/config/env-config.sh"

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"

# Check if Docker is already installed
if command -v docker &> /dev/null; then
    echo "✓ Docker is already installed (version: $(docker --version | cut -d' ' -f3 | tr -d ','))"
    DOCKER_INSTALLED=true
else
    echo "Docker is not installed."
    DOCKER_INSTALLED=false
fi

# Install Docker if needed
if [ "$DOCKER_INSTALLED" = false ]; then
    echo
    echo "Qoffee-Maker requires Docker to run."
    echo
    echo "Installation details:"
    echo "  - Download size: ~100-150 MB"
    echo "  - Installation time: 5-10 minutes"
    echo "  - Requires: Active internet connection"
    echo "  - Disk space needed: ~200 MB"
    echo

    # Prompt for confirmation
    if ! whiptail --title "Install Docker?" --yesno \
        "Qoffee-Maker requires Docker Engine.\n\nInstall Docker now?\n\n• Size: ~100-150 MB download\n• Time: 5-10 minutes\n• Requires internet connection\n\nDocker containers are known to occasionally cause\nnetwork conflicts with AutoHotspot configurations." \
        16 65; then
        echo "Installation cancelled by user."
        exit 1
    fi

    echo
    echo "Installing Docker Engine..."
    echo "This may take several minutes. Please be patient."
    echo

    # Download Docker installation script
    echo "[1/4] Downloading Docker installation script..."
    if ! curl -fsSL https://get.docker.com -o /tmp/get-docker.sh; then
        whiptail --title "Installation Error" --msgbox \
            "Failed to download Docker installation script.\n\nPlease check your internet connection and try again." \
            10 60
        rm -f /tmp/get-docker.sh
        exit 1
    fi

    # Install Docker using official script
    echo "[2/4] Installing Docker Engine (this takes a few minutes)..."
    if ! sudo sh /tmp/get-docker.sh; then
        whiptail --title "Installation Error" --msgbox \
            "Docker installation failed.\n\nPlease check the terminal output for error details." \
            10 60
        rm -f /tmp/get-docker.sh
        exit 1
    fi

    # Add user to docker group
    echo "[3/4] Configuring Docker permissions..."
    sudo usermod -aG docker "$USER_NAME"

    # Enable Docker service
    echo "[4/4] Enabling Docker service..."
    sudo systemctl enable docker

    # Clean up
    rm -f /tmp/get-docker.sh

    echo
    echo "✓ Docker installed successfully!"
    echo

    # Re-exec script with docker group active (avoids need to logout/login)
    # The 'sg' command starts a new shell with the docker group active,
    # so we can continue setup immediately without requiring user logout
    echo "Activating Docker group permissions..."
    if [ -z "$DOCKER_GROUP_ACTIVATED" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        # Use sg to run this script with docker group active
        exec sg docker -c "$0 $*"
    fi
fi

# Check if user is in docker group (according to /etc/group)
if ! groups "$USER_NAME" | grep -q docker; then
    echo "⚠  Warning: User '$USER_NAME' is not in the docker group."
    echo "   Adding user to docker group..."
    sudo usermod -aG docker "$USER_NAME"

    # Re-exec with docker group active
    echo "Activating Docker group permissions..."
    if [ -z "$DOCKER_GROUP_ACTIVATED" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$0 $*"
    fi
fi

# Check if docker group is active in current session
# This handles the case where user was added to docker group previously
# but hasn't logged out/in yet. We use 'sg' to activate it immediately.
if ! groups | grep -q docker; then
    echo "Docker group not active in current session."
    echo "Activating Docker group permissions..."
    if [ -z "$DOCKER_GROUP_ACTIVATED" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$0 $*"
    fi
fi

# Configure Docker networking (required for Qoffee-Maker)
echo "Configuring Docker networking..."
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf 2>/dev/null; then
    sudo sed -i "s/.*net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/g" /etc/sysctl.conf 2>/dev/null || \
        echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf > /dev/null
    sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null
    echo "✓ Docker networking configured"
fi

# Clone Qoffee-Maker repository if needed
if [ ! -d "$DEMO_DIR" ]; then
    echo
    echo "Cloning Qoffee-Maker repository..."
    mkdir -p "$USER_HOME/$REPO/demos"

    if git clone --depth 1 https://github.com/JanLahmann/Qoffee-Maker.git "$DEMO_DIR"; then
        # Fix ownership if cloned as root
        if [ "$(stat -c '%U' "$DEMO_DIR" 2>/dev/null || stat -f '%Su' "$DEMO_DIR")" = "root" ]; then
            sudo chown -R "$USER_NAME":"$USER_NAME" "$DEMO_DIR"
        fi
        echo "✓ Qoffee-Maker repository cloned"
    else
        whiptail --title "Clone Error" --msgbox \
            "Failed to clone Qoffee-Maker repository.\n\nPlease check your internet connection." \
            10 60
        exit 1
    fi
else
    echo "✓ Qoffee-Maker repository already exists"

    # Update repository
    echo "Updating Qoffee-Maker repository..."
    cd "$DEMO_DIR" && git pull --quiet origin main 2>/dev/null || true
    cd "$USER_HOME" || exit
fi

# Create .env configuration file if needed
ENV_FILE="$DEMO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo
    echo "Creating configuration file..."

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

    # Fix ownership
    if [ "$(stat -c '%U' "$ENV_FILE" 2>/dev/null || stat -f '%Su' "$ENV_FILE")" = "root" ]; then
        sudo chown "$USER_NAME":"$USER_NAME" "$ENV_FILE"
    fi

    echo "✓ Configuration file created: $ENV_FILE"
    echo
    echo "⚠  CONFIGURATION REQUIRED!"
    echo
    echo "Before using Qoffee-Maker, you must configure:"
    echo "  1. Home Connect Developer Account"
    echo "     → https://developer.home-connect.com/"
    echo "  2. IBM Quantum Account"
    echo "     → https://quantum-computing.ibm.com/account"
    echo
    echo "Edit: $ENV_FILE"
    echo

    if whiptail --title "Edit Configuration?" --yesno \
        "Configuration file created at:\n$ENV_FILE\n\nYou need to add your API credentials:\n• Home Connect Client ID & Secret\n• IBM Quantum API Key\n\nWould you like to edit it now?" \
        16 65; then
        ${EDITOR:-nano} "$ENV_FILE"
    fi
else
    echo "✓ Configuration file exists: $ENV_FILE"
fi

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
update_environment_file "QOFFEE_MAKER_INSTALLED" "true"

exit 0
