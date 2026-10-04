#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: system information for support and bug reports (#233)
# ============================================================================
# Description: Prints what this image is and where it was built from
#   (/etc/rasqberry-build.json, written by the image build), plus what can
#   only be known at runtime: image type, booted A/B slot, Pi model - and
#   how to reach this Pi and how it is doing (R-016, R-112): name, address,
#   power, temperature, memory and free space.
# Usage: rq_info.sh            human-readable
#        rq_info.sh --json     build metadata plus runtime fields as JSON
#        rq_info.sh --report   save this, disk space, demos and recent logs to
#                              ~/rasqberry-report-<date>.txt for a bug report

BUILD_JSON="${RQ_BUILD_JSON:-/etc/rasqberry-build.json}"

field() { [ -f "$BUILD_JSON" ] && jq -r --arg k "$1" '.[$k] // "" | if type == "array" then join(", ") else . end' "$BUILD_JSON" 2>/dev/null || true; }

# A/B: the running slot comes from the root partition, and what each slot
# holds from rq_slot_manager.sh (R-118; /boot/config/current-slot is only
# written on confirm and lags behind a switch)
image_type="standard"
slot=""
slot_a=""
slot_b=""
manager="$(dirname "$0")/rq_slot_manager.sh"
[ -x "$manager" ] || manager=/usr/bin/rq_slot_manager.sh
summary=""
[ -x "$manager" ] && summary=$("$manager" summary 2>/dev/null || true)
sval() { printf '%s\n' "$summary" | sed -n "s/^$1=//p" | head -1; }
if [ "$(sval layout)" = "ab" ] || lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE '^config$'; then
    image_type="A/B"
    slot=$(sval current)
    [ -n "$slot" ] || slot=$(cat /boot/config/current-slot 2>/dev/null || true)
    slot_a=$(sval slot_a)
    slot_b=$(sval slot_b)
fi
describe() {
    case "$1" in
        EMPTY)      echo "empty (no system)" ;;
        INCOMPLETE) echo "unfinished (an update was interrupted)" ;;
        UNKNOWN|"") echo "unknown (run with sudo to look)" ;;
        SYSTEM)     echo "a system without version information" ;;
        beta-*)     echo "$1 (beta)" ;;
        development-*|dev-*) echo "$1 (dev)" ;;
        v[0-9]*|[0-9]*|stable-*) echo "$1 (stable)" ;;
        *)          echo "$1" ;;
    esac
}
# The Pi model and its RAM (item 2). The model comes from the device tree
# (/proc/cpuinfo "Model" without one); the RAM from the board's revision code
# (bits 20-22: 0 = 256 MB ... 5 = 8 GB, 6 = 16 GB), which says what the board
# has rather than what the kernel can use (MemTotal is a little less).
model=""
[ -r /proc/device-tree/model ] && model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || true)
[ -n "$model" ] || model=$(sed -n 's/^Model[[:space:]]*: *//p' /proc/cpuinfo 2>/dev/null | head -1 || true)
[ -n "$model" ] || model=$(uname -m)
board_ram() {
    local rev mem
    rev=$(sed -n 's/^Revision[[:space:]]*: *//p' /proc/cpuinfo 2>/dev/null | head -1 || true)
    case "$rev" in ''|*[!0-9a-fA-F]*) ;; *)
        if (( 16#$rev & 0x800000 )); then
            mem=$(( (16#$rev >> 20) & 7 ))
            case "$mem" in
                0) echo "256 MB" ;; 1) echo "512 MB" ;; *) echo "$(( 1 << (mem - 2) )) GB" ;;
            esac
            return 0
        fi ;;
    esac
    # No revision code: round MemTotal up to the next power of two
    awk '/^MemTotal:/ { g = $2 / 1048576; n = 1; while (n < g) n *= 2; if (g > 0) printf "%d GB\n", n }' /proc/meminfo 2>/dev/null || true
}
ram=$(board_ram)
hardware="$model${ram:+, $ram RAM}"

# ---------------------------------------------------------------------------
# Reaching this Pi, and how it is doing
# ---------------------------------------------------------------------------
here="$(dirname "$0")"
remote="$here/rq_remote_access.sh"
[ -x "$remote" ] || remote=/usr/bin/rq_remote_access.sh
host_name=$(hostname 2>/dev/null || echo unknown)
mdns=""
addrs=""
if [ -x "$remote" ]; then
    mdns=$("$remote" mdns 2>/dev/null || true)
    addrs=$("$remote" address 2>/dev/null | awk '{ printf "%s%s (%s)", sep, $2, $1; sep = ", " }' || true)
fi
[ -n "$mdns" ] || mdns="$host_name.local"

# vcgencmd get_throttled: bit 0 under-voltage now, bit 16 since start-up,
# bit 3 / 19 the temperature limit now / since start-up
throttled=""
command -v vcgencmd >/dev/null 2>&1 \
    && throttled=$(vcgencmd get_throttled 2>/dev/null | sed -n 's/^throttled=//p' || true)
power_text() {
    local t="$1" v
    case "$t" in 0x[0-9a-fA-F]*) v=$((t)) ;; *) echo "unknown"; return 0 ;; esac
    if (( v & 0x1 )); then
        echo "UNDER-VOLTAGE now - use the official power supply"
    elif (( v & 0x10000 )); then
        echo "under-voltage since start-up - use the official power supply"
    else
        echo "OK"
    fi
}
# Pi 5: the supply says how much it can give (5000 mA = the 27 W supply)
supply_note=""
if [ -r /proc/device-tree/chosen/power/max_current ]; then
    ma=$(od -An -tx1 /proc/device-tree/chosen/power/max_current 2>/dev/null | tr -d ' \n' || true)
    if [ -n "$ma" ] && [ $((16#$ma)) -gt 0 ] && [ $((16#$ma)) -lt 5000 ]; then
        supply_note=" (supply gives $((16#$ma)) mA; the 27 W supply gives 5000)"
    fi
fi
temp_c=""
if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
    temp_c=$(( $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0) / 1000 ))
fi
temp_note=""
case "$throttled" in
    0x[0-9a-fA-F]*) (( throttled & 0x80008 )) && temp_note=" - too hot, slowed down" ;;
esac
mem_used=""; mem_total=""
if [ -r /proc/meminfo ]; then
    mem_total=$(awk '/^MemTotal:/ { print $2 }' /proc/meminfo)
    mem_used=$(awk '/^MemTotal:/ { t = $2 } /^MemAvailable:/ { a = $2 } END { print t - a }' /proc/meminfo)
fi
# RAM in binary GB, as RAM is sold; disk space in decimal GB, as SD cards are
# sold and as the A/B texts say it (item 24: 26.7 GB / 24.3 GB / 24.8G mixed
# both before)
gb() { awk -v k="$1" 'BEGIN { printf "%.1f GB", k / 1048576 }'; }
gb_disk() { awk -v k="$1" 'BEGIN { printf "%.1f GB", k * 1024 / 1e9 }'; }
disk=$(df -Pk / 2>/dev/null | awk 'NR == 2 { print $4, $2 }' || true)
version=$(field version)
[ -n "$version" ] || version=$(cat /etc/rasqberry-version 2>/dev/null || echo unknown)

# A file to attach to a bug report: what this prints, plus disk, memory,
# demos and the recent logs (R-121). No IBM Quantum key or other secrets.
if [ "${1:-}" = "--report" ]; then
    out="${HOME:-/tmp}/rasqberry-report-$(date +%Y%m%d-%H%M%S).txt"
    self="$0"
    section() { printf '\n===== %s =====\n' "$1"; }
    # Read a root-only log without a password prompt, or skip it
    readable() { if [ -r "$1" ]; then tail -n "$2" "$1"; else sudo -n tail -n "$2" "$1" 2>/dev/null || echo "(not readable: $1)"; fi; }
    {
        echo "RasQberry Two report, $(date '+%Y-%m-%d %H:%M:%S')"
        section "System";        "$self" 2>&1 || true
        section "Build (json)";  "$self" --json 2>&1 || true
        section "Disk";          df -h / /boot/firmware /data 2>/dev/null || df -h /
        section "Memory";        free -m 2>/dev/null || true
        section "Docker"
        if command -v docker >/dev/null 2>&1; then
            docker system df 2>&1 || true
            docker image ls 2>&1 || true
            docker ps -a 2>&1 || true
        else
            echo "(no docker)"
        fi
        section "Demos"
        ls -la "$HOME/RasQberry-Two/demos" 2>&1 || true
        section "Settings (secrets removed)"
        grep -vE '^[[:space:]]*#|^[[:space:]]*$' /usr/config/rasqberry_environment.env 2>/dev/null \
            | grep -viE 'token|key|secret|password|passwd' || true
        for f in "$HOME"/.cache/rasqberry/*.log /tmp/rqb-demo.log /var/log/rasqberry-*.log; do
            [ -e "$f" ] || continue
            section "Log: $f (last lines)"
            readable "$f" 80
        done
        section "Journal: warnings since boot (last 100)"
        journalctl -b -p warning -n 100 --no-pager 2>/dev/null \
            || sudo -n journalctl -b -p warning -n 100 --no-pager 2>/dev/null || echo "(not available)"
    } > "$out" 2>&1
    echo "Saved: $out"
    echo "Attach it to a bug report (https://github.com/JanLahmann/RasQberry-Two/issues)."
    echo "It holds no IBM Quantum key, but it shows this Pi's name, addresses and logs."
    exit 0
fi

if [ "${1:-}" = "--json" ]; then
    base='{}'
    [ -f "$BUILD_JSON" ] && base=$(cat "$BUILD_JSON")
    echo "$base" | jq --arg t "$image_type" --arg s "$slot" --arg m "$model" --arg r "$ram" --arg k "$(uname -r)" \
        --arg a "$slot_a" --arg b "$slot_b" \
        --arg hn "$host_name" --arg md "$mdns" --arg ip "$addrs" --arg th "$throttled" \
        --arg pw "$(power_text "$throttled")" --arg tc "$temp_c" \
        --arg mu "$mem_used" --arg mt "$mem_total" --arg df "$disk" \
        '. + {image_type: $t, current_slot: $s, model: $m, ram: $r, running_kernel: $k,
              hostname: $hn, mdns_name: $md, addresses: $ip, throttled: $th, power: $pw,
              temperature_c: $tc, mem_used_kb: $mu, mem_total_kb: $mt,
              root_free_kb: ($df | split(" ")[0] // ""), root_size_kb: ($df | split(" ")[1] // "")}
         + (if $t == "A/B" then {slot_a: $a, slot_b: $b} else {} end)'
    exit 0
fi

# What the A/B card holds, in words (item 24: a small card runs ONE system,
# so "Slot B: empty" was misleading there). No slot is special (ping-pong
# updates): each line says what the slot holds, which one runs and which one
# a normal start boots (the start slot).
card_mode=$(sval card_mode)
default_slot=$(sval default)
slot_line() {   # <A|B> <content>
    local note=""
    [ "$1" = "$slot" ] && note="running"
    [ "$1" = "$default_slot" ] && note="${note:+$note, }start slot"
    printf '%s%s' "$(describe "$2")" "${note:+ - $note}"
}
built=$(field build_timestamp | sed 's/T/ /; s/:[0-9][0-9]Z$/ UTC/; s/Z$/ UTC/')
repo=$(field git_repo)
from="$(field git_branch) @ $(field git_commit | cut -c1-12)"
[ -n "$repo" ] && [ "$repo" != "JanLahmann/RasQberry-Two" ] && from="$repo $from"
os_name=$(field os)
codename=$(printf '%s' "$os_name" | sed -n 's/.*(\(.*\)).*/\1/p')
deb=$(field debian_version)
[ -n "$deb" ] && os_name="Debian $deb${codename:+ ($codename)}"

echo "Name:              $host_name (network: $mdns)"
echo "Address:           ${addrs:-none - not connected}"
echo "Hardware:          $hardware"
echo "Power:             $(power_text "$throttled")$supply_note"
[ -n "$temp_c" ] && echo "Temperature:       ${temp_c} °C$temp_note"
[ -n "$mem_total" ] && echo "Memory:            $(gb "$mem_used") of $(gb "$mem_total") in use"
[ -n "$disk" ] && echo "Free space:        $(gb_disk "${disk% *}") of $(gb_disk "${disk#* }")"
echo
echo "RasQberry version: $version"
if [ -f "$BUILD_JSON" ]; then
    echo "Built:             $built, $from"
    echo "OS / kernel:       $os_name / $(uname -r)"
    echo "Python / Qiskit:   $(field python_version) / $(field qiskit_version)"
else
    echo "OS kernel:         $(uname -r) (no $BUILD_JSON: an image from before build metadata)"
fi
if [ "$image_type" != "A/B" ]; then
    echo "Image type:        standard (one system on this card)"
else
    case "$card_mode" in
        single|single-pending)
            echo "Image type:        A/B image, one system on this card (card under 64 GB)" ;;
        dual-pending)
            echo "Image type:        A/B, second system not set up yet${slot:+ (running Slot $slot)}"
            echo "Slot A:            $(slot_line A "$slot_a")" ;;
        *)
            echo "Image type:        A/B, two systems${slot:+ (running Slot $slot)}"
            echo "Slot A:            $(slot_line A "$slot_a")"
            echo "Slot B:            $(slot_line B "$slot_b")" ;;
    esac
fi

# A failed update, in the words of the slot manager and the taskbar (#242)
if [ "$image_type" = "A/B" ] && [ -x "$(dirname "$manager")/rq_slot_status.sh" ]; then
    failed_update=$("$(dirname "$manager")/rq_slot_status.sh" failure-notice 2>/dev/null || true)
    [ -n "$failed_update" ] && echo "Last update:       $failed_update"
fi
exit 0
