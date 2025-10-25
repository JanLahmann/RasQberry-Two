#!/bin/bash
set -euo pipefail

################################################################################
# qoffee-maker.sh - RasQberry Qoffee-Maker Demo Launcher
#
# Description:
#   Runs Qoffee-Maker in Docker container with Jupyter interface
#   Handles Docker setup, permissions, and API configuration
#   Automatically opens browser to Jupyter notebook interface
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Qoffee-Maker Demo ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"
ENV_FILE="$DEMO_DIR/.env"
DOCKER_IMAGE="ghcr.io/janlahmann/qoffee-maker"
CONTAINER_NAME="qoffee"
PORT="${QOFFEE_PORT:-8887}"

################################################################################
# run_qoffee_setup - Run setup script if needed
################################################################################
run_qoffee_setup() {
    local reason="$1"
    info "$reason"
    echo "Running setup script..."
    if ! "$BIN_DIR/qoffee-setup.sh"; then
        die "Setup failed or was cancelled"
    fi
    info "Setup complete. Continuing with demo launch..."
}

################################################################################
# Prerequisites checks
################################################################################

# Check if demo directory exists
[ -d "$DEMO_DIR" ] || run_qoffee_setup "Error: Qoffee-Maker not installed."

# Check if Docker is installed
command -v docker &> /dev/null || run_qoffee_setup "Error: Docker is not installed."

# Check if user is in docker group
USER_NAME=$(get_user_name)
if ! groups "$USER_NAME" | grep -q docker && [ "$USER_NAME" != "root" ]; then
    run_qoffee_setup "Error: User '$USER_NAME' is not in the docker group."
fi

# Check if docker group is active in current session
# This handles the case where user was added to docker group but hasn't logged out/in.
# We use 'sg' to activate the group immediately without requiring logout.
if ! groups | grep -q docker && [ "$(whoami)" != "root" ]; then
    info "Docker group not active in current session"
    info "Activating Docker group permissions..."
    if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        # Re-exec this script with docker group active
        exec sg docker -c "$0 $*"
    fi
fi

# Verify Docker actually works (after group activation)
if ! docker ps &>/dev/null; then
    echo
    echo "ERROR: Cannot access Docker"
    echo
    echo "Docker is installed but you don't have permission to use it."
    echo "This usually means:"
    echo "  1. You need to be added to the 'docker' group"
    echo "  2. You need to log out and log back in for group changes to take effect"
    echo
    echo "To fix this:"
    echo "  1. Run the Qoffee-Maker setup from raspi-config menu (as root)"
    echo "  2. OR manually run: sudo usermod -aG docker $USER_NAME"
    echo "  3. Then log out and log back in"
    echo
    echo "For now, you can run with sudo:"
    echo "  sudo $0"
    echo
    die "Docker permission denied"
fi

# Check for .env configuration
if [ ! -f "$ENV_FILE" ]; then
    run_qoffee_setup "Error: Configuration file not found."
    # Reload environment after setup
    load_rqb2_env
fi

################################################################################
# Configuration validation
################################################################################

# Check if .env has been configured (not using default values)
if grep -q "your_client_id_here\|your_ibmq_api_key_here" "$ENV_FILE" 2>/dev/null; then
    echo
    warn "Configuration file contains default placeholder values"
    echo
    echo "Please configure your API credentials in:"
    echo "  $ENV_FILE"
    echo
    echo "Required credentials:"
    echo "  1. Home Connect Client ID & Secret"
    echo "     → https://developer.home-connect.com/"
    echo "  2. IBM Quantum API Key"
    echo "     → https://quantum-computing.ibm.com/account"
    echo

    # Only offer to edit if we have a TTY (interactive session)
    if [ -t 0 ]; then
        if show_yesno "Configuration Required" \
            "The Qoffee-Maker configuration file needs to be updated\nwith your API credentials.\n\nWould you like to edit it now?"; then
            ${EDITOR:-nano} "$ENV_FILE"
            echo
            info "Configuration saved. Starting Qoffee-Maker..."
        else
            warn "Continuing with default configuration (may not work)..."
        fi
    else
        # No TTY - skip interactive prompt, just continue
        warn "Continuing with default configuration (may not work)..."
        warn "Edit $ENV_FILE to add your API credentials"
    fi
fi

################################################################################
# Docker container management
################################################################################

# Stop any existing qoffee containers
info "Checking for existing containers..."
if docker ps -q --filter name=$CONTAINER_NAME 2>/dev/null | grep -q .; then
    info "Stopping existing Qoffee-Maker container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
fi

# Remove stopped container if exists
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull latest image
echo
info "Pulling latest Qoffee-Maker Docker image..."
info "This may take a few minutes on first run (~2GB download)..."
if ! docker pull $DOCKER_IMAGE; then
    echo
    die "Failed to pull Docker image. Please check your internet connection"
fi

# Get Jupyter token from .env
JUPYTER_TOKEN=$(grep "^JUPYTER_TOKEN=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
[ -z "$JUPYTER_TOKEN" ] && JUPYTER_TOKEN="super-secret-token"

# Start container
echo
info "Starting Qoffee-Maker container..."
if ! docker run -d \
    --name $CONTAINER_NAME \
    --rm \
    -p ${PORT}:8887 \
    --env JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    --env-file "$ENV_FILE" \
    $DOCKER_IMAGE; then
    echo
    die "Failed to start Docker container. Check logs with: docker logs $CONTAINER_NAME"
fi

# Wait for container to start
info "Waiting for Jupyter to start..."
sleep 5

# Verify container is running
if ! docker ps --filter name=$CONTAINER_NAME --filter status=running | grep -q $CONTAINER_NAME; then
    echo
    echo "Error: Container failed to start properly."
    echo "Logs:"
    docker logs $CONTAINER_NAME 2>&1 | tail -20
    die "Container failed to start"
fi

################################################################################
# Browser launch
################################################################################

# Build URL
JUPYTER_URL="http://127.0.0.1:${PORT}/?token=${JUPYTER_TOKEN}"

echo
echo "✓ Qoffee-Maker is running!"
echo
echo "  Access via browser: $JUPYTER_URL"
echo

# Try to open browser (as user, not root)
if command -v chromium-browser &> /dev/null; then
    info "Opening browser..."
    run_as_user chromium-browser --password-store=basic "$JUPYTER_URL" &
elif command -v firefox &> /dev/null; then
    info "Opening browser..."
    run_as_user firefox "$JUPYTER_URL" &
else
    info "No browser found. Please open the URL manually."
fi

################################################################################
# Interactive wait and cleanup
################################################################################

echo
echo "============================================"
echo "  Qoffee-Maker is running in the background"
echo "============================================"
echo
echo "To stop the container, run:"
echo "  docker stop $CONTAINER_NAME"
echo
echo "Or use the RasQberry menu:"
echo "  Advanced → Stop Qoffee-Maker"
echo

# Only wait for input if we have a TTY (interactive session)
if [ -t 0 ]; then
    echo "Press Enter to stop the container now..."
    read -r

    # Cleanup
    echo
    info "Stopping Qoffee-Maker container..."
    docker stop $CONTAINER_NAME

    info "Container stopped"
    echo
else
    # No TTY - launched from desktop icon, keep container running
    info "Container will keep running in the background"
    info "Use 'docker stop $CONTAINER_NAME' to stop it when done"
    echo
fi
