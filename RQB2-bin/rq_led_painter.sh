#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_painter.sh - RasQberry LED Painter Demo Launcher
#
# Description:
#   Installs and launches the LED Painter demonstration
#   Allows users to paint images on a GUI and display them on the LED array
#   Uses standardized installation approach with chunked LED write support
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV GIT_REPO_DEMO_LED_PAINTER MARKER_LED_PAINTER

DEMO_NAME="LED-Painter"
DEMO_DIR="$USER_HOME/$REPO/demos/led-painter"
MARKER="$MARKER_LED_PAINTER"

################################################################################
# check_and_install_demo - Install LED Painter with all dependencies
#
# Uses inline version of install_demo() pattern for standalone launcher context
################################################################################
check_and_install_demo() {
    # Check if already installed
    if [ -f "$DEMO_DIR/$MARKER" ]; then
        # Verify PySide6 is actually installed in the venv
        if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" ]; then
            if "$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" -c "import PySide6" 2>/dev/null; then
                debug "LED Painter already installed with all dependencies"
                return 0
            fi
            info "Demo directory exists but dependencies are missing. Reinstalling..."
        fi
    fi

    # Demo not installed - auto-install without prompting
    # Desktop icons and automated launchers don't have interactive terminals
    info "Installing $DEMO_NAME..."

    # Create demos directory if it doesn't exist
    mkdir -p "$(dirname "$DEMO_DIR")"

    # Clone repository
    info "Cloning $DEMO_NAME repository..."
    if ! git clone --depth 1 "$GIT_REPO_DEMO_LED_PAINTER" "$DEMO_DIR" 2>&1; then
        die "Failed to clone $DEMO_NAME repository"
    fi

    # Fix ownership if cloned as root
    if [ "$(stat -c '%U' "$DEMO_DIR" 2>/dev/null || stat -f '%Su' "$DEMO_DIR")" = "root" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        chown -R "$SUDO_USER":"$SUDO_USER" "$DEMO_DIR" 2>/dev/null || true
    fi

    # Convert LED-Painter from SPI to PWM/PIO drivers with persistent NeoPixel object
    # This replaces the old patch + GPIO fix approach with a comprehensive conversion script
    CONVERT_SCRIPT=""
    if [ -f "/usr/config/demo-patches/led-painter-convert-to-pwm.py" ]; then
        CONVERT_SCRIPT="/usr/config/demo-patches/led-painter-convert-to-pwm.py"
    elif [ -f "$USER_HOME/$REPO/RQB2-config/demo-patches/led-painter-convert-to-pwm.py" ]; then
        CONVERT_SCRIPT="$USER_HOME/$REPO/RQB2-config/demo-patches/led-painter-convert-to-pwm.py"
    fi

    if [ -n "$CONVERT_SCRIPT" ]; then
        info "Converting to PWM/PIO drivers..."
        if python3 "$CONVERT_SCRIPT" "$DEMO_DIR" > /dev/null 2>&1; then
            info "✓ Converted to PWM/PIO drivers (Pi 4/Pi 5 compatible)"
            info "✓ Applied persistent NeoPixel object (prevents GPIO busy errors)"
        else
            warn "Could not convert to PWM/PIO drivers (demo may not work)"
        fi
    else
        warn "Conversion script not found (demo may use incompatible SPI drivers)"
    fi

    # Install Python dependencies
    info "Installing Python dependencies (this may take several minutes)..."

    # Verify virtual environment exists
    if [ ! -d "$USER_HOME/$REPO/venv/$STD_VENV" ]; then
        die "Virtual environment not found at $USER_HOME/$REPO/venv/$STD_VENV"
    fi

    # Use venv's pip directly
    VENV_PIP="$USER_HOME/$REPO/venv/$STD_VENV/bin/pip3"

    # Install using venv's pip
    # (venv is owned by root from build, so use sudo if we're root or have sudo privileges)
    cd "$DEMO_DIR" || die "Failed to cd to demo directory"
    local pip_exit=0

    if [ "$(id -u)" -eq 0 ]; then
        # Already root, run directly
        $VENV_PIP install -r requirements.txt || pip_exit=$?
    elif sudo -n true 2>/dev/null; then
        # Have sudo privileges
        sudo $VENV_PIP install -r requirements.txt || pip_exit=$?
    else
        # No sudo, try without
        $VENV_PIP install -r requirements.txt || pip_exit=$?
    fi
    cd - > /dev/null || true

    if [ $pip_exit -eq 0 ]; then
        # Update environment flag
        update_env_var "LED_PAINTER_INSTALLED" "true"
        info "$DEMO_NAME installed successfully!"
        return 0
    else
        die "Failed to install Python dependencies"
    fi
}

################################################################################
# Main execution
################################################################################

# Check and install if needed
check_and_install_demo

# Find virtual environment python (required for PySide6, qiskit, etc.)
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

# Bring up the root GPIO writer, unless the system already runs in service mode
# (a renderer is then already active and owns the strip - leave it alone).
RENDERER_STARTED=0
if [ "${LED_RENDER_MODE:-direct}" != "service" ]; then
    if sudo systemctl start rasqberry-led-renderer 2>/dev/null; then
        RENDERER_STARTED=1
        debug "Started rasqberry-led-renderer for this painter session"
    else
        warn "Could not start the LED renderer - the GUI will run but the strip may stay dark"
    fi
fi

stop_renderer() {
    [ "$RENDERER_STARTED" = "1" ] || return 0
    # SIGTERM via systemd makes the renderer blank the strip before exiting.
    sudo systemctl stop rasqberry-led-renderer 2>/dev/null || true
}
trap stop_renderer EXIT

# Never run the Qt GUI as root: it cannot reach the user's Wayland compositor.
# `env` sets the vars explicitly so they survive sudo's env_reset policy.
if [ "$(id -u)" -eq 0 ]; then
    sudo -u "$USER_NAME" -H -- env \
        LED_RENDER_MODE=service \
        WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
        XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_UID}" \
        DISPLAY="${DISPLAY:-:0}" \
        "$VENV_PYTHON" LED_painter.py
else
    LED_RENDER_MODE=service \
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$USER_UID}" \
        "$VENV_PYTHON" LED_painter.py
fi

exit 0