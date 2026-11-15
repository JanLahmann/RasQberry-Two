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
# Two callers: this autostart (as the desktop user, through sudo -n), and
# rq_ssh_window.sh check as root when the password is changed (a card whose
# VNC waited for that); sudo -n works for root as well. Keep both working.
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

# Only inside the desktop session: raspi-config picks wayvnc only while labwc
# runs, and before that it switches on the X11 VNC server instead (an A/B
# update's first boot, 2026-11-15). Without labwc the login does it later.
if ! pgrep -x labwc >/dev/null 2>&1; then
    log "no desktop session yet: VNC is switched on at the desktop login"
    exit 0
fi


if vnc_on; then
    mark_done
    exit 0
fi

# Not while the account has the published password (VNC cannot ask for a new
# one): rq_ssh_window.sh switches it on once the password is changed, or now
# with DEFAULT_PW_WINDOW_VNC=yes in rasqberry_boot.env. Except after an A/B
# update from a system that had VNC on (rq_carry_over.sh writes vnc-was-on;
# used once: deleting the marker later brings the password check back).
WINDOW="${RQ_SSH_WINDOW:-/usr/bin/rq_ssh_window.sh}"
VNC_WAS_ON="${RQ_VNC_WAS_ON:-/var/lib/rasqberry/vnc-was-on}"
if [ ! -e "$VNC_WAS_ON" ] && [ -x "$WINDOW" ] && ! sudo -n "$WINDOW" vnc-allowed 2>/dev/null; then
    log "VNC stays off while the published password is set (on once it is changed)"
    exit 0
fi

sleep "${RQ_VNC_WAIT:-15}"
for attempt in 1 2 3 4 5; do
    # the login and a password change can both get here: the first one wins
    [ -e "$MARKER" ] && exit 0
    out=$(sudo -n raspi-config nonint do_vnc 0 2>&1)
    if vnc_on; then
        log "VNC enabled (attempt $attempt) - once; it stays off if switched off later"
        mark_done
        sudo -n rm -f "$VNC_WAS_ON" 2>/dev/null
        exit 0
    fi
    log "attempt $attempt: VNC still off after do_vnc 0${out:+: $out}"
    sleep "${RQ_VNC_RETRY_WAIT:-10}"
done
log "giving up: VNC is off - enable it in raspi-config (Interface Options -> VNC)"
exit 1
