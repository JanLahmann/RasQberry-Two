#!/bin/bash

# load RasQberry environment and constants from global location
if ! . /usr/config/rasqberry_env-config.sh; then
    echo "ERROR: Failed to load RasQberry environment configuration"
    echo "Please check permissions on /usr/config/rasqberry_env-config.sh"
    echo "File should be readable by all users (chmod 644)"
    echo ""
    echo "To fix: sudo chmod 644 /usr/config/rasqberry_environment.env"
    echo "        sudo chmod 755 /usr/config/rasqberry_env-config.sh"
    return 1 2>/dev/null || exit 1
fi

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

  # Verify Qiskit is installed. Every terminal and SSH login runs this: a file
  # test takes milliseconds, `pip show` seconds on a Pi 4 (R-091), so pip only
  # decides when the file test misses - before the venv is rebuilt.
  if ! compgen -G "$HOME/$REPO/venv/$STD_VENV/lib/python3*/site-packages/qiskit-*.dist-info" > /dev/null \
      && ! pip show qiskit > /dev/null 2>&1; then
    # Qiskit missing - recreate venv from template
    echo "Qiskit not found in venv, recreating from template..."
    deactivate

    # A full copy of the template (bin/ with jupyter included); the broken venv
    # is kept as $STD_VENV.previous, not deleted (R-128).
    /usr/bin/rq_venv_repair.sh --reset --yes
    [ -f $HOME/$REPO/venv/$STD_VENV/bin/activate ] && source $HOME/$REPO/venv/$STD_VENV/bin/activate
  fi
else
  # Virtual environment doesn't exist - create new one from template
  echo "Virtual Environment doesn't exist. Creating new one from template..."

  /usr/bin/rq_venv_repair.sh --reset --yes
  [ -f $HOME/$REPO/venv/$STD_VENV/bin/activate ] && source $HOME/$REPO/venv/$STD_VENV/bin/activate
fi
