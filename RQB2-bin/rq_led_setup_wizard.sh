#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: LED setup wizard
# ============================================================================
# Description:
#   Interactive whiptail walkthrough that identifies the physical LED layout
#   and writes the logical config (LED_LAYOUT).
#
#   STANDARDS-FIRST, LOGO-BASED (plan R1): it assumes one of the two supported
#   kits - one 24x8 panel (single-24x8) or four 4x12 panels (quad-4x12; a 3x8x8
#   is wired like a single) - possibly mounted upside-down. Only the geometry
#   that matches the physical panel forms a clean, upright IBM logo; the wrong
#   one scatters the same cells into noise. So the person never measures
#   anything - they say which logo reads correctly:
#
#     1. single-24x8 in BLUE, steady, then quad-4x12 in YELLOW, blinking.
#        Blue/yellow stays apart for red-green colour blindness, and steady vs
#        blinking needs no colour at all (R-011). Nothing is pre-selected: both
#        kits are supported (Jan, Q11), and the highlighted first item only
#        explains what to look for.
#     2. Neither? The same two upside-down.
#     3. Still neither: the general per-panel walkthrough (arrangement/corner/
#        run/wiring -> preset match or a custom overlay in ~/.local/config).
#
#   Every answer is confirmed before anything is saved: the chosen layout alone,
#   in WHITE, "does it read IBM, the right way up?" (R-010, R-011). "Nothing
#   lights up / no panel" leads to a short wiring and power checklist and saves
#   nothing but LED_LAYOUT_VERIFIED=skipped, if the person asks for that (R-009,
#   R-010). A layout saved here is also marked verified, in the full wizard too,
#   so the check is not offered again and /data gets "true" (R-150).
#
#   A "diagnostic only" mode runs the same flow and reports what it identified
#   vs what the current config says, WITHOUT writing anything.
#
# Usage:
#   sudo rq_led_setup_wizard.sh          # full wizard (mode menu), from LED menu
#   sudo rq_led_setup_wizard.sh --verify # the LED panel check (setup checklist)
#
# The setup checklist and the LED menu's first visit run --verify while
# LED_LAYOUT_VERIFIED is false; it skips the LED count question (it uses the
# configured layout's count, which this image already drives).
#
# Credit: the probe/observe/infer approach is adapted (with credit, per plan
#   decision D3) from barkol's diagnose_wiring.py in
#   JanLahmann/RasQberry-Two#261.
# ============================================================================

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

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
# Render errors go here, never to the terminal: the logo alternator runs in the
# background while a whiptail question is on screen, and its warnings were
# printed straight across the dialog.
WIZ_LOG="${RQ_WIZ_LOG:-/var/log/rasqberry-led-wizard.log}"
ANSWERS_FILE="${WORKDIR}/answers.json"

# Render-hold state (fix F1, plan Sec 7): in the default LED_RENDER_MODE=direct
# deployment each probe subprocess opens GPIO, draws, and DEINITS on exit -
# blanking the strip before the operator is asked "which corner lit?". To hold
# the frame across the whiptail prompt we run the persistent renderer for the
# wizard's lifetime and route the probes through it in service mode: the probe
# writes its frame to the mmap and the renderer latches it. RENDERER_PID is set
# only while we own a renderer we started ourselves.
RENDERER_PID=""

# The mode every probe, logo and the address scroll draw in while the
# render-hold is up (hold_env). Not the exported LED_RENDER_MODE alone: saving
# a setting (update_env_var) reloads the env file, and its "direct" replaced
# "service" while the renderer still held the panel. The address scroll after
# "Saved" and the last clears then opened the panel themselves: on a Pi 5 the
# scroll could not start (#7); on a Pi 4 two drivers shared the PWM, and the
# one that stopped first left the other's DMA transfer hanging, so the next
# LED demo stayed dark for its whole run (#1).
HOLD_MODE=""

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

# setup | diagnostic (the wiring check writes nothing at all)
WIZ_MODE="setup"

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
    stop_ip_scroll 2>/dev/null || true
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
# sets HOLD_MODE=service so every subsequent probe (hold_env) writes its frame
# to the mmap instead of opening/closing GPIO itself. The renderer latches the
# last frame, so the pattern stays lit while the operator answers the dialog.
#
# Only needed when the system is in the default direct mode: if it is already in
# service mode a renderer (systemd service) is already latching frames, so we
# leave it alone. The override lives in this process only - the root-owned env
# file is never touched, so there is nothing persistent to restore on exit.
# ----------------------------------------------------------------------------
start_render_hold() {
    # The person has been told why (R-133: no second, generic error box)
    ensure_leds_free || exit 0

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
    HOLD_MODE=service
    debug "Render-hold active: probe patterns stay lit across each prompt."
}

# Run a drawing child in the render-hold's mode (see HOLD_MODE)
hold_env() {
    LED_RENDER_MODE="${HOLD_MODE:-${LED_RENDER_MODE:-direct}}" "$@"
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
    HOLD_MODE=""
}

# ----------------------------------------------------------------------------
# Probe helper: render one pattern via the python renderer (library-based, so
# it honours LED_RENDER_MODE=direct|service automatically).
# ----------------------------------------------------------------------------
run_probe() {
    local pattern="$1"; shift || true
    local count="${UPPER_BOUND:-192}"
    hold_env python3 "${PROBE}" --pattern "${pattern}" --count "${count}" \
        --brightness "${PROBE_BRIGHTNESS}" "$@" 2>>"${WIZ_LOG}" \
        || echo "$(date '+%F %T') probe pattern '${pattern}' failed to render" >> "${WIZ_LOG}"
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
    # A path is a custom layout the wizard has not saved yet (--layout-file)
    local src=(--layout "${layout}")
    case "${layout}" in /*) src=(--layout-file "${layout}") ;; esac
    hold_env python3 "${PROBE}" --pattern logo "${src[@]}" --color "${color}" \
        --count "${count}" --brightness "${PROBE_BRIGHTNESS}" "$@" 2>>"${WIZ_LOG}" \
        || echo "$(date '+%F %T') logo render failed for layout '${layout}'" >> "${WIZ_LOG}"
}

# ----------------------------------------------------------------------------
# Can we drive the panel at all? Another program holding it (a demo left
# running, the demo loop, the IP scroll at start-up) made every render fail on
# a Pi 5 - and on a Pi 4, where the PWM driver claims nothing, it drew over the
# test patterns without any error (R-162). So look for a holder FIRST
# (led_holders in rq_common.sh), name it and offer to stop it.
# ----------------------------------------------------------------------------
ensure_leds_free() {
    local holders
    holders=$(led_holders)
    if [ -n "$holders" ]; then
        if ! whiptail --title "LED Panel in Use" --yes-button "Stop It" --no-button "Cancel" --yesno \
"Another program is using the LED panel, so the check cannot show anything:

$(echo "$holders" | sed 's/^[0-9]* /  /')

Stop it and continue?" $(( $(echo "$holders" | wc -l) + 10 )) 70; then
            return 1
        fi
        stop_led_holders "$holders"
    fi
    python3 "${PROBE}" --pattern clear --count "${UPPER_BOUND:-${LED_COUNT:-192}}" \
        --brightness "${PROBE_BRIGHTNESS}" 2>>"${WIZ_LOG}" && return 0
    show_msgbox "LED Panel Not Responding" \
"The LED panel could not be driven. Check the cable and the power supply, then try again.

Details: ${WIZ_LOG}" 12 66
    return 1
}

# ----------------------------------------------------------------------------
# The two candidates, one after the other, while the question is on screen:
# single-24x8 in BLUE, steady (~2 s), then quad-4x12 in YELLOW, blinking
# (~2.4 s). Needs render-hold (service mode) so each frame stays lit. $1:
# --flip-y for the upside-down round. Stopped as soon as the question returns.
# ----------------------------------------------------------------------------
LOGO_ANIM_PID=""
start_logo_alternator() {
    local extra="${1:-}"
    (
        while true; do
            run_logo single-24x8 blue $extra
            sleep 2
            run_logo quad-4x12 yellow --blink 3 $extra
        done
    ) &
    LOGO_ANIM_PID=$!
}
stop_logo_alternator() {
    local pid="${LOGO_ANIM_PID}" kids
    [ -n "${pid}" ] || return 0
    LOGO_ANIM_PID=""
    # Freeze the loop so it starts nothing new, and stop the probe it is
    # running: a blinking one went on drawing for two more seconds, over the
    # next pattern. Then end the loop - bounded: a probe that wedges must not
    # take the wizard down with it (see F2).
    kill -STOP "${pid}" 2>/dev/null || true
    kids=$(pgrep -P "${pid}" 2>/dev/null | tr '\n' ' ' || true)
    # shellcheck disable=SC2086
    [ -z "${kids// /}" ] || kill -TERM ${kids} 2>/dev/null || true
    kill -TERM "${pid}" 2>/dev/null || true
    kill -CONT "${pid}" 2>/dev/null || true
    kill_child_bounded "${pid}"
}

# ----------------------------------------------------------------------------
# A whiptail menu sized to its text (rq_common's show_menu has a fixed height,
# which left one line for the question). Usage: ask_menu TITLE TEXT TAG DESC...
# ----------------------------------------------------------------------------
ask_menu() {
    local title="$1" text="$2" width=76 lines items rows height
    shift 2
    lines=$(printf '%b\n' "$text" | fold -s -w $((width - 4)) | wc -l)
    items=$(( $# / 2 ))
    rows=$(tput lines 2>/dev/null || echo 24)
    [ "$rows" -ge 12 ] 2>/dev/null || rows=24
    height=$(( lines + items + 8 ))
    [ "$height" -gt "$rows" ] && height="$rows"
    whiptail --title "$title" --notags --menu "$text" "$height" "$width" "$items" \
        -- "$@" 3>&1 1>&2 2>&3
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

# Step 1: how many LEDs at most (the full wizard only; --verify uses the
# configured layout's count).
step_safety() {
    local default_count
    default_count="${LED_COUNT:-192}"
    show_msgbox "LED Setup Wizard" \
"This wizard lights test patterns on your LED panel, asks what you see and saves the matching layout.

The patterns are dim (about 15% brightness), so any power supply copes with them." 12 66

    UPPER_BOUND=$(ask_int "Number of LEDs" \
"How many LEDs does your panel have in total? Both RasQberry Two kits have 192. The wizard lights no more than this." \
        "${default_count}") || return 1
    return 0
}

# Step 2: physical arrangement + panel geometry. The size questions start at
# the kit panels' sizes for that arrangement (R-010).
step_arrangement() {
    local def_w=8 def_h=8
    ARRANGEMENT=$(ask_menu "Panel Arrangement" \
"How are your LED panels arranged?" \
        single           "One single panel" \
        grid-2x2         "Four panels, two above two" \
        chain-horizontal "Several panels side by side") || return 1

    case "${ARRANGEMENT}" in
        single)   def_w=24; def_h=8 ;;
        grid-2x2) def_w=12; def_h=4 ;;
    esac
    PANEL_WIDTH=$(ask_int "Panel Width" \
"Width of ONE panel (number of LED columns):" "${def_w}") || return 1
    PANEL_HEIGHT=$(ask_int "Panel Height" \
"Height of ONE panel (number of LED rows):" "${def_h}") || return 1

    case "${ARRANGEMENT}" in
        single)
            PANEL_COUNT=1
            ;;
        grid-2x2)
            PANEL_COUNT=4
            ;;
        chain-horizontal)
            PANEL_COUNT=$(ask_int "Number of Panels" \
"How many panels are chained together?" "3") || return 1
            CHAIN_START=$(ask_menu "Chain Start" \
"Which side holds the FIRST panel (the one the data wire goes into)?" \
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
        FIRST_PIXEL_CORNER=$(ask_menu "First LED" \
"One LED is lit: the first one in the chain. In which CORNER of the panel is it?" \
            top-left     "Top left" \
            top-right    "Top right" \
            bottom-left  "Bottom left" \
            bottom-right "Bottom right" \
            REPEAT       "None of these / show it again") || return 1
        [ "${FIRST_PIXEL_CORNER}" = "REPEAT" ] && continue
        return 0
    done
}

# Step 4: which way did the first run travel? (with repeat escape)
step_run_axis() {
    while true; do
        run_probe edge --index 0 --run "${PANEL_HEIGHT}"
        RUN_AXIS=$(ask_menu "Run Direction" \
"A short line is lit: it starts at the WHITE LED (the first one) and goes on in blue. Which way does it go?" \
            vertical   "Up or down (along a column)" \
            horizontal "Left or right (along a row)" \
            REPEAT     "None of these / show it again") || return 1
        [ "${RUN_AXIS}" = "REPEAT" ] && continue
        return 0
    done
}

# Step 5: did the second run reverse (serpentine) or repeat (progressive)?
step_wiring() {
    while true; do
        run_probe row2 --run "${PANEL_HEIGHT}"
        WIRING=$(ask_menu "Wiring" \
"Two lines are lit. Each starts at a WHITE LED: the first goes on in blue, the next one in yellow. Do the two lines run in OPPOSITE directions (zig-zag) or the SAME direction?" \
            serpentine  "Opposite directions (zig-zag)" \
            progressive "The same direction" \
            REPEAT      "None of these / show it again") || return 1
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
        if show_yesno "Panel Order" \
"The first LED of each panel is lit, in chain order: red, green, blue, yellow and so on.

Is there one lit LED on each of the ${PANEL_COUNT} panels?"; then
            return 0
        fi
        if ! show_yesno "Panel Order" "Show the pattern again?"; then
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
    local json inferred count
    if ! json=$(python3 "${INFER}" "${INFER_SRC_ARGS[@]}" --json 2>"${WORKDIR}/err"); then
        show_msgbox "Check Failed" "$(cat "${WORKDIR}/err")"
        return 1
    fi
    inferred=$(printf '%s' "${json}" | sed -n 's/.*"name": *"\([^"]*\)".*/\1/p' | head -1)
    count=$(printf '%s' "${json}" | sed -n 's/.*"count": *\([0-9]*\).*/\1/p' | head -1)

    show_msgbox "LED Wiring Check" \
"From what you saw: $(rq_led_layout_name "${inferred}") (${count} LEDs)

Saved now: $(rq_led_layout_name "${LED_LAYOUT:-}")

Nothing was changed. To save it, run the wizard again and choose the first option." 14 66
}

# ----------------------------------------------------------------------------
# Save: infer, apply LED_LAYOUT (writing a custom overlay entry if needed) and
# mark it verified. Only reached after the person confirmed the layout on the
# panel (confirm_layout), in the full wizard as in the check: the full wizard
# used to save LED_LAYOUT but leave LED_LAYOUT_VERIFIED=false, so the check
# kept coming back and that "false" was copied to /data (R-009, R-150).
# ----------------------------------------------------------------------------
run_setup() {
    local out status name
    if ! out=$(python3 "${INFER}" "${INFER_SRC_ARGS[@]}" --commit 2>"${WORKDIR}/err"); then
        show_msgbox "Not Saved" "The layout could not be worked out:

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

    # Both LED_* writes also save the device settings to /data on the A/B
    # image; the second one carries VERIFIED=true there.
    update_env_var "LED_LAYOUT" "${name}"
    mark_layout_verified

    # The address scroll in the saved layout while the message is up: the
    # person sees it readable now, not only at the next start (#29)
    local plain scroll_note=""
    plain=$(rq_led_layout_name "${name}")
    start_ip_scroll && scroll_note="
The panel shows this Pi's address once, in this layout."
    if [ "${status}" = "PRESET" ]; then
        show_msgbox "LED Panel Set Up" \
"Saved: ${plain}
${scroll_note}
LED demos use it from their next start." 12 64
    else
        show_msgbox "LED Panel Set Up" \
"No built-in layout matched, so yours was saved as a custom layout (in ~/.local/config/led-layouts.json):

  ${plain}
${scroll_note}
LED demos use it from their next start." 14 66
    fi
    stop_ip_scroll
}

# ----------------------------------------------------------------------------
# One pass of the start-up address scroll (rq_display_ip.py --once) in the
# layout just saved, in the background while the "Saved" message is up (#29).
# It draws through the render-hold renderer like every probe, so it holds no
# GPIO of its own; stop_ip_scroll ends it (bounded) and clears the panel, so
# nothing is left on the panel or holding it for the next demo.
# ----------------------------------------------------------------------------
IP_SCROLL_PID=""
start_ip_scroll() {
    local disp="${SCRIPT_DIR}/rq_display_ip.py"
    [ -f "${disp}" ] || return 1
    # hold_env written out: a function in the background would be a subshell,
    # and $! its PID, not the scroll's
    LED_RENDER_MODE="${HOLD_MODE:-${LED_RENDER_MODE:-direct}}" \
        python3 "${disp}" --once >>"${WIZ_LOG}" 2>&1 &
    IP_SCROLL_PID=$!
    return 0
}
stop_ip_scroll() {
    local pid="${IP_SCROLL_PID}"
    [ -n "${pid}" ] || return 0
    IP_SCROLL_PID=""
    kill_child_bounded "${pid}"
    run_probe clear || true
}

# ----------------------------------------------------------------------------
# Confirm a layout before saving it, without relying on colour (R-010, R-011):
# the panel shows ONLY that layout's logo, steady and in WHITE.
#   confirm_layout LAYOUT [--flip-y]    LAYOUT: a name, or a layout JSON file
# Returns 0 = it reads IBM the right way up; 1 = look again; 2 = cancelled.
# ----------------------------------------------------------------------------
confirm_layout() {
    local layout="$1" rc=0
    shift || true
    run_logo "${layout}" white "$@"
    whiptail --title "LED Panel Check" --yes-button "Yes, Save" --no-button "No, Look Again" \
        --yesno "Your choice is now shown alone, in white.

Does the panel show IBM, the right way up?" 11 64 || rc=$?
    run_probe clear || true
    case "${rc}" in
        0) return 0 ;;
        1) return 1 ;;
        *) return 2 ;;
    esac
}

# ----------------------------------------------------------------------------
# What a correct logo looks like (the highlighted first item of the question,
# so a careless Enter explains instead of saving a kit - Q11).
# ----------------------------------------------------------------------------
show_logo_help() {
    show_msgbox "What to Look For" \
"The right one shows the three letters I, B and M side by side, left to right, the right way up, across the whole panel. The other one is a scatter of dots and broken bars.

You do not need to tell the colours apart: the blue logo stays on, the yellow one blinks.

A logo that is upside down or mirrored is not right yet: choose \"Neither\", and the next question shows both turned round." 16 70
}

# ----------------------------------------------------------------------------
# "Nothing lights up / no LED panel" (R-009, R-010): what to check, the views
# that need no panel, and a way out that saves nothing but
# LED_LAYOUT_VERIFIED=skipped (the check is then not offered again).
# Returns 0 = look again; 1 = skipped; 2 = cancelled.
# ----------------------------------------------------------------------------
no_light_help() {
    local pin="${LED_GPIO_PIN:-18}" phys="" choice
    case "${pin}" in
        18) phys=" (pin 12)" ;;
        21) phys=" (pin 40)" ;;
        12) phys=" (pin 32)" ;;
        10) phys=" (pin 19)" ;;
    esac
    run_probe clear || true
    if [ "${WIZ_MODE}" = "diagnostic" ]; then
        # The wiring check saves nothing, not even "skipped"
        set -- again "Check again" stop "Stop the check"
    else
        set -- again "Check again" skip "No LED panel for now: skip the check"
    fi
    choice=$(ask_menu "No Light on the LED Panel" \
"If a panel is connected, check:
 - power: its 5V and GND wires, or its own power supply
 - data: GPIO${pin}${phys} to DIN, the input end of the panel
 - the plugs between the panels

No panel? LED demos also show in a window on the desktop and in a web browser (Quantum Demos -> LED panel -> LED setup & tests -> Output Targets)." \
        "$@") || return 2
    case "${choice}" in
        again) return 0 ;;
        stop)  return 2 ;;
    esac
    mark_layout_skipped
    show_msgbox "LED Panel Check Skipped" \
"Nothing else was changed. When a panel is connected, run the check from the RasQberry Setup icon, or: sudo raspi-config -> 0 RasQberry -> Quantum Demos -> LED panel -> LED setup & tests -> Check the LED Panel." 11 66
    return 1
}

# ============================================================================
# Standards-first identification (logo-based)
# ============================================================================
# The panel shows the IBM logo through the single map (BLUE, steady) and the
# quad map (YELLOW, blinking), one after the other. Only the geometry that
# matches the physical panel forms a clean, upright IBM; the other scatters
# the same cells into noise.
#
#   Round 1: the two kits, normal mounting.
#   Round 2: the same two, upside-down (--flip-y).
#   Then:    neither -> the general per-panel walkthrough.
#
# Every pick is confirmed in white (confirm_layout) before it counts.
#
# Returns: 0 = confirmed (STD_CANDIDATE/STD_TX/STD_TY set); 1 = fall back to the
# general walkthrough; 2 = cancelled; 3 = no light / no panel (skipped).
# ----------------------------------------------------------------------------
identify_standard() {
    local choice round=1 flip cand rc

    while true; do
        if [ "${round}" = 1 ]; then
            flip=""
            start_logo_alternator
            choice=$(ask_menu "LED Panel Check" \
"Your LED panel shows the IBM logo two ways, one after the other: BLUE and steady, then YELLOW and blinking. Only the one that matches your panel reads IBM, the right way up.

Which one reads IBM?" \
                help    "Not sure? What to look for" \
                blue    "BLUE, steady       (one 24x8 panel)" \
                yellow  "YELLOW, blinking   (four 4x12 panels)" \
                neither "Neither reads IBM" \
                dark    "Nothing lights up / no LED panel") || choice="cancel"
        else
            flip="--flip-y"
            start_logo_alternator --flip-y
            choice=$(ask_menu "LED Panel Check" \
"Now the same two, turned upside down: BLUE and steady, then YELLOW and blinking.

Which one reads IBM, the right way up?" \
                help    "Not sure? What to look for" \
                blue    "BLUE, steady       (24x8 panel, mounted upside down)" \
                yellow  "YELLOW, blinking   (4x12 panels, mounted upside down)" \
                back    "Show the first two again" \
                neither "Neither: work it out step by step" \
                dark    "Nothing lights up / no LED panel") || choice="cancel"
        fi
        stop_logo_alternator

        case "${choice}" in
            cancel)  return 2 ;;
            help)    show_logo_help; continue ;;
            back)    round=1; continue ;;
            neither) [ "${round}" = 1 ] && { round=2; continue; }; return 1 ;;
            dark)
                rc=0; no_light_help || rc=$?
                case "${rc}" in
                    0) round=1; continue ;;
                    1) return 3 ;;
                    *) return 2 ;;
                esac ;;
            blue)    cand="single-24x8" ;;
            yellow)  cand="quad-4x12" ;;
            *)       continue ;;
        esac

        rc=0; confirm_layout "${cand}" ${flip} || rc=$?
        case "${rc}" in
            0)
                STD_CANDIDATE="${cand}"; STD_TX="false"; STD_TY="false"
                [ -n "${flip}" ] && STD_TY="true"
                return 0 ;;
            2) return 2 ;;
        esac
        round=1
    done
}


# ----------------------------------------------------------------------------
# Run standards-first identification (falling back to detailed per-panel
# inference) and then apply/report per $1 = setup|diagnostic. Assumes
# UPPER_BOUND is set and start_render_hold is active.
# Sets SETUP_SAVED=true when a layout was saved, SKIPPED=true for "no panel".
# ----------------------------------------------------------------------------
run_identification() {
    local mode="$1"
    WIZ_MODE="${mode}"

    local rc=0
    identify_standard || rc=$?

    case "${rc}" in
        0)
            INFER_SRC_ARGS=(--standard "${STD_CANDIDATE}")
            [ "${STD_TX}" = "true" ] && INFER_SRC_ARGS+=(--flip-x)
            [ "${STD_TY}" = "true" ] && INFER_SRC_ARGS+=(--flip-y)
            run_probe clear || true
            if [ "${mode}" = "diagnostic" ]; then
                run_diagnostic || true
            else
                run_setup && SETUP_SAVED=true || true
            fi
            return 0 ;;
        2) echo "LED panel check cancelled. Nothing was saved."; return 0 ;;
        3) SKIPPED=true; return 0 ;;
    esac

    # rc == 1: no standard matched - fall back to the general per-panel
    # inference walkthrough (any geometry, custom overlays).
    debug "Falling back to detailed layout identification."
    step_arrangement || { echo "Cancelled. Nothing was saved."; return 0; }
    step_corner      || { echo "Cancelled. Nothing was saved."; return 0; }
    step_run_axis    || { echo "Cancelled. Nothing was saved."; return 0; }
    step_wiring      || { echo "Cancelled. Nothing was saved."; return 0; }
    step_boundaries  || true   # informational; never blocks

    run_probe clear || true
    write_answers
    INFER_SRC_ARGS=(--answers-file "${ANSWERS_FILE}")

    if [ "${mode}" = "diagnostic" ]; then
        run_diagnostic || true
        return 0
    fi

    # Show the result before saving it (R-010): a wrong guess on a dark or
    # half-seen panel used to be saved straight away, and marked verified.
    local json candidate="${WORKDIR}/candidate-layout.json"
    if ! json=$(python3 "${INFER}" "${INFER_SRC_ARGS[@]}" --json 2>"${WORKDIR}/err"); then
        show_msgbox "Not Saved" "The layout could not be worked out:

$(cat "${WORKDIR}/err")"
        return 0
    fi
    printf '%s' "${json}" | python3 -c 'import json, sys; json.dump(json.load(sys.stdin)["layout"], open(sys.argv[1], "w"))' "${candidate}" \
        || { show_msgbox "Not Saved" "The layout could not be prepared. Details: ${WIZ_LOG}"; return 0; }
    rc=0; confirm_layout "${candidate}" || rc=$?
    if [ "${rc}" -ne 0 ]; then
        show_msgbox "Not Saved" \
"Nothing was saved. Run the wizard again and compare each question with the panel, or ask for help with the photo of the panel and the answers you gave." 11 64
        return 0
    fi
    run_setup && SETUP_SAVED=true || true
    return 0
}

# ----------------------------------------------------------------------------
# Record the result of the check: true = the layout was confirmed on the
# panel; skipped = no panel (the setup checklist stops offering the check).
# ----------------------------------------------------------------------------
mark_layout_verified() {
    update_env_var "LED_LAYOUT_VERIFIED" "true" 2>/dev/null || \
        warn "could not save LED_LAYOUT_VERIFIED"
}

mark_layout_skipped() {
    update_env_var "LED_LAYOUT_VERIFIED" "skipped" 2>/dev/null || \
        warn "could not save LED_LAYOUT_VERIFIED"
}

# ============================================================================
# The LED panel check (--verify): setup checklist and the LED menu
# ============================================================================
# The image ships a default LED_LAYOUT, but which kit is on the desk is not
# known, so the check asks without a pre-selected answer (Q11). No LED count
# question: it uses the configured layout's count, which this image drives.
# ----------------------------------------------------------------------------
verify_layout() {
    UPPER_BOUND="${LED_COUNT:-192}"
    start_render_hold
    SETUP_SAVED=false
    SKIPPED=false
    run_identification setup
    if [ "${SETUP_SAVED}" != true ] && [ "${SKIPPED}" != true ]; then
        echo "The LED panel check is not done yet. It is in the setup checklist (RasQberry Setup icon, or RasQberry Configuration -> Setup Checklist)."
    fi
    return 0
}

# ============================================================================
# MAIN
# ============================================================================
main() {
    activate_venv >/dev/null 2>&1 || warn "venv not active; probes may fail if hardware libs are missing"

    # The on-screen LED view shows each logo in the layout it is drawn
    # through, while this check runs (rq_led_wizard_probe.py tell_views)
    export RQ_LED_VIEW_OWNER="$$"

    # The LED panel check (setup checklist, LED menu)
    if [ "${1:-}" = "--verify" ]; then
        verify_layout
        return 0
    fi

    local mode
    mode=$(ask_menu "LED Setup Wizard" "What do you want to do?" \
        setup      "Find the layout of my LED panel and save it" \
        diagnostic "Only check the wiring (saves nothing)") || return 0

    step_safety || { echo "Cancelled. Nothing was saved."; return 0; }

    # Probes light patterns and ask what the operator sees; route them through
    # the persistent renderer so each pattern stays lit while they answer (fix
    # F1). Torn down by cleanup() on exit.
    start_render_hold

    SETUP_SAVED=false
    SKIPPED=false
    run_identification "${mode}"
    return 0
}

main "$@"
