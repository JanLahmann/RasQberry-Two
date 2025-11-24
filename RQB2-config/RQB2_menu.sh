#!/bin/sh
# Note: removed set -eu to prevent raspi-config crashes from unset variables
IFS='\
	'

# -----------------------------------------------------------------------------
# RasQberry-Two: RQB2_menu.sh
# Table of Contents:
# 1. Environment & Bootstrap
# 2. Helpers
# 3. Menu Functions
#    a) Environment Variable Menu
#    b) Qiskit Install Menu
#    c) LED Demo Menu
#    d) Quantum Lights Out Menu
#    e) Quantum Raspberry-Tie Menu
#    f) Main Menu
# 4. Error Handling
# -----------------------------------------------------------------------------

# load RasQberry environment and constants with error handling
ENV_CONFIG_FILE="/usr/config/rasqberry_env-config.sh"
if [ -f "$ENV_CONFIG_FILE" ]; then
    . "$ENV_CONFIG_FILE"
else
    echo "Warning: RasQberry environment config not found at $ENV_CONFIG_FILE"
    # Set minimal defaults to prevent crashes
    USER_HOME="${USER_HOME:-/home/${SUDO_USER:-$USER}}"
    REPO="${REPO:-RasQberry-Two}"
    STD_VENV="${STD_VENV:-RQB2}"
    RQB2_CONFDIR="${RQB2_CONFDIR:-.local/config}"
fi

# Constants and reusable paths
REPO_DIR="$USER_HOME/$REPO"
DEMO_ROOT="$REPO_DIR/demos"
BIN_DIR="/usr/bin"  # System-wide bin directory (accessible to both root and normal users)
VENV_ACTIVATE="$REPO_DIR/venv/$STD_VENV/bin/activate"

#
# -----------------------------------------------------------------------------
# 1. Environment & Bootstrap
# -----------------------------------------------------------------------------
#
# Note: No longer need to create symlinks - all scripts are in /usr/bin

# -----------------------------------------------------------------------------
# 2. Helpers
# -----------------------------------------------------------------------------

# POSIX-compatible generic whiptail menu helper
show_menu() {
    title="$1"; shift
    prompt="$1"; shift
    whiptail --title "$title" --menu "$prompt" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" "$@" 3>&1 1>&2 2>&3
}

# Generic installer for demos: name, git URL, marker file, env var, dialog title, optional size
install_demo() {
    NAME="$1"           # demo directory name
    GIT_URL="$2"        # corresponding repo URL variable
    MARKER="$3"         # script or file that must exist
    ENV_VAR="$4"        # environment variable name to set
    TITLE="$5"          # title for dialog messages
    PATCH_FILE="$6"     # optional: patch file name for RasQberry customizations
    INSTALL_REQS="${7:-}"   # optional: "pip" to install requirements.txt (default empty)

    DEST="$DEMO_ROOT/$NAME"

    # Check if already installed
    if [ -f "$DEST/$MARKER" ]; then
        return 0  # Already installed
    fi

    # Show confirmation dialog before downloading (unless auto-install is enabled)
    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
        if command -v whiptail > /dev/null 2>&1; then
            whiptail --title "$TITLE Not Installed" \
                     --yesno "$TITLE is not installed yet.\n\nRequires internet connection.\n\nInstall now?" \
                     10 65 3>&1 1>&2 2>&3

            if [ $? -ne 0 ]; then
                # User cancelled installation
                return 1
            fi
        else
            # Fallback if whiptail not available (POSIX-compliant for dash)
            echo "$TITLE is not installed."
            echo "This requires downloading from GitHub."
            printf "Install now? (y/n) "
            read REPLY
            # POSIX case pattern matching (works in dash, unlike [[ =~ ]])
            case "$REPLY" in
                [Yy]|[Yy][Ee][Ss]) ;;  # Continue with installation
                *) return 1 ;;          # User declined
            esac
        fi
    else
        # Auto-install mode - proceed without prompting
        echo "Auto-installing $TITLE..."
    fi

    # Clone demo repository
    mkdir -p "$DEST"
    if git clone --depth 1 "$GIT_URL" "$DEST"; then
        # Fix ownership if cloned as root (when run from raspi-config)
        if [ "$(stat -c '%U' "$DEST")" = "root" ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
            chown -R "$SUDO_USER":"$SUDO_USER" "$DEST"
        fi

        # Apply RasQberry customization patch if specified
        # Try both locations: /usr/config (on fresh image) and ~/RasQberry-Two (after git clone)
        PATCH_PATH=""
        if [ -n "$PATCH_FILE" ]; then
            if [ -f "/usr/config/demo-patches/$PATCH_FILE" ]; then
                PATCH_PATH="/usr/config/demo-patches/$PATCH_FILE"
            elif [ -f "$REPO_DIR/RQB2-config/demo-patches/$PATCH_FILE" ]; then
                PATCH_PATH="$REPO_DIR/RQB2-config/demo-patches/$PATCH_FILE"
            fi
        fi

        if [ -n "$PATCH_PATH" ]; then
            echo "Applying RasQberry customizations..."
            cd "$DEST" || return 1
            if patch -p1 < "$PATCH_PATH" > /dev/null 2>&1; then
                echo "✓ Applied RasQberry customizations (PWM/PIO LED driver support)"
            else
                echo "Warning: Could not apply customization patch (demo may not work correctly)"
            fi
            cd - > /dev/null || true
        fi

        # Install Python dependencies if requested
        if [ "$INSTALL_REQS" = "pip" ] && [ -f "$DEST/requirements.txt" ]; then
            echo "Installing Python dependencies..."

            # Verify virtual environment exists
            if [ ! -d "$REPO_DIR/venv/$STD_VENV" ]; then
                whiptail --title "Error" --msgbox "Virtual environment not found at $REPO_DIR/venv/$STD_VENV" 8 70
                rm -rf "$DEST"
                return 1
            fi

            # Use venv's pip directly
            VENV_PIP="$REPO_DIR/venv/$STD_VENV/bin/pip3"

            # Show progress message
            if command -v whiptail > /dev/null 2>&1; then
                whiptail --title "Installing Dependencies" --infobox "Installing Python packages from requirements.txt...\n\nThis may take a few minutes.\nPlease wait..." 10 60
            fi

            # Install using venv's pip with sudo (venv is owned by root from build)
            cd "$DEST" || return 1
            if sudo "$VENV_PIP" install -r requirements.txt > /dev/null 2>&1; then
                echo "✓ Python dependencies installed successfully"
            else
                whiptail --title "Warning" --msgbox "Failed to install some Python dependencies.\n\nDemo may not work correctly." 10 60
            fi
            cd - > /dev/null || true
        fi

        update_environment_file "$ENV_VAR" "true"

        # Show success message (unless in auto-install mode)
        if [ "${RQ_AUTO_INSTALL:-0}" != "1" ] && [ "$RQ_NO_MESSAGES" = false ]; then
            whiptail --title "$TITLE" --msgbox "Demo installed successfully." 8 60
        else
            echo "✓ $TITLE installed successfully"
        fi
    else
        # Clean up empty directory and show error
        rm -rf "$DEST"

        # Show error message (unless in auto-install mode)
        if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
            whiptail --title "Installation Error" --msgbox "Failed to download $TITLE demo.\n\nPossible causes:\n- No internet connection\n- Repository unavailable\n- Network firewall blocking access\n\nPlease check your connection and try again." 12 70
        else
            echo "ERROR: Failed to download $TITLE demo"
        fi
        return 1
    fi
}

# Install Quantum-Lights-Out demo if needed
do_qlo_install() {
    install_demo "Quantum-Lights-Out" "$GIT_REPO_DEMO_QLO" \
                 "$MARKER_QLO" "QUANTUM_LIGHTS_OUT_INSTALLED" \
                 "Quantum Lights Out" "$PATCH_FILE_QLO"
}

# Install Quantum Raspberry-Tie demo if needed
do_rasp_tie_install() {
    install_demo "quantum-raspberry-tie" "$GIT_REPO_DEMO_QRT" \
                 "$MARKER_QRT" "QUANTUM_RASPBERRY_TIE_INSTALLED" \
                 "Quantum Raspberry-Tie" "$PATCH_FILE_QRT"
}

# Install Grok Bloch demo if needed
do_grok_bloch_install() {
    install_demo "grok-bloch" "$GIT_REPO_DEMO_GROK_BLOCH" \
                 "$MARKER_GROK_BLOCH" "GROK_BLOCH_INSTALLED" \
                 "Grok Bloch Sphere" ""
}

# LED-Painter installation is handled by rq_led_painter.sh
# (uses conversion script instead of patch file)

# Helper: run a demo in its directory using a pty for correct TTY behavior, or in background without pty
run_demo() {
  # Mode selection: default is pty; allow "bg" as first arg
  MODE="pty"
  if [ "$1" = bg ]; then MODE="bg"; shift; fi
  DEMO_TITLE="$1"; shift
  DEMO_DIR="$1"; shift
  # Build the command string from all remaining args (preserving spaces)
  CMD="$1"
  shift
  for arg in "$@"; do
      CMD="$CMD $arg"
  done
  # Ensure commands run inside the Python virtual environment
  if [ -f "$VENV_ACTIVATE" ]; then
    CMD=". \"$VENV_ACTIVATE\" && exec $CMD"
  fi
  # Save current terminal settings
  OLD_STTY=$(stty -g)
  # Reset terminal state before launching
  stty sane
  # Launch the demo in its own session so we can kill the full process group
  if [ "$MODE" = "pty" ]; then
      ( trap '' INT; cd "$DEMO_DIR" && exec setsid script -qfc "$CMD" /dev/null ) &
  else
      ( trap '' INT; cd "$DEMO_DIR" && exec setsid sh -c "$CMD" < /dev/null ) &
  fi
  DEMO_PID=$!
  LAST_DEMO_PGID="$DEMO_PID"
  # Ask user when to stop
  whiptail --title "${DEMO_TITLE}" --yesno "Demo is running. Select Yes to stop." 8 60
  RESPONSE=$?
  # Restore terminal state before killing demo
  stty sane
  # Terminate the entire demo process group only if user chose Yes
  if [ "$RESPONSE" -eq 0 ]; then
      kill -TERM -"$DEMO_PID" 2>/dev/null || true
      wait "$DEMO_PID" 2>/dev/null || true
  fi
  # Restore original terminal settings
  stty "$OLD_STTY"
  stty intr ^C
  # Final reset to clear any residual state
  reset
}

# Generic runner for Quantum-Lights-Out demo (POSIX sh compatible)
run_qlo_demo() {
    MODE="${1:-}"  # empty for GUI, "console" for console mode
    DEMO_DIR="$DEMO_ROOT/Quantum-Lights-Out"
    # Ensure installed
    do_qlo_install
    # Launch appropriate mode
    if [ "$MODE" = "console" ]; then
        run_demo "Quantum Lights Out Demo (console)" "$DEMO_DIR" python3 lights_out.py --console
    else
        run_demo "Quantum Lights Out Demo" "$DEMO_DIR" python3 lights_out.py
    fi
    # Turn off LEDs when demo ends
    do_led_off
}

# Run quantum-raspberry-tie demo (ensures install first)
run_rasp_tie_demo() {
    # Ensure installation
    do_rasp_tie_install
    DEMO_DIR="$DEMO_ROOT/quantum-raspberry-tie"
    RUN_OPTION=$1
    if  [ "$RUN_OPTION" != "b:aer" ]; then
      echo "For this option, we need a IBM Quantum Token"
      python3 "$BIN_DIR/rq_set_qiskit_ibm_token.py"
    fi
    run_demo "Quantum Raspberry-Tie Demo" "$DEMO_DIR" python3 "QuantumRaspberryTie.v7_1.py" "-${RUN_OPTION}"
    # Turn off LEDs when demo ends
    do_led_off
}

# Run grok-bloch demo local version (ensures install first)
run_grok_bloch_demo() {
    # Ensure installation
    do_grok_bloch_install || return 1

    # Launch the demo using the dedicated launcher script
    # (Script will check for DISPLAY and show appropriate error if needed)
    "$BIN_DIR/rq_grok_bloch.sh"
}

# Run grok-bloch web version (no installation needed)
run_grok_bloch_web_demo() {
    # Check if chromium-browser is available
    if ! command -v chromium-browser >/dev/null 2>&1; then
        whiptail --title "Browser Not Found" --msgbox \
            "Chromium browser is not installed.\n\nThe web version requires a web browser." \
            10 60
        return 1
    fi

    whiptail --title "Grok Bloch Sphere (Web)" --msgbox \
        "Opening the online version of Grok Bloch Sphere in your browser.\n\nURL: https://javafxpert.github.io/grok-bloch/\n\nPress OK to continue." \
        12 70

    # Launch browser with web version (as user if running as root)
    GROK_URL="https://javafxpert.github.io/grok-bloch/"
    if [ "$(whoami)" = "root" ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        su - "$SUDO_USER" -c "DISPLAY=${DISPLAY:-:0} chromium-browser --password-store=basic '$GROK_URL' >/dev/null 2>&1 &"
    else
        chromium-browser --password-store=basic "$GROK_URL" >/dev/null 2>&1 &
    fi
}

# Run quantum fractals demo
run_fractals_demo() {
    # Launch the fractals demo using the dedicated launcher script
    "$BIN_DIR/fractals.sh"
}

# Run LED-Painter demo
run_led_painter_demo() {
    # Launch the LED-Painter demo using the dedicated launcher script
    "$BIN_DIR/rq_led_painter.sh"
}

# Run RasQ-LED demo
run_rasq_led_demo() {
    # Launch the RasQ-LED quantum circuit demo directly
    run_demo "RasQ-LED Demo" "$BIN_DIR" python3 RasQ-LED.py
    # Turn off LEDs when demo ends
    do_led_off
}

# Run Qoffee-Maker demo
run_qoffee_demo() {
    # Check if setup has been run (Docker installed)
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Setup Required" --msgbox \
            "Qoffee-Maker requires Docker, which is not installed.\n\nSetup will now run to install Docker and configure Qoffee-Maker.\n\nNote: This requires internet connection and may take 5-10 minutes." \
            12 70
        "$BIN_DIR/qoffee-setup.sh" || return 1
    fi

    # Launch the Qoffee-Maker demo
    "$BIN_DIR/qoffee-maker.sh"
}

# Stop Qoffee-Maker containers
stop_qoffee_containers() {
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Docker Not Found" --msgbox "Docker is not installed. No containers to stop." 8 60
        return 0
    fi

    # Check if any qoffee containers are running
    if docker ps -q --filter name=qoffee 2>/dev/null | grep -q .; then
        echo "Stopping Qoffee-Maker containers..."
        docker stop $(docker ps -q --filter name=qoffee) 2>/dev/null || true
        whiptail --title "Qoffee-Maker Stopped" --msgbox "All Qoffee-Maker containers have been stopped." 8 60
    else
        whiptail --title "No Containers" --msgbox "No running Qoffee-Maker containers found." 8 60
    fi
}

# Run Quantum-Mixer demo
run_quantum_mixer_demo() {
    # Check if setup has been run (Docker installed)
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Setup Required" --msgbox \
            "Quantum-Mixer requires Docker, which is not installed.\n\nSetup will now run to install Docker.\n\nNote: This requires internet connection and may take 5-10 minutes." \
            12 70
        "$BIN_DIR/qoffee-setup.sh" || return 1
    fi

    # Launch the Quantum-Mixer demo
    "$BIN_DIR/quantum-mixer.sh"
}

# Stop Quantum-Mixer containers
stop_quantum_mixer_containers() {
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Docker Not Found" --msgbox "Docker is not installed. No containers to stop." 8 60
        return 0
    fi

    # Check if any quantum-mixer containers are running
    if docker ps -q --filter name=quantum-mixer 2>/dev/null | grep -q .; then
        echo "Stopping Quantum-Mixer containers..."
        docker stop $(docker ps -q --filter name=quantum-mixer) 2>/dev/null || true
        whiptail --title "Quantum-Mixer Stopped" --msgbox "All Quantum-Mixer containers have been stopped." 8 60
    else
        whiptail --title "No Containers" --msgbox "No running Quantum-Mixer containers found." 8 60
    fi
}

# Run continuous demo loop for conference showcases
run_demo_loop() {
    # Launch the demo loop script
    "$BIN_DIR/rq_demo_loop.sh"
}

# -----------------------------------------------------------------------------
# 3a) Environment Variable Menu
# -----------------------------------------------------------------------------

# Function to update values stored in the rasqberry_environment.env file
do_select_environment_variable() {

  if [ ! -f "$ENV_FILE" ]; then
    whiptail --title "Error" --msgbox "Environment file not found!" 8 50
    return 1
  fi

  # Build menu items as positional parameters from environment file (POSIX-compliant)
  set --
  while IFS='=' read -r key value; do
    # Skip comments and empty lines
    case "$key" in
      ''|'#'*|' #'*|'	#'*) continue ;;
    esac
    set -- "$@" "$key" "$value"
  done < "$ENV_FILE"

  # Create a menu with the environment variables
  FUN=$(whiptail --title "Select Environment Variable" --menu "Choose a variable to update" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" "$@" 3>&1 1>&2 2>&3)
  RET=$?
  if [ "$RET" -eq 1 ]; then
    return 0
  fi
  # Prompt for the new value and update the environment file
  new_value=$(whiptail --inputbox "Enter new value for ${FUN}" "$WT_HEIGHT" "$WT_WIDTH" 3>&1 1>&2 2>&3)
  RET=$?
  if [ "$RET" -eq 0 ]; then
    update_environment_file "${FUN}" "$new_value"
  fi
}

# Function to update values stored in the rasqberry_environment.env file
update_environment_file () {
  #check whether string is empty
  if [ -z "$2" ] || [ -z "$1" ]; then
    # whiptail message box to show error
    if [ "$INTERACTIVE" = true ]; then
      [ "$RQ_NO_MESSAGES" = false ] && whiptail --title "Error" --msgbox "Error: No value provided. Environment variable not updated" 8 78
    fi
  else
    # update environment file
    sed -i "s/^$1=.*/$1=$2/gm" "$ENV_FILE"
    # reload environment file
    . /usr/config/rasqberry_env-config.sh
  fi
}


# Function to check the value of a variable in the environment file
check_environment_variable() {
    VARIABLE_NAME="$1"

    # Check if the environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        whiptail --msgbox "Environment file not found. Please ensure it exists." 20 60 1
        return 1
    fi

    # Retrieve the value of the variable
    VALUE=$(grep -E "^$VARIABLE_NAME=" "$ENV_FILE" | cut -d'=' -f2)

    # Return the value
    echo "$VALUE"
}


# -----------------------------------------------------------------------------
# 3b) Qiskit Install Menu
# -----------------------------------------------------------------------------

# Install any version of Qiskit using consolidated script
# $1 = version (latest, 1.0, 1.1)
# $2 = silent (optional, suppresses whiptail popup)
do_rqb_install_qiskit() {
  sudo -u "$SUDO_USER" -H -- sh -c "$BIN_DIR/rq_install_qiskit.sh $1"
  if [ "$INTERACTIVE" = true ] && ! [ "$2" = silent ]; then
    [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "Qiskit $1 installed" 20 60 1
  fi
}

do_rqb_qiskit_menu() {
    while true; do
        FUN=$(show_menu "Qiskit Install" "Choose version to install" \
           Qnew  "Install Qiskit (latest)" \
           Q11   "Install Qiskit v1.1" \
           Q10   "Install Qiskit v1.0") || break
        case "$FUN" in
            Q11)   do_rqb_install_qiskit 1.1 || { handle_error "Failed to install Qiskit v1.1."; continue; } ;;
            Q10)   do_rqb_install_qiskit 1.0 || { handle_error "Failed to install Qiskit v1.0."; continue; } ;;
            Qnew)  do_rqb_install_qiskit latest || { handle_error "Failed to install latest Qiskit."; continue; } ;;
            *)      break ;;
        esac
    done
}


# -----------------------------------------------------------------------------
# 3c) LED Demo Menu
# -----------------------------------------------------------------------------

#Turn off all LEDs
do_led_off() {
  . "$VENV_ACTIVATE"
  python3 "$BIN_DIR/turn_off_LEDs.py"
}

# -----------------------------------------------------------------------------
# 3c) LED Display Menu (Text & Logo Display)
# -----------------------------------------------------------------------------

do_led_custom_text() {
    run_demo "LED Text Display" "$BIN_DIR" bash rq_led_display_text.sh
}

do_led_choose_logo() {
    run_demo "LED Logo Display" "$BIN_DIR" bash rq_led_display_logo.sh
}

do_led_demo_scroll_welcome() {
    run_demo bg "Scrolling Welcome" "$BIN_DIR" python3 demo_led_text_scroll_welcome.py
    do_led_off
}

do_led_demo_status() {
    run_demo bg "Status Messages" "$BIN_DIR" python3 demo_led_text_status.py
    do_led_off
}

do_led_demo_alert() {
    run_demo bg "Alert Flash" "$BIN_DIR" python3 demo_led_text_alert.py
    do_led_off
}

do_led_demo_rainbow_scroll() {
    run_demo bg "Rainbow Scroll" "$BIN_DIR" python3 demo_led_text_rainbow_scroll.py
    do_led_off
}

do_led_demo_rainbow_static() {
    run_demo bg "Rainbow Color Cycle" "$BIN_DIR" python3 demo_led_text_rainbow_static.py
    do_led_off
}

do_led_demo_gradient() {
    run_demo bg "Color Gradient" "$BIN_DIR" python3 demo_led_text_gradient.py
    do_led_off
}

do_led_demo_ibm_logo() {
    run_demo bg "IBM Logo" "$BIN_DIR" python3 demo_led_ibm_logo.py
    do_led_off
}

do_led_demo_rasqberry_logo() {
    run_demo bg "RasQberry Logo" "$BIN_DIR" python3 demo_led_rasqberry_logo.py
    do_led_off
}

do_led_demo_logo_slideshow() {
    run_demo bg "Logo Slideshow" "$BIN_DIR" python3 demo_led_logo_slideshow.py
    do_led_off
}

do_led_display_menu() {
    while true; do
        FUN=$(show_menu "RasQberry: LED Text & Logo Display" "Display Options" \
           TEXT    "Display Custom Text" \
           LOGO    "Display Logo from Library" \
           "---1"  "--- Text Demos ---" \
           SWEL    "Demo: Scrolling Welcome" \
           STAT    "Demo: Status Messages" \
           ALRT    "Demo: Alert Flash" \
           "---2"  "--- Color Effect Demos ---" \
           RSCR    "Demo: Rainbow Scroll" \
           RSTA    "Demo: Rainbow Color Cycle" \
           GRAD    "Demo: Color Gradient" \
           "---3"  "--- Logo Demos ---" \
           IBML    "Demo: IBM Logo" \
           RQBL    "Demo: RasQberry Logo" \
           SLID    "Demo: Logo Slideshow" \
           "---4"  "---" \
           CLEAR   "Clear LEDs") || break
        case "$FUN" in
            TEXT  ) do_led_custom_text           || { handle_error "Text display failed."; continue; } ;;
            LOGO  ) do_led_choose_logo           || { handle_error "Logo display failed."; continue; } ;;
            SWEL  ) do_led_demo_scroll_welcome   || { handle_error "Demo failed."; continue; } ;;
            STAT  ) do_led_demo_status           || { handle_error "Demo failed."; continue; } ;;
            ALRT  ) do_led_demo_alert            || { handle_error "Demo failed."; continue; } ;;
            RSCR  ) do_led_demo_rainbow_scroll   || { handle_error "Demo failed."; continue; } ;;
            RSTA  ) do_led_demo_rainbow_static   || { handle_error "Demo failed."; continue; } ;;
            GRAD  ) do_led_demo_gradient         || { handle_error "Demo failed."; continue; } ;;
            IBML  ) do_led_demo_ibm_logo         || { handle_error "Demo failed."; continue; } ;;
            RQBL  ) do_led_demo_rasqberry_logo   || { handle_error "Demo failed."; continue; } ;;
            SLID  ) do_led_demo_logo_slideshow   || { handle_error "Demo failed."; continue; } ;;
            CLEAR ) do_led_off                   || { handle_error "Failed to clear LEDs."; continue; } ;;
            "---1"|"---2"|"---3"|"---4" ) continue ;;  # Ignore separator items
            *) break ;;
        esac
    done
}

do_select_led_option() {
    while true; do
        FUN=$(show_menu "RasQberry: LEDs" "LED options" \
           OFF "Turn off all LEDs" \
           DISP "Text & Logo Display" \
           quicktest "Quick LED Test (6 colors)" \
           test "LED Test & Diagnostics" \
           simple "Simple LED Demo" \
           IBM "IBM LED Demo" \
           layout "Configure Matrix Layout") || break
        case "$FUN" in
            OFF ) do_led_off || { handle_error "Turning off all LEDs failed."; continue; } ;;
            DISP ) do_led_display_menu || { handle_error "Failed to open text/logo display menu."; continue; } ;;
            quicktest )
                run_demo bg "Quick LED Test" "$BIN_DIR" python3 rq_test_leds.py || { handle_error "Quick LED test failed."; continue; }
                do_led_off
                ;;
            test )
                run_demo "LED Test" "$BIN_DIR" bash rq_led_test.sh || { handle_error "LED test failed."; continue; }
                do_led_off
                ;;
            simple )
                run_demo bg "Simple LED Demo" "$BIN_DIR" python3 neopixel_spi_simpletest.py || { handle_error "Simple LED demo failed."; continue; }
                do_led_off
                ;;
            IBM )
                run_demo bg "IBM LED Demo" "$BIN_DIR" python3 neopixel_spi_IBMtestFunc.py || { handle_error "IBM LED demo failed."; continue; }
                do_led_off
                ;;
            layout )
                do_select_led_layout || { handle_error "Failed to update LED layout."; continue; }
                ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3d) Quantum Lights Out Menu
# -----------------------------------------------------------------------------

do_select_qlo_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Quantum Lights Out" "Options" \
           QLO  "Run Demo" \
           QLOC "Run Demo (console)") || break
        case "$FUN" in
            QLO  ) run_qlo_demo      || { handle_error "QLO demo failed."; continue; } ;;
            QLOC ) run_qlo_demo console    || { handle_error "QLO console demo failed."; continue; } ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3e) Quantum Raspberry-Tie Menu
# -----------------------------------------------------------------------------

do_select_qrt_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Quantum Raspberry-Tie" "Backend options" \
           b:aer       "Local Aer simulator" \
           b:aer_noise "Aer with noise model" \
           b:least     "Least busy real backend" \
           b:custom    "Custom backend or option") || break
        case "$FUN" in
            b:aer ) run_rasp_tie_demo "$FUN" || { handle_error "RasQberry Tie failed."; continue; } ;;
            b:aer_noise ) run_rasp_tie_demo "$FUN" || { handle_error "RasQberry Tie failed."; continue; } ;;
            b:least ) run_rasp_tie_demo "$FUN" || { handle_error "RasQberry Tie failed."; continue; } ;;
            b:custom)
                CUSTOM_OPTION=$(whiptail --inputbox "Enter your custom backend or option:" 8 50 3>&1 1>&2 2>&3)
                exitstatus=$?
                if [ "$exitstatus" = 0 ]; then
                    run_rasp_tie_demo "$CUSTOM_OPTION" || { handle_error "RasQberry Tie failed."; continue; }
                else
                    echo "You chose to cancel. Demo will launch with Local Simulator"
                    break
                fi
                ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3f) Main Quantum Demo Menu
# -----------------------------------------------------------------------------

do_quantum_demo_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Quantum Demos" "Select demo category" \
       LED  "Test LEDs" \
       QLO  "Quantum-Lights-Out Demo" \
       QRT  "Quantum Raspberry-Tie" \
       GRB  "Grok Bloch Sphere (Local)" \
       GRBW "Grok Bloch Sphere (Web)" \
       FRC  "Quantum Fractals" \
       RQL  "RasQ-LED (Quantum Circuit)" \
       LDP  "LED-Painter (Paint on LEDs)" \
       QOF  "Qoffee-Maker (Docker)" \
       QMX  "Quantum-Mixer (Web)" \
       LOOP "Continuous Demo Loop (Conference)" \
       STOP "Stop last running demo and clear LEDs" \
       QSTP "Stop Qoffee-Maker containers" \
       QMXS "Stop Quantum-Mixer containers") || break
    case "$FUN" in
      LED)  do_select_led_option       || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option       || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option       || { handle_error "Failed to open QRT options."; continue; } ;;
      GRB)  run_grok_bloch_demo        || continue ;;
      GRBW) run_grok_bloch_web_demo    || continue ;;
      FRC)  run_fractals_demo          || { handle_error "Failed to run Quantum Fractals demo."; continue; } ;;
      RQL)  run_rasq_led_demo          || { handle_error "Failed to run RasQ-LED demo."; continue; } ;;
      LDP)  run_led_painter_demo       || { handle_error "Failed to run LED-Painter demo."; continue; } ;;
      QOF)  run_qoffee_demo            || { handle_error "Failed to run Qoffee-Maker demo."; continue; } ;;
      QMX)  run_quantum_mixer_demo     || { handle_error "Failed to run Quantum-Mixer demo."; continue; } ;;
      LOOP) run_demo_loop              || { handle_error "Failed to run demo loop."; continue; } ;;
      STOP) stop_last_demo             || { handle_error "Failed to stop demo."; continue; } ;;
      QSTP) stop_qoffee_containers     || { handle_error "Failed to stop Qoffee containers."; continue; } ;;
      QMXS) stop_quantum_mixer_containers || { handle_error "Failed to stop Quantum-Mixer containers."; continue; } ;;
      *)    handle_error "Programmer error: unrecognized Quantum Demo option ${FUN}."; continue ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# 3g) Main Raspi Config Menu
# -----------------------------------------------------------------------------

do_show_system_info() {
  local version="Unknown"
  if [ -f /etc/rasqberry-version ]; then
    version=$(cat /etc/rasqberry-version)
  fi

  whiptail --title "RasQberry System Information" --msgbox \
    "RasQberry Version: $version\n\nThis version identifier corresponds to the GitHub Actions workflow run that built this image." \
    10 70
}

# -----------------------------------------------------------------------------
# A/B Boot Partition Expansion
# -----------------------------------------------------------------------------

# Expand A/B partitions for 64GB+ SD cards
do_expand_ab_partitions() {
    # Check if this is an AB boot image
    if ! lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -q "config"; then
        whiptail --title "Not AB Boot Image" --msgbox \
            "This system is not running an A/B boot image.\n\nPartition expansion is only available for AB boot layouts." \
            10 60
        return 1
    fi

    # Get SD card size in bytes
    SD_SIZE_BYTES=$(lsblk -bno SIZE /dev/mmcblk0 2>/dev/null | head -1)
    SD_SIZE_GB=$((SD_SIZE_BYTES / 1024 / 1024 / 1024))

    # Check minimum size (63GB = ~64GB marketed card)
    if [ "$SD_SIZE_GB" -lt 63 ]; then
        whiptail --title "SD Card Too Small" --msgbox \
            "SD card size: ${SD_SIZE_GB}GB\n\nPartition expansion requires a 64GB or larger SD card.\n\nYour current 10GB system partition is sufficient for basic use." \
            12 60
        return 1
    fi

    # Check if already expanded (system-b > 1GB indicates expansion)
    SYSTEM_B_SIZE=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    SYSTEM_B_SIZE_GB=$((SYSTEM_B_SIZE / 1024 / 1024 / 1024))
    if [ "$SYSTEM_B_SIZE_GB" -gt 1 ]; then
        whiptail --title "Already Expanded" --msgbox \
            "Partitions appear to already be expanded.\n\nSystem-B size: ${SYSTEM_B_SIZE_GB}GB" \
            10 60
        return 0
    fi

    # Calculate partition sizes
    # Fixed partitions: config (512MB) + boot-a (512MB) + boot-b (512MB) = 1536MB
    FIXED_MB=1536
    SD_SIZE_MB=$((SD_SIZE_BYTES / 1024 / 1024))
    AVAILABLE_MB=$((SD_SIZE_MB - FIXED_MB))

    # Calculate: data=10%, system-a=45%, system-b=45%
    DATA_MB=$((AVAILABLE_MB * 10 / 100))
    SYSTEM_MB=$(((AVAILABLE_MB - DATA_MB) / 2))

    DATA_GB=$((DATA_MB / 1024))
    SYSTEM_GB=$((SYSTEM_MB / 1024))

    # Show confirmation dialog
    if ! whiptail --title "Expand A/B Partitions" --yesno \
        "SD Card Size: ${SD_SIZE_GB}GB\n\nProposed partition sizes:\n  System-A: ${SYSTEM_GB}GB\n  System-B: ${SYSTEM_GB}GB\n  Data:     ${DATA_GB}GB\n\nThis will:\n- Expand system-a from 10GB to ${SYSTEM_GB}GB\n- Expand system-b from 16MB to ${SYSTEM_GB}GB\n- Expand data from 16MB to ${DATA_GB}GB\n\nThis operation cannot be undone.\n\nProceed with expansion?" \
        20 60; then
        return 0
    fi

    # Show progress
    whiptail --title "Expanding Partitions" --infobox \
        "Expanding partitions...\n\nThis may take a few minutes.\nDo not power off the system." \
        10 50

    # Initialize log file
    echo "=== AB Partition Expansion $(date) ===" > /var/log/rasqberry-expand.log

    # Step 1: Unmount partitions that will be modified
    echo "Step 1: Unmounting partitions..." >> /var/log/rasqberry-expand.log
    umount /dev/mmcblk0p7 2>/dev/null || true
    umount /dev/mmcblk0p6 2>/dev/null || true
    # Also unmount any automounted locations
    umount /media/*/system-b 2>/dev/null || true
    umount /media/*/data 2>/dev/null || true

    # Get current partition boundaries
    # p5 = system-a, p6 = system-b, p7 = data
    SYSTEM_A_START=$(parted -s /dev/mmcblk0 unit MiB print | grep "^ 5" | awk '{print $2}' | tr -d 'MiB')

    # Calculate new boundaries
    SYSTEM_A_END=$((SYSTEM_A_START + SYSTEM_MB))
    SYSTEM_B_START=$((SYSTEM_A_END + 2))  # 2 MiB gap for alignment
    SYSTEM_B_END=$((SYSTEM_B_START + SYSTEM_MB))
    DATA_START=$((SYSTEM_B_END + 2))  # 2 MiB gap for alignment

    echo "Calculated boundaries:" >> /var/log/rasqberry-expand.log
    echo "  SYSTEM_A: ${SYSTEM_A_START} - ${SYSTEM_A_END} MiB" >> /var/log/rasqberry-expand.log
    echo "  SYSTEM_B: ${SYSTEM_B_START} - ${SYSTEM_B_END} MiB" >> /var/log/rasqberry-expand.log
    echo "  DATA: ${DATA_START} - 100%" >> /var/log/rasqberry-expand.log

    # Step 2: Delete p7 and p6 first (must be done before resizing p5)
    echo "Step 2: Deleting old partitions..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 rm 7 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Warning: Failed to delete partition 7" >> /var/log/rasqberry-expand.log
    fi
    if ! parted -s /dev/mmcblk0 rm 6 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Warning: Failed to delete partition 6" >> /var/log/rasqberry-expand.log
    fi

    # Step 3: Expand extended partition (p4) to fill disk
    echo "Step 3: Expanding extended partition..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 resizepart 4 100% >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to expand extended partition" >> /var/log/rasqberry-expand.log
    fi

    # Step 4: Resize system-a (p5)
    echo "Step 4: Resizing system-a partition..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 resizepart 5 ${SYSTEM_A_END}MiB >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to resize partition 5" >> /var/log/rasqberry-expand.log
    fi

    # Step 5: Create new system-b and data partitions
    echo "Step 5: Creating new partitions..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 mkpart logical ext4 ${SYSTEM_B_START}MiB ${SYSTEM_B_END}MiB >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to create system-b partition" >> /var/log/rasqberry-expand.log
    fi
    if ! parted -s /dev/mmcblk0 mkpart logical ext4 ${DATA_START}MiB 100% >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to create data partition" >> /var/log/rasqberry-expand.log
    fi

    # Wait for kernel to recognize new partitions
    partprobe /dev/mmcblk0
    sleep 2

    # Step 6: Resize system-a filesystem
    echo "Step 6: Resizing system-a filesystem..." >> /var/log/rasqberry-expand.log
    resize2fs /dev/mmcblk0p5 >> /var/log/rasqberry-expand.log 2>&1 || true

    # Step 7: Format new partitions
    echo "Step 7: Formatting new partitions..." >> /var/log/rasqberry-expand.log
    if ! mkfs.ext4 -F -L "system-b" /dev/mmcblk0p6 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to format system-b" >> /var/log/rasqberry-expand.log
    fi
    if ! mkfs.ext4 -F -L "data" /dev/mmcblk0p7 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to format data" >> /var/log/rasqberry-expand.log
    fi

    # Step 8: Set up system-b structure
    echo "Step 8: Setting up system-b structure..." >> /var/log/rasqberry-expand.log
    TEMP_MOUNT=$(mktemp -d)
    if mount /dev/mmcblk0p6 "$TEMP_MOUNT" 2>> /var/log/rasqberry-expand.log; then
        # Create directory structure (no brace expansion - POSIX sh compatible)
        mkdir -p "$TEMP_MOUNT/boot/config"
        mkdir -p "$TEMP_MOUNT/boot/firmware"
        mkdir -p "$TEMP_MOUNT/data"
        mkdir -p "$TEMP_MOUNT/etc"

        # Create fstab for slot B
        cat > "$TEMP_MOUNT/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/mmcblk0p1              /boot/config    vfat    defaults          0   2
/dev/mmcblk0p3              /boot/firmware  vfat    defaults          0   2
/dev/mmcblk0p6              /               ext4    defaults,noatime  0   1
/dev/mmcblk0p7              /data           ext4    defaults,noatime  0   2
EOF
        umount "$TEMP_MOUNT"
    fi
    rmdir "$TEMP_MOUNT" 2>/dev/null || true

    # Step 9: Set up data partition structure
    echo "Step 9: Setting up data partition..." >> /var/log/rasqberry-expand.log
    TEMP_MOUNT=$(mktemp -d)
    if mount /dev/mmcblk0p7 "$TEMP_MOUNT" 2>> /var/log/rasqberry-expand.log; then
        # Create directory structure (no brace expansion - POSIX sh compatible)
        mkdir -p "$TEMP_MOUNT/home"
        mkdir -p "$TEMP_MOUNT/var/log"
        umount "$TEMP_MOUNT"
    fi
    rmdir "$TEMP_MOUNT" 2>/dev/null || true

    # Remount /data for current session
    mount /dev/mmcblk0p7 /data 2>/dev/null || true

    echo "=== Expansion complete ===" >> /var/log/rasqberry-expand.log

    # Verify expansion
    NEW_SYSTEM_B_SIZE=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    NEW_SYSTEM_B_GB=$((NEW_SYSTEM_B_SIZE / 1024 / 1024 / 1024))

    if [ "$NEW_SYSTEM_B_GB" -gt 1 ]; then
        whiptail --title "Expansion Complete" --msgbox \
            "Partitions expanded successfully!\n\nNew sizes:\n  System-A: ${SYSTEM_GB}GB\n  System-B: ${SYSTEM_GB}GB\n  Data:     ${DATA_GB}GB\n\nYour A/B boot system is now fully configured." \
            14 60
    else
        whiptail --title "Expansion Failed" --msgbox \
            "Partition expansion may have failed.\n\nPlease check /var/log/rasqberry-expand.log for details." \
            10 60
        return 1
    fi
}

# LED Matrix Layout Configuration
do_select_led_layout() {
  # Get current layout setting
  CURRENT_LAYOUT=$(check_environment_variable "LED_MATRIX_LAYOUT")

  # Show current setting in menu
  if [ "$CURRENT_LAYOUT" = "quad" ]; then
    CURRENT_DESC="Current: 4× 4×12 panels (quad layout)"
  else
    CURRENT_DESC="Current: Single 8×24 panel (serpentine)"
  fi

  FUN=$(show_menu "LED Matrix Layout Configuration" "$CURRENT_DESC\n\nSelect your LED matrix layout:\nBoth layouts use 192 LEDs (8 rows × 24 columns)" \
     single "Single 8×24 serpentine panel" \
     quad   "4× 4×12 panels (2×2 grid)") || return 0

  case "$FUN" in
    single)
      update_environment_file "LED_MATRIX_LAYOUT" "single"
      update_environment_file "LED_MATRIX_Y_FLIP" "true"
      whiptail --title "LED Layout Updated" --msgbox \
        "LED matrix layout set to:\n\nSingle 8×24 serpentine panel\n- Total: 192 LEDs (8 rows × 24 columns)\n- Wiring: Serpentine (zigzag) pattern\n- Y-axis: Flipped (upside down)\n\nRestart demos for changes to take effect." \
        13 60
      ;;
    quad)
      update_environment_file "LED_MATRIX_LAYOUT" "quad"
      update_environment_file "LED_MATRIX_Y_FLIP" "false"
      whiptail --title "LED Layout Updated" --msgbox \
        "LED matrix layout set to:\n\n4× 4×12 panels (quad layout)\n- Total: 192 LEDs (8 rows × 24 columns)\n- Each panel: 4×12 LEDs\n- Arrangement: 2×2 grid\n- Wiring: TL→TR→BR→BL\n\nRestart demos for changes to take effect." \
        14 60
      ;;
    *)
      return 0
      ;;
  esac
}

# A/B Boot Administration Menu
do_ab_boot_menu() {
    while true; do
        # Check if this is an AB boot image
        local is_ab_image="No"
        if lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qE "^(config|bootfs-cmn)$"; then
            is_ab_image="Yes"
        fi

        FUN=$(show_menu "RasQberry: A/B Boot Administration" "A/B Image: ${is_ab_image}" \
            EXPAND "Expand A/B Partitions (64GB+ SD)" \
            SLOTS  "Slot Manager (switch, confirm, promote)") || break

        case "$FUN" in
            EXPAND) do_expand_ab_partitions || continue ;;
            SLOTS)  do_slot_manager_menu    || continue ;;
            *)      continue ;;
        esac
    done
}

# GitHub Release Picker Helper Functions
# Fetch releases from GitHub and select image via menus

# Pick stream (dev/beta/stable)
pick_stream() {
    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    whiptail --title "Select Release Stream" --menu \
        "Choose the release stream:\n\n  dev    - Development builds (latest features)\n  beta   - Beta releases (testing)\n  stable - Stable releases (production)" \
        16 60 3 \
        "dev"    "Development builds" \
        "beta"   "Beta releases" \
        "stable" "Stable releases" \
        3>&1 1>&2 2>&3 </dev/tty 2>/dev/tty
}

# Pick release from stream
pick_release() {
    local stream="$1"
    local releases_json
    local menu_items
    local selected

    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    # Fetch releases from GitHub
    whiptail --title "Fetching Releases" --infobox \
        "Fetching releases from GitHub...\n\nPlease wait." 8 50 </dev/tty 2>/dev/tty

    releases_json=$(curl -s "https://api.github.com/repos/JanLahmann/RasQberry-Two/releases" 2>/dev/null)

    if [ -z "$releases_json" ] || echo "$releases_json" | grep -q '"message"'; then
        whiptail --title "Error" --msgbox "Failed to fetch releases from GitHub.\n\nPlease check your internet connection." 10 60 </dev/tty 2>/dev/tty
        return 1
    fi

    # Filter releases by stream prefix and build menu items
    # Format: tag_name + created_at for display
    menu_items=$(echo "$releases_json" | jq -r --arg stream "$stream" '
        [.[] | select(.tag_name | startswith($stream + "-"))] |
        sort_by(.created_at) | reverse |
        .[0:10] |
        .[] |
        "\(.tag_name)\n\(.created_at | split("T")[0])"
    ' 2>/dev/null)

    if [ -z "$menu_items" ]; then
        whiptail --title "No Releases" --msgbox "No releases found for stream: $stream\n\nTry a different stream." 10 50 </dev/tty 2>/dev/tty
        return 1
    fi

    # Convert to whiptail menu format (tag date tag date ...)
    # shellcheck disable=SC2086
    selected=$(echo "$menu_items" | xargs whiptail --title "Select Release" --menu \
        "Choose a release from the '$stream' stream:" \
        20 70 10 3>&1 1>&2 2>&3 </dev/tty 2>/dev/tty)

    if [ -z "$selected" ]; then
        return 1
    fi

    echo "$selected"
}

# Pick image from release assets
pick_image() {
    local release_tag="$1"
    local assets_json
    local menu_items
    local selected

    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    # Fetch release assets
    whiptail --title "Fetching Images" --infobox \
        "Fetching available images for release:\n$release_tag\n\nPlease wait." 10 60 </dev/tty 2>/dev/tty

    assets_json=$(curl -s "https://api.github.com/repos/JanLahmann/RasQberry-Two/releases/tags/$release_tag" 2>/dev/null)

    if [ -z "$assets_json" ] || echo "$assets_json" | grep -q '"message"'; then
        whiptail --title "Error" --msgbox "Failed to fetch release details.\n\nPlease check your connection." 10 60 </dev/tty 2>/dev/tty
        return 1
    fi

    # Filter for .img.xz files and build menu items
    menu_items=$(echo "$assets_json" | jq -r '
        .assets[] |
        select(.name | endswith(".img.xz")) |
        "\(.browser_download_url)\n\(.name) (\(.size / 1024 / 1024 | floor)MB)"
    ' 2>/dev/null)

    if [ -z "$menu_items" ]; then
        whiptail --title "No Images" --msgbox "No image files found in release: $release_tag" 10 50 </dev/tty 2>/dev/tty
        return 1
    fi

    # Count number of images
    local image_count
    image_count=$(echo "$menu_items" | grep -c "^https")

    if [ "$image_count" -eq 1 ]; then
        # Only one image, return it directly
        selected=$(echo "$menu_items" | head -1)
    else
        # Multiple images, show selection menu
        # shellcheck disable=SC2086
        selected=$(echo "$menu_items" | xargs whiptail --title "Select Image" --menu \
            "Multiple images available.\nChoose the image type:" \
            16 80 5 3>&1 1>&2 2>&3 </dev/tty 2>/dev/tty)
    fi

    if [ -z "$selected" ]; then
        return 1
    fi

    echo "$selected"
}

# Main release picker function - returns "url|tag" or empty on cancel
do_pick_release_image() {
    local stream
    local release_tag
    local image_url

    # Check if we have access to /dev/tty for interactive dialogs
    if [ ! -c /dev/tty ] || ! : 2>/dev/tty; then
        whiptail --title "Terminal Required" --msgbox \
            "Interactive menu requires a controlling terminal.\n\nPlease run raspi-config from:\n  - Direct console (keyboard + monitor)\n  - SSH with proper TTY allocation\n  - VNC terminal (not X terminal)" \
            12 60
        return 1
    fi

    # Step 1: Pick stream
    stream=$(pick_stream) || return 1

    # Step 2: Pick release from stream
    release_tag=$(pick_release "$stream") || return 1

    # Step 3: Pick image from release
    image_url=$(pick_image "$release_tag") || return 1

    # Return url|tag format
    echo "${image_url}|${release_tag}"
}

# A/B Boot Slot Manager Menu
do_slot_manager_menu() {
    # Check if this is an AB boot image
    if ! lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qE "^(config|bootfs-cmn)$"; then
        whiptail --title "Not AB Boot Image" --msgbox \
            "This system is not running an A/B boot image.\n\nSlot management is only available for AB boot layouts." \
            10 60
        return 1
    fi

    while true; do
        # Get current status for menu display
        local current_slot
        current_slot=$(/usr/local/bin/rq_slot_manager.sh status 2>&1 | grep "Current Slot:" | awk '{print $NF}')
        local slot_status
        slot_status=$(/usr/local/bin/rq_slot_manager.sh status 2>&1 | grep "Slot Status:" | sed 's/.*Slot Status: //')

        FUN=$(show_menu "RasQberry: A/B Boot Slot Manager" "Current: Slot ${current_slot} (${slot_status})" \
            STATUS   "Show detailed slot status" \
            CONFIRM  "Confirm current slot (prevent rollback)" \
            SWITCH_A "Switch to Slot A on next reboot" \
            SWITCH_B "Switch to Slot B on next reboot" \
            UPDATE   "Update Slot B with new image" \
            ROLLBACK "Force rollback to other slot" \
            PROMOTE  "Promote Slot B to Slot A") || break

        case "$FUN" in
            STATUS)
                local status_output
                status_output=$(/usr/local/bin/rq_slot_manager.sh status 2>&1)
                whiptail --title "A/B Boot Status" --msgbox "$status_output" 20 70
                ;;
            CONFIRM)
                local confirm_output
                confirm_output=$(/usr/local/bin/rq_slot_manager.sh confirm 2>&1)
                whiptail --title "Confirm Slot" --msgbox "$confirm_output" 12 60
                ;;
            SWITCH_A)
                if whiptail --title "Switch to Slot A" --yesno \
                    "This will configure the system to boot from Slot A on next reboot.\n\nContinue?" 10 60; then
                    local switch_output
                    switch_output=$(/usr/local/bin/rq_slot_manager.sh switch-to A 2>&1)
                    whiptail --title "Switch to Slot A" --msgbox "$switch_output\n\nReboot required for changes to take effect." 14 60
                fi
                ;;
            SWITCH_B)
                if whiptail --title "Switch to Slot B" --yesno \
                    "This will configure the system to boot from Slot B on next reboot.\n\nNote: Slot B must have a valid system image installed.\n\nContinue?" 12 60; then
                    local switch_output
                    switch_output=$(/usr/local/bin/rq_slot_manager.sh switch-to B 2>&1)
                    whiptail --title "Switch to Slot B" --msgbox "$switch_output\n\nReboot required for changes to take effect." 14 60
                fi
                ;;
            UPDATE)
                # Use release picker to select image from GitHub
                local picker_result
                picker_result=$(do_pick_release_image) || continue

                # Parse result (url|tag format)
                local image_url
                local release_tag
                image_url=$(echo "$picker_result" | cut -d'|' -f1)
                release_tag=$(echo "$picker_result" | cut -d'|' -f2)

                if [ -z "$image_url" ] || [ -z "$release_tag" ]; then
                    whiptail --title "Error" --msgbox "Failed to get image selection." 8 50
                    continue
                fi

                # Extract just the filename for display
                local image_name
                image_name=$(basename "$image_url")

                if whiptail --title "Confirm Update" --yesno \
                    "This will download and install:\n\nRelease: $release_tag\nImage: $image_name\n\nThis will take 10-20 minutes and reboot automatically.\n\nContinue?" 16 70; then

                    whiptail --title "Updating Slot B" --infobox \
                        "Downloading and installing image to Slot B...\n\nThis will take 10-20 minutes.\nSystem will reboot automatically when complete." 10 60

                    /usr/bin/rq_update_slot.sh "$image_url" "$release_tag" --slot B
                fi
                ;;
            ROLLBACK)
                if whiptail --title "Force Rollback" --yesno \
                    "This will force a rollback to the other slot.\n\nUse this if the current slot is having problems.\n\nContinue?" 12 60; then
                    local rollback_output
                    rollback_output=$(/usr/local/bin/rq_slot_manager.sh rollback 2>&1)
                    whiptail --title "Rollback" --msgbox "$rollback_output\n\nReboot required for changes to take effect." 14 60
                fi
                ;;
            PROMOTE)
                if whiptail --title "Promote Slot B" --yesno \
                    "This will promote Slot B to become the new Slot A.\n\nThis copies the tested Slot B system to Slot A.\n\nWARNING: This will overwrite Slot A!\n\nContinue?" 14 60; then
                    whiptail --title "Promoting Slot B" --infobox \
                        "Promoting Slot B to Slot A...\n\nThis may take several minutes." 8 50
                    local promote_output
                    promote_output=$(/usr/local/bin/rq_slot_manager.sh promote 2>&1)
                    whiptail --title "Promote Result" --msgbox "$promote_output" 16 70
                fi
                ;;
            *)
                continue
                ;;
        esac
    done
}

do_rasqberry_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Main Menu" "System Options" \
       QD      "Quantum Demos" \
       UEF     "Update Env File" \
       AB_BOOT "A/B Boot Administration" \
       INFO    "System Info") || break
    case "$FUN" in
      QD)      do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      UEF)     do_select_environment_variable || { handle_error "Failed to update environment file."; continue; } ;;
      AB_BOOT) do_ab_boot_menu                || continue ;;
      INFO)    do_show_system_info            || { handle_error "Failed to show system info."; continue; } ;;
      *)       handle_error "Programmer error: unrecognized main menu option ${FUN}."; continue ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# 4. Error Handling
# -----------------------------------------------------------------------------

# Function for graceful error handling in menus
handle_error() {
    local MSG="$1"
    whiptail --title "Error" --msgbox "$MSG" 8 60
    return 1
}