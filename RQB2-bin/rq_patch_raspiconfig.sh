#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Patch raspi-config to add RasQberry menu
# ============================================================================
# Description: Apply RQB2 menu integration patch to raspi-config
# Usage: Called from the root @reboot cron job, and by apt right after it
#        installs a new raspi-config (RQB2-system/etc/apt/apt.conf.d/
#        99-rasqberry-raspi-config), so an update does not remove the
#        "0 RasQberry" entry until the next reboot.
#
# The patch makes four changes, and all of them must be there: the line that
# sources RQB2_menu.sh, the "0 RasQberry" menu item, its dispatch line, and
# "9 About raspi-config" sent to do_rasqberry_about (raspi-config's own text
# plus a note about the RasQberry extension). A raspi-config patched by an
# older version (without the About line) counts as partly patched and is
# patched again from the copy `patch -b` kept.
# The old check looked for the word "RasQberry" only, so a raspi-config the
# diff no longer fits (trixie fails hunk 1 of 3) ended up with the menu item but
# without the code behind it - and was reported as success (R-117). Now the
# patch is tried with --dry-run first, nothing is changed unless all of it
# applies, and the result is checked for all three markers.
#
# Exit codes:
#   0 = Success (patch applied or already applied)
#   1 = Error (patch does not fit; raspi-config left without the RasQberry entry)
#
# Environment (tests): RQ_RASPI_CONFIG, RQ_RASPI_CONFIG_DIFF override the paths.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

PATCH_FILE="${RQ_RASPI_CONFIG_DIFF:-/usr/config/raspi-config.diff}"
TARGET_FILE="${RQ_RASPI_CONFIG:-/usr/bin/raspi-config}"

# One marker per change in raspi-config.diff
MARKERS=(
    'RQB2_menu="/usr/config/RQB2_menu.sh"'
    '"0 RasQberry"'
    'do_rasqberry_menu'
    'do_rasqberry_about'
)

# How many of the markers the file has (0..4)
count_markers() {
    local file="$1" n=0 m
    for m in "${MARKERS[@]}"; do
        if grep -qF -- "$m" "$file" 2>/dev/null; then
            n=$((n + 1))
        fi
    done
    echo "$n"
}

[ -f "$TARGET_FILE" ] || die "Target file not found: $TARGET_FILE"

found=$(count_markers "$TARGET_FILE")
if [ "$found" -eq "${#MARKERS[@]}" ]; then
    debug "RasQberry menu already integrated into raspi-config"
    exit 0
fi

[ -f "$PATCH_FILE" ] || die "Patch file not found: $PATCH_FILE"

# Half-applied by an older version of this script: start again from the copy
# `patch -b` kept, if that one is clean.
if [ "$found" -gt 0 ]; then
    if [ -f "$TARGET_FILE.orig" ] && [ "$(count_markers "$TARGET_FILE.orig")" -eq 0 ]; then
        warn "raspi-config has an older or partial RasQberry patch - starting again from $TARGET_FILE.orig"
        cp -p "$TARGET_FILE.orig" "$TARGET_FILE"
    else
        die "raspi-config has only part of the RasQberry patch and no clean backup to start from; reinstall raspi-config (sudo apt install --reinstall raspi-config)"
    fi
fi

# Will all of it apply? (--forward: never reverse-apply)
if ! patch --dry-run --forward -s "$TARGET_FILE" "$PATCH_FILE" >/dev/null 2>&1; then
    die "This raspi-config does not fit the RasQberry patch ($PATCH_FILE); raspi-config left unchanged, so it has no RasQberry entry"
fi

# Apply patch (-b = backup, -r - = no reject files)
info "Applying RasQberry menu patch to raspi-config..."
if patch -b --forward -s -r - "$TARGET_FILE" "$PATCH_FILE" >/dev/null 2>&1 \
    && [ "$(count_markers "$TARGET_FILE")" -eq "${#MARKERS[@]}" ]; then
    info "✓ RasQberry menu integrated successfully"
    exit 0
fi

# Should not happen after a clean dry run; do not leave half a patch behind.
if [ -f "$TARGET_FILE.orig" ]; then
    cp -p "$TARGET_FILE.orig" "$TARGET_FILE"
fi
die "Failed to apply raspi-config patch"
