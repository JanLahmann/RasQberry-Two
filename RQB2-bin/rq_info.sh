#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: system information for support and bug reports (#233)
# ============================================================================
# Description: Prints what this image is and where it was built from
#   (/etc/rasqberry-build.json, written by the image build), plus what can
#   only be known at runtime: image type, booted A/B slot, Pi model.
# Usage: rq_info.sh            human-readable
#        rq_info.sh --json     build metadata plus runtime fields as JSON

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
model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || uname -m)
version=$(field version)
[ -n "$version" ] || version=$(cat /etc/rasqberry-version 2>/dev/null || echo unknown)

if [ "${1:-}" = "--json" ]; then
    base='{}'
    [ -f "$BUILD_JSON" ] && base=$(cat "$BUILD_JSON")
    echo "$base" | jq --arg t "$image_type" --arg s "$slot" --arg m "$model" --arg k "$(uname -r)" \
        --arg a "$slot_a" --arg b "$slot_b" \
        '. + {image_type: $t, current_slot: $s, model: $m, running_kernel: $k}
         + (if $t == "A/B" then {slot_a: $a, slot_b: $b} else {} end)'
    exit 0
fi

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
