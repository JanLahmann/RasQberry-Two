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
verify_env_vars USER_HOME REPO MARKER_GROK_BLOCH

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
if [ ! -f "$DEMO_DIR/$MARKER_GROK_BLOCH" ]; then
    echo "Error: Grok Bloch demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    debug "USER_NAME: $(get_user_name)"
    debug "USER_HOME: $USER_HOME"
    debug "REPO: $REPO"
    debug "Expected path: $DEMO_DIR"
    die "Grok Bloch demo not installed"
fi

info "Starting Grok Bloch Sphere Demo..."
debug "Demo directory: $DEMO_DIR"
debug "Local server port: $PORT"

# Find available port.
#
# Note this only sees LISTENING sockets, so a port still held in TIME_WAIT by a
# previous run looks free. The server below sets SO_REUSEADDR so it can bind
# anyway - without it, restarting the demo within ~60s failed to bind every
# time, silently (see the start-up check further down).
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


class ReusableTCPServer(socketserver.TCPServer):
    # TCPServer defaults this to False, so a port left in TIME_WAIT by the
    # previous run refused the bind and the demo died before serving anything.
    allow_reuse_address = True


port = int(sys.argv[1])
with ReusableTCPServer(("", port), QuietHTTPRequestHandler) as httpd:
    httpd.serve_forever()
EOF

# Start HTTP server in background. Keep the log: if the bind fails we want to
# say why, rather than announce a demo that is not there.
python3 /tmp/grok_server.py "$PORT" >/tmp/grok_server.log 2>&1 &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Confirm it actually came up. It previously could not bind and exit silently,
# leaving the script to print "demo is running" over a dead port.
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    warn "Web server failed to start:"
    sed 's/^/    /' /tmp/grok_server.log >&2 2>/dev/null || true
    die "Could not serve the demo on port $PORT"
fi

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

# Try to open in browser.
#
# Fire and forget: the demo's lifetime must NOT be tied to the PID we spawn
# here. Chromium is single-instance and autostarts on this image, so
# `chromium-browser <url>` hands the URL to the running instance and exits at
# once ("Opening in existing browser session."). Waiting on that PID therefore
# killed the server a second after the tab opened, and the tab it had just
# opened showed connection refused - reliably, since Chromium is always already
# up. An exiting launcher tells us nothing about whether the window closed, so
# we serve until the user stops the demo instead.
BROWSER_URL="http://localhost:$PORT"

if command -v chromium-browser >/dev/null 2>&1; then
    run_as_user chromium-browser --password-store=basic "$BROWSER_URL" >/dev/null 2>&1 &
elif command -v firefox >/dev/null 2>&1; then
    run_as_user firefox "$BROWSER_URL" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    run_as_user xdg-open "$BROWSER_URL" >/dev/null 2>&1 &
else
    info "Please open $BROWSER_URL in your web browser"
fi

echo ""
echo "Grok Bloch Sphere Demo is running!"
echo ""
echo "  URL: $BROWSER_URL"
echo ""

# Serve until the user stops us. Closing the browser tab does not stop the
# demo - see the note above on why that cannot be detected.
if [ -t 0 ]; then
    echo "Press Enter (or Ctrl+C) to stop the demo..."
    read -r
    info "Stopping demo..."
else
    echo "Press Ctrl+C or close this window to stop the demo."
    echo ""
    wait $SERVER_PID
fi
