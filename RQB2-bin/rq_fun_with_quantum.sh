#!/bin/bash
set -euo pipefail

################################################################################
# rq_fun_with_quantum.sh - RasQberry Fun-with-Quantum Demo Launcher
#
# Description:
#   Launches the Fun-with-Quantum Jupyter notebooks for learning quantum
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
    info "Cleaning up..."
    if [ -n "$JUPYTER_PID" ] && kill -0 "$JUPYTER_PID" 2>/dev/null; then
        info "Stopping Jupyter server..."
        kill "$JUPYTER_PID" 2>/dev/null || true
        wait "$JUPYTER_PID" 2>/dev/null || true
    fi
}

################################################################################
# Main
################################################################################

# Setup cleanup trap
trap cleanup EXIT INT TERM

# Check display
check_display || warn "No display detected. Browser may not open automatically."

# Verify demo is installed
if [ ! -f "$DEMO_DIR/$MARKER_FWQ" ]; then
    die "Fun-with-Quantum not installed. Use rq_fun_with_quantum_auto.sh or install via raspi-config."
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

# Launch Jupyter in background
jupyter notebook \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --NotebookApp.token='' \
    --NotebookApp.password='' \
    --NotebookApp.open_browser=False \
    2>&1 &
JUPYTER_PID=$!

# Wait for Jupyter to start
info "Waiting for Jupyter to start..."
sleep 3

# Verify Jupyter is running
if ! kill -0 "$JUPYTER_PID" 2>/dev/null; then
    die "Jupyter failed to start"
fi

echo
echo "✓ Fun-with-Quantum is running!"
echo
echo "  Jupyter URL: $JUPYTER_URL"
echo
echo "  Available notebooks:"
echo "    - Quantum-Coin-Game.ipynb    (superposition & interference)"
echo "    - GHZ-Game.ipynb             (entanglement)"
echo "    - Hardys-Paradox.ipynb       (quantum logic)"
echo "    - 3sat.ipynb                 (Grover's algorithm)"
echo
echo "  RISE Slideshow: Press Alt+R in any notebook"
echo

# Try to open browser
if command -v chromium-browser &>/dev/null; then
    info "Opening browser..."
    run_as_user chromium-browser --password-store=basic "$JUPYTER_URL" &
elif command -v firefox &>/dev/null; then
    info "Opening browser..."
    run_as_user firefox "$JUPYTER_URL" &
else
    info "No browser found. Please open the URL manually."
fi

echo
echo "============================================"
echo "  Fun-with-Quantum is running"
echo "============================================"
echo

# Only wait for input if we have a TTY (interactive session)
if [ -t 0 ]; then
    echo "Press Enter to stop the Jupyter server..."
    read -r
    info "Stopping Jupyter server..."
else
    # No TTY - keep running
    info "Jupyter server running in background (PID: $JUPYTER_PID)"
    info "Stop with: kill $JUPYTER_PID"
    echo
    # Wait for Jupyter process
    wait "$JUPYTER_PID" 2>/dev/null || true
fi
