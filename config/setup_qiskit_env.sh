#!/bin/bash
# Define the global variables
export REPO=RasQberry-Two 
export STD_VENV=RQB2
#echo $HOME

if [ -d "$HOME/$REPO/venv/$STD_VENV" ]; then
  # echo "Virtual Env Exists"
  FOLDER_PATH="$HOME/$REPO"
  # Get the current logged-in user
  CURRENT_USER=$(whoami)
  # Check if the folder is owned by root
  if [ $(stat -c '%U' "$FOLDER_PATH") == "root" ]; then
    # Change the ownership to the logged-in user
    sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$FOLDER_PATH"
    # echo "Ownership of $FOLDER_PATH changed to $CURRENT_USER."
  fi
  source $HOME/$REPO/venv/$STD_VENV/bin/activate
  if ! pip show qiskit > /dev/null 2>&1; then
    deactivate
    rm -fR $HOME/$REPO
    python3 -m venv $HOME/$REPO/venv/$STD_VENV
    cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/*  $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
    source $HOME/$REPO/venv/$STD_VENV/bin/activate
  fi
else
  echo "Virtual Environment don't Exists. Creating New One ..."
  python3 -m venv $HOME/$REPO/venv/$STD_VENV
  cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/*  $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
  source $HOME/$REPO/venv/$STD_VENV/bin/activate
fi

