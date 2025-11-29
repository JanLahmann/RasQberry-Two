#!/bin/bash
# Toggle matchbox-keyboard on/off
if pgrep -x matchbox-keyboard > /dev/null; then
    killall matchbox-keyboard
else
    matchbox-keyboard &
fi
