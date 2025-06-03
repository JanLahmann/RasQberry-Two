#!/bin/bash
#
# RasQberry: Enhanced Grok Bloch Sphere Demo Launcher with Debug
# Starts local HTTP server and opens the demo in browser
#

# Enable debug mode if requested
if [ "$1" = "--debug" ]; then
    set -x
    DEBUG=true
    echo "DEBUG MODE ENABLED"
fi

debug_echo() {
    [ "$DEBUG" = "true" ] && echo "DEBUG: $*"
}

echo "=== Grok Bloch Demo Launcher ==="

# Load environment variables with error checking
debug_echo "Loading environment from: $HOME/.local/bin/env-config.sh"
if [ ! -f "$HOME/.local/bin/env-config.sh" ]; then
    echo "ERROR: Environment config file not found: $HOME/.local/bin/env-config.sh"
    exit 1
fi

. $HOME/.local/bin/env-config.sh
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to load environment configuration"
    exit 1
fi

debug_echo "Environment loaded successfully"
debug_echo "REPO: $REPO"
debug_echo "HOME: $HOME"
debug_echo "USER: $USER"

# Set demo directory and port
DEMO_DIR="$HOME/$REPO/demos/grok-bloch"
PORT=8080

echo "Demo directory: $DEMO_DIR"
echo "Initial port: $PORT"

# Check if demo is installed
debug_echo "Checking for demo installation..."
if [ ! -d "$DEMO_DIR" ]; then
    echo "ERROR: Demo directory not found: $DEMO_DIR"
    echo "Expected structure: $HOME/$REPO/demos/grok-bloch/"
    echo "Actual demos directory contents:"
    ls -la "$HOME/$REPO/demos/" 2>/dev/null || echo "  (demos directory does not exist)"
    exit 1
fi

if [ ! -f "$DEMO_DIR/index.html" ]; then
    echo "ERROR: Demo index.html not found"
    echo "Demo directory contents:"
    ls -la "$DEMO_DIR"
    echo ""
    echo "This suggests the demo installation was incomplete."
    echo "Try reinstalling through the RasQberry menu."
    exit 1
fi

echo "✓ Demo installation verified"

# Check Python3 availability
debug_echo "Checking Python3 availability..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 command not found"
    echo "Python3 is required to run the HTTP server"
    exit 1
fi
echo "✓ Python3 available: $(python3 --version)"

# Check network tools for port scanning
debug_echo "Checking network tools..."
if command -v netstat >/dev/null 2>&1; then
    NETCHECK="netstat -tuln"
elif command -v ss >/dev/null 2>&1; then
    NETCHECK="ss -tuln"
else
    echo "WARNING: No network checking tools (netstat/ss) available"
    echo "Will attempt to use port $PORT without checking"
    NETCHECK=""
fi

# Find available port
if [ -n "$NETCHECK" ]; then
    debug_echo "Scanning for available port starting from $PORT..."
    while $NETCHECK | grep -q ":$PORT "; do
        PORT=$((PORT + 1))
        debug_echo "Port $((PORT - 1)) in use, trying $PORT"
    done
fi

echo "Using port: $PORT"
echo "URL: http://localhost:$PORT"

# Change to demo directory
debug_echo "Changing to demo directory: $DEMO_DIR"
cd "$DEMO_DIR" || {
    echo "ERROR: Cannot change to demo directory: $DEMO_DIR"
    exit 1
}

# Start HTTP server in background
echo "Starting HTTP server..."
debug_echo "Command: python3 -m http.server $PORT"
python3 -m http.server $PORT &
SERVER_PID=$!

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start HTTP server"
    exit 1
fi

debug_echo "Server PID: $SERVER_PID"

# Wait a moment for server to start
sleep 2

# Test if server is responding
debug_echo "Testing server response..."
if command -v curl >/dev/null 2>&1; then
    if curl -s -I "http://localhost:$PORT" >/dev/null 2>&1; then
        echo "✓ HTTP server is responding"
    else
        echo "WARNING: HTTP server may not be responding"
    fi
elif command -v wget >/dev/null 2>&1; then
    if wget -q --spider "http://localhost:$PORT" 2>/dev/null; then
        echo "✓ HTTP server is responding"
    else
        echo "WARNING: HTTP server may not be responding"
    fi
else
    echo "INFO: No curl/wget available to test server response"
fi

# Check display environment
debug_echo "Display environment: DISPLAY=$DISPLAY"
if [ -z "$DISPLAY" ]; then
    echo "WARNING: No DISPLAY environment variable set"
    echo "This may prevent browser from opening"
    echo "For SSH: use 'ssh -X' for X11 forwarding"
    echo "For VNC: ensure VNC server is running"
fi

# Try to open in browser
echo "Opening in browser..."
BROWSER_OPENED=false

debug_echo "Checking browser availability..."
if command -v chromium-browser >/dev/null 2>&1; then
    echo "Using chromium-browser..."
    chromium-browser "http://localhost:$PORT" &
    BROWSER_OPENED=true
elif command -v firefox >/dev/null 2>&1; then
    echo "Using firefox..."
    firefox "http://localhost:$PORT" &
    BROWSER_OPENED=true
elif command -v xdg-open >/dev/null 2>&1; then
    echo "Using xdg-open..."
    xdg-open "http://localhost:$PORT" &
    BROWSER_OPENED=true
else
    echo "No browser commands found (chromium-browser, firefox, xdg-open)"
fi

if [ "$BROWSER_OPENED" = "false" ]; then
    echo ""
    echo "Please manually open this URL in your web browser:"
    echo "  http://localhost:$PORT"
    echo ""
fi

echo ""
echo "=== Grok Bloch Sphere Demo is running! ==="
echo "Server PID: $SERVER_PID"
echo "Local URL: http://localhost:$PORT"
echo ""
echo "Press Ctrl+C to stop the server and close the demo"
echo ""

# Set up signal handling
cleanup() {
    echo ""
    echo "Stopping server..."
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "Demo stopped."
    exit 0
}

trap cleanup INT TERM

# Keep script running and monitor server
while kill -0 $SERVER_PID 2>/dev/null; do
    sleep 1
done

echo "HTTP server stopped unexpectedly"
exit 1