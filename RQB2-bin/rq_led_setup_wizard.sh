#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED setup wizard
# ============================================================================
# Description:
#   Interactive whiptail walkthrough that identifies the physical LED layout
#   and writes the logical config (LED_LAYOUT).
#
#   STANDARDS-FIRST, LOGO-BASED (plan R1): it assumes the user has one of the
#   shipped standard panels - single-24x8 or quad-4x12 (a 3x8x8 is wired like a
#   single) - possibly mounted upside-down. Only the geometry that matches the
#   physical panel forms a clean, upright IBM; the wrong one scatters the same
#   cells into noise. So the operator never measures anything - they just name
#   the colour that reads correctly. Three rounds, each only if the last found
#   nothing:
#
#     1. GREEN (single-24x8) vs RED (quad-4x12), ~2s each. The configured
#        layout is pre-selected, so "the image was already right" is one Enter.
#     2. All four candidates at once, each in its own colour: GREEN single,
#        RED quad, WHITE single upside-down, YELLOW quad upside-down.
#     3. Neither shipped panel: the general per-panel inference walkthrough
#        (arrangement/corner/run/wiring -> preset match or a custom overlay in
#        ~/.local/config), which also covers mirrored and rotated mountings.
#
#   A "diagnostic only" mode runs the same flow and reports what it identified
#   vs what the current config says, WITHOUT writing anything.
#
# Usage:
#   sudo rq_led_setup_wizard.sh          # full wizard (mode menu), from LED menu
#   sudo rq_led_setup_wizard.sh --verify # one-look "is this your panel?" check
#
# FIRST-LOGIN VERIFY (plan R1): the image already ships a configured default
#   LED_LAYOUT, so first contact is a VERIFY, not a from-scratch setup - but it
#   runs the same identification flow, because "is this right?" and "then which
#   is?" are the same question. The configured layout is pre-selected in round 1,
#   so confirming it is one Enter, and a wrong panel goes straight to the
#   alternatives rather than into a second "shall we run setup?" prompt.
#   --verify skips the safety step (it uses the configured LED_COUNT, which this
#   image already drives). The first-login checklist and the LED menu both run it
#   once, gated on LED_LAYOUT_VERIFIED.
#
# Credit: the probe/observe/infer approach is adapted (with credit, per plan
#   decision D3) from barkol's diagnose_wiring.py in
#   JanLahmann/RasQberry-Two#261.
# ============================================================================

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "${SCRIPT_DIR}/rq_common.sh"

# LED/GPIO work needs root (direct mode); re-exec with sudo if necessary.
ensure_root "$@"

# Load and verify environment
load_rqb2_env
verify_env_vars USER_HOME REPO

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
PROBE="${SCRIPT_DIR}/rq_led_wizard_probe.py"
INFER="${SCRIPT_DIR}/rq_led_wizard_infer.py"
RENDERER="${SCRIPT_DIR}/rq_led_renderer.py"
PROBE_BRIGHTNESS="0.15"                 # LOW - probes never need more (current draw)
WORKDIR="$(mktemp -d)"
ANSWERS_FILE="${WORKDIR}/answers.json"

# Render-hold state (fix F1, plan Sec 7): in the default LED_RENDER_MODE=direct
# deployment each probe subprocess opens GPIO, draws, and DEINITS on exit -
# blanking the strip before the operator is asked "which corner lit?". To hold
# the frame across the whiptail prompt we run the persistent renderer for the
# wizard's lifetime and route the probes through it in service mode: the probe
# writes its frame to the mmap and the renderer latches it. RENDERER_PID is set
# only while we own a renderer we started ourselves.
RENDERER_PID=""

# Answer variables (populated by the walkthrough)
ARRANGEMENT=""
PANEL_WIDTH=""
PANEL_HEIGHT=""
PANEL_COUNT=""
FIRST_PIXEL_CORNER=""
RUN_AXIS=""
WIRING=""
CHAIN_START="left"
UPPER_BOUND=""

# Standards-first result (populated by identify_standard): the chosen standard
# preset and the flip corrections the operator confirmed for a rotated mounting.
STD_CANDIDATE=""
STD_TX="false"
STD_TY="false"

# The inference source (set per path before run_setup/run_diagnostic): either
# --standard <name> [--flip-*] (standards-first) or --answers-file <file>
# (general inference fallback).
INFER_SRC_ARGS=()

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
cleanup() {
    # Best-effort: stop any logo animation, blank the strip, tear down the
    # render-hold, reap the virtual GUI, remove temp dir.
    #
    # Say so: this takes a few seconds (blanking the panel, waiting for the
    # renderer to go), and it runs after the last dialog closes - so without a
    # word here the wizard appears to sit silently and then vanish.
    echo "Clearing the panel and finishing up..."
    stop_logo_alternator 2>/dev/null || true
    run_probe clear || true
    stop_render_hold
    reap_virtual_gui
    rm -rf "${WORKDIR}" 2>/dev/null || true
}
setup_cleanup_trap cleanup

# ----------------------------------------------------------------------------
# Reap the auto-launched virtual LED GUI (singleton) so it does not linger past
# the wizard. Only relevant when LED_VIRTUAL is set (otherwise no GUI was ever
# spawned); rq_led_utils.reap_virtual_led_gui() only touches a GUI WE launched
# (pidfile-tracked), so a hand-started window is left alone.
# ----------------------------------------------------------------------------
reap_virtual_gui() {
    [ "${LED_VIRTUAL:-false}" = "true" ] || return 0
    PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}" python3 -c \
        'import rq_led_utils; rq_led_utils.reap_virtual_led_gui()' 2>/dev/null || true
}

# ----------------------------------------------------------------------------
# Render-hold (fix F1): keep the probe pattern lit across the whiptail prompt.
#
# start_render_hold launches the persistent renderer (the sole GPIO writer) and
# exports LED_RENDER_MODE=service so every subsequent probe writes its frame to
# the mmap instead of opening/closing GPIO itself. The renderer latches the last
# frame, so the pattern stays lit while the operator answers the dialog.
#
# Only needed when the system is in the default direct mode: if it is already in
# service mode a renderer (systemd service) is already latching frames, so we
# leave it alone. The override is a process-local env var - the root-owned env
# file is never touched, so there is nothing persistent to restore on exit.
# ----------------------------------------------------------------------------
start_render_hold() {
    # Already in service mode? A renderer is expected to be running; do nothing.
    [ "${LED_RENDER_MODE:-direct}" = "service" ] && return 0

    python3 "${RENDERER}" >/dev/null 2>&1 &
    RENDERER_PID=$!

    # Give the renderer a moment to open the mmap and the physical strip.
    sleep 1
    if ! kill -0 "${RENDERER_PID}" 2>/dev/null; then
        warn "LED renderer did not start; probes run in direct mode (pattern may not hold across the prompt)"
        RENDERER_PID=""
        return 0
    fi

    # Route probes through the mmap so the renderer latches each frame.
    export LED_RENDER_MODE=service
    info "Render-hold active: probe patterns stay lit across each prompt."
}

# Ask a child to stop, but never hang waiting for it: SIGTERM, give it a moment,
# then SIGKILL. An unbounded `wait` here froze the whole wizard - it exits
# through cleanup(), so the user answered the last question and then sat on a
# black screen forever, with raspi-config never returning (finding F2).
#
# The child that does this is the renderer: it catches SIGTERM and leaves its
# run loop, but then blanks the strip on the way out, and on a Pi 4 that call
# goes through rpi_ws281x (PWM/DMA) where it can block indefinitely. Pi 5 drives
# the strip over PIO and exits cleanly, which is why this only bites some rigs.
# The strip is blanked by the probe just above anyway, so killing the renderer
# outright costs nothing.
kill_child_bounded() {
    local pid="$1" waited=0
    [ -n "${pid}" ] || return 0
    kill -TERM "${pid}" 2>/dev/null || true
    while [ "${waited}" -lt 30 ]; do
        kill -0 "${pid}" 2>/dev/null || { wait "${pid}" 2>/dev/null || true; return 0; }
        sleep 0.1
        waited=$((waited + 1))
    done
    kill -KILL "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
}

stop_render_hold() {
    # Stop routing probes through the renderer and blank the strip cleanly.
    if [ -n "${RENDERER_PID}" ]; then
        kill_child_bounded "${RENDERER_PID}"
        RENDERER_PID=""
    fi
    unset LED_RENDER_MODE 2>/dev/null || true
}

# ----------------------------------------------------------------------------
# Probe helper: render one pattern via the python renderer (library-based, so
# it honours LED_RENDER_MODE=direct|service automatically).
# ----------------------------------------------------------------------------
run_probe() {
    local pattern="$1"; shift || true
    local count="${UPPER_BOUND:-192}"
    python3 "${PROBE}" --pattern "${pattern}" --count "${count}" \
        --brightness "${PROBE_BRIGHTNESS}" "$@" 2>/dev/null \
        || warn "probe pattern '${pattern}' failed to render"
}

# ----------------------------------------------------------------------------
# Logo helper: render the IBM logo THROUGH a named layout (optionally flipped) in
# a solid colour. Mapping the recognizable, asymmetric logo through a candidate
# layout is the core of both the standards wizard and --verify: it forms a clean,
# upright IBM only when the layout matches the panel; the wrong geometry (or a
# flipped mounting) scatters it / reads wrong.
# ----------------------------------------------------------------------------
run_logo() {
    local layout="$1" color="$2"; shift 2 || true
    local count="${UPPER_BOUND:-${LED_COUNT:-192}}"
    python3 "${PROBE}" --pattern logo --layout "${layout}" --color "${color}" \
        --count "${count}" --brightness "${PROBE_BRIGHTNESS}" "$@" 2>/dev/null \
        || warn "logo render failed for layout '${layout}'"
}

# ----------------------------------------------------------------------------
# Background logo alternator: flip the panel between the BLUE single-24x8 render
# and the RED quad-4x12 render on a timer, so both candidates are visible while
# the operator reads the (blocking) whiptail question. Needs render-hold active
# (service mode) so each frame latches. Stopped as soon as the question returns.
# ----------------------------------------------------------------------------
LOGO_ANIM_PID=""
start_logo_alternator() {
    # $1 (optional): extra probe flag(s) applied to BOTH renders (e.g. --flip-y
    # for the upside-down-mounting round). GREEN = single-24x8 wiring, RED =
    # quad-4x12 wiring; each is held ~2s so the operator can read it before it
    # swaps, then the (blocking) whiptail question is answered.
    local extra="${1:-}"
    (
        while true; do
            run_logo single-24x8 green $extra
            sleep 2
            run_logo quad-4x12 red $extra
            sleep 2
        done
    ) &
    LOGO_ANIM_PID=$!
}

# ----------------------------------------------------------------------------
# Four-candidate alternator: both shipped layouts, each also upside-down, one
# colour each. Used when neither layout looked right the normal way up.
#
# Every candidate gets its OWN colour, so the answer is "the WHITE one" rather
# than "the green one, the second time round, when they were flipped" - the old
# flow re-used GREEN and RED for the flipped pass, which asked the operator to
# remember which round they were in.
#
# Colour -> (layout, y-flip) MUST match the case block in identify_standard.
# ----------------------------------------------------------------------------
start_flip_alternator() {
    (
        while true; do
            run_logo single-24x8 green;            sleep 2
            run_logo quad-4x12   red;              sleep 2
            run_logo single-24x8 white  --flip-y;  sleep 2
            run_logo quad-4x12   yellow --flip-y;  sleep 2
        done
    ) &
    LOGO_ANIM_PID=$!
}
stop_logo_alternator() {
    if [ -n "${LOGO_ANIM_PID}" ]; then
        # Bounded: this subshell is mid-probe more often than not, and a probe
        # that wedges must not take the wizard down with it (see F2).
        kill_child_bounded "${LOGO_ANIM_PID}"
        LOGO_ANIM_PID=""
    fi
}


# ----------------------------------------------------------------------------
# Small input helper: integer inputbox with validation and a default.
# Echoes the value on success; returns 1 if the user cancelled.
# ----------------------------------------------------------------------------
ask_int() {
    local title="$1" prompt="$2" default="$3" value
    while true; do
        value=$(whiptail --title "${title}" --inputbox "${prompt}" 10 65 "${default}" \
            3>&1 1>&2 2>&3) || return 1
        if printf '%s' "${value}" | grep -qE '^[0-9]+$' && [ "${value}" -gt 0 ]; then
            printf '%s' "${value}"
            return 0
        fi
        show_msgbox "Invalid value" "Please enter a whole number greater than 0."
    done
}

# ============================================================================
# Walkthrough steps
# ============================================================================

# Step 1: safety - stated LED upper bound + low-brightness notice.
step_safety() {
    local default_count
    default_count="${LED_COUNT:-192}"
    show_msgbox "LED setup wizard" \
"This wizard lights test patterns on your LED strip and asks what you see, then
configures the matching layout.

SAFETY: probes run at low brightness (~15%). Large matrices at full white can
draw a lot of current, so the wizard caps brightness for you." 13 70

    UPPER_BOUND=$(ask_int "Safe LED upper bound" \
"Enter the maximum number of LEDs on your strip (a safe upper bound).

The wizard will not light more than this many pixels." \
        "${default_count}") || return 1
    return 0
}

# Step 2: physical arrangement + panel geometry.
step_arrangement() {
    ARRANGEMENT=$(show_menu "Panel arrangement" \
"How are your LED panels physically arranged?" \
        single           "One single panel" \
        chain-horizontal "Several panels chained side by side" \
        grid-2x2         "Four panels in a 2x2 grid") || return 1

    PANEL_WIDTH=$(ask_int "Panel width" \
"Width (number of columns) of ONE panel:" "8") || return 1
    PANEL_HEIGHT=$(ask_int "Panel height" \
"Height (number of rows) of ONE panel:" "8") || return 1

    case "${ARRANGEMENT}" in
        single)
            PANEL_COUNT=1
            ;;
        grid-2x2)
            PANEL_COUNT=4
            ;;
        chain-horizontal)
            PANEL_COUNT=$(ask_int "Panel count" \
"How many panels are chained together?" "3") || return 1
            CHAIN_START=$(show_menu "Chain start" \
"Which side of the matrix holds the FIRST panel (data-in)?" \
                left  "Left-hand side" \
                right "Right-hand side") || return 1
            ;;
    esac
    return 0
}

# Step 3: which corner did the single probe pixel light? (with repeat escape)
step_corner() {
    while true; do
        run_probe corner --index 0
        FIRST_PIXEL_CORNER=$(show_menu "First pixel" \
"A single pixel is lit (the first pixel in the chain).

Which CORNER of the matrix is it in?" \
            top-left     "Top-left" \
            top-right    "Top-right" \
            bottom-left  "Bottom-left" \
            bottom-right "Bottom-right" \
            REPEAT       "None of these / show the pattern again") || return 1
        [ "${FIRST_PIXEL_CORNER}" = "REPEAT" ] && continue
        return 0
    done
}

# Step 4: which way did the first run travel? (with repeat escape)
step_run_axis() {
    while true; do
        run_probe edge --index 0 --run "${PANEL_HEIGHT}"
        RUN_AXIS=$(show_menu "Run direction" \
"Starting from the first pixel (red), a short run of pixels (green) is lit.

Which way does that run travel from the first pixel?" \
            vertical   "Vertically (down/up a column)" \
            horizontal "Horizontally (along a row)" \
            REPEAT     "None of these / show the pattern again") || return 1
        [ "${RUN_AXIS}" = "REPEAT" ] && continue
        return 0
    done
}

# Step 5: did the second run reverse (serpentine) or repeat (progressive)?
step_wiring() {
    while true; do
        run_probe row2 --run "${PANEL_HEIGHT}"
        WIRING=$(show_menu "Wiring style" \
"Two runs are lit: the first (red) and the next one (green).

Does the green run go in the OPPOSITE direction to the red run (zig-zag), or
the SAME direction (straight back to the start)?" \
            serpentine  "Opposite direction (zig-zag / serpentine)" \
            progressive "Same direction (progressive)" \
            REPEAT      "None of these / show the pattern again") || return 1
        [ "${WIRING}" = "REPEAT" ] && continue
        return 0
    done
}

# Step 6 (multi-panel only): boundary confirmation - purely informational.
step_boundaries() {
    [ "${PANEL_COUNT}" -le 1 ] && return 0
    local panel_size=$(( PANEL_WIDTH * PANEL_HEIGHT ))
    while true; do
        run_probe boundaries --panel "${panel_size}"
        if show_yesno "Panel order" \
"The first pixel of each panel is lit in a different colour, in chain order:
red, green, blue, yellow ...

Do the colours appear in the order you expected for ${PANEL_COUNT} panels?"; then
            return 0
        fi
        if ! show_yesno "Panel order" "Show the pattern again?"; then
            return 0
        fi
    done
}

# ----------------------------------------------------------------------------
# Build the answers JSON consumed by rq_led_wizard_infer.py
# ----------------------------------------------------------------------------
write_answers() {
    cat > "${ANSWERS_FILE}" <<EOF
{
  "arrangement": "${ARRANGEMENT}",
  "panel_width": ${PANEL_WIDTH},
  "panel_height": ${PANEL_HEIGHT},
  "panel_count": ${PANEL_COUNT},
  "first_pixel_corner": "${FIRST_PIXEL_CORNER}",
  "run_axis": "${RUN_AXIS}",
  "wiring": "${WIRING}",
  "chain_start": "${CHAIN_START}",
  "upper_bound_leds": ${UPPER_BOUND}
}
EOF
}

# ----------------------------------------------------------------------------
# Diagnostic-only mode: infer, compare against current config, report, no write.
# ----------------------------------------------------------------------------
run_diagnostic() {
    local json inferred count current
    if ! json=$(python3 "${INFER}" "${INFER_SRC_ARGS[@]}" --json 2>"${WORKDIR}/err"); then
        show_msgbox "Diagnostic failed" "$(cat "${WORKDIR}/err")"
        return 1
    fi
    inferred=$(printf '%s' "${json}" | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p' | head -1)
    count=$(printf '%s' "${json}" | sed -n 's/.*"count": *\([0-9]*\).*/\1/p' | head -1)
    current="${LED_LAYOUT:-<unset>}"

    show_msgbox "LED wiring diagnostic" \
"Inferred from what you saw:
  layout : ${inferred}
  LEDs   : ${count}

Current configuration:
  LED_LAYOUT = ${current}

(No changes were written. Run the wizard in setup mode to apply.)" 14 66
}

# ----------------------------------------------------------------------------
# Setup mode: infer, apply LED_LAYOUT (writing a custom overlay entry if needed).
# ----------------------------------------------------------------------------
run_setup() {
    local out status name
    if ! out=$(python3 "${INFER}" "${INFER_SRC_ARGS[@]}" --commit 2>"${WORKDIR}/err"); then
        show_msgbox "Setup failed" "Could not infer a layout:

$(cat "${WORKDIR}/err")"
        return 1
    fi
    # out is a single line: "PRESET <name>" or "CUSTOM <name>"
    status="${out%% *}"
    name="${out#* }"

    # A custom overlay file was just written as root; hand it back to the user.
    if [ "${status}" = "CUSTOM" ]; then
        local user_overlay="${USER_HOME}/.local/config/led-layouts.json"
        if [ -f "${user_overlay}" ]; then
            fix_root_ownership "${USER_HOME}/.local/config" || true
        fi
    fi

    update_env_var "LED_LAYOUT" "${name}"

    if [ "${status}" = "PRESET" ]; then
        show_msgbox "LED layout configured" \
"Matched a built-in layout preset:

  LED_LAYOUT = ${name}

Restart any running LED demos for the change to take effect." 12 64
    else
        show_msgbox "LED layout configured" \
"No built-in preset matched, so a custom layout was written to your
user overlay (~/.local/config/led-layouts.json):

  LED_LAYOUT = ${name}

Restart any running LED demos for the change to take effect." 13 68
    fi
}

# ============================================================================
# Standards-first identification (logo-based)
# ============================================================================
# The panel alternates the IBM logo rendered through the SINGLE map (GREEN) and
# the QUAD map (RED). Only the geometry that matches the physical panel forms a
# clean, upright, recognizable IBM - the wrong geometry scatters the same cells
# into noise. So the operator names a colour, and that answers both questions at
# once: which layout, and which way up.
#
#   Round 1: GREEN upright -> single-24x8      RED upright -> quad-4x12
#            (the configured layout is pre-selected)
#   Round 2: neither? add both upside-down, all four at once, one colour each:
#            GREEN single, RED quad, WHITE single flipped, YELLOW quad flipped
#   Round 3: none of the four -> not a standard panel (or mirrored/rotated some
#            other way): fall back to the general inference walkthrough.
#
# Returns: 0 = confirmed (STD_CANDIDATE/STD_TX/STD_TY set); 1 = fall back to
# general inference; 2 = the operator cancelled.
# ----------------------------------------------------------------------------
identify_standard() {
    local choice default

    # Round 1 - the two shipped layouts, normal mounting. GREEN = single-24x8,
    # RED = quad-4x12, ~2s each. The configured layout is pre-selected, so the
    # common case (the image was right all along) is one Enter.
    default="${LED_LAYOUT:-single-24x8}"
    start_logo_alternator
    choice=$(whiptail --title "LED panel type" --default-item "${default}" --menu \
"Your panel alternates a GREEN 'IBM' logo and a RED one, ~2s each.

Only the geometry matching your panel forms a clean, upright IBM;
the other scatters into noise.

Which colour shows a correct, upright IBM logo?" \
        17 72 3 \
        "single-24x8" "GREEN is correct  (single 24x8 panel)" \
        "quad-4x12"   "RED is correct    (quad of four 4x12)" \
        "neither"     "Neither looks correct" \
        3>&1 1>&2 2>&3) || { stop_logo_alternator; return 2; }
    stop_logo_alternator
    case "${choice}" in
        single-24x8) STD_CANDIDATE="single-24x8"; STD_TX="false"; STD_TY="false"; return 0 ;;
        quad-4x12)   STD_CANDIDATE="quad-4x12";   STD_TX="false"; STD_TY="false"; return 0 ;;
    esac

    # Round 2 - the same two, plus both upside-down, ALL FOUR AT ONCE, each in
    # its own colour. Catches a panel wired correctly but mounted rotated 180.
    #
    # One menu of four beats two rounds of two: the operator compares every
    # candidate in one pass and answers by colour, instead of being asked the
    # same green/red question twice and having to remember that the second time
    # meant "flipped".
    start_flip_alternator
    choice=$(whiptail --title "LED panel type" --menu \
"Still cycling, ~2s each - now four candidates, each in its own colour:

  GREEN  = single 24x8              WHITE  = single 24x8, upside-down
  RED    = quad 4x12                YELLOW = quad 4x12, upside-down

Which colour shows a correct, upright IBM logo?" \
        18 74 5 \
        "single-24x8"      "GREEN is correct   (single 24x8)" \
        "quad-4x12"        "RED is correct     (quad 4x12)" \
        "single-24x8-flip" "WHITE is correct   (single 24x8, upside-down)" \
        "quad-4x12-flip"   "YELLOW is correct  (quad 4x12, upside-down)" \
        "none"             "None of the four - run deeper analysis" \
        3>&1 1>&2 2>&3) || { stop_logo_alternator; return 2; }
    stop_logo_alternator

    # Colour -> flips MUST match start_flip_alternator's render order.
    case "${choice}" in
        single-24x8)      STD_CANDIDATE="single-24x8"; STD_TX="false"; STD_TY="false"; return 0 ;;
        quad-4x12)        STD_CANDIDATE="quad-4x12";   STD_TX="false"; STD_TY="false"; return 0 ;;
        single-24x8-flip) STD_CANDIDATE="single-24x8"; STD_TX="false"; STD_TY="true";  return 0 ;;
        quad-4x12-flip)   STD_CANDIDATE="quad-4x12";   STD_TX="false"; STD_TY="true";  return 0 ;;
        none)             return 1 ;;   # -> general per-panel inference (the full agent)
    esac
    return 1
}


# ----------------------------------------------------------------------------
# Run standards-first identification (falling back to detailed per-panel
# inference) and then apply/report per $1 = setup|diagnostic. Assumes
# step_safety has set UPPER_BOUND and start_render_hold is active.
# ----------------------------------------------------------------------------
run_identification() {
    local mode="$1"

    # Standards-first: try to identify one of the three shipped standard panels
    # as fast as possible (~2 questions), correcting for a flipped mounting.
    local rc=0
    identify_standard || rc=$?

    if [ "${rc}" -eq 0 ]; then
        # A standard (optionally flip-corrected) was confirmed.
        INFER_SRC_ARGS=(--standard "${STD_CANDIDATE}")
        [ "${STD_TX}" = "true" ] && INFER_SRC_ARGS+=(--flip-x)
        [ "${STD_TY}" = "true" ] && INFER_SRC_ARGS+=(--flip-y)
        run_probe clear || true
        if [ "${mode}" = "diagnostic" ]; then
            run_diagnostic || true
        else
            run_setup || true
        fi
        return 0
    elif [ "${rc}" -eq 2 ]; then
        info "Wizard cancelled."
        return 0
    fi

    # rc == 1: no standard matched - fall back to the general per-panel
    # inference walkthrough (any geometry, custom overlays).
    info "Falling back to detailed layout identification."
    step_arrangement || { info "Wizard cancelled."; return 0; }
    step_corner      || { info "Wizard cancelled."; return 0; }
    step_run_axis    || { info "Wizard cancelled."; return 0; }
    step_wiring      || { info "Wizard cancelled."; return 0; }
    step_boundaries  || true   # informational; never blocks

    run_probe clear || true
    write_answers
    INFER_SRC_ARGS=(--answers-file "${ANSWERS_FILE}")

    if [ "${mode}" = "diagnostic" ]; then
        run_diagnostic || true
    else
        run_setup || true
    fi
    return 0
}

# ----------------------------------------------------------------------------
# Record that the operator has verified the LED layout, so the first-login
# prompt (driven from the LED menu) does not reappear on later sessions.
# ----------------------------------------------------------------------------
mark_layout_verified() {
    update_env_var "LED_LAYOUT_VERIFIED" "true" 2>/dev/null || \
        warn "could not persist LED_LAYOUT_VERIFIED"
}

# ============================================================================
# First-login verification (plan R1)
# ============================================================================
# The image ships a configured default LED_LAYOUT, so first contact is a VERIFY
# step, not a from-scratch setup: render the asymmetric 'F' THROUGH the current
# layout and ask whether it looks correct. YES -> mark verified. NO -> drop into
# the standards-first setup to correct it (then mark verified either way, so the
# one-time prompt does not keep reappearing). A hard cancel of the first question
# leaves it unverified so the user is offered the check again next time.
# ----------------------------------------------------------------------------
verify_layout() {
    # Show the candidates and ask which is right - do not ask about the current
    # layout on its own first.
    #
    # It used to render only the configured layout and ask yes/no, then, on "no",
    # ask a SECOND question ("run the setup now?") before showing any
    # alternative. Three prompts to reach the point. The identification flow
    # already shows both shipped layouts side by side and pre-selects the
    # configured one, so a correct panel is still a single Enter - and a wrong
    # one goes straight to the alternatives instead of a dead end.
    #
    # No safety step here: --verify runs against the configured LED_COUNT, which
    # is the count this image already drives.
    UPPER_BOUND="${LED_COUNT:-192}"
    start_render_hold
    run_identification setup
    mark_layout_verified
    return 0
}

# ============================================================================
# MAIN
# ============================================================================
main() {
    activate_venv >/dev/null 2>&1 || warn "venv not active; probes may fail if hardware libs are missing"

    # First-login VERIFY mode (invoked once from the LED menu): confirm the
    # shipped default layout matches the panel, or correct it.
    if [ "${1:-}" = "--verify" ]; then
        verify_layout
        return 0
    fi

    local mode
    mode=$(show_menu "LED setup wizard" "Choose a mode:" \
        setup      "Identify layout and SAVE the configuration" \
        diagnostic "Diagnose wiring only (report, no changes)") || return 0

    step_safety || { info "Wizard cancelled."; return 0; }

    # Probes light patterns and ask what the operator sees; route them through
    # the persistent renderer so each pattern stays lit while they answer (fix
    # F1). Torn down by cleanup() on exit.
    start_render_hold

    run_identification "${mode}"
    return 0
}

main "$@"
