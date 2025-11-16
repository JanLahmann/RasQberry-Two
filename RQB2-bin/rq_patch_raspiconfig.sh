#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Patch raspi-config to add RasQberry menu
# ============================================================================
# Description: Apply RQB2 menu integration patch to raspi-config
# Usage: Called from boot-time cron job
#
# Exit codes:
#   0 = Success (patch applied or already applied)
#   1 = Error (patch failed)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

PATCH_FILE="/usr/config/raspi-config.diff"
TARGET_FILE="/usr/bin/raspi-config"
MARKER_STRING="RasQberry"

# Check if patch already applied
if grep -q "$MARKER_STRING" "$TARGET_FILE" 2>/dev/null; then
    debug "RasQberry menu already integrated into raspi-config"
    exit 0
fi

# Verify patch file exists
if [ ! -f "$PATCH_FILE" ]; then
    die "Patch file not found: $PATCH_FILE"
fi

# Verify target file exists
if [ ! -f "$TARGET_FILE" ]; then
    die "Target file not found: $TARGET_FILE"
fi

# Apply patch (--forward = skip if already applied, -b = backup, -r - = no reject files)
info "Applying RasQberry menu patch to raspi-config..."
if patch -b --forward -r - "$TARGET_FILE" "$PATCH_FILE" >/dev/null 2>&1; then
    info "✓ RasQberry menu integrated successfully"
    exit 0
else
    # Check if it was already applied (patch exits with 1 if already applied)
    if grep -q "$MARKER_STRING" "$TARGET_FILE" 2>/dev/null; then
        debug "Patch was already applied (detected by marker string)"
        exit 0
    else
        die "Failed to apply raspi-config patch"
    fi
fi
