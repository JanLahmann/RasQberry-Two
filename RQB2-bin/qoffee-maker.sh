#!/bin/bash
set -euo pipefail

################################################################################
# qoffee-maker.sh - RasQberry Qoffee-Maker Demo Launcher
#
# Description:
#   Runs Qoffee-Maker in a Docker container with a Jupyter interface and
#   opens the Qoffee app in the browser (fullscreen; F11 leaves it).
#   The image is pinned by digest per release and pulled only when missing,
#   so the demo starts offline once it is there (R-038). Which image
#   RasQberry should run long-term is open (Jan, Q29: the 2022 arm/v7 image
#   still uses the retired IBMQ API).
#
# Usage: qoffee-maker.sh [--install-only]
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

echo
echo "=== Qoffee-Maker Demo ==="
echo

load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

DEMO_DIR="$USER_HOME/$REPO/demos/Qoffee-Maker"
ENV_FILE="$DEMO_DIR/.env"
DOCKER_IMAGE="$(rq_demo_image qoffee-maker)"
CONTAINER_NAME="qoffee"
NOTEBOOK="qoffee.ipynb"
# Kiosk app mode: a custom.js that auto-fires the Qoffee 'rocket' once the
# notebook loads (shipped copy first, then the repo checkout)
APPMODE_JS=""
for _cand in \
    "/usr/config/demo-patches/qoffee-appmode-custom.js" \
    "$USER_HOME/$REPO/RQB2-config/demo-patches/qoffee-appmode-custom.js"; do
    if [ -f "$_cand" ]; then
        APPMODE_JS="$_cand"
        break
    fi
done

rq_docker_access "$@"

################################################################################
# First install: notebooks + settings (qoffee-setup.sh) and the image, after
# one consent dialog (no-op when the demo engine asked already)
################################################################################
if [ ! -f "$DEMO_DIR/$NOTEBOOK" ] || [ ! -f "$ENV_FILE" ] \
        || ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    rq_require_demo_consent qoffee-maker
    if [ ! -f "$DEMO_DIR/$NOTEBOOK" ] || [ ! -f "$ENV_FILE" ]; then
        "$BIN_DIR/qoffee-setup.sh" || die "The Qoffee-Maker setup did not finish."
    fi
    if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
        rq_docker_pull "$DOCKER_IMAGE" "Qoffee-Maker"
        rq_docker_drop_old "$DOCKER_IMAGE"
    fi
fi
# The menu's installer (do_qoffee_install) stops here
[ "${1:-}" = "--install-only" ] && exit 0

################################################################################
# Start (an earlier Qoffee container is replaced)
################################################################################
rq_docker_stop "$CONTAINER_NAME" || die "The previous Qoffee-Maker container did not go away; try again in a minute."
PORT="${QOFFEE_PORT:-$(find_available_port 8887)}"
port_in_use "$PORT" && PORT=$(find_available_port $((PORT + 1)))

JUPYTER_TOKEN=$(grep "^JUPYTER_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
[ -n "$JUPYTER_TOKEN" ] || JUPYTER_TOKEN="super-secret-token"

# The pulled image runs as root (config in /root/.jupyter), not as jovyan:
# mount the app-mode script for both, so app mode starts either way (R-108)
APPMODE_MOUNT=()
if [ -n "$APPMODE_JS" ]; then
    APPMODE_MOUNT=(-v "$APPMODE_JS:/root/.jupyter/custom/custom.js:ro"
                   -v "$APPMODE_JS:/home/jovyan/.jupyter/custom/custom.js:ro")
else
    warn "App-mode script not found; the notebook opens without app mode"
fi

info "Starting Qoffee-Maker..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=qoffee-maker" \
    -p "127.0.0.1:${PORT}:8887" \
    --env JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    --env-file "$ENV_FILE" \
    ${APPMODE_MOUNT[@]+"${APPMODE_MOUNT[@]}"} \
    "$DOCKER_IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The Qoffee-Maker container did not start."
fi

info "Waiting for Jupyter..."
for _ in $(seq 1 45); do
    curl -s -o /dev/null "http://127.0.0.1:${PORT}/login" && break
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "Qoffee-Maker stopped while starting."
    sleep 1
done

JUPYTER_URL="http://127.0.0.1:${PORT}/notebooks/${NOTEBOOK}?token=${JUPYTER_TOKEN}"
echo
echo "Qoffee-Maker is running: $JUPYTER_URL"
echo "The app opens fullscreen; F11 leaves fullscreen."
echo
# Fullscreen like a kiosk (the app's own fullscreen request needs a click)
if check_display && command -v chromium-browser >/dev/null 2>&1; then
    info "Opening the browser..."
    run_as_user chromium-browser --password-store=basic --start-fullscreen "$JUPYTER_URL" >/dev/null 2>&1 &
else
    rq_show_url "$JUPYTER_URL" "$PORT"
fi

################################################################################
# Stop
################################################################################
echo "To stop it later: RasQberry menu > Quantum Demos > Stop Docker demos."
if [ -t 0 ]; then
    echo "Press Enter to stop Qoffee-Maker..."
    read -r || exit 0
    info "Stopping Qoffee-Maker..."
    rq_docker_stop "$CONTAINER_NAME" || true
    info "Qoffee-Maker stopped."
else
    info "Qoffee-Maker keeps running in the background."
fi
