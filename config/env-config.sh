#!/bin/sh
# shellcheck disable=SC2046
if [ -e /home/$SUDO_USER/$REPO/config/env ] ; then
  export $(grep -v "^#" "/home/$SUDO_USER/$REPO/config/env" | xargs -d "\n")
fi
if [ -e /home/$USER/$REPO/config/env ] ; then
  export $(grep -v "^#" "/home/$USER/$REPO/config/env" | xargs -d "\n")
fi