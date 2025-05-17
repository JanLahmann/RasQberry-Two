#!/bin/sh

# ******Added By Rishi as part of rasQberry-two project*******
SOURCE_FILE=/home/$SUDO_USER/"$RQB2_CONFDIR/env-config.sh"
TARGET_LINK=/home/$SUDO_USER/.local/bin/env-config.sh
# Check if the symbolic link already exists
if [ -L "$TARGET_LINK" ]; 
then 
    # If the link exist remove it
    sudo rm $TARGET_LINK
    echo "Symbolic link Removed"
else
    echo "Symbolic link doesn't exists"
fi
# ***********end changes************
# Create symbolic link 
sudo ln -sf "$SOURCE_FILE" "$TARGET_LINK"

# Load environment variables
. /home/$SUDO_USER/.local/bin/env-config.sh

# Function to update values stored in the rasqberry_environment.env file
do_select_environment_variable() {
  ENV_FILE="/home/$SUDO_USER/$RQB2_CONFDIR/rasqberry_environment.env"

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
    sed -i "s/^$1=.*/$1=$2/gm" /home/$SUDO_USER/$RQB2_CONFDIR/rasqberry_environment.env
    # reload environment file
    . /home/$SUDO_USER/.local/bin/env-config.sh
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
    ENV_FILE="/home/$SUDO_USER/$RQB2_CONFDIR/rasqberry_environment.env"
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

# Helper: run a demo in a directory and stop it via a dialog instead of Ctrl-C
run_demo() {
  local DEMO_TITLE="$1"; shift
  local DEMO_DIR="$1"; shift
  # Launch the demo in its directory, ignoring SIGINT so only this script handles it
  ( trap '' SIGINT; cd "$DEMO_DIR" && exec "$@" ) &
  local DEMO_PID=$!
  # Prompt user to stop the demo
  whiptail --title "$DEMO_TITLE" --msgbox "Demo is running. Click OK to stop." 8 60
  # Terminate the demo process
  kill "$DEMO_PID" 2>/dev/null || true
  wait "$DEMO_PID" 2>/dev/null || true
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
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    apt update && apt full-upgrade
    apt install -y python3-gi gir1.2-gtk-3.0 libcairo2-dev libgirepository1.0-dev python3-numpy python3-pil python3-pkg-resources python3-sense-emu sense-emu-tools sense-hat
    pip install pygobject qiskit-ibm-runtime sense-emu qiskit_aer sense-hat
    if  [ "$FUN" != "b:aer" ]; then
        python3 /home/$SUDO_USER/.local/bin/rq_set_qiskit_ibm_token.py
    else
        echo "Skipping  IBM Qiskit Credential Setting as its local simulator"
    fi
}

#Running quantum-raspberry-tie demo
do_rasp_tie_install() {
    VARIABLE_NAME="QUANTUM_RASPBERRY_TIE_INSTALLED"

    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" != "true" ]; then
        # Update the value of QUANTUM_RASPBERRY_TIE_INSTALLED to true
        update_environment_file "$VARIABLE_NAME" "true"

        # Proceed with the installation
        . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
        if [ ! -f "/home/$SUDO_USER/$REPO/demos/quantum-raspberry-tie/QuantumRaspberryTie.qk1.py" ]; then
            mkdir -p /home/$SUDO_USER/$REPO/demos/quantum-raspberry-tie
            export CLONE_DIR_DEMO1="/home/$SUDO_USER/$REPO/demos/quantum-raspberry-tie"
            git clone ${GIT_REPO_DEMO_QRT} ${CLONE_DIR_DEMO1}
        fi
        FOLDER_PATH="/home/$SUDO_USER/$REPO/demos"
        if [ "$(stat -c '%U' "$FOLDER_PATH")" = "root" ]; then
            sudo chown -R "$SUDO_USER":"$SUDO_USER" "$FOLDER_PATH"
        fi
        if [ ! -f "/home/$SUDO_USER/$REPO/demos/quantum-raspberry-tie/QuantumRaspberryTie.qk1.py" ]; then
            whiptail --msgbox "Quantum Raspberry Tie script not found. Please ensure it's installed in the demos directory." 20 60 1
            return 1
        fi
    else
        whiptail --msgbox "Quantum Raspberry Tie demo is already installed. Launching demo now." 20 60 1
    fi
    RUN_OPTION=$1
    run_demo "Quantum Raspberry-Tie Demo" "/home/$SUDO_USER/$REPO/demos/quantum-raspberry-tie" python3 "QuantumRaspberryTie.qk1.py" "-$RUN_OPTION"
    # Turn off LEDs when demo ends
    do_led_off
}

# Initial setup for RasQberry
# Sets PATH, LOCALE, create python venv
do_rqb_initial_config() {
  ( echo; echo '##### added for rasqberry #####';
  echo 'export PATH=/home/'$SUDO_USER'/.local/bin:/home/'$SUDO_USER'/'$REPO'/demos/bin:$PATH';
  # fix locale
  echo "LANG=en_GB.UTF-8\nLC_CTYPE=en_GB.UTF-8\nLC_MESSAGES=en_GB.UTF-8\nLC_ALL=en_GB.UTF-8" > /etc/default/locale
  ) >> /home/$SUDO_USER/.bashrc && . /home/$SUDO_USER/.bashrc
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
  sudo -u $SUDO_USER -H -- sh -c '/home/'$SUDO_USER'/.local/bin/rq_install_Qiskit'$1'.sh'
  if [ "$INTERACTIVE" = true ] && ! [ "$2" = silent ]; then
    [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "Qiskit $1 installed" 20 60 1
  fi
}


do_rqb_qiskit_menu() {
  FUN=$(whiptail --title "Raspberry Pi Software Configuration Tool (raspi-config)" --menu "Install Qiskit" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" --cancel-button Back --ok-button Select \
    "Qnew Qiskit"      "Install Qiskit (latest version)" \
    "Q0101 Qiskit 1.1" "Install Qiskit v1.1" \
    "Q0100 Qiskit 1.0     " "Install Qiskit v1.0" \
    3>&1 1>&2 2>&3)
  RET=$?
  if [ $RET -eq 1 ]; then
    return 0
  elif [ $RET -eq 0 ]; then
    case "$FUN" in
      Q0101\ *) do_rqb_install_qiskit 0101 ;;
      Q0100\ *) do_rqb_install_qiskit 0100 ;;
      Qnew\ *) do_rqb_install_qiskit _latest ;;
      *) whiptail --msgbox "Programmer error: unrecognized option" 20 60 1 ;;
    esac || whiptail --msgbox "There was an error running option $FUN" 20 60 1
  fi
}


#Enable LEDs
do_led_install() {
    VARIABLE_NAME="TEST_LED_INSTALLED"

    # Check if the demo is already installed
    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" = "true" ]; then
        whiptail --msgbox "LED Test demo is already installed." 20 60 1
        return 0
    fi

    # Update the value of TEST_LED_INSTALLED to true
    update_environment_file "$VARIABLE_NAME" "true"

    # Proceed with the installation
  . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
  pip install adafruit-circuitpython-neopixel-spi
}

#Turn off all LEDs
do_led_off() {
  . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
  python3 /home/$SUDO_USER/.local/bin/turn_off_LEDs.py
}

#Simple LEDs demo
do_led_simple() {
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    run_demo "Simple LED Demo" "/home/$SUDO_USER/.local/bin" python3 "neopixel_spi_simpletest.py"
    # Turn off LEDs when demo ends
    do_led_off
}

#IBM LED demo
do_led_ibm() {
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    run_demo "IBM LED Demo" "/home/$SUDO_USER/.local/bin" python3 "neopixel_spi_IBMtestFunc.py"
    # Turn off LEDs when demo ends
    do_led_off
}


do_select_led_option() {
    while true; do
        FUN=$(whiptail --title "Raspberry Pi LED (raspi-config)" --menu "LED options" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" --cancel-button Back --ok-button Select \
        "LI" "Enable LEDs" \
        "OFF" "Turn off all LEDs" \
        "simple" "simple LED demo" \
        "IBM" "Display IBM on LEDs" \
        3>&1 1>&2 2>&3)
        RET=$?
        if [ $RET -ne 0 ]; then
            break
        fi
        case "$FUN" in
            "LI" ) do_led_install || handle_error "LED Installation Failed." ;;
            "OFF" ) do_led_off || handle_error "Turning off all LEDs Failed." ;;
            "simple" ) do_led_simple || handle_error "Simple LED demo Failed." ;;
            "IBM" ) do_led_ibm || handle_error "LED IBM Failed." ;;
            *)
                break
                ;;
        esac
    done
}


#Install Quantum-Lights-Out demo
do_qlo_install() {
    VARIABLE_NAME="QUANTUM_LIGHTS_OUT_INSTALLED"

    # Check if the demo is already installed
    INSTALLED=$(check_environment_variable "$VARIABLE_NAME")
    if [ "$INSTALLED" = "true" ]; then
        whiptail --msgbox "Quantum Lights Out demo is already installed." 20 60 1
        return 0
    fi

    # Update the value of QUANTUM_LIGHTS_OUT_INSTALLED to true
    update_environment_file "$VARIABLE_NAME" "true"

    # Proceed with the installation
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        mkdir -p /home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out
        export CLONE_DIR_DEMO_QLO="/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out"
        git clone ${GIT_REPO_DEMO_QLO} ${CLONE_DIR_DEMO_QLO}
    fi
    FOLDER_PATH="/home/$SUDO_USER/$REPO/demos"
    # Get the current logged-in user
    CURRENT_USER=$(whoami)
    # Check if the folder is owned by root
    if [ "$(stat -c '%U' "$FOLDER_PATH")" = "root" ]; then
      # Change the ownership to the logged-in user
      sudo chown -R "$SUDO_USER":"$SUDO_USER" "$FOLDER_PATH"
     # echo "Ownership of $FOLDER_PATH changed to $CURRENT_USER."
    fi
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        whiptail --msgbox "Quantum Raspberry Tie script not found. Please ensure it's installed in the demos directory." 20 60 1
        return 1
    fi
}

do_qlo_run() {
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        do_qlo_install
    fi
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        whiptail --msgbox "Quantum Raspberry Tie script not found. Please ensure it's installed in the demos directory." 20 60 1
        return 1
    fi
    run_demo "Quantum Lights Out Demo" "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out" python3 "lights_out.py"
    # Turn off LEDs when demo ends
    do_led_off
}

do_qloc_run() {
    . /home/$SUDO_USER/$REPO/venv/$STD_VENV/bin/activate
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        do_qlo_install
    fi
    if [ ! -f "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out/lights_out.py" ]; then
        whiptail --msgbox "Quantum Raspberry Tie script not found. Please ensure it's installed in the demos directory." 20 60 1
        return 1
    fi
    run_demo "Quantum Lights Out Demo (console)" "/home/$SUDO_USER/$REPO/demos/Quantum-Lights-Out" python3 "lights_out.py" --console
    # Turn off LEDs when demo ends
    do_led_off
}


do_select_qlo_option() {
    while true; do
        FUN=$(whiptail --title "Quantum-Lights-Out Demo" --menu "Options" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" --cancel-button Back --ok-button Select \
        "QLOI" "Install Demo" \
        "QLO" "Run Demo" \
        "QLOC" "Run Demo (console)" \
        3>&1 1>&2 2>&3)
        RET=$?
        if [ $RET -ne 0 ]; then
            break
        fi
        case "$FUN" in
            "QLOI" ) do_qlo_install || handle_error "QLO Demo Installation Failed." ;;
            "QLO"  ) do_qlo_run      || handle_error "QLO Demo Failed." ;;
            "QLOC" ) do_qloc_run    || handle_error "QLO Console Demo Failed." ;;
            *)
                break
                ;;
        esac
    done
}

do_select_qrt_option() {
    while true; do
        FUN=$(whiptail --title "Raspberry Pi Quantum-Raspberry-Tie Option Select  (raspi-config)" --menu "Backend options" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" --cancel-button Back --ok-button Select \
        "b:aer" "Spins up a local Aer simulator" \
        "b:aer_noise" "Spins up a local Aer simulator with a noise model" \
        "b:least" "Code will run on the least busy *real* backend for your account" \
        "b:custom" "Enter a custom backend or option" \
        3>&1 1>&2 2>&3)
        RET=$?
        if [ $RET -ne 0 ]; then
            break
        fi
        case "$FUN" in
            "b:aer" ) do_rasp_tie_install $FUN || handle_error "Rasqberry Tie Demo Installation Failed." ;;
            "b:aer_noise") do_rasp_tie_install $FUN || handle_error "Rasqberry Tie Demo Installation Failed." ;;
            "b:least") do_rasp_tie_install $FUN || handle_error "Rasqberry Tie Demo Installation Failed." ;;
            "b:custom")
                CUSTOM_OPTION=$(whiptail --inputbox "Enter your custom backend or option:" 8 50 3>&1 1>&2 2>&3)
                exitstatus=$?
                if [ $exitstatus = 0 ]; then
                    do_rasp_tie_install $CUSTOM_OPTION || handle_error "Rasqberry Tie Demo Installation Failed."
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
    FUN=$(whiptail --title "Raspberry Pi Quantum Demo (raspi-config)" --menu "Install Quantum Demo" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" --cancel-button Back --ok-button Select \
          "LED" "test LEDs" \
          "QLO Demo" "Quantum-Lights-Out Demo" \
          "QRT Demo" "quantum-raspberry-tie" \
          "SQE" "Setup-Quantum-Demo-Essentials"\
     3>&1 1>&2 2>&3)
    RET=$?
    if [ $RET -ne 0 ]; then
      break
    fi
    case "$FUN" in
      LED) do_select_led_option ;;
      QLO\ *) do_select_qlo_option ;;
      QRT\ *) do_select_qrt_option ;;
      SQE) do_setup_quantum_demo_essential ;;
      *) whiptail --msgbox "Programmer error: unrecognized option" 20 60 1 ;;
    esac || whiptail --msgbox "There was an error running option $FUN" 20 60 1
  done
}

do_rasqberry_menu() {
  while true; do
    FUN=$(whiptail --title "Raspberry Pi Software Configuration Tool (raspi-config)" --menu "System Options" $WT_HEIGHT $WT_WIDTH $WT_MENU_HEIGHT --cancel-button Back --ok-button Select \
      "QD Quantum Demos"  "Install Quantum Demos"\
      "UEF Update Environment File" "Update the environment file" \
      3>&1 1>&2 2>&3)
    RET=$?
    if [ $RET -ne 0 ]; then
      break
    fi
    case "$FUN" in
      QD\ *) do_quantum_demo_menu;;
      UEF\ *) do_select_environment_variable ;;
      *) whiptail --msgbox "Programmer error: unrecognized option" 20 60 1 ;;
    esac || whiptail --msgbox "There was an error running option $FUN" 20 60 1
  done
}
# Function for graceful error handlings
handle_error() {
    echo "Error: $1"
    echo "Exiting with error."
    exit 1
}