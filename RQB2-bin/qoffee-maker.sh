#!/bin/bash
#
# RasQberry-Two: Qoffee-Maker Demo Launcher
# Runs Qoffee-Maker in Docker container with Jupyter interface
#

echo
echo "=== Qoffee-Maker Demo ==="
echo

# Determine user and paths FIRST (before loading config)
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables from user's home directory
. "$USER_HOME/.local/config/env-config.sh"

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"
ENV_FILE="$DEMO_DIR/.env"
DOCKER_IMAGE="ghcr.io/janlahmann/qoffee-maker"
CONTAINER_NAME="qoffee"
PORT="${QOFFEE_PORT:-8887}"

# Check if demo directory exists
if [ ! -d "$DEMO_DIR" ]; then
    echo "Error: Qoffee-Maker not installed."
    echo "Running setup script..."
    exec "$BIN_DIR/qoffee-setup.sh"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Running setup script..."
    exec "$BIN_DIR/qoffee-setup.sh"
fi

# Check if user is in docker group
if ! groups "$USER_NAME" | grep -q docker && [ "$USER_NAME" != "root" ]; then
    echo "Error: User '$USER_NAME' is not in the docker group."
    echo "Running setup script to configure permissions..."
    exec "$BIN_DIR/qoffee-setup.sh"
fi

# Check if docker group is active in current session
# This handles the case where user was added to docker group but hasn't logged out/in.
# We use 'sg' to activate the group immediately without requiring logout.
if ! groups | grep -q docker && [ "$(whoami)" != "root" ]; then
    echo "Docker group not active in current session."
    echo "Activating Docker group permissions..."
    if [ -z "$DOCKER_GROUP_ACTIVATED" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        # Re-exec this script with docker group active
        exec sg docker -c "$0 $*"
    fi
fi

# Check for .env configuration
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Configuration file not found."
    echo "Running setup script to create configuration..."
    exec "$BIN_DIR/qoffee-setup.sh"
fi

# Check if .env has been configured (not using default values)
if grep -q "your_client_id_here\|your_ibmq_api_key_here" "$ENV_FILE" 2>/dev/null; then
    echo
    echo "⚠  Warning: Configuration file contains default placeholder values."
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

    if whiptail --title "Configuration Required" --yesno \
        "The Qoffee-Maker configuration file needs to be updated\nwith your API credentials.\n\nWould you like to edit it now?" \
        12 65; then
        ${EDITOR:-nano} "$ENV_FILE"
        echo
        echo "Configuration saved. Starting Qoffee-Maker..."
    else
        echo "Continuing with default configuration (may not work)..."
    fi
fi

# Stop any existing qoffee containers
echo "Checking for existing containers..."
if docker ps -q --filter name=$CONTAINER_NAME 2>/dev/null | grep -q .; then
    echo "Stopping existing Qoffee-Maker container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
fi

# Remove stopped container if exists
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull latest image
echo
echo "Pulling latest Qoffee-Maker Docker image..."
echo "This may take a few minutes on first run (~2GB download)..."
if ! docker pull $DOCKER_IMAGE; then
    echo
    echo "Error: Failed to pull Docker image."
    echo "Please check your internet connection and try again."
    exit 1
fi

# Get Jupyter token from .env
JUPYTER_TOKEN=$(grep "^JUPYTER_TOKEN=" "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$JUPYTER_TOKEN" ]; then
    JUPYTER_TOKEN="super-secret-token"
fi

# Start container
echo
echo "Starting Qoffee-Maker container..."
if ! docker run -d \
    --name $CONTAINER_NAME \
    --rm \
    -p ${PORT}:8887 \
    --env JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    --env-file "$ENV_FILE" \
    $DOCKER_IMAGE; then
    echo
    echo "Error: Failed to start Docker container."
    echo "Check the logs with: docker logs $CONTAINER_NAME"
    exit 1
fi

# Wait for container to start
echo "Waiting for Jupyter to start..."
sleep 5

# Verify container is running
if ! docker ps --filter name=$CONTAINER_NAME --filter status=running | grep -q $CONTAINER_NAME; then
    echo
    echo "Error: Container failed to start properly."
    echo "Logs:"
    docker logs $CONTAINER_NAME 2>&1 | tail -20
    exit 1
fi

# Build URL
JUPYTER_URL="http://127.0.0.1:${PORT}/?token=${JUPYTER_TOKEN}"

echo
echo "✓ Qoffee-Maker is running!"
echo
echo "  Access via browser: $JUPYTER_URL"
echo

# Try to open browser (as user, not root)
if command -v chromium-browser &> /dev/null; then
    echo "Opening browser..."
    # Run browser as user if we're root
    if [ "$(whoami)" = "root" ] && [ -n "$USER_NAME" ]; then
        su - "$USER_NAME" -c "DISPLAY=:0 chromium-browser --password-store=basic '$JUPYTER_URL' &"
    else
        chromium-browser --password-store=basic "$JUPYTER_URL" &
    fi
elif command -v firefox &> /dev/null; then
    echo "Opening browser..."
    if [ "$(whoami)" = "root" ] && [ -n "$USER_NAME" ]; then
        su - "$USER_NAME" -c "DISPLAY=:0 firefox '$JUPYTER_URL' &"
    else
        firefox "$JUPYTER_URL" &
    fi
else
    echo "No browser found. Please open the URL manually."
fi

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
echo "Press Enter to stop the container now..."
read -r

# Cleanup
echo
echo "Stopping Qoffee-Maker container..."
docker stop $CONTAINER_NAME

echo "Container stopped."
echo
