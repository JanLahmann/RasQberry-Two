#!/bin/bash
set -euo pipefail

################################################################################
# rq_demo_loop.sh - RasQberry Continuous Demo Loop
#
# Description:
#   Runs LED demos one after another, for a stand (conference showcases).
#   Provides interactive controls for skipping/exiting demos.
#   Which demos it runs is a setting (DEMO_LOOP_DEMOS: "all", or a
#   comma-separated list of ibm-logo, quantum-lights-out,
#   quantum-raspberry-tie, rasq-led); the timings are DEMO_LOOP_*_TIME.
#
# Usage:
#   rq_demo_loop.sh             run the chosen demos, again and again
#   rq_demo_loop.sh --choose    choose the demos (a checklist; saved)
#   rq_demo_loop.sh --demos     print the chosen demos' names
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Ensure running as root (PWM/PIO LED drivers require GPIO access)
ensure_root "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars BIN_DIR

# Default timings (in seconds) - can be overridden via environment variables
IBM_LOGO_TIME="${DEMO_LOOP_IBM_LOGO_TIME:-15}"
LIGHTS_OUT_TIME="${DEMO_LOOP_LIGHTS_OUT_TIME:-60}"
RASQBERRY_TIE_TIME="${DEMO_LOOP_RASQBERRY_TIE_TIME:-60}"
RASQ_LED_TIME="${DEMO_LOOP_RASQ_LED_TIME:-60}"
PAUSE_BETWEEN_DEMOS="${DEMO_LOOP_PAUSE:-2}"

################################################################################
# The demos the loop can run, in loop order (Jan, 2026-10-05: choose which)
################################################################################
LOOP_IDS="ibm-logo quantum-lights-out quantum-raspberry-tie rasq-led"

loop_name() {
    case "$1" in
        ibm-logo)              echo "IBM Logo" ;;
        quantum-lights-out)    echo "Quantum Lights Out" ;;
        quantum-raspberry-tie) echo "Quantum Raspberry Tie" ;;
        rasq-led)              echo "RasQ-LED" ;;
    esac
}

loop_time() {
    case "$1" in
        ibm-logo)              echo "$IBM_LOGO_TIME" ;;
        quantum-lights-out)    echo "$LIGHTS_OUT_TIME" ;;
        quantum-raspberry-tie) echo "$RASQBERRY_TIE_TIME" ;;
        rasq-led)              echo "$RASQ_LED_TIME" ;;
    esac
}

# The chosen demos' ids, in loop order. "all", nothing or nothing known: all.
chosen_demos() {
    local saved=",${DEMO_LOOP_DEMOS:-all}," id picked=""
    saved="${saved// /}"
    for id in $LOOP_IDS; do
        case "$saved" in *",$id,"*) picked="$picked $id" ;; esac
    done
    picked="${picked# }"
    echo "${picked:-$LOOP_IDS}"
}

# The chosen demos in words: "all demos" or their names
chosen_words() {
    local ids id words=""
    ids=$(chosen_demos)
    if [ "$ids" = "$LOOP_IDS" ]; then
        echo "all demos"
        return 0
    fi
    for id in $ids; do words="${words:+$words, }$(loop_name "$id")"; done
    echo "$words"
}

# --choose: a checklist pre-ticked with the saved choice; "All demos" (or
# every demo ticked) saves "all", the one-step way back
choose_demos() {
    local chosen id state items=() sel picked=""
    chosen=" $(chosen_demos) "
    for id in $LOOP_IDS; do
        case "$chosen" in *" $id "*) state=ON ;; *) state=OFF ;; esac
        items+=("$id" "$(loop_name "$id") ($(loop_time "$id") s)" "$state")
    done
    items+=(all "All demos (as shipped)" OFF)
    sel=$(whiptail --title "Demo Loop" --notags --checklist \
"Which demos should the loop show? Space ticks a demo, Enter saves." \
        15 66 5 "${items[@]}" 3>&1 1>&2 2>&3) || return 0
    sel=" $(printf '%s' "$sel" | tr -d '"' | tr '\n\t' '  ') "
    case "$sel" in
        *" all "*) picked="all" ;;
        *)
            for id in $LOOP_IDS; do
                case "$sel" in *" $id "*) picked="${picked:+$picked,}$id" ;; esac
            done
            [ "$picked" = "${LOOP_IDS// /,}" ] && picked="all" ;;
    esac
    if [ -z "$picked" ]; then
        show_msgbox "Demo Loop" "Nothing was changed: choose at least one demo." 8 60
        return 0
    fi
    update_env_var DEMO_LOOP_DEMOS "$picked" || die "Could not save the choice of demos."
    show_msgbox "Demo Loop" "Saved. The loop shows: $(chosen_words)." 8 66
}

case "${1:-}" in
    "")       ;;
    --choose) choose_demos; exit 0 ;;
    --demos)  chosen_words; exit 0 ;;
    *)        die "Usage: rq_demo_loop.sh [--choose | --demos]" ;;
esac

LOOP_DEMOS=$(chosen_demos)

# The demos it restarts again and again are not counted one by one (the
# usage count in rq_demo_run.sh)
export RQ_DEMO_HOW=loop
# One on-screen LED view for all its demos: closing and reopening it at every
# demo would take the keyboard focus from this window each time (R-100)
export RQ_LED_KEEP_WINDOW=1

################################################################################
# cleanup - Stop all demos and turn off LEDs
################################################################################
cleanup() {
    # runs once: the exit below fires the EXIT trap again (R-164)
    trap - EXIT INT TERM
    echo ""
    info "Stopping demo loop..."
    # Kill any running demo processes
    cleanup_demo_processes "QuantumLightsOut|lights_out.py|QuantumRaspberryTie|sense_emu_gui|RasQ-LED"
    # Turn off all LEDs and close the on-screen view
    clear_leds --close-window
    info "Demo loop stopped"
    exit 0
}

# Set up trap to handle Ctrl+C
setup_cleanup_trap cleanup

################################################################################
# Download the demos first: installing inside a demo's time slot used up that
# slot (on a fresh image the whole first loop showed installers, not demos).
# One question for all missing demos, not one per demo, and a line why
# (user test 2026-10-08, F2); "Not now" runs the loop without them.
################################################################################
# The window keeps the loop's name: each demo the loop starts (rq_demo_run.sh)
# would rename it to its own (F2)
loop_title() {
    RQ_WINDOW_TITLE="Demo Loop${1:+: $1}"
    export RQ_WINDOW_TITLE
    [ -t 1 ] && printf '\033]0;%s\007' "$RQ_WINDOW_TITLE"
    return 0
}
loop_title

# A size from a demo's manifest (install.download.<field>, MB)
demo_mb() {   # <id> <field>
    local mf
    mf=$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$1" 2>/dev/null) || { echo 0; return 0; }
    jq -r ".install.download.$2 // .install.download.download_mb // 0" "$mf" 2>/dev/null || echo 0
}

drop_demo() {   # <id>: the loop runs without it
    LOOP_DEMOS=$(printf '%s\n' $LOOP_DEMOS | { grep -vx "$1" || true; } | tr '\n' ' ')
    LOOP_DEMOS="${LOOP_DEMOS% }"
}

missing=""
for demo in quantum-lights-out quantum-raspberry-tie; do
    case " $LOOP_DEMOS " in *" $demo "*) ;; *) continue ;; esac
    "$BIN_DIR/rq_demo_run.sh" "$demo" --is-installed >/dev/null 2>&1 || missing="$missing $demo"
done
missing="${missing# }"
if [ -n "$missing" ]; then
    names="" dl=0 disk=0 verb="is"
    [ "${missing#* }" = "$missing" ] || verb="are"
    for demo in $missing; do
        names="${names:+$names and }$(loop_name "$demo")"
        dl=$((dl + $(demo_mb "$demo" download_mb)))
        disk=$((disk + $(demo_mb "$demo" disk_mb)))
    done
    rc=0
    rq_confirm_download "$names" "$dl" "$disk" --url "https://github.com" \
        --what "Demo code from GitHub" \
        --title "Demo Loop" \
        --intro "The Demo Loop shows $names, which $verb not on this Pi yet." \
        --question "Download now? (Not now: the loop runs without them.)" || rc=$?
    if [ "$rc" = 0 ]; then
        for demo in $missing; do
            echo "Downloading $(loop_name "$demo") for the loop..."
            if ! RQ_AUTO_INSTALL=1 "$BIN_DIR/rq_demo_run.sh" "$demo" --install-only; then
                warn "Could not download $(loop_name "$demo"): the loop runs without it."
                drop_demo "$demo"
            fi
        done
    else
        [ "$rc" = 1 ] || warn "${RQ_CONSENT_MSG:-The download was stopped.}"
        for demo in $missing; do drop_demo "$demo"; done
        info "The loop runs without $names."
    fi
    loop_title
fi
[ -n "$LOOP_DEMOS" ] || { info "No demo left to show."; exit 0; }
# shellcheck disable=SC2086
set -- $LOOP_DEMOS
LOOP_COUNT_DEMOS=$#
echo ""

################################################################################
# Display header and instructions
################################################################################

echo "=============================================="
echo "  RasQberry Continuous Demo Loop"
echo "=============================================="
echo ""
echo "Demo timings:"
for id in $LOOP_DEMOS; do
    echo "  - $(loop_name "$id"): $(loop_time "$id")s"
done
echo "  (Choose: RasQberry menu > Quantum Demos > Workshops & events > Demo Loop)"
echo ""
echo "=============================================="
echo "  Controls:"
echo "    Press ENTER or 'q' - Skip to next demo"
echo "    Press 'x' or 'X'   - Exit demo loop"
echo "    Press Ctrl+C       - Emergency stop"
echo "=============================================="
echo ""

################################################################################
# run_demo_with_controls - Run a demo with interactive skip/exit option
#
# Arguments:
#   $1 - Demo name (for display)
#   $2 - Demo command to run
#   $3 - Demo timeout (seconds)
################################################################################
run_demo_with_controls() {
    local demo_name="$1"
    local demo_cmd="$2"
    local demo_time="$3"

    echo "$demo_name..."

    # Run demo in background with timeout
    timeout "$demo_time" bash -c "$demo_cmd" &
    DEMO_PID=$!

    # Clear any buffered input from stdin before monitoring
    # This prevents accidental immediate skip when launched from desktop icons
    while read -t 0; do read -t 0.1 -n 1000; done 2>/dev/null

    # Monitor for user input while demo runs
    local elapsed=0
    while kill -0 $DEMO_PID 2>/dev/null; do
        # Check for keypress (non-blocking, 1 second timeout). Ctrl+C runs
        # the cleanup trap after the read, not inside it (rq_read_deferred)
        if rq_read_deferred -t 1 -n 1 key 2>/dev/null; then
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

# One demo of the loop: run it, then stop what it left and clear the panel
run_loop_demo() {   # <id> <number>
    local id="$1" n="$2" t
    t=$(loop_time "$id")
    loop_title "$(loop_name "$id")"
    case "$id" in
        ibm-logo)
            run_demo_with_controls "[$n/$LOOP_COUNT_DEMOS] IBM Logo animation (${t}s)" \
                "$BIN_DIR/rq_led_ibm_demo.sh" "$t" ;;
        quantum-lights-out)
            run_demo_with_controls "[$n/$LOOP_COUNT_DEMOS] Quantum Lights Out demo (${t}s)" \
                "$BIN_DIR/rq_demo_run.sh quantum-lights-out" "$t"
            cleanup_demo_processes "QuantumLightsOut" "lights_out.py"
            clear_leds ;;
        quantum-raspberry-tie)
            run_demo_with_controls "[$n/$LOOP_COUNT_DEMOS] Quantum Raspberry Tie demo (${t}s)" \
                "$BIN_DIR/rq_demo_run.sh quantum-raspberry-tie" "$t"
            # Raspberry Tie also opens the SenseHAT emulator window
            cleanup_demo_processes "QuantumRaspberryTie" "sense_emu_gui"
            clear_leds ;;
        rasq-led)
            run_demo_with_controls "[$n/$LOOP_COUNT_DEMOS] RasQ-LED quantum circuit demo (${t}s)" \
                "$BIN_DIR/rq_rasq_led.sh" "$t"
            cleanup_demo_processes "RasQ-LED"
            clear_leds ;;
    esac
    sleep "${PAUSE_BETWEEN_DEMOS}"
}

################################################################################
# Main demo loop (RQ_DEMO_LOOP_ROUNDS: stop after that many rounds - tests)
################################################################################

LOOP_COUNT=0

while true; do
    LOOP_COUNT=$((LOOP_COUNT + 1))
    echo "========================================="
    echo "Loop #${LOOP_COUNT} - $(date '+%H:%M:%S')"
    echo "========================================="

    n=0
    for id in $LOOP_DEMOS; do
        n=$((n + 1))
        run_loop_demo "$id" "$n"
    done

    echo "Loop #${LOOP_COUNT} complete. Starting next loop..."
    echo ""
    if [ "${RQ_DEMO_LOOP_ROUNDS:-0}" -gt 0 ] && [ "$LOOP_COUNT" -ge "${RQ_DEMO_LOOP_ROUNDS}" ]; then
        cleanup
    fi
done
