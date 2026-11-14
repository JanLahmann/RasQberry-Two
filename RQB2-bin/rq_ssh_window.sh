#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: SSH on a card that still has the published demo password
# ============================================================================
# Description: A card written without Raspberry Pi Imager's settings starts
#   with the published demo password. While the desktop user (uid 1000) still
#   has it (Jan, 2026-11-14, option d):
#   - password login over SSH is open for a window after each start, counted
#     from when the Pi first has a network (a headless Pi may first spend
#     minutes in the setup Wi-Fi), DEFAULT_PW_WINDOW_MIN minutes (15; 0 = no
#     window). Sessions opened in the window keep running; key logins are
#     never affected.
#   - an SSH login with the password must set a new one first
#     (rq_ssh_first_login.sh, sshd ForceCommand for that user).
#   - VNC stays off until the password is changed (rasqberry-enable-vnc.sh),
#     unless DEFAULT_PW_WINDOW_VNC=yes (classrooms, booths). A card that had
#     VNC on before keeps it, also across A/B updates (it may be its only
#     way in; rq_carry_over.sh writes vnc-was-on).
#   - no port forwarding for that user meanwhile (ssh -N skips the step).
#   Both settings are read at every start from rasqberry_boot.env (CONFIG on
#   A/B cards, else the boot partition), so an edit after flashing counts.
#   Once the password is changed (any way: the checklist, the menu, passwd),
#   rasqberry-ssh-window-check.path runs "check" and all this goes away.
#   An Imager-customised card (own password, or keys only) has no demo
#   password, or password login is off anyway: nothing changes there.
#
# Usage: rq_ssh_window.sh close | window | check | status | vnc-allowed
#   close        (root, before sshd starts) the drop-in for a closed window
#   window       (root) wait for a network, open the window, close it after
#   check        (root) remove the drop-in once the demo password is gone
#   status       demo password, window minutes, VNC setting, drop-in state
#   vnc-allowed  exit 0 if VNC may be switched on now
#
# Environment (tests): RQ_SSHD_DIR, RQ_SSH_DROPIN, RQ_BOOT_ENV_FILES (colon-separated),
#   RQ_DEMO_PW_STATE (yes|no|unknown instead of asking rq_remote_access.sh),
#   RQ_SSH_USER, RQ_SSH_RELOAD (command), RQ_SSH_POLL (seconds), RQ_NO_LED=1,
#   RQ_SSH_BANNER, RQ_VNC_MARKER

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

SSHD_DIR="${RQ_SSHD_DIR:-/etc/ssh}"
DROPIN="${RQ_SSH_DROPIN:-$SSHD_DIR/sshd_config.d/05-rasqberry-first-login.conf}"
BOOT_ENV_FILES="${RQ_BOOT_ENV_FILES:-/boot/firmware/rasqberry_boot.env:/boot/config/rasqberry_boot.env}"
BANNER="${RQ_SSH_BANNER:-/run/rasqberry/ssh-password-closed.txt}"
FIRST_LOGIN=/usr/bin/rq_ssh_first_login.sh
POLL="${RQ_SSH_POLL:-5}"
VNC_MARKER="${RQ_VNC_MARKER:-/var/lib/rasqberry/vnc-auto-enabled}"
SCROLL_UNIT="rasqberry-ssh-window-scroll"

# A setting from rasqberry_boot.env (the last file that has it wins: CONFIG
# on A/B cards), else the default
boot_setting() {
    local key="$1" value="$2" file line
    local IFS=:
    for file in $BOOT_ENV_FILES; do
        [ -r "$file" ] || continue
        line=$(grep -E "^[[:space:]]*${key}=" "$file" 2>/dev/null | tail -n 1 || true)
        [ -n "$line" ] && value=$(printf '%s' "${line#*=}" | tr -d " \"'\r")
    done
    printf '%s' "$value"
}

window_minutes() {
    local m
    m=$(boot_setting DEFAULT_PW_WINDOW_MIN 15)
    case "$m" in ''|*[!0-9]*) m=15 ;; esac
    m=$((10#$m))                     # 08 is eight, not a bad octal number
    [ "$m" -le 240 ] || m=240
    printf '%s' "$m"
}

vnc_in_window() { [ "$(boot_setting DEFAULT_PW_WINDOW_VNC no)" = yes ]; }

desktop_user() { printf '%s' "${RQ_SSH_USER:-$(getent passwd 1000 2>/dev/null | cut -d: -f1)}"; }

# yes | no | unknown: does the desktop user still have the demo password?
demo_password() {
    [ -z "${RQ_DEMO_PW_STATE:-}" ] || { printf '%s' "$RQ_DEMO_PW_STATE"; return 0; }
    "$SCRIPT_DIR/rq_remote_access.sh" demo-password 2>/dev/null || printf unknown
}

# The drop-in: first-login step for the user; with "closed" also no password
# login. Unknown counts as the demo password (the safe side).
write_dropin() {
    local state="$1" user tmp
    user=$(desktop_user)
    [ -n "$user" ] || { warn "rq_ssh_window: no desktop user (uid 1000)"; return 1; }
    tmp="$DROPIN.tmp"
    {
        echo "# rq_ssh_window.sh: $user still has the published demo password."
        echo "# Removed by itself once it is changed. Do not edit."
        echo "ExposeAuthInfo yes"
        echo "Match User $user"
        echo "    ForceCommand $FIRST_LOGIN"
        # a login without a shell (ssh -N) would skip the password step
        echo "    DisableForwarding yes"
        if [ "$state" = closed ]; then
            echo "    PasswordAuthentication no"
            echo "    KbdInteractiveAuthentication no"
            echo "    Banner $BANNER"
        fi
    } > "$tmp"
    chmod 644 "$tmp"
    mv -f "$tmp" "$DROPIN"
    write_banner
}

# The closed-window banner, with this card's window length
write_banner() {
    local minutes how
    minutes=$(window_minutes)
    if [ "$minutes" -eq 0 ]; then
        how="Password login is off on this card (DEFAULT_PW_WINDOW_MIN=0): use an SSH key."
    else
        how="Restart the Pi and log in within $minutes minutes; you set a new password first."
    fi
    mkdir -p "$(dirname "$BANNER")"
    printf '%s\n%s\n%s\n' "RasQberry: password login is closed while this Pi has the published password." \
        "$how" "Or set a password or SSH key in Raspberry Pi Imager." > "$BANNER"
}

remove_dropin() { rm -f "$DROPIN" "$DROPIN.tmp"; }

# Tell sshd, if it runs. If sshd rejects the files, an open window is
# closed again, never the other way round: the safe state stays.
reload_sshd() {
    if [ -n "${RQ_SSH_RELOAD:-}" ]; then
        $RQ_SSH_RELOAD
        return 0
    fi
    mkdir -p /run/sshd                 # sshd -t needs it, also while ssh is off
    if ! /usr/sbin/sshd -t 2>/dev/null; then
        warn "rq_ssh_window: sshd rejects its configuration; password login stays closed"
        write_dropin closed
    fi
    systemctl try-reload-or-restart ssh.service 2>/dev/null || true
}

led_message() {
    [ "${RQ_NO_LED:-}" != 1 ] || return 0
    rq_wifi_scroll "$SCROLL_UNIT" "$1" "$2" 2>/dev/null || true
}

# Password login off anyway, by another file (Imager's "public-key only",
# carried over by an update): then there is nothing to open or ask.
keys_only_anyway() {
    [ "$(rq_sshd_first_value "$SSHD_DIR" passwordauthentication)" = no ]
}

has_network() { [ -n "$(ip route show default 2>/dev/null)" ]; }

cmd_close() {
    if [ "$(demo_password)" = no ] || keys_only_anyway; then
        remove_dropin
    else
        write_dropin closed
    fi
}

cmd_window() {
    local minutes user addr
    # the password may have come in since "close" (carry-over, Imager)
    [ "$(demo_password)" != no ] || { cmd_check; return 0; }
    keys_only_anyway && return 0
    minutes=$(window_minutes)
    if [ "$minutes" -eq 0 ]; then
        info "rq_ssh_window: no window (DEFAULT_PW_WINDOW_MIN=0): SSH takes keys only until the password is changed."
        return 0
    fi
    until has_network; do sleep "$POLL"; done
    [ "$(demo_password)" != no ] || { cmd_check; return 0; }
    user=$(desktop_user)
    write_dropin open
    reload_sshd
    addr=$(hostname -I 2>/dev/null | cut -d' ' -f1)
    info "rq_ssh_window: SSH password login open for $minutes minutes ($user@${addr:-?}); a new password is asked first."
    led_message 120 "SSH open $minutes min - log in as $user@${addr:-?}"
    sleep $((minutes * 60))
    if [ "$(demo_password)" = no ]; then
        cmd_check
        return 0
    fi
    write_dropin closed
    reload_sshd
    info "rq_ssh_window: SSH password login closed (restart the Pi to open it again)."
    led_message 60 "SSH closed - restart to reopen"
}

cmd_check() {
    [ "$(demo_password)" = no ] || return 0
    [ -e "$DROPIN" ] || return 0
    remove_dropin
    reload_sshd
    # VNC waited for this (rasqberry-enable-vnc.sh): on now, once, as at a first login
    if [ ! -e "$VNC_MARKER" ] && raspi-config nonint do_vnc 0 >/dev/null 2>&1; then
        mkdir -p "$(dirname "$VNC_MARKER")" && date '+%F %T' > "$VNC_MARKER"
    fi
    info "rq_ssh_window: the demo password is changed: no more first-login step; VNC on."
}

cmd_status() {
    local state=none
    [ -e "$DROPIN" ] && state=$(grep -q '^PasswordAuthentication no' "$DROPIN" && echo closed || echo open)
    printf 'demo_password=%s\nwindow_min=%s\nvnc_in_window=%s\ndropin=%s\n' \
        "$(demo_password)" "$(window_minutes)" "$(vnc_in_window && echo yes || echo no)" "$state"
}

main() {
    case "${1:-}" in
        close)       ensure_root "$@"; cmd_close ;;
        window)      ensure_root "$@"; cmd_window ;;
        check)       ensure_root "$@"; cmd_check ;;
        status)      cmd_status ;;
        vnc-allowed) [ "$(demo_password)" = no ] || vnc_in_window ;;
        *)           die "Usage: $(basename "$0") close | window | check | status | vnc-allowed" ;;
    esac
}

[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0
main "$@"
