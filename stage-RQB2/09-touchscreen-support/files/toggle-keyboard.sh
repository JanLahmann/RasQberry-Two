#!/bin/bash
# Toggle wvkbd virtual keyboard on/off
# wvkbd is a Wayland-native on-screen keyboard

if pgrep -x wvkbd-mobintl > /dev/null; then
    # Running - send toggle signal to hide/show
    pkill -SIGRTMIN wvkbd-mobintl
else
    # Not running - start it
    wvkbd-mobintl -H 200 &
fi
