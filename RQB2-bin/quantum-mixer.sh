#!/bin/bash
set -euo pipefail

################################################################################
# quantum-mixer.sh - RasQberry Quantum-Mixer Demo Launcher
#
# Description:
#   Web-based quantum beverage mixer (Qocktails, Qoffee, Ice) in a Docker
#   container. The arm64 image is built by RasQberry's CI from the pinned
#   quantum-mixer commit (.github/workflows/quantum-mixer-image.yml) and
#   pulled from ghcr.io like the other Docker demos (Jan, Q27c). Building it
#   on this Pi (15-30 minutes, 5.6 GB build cache) is only the fallback when
#   the prebuilt image cannot be had.
#
# Usage: quantum-mixer.sh [--install-only]
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

echo
echo "=== Quantum-Mixer Demo ==="
echo

load_rqb2_env
verify_env_vars USER_HOME REPO BIN_DIR

DOCKER_IMAGE="$(rq_demo_image quantum-mixer)"
SRC_URL="$(rq_demo_repo quantum-mixer)"
SRC_REF="$(rq_demo_ref quantum-mixer)"
CONTAINER_NAME="quantum-mixer"
REPO_DIR="$(get_demo_dir quantum-mixer)"
[ -n "$DOCKER_IMAGE" ] || die "The Quantum-Mixer demo description (manifest) names no Docker image."

# A local fallback build is tagged with the pinned name when that is a tag;
# a digest cannot be given to a local build, so it gets its own tag then
LOCAL_IMAGE="$DOCKER_IMAGE"
case "$DOCKER_IMAGE" in
    *@*) LOCAL_IMAGE="${DOCKER_IMAGE%%@*}:local-${SRC_REF:0:12}" ;;
esac

rq_docker_access "$@"

# Build the image on this Pi from the pinned source (fallback only)
build_locally() {
    local rc=0
    rq_confirm_download "Quantum-Mixer" 1200 2300 --peak 5600 --time "15-30 minutes" \
        --what "Source code from GitHub, built into a Docker image on this Pi" \
        --path /var/lib/docker --url "$SRC_URL" \
        --title "Build Quantum-Mixer on this Pi?" \
        --intro "The prebuilt Quantum-Mixer image could not be downloaded." \
        --question "Build it on this Pi instead?" || rc=$?
    case "$rc" in
        0) ;;
        1) info "${RQ_CONSENT_MSG:-Not built.}"; exit 0 ;;
        *) die "${RQ_CONSENT_MSG:-Quantum-Mixer cannot be built.}" ;;
    esac
    if [ ! -f "$REPO_DIR/Dockerfile.arm64" ]; then
        rq_remove_tree "$REPO_DIR" || die "An earlier, incomplete download is in the way: $REPO_DIR"
        fetch_pinned_repo "$SRC_URL" "$SRC_REF" "$REPO_DIR" \
            || die "Could not download the Quantum-Mixer source from $SRC_URL"
    fi
    info "Building the Quantum-Mixer image (15-30 minutes)..."
    if ! (cd "$REPO_DIR" && docker build -f Dockerfile.arm64 -t "$LOCAL_IMAGE" .); then
        docker builder prune -f >/dev/null 2>&1 || true
        die "The Quantum-Mixer image could not be built (see the output above)."
    fi
    # The build leaves a cache of about 5.6 GB that nothing reuses (R-153)
    docker builder prune -f >/dev/null 2>&1 || true
}

################################################################################
# Install: pull the prebuilt image (consent first; no-op when the engine asked)
################################################################################
RUN_IMAGE=""
if docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    RUN_IMAGE="$DOCKER_IMAGE"
elif docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
    RUN_IMAGE="$LOCAL_IMAGE"
else
    rq_require_demo_consent quantum-mixer
    info "Downloading Quantum-Mixer: $DOCKER_IMAGE"
    if docker pull "$DOCKER_IMAGE"; then
        RUN_IMAGE="$DOCKER_IMAGE"
    elif rq_reachable "https://ghcr.io/v2/"; then
        warn "The prebuilt image is not available on ghcr.io."
        build_locally
        RUN_IMAGE="$LOCAL_IMAGE"
    else
        die "Could not download Quantum-Mixer: ghcr.io cannot be reached. Connect the Pi to the internet and try again."
    fi
    rq_docker_drop_old "$RUN_IMAGE"
    update_env_var "QUANTUM_MIXER_INSTALLED" "true" >/dev/null 2>&1 || true
fi
[ "${1:-}" = "--install-only" ] && exit 0

################################################################################
# Start (an earlier Mixer container is replaced)
################################################################################
rq_docker_stop "$CONTAINER_NAME" || die "The previous Quantum-Mixer container did not go away; try again in a minute."
PORT="${QUANTUM_MIXER_PORT:-$(find_available_port 8085)}"

info "Starting Quantum-Mixer..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=quantum-mixer" \
    -p "127.0.0.1:${PORT}:8080" \
    "$RUN_IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The Quantum-Mixer container did not start."
fi

MIXER_URL="http://127.0.0.1:${PORT}/"
for _ in $(seq 1 30); do
    curl -s -o /dev/null "$MIXER_URL" && break
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "Quantum-Mixer stopped while starting."
    sleep 1
done

echo
echo "Quantum-Mixer is running: $MIXER_URL"
echo "  Qocktails - quantum cocktail mixer; Qoffee - needs Home Connect; Ice"
echo
rq_show_url "$MIXER_URL" "$PORT"

echo "To stop it later: RasQberry menu > Quantum Demos > Stop Docker demos."
if [ -t 0 ]; then
    echo "Press Enter to stop Quantum-Mixer..."
    read -r || exit 0
    info "Stopping Quantum-Mixer..."
    rq_docker_stop "$CONTAINER_NAME" || true
    info "Quantum-Mixer stopped."
else
    info "Quantum-Mixer keeps running in the background."
fi
