#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Wi-Fi hotspot for booths and classrooms
# ============================================================================
# Description: The Pi opens its own Wi-Fi, so phones and laptops reach the
#   demos where the venue's Wi-Fi keeps devices apart (client isolation).
#   A NetworkManager profile ("rasqberry-hotspot"): WPA2 (rsn/ccmp - the
#   onboard chip cannot run WPA3 as a hotspot), PMF off (trixie-feedback#29),
#   ipv4 shared (NetworkManager's own DHCP and DNS, address 10.42.0.1).
#   The profile is made anew from the settings at every start.
#
#   Settings (rasqberry_environment.env, kept on /data across A/B updates):
#     HOTSPOT_SSID            empty: RasQberry-XXXX (end of the MAC address)
#     HOTSPOT_PASSWORD        empty: a random one, made at the first start, kept
#     HOTSPOT_BAND            a (5 GHz, channel 36: no trouble with Bluetooth
#                             speakers) or bg (2.4 GHz, channel 6, old devices)
#     HOTSPOT_INTERFACE       auto: a USB Wi-Fi adapter if there is one, else
#                             the onboard Wi-Fi (which then is the hotspot only:
#                             one radio cannot be hotspot and client reliably)
#     HOTSPOT_SHARE_INTERNET  yes: devices on the hotspot reach the internet
#                             through the Pi's other connection; no: the Pi only
#     HOTSPOT_AT_BOOT         yes: the hotspot starts with the Pi
#   A file rasqberry-hotspot.txt on the boot partition (put there after
#   flashing, from any computer) sets these before the first start; "boot"
#   saves it and keeps no password on the card.
#
# Usage: rq_hotspot.sh on|off|status|qr|card|boot   (as root)
#   card: the join card (QR codes, name, password) in the browser, to show or print

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

PROFILE="rasqberry-hotspot"
ADDRESS="10.42.0.1"
NFT_TABLE="rasqberry_hotspot"
BOOT_FILE="${RQ_HOTSPOT_BOOT_FILE:-/boot/firmware/rasqberry-hotspot.txt}"
SETTINGS="HOTSPOT_SSID HOTSPOT_PASSWORD HOTSPOT_BAND HOTSPOT_INTERFACE HOTSPOT_SHARE_INTERNET HOTSPOT_AT_BOOT"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# valid_setting KEY VALUE: is VALUE allowed for KEY?
valid_setting() {
    local value="$2"
    case "$1" in
        HOTSPOT_SSID)      [ -z "$value" ] || [ "$(printf '%s' "$value" | wc -c)" -le 32 ] ;;
        HOTSPOT_PASSWORD)  [ -z "$value" ] || { [ "${#value}" -ge 8 ] && [ "${#value}" -le 63 ] \
                               && printf '%s' "$value" | LC_ALL=C grep -q '^[[:print:]]*$'; } ;;
        HOTSPOT_BAND)      [ "$value" = a ] || [ "$value" = bg ] ;;
        HOTSPOT_INTERFACE) [ "$value" = auto ] || [[ "$value" =~ ^[A-Za-z0-9_.-]{1,15}$ ]] ;;
        HOTSPOT_SHARE_INTERNET|HOTSPOT_AT_BOOT) [ "$value" = yes ] || [ "$value" = no ] ;;
        *) return 1 ;;
    esac
}

# setting KEY DEFAULT: the saved value, or DEFAULT when it is missing or invalid
setting() {
    local value="${!1:-}"
    if [ -n "$value" ] && valid_setting "$1" "$value"; then echo "$value"; else echo "$2"; fi
}

# The Wi-Fi device for the hotspot: HOTSPOT_INTERFACE, or (auto) a USB
# adapter before the onboard Wi-Fi (brcmfmac)
hotspot_interface() {
    local wanted dev driver onboard=""
    wanted=$(setting HOTSPOT_INTERFACE auto)
    if [ "$wanted" != auto ]; then echo "$wanted"; return 0; fi
    for dev in $(nmcli -t -f DEVICE,TYPE device 2>/dev/null | awk -F: '$2 == "wifi" { print $1 }'); do
        driver=$(basename "$(readlink -f "/sys/class/net/$dev/device/driver" 2>/dev/null)" 2>/dev/null || true)
        if [ "$driver" = brcmfmac ]; then onboard="${onboard:-$dev}"; else echo "$dev"; return 0; fi
    done
    [ -n "$onboard" ] && echo "$onboard"
}

# RasQberry-XXXX: the last four hex digits of the device's MAC address
default_ssid() {
    local mac
    mac=$(cat "/sys/class/net/$1/address" 2>/dev/null || echo "00:00")
    mac=${mac//:/}
    echo "RasQberry-$(printf '%s' "${mac: -4}" | tr '[:lower:]' '[:upper:]')"
}

# 10 characters without look-alikes (0/O, 1/l/I)
new_password() {
    python3 -c 'import secrets; a = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"; print("".join(secrets.choice(a) for _ in range(10)))'
}

# The hotspot's password; made and saved at the first start
hotspot_password() {
    local pw
    pw=$(setting HOTSPOT_PASSWORD "")
    if [ -z "$pw" ]; then
        pw=$(new_password)
        update_env_var HOTSPOT_PASSWORD "$pw" >/dev/null || warn "The new hotspot password could not be saved; it changes at the next start."
    fi
    echo "$pw"
}

# ---------------------------------------------------------------------------
# Boot-partition file
# ---------------------------------------------------------------------------

# Save the settings from rasqberry-hotspot.txt, then keep the file without the
# password (as rasqberry-hotspot.applied.txt), so it is applied once
apply_boot_file() {
    [ -f "$BOOT_FILE" ] || return 0
    local line key value applied="${BOOT_FILE%.txt}.applied.txt" n=0
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%$'\r'}
        case "$line" in ""|\#*) continue ;; esac
        key=${line%%=*}; value=${line#*=}
        key=$(printf '%s' "$key" | tr -d '[:space:]')
        value=${value%\"}; value=${value#\"}
        case " $SETTINGS " in *" $key "*) ;; *) warn "rasqberry-hotspot.txt: unknown setting $key"; continue ;; esac
        if valid_setting "$key" "$value"; then
            update_env_var "$key" "$value" >/dev/null && n=$((n + 1))
        else
            warn "rasqberry-hotspot.txt: $key has a value that is not allowed; left as it was"
        fi
    done < "$BOOT_FILE"
    sed -E 's/^([[:space:]]*HOTSPOT_PASSWORD[[:space:]]*=).*/# HOTSPOT_PASSWORD was saved on the Pi/' "$BOOT_FILE" > "$applied"
    rm -f "$BOOT_FILE"
    info "Hotspot: $n setting(s) taken from the boot partition."
    load_rqb2_env
}

# ---------------------------------------------------------------------------
# Internet sharing
# ---------------------------------------------------------------------------

# share_rules IFACE: with HOTSPOT_SHARE_INTERNET=no, forwarding to and from
# the hotspot is dropped (NetworkManager 1.52 has no ipv4.forwarding); with
# yes, NetworkManager's NAT must be there (missing after boot: trixie-feedback#62)
share_rules() {
    local iface="$1"
    nft delete table inet "$NFT_TABLE" 2>/dev/null || true
    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = no ]; then
        nft -f - <<EOF
table inet $NFT_TABLE {
    chain forward {
        type filter hook forward priority filter - 1; policy accept;
        iifname "$iface" drop
        oifname "$iface" drop
    }
}
EOF
    fi
}

nat_ready() {
    nft list tables 2>/dev/null | grep -q "nm-shared-$1"
}

# ---------------------------------------------------------------------------
# Demos that show an address to phones
# ---------------------------------------------------------------------------

ENT_ENV="${RQ_HOTSPOT_ENTANGIBLE_ENV:-/etc/default/entangible}"
ENT_MARK="# rq_hotspot.sh: phones on the hotspot use its address (removed when it stops)"

# advertise on|off: Entangible prints the address phones open (QR codes, its
# TLS certificate); without QAMPOSER_ADVERTISE_HOST it takes the default
# route's, which a hotspot without internet does not have. A value the user
# set stays; ours comes with a marker line and goes when the hotspot stops.
advertise() {
    [ -f "$ENT_ENV" ] || return 0
    local tmp changed=""
    tmp=$(mktemp)
    awk -v m="$ENT_MARK" '$0 == m { skip = 1; next } skip { skip = 0; next } { print }' "$ENT_ENV" > "$tmp"
    cmp -s "$tmp" "$ENT_ENV" || changed=1
    if [ "$1" = on ] && ! grep -q '^[[:space:]]*QAMPOSER_ADVERTISE_HOST[[:space:]]*=' "$tmp"; then
        printf '%s\nQAMPOSER_ADVERTISE_HOST=%s\n' "$ENT_MARK" "$ADDRESS" >> "$tmp"
        changed=1
    fi
    if [ -n "$changed" ]; then
        cat "$tmp" > "$ENT_ENV"
        if systemctl is-active --quiet entangible-host.service 2>/dev/null; then
            systemctl restart entangible-host.service 2>/dev/null || true
        fi
    fi
    rm -f "$tmp"
}

# ---------------------------------------------------------------------------
# Landing page (rq_hotspot_portal.py)
# ---------------------------------------------------------------------------

CAPTIVE_CONF="${RQ_HOTSPOT_CAPTIVE_CONF:-/etc/NetworkManager/dnsmasq-shared.d/rasqberry-hotspot-captive.conf}"
PORTAL_ENV="${RQ_HOTSPOT_PORTAL_ENV:-/run/rasqberry/hotspot-portal.env}"

# Without internet to share, every name points to the Pi: phones then find
# the landing page by themselves on joining (and say "no internet"). Written
# before the hotspot starts - NetworkManager's dnsmasq reads it then.
captive_dns() {
    local iface="$1" uplink
    uplink=$(ip -4 route show default 2>/dev/null | awk -v i="$iface" '$0 !~ ("dev " i " ") { print; exit }')
    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ] && [ -n "$uplink" ]; then
        rm -f "$CAPTIVE_CONF"
    else
        mkdir -p "$(dirname "$CAPTIVE_CONF")"
        printf '# rq_hotspot.sh: no internet on the hotspot, so every name leads to the landing page\naddress=/#/%s\n' "$ADDRESS" > "$CAPTIVE_CONF"
    fi
}

# portal on SSID IFACE | portal off
# The page says whether this Wi-Fi reaches the internet: yes when names are
# not all pointed to the Pi (captive_dns: sharing on and a way out) and the
# NAT is there; the page itself checks the way out again at every visit
# (rig mission 2026-10-16: it always said "no internet").
portal() {
    if [ "$1" = on ]; then
        local internet=no
        if [ ! -f "$CAPTIVE_CONF" ] && nat_ready "${3:-}"; then
            internet=yes
        fi
        mkdir -p "$(dirname "$PORTAL_ENV")"
        printf 'RQ_HOTSPOT_SSID=%s\nRQ_HOTSPOT_INTERNET=%s\nRQ_HOTSPOT_IFACE=%s\n' \
            "$2" "$internet" "${3:-}" > "$PORTAL_ENV"
        systemctl restart rasqberry-hotspot-portal.service 2>/dev/null \
            || warn "The landing page (http://$ADDRESS) did not start."
    else
        systemctl stop rasqberry-hotspot-portal.service 2>/dev/null || true
        rm -f "$CAPTIVE_CONF" "$PORTAL_ENV"
    fi
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

wifi_country() {
    /usr/sbin/iw reg get 2>/dev/null | awk '/^country/ { sub(":", "", $2); print $2; exit }'
}

qr_text() {
    # WIFI:T:WPA;S:<ssid>;P:<password>;; with \ ; , : " escaped
    local esc='s/([\\;,:"])/\\\1/g'
    printf 'WIFI:T:WPA;S:%s;P:%s;;' "$(printf '%s' "$1" | sed -E "$esc")" "$(printf '%s' "$2" | sed -E "$esc")"
}

show_join() {
    local ssid="$1" pw="$2"
    echo "Wi-Fi:    $ssid"
    echo "Password: $pw"
    echo "Address:  http://$ADDRESS"
    if command -v qrencode >/dev/null 2>&1; then
        echo "Scan to join:"
        qrencode -t ANSIUTF8 -m 2 "$(qr_text "$ssid" "$pw")" 2>/dev/null || true
    fi
}

cmd_on() {
    local quiet="${1:-}" iface ssid pw band channel label country client
    iface=$(hotspot_interface)
    [ -n "$iface" ] || die "No Wi-Fi device found for the hotspot."
    country=$(wifi_country)
    if [ -z "$country" ] || [ "$country" = 00 ]; then
        die "The Wi-Fi country is not set, so the Wi-Fi stays off. Set it first: sudo raspi-config > Localisation Options > WLAN Country."
    fi
    ssid=$(setting HOTSPOT_SSID "$(default_ssid "$iface")")
    pw=$(hotspot_password)
    band=$(setting HOTSPOT_BAND a)
    if [ "$band" = a ]; then channel=36; label="5 GHz"; else channel=6; label="2.4 GHz"; fi

    client=$(nmcli -t -f DEVICE,STATE,CONNECTION device 2>/dev/null \
        | awk -F: -v d="$iface" -v p="$PROFILE" '$1 == d && $2 == "connected" && $3 != p { print $3 }')
    [ -n "$client" ] && [ -z "$quiet" ] && \
        info "$iface leaves the Wi-Fi \"$client\" while the hotspot runs (one radio cannot be both)."

    captive_dns "$iface"
    nmcli connection delete "$PROFILE" >/dev/null 2>&1 || true
    nmcli connection add type wifi con-name "$PROFILE" ifname "$iface" ssid "$ssid" \
        connection.autoconnect no \
        802-11-wireless.mode ap 802-11-wireless.band "$band" 802-11-wireless.channel "$channel" \
        wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp \
        wifi-sec.pmf 1 wifi-sec.psk "$pw" \
        ipv4.method shared ipv4.addresses "$ADDRESS/24" ipv6.method disabled >/dev/null \
        || die "The hotspot profile could not be made."
    chmod 600 "/etc/NetworkManager/system-connections/$PROFILE.nmconnection" 2>/dev/null || true
    nmcli --wait 30 connection up "$PROFILE" >/dev/null 2>&1 \
        || die "The hotspot did not start on $iface (band $band, channel $channel). See: journalctl -u NetworkManager -n 30"

    share_rules "$iface"
    advertise on
    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ] && ! nat_ready "$iface"; then
        # trixie-feedback#62: NAT missing - once more brings it
        nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
        nmcli --wait 30 connection up "$PROFILE" >/dev/null 2>&1 || true
        nat_ready "$iface" || warn "Internet sharing is on, but NetworkManager set up no NAT for $iface."
    fi
    # after the NAT check: the page says whether there is internet
    portal on "$ssid" "$iface"
    [ -n "$quiet" ] || { info "Hotspot on ($iface, $label, channel $channel)."; show_join "$ssid" "$pw"; }
}

cmd_off() {
    if nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx "$PROFILE"; then
        nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
        info "Hotspot off. The Wi-Fi joins its usual network again."
    else
        info "The hotspot is not running."
    fi
    nft delete table inet "$NFT_TABLE" 2>/dev/null || true
    advertise off
    portal off
}

cmd_status() {
    local iface ssid clients
    if ! nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx "$PROFILE"; then
        echo "Hotspot: off (at boot: $(setting HOTSPOT_AT_BOOT no))"
        return 0
    fi
    iface=$(nmcli -g connection.interface-name connection show "$PROFILE" 2>/dev/null)
    ssid=$(nmcli -g 802-11-wireless.ssid connection show "$PROFILE" 2>/dev/null)
    clients=$(/usr/sbin/iw dev "$iface" station dump 2>/dev/null | grep -c '^Station' || true)
    echo "Hotspot: on ($iface, $ssid, $(nmcli -g 802-11-wireless.band connection show "$PROFILE" | sed 's/^a$/5 GHz/;s/^bg$/2.4 GHz/'))"
    echo "Devices connected: ${clients:-0}"
    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ]; then
        if nat_ready "$iface"; then echo "Internet sharing: on"; else echo "Internet sharing: on, but no NAT set up"; fi
    else
        echo "Internet sharing: off"
    fi
    echo "At boot: $(setting HOTSPOT_AT_BOOT no)"
}

cmd_qr() {
    local iface
    iface=$(hotspot_interface)
    show_join "$(setting HOTSPOT_SSID "$(default_ssid "${iface:-wlan0}")")" "$(hotspot_password)"
}

# The join card: Wi-Fi QR code, name, password and the landing page - on
# the screen at a booth, or printed (one A6 card; the browser prints it)
html_escape() {
    sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'
}

write_card() {
    local ssid="$1" pw="$2" out="$3" wifi_svg url_svg
    command -v qrencode >/dev/null 2>&1 || die "qrencode is missing (sudo apt install qrencode)."
    wifi_svg=$(qrencode -t SVG -m 1 --svg-path -o - "$(qr_text "$ssid" "$pw")" | sed '1,/<svg/{/<svg/!d}')
    url_svg=$(qrencode -t SVG -m 1 --svg-path -o - "http://$ADDRESS/" | sed '1,/<svg/{/<svg/!d}')
    cat > "$out" <<CARD
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join the RasQberry Wi-Fi</title>
<style>
@page { size: A6; margin: 8mm; }
* { box-sizing: border-box; }
body { margin: 0; background: #f4f4f4; color: #161616; font: 18px/1.4 system-ui, sans-serif; }
.card { max-width: 420px; margin: 24px auto; background: #fff; border: 1px solid #c6c6c6; border-radius: 12px; padding: 24px; text-align: center; }
h1 { font-size: 24px; margin: 0 0 4px; }
.step { color: #525252; margin: 18px 0 8px; font-size: 16px; }
.qr svg { width: 200px; height: 200px; }
.qr.small svg { width: 120px; height: 120px; }
.field { font-size: 15px; color: #525252; margin-top: 8px; }
.value { font: 600 22px/1.3 ui-monospace, monospace; word-break: break-all; }
.print { margin: 0 auto 24px; display: block; padding: 10px 18px; font-size: 16px; border-radius: 8px; border: 1px solid #8d8d8d; background: #fff; }
@media print { body { background: #fff; } .card { margin: 0; border: none; } .print { display: none; } }
</style></head>
<body>
<div class="card">
  <h1>RasQberry Two</h1>
  <div>Quantum computing demos on this Wi-Fi</div>
  <div class="step">1. Scan to join the Wi-Fi</div>
  <div class="qr">$wifi_svg</div>
  <div class="field">Wi-Fi</div><div class="value">$(printf '%s' "$ssid" | html_escape)</div>
  <div class="field">Password</div><div class="value">$(printf '%s' "$pw" | html_escape)</div>
  <div class="step">2. Then open the demos</div>
  <div class="qr small">$url_svg</div>
  <div class="value">http://$ADDRESS</div>
</div>
<button class="print" onclick="window.print()">Print this card</button>
</body></html>
CARD
}

cmd_card() {
    local iface ssid pw dir out user
    iface=$(hotspot_interface)
    ssid=$(setting HOTSPOT_SSID "$(default_ssid "${iface:-wlan0}")")
    pw=$(hotspot_password)
    user=$(get_user_name)
    dir="${USER_HOME:-/home/$user}/.cache/rasqberry"
    mkdir -p "$dir"
    out="$dir/hotspot-card.html"
    write_card "$ssid" "$pw" "$out"
    chown "$user:" "$dir" "$out" 2>/dev/null || true
    chmod 600 "$out"
    info "Join card: $out"
    rq_open_browser "file://$out" >/dev/null 2>&1 || info "Open it in the browser to show or print it."
}

cmd_boot() {
    apply_boot_file
    [ "$(setting HOTSPOT_AT_BOOT no)" = yes ] || exit 0
    cmd_on quiet
}

# Sourced (tests): the functions only
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0

rq_help_guard "$@"
ensure_root "$@"
load_rqb2_env

case "${1:-}" in
    on)     cmd_on ;;
    off)    cmd_off ;;
    status) cmd_status ;;
    qr)     cmd_qr ;;
    card)   cmd_card ;;
    boot)   cmd_boot ;;
    *)      echo "Usage: $(basename "$0") on|off|status|qr|card|boot" >&2; exit 2 ;;
esac
