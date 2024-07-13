#!/bin/sh
# shellcheck disable=SC2046
if [ -e /home/$SUDO_USER/config/env ] ; then
  echo "/home/$SUDO_USER/config/env found"
  export $(grep -v "^#" "/home/$SUDO_USER/config/env" | xargs -d "\n")
else
  echo "/home/$SUDO_USER/config/env not found"
fi
if [ -e /home/$USER/config/env ] ; then
  echo "/home/$USER/config/env found"
  export $(grep -v "^#" "/home/$USER/config/env" | xargs -d "\n")
else
  echo "/home/$USER/config/env not found"
fi