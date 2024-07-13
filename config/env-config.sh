#!/bin/sh
# shellcheck disable=SC2046
export $(grep -v "^#" "/home/$SUDO_USER/$REPO/config/RQB2.env" | xargs -d "\n")
