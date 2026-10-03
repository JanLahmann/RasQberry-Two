#!/bin/bash
set -euo pipefail

################################################################################
# rq_doqumentation.sh - RasQberry doQumentation (Workshop Server) Launcher
#
# Description:
#   Runs the doQumentation "jupyter-local" image in a Docker container: the
#   IBM Quantum tutorials, guides and courses as a local website whose code
#   cells run on a Qiskit Jupyter server on this Pi. One Pi serves the laptops
#   of a class over the LAN (Jan, Q30).
#
#   The image is pinned by digest per RasQberry release (manifest
#   entrypoint.docker_image); "Update demos" can move it to a newer upstream
#   build (rq_demo_image). It is downloaded on first use, after the consent
#   dialog with its size.
#
#   Re-opening attaches to a running server instead of restarting it (R-069,
#   R-145): Keep (default) / Restart / Stop, and Cancel keeps it. Only the
#   window that started the server offers to stop it. Without a screen (SSH)
#   it starts headless and prints the addresses (Jan, Q19).
#
# Container port model (jupyter-local target):
#   - nginx :80  serves the site and proxies the Jupyter API (/api/,
#                /terminals/), adding the token: participants need no token.
#   - jupyter :8888  direct JupyterLab (token), published on 127.0.0.1 only,
#                for the teacher on the Pi or over an ssh -L tunnel.
#   CORS_ORIGIN lists localhost, the Pi's .local name and its LAN addresses,
#   so code runs from every address a participant may use.
#
# Usage: rq_doqumentation.sh
#   DOQUMENTATION_PROFILE=2|8|15  skip the participants picker
#
# doQumentation is part of the "Fun with Quantum" family and is not affiliated
# with, endorsed by, or sponsored by IBM. Tutorial content is sourced from
# Qiskit/documentation (CC BY-SA 4.0); doQumentation code is Apache-2.0.
# Source: https://github.com/JanLahmann/doQumentation
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

echo
echo "=== doQumentation (Workshop Server) ==="
echo

load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

CONTAINER_NAME="doqumentation"
DOCKER_IMAGE="$(rq_demo_image doqumentation)"
[ -n "$DOCKER_IMAGE" ] || die "The doQumentation demo description (manifest) names no Docker image."

rq_docker_access "$@"

# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------
# The Pi's IPv4 LAN addresses (not Docker's own bridges)
lan_ips() {
    local ip
    if command -v ip >/dev/null 2>&1; then
        ip -4 -o addr show scope global 2>/dev/null \
            | awk '$2 !~ /^(docker|br-|veth|virbr)/ { sub(/\/.*/, "", $4); print $4 }' || true
        return 0
    fi
    for ip in $(hostname -I 2>/dev/null || true); do
        case "$ip" in *:*|172.17.*) continue ;; esac
        echo "$ip"
    done
}

# Host port a container port is published on (e.g. 80/tcp -> 8080)
published_port() {
    docker port "$CONTAINER_NAME" "$1" 2>/dev/null | head -1 | sed 's/.*://' || true
}

container_token() {
    docker container inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CONTAINER_NAME" 2>/dev/null \
        | sed -n 's/^JUPYTER_TOKEN=//p' | head -1 || true
}

# The addresses participants open, one per line
participant_urls() {
    local port="$1" ip
    echo "http://$(hostname 2>/dev/null).local:${port}/"
    for ip in $(lan_ips); do
        echo "http://${ip}:${port}/"
    done
}

# Print where everyone finds the server; LAB_URL only for this window
print_addresses() {
    local port="$1" lab_url="$2" url
    echo
    echo "Workshop Server (doQumentation) is running."
    echo
    echo "Participants open one of these addresses (same network as this Pi):"
    participant_urls "$port" | while IFS= read -r url; do echo "    $url"; done
    echo "On this Pi: http://localhost:${port}/"
    if command -v qrencode >/dev/null 2>&1; then
        qrencode -t ANSIUTF8 "$(participant_urls "$port" | sed -n 2p)" 2>/dev/null || true
    fi
    echo
    echo "Teacher only - JupyterLab with every notebook (on this Pi or through ssh -L):"
    echo "    $lab_url"
    echo
    echo "Trust: everyone on this network can run code on this server and change"
    echo "the shared notebooks. Use it on a class network you trust, not on public"
    echo "Wi-Fi. Notebooks idle for 10 minutes are stopped; work is not kept when"
    echo "the server stops - participants download what they want to keep."
    echo "The 'Open in Lab' button on the website does not work for participants yet."
    echo
}

# ---------------------------------------------------------------------------
# Already running? Attach instead of restarting it (R-069, R-145)
# ---------------------------------------------------------------------------
if rq_docker_running "$CONTAINER_NAME"; then
    action="KEEP"
    if [ -t 0 ]; then
        action=$(whiptail --title "Workshop Server is running" --default-item KEEP --menu \
            "doQumentation is already running. Participants may be using it.\nRestart or Stop ends their sessions and loses unsaved work." \
            14 74 3 \
            KEEP    "Keep it running and show the addresses" \
            RESTART "Restart it" \
            STOP    "Stop it" 3>&1 1>&2 2>&3) || action="KEEP"
    fi
    case "$action" in
        STOP)
            info "Stopping the Workshop Server..."
            rq_docker_stop "$CONTAINER_NAME" || warn "The container is still being removed."
            info "Workshop Server stopped."
            exit 0
            ;;
        RESTART)
            info "Stopping the Workshop Server..."
            rq_docker_stop "$CONTAINER_NAME" \
                || die "The old Workshop Server container did not go away; try again in a minute."
            ;;
        *)
            site_port=$(published_port 80/tcp)
            lab_port=$(published_port 8888/tcp)
            [ -n "$site_port" ] || die "The running Workshop Server publishes no website port."
            print_addresses "$site_port" "http://127.0.0.1:${lab_port:-?}/lab?token=$(container_token)"
            if [ "$(docker container inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null)" != "$DOCKER_IMAGE" ]; then
                info "A different doQumentation version is selected; Restart the server to use it."
            fi
            rq_show_url "http://127.0.0.1:${site_port}/" "$site_port"
            if [ -t 0 ]; then
                echo "This window did not start the server: closing it keeps the server running."
                echo "Press Enter to close this window."
                read -r || true
            fi
            exit 0
            ;;
    esac
fi
# A stopped container of an earlier run (kept for its log, R-109)
rq_docker_stop "$CONTAINER_NAME" 5 || true

# ---------------------------------------------------------------------------
# Participants (resource caps), sized to this Pi's memory (R-065, R-151)
# ---------------------------------------------------------------------------
MEM_TOTAL_MB=$(awk '/^MemTotal:/ { printf "%d\n", $2 / 1024 }' /proc/meminfo 2>/dev/null || echo 0)
MEM_CAP_MB=$(( MEM_TOTAL_MB > 1500 ? MEM_TOTAL_MB - 768 : 1024 ))

# map_profile <2|8|15>: PROFILE_USERS MEM MEMSWAP CPUS PIDS; fails if the Pi
# has too little memory for it
map_profile() {
    local want_mb min_mb swap_mb=0
    case "$1" in
        2)  PROFILE_USERS=2;  want_mb=3072; min_mb=0;    CPUS="2"; PIDS="256" ;;
        8)  PROFILE_USERS=8;  want_mb=6144; min_mb=3500; CPUS="3"; PIDS="512" ;;
        15) PROFILE_USERS=15; want_mb=7168; min_mb=7000; CPUS="4"; PIDS="1024"; swap_mb=1024 ;;
        *)  return 1 ;;
    esac
    [ "$MEM_TOTAL_MB" -ge "$min_mb" ] || return 1
    [ "$want_mb" -le "$MEM_CAP_MB" ] || want_mb=$MEM_CAP_MB
    MEM="${want_mb}m"
    MEMSWAP="$((want_mb + swap_mb))m"
    return 0
}

PROFILE=""
if [ -n "${DOQUMENTATION_PROFILE:-}" ]; then
    if map_profile "$DOQUMENTATION_PROFILE"; then
        PROFILE="$DOQUMENTATION_PROFILE"
    else
        warn "Ignoring DOQUMENTATION_PROFILE='$DOQUMENTATION_PROFILE' (2, 8 or 15, and 8/15 need a 4/8 GB Pi)"
    fi
fi

if [ -z "$PROFILE" ] && [ -t 0 ]; then
    set --
    map_profile 2 && set -- "$@" 2  "Up to ~2 participants (default)"
    map_profile 8 && set -- "$@" 8  "Up to ~8 participants (most of this Pi)"
    map_profile 15 && set -- "$@" 15 "Up to ~15 participants (all of this Pi)"
    if [ $# -gt 2 ]; then
        choice=$(whiptail --title "Workshop Server" --default-item 2 --menu \
            "How many participants run code at the same time?\nThis Pi has $(( (MEM_TOTAL_MB + 500) / 1000 )) GB of memory." \
            14 64 3 "$@" 3>&1 1>&2 2>&3) || { info "Not started."; exit 0; }
        map_profile "$choice" && PROFILE="$choice"
    fi
fi
if [ -z "$PROFILE" ]; then
    PROFILE="2"
    map_profile "$PROFILE"
fi
info "Up to ~${PROFILE_USERS} participants (memory ${MEM}, ${CPUS} CPUs)"

# ---------------------------------------------------------------------------
# Image: the pinned version, downloaded after the consent dialog
# ---------------------------------------------------------------------------
if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    rq_require_demo_consent doqumentation
    rq_docker_pull "$DOCKER_IMAGE" "doQumentation"
    rq_docker_drop_old "$DOCKER_IMAGE"
fi

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
SITE_PORT="${DOQUMENTATION_SITE_PORT:-$(find_available_port 8080)}"
LAB_PORT="${DOQUMENTATION_LAB_PORT:-$(find_available_port 8896)}"

JUPYTER_TOKEN="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' || true)"
[ -n "$JUPYTER_TOKEN" ] || JUPYTER_TOKEN="rasqberry-workshop"

CORS_ORIGIN="http://localhost:${SITE_PORT},http://127.0.0.1:${SITE_PORT}"
CORS_ORIGIN="${CORS_ORIGIN},http://$(hostname 2>/dev/null).local:${SITE_PORT}"
for ip in $(lan_ips); do
    CORS_ORIGIN="${CORS_ORIGIN},http://${ip}:${SITE_PORT}"
done

info "Starting the Workshop Server..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=doqumentation" \
    -p "${SITE_PORT}:80" \
    -p "127.0.0.1:${LAB_PORT}:8888" \
    --memory "$MEM" \
    --memory-swap "$MEMSWAP" \
    --cpus "$CPUS" \
    --pids-limit "$PIDS" \
    -e JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    -e CORS_ORIGIN="$CORS_ORIGIN" \
    "$DOCKER_IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The Workshop Server container did not start."
fi

info "Waiting for the website..."
SITE_URL="http://127.0.0.1:${SITE_PORT}/"
WAIT_COUNT=0
until curl -sf "$SITE_URL" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "The Workshop Server stopped while starting."
    if [ "$WAIT_COUNT" -ge 60 ]; then
        rq_docker_fail "$CONTAINER_NAME" "The Workshop Server did not answer within 60 seconds."
    fi
done

LAB_URL="http://127.0.0.1:${LAB_PORT}/lab?token=${JUPYTER_TOKEN}"
print_addresses "$SITE_PORT" "$LAB_URL"

if [ -t 0 ] && command -v whiptail >/dev/null 2>&1; then
    show_msgbox "Workshop Server is running" \
        "Participants open (same network as this Pi):\n\n$(participant_urls "$SITE_PORT" | sed 's/^/   /')\n\nEveryone on this network can run code here and change the shared notebooks: use a class network you trust." \
        16 70
fi

rq_show_url "$SITE_URL" "$SITE_PORT"

# ---------------------------------------------------------------------------
# This window started the server: only it offers to stop it (R-145)
# ---------------------------------------------------------------------------
if [ -t 0 ]; then
    echo "Closing this window keeps the server running (RasQberry menu: Quantum"
    echo "Demos > Stop Docker demos, or open doQumentation again to stop it)."
    echo "Press Enter to stop the Workshop Server..."
    read -r || exit 0
    if command -v whiptail >/dev/null 2>&1 && ! whiptail --title "Stop the Workshop Server?" --defaultno \
            --yes-button "Stop" --no-button "Keep running" --yesno \
            "Participants lose code they have not saved.\n\nStop the Workshop Server now?" 10 60; then
        info "The Workshop Server keeps running."
        exit 0
    fi
    info "Stopping the Workshop Server..."
    rq_docker_stop "$CONTAINER_NAME" || warn "The container is still being removed."
    info "Workshop Server stopped."
else
    info "The Workshop Server keeps running. Stop it with: docker stop $CONTAINER_NAME"
fi
