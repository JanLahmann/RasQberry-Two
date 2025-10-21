#!/bin/bash
# RasQberry: Launch LED-Painter Demo
# Allows users to paint images on a GUI and display them on the LED array

# Source environment configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
else
    echo "Error: Environment configuration not found"
    exit 1
fi

DEMO_NAME="LED-Painter"
DEMO_DIR="$USER_HOME/$REPO/demos/led-painter"
GIT_URL="${GIT_REPO_DEMO_LED_PAINTER:-https://github.com/Luka-D/RasQberry-Two-LED-Painter.git}"

# Function to check and install demo if needed
check_and_install_demo() {
    # Check if demo is already installed with all dependencies
    if [ -d "$DEMO_DIR" ] && [ -f "$DEMO_DIR/LED_painter.py" ]; then
        # Verify PySide6 is actually installed in the venv
        if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" ]; then
            if "$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" -c "import PySide6" 2>/dev/null; then
                return 0
            fi
            echo "Demo directory exists but dependencies are missing. Reinstalling..."
        fi
    fi

    # Demo not installed - show confirmation dialog
    if command -v whiptail &> /dev/null; then
        whiptail --title "$DEMO_NAME Not Installed" \
                 --yesno "$DEMO_NAME is not installed yet.\n\nThis will download ~5MB from GitHub and install ~500MB of dependencies (PySide6).\n\nRequires internet connection.\n\nInstall now?" \
                 14 65 3>&1 1>&2 2>&3

        if [ $? -ne 0 ]; then
            echo "Installation cancelled by user."
            exit 0
        fi
    else
        # Fallback if whiptail not available
        echo "$DEMO_NAME is not installed."
        echo "This requires downloading from GitHub and installing dependencies."
        read -p "Install now? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            exit 0
        fi
    fi

    # Install demo
    echo "Installing $DEMO_NAME..."

    # Create demos directory if it doesn't exist
    mkdir -p "$(dirname "$DEMO_DIR")"

    # Clone repository
    if ! git clone --depth 1 "$GIT_URL" "$DEMO_DIR"; then
        if command -v whiptail &> /dev/null; then
            whiptail --title "Installation Failed" \
                     --msgbox "Failed to download $DEMO_NAME.\n\nPlease check:\n- Internet connection\n- GitHub access\n\nError: git clone failed" \
                     12 60
        else
            echo "Error: Failed to clone $DEMO_NAME repository."
            echo "Please check your internet connection and try again."
        fi
        exit 1
    fi

    # Install system dependencies
    echo "Installing system dependencies..."
    if ! dpkg -l | grep -q libxcb-cursor-dev; then
        if command -v whiptail &> /dev/null; then
            whiptail --title "Installing Dependencies" \
                     --msgbox "Installing system package: libxcb-cursor-dev\n\nThis requires sudo privileges." \
                     10 60
        fi

        if ! sudo apt-get install -y libxcb-cursor-dev; then
            if command -v whiptail &> /dev/null; then
                whiptail --title "Installation Failed" \
                         --msgbox "Failed to install system dependencies.\n\nPlease run manually:\nsudo apt-get install libxcb-cursor-dev" \
                         10 60
            fi
            exit 1
        fi
    fi

    # Install Python dependencies
    echo "Installing Python dependencies (this may take several minutes)..."

    # Verify virtual environment exists and variables are set
    if [ -z "$REPO" ] || [ -z "$STD_VENV" ]; then
        echo "Error: Environment variables not properly loaded (REPO=$REPO, STD_VENV=$STD_VENV)"
        if command -v whiptail &> /dev/null; then
            whiptail --title "Configuration Error" \
                     --msgbox "Environment configuration not properly loaded.\n\nPlease check /usr/config/rasqberry_env-config.sh" \
                     10 60
        fi
        exit 1
    fi

    if [ ! -d "$USER_HOME/$REPO/venv/$STD_VENV" ]; then
        echo "Error: Virtual environment not found at $USER_HOME/$REPO/venv/$STD_VENV"
        if command -v whiptail &> /dev/null; then
            whiptail --title "Virtual Environment Missing" \
                     --msgbox "Virtual environment not found.\n\nExpected: $USER_HOME/$REPO/venv/$STD_VENV" \
                     10 60
        fi
        exit 1
    fi

    # Use venv's pip directly (no need to activate in subshell)
    VENV_PIP="$USER_HOME/$REPO/venv/$STD_VENV/bin/pip3"

    if command -v whiptail &> /dev/null; then
        # Show info box (no progress bar since pip doesn't provide progress)
        whiptail --title "Installing Python Dependencies" \
                 --infobox "Installing PySide6 and dependencies...\n\nThis may take 5-10 minutes.\nPlease wait..." \
                 8 60

        # Install using venv's pip with sudo (venv is owned by root from build)
        # Use pipefail to catch pip errors even when piping to tee
        (
            set -o pipefail
            cd "$DEMO_DIR"
            sudo "$VENV_PIP" install -r requirements.txt 2>&1 | tee /tmp/led-painter-install.log
        )
        PIP_EXIT=$?
    else
        (
            cd "$DEMO_DIR"
            sudo "$VENV_PIP" install -r requirements.txt
        )
        PIP_EXIT=$?
    fi

    if [ $PIP_EXIT -eq 0 ]; then
        # Update environment flag (check both user and system config locations)
        for env_file in "/usr/config/rasqberry_environment.env" "$USER_HOME/.local/config/rasqberry_environment.env"; do
            if [ -f "$env_file" ]; then
                sed -i 's/LED_PAINTER_INSTALLED=false/LED_PAINTER_INSTALLED=true/' "$env_file"
            fi
        done

        if command -v whiptail &> /dev/null; then
            whiptail --title "Installation Complete" \
                     --msgbox "$DEMO_NAME has been installed successfully!\n\nLaunching now..." \
                     10 50
        else
            echo "$DEMO_NAME installed successfully!"
        fi
        return 0
    else
        if command -v whiptail &> /dev/null; then
            whiptail --title "Installation Failed" \
                     --msgbox "Failed to install Python dependencies.\n\nCheck log: /tmp/led-painter-install.log" \
                     10 60
        fi
        exit 1
    fi
}

# Check and install if needed
check_and_install_demo

# Activate virtual environment
if [ -d "$USER_HOME/$REPO/venv/$STD_VENV" ]; then
    source "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# Launch LED-Painter
echo "Starting $DEMO_NAME..."
cd "$DEMO_DIR"

# Check if display is available
if [ -z "$DISPLAY" ]; then
    if command -v whiptail &> /dev/null; then
        whiptail --title "Display Required" \
                 --msgbox "$DEMO_NAME requires a graphical display.\n\nPlease run from desktop environment or enable X11 forwarding." \
                 10 60
    else
        echo "Error: DISPLAY not set. $DEMO_NAME requires a graphical environment."
    fi
    exit 1
fi

# Run the LED-Painter using venv python
"$USER_HOME/$REPO/venv/$STD_VENV/bin/python3" LED_painter.py

exit 0
