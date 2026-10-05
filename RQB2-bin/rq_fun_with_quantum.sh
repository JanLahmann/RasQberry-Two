#!/bin/bash
set -euo pipefail

################################################################################
# rq_fun_with_quantum.sh - RasQberry Fun with Quantum Demo Launcher
#
# Description:
#   Launches the Fun with Quantum Jupyter notebooks for learning quantum
#   computing through interactive games and demonstrations.
#   Includes RISE slideshow extension for presentation mode.
#
# Usage:
#   rq_fun_with_quantum.sh [notebook]
#
# Arguments:
#   notebook  - Optional: specific notebook to open (e.g., Quantum-Coin-Game.ipynb)
#               Default: opens notebook directory listing
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

echo
echo "=== Fun with Quantum ==="
echo

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV MARKER_FWQ

# Demo configuration
DEMO_NAME="fun-with-quantum"
DEMO_DIR="$USER_HOME/$REPO/demos/$DEMO_NAME"
PORT="${FWQ_JUPYTER_PORT:-8888}"
NOTEBOOK="${1:-}"

# Jupyter process tracking
JUPYTER_PID=""

################################################################################
# Cleanup function
################################################################################
cleanup() {
    set +e   # a closed window cannot show messages: still stop the server
    trap '' HUP INT TERM
    info "Cleaning up..."
    if [ -n "$JUPYTER_PID" ] && kill -0 "$JUPYTER_PID" 2>/dev/null; then
        rq_close_demo_tabs   # before the server goes: no "Dead kernel" tab (#9)
        info "Stopping Jupyter server..."
        kill "$JUPYTER_PID" 2>/dev/null || true
        wait "$JUPYTER_PID" 2>/dev/null || true
    fi
}

################################################################################
# Main
################################################################################

# Setup cleanup trap
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# Without a screen (SSH) the server starts headless and the address and an
# ssh -L tunnel command are printed instead of opening a browser (Jan, Q19)

# Verify demo is installed
if [ ! -f "$DEMO_DIR/$MARKER_FWQ" ]; then
    die "Fun with Quantum is not installed. Run 'rq_demo_run.sh fun-with-quantum' (installs on demand) or install via raspi-config."
fi

# Activate virtual environment
info "Activating Python virtual environment..."
activate_venv || die "Failed to activate virtual environment"

# Check if Jupyter is available
if ! command -v jupyter &>/dev/null; then
    die "Jupyter is not installed. Please run the Qiskit installation first."
fi

# Check if port is already in use
if lsof -i ":$PORT" &>/dev/null; then
    warn "Port $PORT is already in use"
    # Try to find an available port
    for p in 8889 8890 8891 8892; do
        if ! lsof -i ":$p" &>/dev/null; then
            PORT=$p
            info "Using alternative port: $PORT"
            break
        fi
    done
fi

# Build Jupyter URL
if [ -n "$NOTEBOOK" ]; then
    JUPYTER_URL="http://127.0.0.1:${PORT}/notebooks/${NOTEBOOK}"
else
    JUPYTER_URL="http://127.0.0.1:${PORT}/tree"
fi

# Start Jupyter notebook
echo
info "Starting Jupyter notebook server..."
cd "$DEMO_DIR"

# Launch Jupyter in background.
#
# This demo runs the classic notebook 6 server on purpose: it offers the RISE
# slideshow (Alt+R), and RISE 5.7.1 needs notebook 6. The venv also has
# JupyterLab 4, whose pip install drops a config enabling the jupyterlab SERVER
# EXTENSION for NotebookApp - but a Lab 4 extension cannot load into notebook 6,
# so it threw a full traceback ("'NotebookApp' object has no attribute
# 'identity_provider'") across the terminal on every launch. The server carried
# on serving, yet the demo looked like it had crashed. Turn the extension off
# for this server; RISE and the notebooks are unaffected.
#
# The server's own log ("notebook is not trusted", kernel messages) goes to a
# file, not over this window (item 10). ws_ping_interval=0: notebook 6 hands
# its ping settings in milliseconds to a Tornado that reads seconds and
# warned "websocket_ping_timeout (90000) cannot be longer than the
# websocket_ping_interval (30000)" whenever a notebook opened. Keep-alive
# pings are not needed between the browser and 127.0.0.1.
SERVER_LOG="$USER_HOME/.cache/rasqberry/fun-with-quantum-server.log"
mkdir -p "$(dirname "$SERVER_LOG")" 2>/dev/null || true
: > "$SERVER_LOG" 2>/dev/null || SERVER_LOG=/dev/null
jupyter notebook \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --NotebookApp.token='' \
    --NotebookApp.password='' \
    --NotebookApp.open_browser=False \
    --NotebookApp.nbserver_extensions="{'jupyterlab':False}" \
    --NotebookApp.tornado_settings="{'ws_ping_interval': 0}" \
    >"$SERVER_LOG" 2>&1 &
JUPYTER_PID=$!

# Wait for Jupyter to start
info "Waiting for Jupyter to start..."
sleep 3

# Verify Jupyter is running
if ! kill -0 "$JUPYTER_PID" 2>/dev/null; then
    [ -s "$SERVER_LOG" ] && tail -5 "$SERVER_LOG"
    die "Jupyter failed to start (log: $SERVER_LOG)"
fi

# Wait until it answers: on a busy Pi 4 the port opens a few seconds after
# the 3 s above, and a browser opened before that shows "can't be reached"
# (and its tab was taken for one whose demo had stopped). The loop returns
# as soon as Jupyter answers, so the limit costs nothing.
waited=0
while ! curl -s -o /dev/null "http://127.0.0.1:${PORT}/" 2>/dev/null; do
    kill -0 "$JUPYTER_PID" 2>/dev/null || { [ -s "$SERVER_LOG" ] && tail -5 "$SERVER_LOG"; die "Jupyter exited during startup (log: $SERVER_LOG)"; }
    [ "$waited" -lt 60 ] || die "Jupyter did not answer within 60 seconds (log: $SERVER_LOG)"
    sleep 1
    waited=$((waited + 1))
done

# The notebooks, as the demo menu lists them (the manifest's variants), so
# this list cannot fall behind the demo again (item 10)
notebook_list() {
    local mf
    mf=$(rq_find_manifest "$(rq_shipped_manifest_dir)" fun-with-quantum 2>/dev/null) || return 0
    jq -r '.variants[]? | select((.args // [])[0] // "" | endswith(".ipynb"))
           | "    - \(.name)  (\(.args[0]))"' "$mf" 2>/dev/null || true
}

echo
echo "Fun with Quantum is running: $JUPYTER_URL"
echo
echo "  Notebooks:"
notebook_list
echo
echo "  Slideshow (RISE): Alt+R in a notebook"
echo "  Server log: $SERVER_LOG"
echo

# Try to open browser (its console output would be drawn over the
# raspi-config menu, R-137)
rq_show_url "$JUPYTER_URL" "$PORT"

# Enter, Ctrl+C or closing this window stops it (items 5, 33); without a
# terminal it runs until the server ends. The cleanup trap stops the server.
[ -t 0 ] || info "Jupyter server running in background (PID: $JUPYTER_PID). Stop with: kill $JUPYTER_PID"
rq_wait_for_stop "Fun with Quantum" "$JUPYTER_PID"
