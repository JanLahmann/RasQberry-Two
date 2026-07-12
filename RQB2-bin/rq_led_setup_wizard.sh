#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED setup wizard
# ============================================================================
# Description:
#   Interactive whiptail walkthrough that identifies the physical LED layout
#   and writes the logical config (LED_LAYOUT). It lights unambiguous probe
#   patterns on the strip, asks the user what they physically see, infers the
#   panel size/count/chain-order/serpentine/flip, then either selects a
#   matching shipped registry preset or writes a custom entry to the user-local
#   layouts overlay (~/.local/config/led-layouts.json).
#
#   A "diagnostic only" mode runs the same probes and reports what it inferred
#   vs what the current config says, WITHOUT writing anything.
#
# Usage:
#   sudo rq_led_setup_wizard.sh          # invoked from the RasQberry LED menu
#
# TODO (out of scope for this pass, plan Sec 2.8): offer this wizard
#   automatically on first login when no LED_LAYOUT is configured. Not
#   implemented here - the wizard is reached only via the LED menu for now.
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
PROBE_BRIGHTNESS="0.15"                 # LOW - probes never need more (current draw)
WORKDIR="$(mktemp -d)"
ANSWERS_FILE="${WORKDIR}/answers.json"

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

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------
cleanup() {
    # Best-effort: blank the strip and remove the temp dir.
    run_probe clear || true
    rm -rf "${WORKDIR}" 2>/dev/null || true
}
setup_cleanup_trap cleanup

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
    if ! json=$(python3 "${INFER}" --answers-file "${ANSWERS_FILE}" --json 2>"${WORKDIR}/err"); then
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
    if ! out=$(python3 "${INFER}" --answers-file "${ANSWERS_FILE}" --commit 2>"${WORKDIR}/err"); then
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
# MAIN
# ============================================================================
main() {
    activate_venv >/dev/null 2>&1 || warn "venv not active; probes may fail if hardware libs are missing"

    local mode
    mode=$(show_menu "LED setup wizard" "Choose a mode:" \
        setup      "Identify layout and SAVE the configuration" \
        diagnostic "Diagnose wiring only (report, no changes)") || return 0

    step_safety      || { info "Wizard cancelled."; return 0; }
    step_arrangement || { info "Wizard cancelled."; return 0; }
    step_corner      || { info "Wizard cancelled."; return 0; }
    step_run_axis    || { info "Wizard cancelled."; return 0; }
    step_wiring      || { info "Wizard cancelled."; return 0; }
    step_boundaries  || true   # informational; never blocks

    run_probe clear || true
    write_answers

    if [ "${mode}" = "diagnostic" ]; then
        run_diagnostic || true
    else
        run_setup || true
    fi
    return 0
}

main "$@"
