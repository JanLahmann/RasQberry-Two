#!/bin/bash
# RasQberry Desktop Login: switch VNC on ONCE (Jan, Q17)
#
# The image ships with wayvnc not enabled; this autostart switches it on at the
# first desktop login (the image logs itself in, so that is the first start)
# and writes a marker. From then on VNC is the user's choice: switched off in
# raspi-config or the RasQberry menu, it stays off (R-014 - it used to be
# switched back on at every login). An A/B update carries the choice over
# (rq_carry_over.sh). To have it switched on again by this script, delete the
# marker: sudo rm /var/lib/rasqberry/vnc-auto-enabled
#
# On a fresh slot, raspi-config aborted in the first seconds of the session:
# it sources demo-menu-cache.sh, which rasqberry-demo-cache.service was still
# writing (#288). The generator now writes the cache atomically; the wait and
# the retries until get_vnc confirms VNC is on stay as a safety net, and the
# marker is written only after VNC is on. Every outcome goes to the journal:
# journalctl -t rasqberry-enable-vnc

MARKER="${RQ_VNC_MARKER:-/var/lib/rasqberry/vnc-auto-enabled}"

log() { logger -t rasqberry-enable-vnc "$*"; }
vnc_on() { [ "$(sudo -n raspi-config nonint get_vnc 2>/dev/null)" = "0" ]; }
mark_done() {
    sudo -n mkdir -p "$(dirname "$MARKER")" 2>/dev/null
    date '+%F %T' | sudo -n tee "$MARKER" >/dev/null 2>&1 \
        || log "could not write $MARKER - VNC will be switched on again at the next login"
}

# Done once: from now on, on or off is the user's choice
[ -e "$MARKER" ] && exit 0

if vnc_on; then
    mark_done
    exit 0
fi

sleep "${RQ_VNC_WAIT:-15}"
for attempt in 1 2 3 4 5; do
    out=$(sudo -n raspi-config nonint do_vnc 0 2>&1)
    if vnc_on; then
        log "VNC enabled (attempt $attempt) - once; it stays off if switched off later"
        mark_done
        exit 0
    fi
    log "attempt $attempt: VNC still off after do_vnc 0${out:+: $out}"
    sleep "${RQ_VNC_RETRY_WAIT:-10}"
done
log "giving up: VNC is off - enable it in raspi-config (Interface Options -> VNC)"
exit 1
