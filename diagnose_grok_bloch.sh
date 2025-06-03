#!/bin/bash
#
# Grok Bloch Demo Diagnostic Script
# Run this script to diagnose why the Grok Bloch demo might be failing
#

echo "=== RasQberry Grok Bloch Demo Diagnostics ==="
echo ""

# Check environment setup
echo "1. Environment Configuration:"
echo "   HOME: $HOME"
echo "   USER: $USER"
echo "   SUDO_USER: ${SUDO_USER:-<not set>}"

ENV_CONFIG="$HOME/.local/bin/env-config.sh"
echo "   Environment config: $ENV_CONFIG"
if [ -f "$ENV_CONFIG" ]; then
    echo "   ✓ Environment config exists"
    # Try to load it
    if . "$ENV_CONFIG" 2>/dev/null; then
        echo "   ✓ Environment config loads successfully"
        echo "   REPO: ${REPO:-<not set>}"
        echo "   GROK_BLOCH_INSTALLED: ${GROK_BLOCH_INSTALLED:-<not set>}"
    else
        echo "   ✗ Environment config failed to load"
    fi
else
    echo "   ✗ Environment config file missing"
fi
echo ""

# Check demo installation
echo "2. Demo Installation:"
if [ -n "$REPO" ]; then
    DEMO_DIR="$HOME/$REPO/demos/grok-bloch"
    echo "   Demo directory: $DEMO_DIR"
    
    if [ -d "$DEMO_DIR" ]; then
        echo "   ✓ Demo directory exists"
        echo "   Contents:"
        ls -la "$DEMO_DIR" | sed 's/^/     /'
        
        if [ -f "$DEMO_DIR/index.html" ]; then
            echo "   ✓ index.html found"
            echo "   File size: $(stat -f%z "$DEMO_DIR/index.html" 2>/dev/null || stat -c%s "$DEMO_DIR/index.html" 2>/dev/null || echo "unknown") bytes"
        else
            echo "   ✗ index.html missing"
        fi
    else
        echo "   ✗ Demo directory missing"
        echo "   Parent directory contents:"
        ls -la "$HOME/$REPO/demos/" 2>/dev/null | sed 's/^/     /' || echo "     (parent directory does not exist)"
    fi
else
    echo "   ✗ REPO variable not set - cannot check demo installation"
fi
echo ""

# Check system dependencies
echo "3. System Dependencies:"
echo "   Python3: $(command -v python3 || echo "NOT FOUND")"
if command -v python3 >/dev/null 2>&1; then
    echo "   Python version: $(python3 --version)"
    # Test HTTP server module
    if python3 -c "import http.server" 2>/dev/null; then
        echo "   ✓ HTTP server module available"
    else
        echo "   ✗ HTTP server module not available"
    fi
fi

echo "   Browsers:"
echo "     chromium-browser: $(command -v chromium-browser || echo "NOT FOUND")"
echo "     firefox: $(command -v firefox || echo "NOT FOUND")"
echo "     xdg-open: $(command -v xdg-open || echo "NOT FOUND")"

echo "   Network tools:"
echo "     netstat: $(command -v netstat || echo "NOT FOUND")"
echo "     ss: $(command -v ss || echo "NOT FOUND")"
echo "     curl: $(command -v curl || echo "NOT FOUND")"
echo "     wget: $(command -v wget || echo "NOT FOUND")"
echo ""

# Check display environment
echo "4. Display Environment:"
echo "   DISPLAY: ${DISPLAY:-<not set>}"
echo "   XDG_SESSION_TYPE: ${XDG_SESSION_TYPE:-<not set>}"
echo "   WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-<not set>}"

if [ -n "$DISPLAY" ]; then
    if command -v xdpyinfo >/dev/null 2>&1; then
        if xdpyinfo >/dev/null 2>&1; then
            echo "   ✓ X11 display accessible"
        else
            echo "   ✗ X11 display not accessible"
        fi
    else
        echo "   ? Cannot test X11 (xdpyinfo not available)"
    fi
else
    echo "   ⚠ No DISPLAY set - GUI applications may not work"
fi
echo ""

# Check network ports
echo "5. Network Port Availability:"
TEST_PORT=8080
if command -v netstat >/dev/null 2>&1; then
    if netstat -tuln | grep -q ":$TEST_PORT "; then
        echo "   ⚠ Port $TEST_PORT is already in use"
        echo "   Processes using port $TEST_PORT:"
        netstat -tulnp 2>/dev/null | grep ":$TEST_PORT " | sed 's/^/     /'
    else
        echo "   ✓ Port $TEST_PORT appears available"
    fi
elif command -v ss >/dev/null 2>&1; then
    if ss -tuln | grep -q ":$TEST_PORT "; then
        echo "   ⚠ Port $TEST_PORT is already in use"
        echo "   Processes using port $TEST_PORT:"
        ss -tulnp 2>/dev/null | grep ":$TEST_PORT " | sed 's/^/     /'
    else
        echo "   ✓ Port $TEST_PORT appears available"
    fi
else
    echo "   ? Cannot check port availability (no netstat/ss)"
fi
echo ""

# Check launcher script
echo "6. Launcher Script:"
LAUNCHER="$HOME/.local/bin/rq_grok_bloch.sh"
echo "   Launcher: $LAUNCHER"
if [ -f "$LAUNCHER" ]; then
    echo "   ✓ Launcher script exists"
    echo "   Permissions: $(ls -l "$LAUNCHER" | cut -d' ' -f1)"
    if [ -x "$LAUNCHER" ]; then
        echo "   ✓ Launcher script is executable"
    else
        echo "   ✗ Launcher script is not executable"
    fi
else
    echo "   ✗ Launcher script missing"
fi
echo ""

echo "=== Diagnostic Summary ==="
echo ""
echo "To test the Grok Bloch demo manually:"
echo "1. Load environment: . $HOME/.local/bin/env-config.sh"
echo "2. Check installation: ls -la \$HOME/\$REPO/demos/grok-bloch/"
echo "3. Test HTTP server: cd \$HOME/\$REPO/demos/grok-bloch && python3 -m http.server 8080"
echo "4. Open browser: http://localhost:8080"
echo ""
echo "For enhanced debugging, use the debug launcher:"
echo "   ./rq_grok_bloch_debug.sh --debug"