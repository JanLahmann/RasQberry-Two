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
#   Only while the Pi has never had a network: once Ethernet or Wi-Fi was up
#   at a start (network-seen, on /data where there is one, so both A/B slots
#   share it), it does not start again. It ends after 30
#   minutes without anyone on it; NetworkManager then keeps trying the known
#   networks. Not when the booth hotspot starts at boot (HOTSPOT_AT_BOOT).
#   The LED panel scrolls the name and password while it runs.
#
# Usage: rq_setup_hotspot.sh   (as root; rasqberry-setup-hotspot.service)
# Environment (tests): RQ_SETUP_WAIT (seconds, default 120), RQ_NETWORK_SEEN

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
PASSWORD="rasqberry"
UI_DIR="/usr/share/rasqberry/setup-portal"
WIFI_CONNECT="/usr/local/sbin/wifi-connect"
IDLE_SECONDS=1800

# Is the Pi on a network (Ethernet or Wi-Fi with an address)?
network_up() {
    case "$(nmcli -t -f STATE general 2>/dev/null)" in
        connected*) return 0 ;;
    esac
    return 1
}

# The Wi-Fi country from the time zone (Imager sets it even without Wi-Fi):
# without a country the Wi-Fi stays off (rfkill)
wifi_country_from_timezone() {
    local tz
    tz=$(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || true)
    [ -n "$tz" ] || return 1
    awk -v tz="$tz" '!/^#/ && $3 == tz { print $1; exit }' /usr/share/zoneinfo/zone.tab 2>/dev/null
}

ensure_wifi_country() {
    local country
    country=$(/usr/sbin/iw reg get 2>/dev/null | awk '/^country/ { sub(":", "", $2); print $2; exit }')
    if [ -z "$country" ] || [ "$country" = 00 ]; then
        country=$(wifi_country_from_timezone || true)
        [ -n "$country" ] || country=GB
        info "Setup hotspot: Wi-Fi country set to $country (from the time zone)."
        raspi-config nonint do_wifi_country "$country" >/dev/null 2>&1 || /usr/sbin/iw reg set "$country" 2>/dev/null || true
    fi
    rfkill unblock wifi 2>/dev/null || true
}

# The onboard Wi-Fi (or the first one)
wifi_device() {
    nmcli -t -f DEVICE,TYPE device 2>/dev/null | awk -F: '$2 == "wifi" { print $1; exit }'
}

# Scroll name and password on the LED panel while the setup hotspot runs
led_scroll_start() {
    local text="$1" py
    py=$(find_venv 2>/dev/null)/bin/python3
    [ -x "$py" ] || py=python3
    "$py" /usr/bin/rq_display_ip.py --text "$text" --duration "$IDLE_SECONDS" --speed 0.08 --brightness 0.3 \
        >/dev/null 2>&1 &
    LED_PID=$!
}

led_scroll_stop() {
    if [ -n "${LED_PID:-}" ]; then
        kill "$LED_PID" 2>/dev/null || true
        wait "$LED_PID" 2>/dev/null || true
    fi
}

main() {
    ensure_root "$@"
    load_rqb2_env

    [ "${HOTSPOT_AT_BOOT:-no}" = yes ] && exit 0
    [ -e "$SEEN" ] && exit 0
    [ -x "$WIFI_CONNECT" ] || { warn "Setup hotspot: wifi-connect is missing."; exit 0; }

    local waited=0
    while [ "$waited" -lt "$WAIT" ]; do
        if network_up; then
            mkdir -p "$(dirname "$SEEN")"; touch "$SEEN"
            exit 0
        fi
        sleep 5
        waited=$((waited + 5))
    done

    ensure_wifi_country
    local dev mac ssid
    dev=$(wifi_device)
    [ -n "$dev" ] || { warn "Setup hotspot: no Wi-Fi device."; exit 0; }
    mac=$(cat "/sys/class/net/$dev/address" 2>/dev/null || echo 00:00)
    mac=${mac//:/}
    ssid="RasQberry-Setup-$(printf '%s' "${mac: -4}" | tr '[:lower:]' '[:upper:]')"

    info "No network: setup hotspot \"$ssid\" (password: $PASSWORD) on $dev."
    trap led_scroll_stop EXIT
    led_scroll_start "Wi-Fi $ssid  ***  password $PASSWORD"
    "$WIFI_CONNECT" --portal-interface "$dev" --portal-ssid "$ssid" --portal-passphrase "$PASSWORD" \
        --activity-timeout "$IDLE_SECONDS" --ui-directory "$UI_DIR" || true
    led_scroll_stop
    if network_up; then
        mkdir -p "$(dirname "$SEEN")"; touch "$SEEN"
        info "Setup hotspot: joined a network."
    else
        info "Setup hotspot: ended without a network; the Pi keeps trying the known ones."
    fi
}

# Sourced (tests): the functions only
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0
main "$@"
