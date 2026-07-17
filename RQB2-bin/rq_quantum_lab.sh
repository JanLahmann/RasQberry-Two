#!/bin/bash
set -euo pipefail

################################################################################
# rq_quantum_lab.sh - RasQberry Quantum Lab (QuBins) Demo Launcher
#
# Description:
#   Runs a local JupyterLab quantum environment in a Docker container using the
#   QuBins signed community image (ghcr.io/qubins/images:latest-xl). The IBM
#   Quantum Learning course notebooks - the same Qiskit/documentation content
#   the ibm-courses demo installs - are mounted read-only into the container so
#   users can run the official courses fully locally.
#
#   Follows the qoffee-maker.sh pattern: manifest declares entrypoint type
#   "docker" plus this dedicated launcher, which handles Docker setup,
#   permissions, image pull, container lifecycle and the browser launch.
#
# Content licensed under CC BY-SA 4.0 by IBM/Qiskit
# Source: https://github.com/Qiskit/documentation
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== Quantum Lab (QuBins) Demo ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

DOCKER_IMAGE="ghcr.io/qubins/images:latest-xl"
CONTAINER_NAME="quantum-lab"
PORT="${QUANTUM_LAB_PORT:-$(find_available_port 8892)}"

# A fixed, known token that we bake into the container AND the URL we open.
# An empty JUPYTER_TOKEN does NOT disable auth on this image: its start script
# treats an unset/empty value as "generate a random token", so the browser
# lands on JupyterLab's /login wall instead of the lab. A non-empty token that
# we also put in the URL bypasses the wall deterministically. The port binds to
# loopback only (see below), so this token is not a LAN-exposed secret.
LAB_TOKEN="rasqberry"

# The IBM Quantum Learning content is installed by the ibm-courses demo into
# this exact directory (sparse checkout of Qiskit/documentation). We reuse it
# rather than re-cloning inside the container.
DOCS_DIR="$USER_HOME/$REPO/demos/ibm-quantum-learning"

################################################################################
# Prerequisites: Docker (mirrors qoffee-maker.sh)
################################################################################

# Check if Docker is installed
check_docker || die "Error: Docker is not installed (the image may be misbuilt)."

# Check if user is in docker group
USER_NAME=$(get_user_name)
if ! groups "$USER_NAME" | grep -q docker && [ "$USER_NAME" != "root" ]; then
    die "Error: User '$USER_NAME' is not in the docker group (the image may be misbuilt)."
fi

# Check if docker group is active in current session
# This handles the case where user was added to docker group but hasn't logged
# out/in. We use 'sg' to activate the group immediately without requiring logout.
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
    echo "Add yourself to the 'docker' group and log out/in, or run with sudo."
    echo
    die "Docker permission denied"
fi

################################################################################
# Ensure the IBM Quantum Learning course notebooks are present
#
# Reuse the exact same install path as the ibm-courses demo: this clones the
# Qiskit/documentation sparse checkout into DOCS_DIR (as the user) and generates
# the WELCOME notebook if it is not already there. install_demo_raspiconfig sets
# RQ_AUTO_INSTALL=1 so no interactive prompts appear.
################################################################################
if [ ! -d "$DOCS_DIR/.git" ]; then
    info "IBM Quantum Learning content not found."
    info "Installing course notebooks (Qiskit/documentation)..."
    install_demo_raspiconfig do_ibm_courses_install \
        || die "Failed to install IBM Quantum Learning content"
fi

# Final sanity check before mounting
[ -d "$DOCS_DIR" ] || die "IBM Quantum Learning content missing at $DOCS_DIR"

################################################################################
# Docker container management
################################################################################

# Stop/replace any existing quantum-lab container
info "Checking for existing containers..."
if docker ps -q --filter name=$CONTAINER_NAME 2>/dev/null | grep -q .; then
    info "Stopping existing Quantum Lab container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
fi
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull the image only if it is not already present locally. The QuBins xl image
# is ~1 GB, so warn the user once that the first run downloads it.
if ! docker images -q "$DOCKER_IMAGE" 2>/dev/null | grep -q .; then
    echo
    info "Quantum Lab image not found locally."
    info "Pulling $DOCKER_IMAGE ..."
    info "This is a ~1 GB download and may take several minutes on first run."
    if ! docker pull "$DOCKER_IMAGE"; then
        echo
        die "Failed to pull Docker image. Please check your internet connection"
    fi
fi

################################################################################
# Start container
#
# Security tradeoff:
#   -p 127.0.0.1:${PORT}:8888  binds the published port to host loopback ONLY,
#   so the JupyterLab server is NOT reachable from the LAN. Access is restricted
#   to this machine, and we bake in a fixed token (LAB_TOKEN) that we also carry
#   in the URL we open, for a friction-free classroom experience. Do NOT change
#   the bind address to 0.0.0.0 without switching to a strong per-run secret.
#
# The QuBins image is based on quay.io/jupyter/base-notebook: default user is
# "jovyan", home /home/jovyan, JupyterLab listens on port 8888 inside.
#
# The course notebooks are mounted READ-ONLY. Edits inside the container are
# ephemeral (the container runs with --rm); learners who want to keep changes
# should "Save As" / copy a notebook into their writable home in the container.
# (The xl image ships nbgitpuller, so a persistent work dir could be added
# later if desired; kept minimal here to match the qoffee-maker pattern, which
# mounts no writable work dir.)
################################################################################
echo
info "Starting Quantum Lab container..."
if ! docker run -d \
    --name $CONTAINER_NAME \
    --rm \
    -p 127.0.0.1:${PORT}:8888 \
    -e JUPYTER_TOKEN="$LAB_TOKEN" \
    -v "$DOCS_DIR":/home/jovyan/ibm-quantum-learning:ro \
    "$DOCKER_IMAGE"; then
    echo
    die "Failed to start Docker container. Check logs with: docker logs $CONTAINER_NAME"
fi

# Wait for JupyterLab to answer on the loopback port
info "Waiting for JupyterLab to start..."
LAB_URL="http://127.0.0.1:${PORT}/lab?token=${LAB_TOKEN}"
MAX_WAIT=30
WAIT_COUNT=0
until curl -sf "http://127.0.0.1:${PORT}/lab" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    # Bail out early if the container died
    if ! docker ps --filter name=$CONTAINER_NAME --filter status=running | grep -q $CONTAINER_NAME; then
        echo
        echo "Error: Container stopped unexpectedly."
        echo "Logs:"
        docker logs $CONTAINER_NAME 2>&1 | tail -20 || true
        die "Container failed to start"
    fi
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        docker logs $CONTAINER_NAME 2>&1 | tail -20 || true
        docker stop $CONTAINER_NAME 2>/dev/null || true
        die "JupyterLab did not respond after ${MAX_WAIT} seconds"
    fi
done

info "JupyterLab ready!"

################################################################################
# Browser launch
################################################################################
echo
echo "✓ Quantum Lab is running!"
echo
echo "  Access via browser: $LAB_URL"
echo
echo "  Course notebooks are mounted at: ibm-quantum-learning/ (read-only)"
echo "  Content licensed under CC BY-SA 4.0 by IBM/Qiskit"
echo

# Open browser as the desktop user (never as root)
if command -v chromium-browser &>/dev/null; then
    info "Opening browser..."
    run_as_user chromium-browser --password-store=basic "$LAB_URL" &
elif command -v firefox &>/dev/null; then
    info "Opening browser..."
    run_as_user firefox "$LAB_URL" &
elif command -v xdg-open &>/dev/null; then
    info "Opening browser..."
    run_as_user xdg-open "$LAB_URL" &
else
    info "No browser found. Please open manually: $LAB_URL"
fi

################################################################################
# Interactive wait and cleanup (matches qoffee-maker.sh lifecycle)
################################################################################
echo
echo "============================================"
echo "  Quantum Lab is running in the background"
echo "============================================"
echo
echo "To stop the container, run:"
echo "  docker stop $CONTAINER_NAME"
echo

# Only wait for input if we have a TTY (interactive session)
if [ -t 0 ]; then
    echo "Press Enter to stop the container now..."
    read -r
    echo
    info "Stopping Quantum Lab container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    info "Container stopped"
    echo
else
    # No TTY - launched from desktop icon, keep container running
    info "Container will keep running in the background"
    info "Use 'docker stop $CONTAINER_NAME' to stop it when done"
    echo
fi
