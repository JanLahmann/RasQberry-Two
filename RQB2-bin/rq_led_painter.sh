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

    # Demo not installed - ask user for confirmation
    if ! show_yesno "$DEMO_NAME Not Installed" \
        "$DEMO_NAME is not installed yet.\n\nThis will download from GitHub and install dependencies (PySide6).\n\nRequires internet connection.\n\nInstall now?"; then
        info "Installation cancelled by user"
        exit 0
    fi

    # Install demo
    info "Installing $DEMO_NAME..."

    # Create demos directory if it doesn't exist
    mkdir -p "$(dirname "$DEMO_DIR")"

    # Clone repository
    if ! git clone --depth 1 "$GIT_REPO_DEMO_LED_PAINTER" "$DEMO_DIR" 2>&1 | tee /tmp/led-painter-clone.log; then
        show_msgbox "Installation Failed" "Failed to download $DEMO_NAME.\n\nPlease check:\n- Internet connection\n- GitHub access\n\nError: git clone failed"
        die "Failed to clone $DEMO_NAME repository"
    fi

    # Fix ownership if cloned as root
    if [ "$(stat -c '%U' "$DEMO_DIR" 2>/dev/null || stat -f '%Su' "$DEMO_DIR")" = "root" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        chown -R "$SUDO_USER":"$SUDO_USER" "$DEMO_DIR" 2>/dev/null || true
    fi

    # Apply RasQberry customization patch
    if [ -n "$PATCH_FILE_LED_PAINTER" ] && [ -f "$USER_HOME/$REPO/RQB2-config/demo-patches/$PATCH_FILE_LED_PAINTER" ]; then
        info "Applying RasQberry customizations..."
        cd "$DEMO_DIR" || die "Failed to cd to demo directory"
        if patch -p1 < "$USER_HOME/$REPO/RQB2-config/demo-patches/$PATCH_FILE_LED_PAINTER" > /dev/null 2>&1; then
            info "✓ Applied RasQberry customizations (chunked LED writes for 192+ LEDs)"
        else
            warn "Could not apply customization patch (demo may not work with 192+ LEDs)"
        fi
        cd - > /dev/null || true
    fi

    # Install Python dependencies
    info "Installing Python dependencies (this may take several minutes)..."

    # Verify virtual environment exists
    if [ ! -d "$USER_HOME/$REPO/venv/$STD_VENV" ]; then
        show_msgbox "Virtual Environment Missing" "Virtual environment not found.\n\nExpected: $USER_HOME/$REPO/venv/$STD_VENV"
        die "Virtual environment not found at $USER_HOME/$REPO/venv/$STD_VENV"
    fi

    # Use venv's pip directly
    VENV_PIP="$USER_HOME/$REPO/venv/$STD_VENV/bin/pip3"

    # Show info message
    show_infobox "Installing Python Dependencies" "Installing PySide6 and dependencies...\n\nThis may take 5-10 minutes.\nPlease wait..."

    # Install using venv's pip
    # (venv is owned by root from build, so use sudo if we're root or have sudo privileges)
    cd "$DEMO_DIR" || die "Failed to cd to demo directory"
    local pip_cmd="$VENV_PIP install -r requirements.txt"
    local pip_exit=0

    if [ "$(id -u)" -eq 0 ]; then
        # Already root, run directly
        $pip_cmd > /tmp/led-painter-install.log 2>&1 || pip_exit=$?
    elif sudo -n true 2>/dev/null; then
        # Have sudo privileges
        sudo $pip_cmd > /tmp/led-painter-install.log 2>&1 || pip_exit=$?
    else
        # No sudo, try without
        $pip_cmd > /tmp/led-painter-install.log 2>&1 || pip_exit=$?
    fi
    cd - > /dev/null || true

    if [ $pip_exit -eq 0 ]; then
        # Update environment flag
        update_env_var "LED_PAINTER_INSTALLED" "true"
        show_msgbox "Installation Complete" "$DEMO_NAME has been installed successfully!\n\nLaunching now..."
        info "$DEMO_NAME installed successfully!"
        return 0
    else
        show_msgbox "Installation Failed" "Failed to install Python dependencies.\n\nCheck log: /tmp/led-painter-install.log"
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
    show_msgbox "Display Required" "$DEMO_NAME requires a graphical display.\n\nPlease run from desktop environment or enable X11 forwarding."
    die "DISPLAY not set. $DEMO_NAME requires a graphical environment"
fi

# Run as actual user (not root) to avoid GUI/display permission issues
# When launched from raspi-config, this ensures Qt/PySide6 can access the user's display
# Use full path to venv python so it has access to PySide6, qiskit, etc.
run_as_user "$VENV_PYTHON" LED_painter.py

exit 0