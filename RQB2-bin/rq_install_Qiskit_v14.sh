#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Installation of Qiskit v1.4 (minimal)
#

#If no parameter passed
if [ "${PIGEN}" == "true" ]; then
  # if images building parameter passed 
  .  /home/"${FIRST_USER_NAME}"/$REPO/venv/$STD_VENV_14/bin/activate
else
   # Load environment variables
  . $HOME/.local/bin/env-config.sh
  . $HOME/$REPO/venv/$STD_VENV_14/bin/activate
fi

export STARTDATE=`date`
echo; echo; echo "Install Qiskit v1.4 (minimal)"; echo;

# Install specific Qiskit 1.4 version with minimal dependencies
pip install 'qiskit==1.4.*' || { echo "Failed to install Qiskit 1.4"; exit 1; }
pip install 'qiskit-aer==0.15.*' || { echo "Failed to install qiskit-aer"; exit 1; }
pip install 'qiskit-ibm-runtime==0.30.*' || { echo "Failed to install qiskit-ibm-runtime"; exit 1; }

# Essential packages only (no hardware-specific dependencies for now)
pip install matplotlib numpy pillow || { echo "Failed to install essential packages"; exit 1; }

pip3 list | grep qiskit

echo; echo "start Qiskit v1.4 install: " $STARTDATE &&
echo "end   Qiskit v1.4 install: " `date`