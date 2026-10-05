#!/bin/bash
set -euo pipefail

################################################################################
# rq_ibm_courses.sh - IBM Quantum Courses Launcher
#
# Description:
#   Launches JupyterLab with IBM Quantum courses from Qiskit documentation
#   Auto-opens WELCOME-courses.ipynb in the browser
#
# Content licensed under CC BY-SA 4.0 by IBM/Qiskit
# Source: https://github.com/Qiskit/documentation
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO STD_VENV MARKER_IBM_COURSES IBM_COURSES_JUPYTER_PORT

# Without a screen (SSH) the server starts headless and the address and an
# ssh -L tunnel command are printed instead of opening a browser (Jan, Q19)

DEMO_DIR="$USER_HOME/$REPO/demos/ibm-quantum-learning"
PORT="${IBM_COURSES_JUPYTER_PORT:-8890}"

# Check if demo is installed
if [ ! -f "$DEMO_DIR/$MARKER_IBM_COURSES" ]; then
    echo "Error: IBM Quantum Courses not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    debug "USER_HOME: $USER_HOME"
    debug "REPO: $REPO"
    debug "Expected path: $DEMO_DIR"
    die "IBM Quantum Courses not installed"
fi

# Only the notebooks and what they need, not the repository's own files (#18)
rq_ibm_learning_tidy "$DEMO_DIR"

info "Starting IBM Quantum Courses..."
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
# Its own JupyterLab workspace: Tutorials and Courses share a folder, and
# each opened with the tabs the other one left (#18)
WELCOME_URL="http://localhost:${PORT}/lab/workspaces/ibm-courses/tree/WELCOME-courses.ipynb?token=${JUPYTER_TOKEN}"

# Change to demo directory
cd "$DEMO_DIR" || die "Failed to change to demo directory"

info "Launching JupyterLab..."

# Start JupyterLab in background
jupyter-lab \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --ServerApp.token="$JUPYTER_TOKEN" \
    --ServerApp.password="" \
    >/dev/null 2>&1 &

JUPYTER_PID=$!

# Wait for startup
sleep 3

if ! kill -0 $JUPYTER_PID 2>/dev/null; then
    die "JupyterLab failed to start"
fi

# Wait for server to respond
# JupyterLab needs ~15 s to start on a Pi 4; the loop returns as soon as
# it answers, so a generous limit costs nothing (rig test, #234)
MAX_WAIT=60
WAIT_COUNT=0
while ! curl -s "http://localhost:${PORT}/" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ -n "${JUPYTER_PID:-}" ] && ! kill -0 "$JUPYTER_PID" 2>/dev/null; then
        die "JupyterLab exited during startup - see the output above"
    fi
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        kill $JUPYTER_PID 2>/dev/null || true
        die "JupyterLab failed to respond after ${MAX_WAIT} seconds"
    fi
done

info "JupyterLab ready!"

################################################################################
# cleanup - Stop JupyterLab on exit
################################################################################
cleanup() {
    set +e   # a closed window cannot show messages: still stop the server
    trap '' HUP INT TERM
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
rq_show_url "$WELCOME_URL" "$PORT"

################################################################################
# Display info and wait
################################################################################
echo ""
echo "======================================"
echo "  IBM Quantum Courses Running"
echo "======================================"
echo ""
echo "URL: $WELCOME_URL"
echo ""
echo "Content licensed under CC BY-SA 4.0 by IBM/Qiskit"
echo "Source: https://github.com/Qiskit/documentation"
echo ""
rq_wait_for_stop "IBM Quantum Courses" "$JUPYTER_PID"
cleanup
