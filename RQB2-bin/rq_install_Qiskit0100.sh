#!/bin/bash
#
# installation of Qiskit 1.0
#

# Load environment variables
. $HOME/.local/bin/env-config.sh


export STARTDATE=`date`
echo; echo; echo "Install Qiskit 1.0"; echo;

. $HOME/$REPO/venv/$STD_VENV/bin/activate
pip install --prefer-binary  'qiskit[all]==1.0.*'


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`