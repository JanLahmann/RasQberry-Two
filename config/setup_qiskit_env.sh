  GNU nano 7.2                                                                                        /usr/config/setup_qiskit_env.sh *                                                                                               
#!/bin/bash

# Define the global variables
export REPO=RasQberry-Two 
export STD_VENV=RQB2

echo $HOME

# Full path to the virtual environment's activate script
export VENV_ACTIVATE=$HOME/$REPO/venv/$STD_VENV/bin/activate

# Check if the virtual environment exists
if [ -f "$VENV_ACTIVATE" ]; then
   echo "Virtual Env exit"
   source $HOME/$REPO/venv/$STD_VENV/bin/activate
else
    echo "Virtual Env does not exit"
    # Ensure the .local/bin and .local/config directories exist
    mkdir -p $HOME/.local/bin
    mkdir -p $HOME/.local/config

    # Copy the rb*.sh scripts to the user's .local/bin directory
     #echo `sudo ls -lrt /usr/config/`
     cp  /usr/bin/rq*.sh $HOME/.local/bin/

    # Copy the config files to the user's .local/config directory
     cp /usr/config/* $HOME/.local/config/
    # Virtual environment does not exist, create the necessary directory structure
    # Copy the entire venv directory from /usr/bin to the target location
    virtualenv-clone /usr/venv $HOME/$REPO/venv/$STD_VENV
    # Activate the new virtual environment
    source $HOME/$REPO/venv/$STD_VENV/bin/activate
fi
