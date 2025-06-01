#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'


# installation of Qiskit (latest version)
#

#If no parameter passed
if [ "${PIGEN}" == "true" ]; then
  # if images building parameter passed 
  .  /home/"${FIRST_USER_NAME}"/$REPO/venv/$STD_VENV/bin/activate
else
   # Load environment variables
  . $HOME/.local/bin/env-config.sh
  . $HOME/$REPO/venv/$STD_VENV/bin/activate
fi

export STARTDATE=`date`
echo; echo; echo "Install Qiskit (latest version)"; echo;

pip install 'qiskit[all]'
pip install qiskit_ibm_runtime qiskit_aer
pip install adafruit-circuitpython-neopixel-spi rpi_ws281x pygobject qiskit-ibm-runtime sense-emu qiskit_aer sense-hat celluloid selenium webdriver-manager


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`
