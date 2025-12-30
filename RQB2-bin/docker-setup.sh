#!/bin/bash
set -euo pipefail

################################################################################
# docker-setup.sh - RasQberry Docker Setup
#
# Description:
#   Installs Docker and configures permissions for RasQberry demos
#   Handles Docker installation, user permissions, networking
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Docker Setup ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME BIN_DIR

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
    info "This demo requires Docker to run"
    echo
    echo "Installation details:"
    echo "  - Download size: ~100-150 MB"
    echo "  - Installation time: 5-10 minutes"
    echo "  - Requires: Active internet connection"
    echo "  - Disk space needed: ~200 MB"
    echo

    # Prompt for confirmation
    if ! show_yesno "Install Docker?" \
        "This demo requires Docker Engine.\n\nInstall Docker now?\n\n• Size: ~100-150 MB download\n• Time: 5-10 minutes\n• Requires internet connection\n\nDocker containers are known to occasionally cause\nnetwork conflicts with AutoHotspot configurations."; then
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
    USER_NAME=$(get_user_name)
    sudo usermod -aG docker "$USER_NAME"

    # Enable Docker service
    info "[4/4] Enabling Docker service..."
    sudo systemctl enable docker

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
USER_NAME=$(get_user_name)
if ! groups "$USER_NAME" | grep -q docker; then
    warn "User '$USER_NAME' is not in the docker group"
    info "Adding user to docker group..."
    sudo usermod -aG docker "$USER_NAME"

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

# Configure Docker networking
info "Configuring Docker networking..."
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf 2>/dev/null; then
    sudo sed -i "s/.*net.ipv4.ip_forward=.*/net.ipv4.ip_forward=1/g" /etc/sysctl.conf 2>/dev/null || \
        echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf > /dev/null
    sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null
    info "Docker networking configured"
fi

echo
info "Docker is ready!"
echo

exit 0
