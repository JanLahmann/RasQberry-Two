#!/bin/bash
set -euo pipefail

################################################################################
# quantum-mixer.sh - RasQberry Quantum-Mixer Demo Launcher
#
# Description:
#   Modern web-based quantum beverage mixer (Qocktails, Qoffee, Ice)
#   Runs in Docker container with web interface
#   Handles Docker setup, image building, and permissions
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Quantum-Mixer Demo ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME BIN_DIR

DOCKER_IMAGE="${QUANTUM_MIXER_DOCKER_IMAGE:-quantum-mixer:arm64}"
CONTAINER_NAME="quantum-mixer"
PORT="${QUANTUM_MIXER_PORT:-8080}"
REPO_DIR="${USER_HOME}/quantum-mixer"
REPO_URL="${GIT_REPO_DEMO_QUANTUM_MIXER:-https://github.com/JanLahmann/quantum-mixer.git}"

################################################################################
# run_docker_setup - Run docker-setup for Docker prerequisites
################################################################################
run_docker_setup() {
    local reason="$1"
    info "$reason"
    echo "Running Docker setup..."
    "$BIN_DIR/docker-setup.sh" || exit 1
    # Re-exec this script after Docker setup completes
    exec "$0" "$@"
}

################################################################################
# Prerequisites checks
################################################################################

# Check if Docker is installed
command -v docker &> /dev/null || run_docker_setup "Error: Docker is not installed."

# Check if user is in docker group
USER_NAME=$(get_user_name)
if ! groups "$USER_NAME" | grep -q docker && [ "$USER_NAME" != "root" ]; then
    run_docker_setup "Error: User '$USER_NAME' is not in the docker group."
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

################################################################################
# Docker container management
################################################################################

# Stop any existing quantum-mixer containers
info "Checking for existing containers..."
if docker ps -q --filter name=$CONTAINER_NAME 2>/dev/null | grep -q .; then
    info "Stopping existing Quantum-Mixer container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
fi

# Remove stopped container if exists
docker rm $CONTAINER_NAME 2>/dev/null || true

################################################################################
# Docker image build (if needed)
################################################################################

# Check if we need to build the Docker image
IMAGE_EXISTS=$(docker images -q $DOCKER_IMAGE 2>/dev/null)
if [ -z "$IMAGE_EXISTS" ]; then
    echo
    info "Docker image not found. Building Quantum-Mixer from source..."
    echo

    # Clone or update repository
    if [ ! -d "$REPO_DIR" ]; then
        info "Cloning quantum-mixer repository..."
        if ! clone_demo "$REPO_URL" "$REPO_DIR"; then
            die "Failed to clone repository. Please check your internet connection"
        fi
    else
        info "Updating quantum-mixer repository..."
        cd "$REPO_DIR"
        git pull origin main || warn "Could not update repository, using existing version"
    fi

    # Build Docker image using ARM64 Dockerfile
    echo
    info "Building Docker image for ARM64..."
    info "This may take 10-15 minutes on first build..."
    cd "$REPO_DIR"

    if ! docker build -f Dockerfile.arm64 -t $DOCKER_IMAGE .; then
        echo
        die "Failed to build Docker image. Check the build output above for details"
    fi

    echo
    echo "✓ Docker image built successfully!"
else
    info "Using existing Docker image: $DOCKER_IMAGE"
fi

################################################################################
# Start container
################################################################################

echo
info "Starting Quantum-Mixer container..."
if ! docker run -d \
    --name $CONTAINER_NAME \
    --rm \
    -p ${PORT}:8080 \
    $DOCKER_IMAGE; then
    echo
    die "Failed to start Docker container. Check logs with: docker logs $CONTAINER_NAME"
fi

# Wait for container to start
info "Waiting for web server to start..."
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
    info "Opening browser..."
    run_as_user chromium-browser --password-store=basic "$MIXER_URL" &
elif command -v firefox &> /dev/null; then
    info "Opening browser..."
    run_as_user firefox "$MIXER_URL" &
else
    info "No browser found. Please open the URL manually."
fi

################################################################################
# Interactive wait and cleanup
################################################################################

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
info "Stopping Quantum-Mixer container..."
docker stop $CONTAINER_NAME

info "Container stopped"
echo
