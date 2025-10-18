#!/bin/bash
#
# RasQberry-Two: Continuous Demo Loop
# Runs multiple demos in sequence for conference showcases
#

# Load environment variables for configurable timings
. "$HOME/.local/config/env-config.sh" 2>/dev/null || true

# Default timings (in seconds) - can be overridden via environment variables
IBM_LOGO_TIME="${DEMO_LOOP_IBM_LOGO_TIME:-15}"
LIGHTS_OUT_TIME="${DEMO_LOOP_LIGHTS_OUT_TIME:-60}"
RASQBERRY_TIE_TIME="${DEMO_LOOP_RASQBERRY_TIE_TIME:-60}"
RASQ_LED_TIME="${DEMO_LOOP_RASQ_LED_TIME:-60}"
PAUSE_BETWEEN_DEMOS="${DEMO_LOOP_PAUSE:-2}"

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping demo loop..."
    # Kill any running demo processes
    pkill -f "QuantumLightsOut" 2>/dev/null || true
    pkill -f "QuantumRaspberryTie" 2>/dev/null || true
    pkill -f "RasQ-LED" 2>/dev/null || true
    # Turn off all LEDs
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    echo "Demo loop stopped."
    exit 0
}

# Set up trap to handle Ctrl+C
trap cleanup SIGINT SIGTERM

echo "=== RasQberry Continuous Demo Loop ==="
echo ""
echo "Demo timings:"
echo "  - IBM Logo: ${IBM_LOGO_TIME}s"
echo "  - Quantum Lights Out: ${LIGHTS_OUT_TIME}s"
echo "  - RasQberry Tie: ${RASQBERRY_TIE_TIME}s"
echo "  - RasQ-LED: ${RASQ_LED_TIME}s"
echo ""
echo "Press Ctrl+C to stop"
echo ""

LOOP_COUNT=0

while true; do
    LOOP_COUNT=$((LOOP_COUNT + 1))
    echo "========================================="
    echo "Loop #${LOOP_COUNT} - $(date '+%H:%M:%S')"
    echo "========================================="

    # Demo 1: IBM Logo
    echo "[1/4] IBM Logo animation (${IBM_LOGO_TIME}s)..."
    timeout ${IBM_LOGO_TIME} "$BIN_DIR/rq_led_ibm_demo.sh" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 2: Quantum Lights Out
    echo "[2/4] Quantum Lights Out demo (${LIGHTS_OUT_TIME}s)..."
    timeout ${LIGHTS_OUT_TIME} "$BIN_DIR/rq_quantum_lights_out_auto.sh" 2>/dev/null || true
    pkill -f "QuantumLightsOut" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 3: RasQberry Tie
    echo "[3/4] RasQberry Tie demo (${RASQBERRY_TIE_TIME}s)..."
    timeout ${RASQBERRY_TIE_TIME} "$BIN_DIR/rq_quantum_raspberry_tie_auto.sh" 2>/dev/null || true
    pkill -f "QuantumRaspberryTie" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 4: RasQ-LED
    echo "[4/4] RasQ-LED quantum circuit demo (${RASQ_LED_TIME}s)..."
    timeout ${RASQ_LED_TIME} "$BIN_DIR/rq_rasq_led.sh" 2>/dev/null || true
    pkill -f "RasQ-LED" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    echo "Loop #${LOOP_COUNT} complete. Starting next loop..."
    echo ""
done
