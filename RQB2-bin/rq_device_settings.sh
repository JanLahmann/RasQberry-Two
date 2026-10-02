#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Device settings that survive A/B image updates
# ============================================================================
# Description: Each A/B slot has its own root filesystem, so a freshly flashed
#   slot starts with the shipped rasqberry_environment.env: the LED layout
#   chosen in the first-login wizard is gone after every image update (#290).
#   This keeps a copy of the device's LED settings on the /data partition,
#   which both slots mount, and puts them back into a slot that lacks them.
#
#   Saved: LED_* and RASQ_LED_* keys (layout, verification, pin, brightness,
#   outputs) - but not *_INSTALLED flags, since installed software is per
#   slot, nor the retired LED_MATRIX_* keys - plus the user's custom layouts
#   (~/.local/config/led-layouts.json).
#
#   Restore runs at boot (rasqberry-load-boot-config.sh) and only applies the
#   saved copy when this slot has never applied it, or when it was saved
#   later than the last apply (i.e. changed on the other slot). A change made
#   on this slot is therefore never reverted by an older copy.
#
#   Without a separate /data mount (the standard image) there is nothing to
#   share between slots and both commands do nothing.
#
# Usage: rq_device_settings.sh save|restore|show   (as root)
#
# Environment overrides (tests): RQ_ENV_FILE, RQ_SETTINGS_DIR, RQ_SETTINGS_MARKER,
#   RQ_SETTINGS_USER_HOME, RQ_SETTINGS_SKIP_MOUNT_CHECK=1

ENV_FILE="${RQ_ENV_FILE:-/usr/config/rasqberry_environment.env}"
DATA_MOUNT="/data"
STORE_DIR="${RQ_SETTINGS_DIR:-$DATA_MOUNT/rasqberry}"
STORE_ENV="$STORE_DIR/device-settings.env"
STORE_LAYOUTS="$STORE_DIR/led-layouts.json"
# On the slot's own root, so a freshly flashed slot has none
MARKER="${RQ_SETTINGS_MARKER:-/var/lib/rasqberry/device-settings.applied}"

KEY_RE='^(LED_|RASQ_LED_)[A-Za-z0-9_]*='
# Not device settings: *_INSTALLED flags (per slot), and the retired
# LED_MATRIX_* keys (Q22: LED_LAYOUT is the one layout setting) - an older
# store must not put them back into a new slot.
SKIP_RE='^([A-Za-z0-9_]*_INSTALLED|LED_MATRIX_[A-Za-z0-9_]*)='

log() {
    if command -v logger >/dev/null 2>&1; then
        logger -t rasqberry-device-settings "$*" 2>/dev/null || true
    fi
    echo "rq_device_settings: $*" >&2
}

# Home of the desktop user (uid 1000); this runs as root at boot
user_home() {
    if [ -n "${RQ_SETTINGS_USER_HOME:-}" ]; then
        echo "$RQ_SETTINGS_USER_HOME"
    else
        getent passwd 1000 2>/dev/null | cut -d: -f6
    fi
}

shared_store_available() {
    [ "${RQ_SETTINGS_SKIP_MOUNT_CHECK:-0}" = "1" ] && return 0
    command -v mountpoint >/dev/null 2>&1 && mountpoint -q "$DATA_MOUNT"
}

do_save() {
    shared_store_available || return 0
    [ -f "$ENV_FILE" ] || { log "no $ENV_FILE - nothing to save"; return 0; }

    mkdir -p "$STORE_DIR"
    local tmp="$STORE_ENV.tmp.$$"
    {
        echo "# RasQberry device settings, shared by both A/B slots."
        echo "# Written by rq_device_settings.sh save; restored into a fresh slot at boot."
        grep -E "$KEY_RE" "$ENV_FILE" | grep -vE "$SKIP_RE" || true
    } > "$tmp"
    mv -f "$tmp" "$STORE_ENV"

    local home
    home=$(user_home)
    if [ -n "$home" ] && [ -f "$home/.local/config/led-layouts.json" ]; then
        cp -f "$home/.local/config/led-layouts.json" "$STORE_LAYOUTS"
    fi

    # This slot already has these values: mark them applied, after the store
    # was written, so the next boot does not "restore" our own save.
    mkdir -p "$(dirname "$MARKER")"
    touch "$MARKER"
    log "saved $(grep -cE "$KEY_RE" "$STORE_ENV" || true) setting(s) to $STORE_DIR"
}

do_restore() {
    shared_store_available || return 0
    [ -f "$STORE_ENV" ] || return 0
    [ -f "$ENV_FILE" ] || { log "no $ENV_FILE - cannot restore"; return 0; }
    if [ -e "$MARKER" ] && ! [ "$STORE_ENV" -nt "$MARKER" ]; then
        return 0
    fi

    local tmp="$ENV_FILE.tmp.$$" line key changed=0
    cp -p "$ENV_FILE" "$tmp"
    while IFS= read -r line; do
        [[ "$line" =~ $KEY_RE ]] || continue
        [[ "$line" =~ $SKIP_RE ]] && continue
        key="${line%%=*}"
        if grep -qxF -- "$line" "$tmp"; then
            continue
        elif grep -q "^${key}=" "$tmp"; then
            # Replace the (last) assignment in place, keeping the file layout
            awk -v k="$key" -v l="$line" 'BEGIN{n=0} $0 ~ "^"k"=" {last=NR} {a[NR]=$0}
                END{for(i=1;i<=NR;i++) print (i==last ? l : a[i])}' "$tmp" > "$tmp.new"
            mv -f "$tmp.new" "$tmp"
        else
            echo "$line" >> "$tmp"
        fi
        changed=$((changed + 1))
    done < "$STORE_ENV"
    chmod 644 "$tmp"
    mv -f "$tmp" "$ENV_FILE"

    local home dest
    home=$(user_home)
    dest="$home/.local/config/led-layouts.json"
    if [ -n "$home" ] && [ -d "$home" ] && [ -f "$STORE_LAYOUTS" ] && ! [ -f "$dest" ]; then
        mkdir -p "$(dirname "$dest")"
        cp -f "$STORE_LAYOUTS" "$dest"
        if [ "$(id -u)" = "0" ]; then
            chown "$(stat -c %u:%g "$home" 2>/dev/null || echo 1000:1000)" \
                "$home/.local" "$home/.local/config" "$dest" 2>/dev/null || true
        fi
        log "restored custom LED layouts to $dest"
    fi

    mkdir -p "$(dirname "$MARKER")"
    touch "$MARKER"
    log "restored $changed setting(s) from $STORE_DIR"
}

case "${1:-}" in
    save)    do_save ;;
    restore) do_restore ;;
    show)    [ -f "$STORE_ENV" ] && cat "$STORE_ENV" || echo "(no saved device settings)" ;;
    *)       echo "Usage: $(basename "$0") save|restore|show" >&2; exit 2 ;;
esac
