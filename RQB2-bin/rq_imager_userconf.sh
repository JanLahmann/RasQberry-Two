#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Raspberry Pi Imager's user settings, without renaming the user
# ============================================================================
# Description: rq_imager_firstrun.sh points Imager's firstrun.sh here instead
#   of /usr/lib/userconf-pi/userconf (same arguments: NAME [PASSWORD_HASH]).
#   The password (and with it SSH and VNC logins) is applied to the first user,
#   rasqberry, as userconf would - but the user is NOT renamed: its home holds
#   the demos, the Python environment and the desktop settings, and a rename
#   breaks them. Imager renames to "pi" when it has an SSH key but no user name.
#   A different requested name is logged and kept in
#   /var/lib/rasqberry/imager-user-requested.
#   The desktop keeps logging in by itself, as on every RasQberry card
#   (userconf would switch it to a login screen).
#
# Usage: rq_imager_userconf.sh NAME [PASSWORD_HASH]
# Environment (tests): RQ_USERCONF (/usr/lib/userconf-pi/userconf),
#   RQ_LIGHTDM_CONF, RQ_USERCONF_STATE (/var/lib/userconf-pi),
#   RQ_IMAGER_STATE (/var/lib/rasqberry), RQ_IMAGER_LOG

USERCONF="${RQ_USERCONF:-/usr/lib/userconf-pi/userconf}"
LIGHTDM_CONF="${RQ_LIGHTDM_CONF:-/etc/lightdm/lightdm.conf}"
USERCONF_STATE="${RQ_USERCONF_STATE:-/var/lib/userconf-pi}"
STATE_DIR="${RQ_IMAGER_STATE:-/var/lib/rasqberry}"
LOG_FILE="${RQ_IMAGER_LOG:-/var/log/rasqberry-imager.log}"

log() {
    echo "rq_imager_userconf: $*"
    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; } 2>/dev/null || true
}

wanted="${1:-}"
hash="${2:-}"
first=$(getent passwd 1000 | cut -d: -f1)
[ -n "$first" ] || first=rasqberry

if [ -n "$wanted" ] && [ "$wanted" != "$first" ]; then
    log "Imager asked for the user '$wanted'. RasQberry keeps the user '$first' (its demos and settings belong to it); the password and SSH key from Imager are set for '$first'."
    mkdir -p "$STATE_DIR"
    printf '%s\n' "$wanted" > "$STATE_DIR/imager-user-requested"
fi

if grep -q '^autologin-user=' "$LIGHTDM_CONF" 2>/dev/null; then
    mkdir -p "$USERCONF_STATE"
    : > "$USERCONF_STATE/autologin"
fi

[ -n "$hash" ] && log "Password from Imager set for '$first'"
exec "$USERCONF" "$first" "$hash"
