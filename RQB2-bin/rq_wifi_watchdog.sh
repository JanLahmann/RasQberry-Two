#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: bring Wi-Fi back when NetworkManager gave up on it
# ============================================================================
# Description: On the rig (2026-10-04: first start of a new card, Wi-Fi from
#   Raspberry Pi Imager, no cable) the router rejected the first association
#   attempts. NetworkManager 1.42 takes a timeout on a profile that has never
#   connected as a wrong password: it asks a secret agent for a new one
#   (device state need-auth) and, when none answers, fails with "no secrets"
#   and blocks the profile from connecting on its own until an agent
#   registers. connection.autoconnect-retries does not count these failures.
#   Without a screen nobody answers: the Pi stayed offline with the right
#   password stored, and `nmcli connection up preconfigured` connected at once.
#
#   Each run (rasqberry-wifi-watchdog.timer: 90 s after boot, then every
#   minute), as root:
#   1. Wi-Fi profiles with a stored password whose
#      connection.autoconnect-retries is still the default (-1: 4 tries, then
#      a 5-minute pause) get 0, "retry forever". One place for every way a
#      profile comes: Imager's "preconfigured", the setup checklist (nmtui),
#      raspi-config, the desktop, profiles carried over on /data.
#   2. A Wi-Fi device found stuck at two checks in a row - in need-auth, or
#      disconnected after a failure - gets one `nmcli connection up`: of the
#      profile it was trying (need-auth), or of the best stored-password
#      profile whose network is in range (disconnected). Then 2, 4, 8, 16 and
#      30 minutes between tries, until it is connected.
#   One journal line for each change and each try; nothing otherwise.
#
#   Left alone: Wi-Fi switched off (nmcli radio wifi off) or networking off;
#   a device the user disconnected or set to autoconnect no; profiles with
#   autoconnect no; profiles without a stored password (asked each time,
#   kept by a desktop keyring, open networks, 802.1X); hotspots; profiles
#   not saved in /etc/NetworkManager/system-connections; a device that is
#   connected, connecting, unavailable or unmanaged. Ethernet does not
#   matter: Wi-Fi next to a cable is harmless.
#
# Usage: rq_wifi_watchdog.sh   (as root)
# Environment (tests): RQ_WIFI_STATE_DIR (default /run/rasqberry), RQ_WIFI_LOG
#   (a file instead of the journal), RQ_WIFI_NOW (seconds since boot)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

export LC_ALL=C
STATE_DIR="${RQ_WIFI_STATE_DIR:-/run/rasqberry}"
# Seconds since boot: the clock jumps when NTP sets it after start-up, and
# the state lives in /run, which starts empty at every boot
NOW="${RQ_WIFI_NOW:-$(cut -d. -f1 /proc/uptime 2>/dev/null || date +%s)}"
NM_DIR="/etc/NetworkManager/system-connections/"
STUCK_SECS=50      # stuck at the previous check too (the timer runs every minute)
FIRST_GAP=120      # seconds between the first and the second try; doubles
MAX_GAP=1800

log() {
    if [ -n "${RQ_WIFI_LOG:-}" ]; then
        printf '%s\n' "$*" >> "$RQ_WIFI_LOG"
        return 0
    fi
    if [ -t 1 ]; then printf '%s\n' "$*"; fi
    logger -t rasqberry-wifi-watchdog -p daemon.notice -- "$*" 2>/dev/null \
        || printf 'rasqberry-wifi-watchdog: %s\n' "$*" >&2
}

# The value of KEY in nmcli's terse "KEY:value" lines ($2); "--" is empty
field() {
    awk -v k="$1:" 'index($0, k) == 1 {
        v = substr($0, length(k) + 1); if (v == "--") v = ""; print v; exit }' <<< "$2"
}

# TYPE:UUID:AUTOCONNECT:PRIORITY:TIMESTAMP:ACTIVE:FILENAME of the Wi-Fi
# profiles, best first: priority, then the most recently connected
# (FILENAME last: a terse list escapes a ":" in it)
wifi_profiles() {
    local list
    list=$(nmcli -t -f TYPE,UUID,AUTOCONNECT,AUTOCONNECT-PRIORITY,TIMESTAMP,ACTIVE,FILENAME \
        connection show 2>/dev/null) || return 0
    awk -F: '$1 == "802-11-wireless"' <<< "$list" | sort -t: -k4,4nr -k5,5nr
}

# profile_info UUID: sets P_ID, P_AUTO, P_IFACE, P_RETRIES, P_SSID, P_HIDDEN, and
# P_STORED=yes for a Wi-Fi client profile with a stored password: key-mgmt
# wpa-psk or sae, psk-flags 0 (NetworkManager itself keeps the secret, no
# agent asked) and a psk, which is only tested for being there.
profile_info() {
    local out flags psk
    P_ID=""; P_AUTO=""; P_IFACE=""; P_RETRIES=""; P_SSID=""; P_HIDDEN=""; P_STORED=no
    out=$(nmcli -t -f connection.id,connection.autoconnect,connection.interface-name,connection.autoconnect-retries,802-11-wireless.mode,802-11-wireless.ssid,802-11-wireless.hidden,802-11-wireless-security.key-mgmt,802-11-wireless-security.psk-flags \
        connection show uuid "$1" 2>/dev/null) || return 1
    P_ID=$(field connection.id "$out")
    P_AUTO=$(field connection.autoconnect "$out")
    P_IFACE=$(field connection.interface-name "$out")
    P_RETRIES=$(field connection.autoconnect-retries "$out")
    P_RETRIES="${P_RETRIES%% *}"
    P_SSID=$(field 802-11-wireless.ssid "$out")
    P_HIDDEN=$(field 802-11-wireless.hidden "$out")
    case "$(field 802-11-wireless.mode "$out")" in ""|infrastructure) ;; *) return 0 ;; esac
    case "$(field 802-11-wireless-security.key-mgmt "$out")" in wpa-psk|sae) ;; *) return 0 ;; esac
    flags=$(field 802-11-wireless-security.psk-flags "$out")
    [ "${flags%% *}" = "0" ] || return 0
    psk=$(nmcli -s -g 802-11-wireless-security.psk connection show uuid "$1" 2>/dev/null) || psk=""
    [ -n "$psk" ] || return 0
    psk=""
    P_STORED=yes
}

# 1. Stored-password profiles retry forever (only where it is still -1)
tune_profiles() {
    local uuid ac file
    while IFS=: read -r _ uuid ac _ _ _ file; do
        [ "$ac" = "yes" ] || continue
        case "$file" in "$NM_DIR"*) ;; *) continue ;; esac
        profile_info "$uuid" || continue
        [ "$P_STORED" = "yes" ] && [ "$P_RETRIES" = "-1" ] || continue
        if nmcli connection modify uuid "$uuid" connection.autoconnect-retries 0 >/dev/null 2>&1; then
            log "Wi-Fi profile '$P_ID' has a stored password: it now retries forever (connection.autoconnect-retries 0)"
        fi
    done < <(wifi_profiles)
}

# in_range DEV SSID: is SSID in DEV's last scan? (no new scan)
in_range() {
    local list
    [ -n "$2" ] || return 1
    list=$(nmcli -e no -t -f SSID device wifi list ifname "$1" --rescan no 2>/dev/null) || return 1
    grep -qxF -- "$2" <<< "$list"
}

# best_profile DEV: the UUID of the best stored-password profile for DEV with
# autoconnect, not active on another device, whose network is in range (or
# hidden: not in a scan)
best_profile() {
    local dev="$1" uuid ac active
    while IFS=: read -r _ uuid ac _ _ active _; do
        [ "$ac" = "yes" ] && [ "$active" != "yes" ] || continue
        profile_info "$uuid" || continue
        [ "$P_STORED" = "yes" ] || continue
        [ -z "$P_IFACE" ] || [ "$P_IFACE" = "$dev" ] || continue
        [ "$P_HIDDEN" = "yes" ] || in_range "$dev" "$P_SSID" || continue
        echo "$uuid"
        return 0
    done < <(wifi_profiles)
    return 1
}

# The state of one device, in STATE_DIR/wifi-watchdog.DEV:
# KEY (state:profile, "-" for none) SEEN (when first stuck) TRIES LAST (try)
read_state() {
    S_KEY="-"; S_SEEN=0; S_TRIES=0; S_LAST=0
    if [ -f "$1" ]; then
        read -r S_KEY S_SEEN S_TRIES S_LAST < "$1" || true
    fi
    if ! [[ "$S_SEEN" =~ ^[0-9]+$ && "$S_TRIES" =~ ^[0-9]+$ && "$S_LAST" =~ ^[0-9]+$ ]]; then
        S_KEY="-"; S_SEEN=0; S_TRIES=0; S_LAST=0
    fi
}
write_state() {
    mkdir -p "$STATE_DIR" 2>/dev/null || return 0
    echo "${S_KEY:--} $S_SEEN $S_TRIES $S_LAST" > "$1" 2>/dev/null || true
}

# 2. One Wi-Fi device
check_device() {
    local dev="$1" info state reason dev_ac con uuid file key gap n rc result why
    info=$(nmcli -t -f GENERAL.STATE,GENERAL.REASON,GENERAL.AUTOCONNECT,GENERAL.CON-UUID \
        device show "$dev" 2>/dev/null) || return 0
    state=$(field GENERAL.STATE "$info"); state="${state%% *}"
    reason=$(field GENERAL.REASON "$info"); reason="${reason%% *}"
    dev_ac=$(field GENERAL.AUTOCONNECT "$info")
    con=$(field GENERAL.CON-UUID "$info")
    file="$STATE_DIR/wifi-watchdog.$dev"
    read_state "$file"

    # NMDeviceState 100 activated, 60 need-auth, 30 disconnected, 120 failed;
    # reason 39: disconnected by the user or a client. Device autoconnect
    # "no": `nmcli device disconnect` or `... set DEV autoconnect no`.
    case "$state" in
        100) rm -f "$file"; return 0 ;;
        60) ;;
        30|120) [ "$reason" != "39" ] || state="" ;;
        *) state="" ;;
    esac
    [ "$dev_ac" != "no" ] || state=""

    uuid=""
    if [ "$state" = "60" ]; then
        # Only the profile it is trying: another one would also end what a
        # person may be typing into a password dialog
        if [ -n "$con" ] && profile_info "$con" && [ "$P_STORED" = "yes" ] \
            && [ "$P_AUTO" = "yes" ]; then
            uuid="$con"
        fi
    elif [ -n "$state" ]; then
        uuid=$(best_profile "$dev") || uuid=""
    fi
    if [ -z "$uuid" ]; then
        # nothing to do: a later stuck state is counted afresh
        if [ "$S_KEY" != "-" ]; then S_KEY="-"; S_SEEN=0; write_state "$file"; fi
        return 0
    fi

    # Stuck at the previous check too?
    key="$state:$uuid"
    if [ "$S_KEY" != "$key" ]; then
        S_KEY="$key"; S_SEEN="$NOW"
        write_state "$file"
        return 0
    fi
    [ $((NOW - S_SEEN)) -ge "$STUCK_SECS" ] || return 0

    # Back off: 2, 4, 8, 16, then 30 minutes after a try (10 s timer slack)
    if [ "$S_TRIES" -gt 0 ]; then
        gap=$FIRST_GAP; n=1
        while [ "$n" -lt "$S_TRIES" ] && [ "$gap" -lt "$MAX_GAP" ]; do
            gap=$((gap * 2)); n=$((n + 1))
        done
        [ "$gap" -le "$MAX_GAP" ] || gap=$MAX_GAP
        [ $((NOW - S_LAST)) -ge $((gap - 10)) ] || return 0
    fi

    profile_info "$uuid" || return 0
    S_TRIES=$((S_TRIES + 1)); S_LAST="$NOW"; S_KEY="-"; S_SEEN=0
    write_state "$file"
    rc=0
    nmcli --wait 60 connection up uuid "$uuid" ifname "$dev" >/dev/null 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then
        result="connected"
        rm -f "$file"
    else
        result="not connected yet (nmcli exit $rc), trying again later"
    fi
    if [ "$state" = "60" ]; then
        why="waited for a password (need-auth) although one is stored"
    else
        why="disconnected after a failure"
    fi
    log "$dev $why: brought up Wi-Fi profile '$P_ID' (try $S_TRIES): $result"
}

# NetworkManager runs, and networking and Wi-Fi are switched on
[ "$(nmcli networking 2>/dev/null || true)" = "enabled" ] || exit 0
[ "$(nmcli radio wifi 2>/dev/null || true)" = "enabled" ] || exit 0

tune_profiles
while IFS=: read -r dev type; do
    [ "$type" = "wifi" ] || continue
    check_device "$dev"
done < <(nmcli -t -f DEVICE,TYPE device 2>/dev/null || true)
exit 0
