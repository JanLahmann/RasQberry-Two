#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# load RasQberry environment and constants
. "/home/${SUDO_USER:-$USER}/${RQB2_CONFDIR:-.local/config}/env-config.sh"


# installation of Qiskit 1.0
#


export STARTDATE=`date`
echo; echo; echo "Install Qiskit 1.0"; echo;

. $HOME/$REPO/venv/$STD_VENV/bin/activate
pip install --prefer-binary  'qiskit[all]==1.0.*'


pip3 list | grep qiskit

echo; echo "start Qiskit install: " $STARTDATE &&
echo "end   Qiskit install: " `date`