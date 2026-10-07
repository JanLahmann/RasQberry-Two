#!/bin/bash
set -euo pipefail

################################################################################
# rq_quantum_lab.sh - RasQberry Quantum Lab (QuBins) Demo Launcher
#
# Description:
#   Runs a local JupyterLab quantum environment in a Docker container using the
#   QuBins signed community image (ghcr.io/qubins/images, pinned by digest). The IBM
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
rq_help_guard "$@"

echo
echo "=== Quantum Lab (QuBins) Demo ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

# Pinned per release by digest (manifest); "Update demos" can move it
DOCKER_IMAGE="$(rq_demo_image quantum-lab)"
CONTAINER_NAME="quantum-lab"
# One fixed port, so a relaunch does not move the lab to another address
# (R-153): the old container is gone before the new one starts.
PORT="${QUANTUM_LAB_PORT:-8892}"
# Learners' own work survives a stop (R-067): this folder on the Pi is the
# lab's "my-work" folder.
WORK_DIR="$USER_HOME/$REPO/work/quantum-lab"
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

# Set from here, so the QuBins image stays as published (#18, Jan):
# - the lab opens on a short welcome page (read-only) instead of a bare
#   launcher;
# - no "Would you like to get notified about official Jupyter news?": the
#   Pi's own JupyterLab setting (RQB2-system), read-only in the container.
WELCOME_SRC="$(dirname "$(rq_shipped_manifest_dir)")/quantum-lab/WELCOME.ipynb"
LAB_OVERRIDES="${RQ_LAB_OVERRIDES:-/etc/jupyter/labconfig/default_setting_overrides.json}"
EXTRA_MOUNTS=()
START_PAGE="lab"
if [ -f "$WELCOME_SRC" ]; then
    EXTRA_MOUNTS+=(-v "$WELCOME_SRC:/home/jovyan/WELCOME.ipynb:ro")
    START_PAGE="lab/tree/WELCOME.ipynb"
fi
if [ -f "$LAB_OVERRIDES" ]; then
    EXTRA_MOUNTS+=(-v "$LAB_OVERRIDES:/etc/jupyter/labconfig/default_setting_overrides.json:ro")
fi

################################################################################
# Prerequisites: Docker (mirrors qoffee-maker.sh)
################################################################################

rq_docker_access "$@"

################################################################################
# Ensure the IBM Quantum Learning course notebooks are present
#
# Reuse the exact same install path as the ibm-courses demo: this clones the
# Qiskit/documentation sparse checkout into DOCS_DIR (as the user) and generates
# the WELCOME notebook if it is not already there. install_demo_raspiconfig sets
# RQ_AUTO_INSTALL=1 so no interactive prompts appear.
################################################################################
# The WELCOME notebook marks a finished install; a .git alone may be what an
# interrupted download left (R-056)
if [ ! -f "$DOCS_DIR/${MARKER_IBM_COURSES:-WELCOME-courses.ipynb}" ]; then
    info "IBM Quantum Learning content not found."
    # Quantum Lab's own question named them ("and the IBM course notebooks
    # if missing"): no second question after the long image download, which
    # kept someone who had walked away waiting (user test 2026-10-07, P6).
    # The space and network checks still run.
    if [ "${RQ_CONFIRMED_DEMO:-}" = "quantum-lab" ]; then
        RQ_AUTO_INSTALL=1 rq_require_demo_consent ibm-courses
    else
        rq_require_demo_consent ibm-courses
    fi
    info "Installing course notebooks (Qiskit/documentation)..."
    install_demo_raspiconfig do_ibm_courses_install \
        || die "Failed to install IBM Quantum Learning content"
fi

# Final sanity check before mounting
[ -d "$DOCS_DIR" ] || die "IBM Quantum Learning content missing at $DOCS_DIR"
# Only the notebooks and what they need, not the repository's own files (#18)
rq_ibm_learning_tidy "$DOCS_DIR"

################################################################################
# Docker container management
################################################################################

# Replace an earlier Quantum Lab container, and wait until it is gone
rq_docker_stop "$CONTAINER_NAME" \
    || die "The previous Quantum Lab container did not go away; try again in a minute."
if port_in_use "$PORT"; then
    PORT=$(find_available_port $((PORT + 1)))
    warn "Port 8892 is taken; Quantum Lab uses $PORT this time."
fi

# The image (pinned), downloaded after the consent dialog; the manifest's
# fallback tag when QuBins no longer offers the pinned build
if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    rq_require_demo_consent quantum-lab
    rq_demo_docker_pull quantum-lab "$DOCKER_IMAGE" "Quantum Lab (QuBins)"
    DOCKER_IMAGE="$RQ_DOCKER_PULLED"
    rq_docker_drop_old "$DOCKER_IMAGE"
fi

mkdir -p "$WORK_DIR"
fix_root_ownership "$USER_HOME/$REPO/work" >/dev/null 2>&1 || true
# jovyan in the container is uid 1000, like the first desktop user; a folder
# of another owner is opened up so the lab can save into it
[ "$(stat -c %u "$WORK_DIR" 2>/dev/null || echo 1000)" = "1000" ] || chmod 777 "$WORK_DIR" 2>/dev/null || true

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
# The course notebooks are mounted READ-ONLY. Learners save their work in
# my-work/, which is WORK_DIR on the Pi and survives a stop (R-067); anything
# else in the container is gone when it stops.
################################################################################
echo
info "Starting Quantum Lab container..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=quantum-lab" \
    -p "127.0.0.1:${PORT}:8888" \
    -e JUPYTER_TOKEN="$LAB_TOKEN" \
    -v "$DOCS_DIR":/home/jovyan/ibm-quantum-learning:ro \
    -v "$WORK_DIR":/home/jovyan/my-work \
    ${EXTRA_MOUNTS[@]+"${EXTRA_MOUNTS[@]}"} \
    "$DOCKER_IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The Quantum Lab container did not start."
fi

# Wait for JupyterLab to answer on the loopback port
info "Waiting for JupyterLab to start..."
LAB_URL="http://127.0.0.1:${PORT}/${START_PAGE}?token=${LAB_TOKEN}"
# JupyterLab needs ~15 s to start on a Pi 4; the loop returns as soon as
# it answers, so a generous limit costs nothing (rig test, #234)
MAX_WAIT=60
WAIT_COUNT=0
until curl -sf "http://127.0.0.1:${PORT}/lab" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "Quantum Lab stopped while starting."
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        rq_docker_fail "$CONTAINER_NAME" "JupyterLab did not answer within ${MAX_WAIT} seconds."
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
echo "  Course notebooks: ibm-quantum-learning/ (read-only)"
echo "  Save your own work in my-work/ - it is kept on the Pi in:"
echo "    $WORK_DIR"
echo "  Anything saved elsewhere in the lab is lost when it stops."
echo "  Content licensed under CC BY-SA 4.0 by IBM/Qiskit"
echo

rq_show_url "$LAB_URL" "$PORT"

################################################################################
# Stop: Enter, Ctrl+C or closing this window (item 33; as qoffee-maker.sh)
################################################################################
rq_docker_stop_with_window "$CONTAINER_NAME" "Quantum Lab"
