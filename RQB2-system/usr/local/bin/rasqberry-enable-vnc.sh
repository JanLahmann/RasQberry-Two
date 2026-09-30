#!/bin/bash
# RasQberry Desktop Login: Ensure VNC Server is Enabled
# Runs on every login - raspi-config do_vnc is idempotent
#
# On a fresh slot, raspi-config aborted in the first seconds of the session:
# it sources demo-menu-cache.sh, which rasqberry-demo-cache.service was still
# writing (#288). The generator now writes the cache atomically; the wait and
# the retries until get_vnc confirms VNC is on stay as a safety net. Every
# outcome goes to the journal: journalctl -t rasqberry-enable-vnc

log() { logger -t rasqberry-enable-vnc "$*"; }
vnc_on() { [ "$(sudo raspi-config nonint get_vnc 2>/dev/null)" = "0" ]; }

vnc_on && exit 0

sleep 15
for attempt in 1 2 3 4 5; do
    out=$(sudo raspi-config nonint do_vnc 0 2>&1)
    if vnc_on; then
        log "VNC enabled (attempt $attempt)"
        exit 0
    fi
    log "attempt $attempt: VNC still off after do_vnc 0${out:+: $out}"
    sleep 10
done
log "giving up: VNC is off - enable it in raspi-config (Interface Options -> VNC)"
exit 1
