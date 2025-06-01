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
if [ -f "$HOME/.local/bin/env-config.sh" ]; then
    . "$HOME/.local/bin/env-config.sh"
else
    echo "Error: Environment config not found at $HOME/.local/bin/env-config.sh"
    exit 1
fi

# Verify REPO variable is set
if [ -z "$REPO" ]; then
    echo "Error: REPO variable not set after loading environment"
    echo "Environment loading may have failed"
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

# Start HTTP server in background
python3 -m http.server $PORT &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

echo "Opening in browser..."
# Try to open in browser
if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser "http://localhost:$PORT" &
elif command -v firefox >/dev/null 2>&1; then
    firefox "http://localhost:$PORT" &
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:$PORT" &
else
    echo "Please open http://localhost:$PORT in your web browser"
fi

echo ""
echo "Grok Bloch Sphere Demo is running!"
echo "Press Ctrl+C to stop the server and close the demo"
echo ""

# Wait for user to stop
trap "echo 'Stopping server...'; kill $SERVER_PID 2>/dev/null; exit 0" INT

# Keep script running
wait $SERVER_PID