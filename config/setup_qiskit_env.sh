#!/bin/bash
# Define the global variables
export REPO=RasQberry-Two 
export STD_VENV=RQB2
echo $HOME

if [ -d "$HOME/$REPO/venv/$STD_VENV" ]; then
  echo "Virtual Env Exists"
  source $HOME/$REPO/venv/$STD_VENV/bin/activate
  if ! pip show qiskit > /dev/null 2>&1; then
    deactivate
    rm -fR $HOME/$REPO/venv/$STD_VENV
    python3 -m venv $HOME/$REPO/venv/$STD_VENV
    cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/* $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
    source $HOME/$REPO/venv/$STD_VENV/bin/activate
  fi
else
  echo "Virtual Env don't Exists. Creating New One ..."
  python3 -m venv $HOME/$REPO/venv/$STD_VENV
  cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/*  $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
  source $HOME/$REPO/venv/$STD_VENV/bin/activate
fi
