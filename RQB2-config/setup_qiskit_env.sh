#!/bin/bash

# load RasQberry environment and constants from global location
. /usr/config/rasqberry_env-config.sh

# Get the current logged-in user
CURRENT_USER=$(whoami)

# Fix ownership FIRST if $REPO directory is accidentally owned by root
# This can happen if demos were installed as root
if [ -d "$HOME/$REPO" ]; then
  FOLDER_OWNER=$(stat -c '%U' "$HOME/$REPO" 2>/dev/null || echo "$CURRENT_USER")
  if [ "$FOLDER_OWNER" == "root" ]; then
    echo "Fixing ownership of $HOME/$REPO (was owned by root)..."
    sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$HOME/$REPO"
  fi
fi

# Now check if virtual environment exists
if [ -d "$HOME/$REPO/venv/$STD_VENV" ]; then
  # Virtual environment exists, activate it
  source $HOME/$REPO/venv/$STD_VENV/bin/activate

  # Verify Qiskit is installed
  if ! pip show qiskit > /dev/null 2>&1; then
    # Qiskit missing - recreate venv from template
    echo "Qiskit not found in venv, recreating from template..."
    deactivate

    # Only delete venv subdirectory, NOT the entire $REPO (demos might be there!)
    rm -fR $HOME/$REPO/venv

    # Recreate venv from system template
    mkdir -p $HOME/$REPO/venv
    python3 -m venv $HOME/$REPO/venv/$STD_VENV
    cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/* $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/

    # Copy RQB2-bin scripts to user's local bin (if not already there)
    mkdir -p $HOME/.local/bin
    cp /usr/bin/rq*.* $HOME/.local/bin/ 2>/dev/null || true

    source $HOME/$REPO/venv/$STD_VENV/bin/activate
  fi
else
  # Virtual environment doesn't exist - create new one from template
  echo "Virtual Environment doesn't exist. Creating new one from template..."

  mkdir -p $HOME/$REPO/venv
  python3 -m venv $HOME/$REPO/venv/$STD_VENV
  cp -r /usr/venv/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/* $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/

  # Copy RQB2-bin scripts to user's local bin
  mkdir -p $HOME/.local/bin
  cp /usr/bin/rq*.* $HOME/.local/bin/ 2>/dev/null || true

  source $HOME/$REPO/venv/$STD_VENV/bin/activate
fi
