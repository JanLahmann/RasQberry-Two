#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Raspberry Pi Imager's user settings (name and password)
# ============================================================================
# Description: rq_imager_firstrun.sh points Imager's firstrun.sh here instead
#   of /usr/lib/userconf-pi/userconf (same arguments: NAME [PASSWORD_HASH]).
#   It runs once, at the first start of a newly written card, before anyone
#   logs in.
#   - A name typed in Imager (#319): rq_user_rename.sh renames the first
#     user, rasqberry, to it and moves its home to /home/NAME, rewriting the
#     paths and names the image holds (the Python environment, autologin,
#     sudo, services ...). Any failure undoes the rename: the user stays
#     rasqberry, and the first login says why.
#     Imager sends "pi" with no password when only an SSH key is set: that
#     is not a name someone typed, and the user stays rasqberry.
#   - The password (and with it SSH and VNC logins) is then applied by
#     Raspberry Pi OS's userconf to the first user under its current name, so
#     userconf renames nothing itself.
#   - The desktop keeps logging in by itself, as on every RasQberry card
#     (userconf would switch it to a login screen).
#   The requested name is kept in /var/lib/rasqberry/imager-user-requested.
#   Raspberry Pi Connect from Imager then goes to the renamed user
#   (rq_imager_firstrun.sh points Imager's TARGET_USER at uid 1000).
#
# Usage: rq_imager_userconf.sh NAME [PASSWORD_HASH]
# Environment (tests): RQ_USERCONF (/usr/lib/userconf-pi/userconf),
#   RQ_LIGHTDM_CONF, RQ_USERCONF_STATE (/var/lib/userconf-pi),
#   RQ_IMAGER_STATE (/var/lib/rasqberry), RQ_IMAGER_LOG,
#   RQ_USER_RENAME (/usr/bin/rq_user_rename.sh)

USERCONF="${RQ_USERCONF:-/usr/lib/userconf-pi/userconf}"
LIGHTDM_CONF="${RQ_LIGHTDM_CONF:-/etc/lightdm/lightdm.conf}"
USERCONF_STATE="${RQ_USERCONF_STATE:-/var/lib/userconf-pi}"
STATE_DIR="${RQ_IMAGER_STATE:-/var/lib/rasqberry}"
LOG_FILE="${RQ_IMAGER_LOG:-/var/log/rasqberry-imager.log}"
RENAME="${RQ_USER_RENAME:-/usr/bin/rq_user_rename.sh}"

log() {
    echo "rq_imager_userconf: $*"
    { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; } 2>/dev/null || true
}

first_user() { getent passwd 1000 | cut -d: -f1; }

wanted="${1:-}"
hash="${2:-}"
first=$(first_user)
[ -n "$first" ] || first=rasqberry

if [ -n "$wanted" ] && [ "$wanted" != "$first" ]; then
    if [ -z "$hash" ]; then
        log "Imager sent the user name '$wanted' without a password (what it does when only an SSH key is set): the user stays '$first'"
    else
        mkdir -p "$STATE_DIR"
        printf '%s\n' "$wanted" > "$STATE_DIR/imager-user-requested"
        log "Imager asked for the user '$wanted': renaming '$first'"
        if [ -x "$RENAME" ] && "$RENAME" apply "$wanted" --why "Raspberry Pi Imager"; then
            first=$(first_user)
            [ -n "$first" ] || first="$wanted"
            log "The user is now '$first' (home $(getent passwd 1000 | cut -d: -f6))"
        else
            first=$(first_user)
            [ -n "$first" ] || first=rasqberry
            log "The user stays '$first' (see /var/log/rasqberry-user-rename.log); the password and SSH key from Imager are set for '$first'"
        fi
    fi
fi

if grep -q '^autologin-user=' "$LIGHTDM_CONF" 2>/dev/null; then
    mkdir -p "$USERCONF_STATE"
    : > "$USERCONF_STATE/autologin"
fi

[ -n "$hash" ] && log "Password from Imager set for '$first'"
exec "$USERCONF" "$first" "$hash"
