#!/bin/bash
# Toggle wvkbd virtual keyboard on/off
# wvkbd is a Wayland-native on-screen keyboard
# Signals: SIGUSR1=hide, SIGUSR2=show, SIGRTMIN=toggle

PID=$(pgrep -x wvkbd-mobintl)

if [ -n "$PID" ]; then
    # Check if wvkbd is hung (>10% CPU when idle indicates problem)
    CPU=$(ps -p $PID -o %cpu= 2>/dev/null | cut -d. -f1)
    if [ -n "$CPU" ] && [ "$CPU" -gt 10 ]; then
        # Hung - kill ALL instances and restart
        pkill -9 wvkbd-mobintl 2>/dev/null
        sleep 0.5
        wvkbd-mobintl -H 200 &
    else
        # Running normally - send toggle signal
        kill -s SIGRTMIN $PID
    fi
else
    # Not running - start it
    wvkbd-mobintl -H 200 &
fi
