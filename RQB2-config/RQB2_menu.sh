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
BIN_DIR="$USER_HOME/.local/bin"
VENV_ACTIVATE="$REPO_DIR/venv/$STD_VENV/bin/activate"

#
# -----------------------------------------------------------------------------
# 1. Environment & Bootstrap
# -----------------------------------------------------------------------------
#
# Bootstrap: ensure rasqberry_env-config.sh is linked into $BIN_DIR for scripts (for backward compatibility)
bootstrap_env_config() {
    SOURCE_FILE="/usr/config/rasqberry_env-config.sh"
    TARGET_LINK="$BIN_DIR/rasqberry_env-config.sh"
    # Remove existing symlink if present
    if [ -L "$TARGET_LINK" ]; then
        rm -f "$TARGET_LINK"
    fi
    # Create symbolic link
    ln -sf "$SOURCE_FILE" "$TARGET_LINK"
} || die "Failed to set up configuration link"

# Run bootstrap to set up env-config link
bootstrap_env_config

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
    NAME="$1"       # demo directory name
    GIT_URL="$2"    # corresponding repo URL variable
    MARKER="$3"     # script or file that must exist
    ENV_VAR="$4"    # environment variable name to set
    TITLE="$5"      # title for dialog messages
    SIZE="$6"       # optional: download size (e.g., "5MB")

    DEST="$DEMO_ROOT/$NAME"

    # Check if already installed
    if [ -f "$DEST/$MARKER" ]; then
        return 0  # Already installed
    fi

    # Show confirmation dialog before downloading
    if command -v whiptail > /dev/null 2>&1; then
        SIZE_MSG=""
        if [ -n "$SIZE" ]; then
            SIZE_MSG="\n\nDownload size: ~$SIZE"
        fi

        whiptail --title "$TITLE Not Installed" \
                 --yesno "$TITLE is not installed yet.$SIZE_MSG\n\nRequires internet connection.\n\nInstall now?" \
                 12 65 3>&1 1>&2 2>&3

        if [ $? -ne 0 ]; then
            # User cancelled installation
            return 1
        fi
    else
        # Fallback if whiptail not available
        echo "$TITLE is not installed."
        echo "This requires downloading from GitHub."
        read -p "Install now? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi

    # Clone demo repository
    mkdir -p "$DEST"
    if git clone --depth 1 "$GIT_URL" "$DEST"; then
        # Fix ownership if cloned as root (when run from raspi-config)
        if [ "$(stat -c '%U' "$DEST")" = "root" ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
            chown -R "$SUDO_USER":"$SUDO_USER" "$DEST"
        fi
        update_environment_file "$ENV_VAR" "true"
        [ "$RQ_NO_MESSAGES" = false ] && whiptail --title "$TITLE" --msgbox "Demo installed successfully." 8 60
    else
        # Clean up empty directory and show error
        rm -rf "$DEST"
        whiptail --title "Installation Error" --msgbox "Failed to download $TITLE demo.\n\nPossible causes:\n- No internet connection\n- Repository unavailable\n- Network firewall blocking access\n\nPlease check your connection and try again." 12 70
        return 1
    fi
}

# Install Quantum-Lights-Out demo if needed
do_qlo_install() {
    install_demo "Quantum-Lights-Out" "$GIT_REPO_DEMO_QLO" \
                 "lights_out.py" "QUANTUM_LIGHTS_OUT_INSTALLED" \
                 "Quantum Lights Out"
}

# Install Quantum Raspberry-Tie demo if needed
do_rasp_tie_install() {
    install_demo "quantum-raspberry-tie" "$GIT_REPO_DEMO_QRT" \
                 "QuantumRaspberryTie.v7_1.py" "QUANTUM_RASPBERRY_TIE_INSTALLED" \
                 "Quantum Raspberry-Tie"
}

# Install Grok Bloch demo if needed
do_grok_bloch_install() {
    install_demo "grok-bloch" "$GIT_REPO_DEMO_GROK_BLOCH" \
                 "index.html" "GROK_BLOCH_INSTALLED" \
                 "Grok Bloch Sphere"
}

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
      ( trap '' INT; cd "$DEMO_DIR" && exec setsid sh -c "$CMD" ) &
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

# install any version of qiskit. $1 parameter is the version (e.g. 0.37 = 037), set $2=silent for one-time silent (no whiptail popup) install
# Attention: Only works for specific Qiskit versions with predefined scripts which should be names as "rq_install_qiskitXXX.sh"
# Install latest version of Qiskit via "rq_install_qiskit_latest.sh"
do_rqb_install_qiskit() {
  sudo -u "$SUDO_USER" -H -- sh -c "$BIN_DIR/rq_install_Qiskit$1.sh"
  if [ "$INTERACTIVE" = true ] && ! [ "$2" = silent ]; then
    [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "Qiskit $1 installed" 20 60 1
  fi
}

do_rqb_qiskit_menu() {
    while true; do
        FUN=$(show_menu "Qiskit Install" "Choose version to install" \
           Qnew  "Install Qiskit (latest)" \
           Q0101 "Install Qiskit v1.1" \
           Q0100 "Install Qiskit v1.0") || break
        case "$FUN" in
            Q0101) do_rqb_install_qiskit 0101 || { handle_error "Failed to install Qiskit v1.1."; continue; } ;;
            Q0100) do_rqb_install_qiskit 0100 || { handle_error "Failed to install Qiskit v1.0."; continue; } ;;
            Qnew)  do_rqb_install_qiskit _latest || { handle_error "Failed to install latest Qiskit."; continue; } ;;
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

do_select_led_option() {
    while true; do
        FUN=$(show_menu "RasQberry: LEDs" "LED options" \
           OFF "Turn off all LEDs" \
           simple "Simple LED Demo" \
           IBM "IBM LED Demo") || break
        case "$FUN" in
            OFF ) do_led_off || { handle_error "Turning off all LEDs failed."; continue; } ;;
            simple )
                run_demo bg "Simple LED Demo" "$BIN_DIR" python3 neopixel_spi_simpletest.py || { handle_error "Simple LED demo failed."; continue; }
                do_led_off
                ;;
            IBM )
                run_demo bg "IBM LED Demo" "$BIN_DIR" python3 neopixel_spi_IBMtestFunc.py || { handle_error "IBM LED demo failed."; continue; }
                do_led_off
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

do_rasqberry_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Main Menu" "System Options" \
       QD  "Quantum Demos" \
       UEF "Update Env File" \
       INFO "System Info") || break
    case "$FUN" in
      QD)   do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      UEF)  do_select_environment_variable || { handle_error "Failed to update environment file."; continue; } ;;
      INFO) do_show_system_info            || { handle_error "Failed to show system info."; continue; } ;;
      *)    handle_error "Programmer error: unrecognized main menu option ${FUN}."; continue ;;
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