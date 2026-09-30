#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Tryboot Retry
# ============================================================================
# Description: Re-issue a lost slot switch at boot time.
#
# The firmware tryboot flag is sometimes lost when the reboot is issued
# right after writing a slot image (observed on Pi 4 and Pi 5): the system
# then boots the default slot instead of the requested target. This oneshot
# runs early in boot; if a slot switch was requested (target-slot marker)
# but the wrong slot booted, it re-issues the tryboot reboot ONCE.
# The retry budget (switch-retries marker) prevents reboot loops; when it
# is exhausted the health check reports the failed switch instead.
#
# Runs via rasqberry-tryboot-retry.service (before the health check).

BOOT_COMMON_DIR="/boot/config"
TARGET_FILE="${BOOT_COMMON_DIR}/target-slot"
RETRY_FILE="${BOOT_COMMON_DIR}/switch-retries"
MAX_RETRIES=1

# No switch pending - nothing to do
[ -f "$TARGET_FILE" ] || exit 0

target=$(tr -d '[:space:]' < "$TARGET_FILE")
if [ "$target" != "A" ] && [ "$target" != "B" ]; then
    echo "Ignoring invalid target-slot marker: '$target'"
    exit 0
fi

# Determine the currently booted slot (v3 layout: p5=A, p6=B)
root_part=$(findmnt / -o source -n)
case "$root_part" in
    *5) current="A" ;;
    *6) current="B" ;;
    *)  echo "Cannot determine slot from root partition $root_part"; exit 0 ;;
esac

if [ "$current" = "$target" ]; then
    # Switch succeeded - health check will confirm and consume the marker
    rm -f "$RETRY_FILE"
    exit 0
fi

retries=$(cat "$RETRY_FILE" 2>/dev/null || echo 0)
case "$retries" in *[!0-9]*|"") retries=0 ;; esac

if [ "$retries" -ge "$MAX_RETRIES" ]; then
    echo "Tryboot retry budget exhausted (target Slot $target, booted Slot $current)."
    echo "Leaving target-slot marker for the health check to report."
    rm -f "$RETRY_FILE"
    exit 0
fi

echo $((retries + 1)) > "$RETRY_FILE"
sync
echo "Booted Slot $current but requested target is Slot $target."
echo "Re-issuing tryboot (attempt $((retries + 1))/${MAX_RETRIES})..."
reboot '0 tryboot'
