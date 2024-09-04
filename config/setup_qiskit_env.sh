#!/bin/bash

# Define the global variables
USER_HOME="$HOME"
REPO=RasQberry-Two 
STD_VENV=RQB2

# Full path to the virtual environment's activate script
VENV_ACTIVATE="$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"

# Check if the virtual environment exists
if [ -f "$VENV_ACTIVATE" ]; then
    # Virtual environment exists, activate it
    source "$VENV_ACTIVATE"
    
    # Check if Qiskit is installed
    if ! pip list | grep -q qiskit; then
        # Install Qiskit if not installed
        .  $USER_HOME/.local/bin/rq_install_Qiskit_latest.sh
    else    
        echo "qiskit is installed"
    fi
else
    # Ensure the .local/bin and .local/config directories exist
    mkdir -p "$USER_HOME/.local/bin"
    mkdir -p "$USER_HOME/.local/config"

    # Copy the rb*.sh scripts to the user's .local/bin directory
    cp /usr/bin/rb*.sh "$USER_HOME/.local/bin/"

    # Copy the config files to the user's .local/config directory
    cp /usr/bin/config* "$USER_HOME/.local/config/"
    # Virtual environment does not exist, create the necessary directory structure
    mkdir -p "$USER_HOME/$REPO/venv/$STD_VENV"
    
    # Copy the entire venv directory from /usr/bin to the target location
    cp -r /usr/bin/venv "$USER_HOME/$REPO/venv/$STD_VENV"
    
    # Activate the new virtual environment
    source "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
    
    if ! pip list | grep -q qiskit; then
        # Install Qiskit if not installed
        .  $USER_HOME/.local/bin/rq_install_Qiskit_latest.sh
    else    
        echo "qiskit is installed"
    fi
    
fi


