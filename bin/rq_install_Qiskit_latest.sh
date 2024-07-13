#!/bin/bash
#
# installation of Qiskit (latest version)
#

# Load environment variables
. $HOME/.local/bin/env-config.sh


export STARTDATE=`date`
echo; echo; echo "Install Qiskit (latest version)"; echo;

. $HOME/$REPO/venv/$STD_VENV/bin/activate
pip install 'qiskit[all]'


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`