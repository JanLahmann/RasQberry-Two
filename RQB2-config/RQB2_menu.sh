#!/bin/sh
set -eu
IFS='\
	'

# load RasQberry environment and constants
. "/home/${SUDO_USER:-$USER}/${RQB2_CONFDIR:-.local/config}/env-config.sh"

# Constants and reusable paths
REPO_DIR="$USER_HOME/$REPO"
DEMO_ROOT="$REPO_DIR/demos"
BIN_DIR="$USER_HOME/.local/bin"
VENV_ACTIVATE="$REPO_DIR/venv/$STD_VENV/bin/activate"

# Bootstrap: ensure env-config.sh is linked into $BIN_DIR for scripts
bootstrap_env_config() {
    SOURCE_FILE="$USER_HOME/$RQB2_CONFDIR/env-config.sh"
    TARGET_LINK="$BIN_DIR/env-config.sh"
    # Remove existing symlink if present
    if [ -L "$TARGET_LINK" ]; then
        rm -f "$TARGET_LINK"
    fi
    # Create symbolic link
    ln -sf "$SOURCE_FILE" "$TARGET_LINK"
} || die "Failed to set up configuration link"


# Run bootstrap to set up env-config link
bootstrap_env_config

# POSIX-compatible generic whiptail menu helper
show_menu() {
    title="$1"; shift
    prompt="$1"; shift
    whiptail --title "$title" --menu "$prompt" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" "$@" 3>&1 1>&2 2>&3
}


# Function to update values stored in the rasqberry_environment.env file
do_select_environment_variable() {

  if [ ! -f "$ENV_FILE" ]; then
    whiptail --title "Error" --msgbox "Environment file not found!" 8 50
    return 1
  fi

  # Read and format environment file, excluding comments and empty lines
  ENV_VARS=$(grep -vE '^\s*#|^\s*$' "$ENV_FILE" | awk -F= '{print $1 " " $2}')

  # Create a menu with the environment variables
  FUN=$(whiptail --title "Select Environment Variable" --menu "Choose a variable to update" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" $(echo "$ENV_VARS" | awk '{print $1 " " $2}') 3>&1 1>&2 2>&3)
  RET=$?
  if [ $RET -eq 1 ]; then
    return 0
  elif [ $RET -eq 0 ]; then
    do_menu_update_environment_file "$FUN"
  fi
}


# Function to update values stored in the rasqberry_environment.env file
update_environment_file () {
  #check whether string is empty
  if [ -z "$2" ]||[ -z "$1" ]; then
    # whiptail message box to show error
    if [ "$INTERACTIVE" = true ]; then
      [ "$RQ_NO_MESSAGES" = false ] && whiptail --title "Error" --msgbox "Error: No value provided. Environment variable not updated" 8 78
    fi
  else
    # update environment file
    sed -i "s/^$1=.*/$1=$2/gm" "$ENV_FILE"
    # reload environment file
    . "$BIN_DIR/env-config.sh"
  fi
}

# Function to update values stored in the $ENV file
# $1 = variable name, $2 = value
do_menu_update_environment_file() {
  new_value=$(whiptail --inputbox "$1" "$WT_HEIGHT" "$WT_WIDTH" --title "Type in the new value" 3>&1 1>&2 2>&3)
  update_environment_file "$1" "$new_value"
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


# Generic installer for demos: name, git URL, marker file
install_demo() {
    NAME="$1"       # e.g. Quantum-Lights-Out or quantum-raspberry-tie
    GIT_URL="$2"    # e.g. $GIT_REPO_DEMO_QLO or $GIT_REPO_DEMO_QRT
    MARKER="$3"     # script or file that must exist in the clone

    DEST="$DEMO_ROOT/$NAME"
    if [ ! -f "$DEST/$MARKER" ]; then
        mkdir -p "$DEST"
        git clone --depth 1 "$GIT_URL" "$DEST"
        # ensure correct ownership
        if [ "$(stat -c '%U' "$DEMO_ROOT")" = "root" ]; then
            sudo chown -R "$SUDO_USER":"$SUDO_USER" "$DEMO_ROOT"
        fi
    fi
}

# Helper: run a demo in its directory using a pty for correct TTY behavior
run_demo() {
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
  ( trap '' INT; cd "$DEMO_DIR" && exec setsid script -qfc "$CMD" /dev/null ) &
  DEMO_PID=$!
  # Ask user when to stop
  whiptail --title "$DEMO_TITLE" --yesno "Demo is running. Select Yes to stop." 8 60
  # Restore terminal state before killing demo
  stty sane
  # Terminate the entire demo process group
  kill -TERM -"$DEMO_PID" 2>/dev/null || true
  wait "$DEMO_PID" 2>/dev/null || true
  # Restore original terminal settings
  stty "$OLD_STTY"
  # Final reset to clear any residual state
  reset
}

# Helper: run a non-interactive demo in the background without a pty
run_demo_bg() {
    DEMO_TITLE="$1"; shift
    DEMO_DIR="$1"; shift
    CMD="$*"
    OLD_STTY=$(stty -g)
    stty sane
    # Launch demo in its own session so we can kill the full process group
    ( trap '' INT; cd "$DEMO_DIR" && exec setsid $CMD ) &
    DEMO_PID=$!
    whiptail --title "$DEMO_TITLE" --yesno "Demo is running. Select Yes to stop." 8 60
    stty sane
    kill -TERM -"$DEMO_PID" 2>/dev/null || true
    wait "$DEMO_PID" 2>/dev/null || true
    stty "$OLD_STTY"
    reset
}

#set up for demo adding sense-hat
do_setup_quantum_demo_essential() {
    VARIABLE_NAME="QUANTUM_DEMO_ESSENTIALS_INSTALLED"

    # Check if the demo is already installed
    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" = "true" ]; then
        whiptail --msgbox "Quantum Demo Essentials is already installed." 20 60 1
        return 0
    fi

    # Update the value of QUANTUM_DEMO_ESSENTIALS_INSTALLED to true
    update_environment_file "$VARIABLE_NAME" "true"

    # Proceed with the installation
    FUN=$1
    update_environment_file "INTERACTIVE" "false"
    . "$VENV_ACTIVATE"
    apt update && apt full-upgrade
    #apt install -y python3-gi gir1.2-gtk-3.0 libcairo2-dev libgirepository1.0-dev python3-numpy python3-pil python3-pkg-resources python3-sense-emu sense-emu-tools sense-hat #moved to pi-gen stage-RQB2
    #pip install pygobject qiskit-ibm-runtime sense-emu qiskit_aer sense-hat #moved to qiskit install script
    #if  [ "$FUN" != "b:aer" ]; then
    #    python3 /home/$SUDO_USER/.local/bin/rq_set_qiskit_ibm_token.py
    #else
    #    echo "Skipping  IBM Qiskit Credential Setting as its local simulator"
    #fi
}

#Running quantum-raspberry-tie demo
do_rasp_tie_install() {
    # Ensure Quantum Raspberry-Tie demo is installed
    VARIABLE_NAME="QUANTUM_RASPBERRY_TIE_INSTALLED"
    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" != "true" ]; then
        install_demo "quantum-raspberry-tie" "$GIT_REPO_DEMO_QRT" "QuantumRaspberryTie.qk1.py"
        update_environment_file "$VARIABLE_NAME" "true"
        whiptail --title "Quantum Raspberry-Tie" --msgbox "Demo installed successfully." 8 60
    else
        whiptail --title "Quantum Raspberry-Tie" --msgbox "Demo already installed." 8 60
    fi
    DEMO_DIR="$DEMO_ROOT/quantum-raspberry-tie"
    RUN_OPTION=$1
    if  [ "$RUN_OPTION" != "b:aer" ]; then
      python3 "$BIN_DIR/rq_set_qiskit_ibm_token.py"
    else
      echo "Skipping  IBM Qiskit Credential Setting as its local simulator"
    fi
    run_demo "Quantum Raspberry-Tie Demo" "$DEMO_DIR" python3 "QuantumRaspberryTie.qk1.py" "-$RUN_OPTION"
    # Turn off LEDs when demo ends
    do_led_off
}

# Initial setup for RasQberry
# Sets PATH, LOCALE, create python venv
do_rqb_initial_config() {
  ( echo; echo '##### added for rasqberry #####';
  echo "export PATH=\"$BIN_DIR:$DEMO_ROOT/bin:\$PATH\"";
  # fix locale
  echo "LANG=en_GB.UTF-8\nLC_CTYPE=en_GB.UTF-8\nLC_MESSAGES=en_GB.UTF-8\nLC_ALL=en_GB.UTF-8" > /etc/default/locale
  ) >> "$USER_HOME/.bashrc" && . "$USER_HOME/.bashrc"
  # create venv for Qiskit
  sudo -u $SUDO_USER -H -E -- sh -c 'python3 -m venv /home/'$SUDO_USER'/'$REPO'/venv/'$STD_VENV
  if [ "$INTERACTIVE" = true ]; then
      [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "initial config completed" 20 60 1
  fi
}

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


#Turn off all LEDs
do_led_off() {
  . "$VENV_ACTIVATE"
  python3 "$BIN_DIR/turn_off_LEDs.py"
}

# Generic runner for LED demos
run_led_demo() {
  DEMO_TITLE="$1"; shift
  SCRIPT_NAME="$1"; shift
  # Activate Python environment
  . "$VENV_ACTIVATE"
  # Run demo in background and allow clean stop
  run_demo_bg "$DEMO_TITLE" "$BIN_DIR" python3 "$SCRIPT_NAME"
  # Ensure LEDs are off afterwards
  do_led_off
}


# Generic runner for Quantum-Lights-Out demo (POSIX sh compatible)
run_qlo_demo() {
    MODE="${1:-}"  # empty for GUI, "console" for console mode
    # Activate virtual environment
    . "$VENV_ACTIVATE"
    DEMO_DIR="$DEMO_ROOT/Quantum-Lights-Out"
    DEMO_SCRIPT="$DEMO_DIR/lights_out.py"
    # Ensure installed
    if [ ! -f "$DEMO_SCRIPT" ]; then
        do_qlo_install
    fi
    if [ ! -f "$DEMO_SCRIPT" ]; then
        whiptail --msgbox "Lights Out script missing. Aborting." 20 60 1
        return 1
    fi
    # Launch appropriate mode
    if [ "$MODE" = "console" ]; then
        run_demo "Quantum Lights Out Demo (console)" "$DEMO_DIR" python3 lights_out.py --console
    else
        run_demo "Quantum Lights Out Demo" "$DEMO_DIR" python3 lights_out.py
    fi
    # Turn off LEDs when demo ends
    do_led_off
}


do_select_led_option() {
    while true; do
        FUN=$(show_menu "RasQberry: LEDs" "LED options" \
           OFF "Turn off all LEDs" \
           simple "Simple LED Demo" \
           IBM "IBM LED Demo") || break
        case "$FUN" in
            "OFF" ) do_led_off || { handle_error "Turning off all LEDs failed."; continue; } ;;
            "simple" ) run_led_demo "Simple LED Demo" neopixel_spi_simpletest.py || { handle_error "Simple LED demo failed."; continue; } ;;
            "IBM" ) run_led_demo "IBM LED Demo" neopixel_spi_IBMtestFunc.py || { handle_error "LED IBM demo failed."; continue; } ;;
            *)
                break
                ;;
        esac
    done
}


# Install Quantum-Lights-Out demo if needed
do_qlo_install() {
    VARIABLE_NAME="QUANTUM_LIGHTS_OUT_INSTALLED"
    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" != "true" ]; then
        install_demo "Quantum-Lights-Out" "$GIT_REPO_DEMO_QLO" "lights_out.py"
        update_environment_file "$VARIABLE_NAME" "true"
        whiptail --title "Quantum Lights Out" --msgbox "Demo installed successfully." 8 60
    else
        whiptail --title "Quantum Lights Out" --msgbox "Demo already installed." 8 60
    fi
}


do_select_qlo_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Quantum Lights Out" "Options" \
           QLO  "Run Demo" \
           QLOC "Run Demo (console)") || break
        case "$FUN" in
            "QLO"  ) run_qlo_demo      || { handle_error "QLO demo failed."; continue; } ;;
            "QLOC" ) run_qlo_demo console    || { handle_error "QLO console demo failed."; continue; } ;;
            *)
                break
                ;;
        esac
    done
}

do_select_qrt_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Quantum Raspberry-Tie" "Backend options" \
           b:aer       "Local Aer simulator" \
           b:aer_noise "Aer with noise model" \
           b:least     "Least busy real backend" \
           b:custom    "Custom backend or option") || break
        case "$FUN" in
            "b:aer" ) do_rasp_tie_install $FUN || { handle_error "Rasqberry Tie installation failed."; continue; } ;;
            "b:aer_noise") do_rasp_tie_install $FUN || { handle_error "Rasqberry Tie installation failed."; continue; } ;;
            "b:least") do_rasp_tie_install $FUN || { handle_error "Rasqberry Tie installation failed."; continue; } ;;
            "b:custom")
                CUSTOM_OPTION=$(whiptail --inputbox "Enter your custom backend or option:" 8 50 3>&1 1>&2 2>&3)
                exitstatus=$?
                if [ $exitstatus = 0 ]; then
                    do_rasp_tie_install $CUSTOM_OPTION || { handle_error "Rasqberry Tie installation failed."; continue; }
                else
                    echo "You chose to cancel. Demo will launch with Local Simulator"
                    break
                fi
                ;;
            *)
                break
                ;;
        esac
    done
}


do_quantum_demo_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Quantum Demos" "Select demo category" \
       LED  "Test LEDs" \
       QLO  "Quantum-Lights-Out Demo" \
       QRT  "Quantum Raspberry-Tie") || break
    case "$FUN" in
      LED)  do_select_led_option    || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option    || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option    || { handle_error "Failed to open QRT options."; continue; } ;;
      *)    handle_error "Programmer error: unrecognized Quantum Demo option $FUN."; continue ;;
    esac
  done
}

do_rasqberry_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Main Menu" "System Options" \
       QD  "Quantum Demos" \
       UEF "Update Env File") || break
    case "$FUN" in
      QD)  do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      UEF) do_select_environment_variable || { handle_error "Failed to update environment file."; continue; } ;;
      *)   handle_error "Programmer error: unrecognized main menu option $FUN."; continue ;;
    esac
  done
}


# Function for graceful error handling in menus
handle_error() {
    local MSG="$1"
    whiptail --title "Error" --msgbox "$MSG" 8 60
    return 1
}