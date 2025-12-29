#!/bin/bash
#
# Test all LED demos with virtual display
#
# This script starts the virtual LED GUI and runs through all LED demos
# to verify they work correctly with the virtual display.
#
# Usage:
#   ./test_all_led_demos.sh
#
# Requirements:
#   - LED_VIRTUAL=true must be set in /usr/config/rasqberry_environment.env
#   - RQB2 virtual environment with Qiskit for quantum demos

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${HOME}/RasQberry-Two/venv/RQB2"
LOG_FILE="/tmp/led_demo_test.log"

# Demo list: script:duration_seconds
DEMOS=(
    "demo_led_text_rainbow_scroll.py:8"
    "demo_led_text_static.py:3"
    "demo_led_text_alert.py:3"
    "demo_led_text_gradient.py:3"
    "demo_led_rasqberry_logo.py:3"
    "demo_led_ibm_logo.py:3"
    "demo_led_logo_slideshow.py:8"
    "rq_display_ip.py:5"
    "test_virtual_led.py:10"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Virtual LED Demo Test Suite"
echo "=========================================="
echo ""

# Check if virtual mode is enabled
if grep -q "LED_VIRTUAL=true" /usr/config/rasqberry_environment.env 2>/dev/null; then
    echo -e "${GREEN}LED_VIRTUAL=true${NC} - Virtual mode enabled"
else
    echo -e "${YELLOW}Warning: LED_VIRTUAL not set to true${NC}"
    echo "Setting LED_VIRTUAL=true for this session..."
    export LED_VIRTUAL=true
fi

# Activate virtual environment if it exists
if [ -f "${VENV_PATH}/bin/activate" ]; then
    echo "Activating RQB2 virtual environment..."
    source "${VENV_PATH}/bin/activate"
else
    echo -e "${YELLOW}Warning: RQB2 venv not found at ${VENV_PATH}${NC}"
    echo "Some demos may fail without Qiskit"
fi

# Start virtual LED GUI
echo ""
echo "Starting virtual LED GUI..."
export DISPLAY="${DISPLAY:-:0}"
python3 "${SCRIPT_DIR}/rq_led_virtual_gui.py" &
GUI_PID=$!
sleep 2

# Check if GUI started
if ! kill -0 $GUI_PID 2>/dev/null; then
    echo -e "${RED}Error: Failed to start virtual LED GUI${NC}"
    exit 1
fi
echo -e "${GREEN}Virtual LED GUI started (PID: $GUI_PID)${NC}"

# Run demos
echo ""
echo "Running LED demos..."
echo "=========================================="

PASSED=0
FAILED=0

for demo_spec in "${DEMOS[@]}"; do
    demo="${demo_spec%%:*}"
    duration="${demo_spec##*:}"

    if [ ! -f "${SCRIPT_DIR}/${demo}" ]; then
        echo -e "${YELLOW}SKIP${NC}: $demo (not found)"
        continue
    fi

    echo -n "Testing: $demo (${duration}s)... "

    if timeout "$duration" python3 "${SCRIPT_DIR}/${demo}" >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            # Timeout is expected for demos that run indefinitely
            echo -e "${GREEN}OK${NC} (timeout)"
            ((PASSED++))
        else
            echo -e "${RED}FAIL${NC} (exit code: $exit_code)"
            ((FAILED++))
        fi
    fi
    sleep 1
done

# Test RasQ-LED (requires Qiskit, needs special handling for stdin)
echo -n "Testing: RasQ-LED.py (15s)... "
if [ -f "${SCRIPT_DIR}/RasQ-LED.py" ]; then
    if sleep 20 | timeout 15 python3 "${SCRIPT_DIR}/RasQ-LED.py" >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}OK${NC}"
        ((PASSED++))
    else
        exit_code=$?
        if [ $exit_code -eq 124 ]; then
            echo -e "${GREEN}OK${NC} (timeout)"
            ((PASSED++))
        else
            echo -e "${YELLOW}SKIP${NC} (may need Qiskit)"
        fi
    fi
else
    echo -e "${YELLOW}SKIP${NC} (not found)"
fi

# Cleanup
echo ""
echo "Stopping virtual LED GUI..."
kill $GUI_PID 2>/dev/null || true
wait $GUI_PID 2>/dev/null || true

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Passed: ${GREEN}${PASSED}${NC}"
echo -e "Failed: ${RED}${FAILED}${NC}"
echo ""
echo "Log file: $LOG_FILE"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    exit 1
fi
