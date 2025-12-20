#!/bin/bash
# Toggle squeekboard on-screen keyboard on/off
if pgrep -x squeekboard > /dev/null; then
    pkill squeekboard
else
    squeekboard &
fi
