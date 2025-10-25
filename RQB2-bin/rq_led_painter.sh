#!/bin/bash
set -euo pipefail

################################################################################
# rq_led_painter.sh - RasQberry LED Painter Demo Launcher
#
# Description:
#   Installs and launches the LED Painter demonstration
#   Allows users to paint images on a GUI and display them on the LED array
#   Handles dependency installation (system packages and Python packages)
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment and verify required variables
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

DEMO_NAME="LED-Painter"
DEMO_DIR="$USER_HOME/$REPO/demos/led-painter"
GIT_URL="${GIT_REPO_DEMO_LED_PAINTER:-https://github.com/Luka-D/RasQberry-Two-LED-Painter.git}"

################################################################################
# check_and_install_demo - Install LED Painter with all dependencies
#
# This function handles the complete installation process:
# 1. Checks if already installed with PySide6 dependency
# 2. Prompts user for installation
# 3. Clones the git repository
# 4. Installs system dependencies (libxcb-cursor-dev)
# 5. Installs Python dependencies (PySide6, etc.)
# 6. Updates environment flags
################################################################################
check_and_install_demo() {
    # Check if demo is already installed with all dependencies
    if [ -d "$DEMO_DIR" ] && [ -f "$DEMO_DIR/LED_painter.py" ]; then
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
        "$DEMO_NAME is not installed yet.\n\nThis will download ~5MB from GitHub and install ~500MB of dependencies (PySide6).\n\nRequires internet connection.\n\nInstall now?"; then
        info "Installation cancelled by user"
        exit 0
    fi

    # Install demo
    info "Installing $DEMO_NAME..."

    # Create demos directory if it doesn't exist
    mkdir -p "$(dirname "$DEMO_DIR")"

    # Clone repository
    if ! clone_demo "$GIT_URL" "$DEMO_DIR"; then
        show_msgbox "Installation Failed" "Failed to download $DEMO_NAME.\n\nPlease check:\n- Internet connection\n- GitHub access\n\nError: git clone failed"
        die "Failed to clone $DEMO_NAME repository"
    fi

    # Install system dependencies
    info "Installing system dependencies..."
    if ! dpkg -l | grep -q libxcb-cursor-dev; then
        show_msgbox "Installing Dependencies" "Installing system package: libxcb-cursor-dev\n\nThis requires sudo privileges."

        if ! sudo apt-get install -y libxcb-cursor-dev; then
            show_msgbox "Installation Failed" "Failed to install system dependencies.\n\nPlease run manually:\nsudo apt-get install libxcb-cursor-dev"
            die "Failed to install libxcb-cursor-dev"
        fi
    fi

    # Install Python dependencies
    info "Installing Python dependencies (this may take several minutes)..."

    # Verify virtual environment exists
    if [ ! -d "$USER_HOME/$REPO/venv/$STD_VENV" ]; then
        show_msgbox "Virtual Environment Missing" "Virtual environment not found.\n\nExpected: $USER_HOME/$REPO/venv/$STD_VENV"
        die "Virtual environment not found at $USER_HOME/$REPO/venv/$STD_VENV"
    fi

    # Use venv's pip directly (no need to activate in subshell)
    VENV_PIP="$USER_HOME/$REPO/venv/$STD_VENV/bin/pip3"

    # Show info box (no progress bar since pip doesn't provide progress)
    show_infobox "Installing Python Dependencies" "Installing PySide6 and dependencies...\n\nThis may take 5-10 minutes.\nPlease wait..."

    # Install using venv's pip with sudo (venv is owned by root from build)
    # Create log file with proper permissions first
    LOG_FILE="/tmp/led-painter-install-$$.log"
    touch "$LOG_FILE" 2>/dev/null || LOG_FILE="/dev/null"

    local pip_exit=0
    (
        cd "$DEMO_DIR"
        sudo "$VENV_PIP" install -r requirements.txt 2>&1 | tee "$LOG_FILE"
    ) || pip_exit=$?

    if [ $pip_exit -eq 0 ]; then
        # Update environment flag
        update_env_var "LED_PAINTER_INSTALLED" "true"

        show_msgbox "Installation Complete" "$DEMO_NAME has been installed successfully!\n\nLaunching now..."
        info "$DEMO_NAME installed successfully!"
        return 0
    else
        local log_msg="Failed to install Python dependencies."
        if [ -f "$LOG_FILE" ] && [ "$LOG_FILE" != "/dev/null" ]; then
            log_msg="$log_msg\n\nCheck log: $LOG_FILE"
        fi
        show_msgbox "Installation Failed" "$log_msg"
        die "Failed to install Python dependencies"
    fi
}

################################################################################
# Main execution
################################################################################

# Check and install if needed
check_and_install_demo

# Activate virtual environment
activate_venv || warn "Could not activate virtual environment, continuing anyway..."

# Launch LED-Painter
info "Starting $DEMO_NAME..."
cd "$DEMO_DIR" || die "Failed to change to demo directory"

# Check if display is available
if ! check_display; then
    show_msgbox "Display Required" "$DEMO_NAME requires a graphical display.\n\nPlease run from desktop environment or enable X11 forwarding."
    die "DISPLAY not set. $DEMO_NAME requires a graphical environment"
fi

# Run the LED-Painter using venv python
"$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" LED_painter.py

exit 0
