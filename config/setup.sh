#!/bin/sh

############# CONFIGURATION METHODS #############

### Initial

# Initial setup for RasQberry
# Sets LOCALE, changes splash screen
do_rq_initial_config() {
  ( echo; echo '##### added for rasqberry #####';
  echo 'export PATH=/home/pi/.local/bin:/home/pi/RasQberry/demos/bin:$PATH';
  ) >> /home/pi/.bashrc && . /home/pi/.bashrc
  if [ "$INTERACTIVE" = true ]; then
      [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "initial config completed" 20 60 1
  fi
}

# Update RasQberry and create swapfile
do_rqb_system_update() {
  sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
  /etc/init.d/dphys-swapfile stop
  /etc/init.d/dphys-swapfile start
  apt update
  apt -y full-upgrade
}

do_rasqberry_menu() {
  FUN=$(whiptail --title "Raspberry Pi Software Configuration Tool (raspi-config)" --menu "System Options" $WT_HEIGHT $WT_WIDTH $WT_MENU_HEIGHT --cancel-button Back --ok-button Select \
    "IC Initial Config" "Basic configurations (PATH, LOCALE, Python venv & Packages, etc)" \
    "SU System Update " "Update the system and create swapfile" \
    "IQ Qiskit Install" "Install latest version of Qiskit" \
    3>&1 1>&2 2>&3)
  RET=$?
  if [ $RET -eq 1 ]; then
    return 0
  elif [ $RET -eq 0 ]; then
    case "$FUN" in
      IC\ *) do_rqb_initial_config ;;
      SU\ *) do_rqb_system_update ;;
#      IQ\ *) do_rqb_install_qiskit ;;
      *) whiptail --msgbox "Programmer error: unrecognized option" 20 60 1 ;;
    esac || whiptail --msgbox "There was an error running option $FUN" 20 60 1
  fi
}