#!/bin/bash
#
# RasQberry: Launch Grok Bloch Sphere Demo
# Starts local HTTP server and opens the demo in browser
#

# Determine user and paths (handle sudo/root context)
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_NAME="${SUDO_USER}"
    USER_HOME="/home/${SUDO_USER}"
else
    USER_NAME="$(whoami)"
    USER_HOME="${HOME}"
fi

# Load environment variables
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
else
    echo "Error: Environment config not found at /usr/config/rasqberry_env-config.sh"
    exit 1
fi

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    echo "Environment loading may have failed"
    exit 1
fi

# Check for GUI/Desktop environment
if [ -z "$DISPLAY" ]; then
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
    exit 1
fi

DEMO_DIR="$USER_HOME/$REPO/demos/grok-bloch"
PORT=8080

# Check if demo is installed
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Error: Grok Bloch demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    echo "Debug info:"
    echo "  USER_NAME: $USER_NAME"
    echo "  USER_HOME: $USER_HOME"
    echo "  REPO: $REPO"
    echo "  Expected path: $DEMO_DIR"
    exit 1
fi

echo "Starting Grok Bloch Sphere Demo..."
echo "Demo directory: $DEMO_DIR"
echo "Local server port: $PORT"

# Find available port
while netstat -tuln | grep -q ":$PORT "; do
    PORT=$((PORT + 1))
done

echo "Using port: $PORT"
echo "URL: http://localhost:$PORT"

# Change to demo directory
cd "$DEMO_DIR"

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

echo "Opening in browser..."

# Function to cleanup server and temp files
cleanup() {
    echo "Cleaning up..."
    kill $SERVER_PID 2>/dev/null
    rm -f /tmp/grok_server.py
    exit 0
}

# Set up cleanup trap
trap cleanup INT TERM EXIT

# Try to open in browser and get browser PID
BROWSER_PID=""
BROWSER_URL="http://localhost:$PORT"

# Determine how to launch browser (as user if running as root)
if [ "$(whoami)" = "root" ] && [ -n "$USER_NAME" ] && [ "$USER_NAME" != "root" ]; then
    # Running as root, launch browser as user
    if command -v chromium-browser >/dev/null 2>&1; then
        su - "$USER_NAME" -c "DISPLAY=${DISPLAY:-:0} chromium-browser --password-store=basic '$BROWSER_URL' >/dev/null 2>&1 &"
    elif command -v firefox >/dev/null 2>&1; then
        su - "$USER_NAME" -c "DISPLAY=${DISPLAY:-:0} firefox '$BROWSER_URL' >/dev/null 2>&1 &"
    elif command -v xdg-open >/dev/null 2>&1; then
        su - "$USER_NAME" -c "DISPLAY=${DISPLAY:-:0} xdg-open '$BROWSER_URL' >/dev/null 2>&1 &"
    else
        echo "Please open $BROWSER_URL in your web browser"
    fi
    # When using su, we can't track browser PID reliably, so don't auto-close
    BROWSER_PID=""
else
    # Running as regular user, launch normally
    if command -v chromium-browser >/dev/null 2>&1; then
        chromium-browser --password-store=basic "$BROWSER_URL" >/dev/null 2>&1 &
        BROWSER_PID=$!
    elif command -v firefox >/dev/null 2>&1; then
        firefox "$BROWSER_URL" >/dev/null 2>&1 &
        BROWSER_PID=$!
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$BROWSER_URL" >/dev/null 2>&1 &
    else
        echo "Please open $BROWSER_URL in your web browser"
    fi
fi

echo ""
echo "Grok Bloch Sphere Demo is running!"
if [ -n "$BROWSER_PID" ]; then
    echo "The demo will automatically close when you close the browser window."
else
    echo "Press Ctrl+C or close this window to stop the demo."
fi
echo "Or press Ctrl+C to stop manually."
echo ""

# Monitor browser process if we have a PID
if [ -n "$BROWSER_PID" ]; then
    # Wait for either server or browser to exit
    while kill -0 $SERVER_PID 2>/dev/null && kill -0 $BROWSER_PID 2>/dev/null; do
        sleep 1
    done

    # If browser closed, clean up
    if ! kill -0 $BROWSER_PID 2>/dev/null; then
        echo "Browser closed. Stopping demo..."
        cleanup
    fi
else
    # No browser PID tracking, just wait for server or Ctrl+C
    wait $SERVER_PID
fi