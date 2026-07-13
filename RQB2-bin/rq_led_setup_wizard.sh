#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED setup wizard
# ============================================================================
# Description:
#   Interactive whiptail walkthrough that identifies the physical LED layout
#   and writes the logical config (LED_LAYOUT).
#
#   STANDARDS-FIRST (plan R1): it assumes the user has one of the three shipped
#   standard panels - single-24x8, quad-4x12, triple-8x8 (all 192 LEDs, all a
#   24x8 composite) - possibly mounted flipped/upside-down, and guides them to
#   the right one from ONE image: a two-block signature probe lights the FIRST
#   chain block (idx 0-47) RED and the LAST block (idx 144-191) GREEN. Where the
#   RED block lands fingerprints the panel AND its mounting - full-height strips
#   (far-left vs far-right) for single-24x8, or a quarter block (which corner) for
#   quad-4x12, covering 180-degree mounting and the BL-first quad chaining. Each
#   state maps to the base preset plus x/y flips. A 3x8x8 is wired like single.
#   Only if
#   the panel is not a standard does it fall back to the general per-panel
#   inference walkthrough (arrangement/corner/run/wiring -> preset match or a
#   custom overlay in ~/.local/config/led-layouts.json).
#
#   A "diagnostic only" mode runs the same flow and reports what it identified
#   vs what the current config says, WITHOUT writing anything.
#
# Usage:
#   sudo rq_led_setup_wizard.sh          # invoked from the RasQberry LED menu
#
# TODO (out of scope for this pass, plan R1): the image already ships a
#   configured default LED_LAYOUT, so first login is a VERIFY step, not a
#   from-scratch setup - offer this wizard at first login as a quick "is this
#   your panel?" confirmation (the glyph step), not gated on an absent layout.
#   Not wired to first-login here; the wizard is reached via the LED menu for now.
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
    # Best-effort: blank the strip, tear down the render-hold, remove temp dir.
    run_probe clear || true
    stop_render_hold
    rm -rf "${WORKDIR}" 2>/dev/null || true
}
setup_cleanup_trap cleanup

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
# Standards-first identification
# ============================================================================
# In practice there are two physical panels - single (24x8) and quad (four 4x12
# mounted 2x2) - and the panel may be mounted rotated 180 degrees about the
# viewing axis (which swaps left<->right AND top<->bottom, not a pure y-flip) or
# the quad may be chained the other way (BL->BR->TR->TL instead of TL->...->BL,
# which is exactly quad-4x12 y-flipped). A 3x8x8 is wired like single-24x8.
#
# ONE image identifies all of this: two solid colour BLOCKS - the FIRST chain
# block (idx 0-47) RED and the LAST chain block (idx 144-191) GREEN - plus a
# WHITE 2x2 marker at the chain start. Where the RED block lands fingerprints the
# state; the WHITE marker's corner supplies single's y-flip (which the full-height
# strips otherwise hide). GREEN is the opposite block, for confirmation:
#   - single: 8-tall columns -> full-height STRIPS. RED far-left = normal; RED
#     far-right = rotated 180.
#   - quad: 4-tall columns -> half-height quarter BLOCKS. RED upper-left = normal;
#     lower-right = 180; lower-left = alt-chain (BL-first); upper-right = alt-chain
#     rotated. Each state maps to the base preset + x/y flips (180 = both axes).
# Returns: 0 = a standard was confirmed (STD_CANDIDATE/STD_TX/STD_TY set);
# 1 = fall back to general inference; 2 = the operator cancelled.
# ----------------------------------------------------------------------------
identify_standard() {
    # One image (RED block idx 0-47, GREEN block idx 144-191, WHITE start marker),
    # held lit across two quick questions: panel type (shape), then orientation.
    local shape pos
    while true; do
        run_probe twoblock --run 48
        shape=$(show_menu "Panel type" \
"Two solid blocks are lit - RED marks the chain START, GREEN the END - with a
small WHITE 2x2 marker at the very start. Are the two big blocks:" \
            strip  "Tall FULL-HEIGHT strips (a single 24x8 panel)" \
            block  "Shorter HALF-HEIGHT blocks (a quad of four 4x12 panels)" \
            other  "Neither / not a standard RasQberry panel" \
            REPEAT "Show the pattern again") || return 2
        case "${shape}" in
            strip|block) break ;;
            other)       return 1 ;;   # fall back to general inference
            REPEAT)      continue ;;
        esac
    done

    if [ "${shape}" = "strip" ]; then
        # Single: the RED strip's SIDE gives the left/right flip; the WHITE marker
        # (top vs bottom of that strip) gives the y flip the strips alone can't.
        STD_CANDIDATE="single-24x8"
        pos=$(show_menu "Panel orientation" \
"On the RED strip: which SIDE is it on, and where is the small WHITE marker?" \
            lb "RED strip on the LEFT,  WHITE marker at its BOTTOM" \
            lt "RED strip on the LEFT,  WHITE marker at its TOP" \
            rb "RED strip on the RIGHT, WHITE marker at its BOTTOM" \
            rt "RED strip on the RIGHT, WHITE marker at its TOP") || return 2
        case "${pos}" in
            lb) STD_TX="false"; STD_TY="false" ;;
            lt) STD_TX="false"; STD_TY="true"  ;;
            rb) STD_TX="true";  STD_TY="false" ;;
            rt) STD_TX="true";  STD_TY="true"  ;;
        esac
        return 0
    fi

    # Quad: the RED block's corner encodes both axes (blocks are half-height).
    STD_CANDIDATE="quad-4x12"
    pos=$(show_menu "Panel orientation" \
"Which CORNER is the RED block in?" \
        ul "UPPER-LEFT  (normal)" \
        ur "UPPER-RIGHT" \
        ll "LOWER-LEFT" \
        lr "LOWER-RIGHT") || return 2
    case "${pos}" in
        ul) STD_TX="false"; STD_TY="false" ;;
        ur) STD_TX="true";  STD_TY="false" ;;
        ll) STD_TX="false"; STD_TY="true"  ;;
        lr) STD_TX="true";  STD_TY="true"  ;;
    esac
    return 0
}

# ============================================================================
# MAIN
# ============================================================================
main() {
    activate_venv >/dev/null 2>&1 || warn "venv not active; probes may fail if hardware libs are missing"

    local mode
    mode=$(show_menu "LED setup wizard" "Choose a mode:" \
        setup      "Identify layout and SAVE the configuration" \
        diagnostic "Diagnose wiring only (report, no changes)") || return 0

    step_safety || { info "Wizard cancelled."; return 0; }

    # Probes light patterns and ask what the operator sees; route them through
    # the persistent renderer so each pattern stays lit while they answer (fix
    # F1). Torn down by cleanup() on exit.
    start_render_hold

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

main "$@"
