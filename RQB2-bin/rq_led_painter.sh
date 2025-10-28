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
verify_env_vars REPO USER_HOME STD_VENV GIT_REPO_DEMO_LED_PAINTER MARKER_LED_PAINTER PATCH_FILE_LED_PAINTER

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

    # Apply RasQberry customization patch
    # Try both locations: /usr/config (on fresh image) and ~/RasQberry-Two (after git clone)
    PATCH_PATH=""
    if [ -n "$PATCH_FILE_LED_PAINTER" ]; then
        if [ -f "/usr/config/demo-patches/$PATCH_FILE_LED_PAINTER" ]; then
            PATCH_PATH="/usr/config/demo-patches/$PATCH_FILE_LED_PAINTER"
        elif [ -f "$USER_HOME/$REPO/RQB2-config/demo-patches/$PATCH_FILE_LED_PAINTER" ]; then
            PATCH_PATH="$USER_HOME/$REPO/RQB2-config/demo-patches/$PATCH_FILE_LED_PAINTER"
        fi
    fi

    if [ -n "$PATCH_PATH" ]; then
        info "Applying RasQberry customizations..."
        cd "$DEMO_DIR" || die "Failed to cd to demo directory"
        if patch -p1 < "$PATCH_PATH" > /dev/null 2>&1; then
            info "✓ Applied RasQberry customizations (chunked LED writes for 192+ LEDs)"
        else
            warn "Could not apply customization patch (demo may not work with 192+ LEDs)"
        fi
        cd - > /dev/null || true
    fi

    # Apply GPIO busy fix (persistent NeoPixel object)
    GPIO_FIX_SCRIPT=""
    if [ -f "/usr/config/demo-patches/led-painter-fix-gpio-busy.py" ]; then
        GPIO_FIX_SCRIPT="/usr/config/demo-patches/led-painter-fix-gpio-busy.py"
    elif [ -f "$USER_HOME/$REPO/RQB2-config/demo-patches/led-painter-fix-gpio-busy.py" ]; then
        GPIO_FIX_SCRIPT="$USER_HOME/$REPO/RQB2-config/demo-patches/led-painter-fix-gpio-busy.py"
    fi

    if [ -n "$GPIO_FIX_SCRIPT" ] && [ -f "$DEMO_DIR/display_to_LEDs_from_file.py" ]; then
        info "Applying GPIO busy fix..."
        if python3 "$GPIO_FIX_SCRIPT" "$DEMO_DIR/display_to_LEDs_from_file.py" > /dev/null 2>&1; then
            info "✓ Applied GPIO busy fix (persistent NeoPixel object)"
        else
            warn "Could not apply GPIO busy fix (multiple displays may fail)"
        fi
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

# Check if display is available
if ! check_display; then
    die "DISPLAY not set. $DEMO_NAME requires a graphical environment"
fi

# Run with sudo (required for PWM/PIO LED control on GPIO)
# Preserve DISPLAY for Qt/PySide6 GUI
# Note: PWM/PIO drivers require root access, unlike old SPI driver
if [ "$(id -u)" -eq 0 ]; then
    # Already root
    DISPLAY="${DISPLAY:-:0}" "$VENV_PYTHON" LED_painter.py
else
    # Need sudo for GPIO access
    sudo DISPLAY="${DISPLAY:-:0}" "$VENV_PYTHON" LED_painter.py
fi

exit 0