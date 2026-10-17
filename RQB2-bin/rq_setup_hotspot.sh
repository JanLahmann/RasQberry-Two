#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: setup hotspot - first access to a new Pi without a network
# ============================================================================
# Description: A card flashed without Wi-Fi, started without a cable, also
#   without a screen: after about two minutes with no network, the Pi opens
#   the Wi-Fi "RasQberry-Setup-XXXX" (password "rasqberry", documented).
#   Joining it opens a page (captive portal) that lists the Wi-Fi networks
#   in range; the one chosen is joined, and the LED panel then scrolls the
#   Pi's new address (rasqberry-ip-display's NetworkManager hook). balena
#   wifi-connect does the work (hotspot, DNS, page server, joining); the page
#   is RasQberry's (/usr/share/rasqberry/setup-portal).
#
#   A network is a real way out: an Ethernet or Wi-Fi device that
#   NetworkManager connected, with a default route. Docker's bridge made
#   NetworkManager say "connected (local only)", which used to count, so the
#   setup Wi-Fi never opened on a RasQberry image (review A1).
#
#   Only while the Pi has never had a network: once it had one at a start
#   (network-seen, on /data where there is one, so both A/B slots share it),
#   it does not start again. It ends
#     - when there is a network: a cable plugged in, a second Wi-Fi adapter,
#       or a known Wi-Fi in range while nobody is on the setup Wi-Fi (the Pi
#       joins it; if that fails, the setup Wi-Fi comes back),
#     - after 30 minutes without anyone on it, and after an hour at most;
#       NetworkManager then keeps trying the known networks.
#   wifi-connect's own --activity-timeout stops counting once anyone opened
#   the page (review A5), so this script watches it instead.
#   Not when the booth hotspot starts at boot (HOTSPOT_AT_BOOT) - unless it
#   did not start: then this is the way in to a Pi without a screen (A6).
#   The LED panel scrolls the name and password while it runs.
#
# Usage: rq_setup_hotspot.sh   (as root; rasqberry-setup-hotspot.service)
# Environment (tests): RQ_SETUP_WAIT (seconds, default 120), RQ_NETWORK_SEEN,
#   RQ_SETUP_POLL (seconds between checks, default 5)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

if [ -n "${RQ_NETWORK_SEEN:-}" ]; then
    SEEN="$RQ_NETWORK_SEEN"
elif mountpoint -q /data 2>/dev/null; then
    SEEN=/data/rasqberry/network-seen
else
    SEEN=/var/lib/rasqberry/network-seen
fi
WAIT="${RQ_SETUP_WAIT:-120}"
POLL="${RQ_SETUP_POLL:-5}"
PASSWORD="rasqberry"
UI_DIR="/usr/share/rasqberry/setup-portal"
WIFI_CONNECT="/usr/local/sbin/wifi-connect"
IDLE_SECONDS=1800       # nobody on the setup Wi-Fi this long: it ends
HARD_LIMIT=3600         # it ends after an hour in any case
SCAN_AFTER=120          # nobody on it this long: look for a known Wi-Fi ...
SCAN_EVERY=120          # ... this often
JOIN_WAIT=90            # a known Wi-Fi in range: time to join it
JOIN_TRIES=3            # at most this many times
SCROLL_UNIT="rasqberry-setup-scroll"
WC_PID=""
REASON=""
SSID=""
START=0
JOINS=0

# Seconds since boot: the clock jumps when NTP sets it
now() { cut -d. -f1 /proc/uptime 2>/dev/null || date +%s; }

# Is there a real network: an Ethernet or Wi-Fi device NetworkManager
# connected itself ("connected", not "connected (externally)" as docker0 is),
# with a default route (IPv4 or IPv6)? An access point - this setup Wi-Fi,
# the booth hotspot - has none. NetworkManager's overall state is no help:
# docker0 makes it "connected (local only)" (review A1).
network_up() {
    local dev type state
    while IFS=: read -r dev type state; do
        case "$type" in ethernet|wifi) ;; *) continue ;; esac
        [ "$state" = connected ] || continue
        if [ -n "$(ip -4 route show default dev "$dev" 2>/dev/null)" ] \
            || [ -n "$(ip -6 route show default dev "$dev" 2>/dev/null)" ]; then
            return 0
        fi
    done < <(nmcli -t -f DEVICE,TYPE,STATE device 2>/dev/null || true)
    return 1
}

mark_seen() { mkdir -p "$(dirname "$SEEN")"; touch "$SEEN"; }

# wait_for_network SECONDS: 0 as soon as there is one
wait_for_network() {
    local waited=0
    while [ "$waited" -lt "$1" ]; do
        network_up && return 0
        sleep "$POLL"
        waited=$((waited + POLL))
    done
    network_up
}

# The booth hotspot (rq_hotspot.sh) is on
booth_running() {
    nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx rasqberry-hotspot
}

# The Wi-Fi country from the time zone (Imager sets it even without Wi-Fi):
# without a country the Wi-Fi stays off (rfkill)
wifi_country_from_timezone() {
    local tz
    tz=$(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || true)
    [ -n "$tz" ] || return 1
    awk -v tz="$tz" '!/^#/ && $3 == tz { print $1; exit }' /usr/share/zoneinfo/zone.tab 2>/dev/null
}

# No country, or still the image's GB while the time zone says another
# country (a Pi that never had a network kept the image default; on GB the
# setup Wi-Fi may take channel 12 or 13, which US phones do not see - A12)
ensure_wifi_country() {
    local country tz_country
    country=$(/usr/sbin/iw reg get 2>/dev/null | awk '/^country/ { sub(":", "", $2); print $2; exit }')
    tz_country=$(wifi_country_from_timezone || true)
    if [ -z "$country" ] || [ "$country" = 00 ] \
        || { [ "$country" = GB ] && [ -n "$tz_country" ] && [ "$tz_country" != GB ]; }; then
        country=${tz_country:-GB}
        info "Setup hotspot: Wi-Fi country set to $country (from the time zone)."
        raspi-config nonint do_wifi_country "$country" >/dev/null 2>&1 || /usr/sbin/iw reg set "$country" 2>/dev/null || true
    fi
    rfkill unblock wifi 2>/dev/null || true
}

# The onboard Wi-Fi (or the first one)
wifi_device() {
    nmcli -t -f DEVICE,TYPE device 2>/dev/null | awk -F: '$2 == "wifi" { print $1; exit }'
}

# Devices on the setup Wi-Fi
stations() {
    /usr/sbin/iw dev "$1" station dump 2>/dev/null | grep -c '^Station' || true
}

# The setup Wi-Fi is up (not between two tries of wifi-connect)
ap_up() {
    /usr/sbin/iw dev "$1" info 2>/dev/null | grep -q 'type AP'
}

# The SSIDs of the Wi-Fi networks this Pi knows and joins by itself
# (nmcli -g escapes ":" and "\\" with a backslash: undone here)
known_ssids() {
    local uuid type auto
    while IFS=: read -r uuid type auto; do
        [ "$type" = 802-11-wireless ] && [ "$auto" = yes ] || continue
        case "$(nmcli -g 802-11-wireless.mode connection show uuid "$uuid" 2>/dev/null)" in
            ""|infrastructure)
                nmcli -g 802-11-wireless.ssid connection show uuid "$uuid" 2>/dev/null \
                    | sed 's/\\\(.\)/\1/g' || true ;;
        esac
    done < <(nmcli -t -f UUID,TYPE,AUTOCONNECT connection show 2>/dev/null || true)
}

# iw_escape SSID: the name as `iw scan` prints it - printable ASCII as is, a
# space as is unless first or last, a backslash and every other byte (accents,
# emoji) as \xNN; "Müller WLAN" never matched otherwise
iw_escape() {
    printf '%s' "$1" | od -An -tu1 -v | awk '{ for (i = 1; i <= NF; i++) b[n++] = $i }
        END { for (i = 0; i < n; i++) { c = b[i] + 0
                if (c > 32 && c < 127 && c != 92) printf "%c", c
                else if (c == 32 && i != 0 && i != n - 1) printf " "
                else printf "\\x%02x", c } }'
}

# Is a known Wi-Fi in range? One scan: the onboard radio scans in access
# point mode too (rig, Pi 4, 2026-10-17); only while nobody is on it.
known_in_range() {
    local known seen ssid
    known=$(known_ssids)
    [ -n "$known" ] || return 1
    seen=$(/usr/sbin/iw dev "$1" scan 2>/dev/null | sed -n 's/^[[:space:]]*SSID: //p') || return 1
    while IFS= read -r ssid; do
        [ -n "$ssid" ] && grep -qxF -- "$(iw_escape "$ssid")" <<< "$seen" && return 0
    done <<< "$known"
    return 1
}

# Name and password on the LED panel, in a unit of its own: "Stop It" and
# Clear LEDs stop the scroll there, not this service (review A10)
led_scroll_start() {
    rq_wifi_scroll "$SCROLL_UNIT" "$HARD_LIMIT" "$1" || true
}

led_scroll_stop() {
    rq_wifi_scroll_stop "$SCROLL_UNIT"
}

# Watch the running wifi-connect; REASON says why it should end:
# exited | network | known | idle | limit
watch_portal() {
    local dev="$1" t idle_since last_scan=0 n
    idle_since=$(now)
    REASON=exited
    while kill -0 "$WC_PID" 2>/dev/null; do
        sleep "$POLL"
        kill -0 "$WC_PID" 2>/dev/null || break
        t=$(now)
        if network_up; then REASON=network; return 0; fi
        n=$(stations "$dev")
        [ "${n:-0}" -eq 0 ] || idle_since=$t
        if [ $((t - START)) -ge "$HARD_LIMIT" ]; then REASON=limit; return 0; fi
        if [ $((t - idle_since)) -ge "$IDLE_SECONDS" ]; then REASON=idle; return 0; fi
        if [ "${n:-0}" -eq 0 ] && [ "$JOINS" -lt "$JOIN_TRIES" ] \
            && [ $((t - idle_since)) -ge "$SCAN_AFTER" ] \
            && [ $((t - last_scan)) -ge "$SCAN_EVERY" ] && ap_up "$dev"; then
            last_scan=$t
            if known_in_range "$dev"; then REASON=known; return 0; fi
        fi
    done
}

# End wifi-connect: on TERM it takes its access point down itself; after a
# KILL the profile may stay, so remove an access point of that name
stop_portal() {
    local waited=0 uuid
    if [ -n "$WC_PID" ]; then
        kill -TERM "$WC_PID" 2>/dev/null || true
        while kill -0 "$WC_PID" 2>/dev/null && [ "$waited" -lt 15 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        kill -KILL "$WC_PID" 2>/dev/null || true
        wait "$WC_PID" 2>/dev/null || true
        WC_PID=""
    fi
    for uuid in $(nmcli -t -f UUID,TYPE connection show 2>/dev/null | awk -F: '$2 == "802-11-wireless" { print $1 }'); do
        if [ "$(nmcli -g 802-11-wireless.mode connection show uuid "$uuid" 2>/dev/null)" = ap ] \
            && [ "$(nmcli -g 802-11-wireless.ssid connection show uuid "$uuid" 2>/dev/null)" = "$SSID" ]; then
            nmcli connection delete uuid "$uuid" >/dev/null 2>&1 || true
        fi
    done
}

cleanup() {
    stop_portal
    led_scroll_stop
}

main() {
    ensure_root "$@"
    load_rqb2_env

    local booth_failed=""
    if [ "${HOTSPOT_AT_BOOT:-no}" = yes ]; then
        # rasqberry-hotspot.service has run (this unit comes after it)
        booth_running && exit 0
        warn "Setup hotspot: the booth hotspot (HOTSPOT_AT_BOOT) did not start; without a network the setup Wi-Fi opens instead."
        booth_failed=1
    fi
    [ -n "$booth_failed" ] || [ ! -e "$SEEN" ] || exit 0
    [ -x "$WIFI_CONNECT" ] || { warn "Setup hotspot: wifi-connect is missing."; exit 0; }

    if wait_for_network "$WAIT"; then
        mark_seen
        exit 0
    fi

    ensure_wifi_country
    local dev mac
    dev=$(wifi_device)
    [ -n "$dev" ] || { warn "Setup hotspot: no Wi-Fi device."; exit 0; }
    mac=$(cat "/sys/class/net/$dev/address" 2>/dev/null || echo 00:00)
    mac=${mac//:/}
    SSID="RasQberry-Setup-$(printf '%s' "${mac: -4}" | tr '[:lower:]' '[:upper:]')"

    info "No network: setup hotspot \"$SSID\" (password: $PASSWORD) on $dev."
    trap cleanup EXIT
    trap 'exit 143' TERM
    trap 'exit 130' INT
    START=$(now)
    JOINS=0
    while :; do
        led_scroll_start "Wi-Fi $SSID  ***  password $PASSWORD"
        "$WIFI_CONNECT" --portal-interface "$dev" --portal-ssid "$SSID" --portal-passphrase "$PASSWORD" \
            --activity-timeout "$IDLE_SECONDS" --ui-directory "$UI_DIR" &
        WC_PID=$!
        watch_portal "$dev"
        stop_portal
        led_scroll_stop
        case "$REASON" in
            known)
                info "Setup hotspot: a known Wi-Fi is in range; joining it."
                JOINS=$((JOINS + 1))
                nmcli --wait "$JOIN_WAIT" device connect "$dev" >/dev/null 2>&1 || true
                wait_for_network "$POLL" && break
                [ $(($(now) - START)) -lt "$HARD_LIMIT" ] || break
                info "Setup hotspot: that did not work; the setup Wi-Fi opens again." ;;
            idle)  info "Setup hotspot: nobody on it for $((IDLE_SECONDS / 60)) minutes; it ends."; break ;;
            limit) info "Setup hotspot: open for $((HARD_LIMIT / 60)) minutes; it ends."; break ;;
            *)     break ;;
        esac
    done
    if network_up; then
        mark_seen
        info "Setup hotspot: joined a network."
    else
        info "Setup hotspot: ended without a network; the Pi keeps trying the known ones."
    fi
}

# Sourced (tests): the functions only
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0
main "$@"
