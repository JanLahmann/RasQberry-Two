  GNU nano 7.2                                                                                        /usr/config/setup_qiskit_env.sh *                                                                                               
#!/bin/bash

# Define the global variables
export REPO=RasQberry-Two 
export STD_VENV=RQB2
echo $HOME
qiskit_install_status="false"
if [ -d $HOME/$REPO/venv/$STD_VENV]
  source $HOME/$REPO/venv/$STD_VENV/bin/activate
  if ! pip list | grep -q qiskit; then
    deactivate
    cp -r /usr/venv/lib/python3.11/site-packages/* $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
    echo "source \$HOME/$REPO/venv/$STD_VENV/bin/activate" >> $HOME/.bashrc
    source $HOME/.bashrc
  fi
else
  python3 -m venv $HOME/$REPO/venv/$STD_VENV
  cp -r /usr/venv/lib/python3.11/site-packages/* $HOME/$REPO/venv/$STD_VENV/lib/python3.11/site-packages/
  echo "source \$HOME/$REPO/venv/$STD_VENV/bin/activate" >> $HOME/.bashrc
  source $HOME/.bashrc
fi
