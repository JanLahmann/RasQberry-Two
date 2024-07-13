#!/bin/sh
# shellcheck disable=SC2046
source /home/$SUDO_USER/$REPO/RQB2-initial.env
export $(grep -v "^#" "/home/$SUDO_USER/$REPO/config/$ENV" | xargs -d "\n")
