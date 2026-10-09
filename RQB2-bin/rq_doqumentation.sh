#!/bin/bash
set -euo pipefail

################################################################################
# rq_doqumentation.sh - RasQberry Workshop & Qiskit Server Launcher
#
# Description:
#   Runs the doQumentation "jupyter-local" image in a Docker container: the
#   IBM Quantum tutorials, guides and courses as a local website whose code
#   cells run on a Qiskit Jupyter server on this Pi.
#
#   Two ways to run it (Jan, 2026-10-03):
#   - Workshop & Qiskit Server (default): one Pi serves the laptops of a class
#     over the LAN (Jan, Q30). Participants picker, addresses, QR code.
#   - Qiskit Tutorials on this Pi, --solo: just the person at this Pi. Bound
#     to 127.0.0.1 only, the smallest memory profile, no picker or addresses;
#     opens the browser, and stops with its window.
#
#   The image is pinned by digest per RasQberry release (manifest
#   entrypoint.docker_image); "Update demos" can move it to a newer upstream
#   build (rq_demo_image). It is downloaded on first use, after the consent
#   dialog with its size.
#
#   Re-opening attaches to a running server instead of restarting it (R-069,
#   R-145): Keep (default) / Restart / Stop, and Cancel keeps it. A server
#   running in the other mode can be restarted in the requested one. Only the
#   window that started the server offers to stop it. Without a screen (SSH)
#   it starts headless and prints the addresses (Jan, Q19).
#
# Container port model (jupyter-local target):
#   - nginx :80  serves the site and proxies the Jupyter API (/api/),
#                adding the token: participants need no token.
#                Published on all addresses (workshop) or 127.0.0.1 (solo).
#                LAB_ENABLED=false hides "Open in Lab" (nginx serves no /lab),
#                ALLOW_TERMINALS=false refuses shells for participants
#                (doQumentation#963, #980; set explicitly, R-070).
#   - jupyter :8888  direct JupyterLab (token), published on 127.0.0.1 only,
#                for the teacher on the Pi or over an ssh -L tunnel.
#   CORS_ORIGIN lists localhost, and for a workshop the Pi's .local name and
#   its LAN addresses, so code runs from every address a participant may use.
#   The container's label org.rasqberry.mode says which mode it runs in.
#
# Usage: rq_doqumentation.sh [--solo]
#   DOQUMENTATION_PROFILE=2|8|15  skip the participants picker (workshop)
#
# doQumentation is part of the "Fun with Quantum" family and is not affiliated
# with, endorsed by, or sponsored by IBM. Tutorial content is sourced from
# Qiskit/documentation (CC BY-SA 4.0); doQumentation code is Apache-2.0.
# Source: https://github.com/JanLahmann/doQumentation
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

WORKSHOP_NAME="Workshop & Qiskit Server"
SOLO_NAME="Qiskit Tutorials on this Pi"
MODE="workshop"
case "${1:-}" in
    --solo) MODE="solo" ;;
    "") ;;
    *) die "Usage: $(basename "$0") [--solo]" ;;
esac
mode_name() { if [ "$1" = "solo" ]; then echo "$SOLO_NAME"; else echo "$WORKSHOP_NAME"; fi; }
NAME=$(mode_name "$MODE")

rq_demo_header "$NAME"

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

# The mode the running container was started in (label; older ones: workshop)
running_mode() {
    local mode
    mode=$(docker container inspect -f '{{index .Config.Labels "org.rasqberry.mode"}}' \
        "$CONTAINER_NAME" 2>/dev/null || true)
    [ "$mode" = "solo" ] && echo solo || echo workshop
}

# The name participants' laptops reach this Pi by: the one avahi announces.
# With a second kit of the same name on the network, <hostname>.local is the
# other Pi (#3).
MDNS_NAME=$(rq_mdns_name)
CONFIGURED_NAME="$(hostname 2>/dev/null).local"

# One line when the configured name belongs to another device, else nothing
name_note() {
    [ "$MDNS_NAME" != "$CONFIGURED_NAME" ] || return 0
    echo "Note: $CONFIGURED_NAME is another device on this network, so this Pi is $MDNS_NAME. To give it its own name: RasQberry menu > Remote Access & Security > Name."
}

# The addresses participants open, one per line
participant_urls() {
    local port="$1" ip
    echo "http://${MDNS_NAME}:${port}/"
    for ip in $(lan_ips); do
        echo "http://${ip}:${port}/"
    done
}

# Item 19: what the server means for this Pi, precise and calm
TRUST_SHORT="Anyone on this network can open these addresses and run code on this Pi: use a network you trust, not public Wi-Fi. Restarting the server restores the original notebooks."
# The image serves its code runner (thebelab) and maths fonts itself since
# doQumentation#964/#975, so code runs offline (R-068). Left online: IBM
# Quantum computers, and formulas inside code output (MathJax from a CDN).
INTERNET_NOTE="Code runs on this Pi, also without the internet; only IBM Quantum computers need it."

# A QR code of the first LAN address, for phones and tablets: 29 columns by
# 15 lines (margin 2). Shown last, just above the Enter prompt, so that it
# fits an 80x24 window whole. Needs the qrencode command (package qrencode);
# without it, or without a LAN address, nothing.
print_qr() {
    local url
    command -v qrencode >/dev/null 2>&1 || return 0
    url=$(participant_urls "$1" | sed -n 2p) || url=""
    [ -n "$url" ] || return 0
    echo
    echo "Participants can also scan this code: $url"
    qrencode -t ANSIUTF8 -m 2 "$url" 2>/dev/null || true
    echo
}

# Print where everyone finds the server; LAB_URL only for this window
print_addresses() {
    local port="$1" lab_url="$2" url
    echo
    echo "$WORKSHOP_NAME is running."
    echo
    echo "Participants open one of these addresses (same network as this Pi):"
    participant_urls "$port" | while IFS= read -r url; do echo "    $url"; done
    echo "On this Pi: http://localhost:${port}/"
    if [ -n "$(name_note)" ]; then
        echo
        name_note | fold -s -w 78
    fi
    echo
    echo "Teacher only - JupyterLab with every notebook (on this Pi or through ssh -L):"
    echo "    $lab_url"
    echo
    echo "Please note:"
    echo "- Anyone on this network can open these addresses and run code on this Pi."
    echo "  Use it on a network you trust (a class or home network), not on public Wi-Fi."
    echo "- Everyone works on the same notebooks. Restarting the server restores the"
    echo "  original notebooks; participants download what they want to keep."
    echo "- Code in a notebook left idle for 10 minutes stops; run its cells again."
    echo "- Code runs on this Pi, also without the internet; only IBM Quantum"
    echo "  computers need it."
    echo
}

# Print where the person at this Pi finds it (solo mode)
print_local() {
    local port="$1" lab_url="$2"
    echo
    echo "$SOLO_NAME is running: http://localhost:${port}/"
    echo "Only this Pi can open it. Restarting it restores the original notebooks;"
    echo "download what you want to keep."
    echo "$INTERNET_NOTE"
    echo
    echo "JupyterLab with every notebook: $lab_url"
    echo
}

# What a running server offers, by mode
print_running() {
    local mode="$1" site_port="$2" lab_url="$3"
    if [ "$mode" = "solo" ]; then
        print_local "$site_port" "$lab_url"
    else
        print_addresses "$site_port" "$lab_url"
    fi
}

# ---------------------------------------------------------------------------
# Already running? Attach instead of restarting it (R-069, R-145)
# ---------------------------------------------------------------------------
if rq_docker_running "$CONTAINER_NAME"; then
    RUNNING_MODE=$(running_mode)
    RUNNING_NAME=$(mode_name "$RUNNING_MODE")
    action="KEEP"
    if [ -t 0 ]; then
        if [ "$RUNNING_MODE" = "$MODE" ]; then
            [ "$MODE" = "solo" ] && keep_text="Keep it running and open it" \
                || keep_text="Keep it running and show the addresses"
            set -- KEEP "$keep_text" RESTART "Restart it" STOP "Stop it"
            [ "$MODE" = "solo" ] && question="$NAME is already running." \
                || question="$NAME is already running. Participants may be using it.\nRestart or Stop ends their sessions and loses unsaved work."
            default="KEEP"
        elif [ "$RUNNING_MODE" = "solo" ]; then
            # Bound to this Pi only: participants cannot reach it
            set -- RESTART "Restart it for the group (others on the network can join)" \
                   KEEP    "Keep it for this Pi only and open it" \
                   STOP    "Stop it"
            question="$RUNNING_NAME is running, for this Pi only.\nOthers on the network can join after a restart."
            default="RESTART"
        else
            set -- KEEP    "Open the running server on this Pi" \
                   RESTART "Restart it for this Pi only (participants lose their sessions)" \
                   STOP    "Stop it"
            question="$RUNNING_NAME is running. Participants may be using it."
            default="KEEP"
        fi
        action=$(whiptail --title "$RUNNING_NAME is running" --default-item "$default" --menu \
            "$question" 14 78 3 "$@" 3>&1 1>&2 2>&3) || action="KEEP"
        set --
    fi
    case "$action" in
        STOP)
            info "Stopping $RUNNING_NAME..."
            rq_docker_stop "$CONTAINER_NAME" || warn "The container is still being removed."
            info "$RUNNING_NAME stopped."
            exit 0
            ;;
        RESTART)
            info "Stopping $RUNNING_NAME..."
            rq_docker_stop "$CONTAINER_NAME" \
                || die "The old $RUNNING_NAME container did not go away; try again in a minute."
            ;;
        *)
            site_port=$(published_port 80/tcp)
            lab_port=$(published_port 8888/tcp)
            [ -n "$site_port" ] || die "The running $RUNNING_NAME publishes no website port."
            print_running "$RUNNING_MODE" "$site_port" "http://127.0.0.1:${lab_port:-?}/lab?token=$(container_token)"
            if [ "$(docker container inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null)" != "$DOCKER_IMAGE" ]; then
                info "A different doQumentation version is selected; Restart the server to use it."
            fi
            rq_show_url "http://127.0.0.1:${site_port}/" "$site_port"
            if [ "$RUNNING_MODE" = "workshop" ]; then print_qr "$site_port"; fi
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
if [ "$MODE" = "solo" ]; then
    # One person: the smallest profile, no picker
    PROFILE="2"
elif [ -n "${DOQUMENTATION_PROFILE:-}" ]; then
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
        choice=$(whiptail --title "$WORKSHOP_NAME" --default-item 2 --menu \
            "How many participants run code at the same time?\nThis Pi has $(( (MEM_TOTAL_MB + 500) / 1000 )) GB of memory." \
            14 64 3 "$@" 3>&1 1>&2 2>&3) || { info "Not started."; exit 0; }
        map_profile "$choice" && PROFILE="$choice"
    fi
fi
if [ -z "$PROFILE" ]; then
    PROFILE="2"
fi
map_profile "$PROFILE"
if [ "$MODE" = "solo" ]; then
    info "For you on this Pi (memory ${MEM}, ${CPUS} CPUs)"
else
    info "Up to ~${PROFILE_USERS} participants (memory ${MEM}, ${CPUS} CPUs)"
fi

# ---------------------------------------------------------------------------
# Image: the pinned version, downloaded after the consent dialog
# ---------------------------------------------------------------------------
if ! docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    # named as started: Qiskit Tutorials on this Pi said "Workshop & Qiskit
    # Server" in its download question and errors (user test 2026-10-07)
    RQ_CONSENT_NAME="$NAME" rq_require_demo_consent doqumentation
    # and its download line too: "Downloading Qiskit Tutorials on this Pi",
    # not the image's name (pre-beta check 2026-10-08)
    rq_demo_docker_pull doqumentation "$DOCKER_IMAGE" "$NAME"
    DOCKER_IMAGE="$RQ_DOCKER_PULLED"
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
if [ "$MODE" = "solo" ]; then
    SITE_PUBLISH="127.0.0.1:${SITE_PORT}:80"
else
    SITE_PUBLISH="${SITE_PORT}:80"
    CORS_ORIGIN="${CORS_ORIGIN},http://${MDNS_NAME}:${SITE_PORT}"
    [ "$MDNS_NAME" = "$CONFIGURED_NAME" ] || CORS_ORIGIN="${CORS_ORIGIN},http://${CONFIGURED_NAME}:${SITE_PORT}"
    for ip in $(lan_ips); do
        CORS_ORIGIN="${CORS_ORIGIN},http://${ip}:${SITE_PORT}"
    done
fi

info "Starting $NAME..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=doqumentation" \
    --label "org.rasqberry.mode=$MODE" \
    -p "$SITE_PUBLISH" \
    -p "127.0.0.1:${LAB_PORT}:8888" \
    --memory "$MEM" \
    --memory-swap "$MEMSWAP" \
    --cpus "$CPUS" \
    --pids-limit "$PIDS" \
    -e JUPYTER_TOKEN="$JUPYTER_TOKEN" \
    -e CORS_ORIGIN="$CORS_ORIGIN" \
    -e MPLCONFIGDIR=/tmp/matplotlib \
    -e LAB_ENABLED=false \
    -e ALLOW_TERMINALS=false \
    "$DOCKER_IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The $NAME container did not start."
fi

info "Waiting for the website..."
SITE_URL="http://127.0.0.1:${SITE_PORT}/"
WAIT_COUNT=0
until curl -sf "$SITE_URL" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "$NAME stopped while starting."
    if [ "$WAIT_COUNT" -ge 60 ]; then
        rq_docker_fail "$CONTAINER_NAME" "$NAME did not answer within 60 seconds."
    fi
done

LAB_URL="http://127.0.0.1:${LAB_PORT}/lab?token=${JUPYTER_TOKEN}"
print_running "$MODE" "$SITE_PORT" "$LAB_URL"

if [ "$MODE" = "workshop" ] && [ -t 0 ] && command -v whiptail >/dev/null 2>&1; then
    note=$(name_note)
    show_msgbox "$WORKSHOP_NAME is running" \
        "Participants open (same network as this Pi):\n\n$(participant_urls "$SITE_PORT" | sed 's/^/   /')\n\n${note:+$note\n\n}$TRUST_SHORT\n\n$INTERNET_NOTE" \
        17 74
fi

rq_show_url "$SITE_URL" "$SITE_PORT"
if [ "$MODE" = "workshop" ]; then print_qr "$SITE_PORT"; fi

# ---------------------------------------------------------------------------
# This window started the server: only it offers to stop it (R-145)
# ---------------------------------------------------------------------------
if [ "$MODE" = "solo" ]; then
    # Just you: the server goes with its window like every Docker demo
    # (Enter, Ctrl+C or closing it; without a terminal it keeps running)
    rq_docker_stop_with_window "$CONTAINER_NAME" "$NAME"
    exit 0
fi

if [ -t 0 ]; then
    echo "Closing this window keeps the server running (RasQberry menu: Quantum"
    echo "Demos > Manage demos > Stop Docker demos, or open $WORKSHOP_NAME again)."
    echo "Press Enter to stop the $WORKSHOP_NAME..."
    # Wait for Enter, but end with the server: stopped from its icon (STOP)
    # or with Stop Docker demos, it left this window behind, which then
    # offered to stop a server that was gone (Pi 4 user test 2026-10-07, F4)
    while :; do
        if ! rq_docker_running "$CONTAINER_NAME"; then
            info "The $WORKSHOP_NAME was stopped."
            sleep 3     # readable before the window closes
            exit 0
        fi
        rc=0
        rq_read_deferred -r -t 2 _ || rc=$?
        [ "$rc" -eq 0 ] && break         # Enter
        [ "$rc" -gt 128 ] || exit 0      # no more input
    done
    if ! rq_docker_running "$CONTAINER_NAME"; then
        info "The $WORKSHOP_NAME was stopped."
        exit 0
    fi
    if command -v whiptail >/dev/null 2>&1 && ! whiptail --title "Stop the $WORKSHOP_NAME?" --defaultno \
            --yes-button "Stop" --no-button "Keep running" --yesno \
            "Participants lose work they have not downloaded.\n\nStop the $WORKSHOP_NAME now?" 10 60; then
        info "The $WORKSHOP_NAME keeps running."
        exit 0
    fi
    info "Stopping the $WORKSHOP_NAME..."
    rq_docker_stop "$CONTAINER_NAME" || warn "The container is still being removed."
    info "$WORKSHOP_NAME stopped."
else
    info "The $WORKSHOP_NAME keeps running. To stop it: open it again, or RasQberry menu > Quantum Demos > Manage demos > Stop Docker demos."
fi
