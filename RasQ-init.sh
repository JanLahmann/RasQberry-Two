#!/bin/bash
#
# usage (in RPi terminal):
# wget https://github.com/JanLahmann/RasQberry-Two/raw/master/RasQ-init.sh
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
echo "wget https://github.com/JanLahmann/RasQberry-Two/raw/master/RasQ-init.sh"
echo ". ./RasQ-init.sh"
echo "Also use the previous command to update the RasQberry tooling."
echo;
echo "The script be run with parameters . ./RasQ-init.sh branch gituser devoption"
echo "The -branch parameter is used to specify the branch you want to use"
echo "The -gituser parameter is used to specify the github user to use for the rasqberry repository"
echo "The -devoption parameter is used to install the development version of the rasqberry repository (production=0, dev=1)"
echo "default values are: branch=master gituser=JanLahmann devoption=0"
echo "example: . ./RasQ-init.sh master JanLahmann 1"
echo;
echo "See https://rasqberry.org for an in-depth description" 
echo "of RasQberry, which combines Raspberry Pi and Qiskit,"
echo "IBM's open source Quantum Computing software framework."
echo;

# to use a differnt branch run e.g.   . ./RasQ-init.sh JRL-dev5
BRANCH=${1:-master}
GITUSER=${2:-JanLahmann}
DEVOPTION=${3:-0}
REPO="RasQberry-Two"
echo "using Branch " $BRANCH "and from github-user " $GITUSER "with DevOption " $DEVOPTION

# to reset local changes run.  cd ~/RasQberry; git reset --hard HEAD

cd ~/

# cloning the RasQberry-Two github repo
echo "cloning " $REPO

if [ $DEVOPTION -eq 1 ]; then
    echo "using development mode"
    [ -d $REPO ] && (cd $REPO; git config pull.rebase false; git fetch --unshallow; git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"; git fetch origin; git pull origin $BRANCH)|| git clone --branch $BRANCH https://github.com/$GITUSER/$REPO
else
    echo "using production mode"
    [ -d $REPO ] && (cd $REPO; git config pull.rebase false; git pull origin $BRANCH) || git clone --depth 1 --branch $BRANCH https://github.com/$GITUSER/$REPO
fi

# replacing raspi-config with the modified version
echo "replacing raspi-config with the modified version"
wget https://raw.githubusercontent.com/JanLahmann/RasQberry-raspi-config/bookworm/raspi-config
sudo cp /usr/bin/raspi-config /usr/bin/raspi-config.orig 
sudo cp raspi-config /usr/bin

# copy all binaries from the GH repo to ~/.local/bin
echo "copy all binaries from the GH repo to ~/.local/bin"
[ ! -d ~/.local/bin ] && mkdir ~/.local/bin
[ -d $REPO/bin ] && cp -r $REPO/bin/* ~/.local/bin

echo "RasQ-init.sh finished"
echo "You may now start    sudo raspi-config"