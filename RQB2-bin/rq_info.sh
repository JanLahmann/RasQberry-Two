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
        INCOMPLETE) echo "unfinished (an update or copy was interrupted)" ;;
        UNKNOWN|"") echo "unknown (run with sudo to look)" ;;
        SYSTEM)     echo "a system without version information" ;;
        *)          echo "$1" ;;
    esac
}
model=$( (tr -d '\0' < /proc/device-tree/model) 2>/dev/null || uname -m)

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
gb() { awk -v k="$1" 'BEGIN { printf "%.1f GB", k / 1048576 }'; }
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
    echo "$base" | jq --arg t "$image_type" --arg s "$slot" --arg m "$model" --arg k "$(uname -r)" \
        --arg a "$slot_a" --arg b "$slot_b" \
        --arg hn "$host_name" --arg md "$mdns" --arg ip "$addrs" --arg th "$throttled" \
        --arg pw "$(power_text "$throttled")" --arg tc "$temp_c" \
        --arg mu "$mem_used" --arg mt "$mem_total" --arg df "$disk" \
        '. + {image_type: $t, current_slot: $s, model: $m, running_kernel: $k,
              hostname: $hn, mdns_name: $md, addresses: $ip, throttled: $th, power: $pw,
              temperature_c: $tc, mem_used_kb: $mu, mem_total_kb: $mt,
              root_free_kb: ($df | split(" ")[0] // ""), root_size_kb: ($df | split(" ")[1] // "")}
         + (if $t == "A/B" then {slot_a: $a, slot_b: $b} else {} end)'
    exit 0
fi

echo "Name:              $host_name (network: $mdns)"
echo "Address:           ${addrs:-none - not connected}"
echo "Power:             $(power_text "$throttled")$supply_note"
[ -n "$temp_c" ] && echo "Temperature:       ${temp_c} °C$temp_note"
[ -n "$mem_total" ] && echo "Memory:            $(gb "$mem_used") of $(gb "$mem_total") in use"
[ -n "$disk" ] && echo "Free space:        $(gb "${disk% *}") of $(gb "${disk#* }")"
echo
echo "RasQberry version: $version"
if [ -f "$BUILD_JSON" ]; then
    echo "Built:             $(field build_timestamp)"
    echo "From:              $(field git_repo) @ $(field git_branch) ($(field git_commit | cut -c1-12))"
    echo "OS:                $(field os) (Debian $(field debian_version))"
    echo "Python / Qiskit:   $(field python_version) / $(field qiskit_version)"
else
    echo "(no $BUILD_JSON - image built before build metadata existed)"
fi
echo "Image type:        $image_type${slot:+ (booted from Slot $slot)}"
if [ "$image_type" = "A/B" ]; then
    echo "Slot A (stable):   $(describe "$slot_a")"
    echo "Slot B (testing):  $(describe "$slot_b")"
fi
echo "Hardware:          $model"
echo "Running kernel:    $(uname -r)"
