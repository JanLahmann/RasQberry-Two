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
ENV_CONFIG_FILE="/home/${SUDO_USER:-$USER}/${RQB2_CONFDIR:-.local/config}/env-config.sh"
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

# -----------------------------------------------------------------------------
# 1. Environment & Bootstrap
# -----------------------------------------------------------------------------
bootstrap_env_config() {
    SOURCE_FILE="$USER_HOME/$RQB2_CONFDIR/env-config.sh"
    TARGET_LINK="$BIN_DIR/env-config.sh"
    if [ -L "$TARGET_LINK" ]; then
        rm -f "$TARGET_LINK"
    fi
    ln -sf "$SOURCE_FILE" "$TARGET_LINK"
} || die "Failed to set up configuration link"

bootstrap_env_config

# -----------------------------------------------------------------------------
# 2. Helpers
# -----------------------------------------------------------------------------

show_menu() {
    title="$1"; shift
    prompt="$1"; shift
    whiptail --title "$title" --menu "$prompt" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" "$@" 3>&1 1>&2 2>&3
}

install_demo() {
    NAME="$1"
    GIT_URL="$2"
    MARKER="$3"
    ENV_VAR="$4"
    TITLE="$5"
    FORCE="$6"

    DEST="$DEMO_ROOT/$NAME"

    if [ "$FORCE" = "--force" ] && [ -d "$DEST" ]; then
        echo "[INFO] Forcing reinstallation of $NAME..."
        rm -rf "$DEST"
    fi

    if [ -d "$DEST/.git" ]; then
        echo "[INFO] Pulling latest changes for $NAME..."
        cd "$DEST" && git pull --rebase
        update_environment_file "$ENV_VAR" "true"
        return 0
    fi

    if [ ! -f "$DEST/$MARKER" ]; then
        mkdir -p "$DEST"
        if git clone --depth 1 "$GIT_URL" "$DEST"; then
            if [ "$(stat -c '%U' "$DEMO_ROOT")" = "root" ]; then
                sudo chown -R "$SUDO_USER":"$SUDO_USER" "$DEMO_ROOT"
            fi
            update_environment_file "$ENV_VAR" "true"
            [ "$RQ_NO_MESSAGES" = false ] && whiptail --title "$TITLE" --msgbox "Demo installed successfully." 8 60
        else
            rm -rf "$DEST"
            whiptail --title "Installation Error" --msgbox "Failed to download $TITLE demo.\n\nPossible causes:\n- No internet connection\n- Repository unavailable\n- Network firewall blocking access\n\nPlease check your connection and try again." 12 70
            return 1
        fi
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
                 "QuantumRaspberryTie.qk1.py" "QUANTUM_RASPBERRY_TIE_INSTALLED" \
                 "Quantum Raspberry-Tie"
}

# Install Grok Bloch demo if needed
do_grok_bloch_install() {
    install_demo "grok-bloch" "$GIT_REPO_DEMO_GROK_BLOCH" \
                 "index.html" "GROK_BLOCH_INSTALLED" \
                 "Grok Bloch Sphere"
}

# Helper: Install Dice Game if needed
install_dice_game() {
    install_demo "schrodinger-dice" "$GIT_REPO_DEMO_DICE" \
                 "dice_game_main.py" "SCHRODINGER_DICE_INSTALLED" \
                 "Schrodinger's Dice"
}

# Helper: Install Entanglement Game if needed
install_entg_game() {
    install_demo "entanglement-game" "$GIT_REPO_ENTANG" \
                 "entanglement_game_main.py" "ENTANGLEMENT_GAME_INSTALLED" \
                 "Entanglement Game"
}

# Helper: Install Zeno Game if needed
install_zeno_game() {
    install_demo "zeno-game" "$GIT_REPO_ZENO" \
                 "zeno_gui.py" "ZENO_GAME_INSTALLED" \
                 "Zeno Game"
}

# Helper: Install phg Game if needed
install_phg() {
    install_demo "phg-game" "$GIT_REPO_PHG" \
                 "phg_main.py" "PHG_INSTALLED" \
                 "Period Hunter Game"
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
    run_demo "Quantum Raspberry-Tie Demo" "$DEMO_DIR" python3 "QuantumRaspberryTie.qk1.py" "-${RUN_OPTION}"
    # Turn off LEDs when demo ends
    do_led_off
}

# Run grok-bloch demo (ensures install first)
run_grok_bloch_demo() {
    # Ensure installation
    do_grok_bloch_install
    # Launch the demo using the dedicated launcher script
    "$BIN_DIR/rq_grok_bloch.sh"
}

# Run quantum fractals demo
run_fractals_demo() {
    # Launch the fractals demo using the dedicated launcher script
    "$BIN_DIR/fractals.sh"
}

# Run Dice Game (ensures install first)
run_dice_game_demo() {
    install_dice_game
    DEMO_DIR="$DEMO_ROOT/schrodinger-dice"
    # Run and capture output
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 dice_game_main.py )

    # # Show the result in a message box
    # whiptail --title "Schrodinger's Dice Game - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "===== Schrodinger's Dice Game - Result ====="
    echo "$DEMO_OUTPUT"

    do_led_off
}

# Dice Game Menu (if you'd like extra options later)
do_select_dice_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Schrodinger's Dice" "Choose a mode" \
           RUN "Play Dice Game") || break
        case "$FUN" in
            RUN) run_dice_game_demo || { handle_error "Dice Game failed."; continue; } ;;
            *) break ;;
        esac
    done
}

run_entg_game_demo() {
    install_entg_game
    DEMO_DIR="$DEMO_ROOT/entanglement-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 entanglement_game_main.py )
    
    # Show the result in a message box
    # whiptail --title "Entanglement Game - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "$DEMO_OUTPUT"
    do_led_off
}

do_select_entg_option() {
    while true; do
        FUN=$(show_menu "RasQberry: Quantum Entanglement" "Choose a mode" \
           RUN "Play Entanglement Game") || break
        case "$FUN" in
            RUN) run_entg_game_demo || { handle_error "Entanglement Game failed."; continue; } ;;
            *) break ;;
        esac
    done
}

run_zeno_game_demo() {
    install_zeno_game
    DEMO_DIR="$DEMO_ROOT/zeno-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 zeno_gui.py )
    
    # Show the result in a message box
    #whiptail --title "Zeno Game - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "$DEMO_OUTPUT"
    do_led_off
}

run_phg_demo() {
    install_phg
    DEMO_DIR="$DEMO_ROOT/phg-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 phg_main.py )
    
    # Show the result in a message box
    # whiptail --title "Period Hunter Game - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "$DEMO_OUTPUT"
    do_led_off
}

# Helper: Install phg Game if needed
install_qff() {
    install_demo "QFF-game" "$GIT_REPO_QFF" \
                 "qff_main.py" "QFF_INSTALLED" \
                 "Quantum Factor Finder"
}

run_qff_demo() {
    install_qff
    DEMO_DIR="$DEMO_ROOT/QFF-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 qff_main.py )
    
    # Show the result in a message box
    # whiptail --title "Quantum Factor Finder - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "$DEMO_OUTPUT"
    do_led_off
}

# Helper: Install phg Game if needed
install_tg() {
    install_demo "TG-game" "$GIT_REPO_TG" \
                 "teleportation.py" "TG_INSTALLED=true" \
                 "Teleportation Game"
}

run_tg_demo() {
    install_tg
    DEMO_DIR="$DEMO_ROOT/TG-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 teleportation.py )
    
    # Show the result in a message box
    #whiptail --title "Teleportation - Result" --msgbox "$DEMO_OUTPUT" 12 60
    echo "$DEMO_OUTPUT"
    do_led_off
}


# Helper: Install phg Game if needed
install_dw() {
    install_demo "DW-game" "$GIT_REPO_DW" \
                 "dice_game_main.py" "DW_INSTALLED=true" \
                 "Dice Game with Watson"
}

run_dw_demo() {
    install_dw
    DEMO_DIR="$DEMO_ROOT/DW-game"
    
    # Run and capture output just like the Dice game
    DEMO_OUTPUT=$( . "$VENV_ACTIVATE"; cd "$DEMO_DIR"; python3 dice_game_main.py )
    
    echo "===== Dice Game with Watson - Result ====="
    echo "$DEMO_OUTPUT"
    
    do_led_off
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

  # Read and format environment file, excluding comments and empty lines
  ENV_VARS=$(grep -vE '^\s*#|^\s*$' "$ENV_FILE" | awk -F= '{print $1 " " $2}')

  # Create a menu with the environment variables
  FUN=$(whiptail --title "Select Environment Variable" --menu "Choose a variable to update" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" $(echo "$ENV_VARS" | awk '{print $1 " " $2}') 3>&1 1>&2 2>&3)
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
       GRB  "Grok Bloch Sphere" \
       FRC  "Quantum Fractals" \
       DICE "Schrodinger's Dice Game" \
       ENTG "Quantum Entanglement Game" \
       ZENO "Zeno Measurement Game" \
       PHG  "Period Hunter Game" \
       QFF  "Quantum Factor Finder" \
       TG   "Teleportation Game" \
       DW   "Dice with Watson" \
       STOP "Stop last running demo and clear LEDs") || break
    case "$FUN" in
      LED)  do_select_led_option    || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option    || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option    || { handle_error "Failed to open QRT options."; continue; } ;;
      GRB)  run_grok_bloch_demo     || { handle_error "Failed to run Grok Bloch demo."; continue; } ;;
      FRC)  run_fractals_demo       || { handle_error "Failed to run Quantum Fractals demo."; continue; } ;;
      DICE) do_select_dice_option   || { handle_error "Failed to open Dice Game options."; continue; } ;;
      ENTG) run_entg_game_demo      || { handle_error "Failed to run Entanglement Game."; continue; } ;;
      ZENO) run_zeno_game_demo      || { handle_error "Failed to run Zeno Game."; continue; } ;;
      PHG)  run_phg_demo            || { handle_error "Failed to run PHG Game."; continue; } ;;
      QFF)  run_qff_demo            || { handle_error "Failed to run QFF Game."; continue; } ;;
      TG)   run_tg_demo             || { handle_error "Failed to run QFF Game."; continue; } ;;
      DW)   run_dw_demo             || { handle_error "Failed to run DW Game."; continue; } ;;
      STOP) stop_last_demo          || { handle_error "Failed to stop demo."; continue; } ;;
      *)    handle_error "Programmer error: unrecognized Quantum Demo option ${FUN}."; continue ;;
    esac
  done
}

# -----------------------------------------------------------------------------
# 3g) Main Raspi Config Menu
# -----------------------------------------------------------------------------

do_rasqberry_menu() {
  while true; do
    FUN=$(show_menu "RasQberry: Main Menu" "System Options" \
       QD  "Quantum Demos" \
       UEF "Update Env File") || break
    case "$FUN" in
      QD)  do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      UEF) do_select_environment_variable || { handle_error "Failed to update environment file."; continue; } ;;
      *)   handle_error "Programmer error: unrecognized main menu option ${FUN}."; continue ;;
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
