#!/bin/bash
#
# RasQberry: Launch Grok Bloch Sphere Demo
# Starts local HTTP server and opens the demo in browser
#

# Ensure HOME is set (for desktop launchers)
if [ -z "$HOME" ]; then
    HOME="/home/$(whoami)"
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

DEMO_DIR="$HOME/$REPO/demos/grok-bloch"
PORT=8080

# Check if demo is installed
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Error: Grok Bloch demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
    echo "Debug info:"
    echo "  HOME: $HOME"
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
if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser --password-store=basic "http://localhost:$PORT" >/dev/null 2>&1 &
    BROWSER_PID=$!
elif command -v firefox >/dev/null 2>&1; then
    firefox "http://localhost:$PORT" >/dev/null 2>&1 &
    BROWSER_PID=$!
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:$PORT" >/dev/null 2>&1 &
else
    echo "Please open http://localhost:$PORT in your web browser"
fi

echo ""
echo "Grok Bloch Sphere Demo is running!"
echo "The demo will automatically close when you close the browser window."
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
    # No browser PID, just wait for server
    wait $SERVER_PID
fi