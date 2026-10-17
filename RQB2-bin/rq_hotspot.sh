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
#   Name and password: a root-only file (mode 600), read as plain text and
#     never loaded as shell code - /data/rasqberry/hotspot.conf where there
#     is /data (both A/B slots share it), else /var/lib/rasqberry/hotspot.conf.
#     They used to be in rasqberry_environment.env, which every script and
#     raspi-config load as shell code and anyone can read: a name such as
#     "Booth (Hall 3)" stopped raspi-config (review D1). "migrate" moves
#     values found there into the file.
#     HOTSPOT_SSID            empty: RasQberry-XXXX (end of the MAC address)
#     HOTSPOT_PASSWORD        empty: a random one, made at the first start, kept
#   Settings (rasqberry_environment.env, kept on /data across A/B updates):
#     HOTSPOT_BAND            a (5 GHz, channel 36: no trouble with Bluetooth
#                             speakers) or bg (2.4 GHz, channel 6, old devices)
#     HOTSPOT_INTERFACE       auto: a USB Wi-Fi adapter if there is one, else
#                             the onboard Wi-Fi (which then is the hotspot only:
#                             one radio cannot be hotspot and client reliably)
#     HOTSPOT_SHARE_INTERNET  yes: devices on the hotspot reach the internet
#                             through the Pi's other connection; no: the Pi only
#     HOTSPOT_AT_BOOT         yes: the hotspot starts with the Pi
#     HOTSPOT_ALLOW_ADMIN     no (default): devices on the hotspot cannot use
#                             SSH or VNC on the Pi (its password is on a
#                             public card); yes: they can
#   A file rasqberry-hotspot.txt on the boot partition (put there after
#   flashing, from any computer) sets these before the first start; "boot"
#   saves it and keeps no password on the card.
#
# Usage: rq_hotspot.sh on|off|status|qr|card|boot   (as root)
#   card: the join card (QR codes, name, password) in the browser, to show or print
#   get KEY: a saved setting (empty: the default)
#   set KEY...: save settings, one value per line on stdin, all or none
#     (checked first; the reason goes to stderr) - the menu uses this
#   migrate: move a name or password from the environment file into their own file

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

PROFILE="rasqberry-hotspot"
ADDRESS="10.42.0.1"
NFT_TABLE="rasqberry_hotspot"
BOOT_FILE="${RQ_HOTSPOT_BOOT_FILE:-/boot/firmware/rasqberry-hotspot.txt}"
SETTINGS="HOTSPOT_SSID HOTSPOT_PASSWORD HOTSPOT_BAND HOTSPOT_INTERFACE HOTSPOT_SHARE_INTERNET HOTSPOT_AT_BOOT HOTSPOT_ALLOW_ADMIN"
SECRET_KEYS="HOTSPOT_SSID HOTSPOT_PASSWORD"
if [ -n "${RQ_HOTSPOT_SECRETS:-}" ]; then
    SECRETS="$RQ_HOTSPOT_SECRETS"
elif mountpoint -q /data 2>/dev/null; then
    SECRETS=/data/rasqberry/hotspot.conf
else
    SECRETS=/var/lib/rasqberry/hotspot.conf
fi
# The A/B store of device settings: an older slot may have put the name there
DEVICE_STORE="${RQ_SETTINGS_DIR:-/data/rasqberry}/device-settings.env"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# count_bytes TEXT [TR-SET]: bytes of TEXT (only those in TR-SET, if given)
count_bytes() {
    if [ -n "${2:-}" ]; then
        printf '%s' "$1" | LC_ALL=C tr -dc "$2" | wc -c | tr -d ' '
    else
        printf '%s' "$1" | wc -c | tr -d ' '
    fi
}

# valid_setting KEY VALUE: is VALUE allowed for KEY?
# A name has 1-32 bytes (UTF-8 is fine) and no control characters; a WPA2
# password 8-63 printable ASCII characters (spaces and punctuation are fine).
valid_setting() {
    local value="$2"
    case "$1" in
        HOTSPOT_SSID)      [ -z "$value" ] || { [ "$(count_bytes "$value")" -le 32 ] \
                               && [ "$(count_bytes "$value" '\001-\037\177')" -eq 0 ]; } ;;
        HOTSPOT_PASSWORD)  [ -z "$value" ] || { [ "$(count_bytes "$value")" -ge 8 ] \
                               && [ "$(count_bytes "$value")" -le 63 ] \
                               && [ "$(count_bytes "$value" ' -~')" -eq "$(count_bytes "$value")" ]; } ;;
        HOTSPOT_BAND)      [ "$value" = a ] || [ "$value" = bg ] ;;
        HOTSPOT_INTERFACE) [ "$value" = auto ] || [[ "$value" =~ ^[A-Za-z0-9_.-]{1,15}$ ]] ;;
        HOTSPOT_SHARE_INTERNET|HOTSPOT_AT_BOOT|HOTSPOT_ALLOW_ADMIN) [ "$value" = yes ] || [ "$value" = no ] ;;
        *) return 1 ;;
    esac
}

# setting_rule KEY: what valid_setting asks for, in words
setting_rule() {
    case "$1" in
        HOTSPOT_SSID)     echo "The name has up to 32 characters (fewer with accents or emoji)." ;;
        HOTSPOT_PASSWORD) echo "The password needs 8 to 63 characters: letters, digits, spaces and punctuation, without accents or emoji (WPA2)." ;;
        HOTSPOT_BAND)     echo "The band is a (5 GHz) or bg (2.4 GHz)." ;;
        HOTSPOT_INTERFACE) echo "The Wi-Fi device is auto or a device name such as wlan1." ;;
        HOTSPOT_*)        echo "$1 is yes or no." ;;
        *)                echo "$1 is not a hotspot setting." ;;
    esac
}

is_secret() { case " $SECRET_KEYS " in *" $1 "*) return 0 ;; esac; return 1; }

# secret_get KEY: the saved name or password ('' when there is none)
secret_get() {
    [ -f "$SECRETS" ] || return 0
    awk -v k="$1=" 'index($0, k) == 1 { v = substr($0, length(k) + 1) } END { printf "%s", v }' "$SECRETS"
}

# secret_set KEY VALUE: save it (an empty VALUE removes it: the default)
secret_set() {
    local dir tmp
    dir=$(dirname "$SECRETS")
    (umask 077; mkdir -p "$dir") || return 1
    tmp=$(umask 077; mktemp "$dir/.hotspot.XXXXXX") || return 1
    if {
        echo "# RasQberry Wi-Fi hotspot name and password (rq_hotspot.sh): plain text, never run as shell code."
        if [ -f "$SECRETS" ]; then grep -v -e '^#' -e "^$1=" "$SECRETS" || true; fi
        if [ -n "$2" ]; then printf '%s=%s\n' "$1" "$2"; fi
    } > "$tmp" && chmod 600 "$tmp" && mv -f "$tmp" "$SECRETS"; then
        return 0
    fi
    rm -f "$tmp"
    return 1
}

# save_setting KEY VALUE: name and password to their own file, the rest to
# the environment file (and from there to /data)
save_setting() {
    if is_secret "$1"; then
        secret_set "$1" "$2"
    else
        update_env_var "$1" "$2" >/dev/null
    fi
}

# setting KEY DEFAULT: the saved value, or DEFAULT when it is missing or invalid
setting() {
    local value
    if is_secret "$1"; then value=$(secret_get "$1"); else value="${!1:-}"; fi
    if [ -n "$value" ] && valid_setting "$1" "$value"; then echo "$value"; else echo "$2"; fi
}

# unquote VALUE: without one pair of surrounding quotes ("x" or 'x')
unquote() {
    local v="$1"
    if [ "${#v}" -ge 2 ]; then
        case "$v" in
            \"*\") v=${v#\"}; v=${v%\"} ;;
            \'*\') v=${v#\'}; v=${v%\'} ;;
        esac
    fi
    printf '%s' "$v"
}

# migrate: a name or password in the environment file (written there, as
# typed, before they had their own file) moves to the file; the lines leave
# the environment file, which then loads cleanly again. A fresh A/B slot finds
# them in the /data store an older slot wrote. Runs at every boot, before
# anything loads the environment (rasqberry-load-boot-config.sh).
migrate_secrets() {
    local env="$RQ_ENV_FILE" key line value tmp first=""
    [ -f "$env" ] || return 0
    # the /data store only before the file exists: later, a missing key is
    # the user's choice (the default), not something to fetch again
    [ -f "$SECRETS" ] || first=1
    for key in $SECRET_KEYS; do
        [ -z "$(secret_get "$key")" ] || continue
        line=$(grep -a "^$key=" "$env" 2>/dev/null | tail -n 1 || true)
        if [ -z "${line#*=}" ] && [ -n "$first" ] && [ -f "$DEVICE_STORE" ]; then
            line=$(grep -a "^$key=" "$DEVICE_STORE" 2>/dev/null | tail -n 1 || true)
        fi
        value=$(unquote "${line#*=}")
        [ -n "$value" ] || continue
        if valid_setting "$key" "$value"; then
            secret_set "$key" "$value" && info "Hotspot: $key moved to $SECRETS."
        else
            warn "Hotspot: the saved $key is not allowed and was dropped. $(setting_rule "$key")"
        fi
    done
    grep -qE '^HOTSPOT_(SSID|PASSWORD)=' "$env" || return 0
    tmp=$(mktemp "$(dirname "$env")/.rasqberry_environment.XXXXXX") || return 1
    if grep -vE '^HOTSPOT_(SSID|PASSWORD)=' "$env" > "$tmp" && [ -s "$tmp" ] \
        && chmod 644 "$tmp" && mv -f "$tmp" "$env"; then
        return 0
    fi
    rm -f "$tmp"
    warn "Hotspot: could not take the name and password out of $env."
    return 1
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
        secret_set HOTSPOT_PASSWORD "$pw" || warn "The new hotspot password could not be saved; it changes at the next start."
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
        value=$(unquote "$value")
        case " $SETTINGS " in *" $key "*) ;; *) warn "rasqberry-hotspot.txt: unknown setting $key"; continue ;; esac
        if valid_setting "$key" "$value"; then
            save_setting "$key" "$value" && n=$((n + 1))
        else
            warn "rasqberry-hotspot.txt: $key has a value that is not allowed; left as it was. $(setting_rule "$key")"
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

# share_rules IFACE: the hotspot's firewall, table inet rasqberry_hotspot
# (gone with the hotspot: cmd_off, the NetworkManager hook, a reboot)
#  - SSH (22) and VNC (5900) from devices on the hotspot are dropped, unless
#    HOTSPOT_ALLOW_ADMIN=yes: its password is on a public card, and the Pi
#    may still have the demo password with passwordless sudo (review A2).
#  - HOTSPOT_SHARE_INTERNET=no: nothing passes between the hotspot and other
#    networks (NetworkManager 1.52 has no ipv4.forwarding) - except replies
#    and the demos' own ports: Docker reaches a published port by DNAT and
#    forwarding, which the drop caught (A3).
#  - yes: NetworkManager's NAT must be there (missing after boot:
#    trixie-feedback#62), and Docker's FORWARD policy DROP must not catch the
#    hotspot's traffic (docker_rules, A4).
share_rules() {
    local iface="$1"
    nft delete table inet "$NFT_TABLE" 2>/dev/null || true
    {
        echo "table inet $NFT_TABLE {"
        echo "    chain input {"
        echo "        type filter hook input priority filter - 1; policy accept;"
        if [ "$(setting HOTSPOT_ALLOW_ADMIN no)" != yes ]; then
            echo "        iifname \"$iface\" tcp dport { 22, 5900 } drop"
        fi
        echo "    }"
        if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = no ]; then
            echo "    chain forward {"
            echo "        type filter hook forward priority filter - 1; policy accept;"
            echo "        ct state established,related accept"
            echo "        ct status dnat accept"
            echo "        iifname \"$iface\" drop"
            echo "        oifname \"$iface\" drop"
            echo "    }"
        fi
        echo "}"
    } | nft -f - || warn "The hotspot's firewall rules could not be set (nft)."
    docker_rules "$iface"
}

# Docker sets the iptables FORWARD policy to DROP when it starts, and a drop
# in any chain wins over NetworkManager's sharing: devices on the hotspot got
# no internet while Docker ran (review A4). With sharing on, the hotspot's
# traffic gets an accept in DOCKER-USER, the chain Docker keeps for rules of
# its users (made here when Docker has not started yet; Docker keeps it).
# Traffic to Docker's own bridges still goes through Docker's rules: only
# published ports, not every container port (RETURN, above the accept).
DOCKER_MARK="rasqberry-hotspot"
docker_rules() {
    command -v iptables >/dev/null 2>&1 || return 0
    docker_rules_off
    [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ] || return 0
    local c=(-m comment --comment "$DOCKER_MARK")
    iptables -N DOCKER-USER 2>/dev/null || true
    # -I puts each rule on top: the last one is checked first
    iptables -I DOCKER-USER -o "$1" -m conntrack --ctstate RELATED,ESTABLISHED "${c[@]}" -j ACCEPT \
        && iptables -I DOCKER-USER -i "$1" "${c[@]}" -j ACCEPT \
        && iptables -I DOCKER-USER -i "$1" -o br-+ "${c[@]}" -j RETURN \
        && iptables -I DOCKER-USER -i "$1" -o docker+ "${c[@]}" -j RETURN \
        || warn "Docker's firewall may block internet sharing (iptables DOCKER-USER)."
}

docker_rules_off() {
    command -v iptables >/dev/null 2>&1 || return 0
    local rule args
    iptables -S DOCKER-USER 2>/dev/null | grep -F -- "--comment $DOCKER_MARK" | sed 's/^-A /-D /' \
        | while IFS= read -r rule; do
            read -ra args <<< "$rule"
            iptables "${args[@]}" 2>/dev/null || true
        done || true      # grep finds none: not an error (set -e, pipefail)
}

# Forwarding from IFACE is not dropped: no FORWARD policy DROP, or our accept
forward_ok() {
    command -v iptables >/dev/null 2>&1 || return 0
    iptables -S FORWARD 2>/dev/null | grep -qx -- '-P FORWARD DROP' || return 0
    iptables -C DOCKER-USER -i "$1" -m comment --comment "$DOCKER_MARK" -j ACCEPT 2>/dev/null
}

# All of the hotspot's rules go
rules_off() {
    nft delete table inet "$NFT_TABLE" 2>/dev/null || true
    docker_rules_off
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
# not all pointed to the Pi (captive_dns: sharing on and a way out), the NAT
# is there and no firewall drops the forwarding (Docker, review A4); the page
# itself checks the way out again at every visit (rig mission 2026-10-16: it
# always said "no internet").
portal() {
    if [ "$1" = on ]; then
        local internet=no
        if [ ! -f "$CAPTIVE_CONF" ] && nat_ready "${3:-}" && forward_ok "${3:-}"; then
            internet=yes
        fi
        mkdir -p "$(dirname "$PORTAL_ENV")"
        # systemd's EnvironmentFile: the name in double quotes, with \ " ` $
        # escaped (a name may have any of them)
        printf 'RQ_HOTSPOT_SSID="%s"\nRQ_HOTSPOT_INTERNET=%s\nRQ_HOTSPOT_IFACE=%s\n' \
            "$(printf '%s' "$2" | sed 's/[\\"`$]/\\&/g')" "$internet" "${3:-}" > "$PORTAL_ENV"
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

    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ] && ! nat_ready "$iface"; then
        # trixie-feedback#62: NAT missing - once more brings it
        nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
        nmcli --wait 30 connection up "$PROFILE" >/dev/null 2>&1 || true
        nat_ready "$iface" || warn "Internet sharing is on, but NetworkManager set up no NAT for $iface."
    fi
    # after the NAT bounce: going down takes the rules away (91 hook)
    share_rules "$iface"
    advertise on
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
    rules_off
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
        if ! nat_ready "$iface"; then echo "Internet sharing: on, but no NAT set up"
        elif ! forward_ok "$iface"; then echo "Internet sharing: on, but the firewall drops it"
        else echo "Internet sharing: on"; fi
    else
        echo "Internet sharing: off"
    fi
    if [ "$(setting HOTSPOT_ALLOW_ADMIN no)" = yes ]; then
        echo "SSH and VNC from devices on the hotspot: allowed"
    else
        echo "SSH and VNC from devices on the hotspot: blocked"
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

# get KEY: the saved value ('' for the default)
cmd_get() {
    case " $SETTINGS " in *" ${1:-} "*) ;; *) die "Not a hotspot setting: ${1:-}" ;; esac
    if is_secret "$1"; then secret_get "$1"; else printf '%s' "${!1:-}"; fi
    echo
}

# set KEY...: one value per line on stdin (not in the arguments, where every
# user could read a password); all are checked before any is saved
cmd_set() {
    local key value values=() i=0
    [ "$#" -gt 0 ] || die "Usage: $(basename "$0") set KEY... (values on stdin, one per line)"
    for key in "$@"; do
        case " $SETTINGS " in *" $key "*) ;; *) die "Not a hotspot setting: $key" ;; esac
        IFS= read -r value || [ -n "$value" ] || value=""
        value=${value%$'\r'}
        valid_setting "$key" "$value" || die "$(setting_rule "$key")"
        values+=("$value")
    done
    for key in "$@"; do
        save_setting "$key" "${values[$i]}" || die "Could not save $key (is the SD card full?)."
        i=$((i + 1))
    done
}

# Sourced (tests): the functions only
[[ "${BASH_SOURCE[0]}" == "$0" ]] || return 0

rq_help_guard "$@"
ensure_root "$@"
# before the environment is loaded: a name or password there may not load
migrate_secrets >&2 || { [ "${1:-}" != migrate ] || exit 1; }
[ "${1:-}" != migrate ] || exit 0
load_rqb2_env

case "${1:-}" in
    on)      cmd_on ;;
    off)     cmd_off ;;
    status)  cmd_status ;;
    qr)      cmd_qr ;;
    card)    cmd_card ;;
    boot)    cmd_boot ;;
    get)     cmd_get "${2:-}" ;;
    set)     shift; cmd_set "$@" ;;
    *)       echo "Usage: $(basename "$0") on|off|status|qr|card|boot|get KEY|set KEY...|migrate" >&2; exit 2 ;;
esac
