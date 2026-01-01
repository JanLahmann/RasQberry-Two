#!/bin/bash
#
# rq_demo_run_test.sh - Test script for universal demo launcher
#
# Usage: rq_demo_run_test.sh [--interactive]
#
# Tests rq_demo_run.sh with various demo types.
# Use --interactive to actually launch demos (otherwise dry-run checks only).
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERACTIVE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; }
info() { echo -e "       $1"; }

# Parse args
[ "${1:-}" = "--interactive" ] && INTERACTIVE=true

echo "========================================"
echo "RasQberry Universal Launcher Test"
echo "========================================"
echo

# Test 1: Script exists and is executable
echo "1. Basic checks"
echo "----------------------------------------"
if [ -x "$SCRIPT_DIR/rq_demo_run.sh" ]; then
    pass "rq_demo_run.sh exists and is executable"
else
    fail "rq_demo_run.sh not found or not executable"
    exit 1
fi

# Test 2: Help works
if "$SCRIPT_DIR/rq_demo_run.sh" --help 2>&1 | grep -q "Usage:"; then
    pass "--help shows usage"
else
    fail "--help doesn't work"
fi

# Test 3: jq available
if command -v jq &>/dev/null; then
    pass "jq is installed"
else
    fail "jq not installed"
    exit 1
fi

echo

# Test 4: Manifest loading
echo "2. Manifest loading"
echo "----------------------------------------"
for demo in grok-bloch-web composer fun-with-quantum quantum-mixer led-demos; do
    output=$("$SCRIPT_DIR/rq_demo_run.sh" "$demo" 2>&1 || true)
    if echo "$output" | grep -q "^=== "; then
        pass "Loads manifest: $demo"
    elif echo "$output" | grep -q "not installed\|not found"; then
        # Demo not installed but manifest was parsed
        pass "Loads manifest: $demo (demo not installed)"
    elif echo "$output" | grep -q "No entrypoint"; then
        # Manifest loaded but no default entrypoint (e.g., led-demos needs variant)
        pass "Loads manifest: $demo (needs variant)"
    else
        fail "Can't load manifest: $demo"
        info "$output"
    fi
done

echo

# Test 5: Unknown demo
echo "3. Error handling"
echo "----------------------------------------"
output=$("$SCRIPT_DIR/rq_demo_run.sh" nonexistent-demo 2>&1 || true)
if echo "$output" | grep -q "Manifest not found"; then
    pass "Reports missing manifest"
else
    fail "Doesn't report missing manifest"
    info "$output"
fi

# Test 6: Unknown variant
output=$("$SCRIPT_DIR/rq_demo_run.sh" led-demos nonexistent-variant 2>&1 || true)
if echo "$output" | grep -q "Unknown variant"; then
    pass "Reports unknown variant"
else
    fail "Doesn't report unknown variant"
    info "$output"
fi

echo

# Test 7: Browser type (dry run - just check it tries to launch)
echo "4. Type handlers (dry run)"
echo "----------------------------------------"

# Check browser type parses correctly
output=$("$SCRIPT_DIR/rq_demo_run.sh" grok-bloch-web 2>&1 || true)
if echo "$output" | grep -q "Opening:\|requires a display\|browser\|Display"; then
    pass "Browser type: parses correctly"
else
    fail "Browser type: doesn't parse"
    info "$output"
fi

# Check variant delegation
output=$("$SCRIPT_DIR/rq_demo_run.sh" led-demos ibm-logo 2>&1 || true)
if echo "$output" | grep -q "Delegating to:\|Running variant"; then
    pass "Variant: delegates to launcher"
else
    # May fail if launcher not found, but should try
    if echo "$output" | grep -q "Launcher script not found"; then
        pass "Variant: tries to delegate (launcher not in dev path)"
    else
        fail "Variant: doesn't delegate"
        info "$output"
    fi
fi

echo

# Interactive tests
if $INTERACTIVE; then
    echo "5. Interactive tests"
    echo "----------------------------------------"
    echo "These will actually launch demos. Press Ctrl+C to skip any test."
    echo

    read -rp "Test browser type (grok-bloch-web)? [y/N] " -n 1
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Launching grok-bloch-web..."
        "$SCRIPT_DIR/rq_demo_run.sh" grok-bloch-web || fail "grok-bloch-web failed"
    fi

    read -rp "Test jupyter type (fun-with-quantum)? [y/N] " -n 1
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Launching fun-with-quantum..."
        "$SCRIPT_DIR/rq_demo_run.sh" fun-with-quantum || fail "fun-with-quantum failed"
    fi

    read -rp "Test LED variant (led-demos ibm-logo)? [y/N] " -n 1
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Launching led-demos ibm-logo..."
        "$SCRIPT_DIR/rq_demo_run.sh" led-demos ibm-logo || fail "led-demos ibm-logo failed"
    fi
else
    echo "5. Interactive tests"
    echo "----------------------------------------"
    skip "Run with --interactive to test actual demo launches"
fi

echo
echo "========================================"
echo "Test complete"
echo "========================================"
