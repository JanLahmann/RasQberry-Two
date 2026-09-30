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

image_type="standard"
slot=""
if lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE '^config$'; then
    image_type="A/B"
    slot=$(cat /boot/config/current-slot 2>/dev/null || true)
fi
model=$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || uname -m)
version=$(field version)
[ -n "$version" ] || version=$(cat /etc/rasqberry-version 2>/dev/null || echo unknown)

if [ "${1:-}" = "--json" ]; then
    base='{}'
    [ -f "$BUILD_JSON" ] && base=$(cat "$BUILD_JSON")
    echo "$base" | jq --arg t "$image_type" --arg s "$slot" --arg m "$model" --arg k "$(uname -r)" \
        '. + {image_type: $t, current_slot: $s, model: $m, running_kernel: $k}'
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
echo "Hardware:          $model"
echo "Running kernel:    $(uname -r)"
