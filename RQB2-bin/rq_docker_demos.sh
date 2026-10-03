#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Docker demos - list or stop the running ones
# ============================================================================
# Description: Closing a Docker demo's window keeps the container running
#   (the Workshop & Qiskit Server is meant to). This lists the running demo
#   containers and stops the ones chosen (R-110).
# Usage: rq_docker_demos.sh --list | --stop-menu | --stop NAME...

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Containers of the shipped launchers (older ones carry no label)
KNOWN_NAMES="doqumentation quantum-lab qoffee quantum-mixer"

label_of() {
    case "$1" in
        doqumentation) echo "Workshop & Qiskit Server / Qiskit Tutorials" ;;
        quantum-lab)   echo "Quantum Lab (QuBins)" ;;
        qoffee)        echo "Qoffee-Maker" ;;
        quantum-mixer) echo "Quantum Mixer" ;;
        *)             echo "$1" ;;
    esac
}

# Running demo containers, one name per line
running() {
    {
        docker ps --filter "label=org.rasqberry.demo" --format '{{.Names}}' 2>/dev/null || true
        local n
        for n in $KNOWN_NAMES; do
            rq_docker_running "$n" && echo "$n"
        done
    } | sort -u
}

check_docker || { echo "Docker is not installed."; exit 0; }
[ "$(id -u)" = "0" ] || rq_docker_access "$@"

case "${1:-}" in
    --list)
        running
        ;;
    --stop)
        shift
        for n in "$@"; do
            info "Stopping $(label_of "$n")..."
            rq_docker_stop "$n" || warn "$n is still being removed"
        done
        ;;
    --stop-menu)
        names=$(running)
        if [ -z "$names" ]; then
            show_msgbox "Stop Docker demos" "No Docker demo is running."
            exit 0
        fi
        set --
        for n in $names; do
            set -- "$@" "$n" "$(label_of "$n")" ON
        done
        chosen=$(whiptail --title "Stop Docker demos" --checklist \
            "Running Docker demos. Stop the selected ones?\nWorkshop participants lose work they have not downloaded." \
            16 70 6 "$@" 3>&1 1>&2 2>&3) || exit 0
        for n in $(echo "$chosen" | tr -d '"'); do
            info "Stopping $(label_of "$n")..."
            rq_docker_stop "$n" || warn "$n is still being removed"
        done
        [ -n "$chosen" ] && show_msgbox "Stop Docker demos" "Stopped: $(for n in $(echo "$chosen" | tr -d '"'); do printf '%s, ' "$(label_of "$n")"; done | sed 's/, $//')."
        ;;
    *)
        die "Usage: $(basename "$0") --list | --stop-menu | --stop NAME..."
        ;;
esac
