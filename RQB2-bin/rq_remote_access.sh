#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: remote access and this Pi's name (R-013, R-014, R-063)
# ============================================================================
# Description: What the menu's "Remote Access & Security" and the setup
#   checklist's "Name this RasQberry" use. SSH and VNC are switched through
#   raspi-config, the way its own Interface Options do it.
#
#   status        ssh=on|off  vnc=on|off  name=<hostname>  mdns=<name>.local
#                 ssh_password=yes|no  (no: SSH takes keys only, e.g. Imager's
#                 "public-key authentication only")
#   address       this Pi's IPv4 addresses, "<interface> <address>" per line
#   mdns          the name other computers reach it by. With several Pis
#                 called "rasqberry" on one network, avahi calls the later ones
#                 rasqberry-2.local, -3 ... in no fixed order (R-063).
#   ssh on|off    (root) switch the SSH server on or off, now and at start-up
#   vnc on|off    (root) the same for VNC (wayvnc). Either way VNC is now the
#                 user's choice: it is not switched on again at login (Q17).
#   name NEW      (root) rename this Pi: hostname, /etc/hosts, avahi
#   check-name N  exit 0 if N is a valid name: 1-63 lowercase letters, digits
#                 and hyphens, not starting or ending with a hyphen
#
# Usage: rq_remote_access.sh <command> [argument]
# Environment (tests): RQ_RASPI_CONFIG (default raspi-config),
#   RQ_VNC_MARKER (default /var/lib/rasqberry/vnc-auto-enabled),
#   RQ_SSHD (default /usr/sbin/sshd), RQ_SSHD_DIR (default /etc/ssh)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

RASPI_CONFIG="${RQ_RASPI_CONFIG:-raspi-config}"
VNC_MARKER="${RQ_VNC_MARKER:-/var/lib/rasqberry/vnc-auto-enabled}"
SSHD="${RQ_SSHD:-/usr/sbin/sshd}"
SSHD_DIR="${RQ_SSHD_DIR:-/etc/ssh}"

usage() {
    cat <<'EOF'
Usage: rq_remote_access.sh status | address | mdns
       sudo rq_remote_access.sh ssh on|off | vnc on|off | name NEW
EOF
}

need_root() { [ "$(id -u)" = "0" ] || die "Run this with sudo: sudo $(basename "$0") $*"; }

unit_on() { systemctl is-enabled --quiet "$1" 2>/dev/null; }
ssh_state() { if unit_on ssh.service; then echo on; else echo off; fi; }
vnc_state() { if unit_on wayvnc.service; then echo on; else echo off; fi; }

# The first value sshd reads for <keyword> (lower case) from its files: sshd
# keeps the first one, and Debian's sshd_config includes sshd_config.d/*.conf
# at its top. Stops at the first Match block (what follows is conditional).
sshd_file_value() {
    cat "$SSHD_DIR"/sshd_config.d/*.conf "$SSHD_DIR/sshd_config" 2>/dev/null \
        | awk -v key="$1" 'tolower($1) == "match" { exit }
                           tolower($1) == key { print tolower($2); exit }' || true
}

# Does SSH accept a password? "no" when it takes keys only: Imager's
# "public-key authentication only", which an A/B update carries over in
# sshd_config.d/00-rasqberry-carried.conf (rq_carry_ssh_identity.sh). A
# password also gets in through keyboard-interactive when PAM is on. The
# effective settings come from `sshd -T` (root), else from the files.
ssh_password() {
    local eff pw kbd pam
    eff=$("$SSHD" -T 2>/dev/null || true)
    if printf '%s\n' "$eff" | grep -q '^passwordauthentication '; then
        pw=$(printf '%s\n' "$eff" | awk '$1 == "passwordauthentication" { print $2; exit }')
        kbd=$(printf '%s\n' "$eff" | awk '$1 == "kbdinteractiveauthentication" || $1 == "challengeresponseauthentication" { print $2; exit }')
        pam=$(printf '%s\n' "$eff" | awk '$1 == "usepam" { print $2; exit }')
    else
        pw=$(sshd_file_value passwordauthentication)
        kbd=$(sshd_file_value kbdinteractiveauthentication)
        [ -n "$kbd" ] || kbd=$(sshd_file_value challengeresponseauthentication)
        pam=$(sshd_file_value usepam)
    fi
    # sshd's own defaults: password and keyboard-interactive on, PAM off
    if [ "${pw:-yes}" = yes ] || { [ "${kbd:-yes}" = yes ] && [ "${pam:-no}" = yes ]; }; then
        echo yes
    else
        echo no
    fi
}

current_name() { hostname 2>/dev/null || cat /etc/hostname 2>/dev/null || echo unknown; }

mdns_name() {
    local fqdn=""
    if command -v busctl >/dev/null 2>&1; then
        fqdn=$(timeout 3 busctl --system call org.freedesktop.Avahi / \
            org.freedesktop.Avahi.Server GetHostNameFqdn 2>/dev/null \
            | sed -n 's/^s "\(.*\)"$/\1/p' || true)
    fi
    echo "${fqdn:-$(current_name).local}"
}

addresses() {
    ip -4 -o addr show scope global 2>/dev/null \
        | awk '$2 !~ /^(lo|docker|br-|veth)/ { split($4, a, "/"); print $2, a[1] }' || true
}

valid_name() { [[ "${1:-}" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; }

# ssh|vnc on|off through raspi-config; says the state it ends in, and fails
# when that is not the one asked for
switch() {
    local what="$1" want="${2:-}" now name
    name=$(echo "$what" | tr '[:lower:]' '[:upper:]')
    case "$want" in on|off) ;; *) die "Usage: sudo $(basename "$0") $what on|off" ;; esac
    # raspi-config: 0 = enable, 1 = disable
    "$RASPI_CONFIG" nonint "do_$what" "$([ "$want" = on ] && echo 0 || echo 1)" || true
    now=$("${what}_state")
    if [ "$now" != "$want" ]; then
        echo "$name is still $now."
        return 1
    fi
    echo "$name is $now."
}

cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
    status)
        echo "ssh=$(ssh_state) vnc=$(vnc_state) name=$(current_name) mdns=$(mdns_name) ssh_password=$(ssh_password)" ;;
    address)
        addresses ;;
    mdns)
        mdns_name ;;
    ssh)
        need_root ssh "$@"
        switch ssh "${1:-}" ;;
    vnc)
        need_root vnc "$@"
        switch vnc "${1:-}"
        # Set by hand: the first-login autostart leaves it alone from now on
        mkdir -p "$(dirname "$VNC_MARKER")"
        [ -e "$VNC_MARKER" ] || date '+%F %T' > "$VNC_MARKER" ;;
    check-name)
        valid_name "${1:-}" ;;
    name)
        need_root name "$@"
        new="${1:-}"
        valid_name "$new" || die "Not a valid name: '$new'. Use lowercase letters, digits and hyphens (up to 63)."
        old=$(current_name)
        if [ "$new" != "$old" ]; then
            "$RASPI_CONFIG" nonint do_hostname "$new"
            # avahi does not follow a new hostname by itself
            systemctl try-restart avahi-daemon.service 2>/dev/null || true
        fi
        # Say the name avahi really announces (item 40): when another device
        # has <new>.local already, avahi takes <new>-2.local. It needs a
        # moment after the restart, so ask until it answers with the new name.
        net="$new.local"
        if command -v busctl >/dev/null 2>&1; then
            waited=0
            while [ "$waited" -lt "${RQ_MDNS_WAIT:-8}" ]; do
                sleep 1
                waited=$((waited + 1))
                got=$(mdns_name)
                case "$got" in
                    "$new.local"|"$new"-[0-9]*.local) net="$got"; break ;;
                esac
            done
        fi
        if [ "$net" = "$new.local" ]; then
            echo "This Pi is now called $new ($net on the network)."
        else
            echo "This Pi is now called $new. $new.local is taken on this network, so other computers reach it as $net."
        fi ;;
    -h|--help|"")
        usage ;;
    *)
        usage >&2
        exit 2 ;;
esac
