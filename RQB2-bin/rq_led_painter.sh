#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_painter.sh - RasQberry LED Painter Demo Launcher
#
# Description:
#   Installs and launches the LED Painter demonstration
#   Allows users to paint images on a GUI and display them on the LED array
#   Uses standardized installation approach
#
# Usage:
#   rq_led_painter.sh              install if needed (asks first), then start
#   rq_led_painter.sh --path DIR   set up a downloaded checkout, do not start
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

rq_help_guard "$@"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV GIT_REPO_DEMO_LED_PAINTER MARKER_LED_PAINTER

DEMO_NAME="LED-Painter"
MARKER="$MARKER_LED_PAINTER"

# The manifest is the single source of truth for WHERE the demo lives and WHICH
# upstream commit it is pinned to. This launcher is both a standalone entry point
# (desktop icon, raspi-config menu) and rq_demo_run.sh's delegate, so reading the
# same manifest keeps the two paths on ONE checkout. Hardcoding a directory here
# forked them: the engine installed the pinned tree to the manifest's working_dir
# while this script cloned an unpinned second copy elsewhere, and the unpinned one
# was what actually ran - silently voiding the pin.
MANIFEST_FILE=$(rq_find_manifest "/usr/config/demo-manifests" "led-painter" \
    || echo "$(dirname "$SCRIPT_DIR")/RQB2-config/demo-manifests/rq_demo_led-painter.json")

manifest_field() {
    local val=""
    [ -f "$MANIFEST_FILE" ] && val=$(jq -r "$1 // empty" "$MANIFEST_FILE" 2>/dev/null)
    [ -n "$val" ] && echo "$val" || echo "$2"
}

# Fall back to the upstream repo name (the demo-directory convention) if the
# manifest is unreadable, so a broken manifest cannot resurrect the old fork.
DEMO_DIR=$(get_demo_dir "$(manifest_field '.entrypoint.working_dir' 'RasQberry-Two-LED-Painter')")
DEMO_REF=$(manifest_field '.install.ref' '')
DEMO_URL=$(manifest_field '.install.repo_url' "$GIT_REPO_DEMO_LED_PAINTER")

################################################################################
# check_and_install_demo - Install LED Painter with all dependencies
#
# Uses inline version of install_demo() pattern for standalone launcher context
################################################################################
################################################################################
# link_system_pyqt5 - make Raspberry Pi OS's PyQt5 importable from the venv
#
# The GUI runs on the system PyQt5 (python3-pyqt5), not on PySide6 from pip:
# PySide6's wheels bundle a Qt that crashes with a bus error on the Pi 5 kernel
# (16 KB pages), #302. The image build links it (03-install-qiskit); this covers
# images built before that.
################################################################################
link_system_pyqt5() {
    local venv_py="$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" site dist
    [ -x "$venv_py" ] || return 1
    "$venv_py" -c "import PyQt5.QtWidgets" 2>/dev/null && return 0
    dist=/usr/lib/python3/dist-packages
    [ -d "$dist/PyQt5" ] || { warn "python3-pyqt5 is not installed (sudo apt-get install python3-pyqt5)"; return 1; }
    site=$("$venv_py" -c "import site; print(site.getsitepackages()[0])")
    info "Linking the system PyQt5 into the venv..."
    sudo ln -sfn "$dist/PyQt5" "$site/PyQt5"
    for meta in "$dist"/PyQt5-*.dist-info "$dist"/PyQt5_sip-*.egg-info; do
        [ -e "$meta" ] && sudo ln -sfn "$meta" "$site/"
    done
    "$venv_py" -c "import PyQt5.QtWidgets" 2>/dev/null
}

# Find the PWM/PIO + PyQt5 conversion script (shipped copy, else the checkout)
find_convert_script() {
    local c
    for c in "/usr/config/demo-patches/led-painter-convert-to-pwm.py" \
             "$USER_HOME/$REPO/RQB2-config/demo-patches/led-painter-convert-to-pwm.py"; do
        [ -f "$c" ] && { echo "$c"; return 0; }
    done
    return 1
}

# Convert the checkout in DEMO_DIR from SPI to the PWM/PIO drivers (shared
# NeoPixel object) and its GUI from PySide6 to the system PyQt5 (#302).
# Works on a fresh checkout and on one converted before #302.
convert_checkout() {
    local convert_script
    convert_script=$(find_convert_script) || { warn "Conversion script not found (demo may use incompatible SPI drivers)"; return 1; }
    info "Converting to PWM/PIO drivers and PyQt5..."
    if python3 "$convert_script" "$DEMO_DIR" > /dev/null 2>&1 \
        && grep -q "from PyQt5" "$DEMO_DIR/LED_painter.py" 2>/dev/null \
        && grep -q "_rq_canvas_rect" "$DEMO_DIR/LED_painter.py" 2>/dev/null; then
        info "Converted to PWM/PIO drivers (Pi 4/Pi 5) and PyQt5"
        return 0
    fi
    warn "Could not convert LED Painter"
    return 1
}

# Install the Python requirements of the converted checkout into the venv
install_requirements() {
    info "Installing Python dependencies (this may take several minutes)..."
    [ -d "$USER_HOME/$REPO/venv/$STD_VENV" ] \
        || die "Virtual environment not found at $USER_HOME/$REPO/venv/$STD_VENV"
    local venv_pip="$USER_HOME/$REPO/venv/$STD_VENV/bin/pip3" pip_exit=0
    [ -f "$DEMO_DIR/requirements.txt" ] || return 0
    if [ "$(id -u)" -eq 0 ]; then
        "$venv_pip" install -r "$DEMO_DIR/requirements.txt" || pip_exit=$?
    elif sudo -n true 2>/dev/null; then
        sudo "$venv_pip" install -r "$DEMO_DIR/requirements.txt" || pip_exit=$?
    else
        "$venv_pip" install -r "$DEMO_DIR/requirements.txt" || pip_exit=$?
    fi
    [ "$pip_exit" -eq 0 ] || die "Failed to install Python dependencies"
}

# Fetch the pinned checkout (first install; asks first, one dialog with size)
fetch_checkout() {
    rq_require_demo_consent led-painter "$MANIFEST_FILE"
    info "Installing $DEMO_NAME..."
    mkdir -p "$(dirname "$DEMO_DIR")"
    rq_remove_tree "$DEMO_DIR" || die "Cannot remove the old checkout: $DEMO_DIR"
    # LED-Painter is third-party (Luka-D), and we rewrite its driver code
    # post-checkout, so tracking a moving HEAD would let an upstream commit
    # break the conversion.
    if [ -n "$DEMO_REF" ]; then
        info "Fetching pinned commit $DEMO_REF ..."
        fetch_pinned_repo "$DEMO_URL" "$DEMO_REF" "$DEMO_DIR" \
            || die "Failed to fetch pinned commit $DEMO_REF for $DEMO_NAME"
    else
        info "Cloning $DEMO_NAME repository (unpinned)..."
        clone_demo "$DEMO_URL" "$DEMO_DIR"
    fi
    if [ "$(id -u)" = "0" ] && [ "$(get_user_name)" != "root" ]; then
        chown -R "$(get_user_name):" "$DEMO_DIR" 2>/dev/null || true
    fi
}

# Installed = checkout present AND already ported to PyQt5. A checkout the
# demo engine just fetched, or one converted before #302 (still PySide6, a bus
# error on the Pi 5), is converted in place - it used to be downloaded a
# second time on every first start (R-138).
check_and_install_demo() {
    link_system_pyqt5 || warn "PyQt5 not available in the venv - the painter window cannot open"

    # (and with the canvas below the menu bar: an older conversion is
    # converted again, in place)
    if [ -f "$DEMO_DIR/$MARKER" ] && grep -q "from PyQt5" "$DEMO_DIR/LED_painter.py" 2>/dev/null \
            && grep -q "_rq_canvas_rect" "$DEMO_DIR/LED_painter.py" 2>/dev/null; then
        debug "LED Painter already installed (PyQt5)"
        return 0
    fi
    [ -f "$DEMO_DIR/$MARKER" ] || fetch_checkout
    if ! convert_checkout; then
        # The checkout may be damaged: start again from the pinned commit
        fetch_checkout
        convert_checkout || die "Could not convert LED Painter for this Pi"
    fi
    install_requirements
    update_env_var "LED_PAINTER_INSTALLED" "true" || true
    info "$DEMO_NAME installed successfully!"
}

################################################################################
# Main execution
################################################################################

# --path DIR: set up a checkout the demo engine has just fetched (its
# install.post_install), then stop - "Download all demos" leaves LED-Painter
# ready to start offline.
if [ "${1:-}" = "--path" ]; then
    [ -n "${2:-}" ] || die "--path needs the checkout directory"
    DEMO_DIR="$2"
    check_and_install_demo
    exit 0
fi

# Check and install if needed
check_and_install_demo

# Find virtual environment python (required for PyQt5, qiskit, etc.)
VENV_PATH=$(find_venv "$STD_VENV") || die "Virtual environment '$STD_VENV' not found"
VENV_PYTHON="$VENV_PATH/bin/python3"

# Verify venv python exists
[ -x "$VENV_PYTHON" ] || die "Virtual environment python not found: $VENV_PYTHON"

# Launch LED-Painter
info "Starting $DEMO_NAME..."
cd "$DEMO_DIR" || die "Failed to change to demo directory"

# A graphical session is required - Wayland (labwc, the default) or X.
if [ -z "${WAYLAND_DISPLAY:-}" ] && ! check_display; then
    die "No graphical session (neither WAYLAND_DISPLAY nor DISPLAY is set). $DEMO_NAME requires a desktop."
fi

# LED-Painter draws the matrix in-process (LED_painter.py imports display_to_LEDs
# -> get_pixels), so under the default direct mode the GUI itself would need root
# for GPIO. But a root Qt GUI cannot attach to the user's Wayland session
# ("qt.qpa.xcb: could not connect to display :0"); Qt then falls back to the
# offscreen platform and the painter window never appears (plan #11 sec 2.7).
#
# Instead: run the GUI as the UNPRIVILEGED user - where Wayland works - and let
# the root renderer own the GPIO. With LED_RENDER_MODE=service, get_pixels()
# writes frames to the shared-memory bus and rasqberry-led-renderer.service turns
# them into GPIO. Rig-verified: visible GUI on Wayland + correct strip output.
USER_NAME=$(get_user_name)
USER_UID=$(id -u "$USER_NAME" 2>/dev/null || echo 1000)

# Another program on the LED panel? Name it and offer to stop it, with the
# dialog of the other LED demos (R-162): next to it the renderer cannot drive
# the panel (#6). Only root sees the other programs, and the painter itself
# runs as the desktop user.
if [ "$(id -u)" -eq 0 ]; then
    led_panel_ready || exit 0
elif sudo -n true 2>/dev/null; then
    sudo -n env LED_RENDER_MODE="${LED_RENDER_MODE:-direct}" \
        bash -c '. "$1" && led_panel_ready' _ "$SCRIPT_DIR/rq_common.sh" || exit 0
fi

# Bring up the root GPIO writer, unless the system already runs in service mode
# (a renderer is then already active and owns the strip - leave it alone).
RENDERER_STARTED=0
if [ "${LED_RENDER_MODE:-direct}" != "service" ]; then
    if sudo systemctl start rasqberry-led-renderer 2>/dev/null; then
        RENDERER_STARTED=1
        debug "Started rasqberry-led-renderer for this painter session"
    fi
fi

# Is the renderer still running a moment later? One that cannot open the
# panel's driver stops at once (and systemd tries again every 2 s).
renderer_running() {
    for _ in 1 2; do
        sleep 1
        systemctl is-active --quiet rasqberry-led-renderer 2>/dev/null || return 1
    done
}
# Without it the panel stayed dark and nothing said why (#6)
renderer_running \
    || echo "The LED panel stays dark: the LED renderer did not start (details: journalctl -u rasqberry-led-renderer)."

stop_renderer() {
    [ "$RENDERER_STARTED" = "1" ] || return 0
    # SIGTERM via systemd makes the renderer blank the strip before exiting.
    sudo systemctl stop rasqberry-led-renderer 2>/dev/null || true
}
trap stop_renderer EXIT

# Never run the Qt GUI as root: it cannot reach the user's Wayland compositor.
# `env` sets the vars explicitly so they survive sudo's env_reset policy.
# Closing the painter window, or Enter or Ctrl+C here, stops it (items 4, 8).
# Without Qt's harmless "QStandardPaths: wrong permissions" line (#27).
AS_USER=()
[ "$(id -u)" -eq 0 ] && AS_USER=(sudo -u "$USER_NAME" -H --)
rq_run_demo "$DEMO_NAME" rq_quiet_stderr ${AS_USER[@]+"${AS_USER[@]}"} env \
    LED_RENDER_MODE=service \
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_UID}" \
    DISPLAY="${DISPLAY:-:0}" \
    "$VENV_PYTHON" LED_painter.py

exit 0