#!/bin/bash
set -euo pipefail

################################################################################
# rq_grok_bloch.sh - RasQberry Grok Bloch Sphere Demo Launcher
#
# Description:
#   Starts local HTTP server and opens the Bloch sphere demo in browser
#   Interactive visualization of quantum states. Over SSH it prints the
#   address and an ssh -L tunnel command instead.
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars USER_HOME REPO MARKER_GROK_BLOCH

# Without a screen (SSH) the server starts all the same and the address and
# an ssh -L tunnel command are printed, as for the notebook demos (#17)

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


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    # TCPServer defaults this to False, so a port left in TIME_WAIT by the
    # previous run refused the bind and the demo died before serving anything.
    allow_reuse_address = True
    # One thread per connection: a single-threaded server waits for the
    # request on the connection it accepted first, and a browser's idle
    # connection (Chromium opens spare ones) held up every other request
    # (seen by the rig test, 1 run in 3). Daemon threads: such a connection
    # does not keep the server from stopping. (Not ThreadingHTTPServer: its
    # bind resolves the host name, which can be slow offline.)
    daemon_threads = True


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

################################################################################
# cleanup - Stop server and remove temp files
################################################################################
cleanup() {
    set +e   # a closed window cannot show messages: still stop the server
    trap '' HUP INT TERM
    info "Cleaning up..."
    rq_close_demo_tabs   # its tab goes with it (#9)
    kill $SERVER_PID 2>/dev/null || true
    rm -f /tmp/grok_server.py
    exit 0
}

# Set up cleanup trap
setup_cleanup_trap cleanup

# Try to open in browser.
#
# The demo's lifetime must NOT be tied to the browser command. Chromium is
# single-instance and autostarts on this image, so `chromium-browser <url>`
# hands the URL to the running instance and exits at once ("Opening in
# existing browser session."). Tying the demo to that command therefore
# killed the server a second after the tab opened, and the tab it had just
# opened showed connection refused - reliably, since Chromium is always already
# up. An exiting launcher tells us nothing about whether the window closed, so
# we serve until the user stops the demo instead. rq_open_browser waits only
# for that hand-off; the demo's window of the browser closes when the demo
# stops (#9).
BROWSER_URL="http://localhost:$PORT"

rq_show_url "$BROWSER_URL" "$PORT"

echo ""
echo "Grok Bloch Sphere Demo is running!"
echo ""
echo "  URL: $BROWSER_URL"
echo ""

# Serve until the user stops us. Closing the browser tab does not stop the
# demo - see the note above on why that cannot be detected.
rq_wait_for_stop "Grok Bloch Sphere" "$SERVER_PID"
