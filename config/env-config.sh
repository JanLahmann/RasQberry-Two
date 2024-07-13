#!/bin/sh
# shellcheck disable=SC2046
#echo "will source /home/$SUDO_USER/$REPO/RQB2-initial.env"
#source /home/$SUDO_USER/$REPO/RQB2-initial.env
export ENV="RQB2.env"
export $(grep -v "^#" "/home/$SUDO_USER/$REPO/config/$ENV" | xargs -d "\n")
