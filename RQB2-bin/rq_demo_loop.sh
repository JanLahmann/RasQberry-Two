#!/bin/bash
#
# RasQberry-Two: Continuous Demo Loop
# Runs multiple demos in sequence for conference showcases
#

# Determine user home directory (handle sudo case)
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    USER_HOME="/home/${SUDO_USER}"
else
    USER_HOME="${HOME}"
fi

# Load environment variables for configurable timings
. /usr/config/rasqberry_env-config.sh 2>/dev/null || true

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

echo "=============================================="
echo "  RasQberry Continuous Demo Loop"
echo "=============================================="
echo ""
echo "Demo timings:"
echo "  - IBM Logo: ${IBM_LOGO_TIME}s"
echo "  - Quantum Lights Out: ${LIGHTS_OUT_TIME}s"
echo "  - RasQberry Tie: ${RASQBERRY_TIE_TIME}s"
echo "  - RasQ-LED: ${RASQ_LED_TIME}s"
echo ""
echo "=============================================="
echo "  Controls:"
echo "    Press ENTER or 'q' - Skip to next demo"
echo "    Press 'x' or 'X'   - Exit demo loop"
echo "    Press Ctrl+C       - Emergency stop"
echo "=============================================="
echo ""

# Function to run a demo with interactive skip/exit option
run_demo_with_controls() {
    local demo_name="$1"
    local demo_cmd="$2"
    local demo_time="$3"

    echo "$demo_name..."

    # Run demo in background with timeout
    timeout "$demo_time" bash -c "$demo_cmd" &
    DEMO_PID=$!

    # Monitor for user input while demo runs
    local elapsed=0
    while kill -0 $DEMO_PID 2>/dev/null; do
        # Check for keypress (non-blocking, 1 second timeout)
        if read -t 1 -n 1 key 2>/dev/null; then
            case "$key" in
                q|"")  # q or Enter
                    echo ""
                    echo "[Skipping to next demo...]"
                    kill $DEMO_PID 2>/dev/null || true
                    wait $DEMO_PID 2>/dev/null || true
                    return 0
                    ;;
                x|X)  # Exit loop
                    echo ""
                    echo "[Exiting demo loop...]"
                    kill $DEMO_PID 2>/dev/null || true
                    wait $DEMO_PID 2>/dev/null || true
                    cleanup
                    ;;
            esac
        fi
        elapsed=$((elapsed + 1))
    done

    # Wait for demo to finish
    wait $DEMO_PID 2>/dev/null || true
    return 0
}

LOOP_COUNT=0

while true; do
    LOOP_COUNT=$((LOOP_COUNT + 1))
    echo "========================================="
    echo "Loop #${LOOP_COUNT} - $(date '+%H:%M:%S')"
    echo "========================================="

    # Demo 1: IBM Logo
    run_demo_with_controls \
        "[1/4] IBM Logo animation (${IBM_LOGO_TIME}s)" \
        "$BIN_DIR/rq_led_ibm_demo.sh" \
        "${IBM_LOGO_TIME}"
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 2: Quantum Lights Out
    run_demo_with_controls \
        "[2/4] Quantum Lights Out demo (${LIGHTS_OUT_TIME}s)" \
        "$BIN_DIR/rq_quantum_lights_out_auto.sh" \
        "${LIGHTS_OUT_TIME}"
    pkill -f "QuantumLightsOut" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 3: RasQberry Tie
    run_demo_with_controls \
        "[3/4] RasQberry Tie demo (${RASQBERRY_TIE_TIME}s)" \
        "$BIN_DIR/rq_quantum_raspberry_tie_auto.sh" \
        "${RASQBERRY_TIE_TIME}"
    pkill -f "QuantumRaspberryTie" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    # Demo 4: RasQ-LED
    run_demo_with_controls \
        "[4/4] RasQ-LED quantum circuit demo (${RASQ_LED_TIME}s)" \
        "$BIN_DIR/rq_rasq_led.sh" \
        "${RASQ_LED_TIME}"
    pkill -f "RasQ-LED" 2>/dev/null || true
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true
    sleep ${PAUSE_BETWEEN_DEMOS}

    echo "Loop #${LOOP_COUNT} complete. Starting next loop..."
    echo ""
done
