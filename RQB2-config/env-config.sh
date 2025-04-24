#!/bin/sh
# shellcheck disable=SC2046
# This codeset loads the environment variables from the env file

RQB2_CONFDIR=.local/config # Attention: variable is defined in multiple files
if [ -e /home/$SUDO_USER/$RQB2_CONFDIR/rasqberry_environment.env ] ; then
  export $(grep -v "^#" "/home/$SUDO_USER/$RQB2_CONFDIR/rasqberry_environment.env" | xargs -d "\n")
elif [ -e /home/$USER/$RQB2_CONFDIR/rasqberry_environment.env ] ; then
    export $(grep -v "^#" "/home/$USER/$RQB2_CONFDIR/rasqberry_environment.env" | xargs -d "\n")
else  echo "env file not found"
fi