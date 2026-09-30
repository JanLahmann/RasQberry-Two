#!/bin/bash
set -euo pipefail

################################################################################
# rq_doqumentation.sh - RasQberry doQumentation (Workshop Server) Launcher
#
# Description:
#   Runs the doQumentation "jupyter-local" stack in a Docker container: a local
#   IBM Quantum tutorials/guides/courses website (Docusaurus) with live
#   in-browser code execution against a bundled, Qiskit-laden Jupyter server.
#   This is the basis for a RasQberry "Workshop Server".
#
#   The image is pulled on demand from ghcr.io on first run (~3 GB); it is NOT
#   baked into the base OS image.
#
#   Follows the qoffee-maker.sh / rq_quantum_lab.sh pattern: the manifest
#   declares entrypoint type "docker" plus this dedicated launcher, which
#   handles Docker setup, permissions, image pull, the concurrency-profile
#   picker, container lifecycle and the browser launch.
#
# Container port model (jupyter-local target, verified against the Dockerfile):
#   - nginx :80   serves the static site AND reverse-proxies the Jupyter API
#                 (/api/, /terminals/), injecting the auth token. Code execution
#                 through the site needs NO token from the user.
#   - jupyter :8888  direct JupyterLab (token required); backs the site's
#                    "Open in Lab" button.
#   The site port is published as host 8080 (8080->80); we also publish
#   8888->8888 for the "Open in Lab" button. For LAN participants we pass a
#   CORS_ORIGIN allowlist (doQumentation PR #386) so in-browser execution works
#   from the Pi's mDNS name and LAN IPs, not just localhost. Older images that
#   predate #386 ignore CORS_ORIGIN and fall back to allow_origin=localhost:8080.
#
# Concurrency profiles:
#   A launch-time picker selects how much of the Pi to dedicate to the workshop.
#   2 users is the zero-friction default (chosen automatically when there is no
#   TTY, e.g. desktop-icon launch). Override non-interactively with
#   DOQUMENTATION_PROFILE=2|8|15.
#
# doQumentation is part of the "Fun with Quantum" family and is not affiliated
# with, endorsed by, or sponsored by IBM. Tutorial content is sourced from
# Qiskit/documentation (CC BY-SA 4.0); doQumentation code is Apache-2.0.
# Source: https://github.com/JanLahmann/doQumentation
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

echo
echo "=== doQumentation (Workshop Server) ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

# Tracks the :jupyter tag (on-demand pull, so upstream fixes flow automatically).
# Known-good as of 2026-07-13: sha256:2ab9cf90a741f9183e1e6ed857f94ad5e307378b1f9cacb4faa62f50de38d969
# (ghcr run 29247875829, commit b01bf7c19: qiskit 2.5.0 + the CORS + nginx-sed
# fixes, built via the native matrix). Recorded for reproducibility/debugging.
DOCKER_IMAGE="ghcr.io/janlahmann/doqumentation:jupyter"
CONTAINER_NAME="doqumentation"
# Site (nginx) host port. Defaults to 8080 (the image's default allow_origin
# and tested port). The CORS allowlist below is derived from this port, so LAN
# execution follows it on doQumentation #386+ images; 8080 remains the default.
SITE_PORT="${DOQUMENTATION_SITE_PORT:-$(find_available_port 8080)}"
# Direct JupyterLab host port (backs the "Open in Lab" button). Base 8896 keeps
# it clear of the 8888-8891 range the Jupyter demos allocate, and it shifts
# again if that is taken - fixes the "bind 8888: address already in use" clash.
LAB_PORT="${DOQUMENTATION_LAB_PORT:-$(find_available_port 8896)}"

################################################################################
# Prerequisites: Docker (mirrors rq_quantum_lab.sh)
################################################################################

check_docker || die "Error: Docker is not installed (the image may be misbuilt)."

USER_NAME=$(get_user_name)
if ! groups "$USER_NAME" | grep -q docker && [ "$USER_NAME" != "root" ]; then
    die "Error: User '$USER_NAME' is not in the docker group (the image may be misbuilt)."
fi

# Activate the docker group in this session without a logout, then re-exec.
if ! groups | grep -q docker && [ "$(whoami)" != "root" ]; then
    info "Docker group not active in current session"
    info "Activating Docker group permissions..."
    if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$0 $*"
    fi
fi

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
# Concurrency profile selection
#
# Each profile maps to container-level resource limits passed to `docker run`.
# The single Jupyter server spawns one Qiskit kernel per active participant, so
# these caps bound how much of the 8 GB Pi the workshop may consume. Memory
# cgroup limits require the memory cgroup to be enabled in the kernel cmdline;
# if it is not, Docker prints a warning and ignores --memory (non-fatal).
################################################################################

# map_profile <2|8|15> -> sets PROFILE_USERS, MEM, MEMSWAP, CPUS, PIDS
map_profile() {
    case "$1" in
        2)
            PROFILE_USERS=2;  MEM="3g"; MEMSWAP="3g"; CPUS="2"; PIDS="256"  ;;
        8)
            PROFILE_USERS=8;  MEM="6g"; MEMSWAP="6g"; CPUS="3"; PIDS="512"  ;;
        15)
            PROFILE_USERS=15; MEM="7g"; MEMSWAP="8g"; CPUS="4"; PIDS="1024" ;;
        *)
            return 1 ;;
    esac
    return 0
}

PROFILE=""
# Non-interactive override (desktop icon, scripted launch)
if [ -n "${DOQUMENTATION_PROFILE:-}" ]; then
    if map_profile "$DOQUMENTATION_PROFILE"; then
        PROFILE="$DOQUMENTATION_PROFILE"
    else
        warn "Ignoring invalid DOQUMENTATION_PROFILE='$DOQUMENTATION_PROFILE' (expected 2, 8 or 15)"
    fi
fi

# Interactive picker (default/first option is the 2-user, zero-friction path)
if [ -z "$PROFILE" ] && [ -t 0 ]; then
    choice=$(show_menu "doQumentation - Concurrency" \
        "How many participants should this Workshop Server support?\n\nA single Pi runs one Jupyter server; each active user spawns a Qiskit kernel. Larger profiles dedicate more of the Pi's RAM/CPU." \
        "2"  "Small  - up to ~2 users  (default, leaves headroom)" \
        "8"  "Medium - up to ~8 users  (dedicates most of the Pi)" \
        "15" "Large  - up to ~15 users (uses nearly all resources)" ) || choice=""
    if [ -n "$choice" ] && map_profile "$choice"; then
        PROFILE="$choice"
    fi
fi

# Default: zero-friction 2-user profile (no TTY, or picker cancelled)
if [ -z "$PROFILE" ]; then
    PROFILE="2"
    map_profile "$PROFILE"
fi

info "Concurrency profile: ${PROFILE_USERS}-user (memory=${MEM}, cpus=${CPUS}, pids=${PIDS})"

################################################################################
# Docker container management
################################################################################

info "Checking for existing containers..."
if docker ps -q --filter name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
    info "Stopping existing doQumentation container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
fi
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Pull the image only if it is not already present locally (~3 GB on first run).
if ! docker images -q "$DOCKER_IMAGE" 2>/dev/null | grep -q .; then
    echo
    info "doQumentation image not found locally."
    info "Pulling $DOCKER_IMAGE ..."
    info "This is a ~3 GB download and may take a while on first run."
    if ! docker pull "$DOCKER_IMAGE"; then
        echo
        die "Failed to pull Docker image. Please check your internet connection"
    fi
fi

# Generate a workshop token so the site logs and the "Open in Lab" URL are
# deterministic for this run. Site-driven execution on $SITE_PORT injects this
# token transparently (no user prompt); direct :$LAB_PORT JupyterLab requires it.
JUPYTER_TOKEN="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' || true)"
[ -n "$JUPYTER_TOKEN" ] || JUPYTER_TOKEN="rasqberry-workshop"

# CORS allowlist for in-browser code execution (doQumentation PR #386 contract).
# The site is opened at http://<addr>:${SITE_PORT} both on the Pi and by LAN
# participants; doQumentation's Jupyter enforces allow_origin, so every address a
# browser might use must be listed. We pass a comma-separated CORS_ORIGIN
# (localhost + the Pi's mDNS name + its current IPv4 LAN addresses); the image
# compiles it into an anchored allow_origin_pat. On images predating #386 this
# env is ignored (they fall back to allow_origin=http://localhost:${SITE_PORT}),
# so passing it is safe and forward-compatible.
build_cors_origin() {
    local port="$1" origins host ip
    origins="http://localhost:${port},http://127.0.0.1:${port}"
    host="$(hostname 2>/dev/null || true)"
    [ -n "$host" ] && origins="${origins},http://${host}.local:${port}"
    for ip in $(hostname -I 2>/dev/null || true); do
        case "$ip" in
            *:*) continue ;;   # skip IPv6
        esac
        origins="${origins},http://${ip}:${port}"
    done
    printf '%s' "$origins"
}
CORS_ORIGIN="$(build_cors_origin "$SITE_PORT")"
info "CORS allowlist (active on doQumentation #386+ images): ${CORS_ORIGIN}"

################################################################################
# Start container
#
# -p 8080:80    site (nginx) - fixed host port 8080 (allow_origin constraint)
# -p 8888:8888  direct JupyterLab / "Open in Lab" button
# Resource caps come from the selected concurrency profile.
################################################################################
echo
info "Starting doQumentation container..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --rm \
    -p "${SITE_PORT}:80" \
    -p "${LAB_PORT}:8888" \
    --memory "$MEM" \
    --memory-swap "$MEMSWAP" \
    --cpus "$CPUS" \
    --pids-limit "$PIDS" \
    -e JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    -e CORS_ORIGIN="$CORS_ORIGIN" \
    "$DOCKER_IMAGE"; then
    echo
    die "Failed to start Docker container. Check logs with: docker logs $CONTAINER_NAME"
fi

# Wait for the site (nginx) to answer
info "Waiting for the doQumentation site to start..."
SITE_URL="http://127.0.0.1:${SITE_PORT}/"
MAX_WAIT=45
WAIT_COUNT=0
until curl -sf "$SITE_URL" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if ! docker ps --filter name="$CONTAINER_NAME" --filter status=running | grep -q "$CONTAINER_NAME"; then
        echo
        echo "Error: Container stopped unexpectedly."
        echo "Logs:"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20 || true
        die "Container failed to start"
    fi
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20 || true
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        die "doQumentation site did not respond after ${MAX_WAIT} seconds"
    fi
done

info "doQumentation site ready!"

################################################################################
# Browser launch
################################################################################
LAB_URL="http://127.0.0.1:${LAB_PORT}/lab?token=${JUPYTER_TOKEN}"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo
echo "✓ doQumentation is running!"
echo
echo "  Tutorials website (execute code in-browser, no token needed):"
echo "    $SITE_URL"
if [ -n "$LAN_IP" ]; then
    echo "    http://${LAN_IP}:${SITE_PORT}/   (LAN participants; see note below)"
fi
echo
echo "  Direct JupyterLab / 'Open in Lab' (token required):"
echo "    $LAB_URL"
echo
echo "  Concurrency profile: ${PROFILE_USERS}-user"
echo "  Content licensed under CC BY-SA 4.0 by IBM/Qiskit."
echo
echo "  Note: LAN in-browser execution requires a doQumentation image that"
echo "  supports CORS_ORIGIN (PR #386+); this launcher passes the Pi's mDNS"
echo "  name and LAN IPs. On older images allow_origin is pinned to"
echo "  localhost:${SITE_PORT}, so only on-Pi 'Run' works until the image updates."
echo

# Open browser as the desktop user (never as root)
if command -v chromium-browser &>/dev/null; then
    info "Opening browser..."
    run_as_user chromium-browser --password-store=basic "$SITE_URL" &
elif command -v firefox &>/dev/null; then
    info "Opening browser..."
    run_as_user firefox "$SITE_URL" &
elif command -v xdg-open &>/dev/null; then
    info "Opening browser..."
    run_as_user xdg-open "$SITE_URL" &
else
    info "No browser found. Please open manually: $SITE_URL"
fi

################################################################################
# Interactive wait and cleanup (matches rq_quantum_lab.sh lifecycle)
################################################################################
echo
echo "============================================"
echo "  doQumentation is running in the background"
echo "============================================"
echo
echo "To stop the container, run:"
echo "  docker stop $CONTAINER_NAME"
echo

if [ -t 0 ]; then
    echo "Press Enter to stop the container now..."
    read -r
    echo
    info "Stopping doQumentation container..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    info "Container stopped"
    echo
else
    info "Container will keep running in the background"
    info "Use 'docker stop $CONTAINER_NAME' to stop it when done"
    echo
fi
