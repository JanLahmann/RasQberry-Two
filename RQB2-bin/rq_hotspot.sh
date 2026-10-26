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
#     HOTSPOT_INTERFACE       auto: a radio that can be an access point, an
#                             idle one first, a USB adapter before the onboard
#                             Wi-Fi (which then is the hotspot only: one radio
#                             cannot be hotspot and client reliably)
#     HOTSPOT_SHARE_INTERNET  yes: devices on the hotspot reach the internet
#                             through the Pi's other connection; no: the Pi only
#     HOTSPOT_AT_BOOT         yes: the hotspot starts with the Pi
#     HOTSPOT_ALLOW_ADMIN     auto (default): devices on the hotspot can use
#                             SSH and VNC on the Pi only once no account that
#                             can use sudo (group sudo, the desktop user, root)
#                             has the published default password any more -
#                             the hotspot's password is on a public card;
#                             no: never; yes: always
#   A file rasqberry-hotspot.txt on the boot partition (put there after
#   flashing, from any computer; on an A/B card the CONFIG partition) sets
#   these before the first start; "boot" saves it and keeps no password on
#   the card. What it did not take is listed in rasqberry-hotspot.applied.txt.
#
# Usage: rq_hotspot.sh on|off|status|qr|card|boot   (as root)
#   card: the join card (QR codes, name, password) in the browser, to show or print
#   get KEY: a saved setting (empty: the default)
#   set KEY...: save settings, one value per line on stdin, all or none
#     (checked first; the reason goes to stderr) - the menu uses this
#   migrate: move a name or password from the environment file into their own file
#   sync: its firewall rules, Entangible's address, the landing page and its
#     DNS follow whether the hotspot runs (NetworkManager hook 91-rasqberry-hotspot)
#   iface: the Wi-Fi device the hotspot uses (or would use)
#   admin: may devices on the hotspot use SSH and VNC? on|off, then the reason

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

PROFILE="rasqberry-hotspot"
ADDRESS="10.42.0.1"
NFT_TABLE="rasqberry_hotspot"
BOOT_FILE="${RQ_HOTSPOT_BOOT_FILE:-/boot/firmware/rasqberry-hotspot.txt}"
# A/B card: a computer shows the CONFIG partition first, and Imager writes
# there - the file is read from there too (review A14)
CONFIG_BOOT_FILE="${RQ_HOTSPOT_CONFIG_FILE:-/boot/config/rasqberry-hotspot.txt}"
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
# on, off, boot and sync one at a time (the NetworkManager hook starts sync
# for every change, also for those "on" itself brings)
LOCK="${RQ_HOTSPOT_LOCK:-/run/rasqberry/hotspot.lock}"
# HOTSPOT_ALLOW_ADMIN=auto: the accounts, and their password hashes (tests)
PASSWD_FILE="${RQ_PASSWD_FILE:-/etc/passwd}"
GROUP_FILE="${RQ_GROUP_FILE:-/etc/group}"
SHADOW_FILE="${RQ_SHADOW_FILE:-/etc/shadow}"
# The password every card starts with; it is on the website (R-013)
DEMO_PASSWORD='Qiskit1!'

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
        HOTSPOT_SHARE_INTERNET|HOTSPOT_AT_BOOT) [ "$value" = yes ] || [ "$value" = no ] ;;
        HOTSPOT_ALLOW_ADMIN) [ "$value" = auto ] || [ "$value" = yes ] || [ "$value" = no ] ;;
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
        HOTSPOT_ALLOW_ADMIN) echo "HOTSPOT_ALLOW_ADMIN is auto, yes or no." ;;
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

# Can DEV be an access point? (iw phy: "Supported interface modes: * AP";
# unknown counts as yes)
ap_capable() {
    local phy info
    phy=$(cat "/sys/class/net/$1/phy80211/name" 2>/dev/null) || return 0
    info=$(/usr/sbin/iw phy "$phy" info 2>/dev/null) || return 0
    grep -q 'Supported interface modes' <<< "$info" || return 0
    awk '/Supported interface modes:/ { m = 1; next }
         m && /^[[:space:]]+\* / { if ($2 == "AP") found = 1; next }
         m { m = 0 }
         END { exit !found }' <<< "$info"
}

# The Wi-Fi device for the hotspot: HOTSPOT_INTERFACE, or (auto) one that
# can be an access point - an idle one first, a USB adapter before the
# onboard Wi-Fi (brcmfmac). A radio that is this Pi's Wi-Fi connection only
# when there is no other: "auto" took a USB adapter that was the Pi's way
# out while the onboard radio sat idle (review A13).
hotspot_interface() {
    local wanted dev type state conn driver usb_idle="" onb_idle="" usb_busy="" onb_busy=""
    wanted=$(setting HOTSPOT_INTERFACE auto)
    if [ "$wanted" != auto ]; then echo "$wanted"; return 0; fi
    while IFS=: read -r dev type state conn; do
        [ "$type" = wifi ] && [ -n "$dev" ] || continue
        ap_capable "$dev" || continue
        driver=$(basename "$(readlink -f "/sys/class/net/$dev/device/driver" 2>/dev/null)" 2>/dev/null || true)
        if [ "$state" = connected ] && [ "$conn" != "$PROFILE" ]; then
            if [ "$driver" = brcmfmac ]; then onb_busy=${onb_busy:-$dev}; else usb_busy=${usb_busy:-$dev}; fi
        else
            if [ "$driver" = brcmfmac ]; then onb_idle=${onb_idle:-$dev}; else usb_idle=${usb_idle:-$dev}; fi
        fi
    done < <(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device 2>/dev/null || true)
    dev=${usb_idle:-${onb_idle:-${onb_busy:-$usb_busy}}}
    # no device: empty, and success - under set -e the callers' message
    # ("No Wi-Fi device found") never came, the script just ended (review A8)
    [ -z "$dev" ] || echo "$dev"
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
# password (as rasqberry-hotspot.applied.txt), so it is applied once. What
# was not taken is listed at its end: a rejected password used to leave only
# a journal line, and a headless booth with a password nobody knew (A11).
PW_REJECTED=""
apply_boot_file() {
    local file any=""
    for file in "$BOOT_FILE" "$CONFIG_BOOT_FILE"; do
        [ -f "$file" ] || continue
        apply_one_boot_file "$file"
        any=1
    done
    [ -z "$any" ] || load_rqb2_env
}

apply_one_boot_file() {
    local file="$1" line key value applied="${1%.txt}.applied.txt" n=0 notes=""
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%$'\r'}
        case "$line" in ""|\#*) continue ;; esac
        key=${line%%=*}; value=${line#*=}
        key=$(printf '%s' "$key" | tr -d '[:space:]')
        value=$(unquote "$value")
        case " $SETTINGS " in
            *" $key "*) ;;
            *) warn "rasqberry-hotspot.txt: unknown setting $key"
               notes="$notes# Not taken: $key is not a hotspot setting.\n"
               continue ;;
        esac
        if valid_setting "$key" "$value"; then
            save_setting "$key" "$value" && n=$((n + 1))
        else
            warn "rasqberry-hotspot.txt: $key has a value that is not allowed; left as it was. $(setting_rule "$key")"
            notes="$notes# Not taken: $key. $(setting_rule "$key")\n"
            [ "$key" != HOTSPOT_PASSWORD ] || PW_REJECTED=1
        fi
    done < "$file"
    {
        sed -E 's/^([[:space:]]*HOTSPOT_PASSWORD[[:space:]]*=).*/# HOTSPOT_PASSWORD was saved on the Pi/' "$file"
        if [ -n "$notes" ]; then
            printf '\n'
            printf '%b' "$notes"
            [ -z "$PW_REJECTED" ] || echo "# The hotspot has another password: the LED panel scrolls it at the start, the RasQberry menu shows it (Wi-Fi Hotspot)."
        fi
    } > "$applied"
    rm -f "$file"
    info "Hotspot: $n setting(s) taken from $file."
}

# ---------------------------------------------------------------------------
# SSH and VNC from devices on the hotspot (HOTSPOT_ALLOW_ADMIN)
# ---------------------------------------------------------------------------

# admin_accounts: the accounts that can run anything as root - members of
# the group sudo (also by their primary group), the desktop user (uid 1000),
# root - one per line; fails when the account files cannot be read
admin_accounts() {
    local gid
    [ -r "$PASSWD_FILE" ] && [ -r "$GROUP_FILE" ] || return 1
    gid=$(awk -F: '$1 == "sudo" { print $3; exit }' "$GROUP_FILE")
    {
        echo root
        awk -F: '$3 == 1000 { print $1; exit }' "$PASSWD_FILE"
        awk -F: '$1 == "sudo" { print $4; exit }' "$GROUP_FILE" | tr ',' '\n'
        [ -z "$gid" ] || awk -F: -v g="$gid" '$4 == g { print $1 }' "$PASSWD_FILE"
    } | awk 'NF && !seen[$0]++'
}

# Reads a password and a hash on stdin - never in a command line, where ps
# shows them - and compares through the system's crypt(3), which knows
# yescrypt ($y$) and sha512 ($6$). Exit 0: the hash is of that password;
# 1: it is not; 2: crypt does not know the hash's method (no result, a
# failure token such as "*0", or one that does not start with the hash's
# own settings - macOS answers anything with DES).
CRYPT_CHECK='my $pw = <STDIN>; my $h = <STDIN>;
exit 2 unless defined $pw && defined $h;
chomp $pw; chomp $h;
my $s = ($h =~ /^(.*\$)/) ? $1 : substr($h, 0, 2);
my $c = crypt($pw, $h);
exit 2 unless defined $c && length($c) > length($s) && index($c, $s) == 0;
exit($c eq $h ? 0 : 1);'

# admin_password_changed: 0 only when no account that can use sudo
# (admin_accounts) takes the published default password any more. A locked
# or empty hash (!, !!, *, '') does not take it. What cannot be told - no
# perl, no /etc/shadow, a hash crypt does not know - counts as the default
# password (the safe side). Says why not on stdout; never shows a password
# or a hash.
admin_password_changed() {
    local accounts user hash rc still="" unknown=""
    if ! accounts=$(admin_accounts); then
        echo "the accounts cannot be read"; return 1
    fi
    [ -r "$SHADOW_FILE" ] || { echo "the passwords cannot be read"; return 1; }
    command -v perl >/dev/null 2>&1 || { echo "the passwords cannot be checked (no perl)"; return 1; }
    while IFS= read -r user; do
        hash=$(awk -F: -v u="$user" '$1 == u { print $2; exit }' "$SHADOW_FILE") \
            || { echo "the passwords cannot be read"; return 1; }
        case "$hash" in ''|'!'*|'*'*) continue ;; esac
        rc=0
        printf '%s\n%s\n' "$DEMO_PASSWORD" "$hash" | perl -e "$CRYPT_CHECK" 2>/dev/null || rc=$?
        case "$rc" in
            1) ;;
            0) still="${still:+$still, }$user" ;;
            *) unknown="${unknown:+$unknown, }$user" ;;
        esac
    done <<< "$accounts"
    hash=""
    if [ -n "$still" ]; then
        echo "the default password is still set for $still"
    elif [ -n "$unknown" ]; then
        echo "the password of $unknown cannot be checked"
    else
        return 0
    fi
    return 1
}

# admin_effect: may devices on the hotspot use SSH and VNC? Two lines: on or
# off, then why. auto checks the passwords now: at every on, boot and sync,
# and the menu's password change runs sync.
admin_effect() {
    local why
    case "$(setting HOTSPOT_ALLOW_ADMIN auto)" in
        yes) printf 'on\nset to yes\n' ;;
        no)  printf 'off\nset to no\n' ;;
        *)   if why=$(admin_password_changed); then
                 printf 'on\nauto: the default password has been changed\n'
             else
                 printf 'off\nauto: %s\n' "$why"
             fi ;;
    esac
}

admin_allowed() {
    local effect
    effect=$(admin_effect)
    [ "${effect%%$'\n'*}" = on ]
}

# ---------------------------------------------------------------------------
# Internet sharing
# ---------------------------------------------------------------------------

# share_rules IFACE: the hotspot's firewall, table inet rasqberry_hotspot
# (gone with the hotspot: cmd_off, the NetworkManager hook, a reboot)
#  - SSH (22) and VNC (5900) from devices on the hotspot are dropped unless
#    admin_allowed: its password is on a public card, and the Pi may still
#    have the demo password with passwordless sudo (review A2). auto (the
#    default) lets them through once that password is changed (Jan,
#    2026-10-17).
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
        if ! admin_allowed; then
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
# before the hotspot starts - NetworkManager's dnsmasq reads it then; when
# the way out changes later (a cable in or out), sync restarts the hotspot
# (review A7).
captive_wanted() {
    local uplink
    uplink=$(ip -4 route show default 2>/dev/null | awk -v i="$1" '$0 !~ ("dev " i " ") { print; exit }')
    [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = no ] || [ -z "$uplink" ]
}

captive_dns() {
    if ! captive_wanted "$1"; then
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
        local text
        text=$(printf 'RQ_HOTSPOT_SSID="%s"\nRQ_HOTSPOT_INTERNET=%s\nRQ_HOTSPOT_IFACE=%s' \
            "$(printf '%s' "$2" | sed 's/[\\"`$]/\\&/g')" "$internet" "${3:-}")
        # unchanged and running (sync): no restart under a phone loading it
        if [ "$text" = "$(cat "$PORTAL_ENV" 2>/dev/null)" ] \
            && systemctl is-active --quiet rasqberry-hotspot-portal.service 2>/dev/null; then
            return 0
        fi
        printf '%s\n' "$text" > "$PORTAL_ENV"
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

# Both steps, side by side when they fit 80 columns (the Wi-Fi code is the
# taller one): with internet shared, phones show no captive page, so the
# demos page needs its own code (user test 2026-10-26)
show_join() {
    local ssid="$1" pw="$2" wifi url cols
    echo "Wi-Fi:    $ssid"
    echo "Password: $pw"
    if ! command -v qrencode >/dev/null 2>&1; then
        echo "1. Join the Wi-Fi"
        echo "2. Open the demos page: http://$ADDRESS"
        return 0
    fi
    wifi=$(qrencode -t ANSIUTF8 -m 2 "$(qr_text "$ssid" "$pw")" 2>/dev/null) || wifi=""
    url=$(qrencode -t ANSIUTF8 -m 2 "http://$ADDRESS/" 2>/dev/null) || url=""
    # columns of the Wi-Fi code: two ASCII characters per module
    cols=$(qrencode -t ASCII -m 2 "$(qr_text "$ssid" "$pw")" 2>/dev/null | awk 'NR == 1 { print int(length($0) / 2) }')
    if [ -n "$cols" ] && [ "$cols" -le 50 ] \
        && [ "$(printf '%s\n' "$url" | wc -l)" -le "$(printf '%s\n' "$wifi" | wc -l)" ]; then
        printf "%-$((cols + 3))s%s\n" "1. Join the Wi-Fi" "2. Open the demos page:"
        printf "%-$((cols + 3))s%s\n" "" "http://$ADDRESS"
        paste -d '\t' <(printf '%s\n' "$wifi") <(printf '%s\n' "$url") | sed 's/\t/   /'
    else
        echo "1. Join the Wi-Fi"
        printf '%s\n' "$wifi"
        echo "2. Open the demos page: http://$ADDRESS"
        printf '%s\n' "$url"
    fi
}

# The hotspot runs (also while it is still coming up)
hotspot_active() {
    nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx "$PROFILE"
}

# profile_value FIELD: from the hotspot's NetworkManager profile
profile_value() {
    nmcli -g "$1" connection show "$PROFILE" 2>/dev/null || true
}

# One command at a time (on, off, boot, sync): wait for the one running -
# on, off and boot then go ahead anyway; a sync that waited in vain is not
# needed (the next change brings another)
take_lock() {
    command -v flock >/dev/null 2>&1 || return 0
    mkdir -p "$(dirname "$LOCK")" 2>/dev/null || return 0
    exec 9>"$LOCK" || return 0
    flock -w 300 9 && return 0
    [ "$1" != sync ] || exit 0
    warn "Another hotspot command is still running; going ahead."
}

# sync: everything that goes with the hotspot follows whether it runs. Off
# (stopped from the desktop's network menu, failed, the Pi restarted): its
# rules, Entangible's address and the landing page with its DNS go - left
# behind, phones on the next network were sent to 10.42.0.1 and any other
# shared connection had its DNS taken (review C1). On (also when started
# outside this script): they are set; when the way out changed since the
# start, the hotspot starts again, so its DNS fits (review A7).
# What goes with the hotspot goes
companions_off() {
    rules_off
    advertise off
    portal off
}

cmd_sync() {
    local iface ssid
    if ! hotspot_active; then
        companions_off
        return 0
    fi
    iface=$(profile_value connection.interface-name)
    ssid=$(profile_value 802-11-wireless.ssid)
    [ -n "$iface" ] || return 0
    if captive_wanted "$iface"; then
        [ -f "$CAPTIVE_CONF" ] || { info "Hotspot: no way out any more - starting again with the landing page for every name."; cmd_on quiet; return 0; }
    else
        [ ! -f "$CAPTIVE_CONF" ] || { info "Hotspot: a way out to share - starting again with the internet."; cmd_on quiet; return 0; }
    fi
    share_rules "$iface"
    advertise on
    portal on "$ssid" "$iface"
}

cmd_on() {
    local quiet="${1:-}" iface ssid pw band channel label country client
    iface=$(hotspot_interface)
    [ -n "$iface" ] || die "No Wi-Fi device found for the hotspot."
    country=$(wifi_country)
    if [ -z "$country" ] || [ "$country" = 00 ]; then
        die "The Wi-Fi country is not set, so the Wi-Fi stays off. Set it first: sudo raspi-config > Localisation Options > WLAN Country."
    fi
    ssid=$(setting HOTSPOT_SSID "")
    if [ -z "$ssid" ]; then
        # kept, as the password is: the name came from whichever radio was
        # used, so a card printed with a USB adapter in did not fit later (A13)
        ssid=$(default_ssid "$iface")
        secret_set HOTSPOT_SSID "$ssid" || true
    fi
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
    if ! nmcli --wait 30 connection up "$PROFILE" >/dev/null 2>&1; then
        companions_off      # the captive DNS written above must not stay
        die "The hotspot did not start on $iface (band $band, channel $channel). See: journalctl -u NetworkManager -n 30"
    fi

    if [ "$(setting HOTSPOT_SHARE_INTERNET yes)" = yes ] && ! nat_ready "$iface"; then
        # trixie-feedback#62: NAT missing - once more brings it
        nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
        nmcli --wait 30 connection up "$PROFILE" >/dev/null 2>&1 || true
        nat_ready "$iface" || warn "Internet sharing is on, but NetworkManager set up no NAT for $iface."
    fi
    # after the NAT bounce
    share_rules "$iface"
    advertise on
    # after the NAT check: the page says whether there is internet
    portal on "$ssid" "$iface"
    [ -n "$quiet" ] || { info "Hotspot on ($iface, $label, channel $channel)."; show_join "$ssid" "$pw"; }
}

cmd_off() {
    if nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx "$PROFILE"; then
        nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
        # a second radio (USB adapter) ran it: the Pi's Wi-Fi never left
        if nmcli -t -f TYPE,STATE,CONNECTION device 2>/dev/null \
                | grep -v ":$PROFILE\$" | grep -q '^wifi:connected:'; then
            info "Hotspot off."
        else
            info "Hotspot off. The Wi-Fi joins its usual network again."
        fi
    else
        info "The hotspot is not running."
    fi
    companions_off
}

cmd_status() {
    local iface ssid clients admin
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
    admin=$(admin_effect)
    if [ "${admin%%$'\n'*}" = on ]; then
        echo "SSH and VNC from devices on the hotspot: allowed (${admin#*$'\n'})"
    else
        echo "SSH and VNC from devices on the hotspot: blocked (${admin#*$'\n'})"
    fi
    echo "At boot: $(setting HOTSPOT_AT_BOOT no)"
}

# join_details: "SSID<newline>PASSWORD" - of the running hotspot when it
# runs (the card always fits it), else of the settings
join_details() {
    local iface ssid pw
    if hotspot_active; then
        ssid=$(profile_value 802-11-wireless.ssid)
        pw=$(nmcli -s -g 802-11-wireless-security.psk connection show "$PROFILE" 2>/dev/null || true)
        if [ -n "$ssid" ] && [ -n "$pw" ]; then printf '%s\n%s\n' "$ssid" "$pw"; return 0; fi
    fi
    iface=$(hotspot_interface)
    printf '%s\n%s\n' "$(setting HOTSPOT_SSID "$(default_ssid "${iface:-wlan0}")")" "$(hotspot_password)"
}

cmd_qr() {
    local ssid pw
    { IFS= read -r ssid; IFS= read -r pw; } < <(join_details)
    show_join "$ssid" "$pw"
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
  <div class="step">1. Join the Wi-Fi</div>
  <div class="qr">$wifi_svg</div>
  <div class="field">Wi-Fi</div><div class="value">$(printf '%s' "$ssid" | html_escape)</div>
  <div class="field">Password</div><div class="value">$(printf '%s' "$pw" | html_escape)</div>
  <div class="step">2. Open the demos page</div>
  <div class="qr small">$url_svg</div>
  <div class="value">http://$ADDRESS</div>
</div>
<button class="print" onclick="window.print()">Print this card</button>
</body></html>
CARD
}

cmd_card() {
    local ssid pw dir out user group home
    { IFS= read -r ssid; IFS= read -r pw; } < <(join_details)
    user=$(get_user_name)
    group=$(id -gn "$user" 2>/dev/null || echo "$user")
    home="${USER_HOME:-/home/$user}"
    dir="$home/.cache/rasqberry"
    # the user's, both levels: a ~/.cache made here by root kept desktop
    # apps from writing their cache (review A15)
    [ -d "$home/.cache" ] || install -d -m 700 -o "$user" -g "$group" "$home/.cache" 2>/dev/null \
        || mkdir -p "$home/.cache"
    [ -d "$dir" ] || install -d -m 700 -o "$user" -g "$group" "$dir" 2>/dev/null || mkdir -p "$dir"
    out="$dir/hotspot-card.html"
    write_card "$ssid" "$pw" "$out"
    chown "$user:$group" "$out" 2>/dev/null || true
    chmod 600 "$out"
    info "Join card: $out"
    rq_open_browser "file://$out" >/dev/null 2>&1 || info "Open it in the browser to show or print it."
}

# A headless booth whose password nobody knows (made at this start, or the
# one in rasqberry-hotspot.txt was refused): the LED panel scrolls name and
# password for 10 minutes, and the journal has them once (review A11)
show_unseen_password() {
    local ssid pw
    { IFS= read -r ssid; IFS= read -r pw; } < <(join_details)
    info "Hotspot \"$ssid\" is on; its password is $pw (also in the RasQberry menu: Wi-Fi Hotspot)."
    rq_wifi_scroll rasqberry-hotspot-scroll 600 "Wi-Fi $ssid  ***  password $pw  ***  http://$ADDRESS" || true
}

# wait_for_wifi SECONDS: until NetworkManager has a Wi-Fi device it can use.
# At boot the unit could run before wlan0 was there, or while it was still
# "unavailable" (wpa_supplicant not ready): "device is not available", and
# no retry (review A6).
wait_for_wifi() {
    local waited=0 iface state
    while :; do
        iface=$(hotspot_interface)
        if [ -n "$iface" ]; then
            state=$(nmcli -t -f DEVICE,STATE device 2>/dev/null | awk -F: -v d="$iface" '$1 == d { print $2; exit }')
            case "$state" in ""|unavailable|unmanaged) ;; *) return 0 ;; esac
        fi
        [ "$waited" -lt "$1" ] || return 1
        sleep 2
        waited=$((waited + 2))
    done
}

cmd_boot() {
    local try
    apply_boot_file
    if [ "$(setting HOTSPOT_AT_BOOT no)" != yes ]; then
        # what an earlier hotspot left behind goes (review C1)
        cmd_sync
        return 0
    fi
    wait_for_wifi "${RQ_HOTSPOT_WIFI_WAIT:-60}" \
        || warn "Hotspot: no Wi-Fi device ready after ${RQ_HOTSPOT_WIFI_WAIT:-60} seconds; trying anyway."
    # nobody has seen the password yet: made now, or the card's was refused
    local unseen="$PW_REJECTED"
    [ -n "$(setting HOTSPOT_PASSWORD "")" ] || unseen=1
    for try in 1 2 3; do
        # a subshell: cmd_on ends with die when it fails
        if ( cmd_on quiet ); then
            [ -z "$unseen" ] || show_unseen_password
            return 0
        fi
        [ "$try" = 3 ] && break
        warn "Hotspot: did not start (try $try of 3); again in ${RQ_HOTSPOT_RETRY_WAIT:-10} seconds."
        sleep "${RQ_HOTSPOT_RETRY_WAIT:-10}"
    done
    # nothing half-made stays; the Wi-Fi goes back to its known networks,
    # and without a network the setup Wi-Fi opens (rq_setup_hotspot.sh)
    nmcli connection down "$PROFILE" >/dev/null 2>&1 || true
    cmd_sync
    die "The hotspot did not start at boot. Without a network, the setup Wi-Fi RasQberry-Setup-XXXX opens instead (password: rasqberry)."
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
    on|off|boot|sync) take_lock "$1" ;;
esac
case "${1:-}" in
    on)      cmd_on ;;
    off)     cmd_off ;;
    status)  cmd_status ;;
    qr)      cmd_qr ;;
    card)    cmd_card ;;
    boot)    cmd_boot ;;
    sync)    cmd_sync ;;
    iface)   hotspot_interface ;;
    admin)   admin_effect ;;
    get)     cmd_get "${2:-}" ;;
    set)     shift; cmd_set "$@" ;;
    *)       echo "Usage: $(basename "$0") on|off|status|qr|card|boot|sync|iface|admin|get KEY|set KEY...|migrate" >&2; exit 2 ;;
esac
