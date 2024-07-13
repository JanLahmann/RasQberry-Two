#!/bin/bash
#

# export project / repo name
export REPO=RasQberry-Two # Attention: variable is defined in multiple files
export RQB2_CONFDIR=.local/config # Attention: variable is defined in multiple files

# usage (in RPi terminal):
# wget https://github.com/JanLahmann/RasQberry-Two/raw/main/RasQ-init.sh -O RasQ-init.sh
# . ./RasQ-init.sh
# also use the previous command to update the RasQberry tooling
#
echo; echo;
echo "This script (RasQ-init.sh) downloads a modified raspi-config tool,"
echo "which can be used to install and configure Qiskit and"
echo "several Quantum Computing Demos on the Raspberry Pi"
echo "This script is available at https://github.com/JanLahmann/RasQberry-Two/"
echo;
echo "Before running this script, pls setup the SD card using the" 
echo "Raspberry Pi Imager (with 'Raspberry Pi OS 64-bit with Desktop')," 
echo "then login to the RPi via ssh and run the following commands:"
echo;
echo "wget https://github.com/JanLahmann/RasQberry-Two/raw/main/RasQ-init.sh"
echo ". ./RasQ-init.sh"
echo "Also use the previous command to update the RasQberry tooling."
echo;
echo "The script be run with parameters . ./RasQ-init.sh branch gituser devoption"
echo "The -branch parameter is used to specify the branch you want to use"
echo "The -gituser parameter is used to specify the github user to use for the rasqberry repository"
echo "The -devoption parameter is used to install the development version of the rasqberry repository (production=0, dev=1)"
echo "default values are: branch=main gituser=JanLahmann devoption=0"
echo "example: . ./RasQ-init.sh main JanLahmann 1"
echo;
echo "See https://rasqberry.org for an in-depth description" 
echo "of RasQberry, which combines Raspberry Pi and Qiskit,"
echo "IBM's open source Quantum Computing software framework."
echo;

# to use a differnt branch run e.g.   . ./RasQ-init.sh JRL-dev5
BRANCH=${1:-main}
GITUSER=${2:-JanLahmann}
DEVOPTION=${3:-0}
echo "using Branch " $BRANCH "and from github-user " $GITUSER "with DevOption " $DEVOPTION

# to reset local changes run:  cd ~/RasQberry-Two; git reset --hard HEAD; cd

cd ~/

# cloning the RasQberry-Two github repo
echo; echo "cloning " $REPO

if [ $DEVOPTION -eq 1 ]; then
    echo "using development mode"
    [ -d $REPO ] && (cd $REPO; git config pull.rebase false; git fetch --unshallow; git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"; git fetch origin; git pull origin $BRANCH)|| git clone --branch $BRANCH https://github.com/$GITUSER/$REPO
else
    echo "using production mode"
    [ -d $REPO ] && (cd $REPO; git config pull.rebase false; git pull origin $BRANCH) || git clone --depth 1 --branch $BRANCH https://github.com/$GITUSER/$REPO
fi

# replacing raspi-config with the modified version
echo; echo "replacing raspi-config with the modified version"
wget https://raw.githubusercontent.com/JanLahmann/RasQberry-raspi-config/bookworm/raspi-config -O raspi-config
sudo cp /usr/bin/raspi-config /usr/bin/raspi-config.orig 
sudo cp raspi-config /usr/bin


# copy all binaries from the GH repo to ~/.local/bin
echo; echo "copy all binaries from the GH repo to ~/.local/bin"
[ ! -d ~/.local/bin ] && mkdir ~/.local/bin
[ -d $REPO/bin ] && cp -r $REPO/bin/* ~/.local/bin

# copy all config files from the GH repo to ~/$RQB2_CONFDIR
echo; echo "copy all config files from the GH repo to ~/$RQB2_CONFDIR"
[ ! -d ~/.local/config ] && mkdir ~/$RQB2_CONFDIR
[ -d $REPO/config ] && cp -r $REPO/config/* ~/$RQB2_CONFDIR
ln -sf ~/$RQB2_CONFDIR/env-config.sh ~/.local/bin # make env-config.sh avaialable at a default location

echo; echo "RasQ-init.sh finished"
echo "You may now run    sudo raspi-config"