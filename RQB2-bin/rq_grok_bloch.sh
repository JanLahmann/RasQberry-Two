#!/bin/bash
#
# RasQberry: Launch Grok Bloch Sphere Demo
# Starts local HTTP server and opens the demo in browser
#

# Load environment variables
. $HOME/.local/bin/env-config.sh

DEMO_DIR="$HOME/$REPO/demos/grok-bloch"
PORT=8080

# Check if demo is installed
if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "Error: Grok Bloch demo not found at $DEMO_DIR"
    echo "Please install the demo first through the RasQberry menu."
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