#!/bin/bash
set -euo pipefail

################################################################################
# rq_grok_bloch.sh - RasQberry Grok Bloch Sphere Demo Launcher
#
# Description:
#   Starts local HTTP server and opens the Bloch sphere demo in browser
#   Interactive visualization of quantum states
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO

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

DEMO_DIR="$USER_HOME/$REPO/demos/grok-bloch"
PORT=8080

# Check if demo is installed
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Error: Grok Bloch demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    debug "USER_NAME: $SUDO_USER_NAME"
    debug "USER_HOME: $USER_HOME"
    debug "REPO: $REPO"
    debug "Expected path: $DEMO_DIR"
    die "Grok Bloch demo not installed"
fi

info "Starting Grok Bloch Sphere Demo..."
debug "Demo directory: $DEMO_DIR"
debug "Local server port: $PORT"

# Find available port
while netstat -tuln | grep -q ":$PORT "; do
    PORT=$((PORT + 1))
done

info "Using port: $PORT"
info "URL: http://localhost:$PORT"

# Change to demo directory
cd "$DEMO_DIR" || die "Failed to change to demo directory"

# Create a custom HTTP server handler to suppress favicon errors
cat > /tmp/grok_server.py << 'EOF'
import http.server
import socketserver
import sys
import os

class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress favicon.ico 404 errors
        if 'favicon.ico' in str(args):
            return
        # Suppress other 404 errors
        if '404' in str(args):
            return
        super().log_message(format, *args)

port = int(sys.argv[1])
with socketserver.TCPServer(("", port), QuietHTTPRequestHandler) as httpd:
    httpd.serve_forever()
EOF

# Start HTTP server in background with error suppression
python3 /tmp/grok_server.py $PORT >/dev/null 2>&1 &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

info "Opening in browser..."

################################################################################
# cleanup - Stop server and remove temp files
################################################################################
cleanup() {
    info "Cleaning up..."
    kill $SERVER_PID 2>/dev/null || true
    rm -f /tmp/grok_server.py
    exit 0
}

# Set up cleanup trap
setup_cleanup_trap cleanup

# Try to open in browser
BROWSER_PID=""
BROWSER_URL="http://localhost:$PORT"

# Launch browser as user
if command -v chromium-browser >/dev/null 2>&1; then
    run_as_user chromium-browser --password-store=basic "$BROWSER_URL" >/dev/null 2>&1 &
    BROWSER_PID=$! 2>/dev/null || true
elif command -v firefox >/dev/null 2>&1; then
    run_as_user firefox "$BROWSER_URL" >/dev/null 2>&1 &
    BROWSER_PID=$! 2>/dev/null || true
elif command -v xdg-open >/dev/null 2>&1; then
    run_as_user xdg-open "$BROWSER_URL" >/dev/null 2>&1 &
else
    info "Please open $BROWSER_URL in your web browser"
fi

echo ""
echo "Grok Bloch Sphere Demo is running!"
if [ -n "${BROWSER_PID:-}" ]; then
    echo "The demo will automatically close when you close the browser window."
else
    echo "Press Ctrl+C or close this window to stop the demo."
fi
echo "Or press Ctrl+C to stop manually."
echo ""

# Monitor browser process if we have a PID
if [ -n "${BROWSER_PID:-}" ] && kill -0 $BROWSER_PID 2>/dev/null; then
    # Wait for either server or browser to exit
    while kill -0 $SERVER_PID 2>/dev/null && kill -0 $BROWSER_PID 2>/dev/null; do
        sleep 1
    done

    # If browser closed, clean up
    if ! kill -0 $BROWSER_PID 2>/dev/null; then
        info "Browser closed. Stopping demo..."
        cleanup
    fi
else
    # No browser PID tracking, just wait for server or Ctrl+C
    wait $SERVER_PID
fi
