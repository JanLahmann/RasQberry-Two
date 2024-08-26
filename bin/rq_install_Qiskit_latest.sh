#!/bin/bash
#
# installation of Qiskit (latest version)
#

#If no parameter passed
if [ -z "$1" ]; then
   # Load environment variables
  . $HOME/.local/bin/env-config.sh
  . $HOME/$REPO/venv/$STD_VENV/bin/activate
else
  # if images building parameter passed 
  .  /home/"${FIRST_USER_NAME}"/$REPO/venv/$STD_VENV/bin/activate
fi

export STARTDATE=`date`
echo; echo; echo "Install Qiskit (latest version)"; echo;

pip install 'qiskit[all]'


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`
