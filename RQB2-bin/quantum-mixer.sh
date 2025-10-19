#!/bin/bash
#
# RasQberry-Two: Quantum-Mixer Demo Launcher
# Modern web-based quantum beverage mixer (Qocktails, Qoffee, Ice)
#

echo
echo "=== Quantum-Mixer Demo ==="
echo

# Determine user and paths
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables
. "$USER_HOME/.local/config/env-config.sh"

DOCKER_IMAGE="${QUANTUM_MIXER_DOCKER_IMAGE:-quay.io/janlahmann/quantum-mixer:v1.0}"
CONTAINER_NAME="quantum-mixer"
PORT="${QUANTUM_MIXER_PORT:-8080}"

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

# Stop any existing quantum-mixer containers
echo "Checking for existing containers..."
if docker ps -q --filter name=$CONTAINER_NAME 2>/dev/null | grep -q .; then
    echo "Stopping existing Quantum-Mixer container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
fi

# Remove stopped container if exists
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull latest image from Quay.io
echo
echo "Pulling Quantum-Mixer Docker image from Quay.io..."
echo "Image: $DOCKER_IMAGE"
echo "Size: ~505 MB (first download may take a few minutes)"
if ! docker pull $DOCKER_IMAGE; then
    echo
    echo "Error: Failed to pull Docker image from Quay.io."
    echo "Please check your internet connection and try again."
    exit 1
fi

# Start container
echo
echo "Starting Quantum-Mixer container..."
if ! docker run -d \
    --name $CONTAINER_NAME \
    --rm \
    -p ${PORT}:8080 \
    $DOCKER_IMAGE; then
    echo
    echo "Error: Failed to start Docker container."
    echo "Check the logs with: docker logs $CONTAINER_NAME"
    exit 1
fi

# Wait for container to start
echo "Waiting for web server to start..."
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
MIXER_URL="http://127.0.0.1:${PORT}"

echo
echo "✓ Quantum-Mixer is running!"
echo
echo "  Access via browser: $MIXER_URL"
echo
echo "Available demos:"
echo "  • Qocktails - Quantum cocktail mixer (educational)"
echo "  • Qoffee - Quantum coffee maker (requires Home Connect)"
echo "  • Ice - Quantum ice dispenser"
echo

# Try to open browser (as user, not root)
if command -v chromium-browser &> /dev/null; then
    echo "Opening browser..."
    # Run browser as user if we're root
    if [ "$(whoami)" = "root" ] && [ -n "$USER_NAME" ]; then
        su - "$USER_NAME" -c "DISPLAY=:0 chromium-browser '$MIXER_URL' &"
    else
        chromium-browser "$MIXER_URL" &
    fi
elif command -v firefox &> /dev/null; then
    echo "Opening browser..."
    if [ "$(whoami)" = "root" ] && [ -n "$USER_NAME" ]; then
        su - "$USER_NAME" -c "DISPLAY=:0 firefox '$MIXER_URL' &"
    else
        firefox "$MIXER_URL" &
    fi
else
    echo "No browser found. Please open the URL manually."
fi

echo
echo "============================================"
echo "  Quantum-Mixer is running in the background"
echo "============================================"
echo
echo "To stop the container, run:"
echo "  docker stop $CONTAINER_NAME"
echo
echo "Or use the RasQberry menu:"
echo "  Quantum Demos → Stop Quantum-Mixer"
echo
echo "Press Enter to stop the container now..."
read -r

# Cleanup
echo
echo "Stopping Quantum-Mixer container..."
docker stop $CONTAINER_NAME

echo "Container stopped."
echo
