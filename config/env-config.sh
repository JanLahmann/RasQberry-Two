#!/bin/sh
# shellcheck disable=SC2046

# Attention: variable is defined in multiple files
RQB2_CONFDIR=.local/config 
if [ -e /home/$SUDO_USER/$RQB2_CONFDIR/env ] ; then
  export $(grep -v "^#" "/home/$SUDO_USER/$RQB2_CONFDIR/env" | xargs -d "\n")
elif [ -e /home/$USER/$RQB2_CONFDIR/env ] ; then
    export $(grep -v "^#" "/home/$USER/$RQB2_CONFDIR/env" | xargs -d "\n")
else  echo "env file not found"
fi