#!/bin/bash
set -euo pipefail

################################################################################
# rq_quantum_paradoxes.sh - Quantum Paradoxes Demo Launcher
#
# Description:
#   Launches JupyterLab with quantum-paradoxes notebooks
#   Auto-opens WELCOME.ipynb in the browser
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV MARKER_PARADOXES PARADOXES_JUPYTER_PORT

# Check for GUI/Desktop environment
if ! check_display; then
    echo ""
    echo "=========================================="
    echo "ERROR: Graphical Desktop Required"
    echo "=========================================="
    echo ""
    echo "This demo requires a graphical desktop environment (GUI)."
    echo "It cannot run from a terminal-only session."
    echo ""
    echo "To run this demo:"
    echo "  1. Connect via VNC or use the desktop environment"
    echo "  2. Open a terminal in the desktop"
    echo "  3. Run this demo from there"
    echo ""
    echo "Or use the desktop launcher icon instead."
    echo ""
    die "No display available"
fi

DEMO_DIR="$USER_HOME/$REPO/demos/quantum-paradoxes"
PORT="${PARADOXES_JUPYTER_PORT:-8891}"

# Check if demo is installed
if [ ! -f "$DEMO_DIR/$MARKER_PARADOXES" ]; then
    echo "Error: Quantum Paradoxes demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    debug "USER_HOME: $USER_HOME"
    debug "REPO: $REPO"
    debug "Expected path: $DEMO_DIR"
    die "Quantum Paradoxes demo not installed"
fi

info "Starting Quantum Paradoxes Demo..."
debug "Demo directory: $DEMO_DIR"
debug "JupyterLab port: $PORT"

# Activate virtual environment
activate_venv || warn "Virtual environment not available"

# Verify jupyter-lab is available
if ! command -v jupyter-lab >/dev/null 2>&1; then
    die "JupyterLab not found. Please ensure Qiskit is installed."
fi

# Find available port
while netstat -tuln 2>/dev/null | grep -q ":$PORT "; do
    PORT=$((PORT + 1))
done

info "Using port: $PORT"

# Generate token for security
JUPYTER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
WELCOME_URL="http://localhost:${PORT}/lab/tree/WELCOME.ipynb?token=${JUPYTER_TOKEN}"

# Change to demo directory
cd "$DEMO_DIR" || die "Failed to change to demo directory"

# Check if port is already in use
if netstat -tuln 2>/dev/null | grep -q ":$PORT " || ss -tuln 2>/dev/null | grep -q ":$PORT "; then
    echo ""
    echo "ERROR: Port $PORT is already in use!"
    echo ""
    echo "Another Jupyter server or application may be running on this port."
    echo "You can:"
    echo "  1. Stop the other application first"
    echo "  2. Check running Jupyter servers: jupyter server list"
    echo "  3. Kill all Jupyter processes: pkill -f jupyter"
    echo ""
    die "Port $PORT already in use"
fi

info "Launching JupyterLab on port $PORT..."

# Create temp log file for debugging
JUPYTER_LOG=$(mktemp /tmp/jupyter-paradoxes-XXXXXX.log)

# Start JupyterLab in background, capturing output
jupyter-lab \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --ServerApp.token="$JUPYTER_TOKEN" \
    --ServerApp.password="" \
    >"$JUPYTER_LOG" 2>&1 &

JUPYTER_PID=$!

# Wait for startup
sleep 3

if ! kill -0 $JUPYTER_PID 2>/dev/null; then
    echo ""
    echo "ERROR: JupyterLab failed to start!"
    echo ""
    echo "Log output:"
    cat "$JUPYTER_LOG" | tail -20
    echo ""
    rm -f "$JUPYTER_LOG"
    die "JupyterLab process died unexpectedly"
fi

# Wait for server to respond
MAX_WAIT=15
WAIT_COUNT=0
while ! curl -s "http://localhost:${PORT}/" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo ""
        echo "ERROR: JupyterLab not responding on port $PORT"
        echo ""
        echo "Log output:"
        cat "$JUPYTER_LOG" | tail -20
        echo ""
        kill $JUPYTER_PID 2>/dev/null || true
        rm -f "$JUPYTER_LOG"
        die "JupyterLab failed to respond after ${MAX_WAIT} seconds"
    fi
done

# Cleanup log file on success
rm -f "$JUPYTER_LOG"

info "JupyterLab ready!"

################################################################################
# cleanup - Stop JupyterLab on exit
################################################################################
cleanup() {
    info "Stopping JupyterLab..."
    if [ -n "${JUPYTER_PID:-}" ]; then
        kill $JUPYTER_PID 2>/dev/null || true
        sleep 1
        kill -9 $JUPYTER_PID 2>/dev/null || true
    fi
    exit 0
}

setup_cleanup_trap cleanup

################################################################################
# Open browser
################################################################################
info "Opening browser..."

if command -v chromium-browser >/dev/null 2>&1; then
    run_as_user chromium-browser --password-store=basic "$WELCOME_URL" >/dev/null 2>&1 &
elif command -v firefox >/dev/null 2>&1; then
    run_as_user firefox "$WELCOME_URL" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    run_as_user xdg-open "$WELCOME_URL" >/dev/null 2>&1 &
else
    info "Please open manually: $WELCOME_URL"
fi

################################################################################
# Display info and wait
################################################################################
echo ""
echo "======================================"
echo "  Quantum Paradoxes Demo Running"
echo "======================================"
echo ""
echo "URL: $WELCOME_URL"
echo ""
echo "Available notebooks:"
echo "  - WELCOME.ipynb (Start here)"
echo "  - schrodingers-cat.ipynb"
echo "  - quantum-zeno-effect.ipynb"
echo ""
echo "Press Ctrl+C to stop"
echo ""

wait $JUPYTER_PID 2>/dev/null || true
cleanup
