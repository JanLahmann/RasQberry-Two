#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'


# installation of Qiskit (latest version)
#

# Check if running in pi-gen build environment
# Use parameter expansion to provide default if PIGEN is unset
if [ "${PIGEN:-false}" == "true" ]; then
  # Running in pi-gen: use build-time paths
  .  /home/"${FIRST_USER_NAME}"/$REPO/venv/$STD_VENV/bin/activate
else
  # Running on live system: load environment variables
  . /usr/config/rasqberry_env-config.sh
  . $HOME/$REPO/venv/$STD_VENV/bin/activate
fi

export STARTDATE=`date`
echo; echo; echo "Install Qiskit (latest version)"; echo;

pip install 'qiskit[all]'
pip install qiskit_ibm_runtime qiskit_aer
pip install adafruit-blinka adafruit-circuitpython-neopixel pygobject qiskit-ibm-runtime sense-emu qiskit_aer sense-hat celluloid selenium webdriver-manager matplotlib numpy pillow


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`
