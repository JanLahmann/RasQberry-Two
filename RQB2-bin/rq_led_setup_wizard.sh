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
#   single) - possibly mounted rotated. PRIMARY question is quad-vs-single: the
#   panel alternates the IBM logo rendered through the SINGLE map (BLUE) and the
#   QUAD map (RED); only the matching geometry forms a clean, upright IBM, the
#   other scatters into noise, so the operator just picks the colour that reads
#   correctly. Orientation is a SECOND step only if the logo shows but is flipped
#   (refine_orientation cycles the 4 mountings). If BOTH colours are scrambled it
#   falls back to the general per-panel inference walkthrough (arrangement/corner/
#   run/wiring -> preset match or a custom overlay in ~/.local/config).
#
#   A "diagnostic only" mode runs the same flow and reports what it identified
#   vs what the current config says, WITHOUT writing anything.
#
# Usage:
#   sudo rq_led_setup_wizard.sh          # full wizard (mode menu), from LED menu
#   sudo rq_led_setup_wizard.sh --verify # one-look "is this your panel?" check
#
# FIRST-LOGIN VERIFY (plan R1): the image already ships a configured default
#   LED_LAYOUT, so first contact is a VERIFY step, not a from-scratch setup. The
#   --verify mode renders the IBM logo through the CURRENT layout and asks "does
#   this look correct?"; YES marks it verified, NO drops into the standards-first
#   setup to correct it. The LED menu (RQB2_menu.sh) runs --verify once, gated on
#   LED_LAYOUT_VERIFIED, so the user confirms their panel a single time.
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

stop_render_hold() {
    # Stop routing probes through the renderer and blank the strip cleanly.
    if [ -n "${RENDERER_PID}" ]; then
        # SIGTERM makes the renderer blank the strip and exit (see its run loop).
        kill -TERM "${RENDERER_PID}" 2>/dev/null || true
        wait "${RENDERER_PID}" 2>/dev/null || true
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
    (
        while true; do
            run_logo single-24x8 blue
            sleep 1.6
            run_logo quad-4x12 red
            sleep 1.6
        done
    ) &
    LOGO_ANIM_PID=$!
}
stop_logo_alternator() {
    if [ -n "${LOGO_ANIM_PID}" ]; then
        kill "${LOGO_ANIM_PID}" 2>/dev/null || true
        wait "${LOGO_ANIM_PID}" 2>/dev/null || true
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
# PRIMARY question is quad-vs-single; orientation is a SECOND step only if needed.
# The panel alternates between the IBM logo rendered through the SINGLE map (BLUE)
# and through the QUAD map (RED). Only the geometry that matches the physical
# panel forms a clean, upright, recognizable IBM - the wrong geometry scatters the
# same cells into noise. So:
#   - BLUE upright   -> single-24x8, no flip   (layout AND orientation confirmed)
#   - RED  upright   -> quad-4x12,  no flip
#   - "shows the logo but flipped/upside-down" -> we know the LAYOUT from the
#     colour; refine_orientation() cycles the 4 mountings until one is upright.
#   - "both scrambled" -> not a standard panel: fall back to general inference.
# Returns: 0 = confirmed (STD_CANDIDATE/STD_TX/STD_TY set); 1 = fall back to
# general inference; 2 = the operator cancelled.
# ----------------------------------------------------------------------------
identify_standard() {
    local choice
    start_logo_alternator
    choice=$(show_menu "LED panel type" \
"The panel is alternating between a BLUE 'IBM' logo and a RED one. One colour
uses the SINGLE-panel wiring, the other the QUAD wiring - only the one that
matches your panel forms a clean, upright IBM (the other scatters into noise).

Which colour shows a correct, upright IBM logo?" \
        blue    "BLUE is a correct, upright IBM  (single 24x8 panel)" \
        red     "RED is a correct, upright IBM   (quad of four 4x12)" \
        flipped "One colour shows the IBM but FLIPPED / upside-down" \
        neither "Both are scrambled / unreadable") || { stop_logo_alternator; return 2; }
    stop_logo_alternator

    case "${choice}" in
        blue) STD_CANDIDATE="single-24x8"; STD_TX="false"; STD_TY="false"; return 0 ;;
        red)  STD_CANDIDATE="quad-4x12";   STD_TX="false"; STD_TY="false"; return 0 ;;
        flipped) refine_orientation; return $? ;;
        neither) return 1 ;;   # both geometries wrong -> general inference
    esac
    return 1
}

# ----------------------------------------------------------------------------
# Orientation refinement (second step): a logo formed but the panel is mounted
# rotated. The colour tells us the layout; cycle the 4 mountings (normal, y-flip,
# x-flip, 180) rendering the logo each time until the operator confirms one is
# upright. Returns 0 (confirmed), 1 (none looked right -> fall back), 2 (cancel).
# ----------------------------------------------------------------------------
refine_orientation() {
    local which color ori tx ty
    which=$(show_menu "Which logo" \
"Which colour formed the IBM logo (even though it was flipped or upside-down)?" \
        blue "BLUE (single 24x8 panel)" \
        red  "RED (quad of four 4x12)") || return 2
    case "${which}" in
        blue) STD_CANDIDATE="single-24x8"; color="blue" ;;
        red)  STD_CANDIDATE="quad-4x12";   color="red"  ;;
    esac

    for ori in "false false" "false true" "true false" "true true"; do
        tx="${ori% *}"; ty="${ori#* }"
        local fargs=()
        [ "${tx}" = "true" ] && fargs+=(--flip-x)
        [ "${ty}" = "true" ] && fargs+=(--flip-y)
        # ${arr[@]+...} guards the empty-array expansion under `set -u` on older bash.
        run_logo "${STD_CANDIDATE}" "${color}" ${fargs[@]+"${fargs[@]}"}
        if show_yesno "Orientation" \
"Is the ${color} IBM logo now UPRIGHT and correct (not mirrored or upside-down)?"; then
            STD_TX="${tx}"; STD_TY="${ty}"
            return 0
        fi
    done
    return 1   # none of the four looked right -> general inference
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
    local current="${LED_LAYOUT:-<unset>}"

    # One-look confirmation: default the safe bound to the configured count (no
    # separate safety inputbox) and hold the logo lit across the question.
    UPPER_BOUND="${LED_COUNT:-192}"
    start_render_hold
    run_logo "${current}" green

    if show_yesno "Verify LED panel" \
"RasQberry ships pre-configured for this LED layout:

  LED_LAYOUT = ${current}

A GREEN 'IBM' logo is now shown on your panel. Does it look CORRECT - upright,
and NOT mirrored or upside-down?"; then
        mark_layout_verified
        run_probe clear || true
        show_msgbox "LED panel confirmed" \
"The shipped default layout matches your panel:

  LED_LAYOUT = ${current}

You can re-run the LED Setup Wizard any time from the LED menu." 12 66
        return 0
    fi

    # NO (or cancelled): offer to identify and set the correct layout.
    if show_yesno "Set up LED panel" \
"Let's identify your panel and set the correct layout. Run the setup now?"; then
        step_safety || { info "Setup cancelled."; mark_layout_verified; return 0; }
        run_identification setup
    fi
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
