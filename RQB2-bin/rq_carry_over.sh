#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: what survives an A/B update (R-053)
# ============================================================================
# Description: Each A/B slot has its own root filesystem, so a slot written by
#   an update starts with the image's defaults: Wi-Fi gone, password back to
#   the published default, hostname, language and IBM account reset, files
#   apparently lost. Two mechanisms keep what makes the Pi yours:
#
#   LIVE ON /data - the DATA partition both slots mount; one copy, used by
#   whichever system runs (set up at every boot, "link"):
#     ~/Shared                                -> /data/home/<user>/Shared   (symlink)
#     ~/.qiskit  (IBM Quantum account)        -> /data/home/<user>/.qiskit  (symlink)
#     ~/My-Quantum-Programs (own programs)    -> /data/home/<user>/My-Quantum-Programs
#                                                 (symlink; Jan, Q33c)
#     /etc/NetworkManager/system-connections  <- /data/rasqberry/system-connections
#                                                 (bind mount, before NetworkManager)
#     LED/device settings: /data/rasqberry/device-settings.env (rq_device_settings.sh)
#
#   COPIED ONCE from the other slot, on the first boot of a freshly written
#   slot ("pull"; the image carries /var/lib/rasqberry/carry-over-pending,
#   written by convert-to-ab-boot-v3.sh, and this removes it):
#     the desktop user's password (the hash in /etc/shadow - never plain text),
#     hostname (/etc/hostname, /etc/hosts), time zone, locale, keyboard layout,
#     BROWSER_AUTOSTART, RQ_FIRSTLOGIN_DONE, RQ_UMAMI (usage counts off,
#     on rig and development Pis) and the Demo Loop's choice of demos and
#     timings (DEMO_LOOP_*) from rasqberry_environment.env,
#     VNC switched off (Q17: the new system then does not switch it on),
#     and - from a slot that predates /data - its ~/.qiskit, ~/My-Quantum-Programs
#     and Wi-Fi profiles.
#   (SSH host keys and authorized_keys are copied at update time by
#   rq_carry_ssh_identity.sh.)
#
#   Pulling at first boot, not pushing at update time, means the NEW image
#   decides what to take: the first update from an older release carries
#   over everything above although the old updater knows nothing about it.
#
#   Without a real DATA partition (standard image, or an A/B card still on
#   the 28 MB placeholder) "link" does nothing and everything stays per slot.
#
# Usage: rq_carry_over.sh boot | link | pull <other-root> | list   (as root)
#   boot  rasqberry-carry-over.service: pull (fresh slot only), then link
#
# Environment overrides (tests): RQ_CARRY_ROOT (slot root, default /),
#   RQ_CARRY_DATA (default /data), RQ_CARRY_CONFIG_DIR (default /boot/config),
#   RQ_CARRY_USER, RQ_CARRY_HOME, RQ_CARRY_SKIP_MOUNT_CHECK=1,
#   RQ_CARRY_NO_BIND=1, RQ_CARRY_NO_LIVE=1 (no hostname/locale-gen/nmcli)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

ROOT="${RQ_CARRY_ROOT:-}"
ROOT="${ROOT%/}"
DATA="${RQ_CARRY_DATA:-/data}"
CONFIG_DIR="${RQ_CARRY_CONFIG_DIR:-$ROOT/boot/config}"
PENDING="$ROOT/var/lib/rasqberry/carry-over-pending"
DONE_FILE="$ROOT/var/lib/rasqberry/carry-over.done"
NM_MIGRATED="$ROOT/var/lib/rasqberry/nm-connections-on-data"
NM_DIR="/etc/NetworkManager/system-connections"
DATA_NM="$DATA/rasqberry/system-connections"
DATA_MIN_BYTES=268435456   # 256 MiB: smaller is the image's placeholder
PROGRAMS=My-Quantum-Programs
# rq_learner_setup.sh made ~/My-Quantum-Programs for this user (once)
LEARNER_STAMP=.local/state/rasqberry/learner-setup/programs
# The starter files rq_learner_setup.sh copies into ~/My-Quantum-Programs
STARTERS="$ROOT/usr/config/my-quantum-programs"
ENV_KEYS="BROWSER_AUTOSTART RQ_FIRSTLOGIN_DONE RQ_UMAMI DEMO_LOOP_DEMOS
    DEMO_LOOP_IBM_LOGO_TIME DEMO_LOOP_LIGHTS_OUT_TIME DEMO_LOOP_RASQBERRY_TIE_TIME
    DEMO_LOOP_RASQ_LED_TIME DEMO_LOOP_PAUSE"
# Live = changing the running system (hostname, locale-gen, nmcli), not a test root
LIVE=true
if [ -n "$ROOT" ] || [ "${RQ_CARRY_NO_LIVE:-0}" = "1" ]; then LIVE=false; fi

say() { echo "carry-over: $*"; }

desktop_user() {
    if [ -n "${RQ_CARRY_USER:-}" ]; then echo "$RQ_CARRY_USER"; return; fi
    getent passwd 1000 2>/dev/null | cut -d: -f1
}
desktop_home() {
    if [ -n "${RQ_CARRY_HOME:-}" ]; then echo "$RQ_CARRY_HOME"; return; fi
    getent passwd 1000 2>/dev/null | cut -d: -f6
}

am_root() { [ "$(id -u)" = "0" ]; }

# chown to the owner of the home directory (only possible as root).
# give_to_user [-R] <path>: -R only right after copying files in - not at
# every boot over a Shared folder that may hold thousands of files.
give_to_user() {
    am_root || return 0
    local rec="" owner
    if [ "${1:-}" = "-R" ]; then rec="-R"; shift; fi
    owner=$(stat -c %u:%g "$ROOT$(desktop_home)" 2>/dev/null || echo 1000:1000)
    chown $rec "$owner" "$@" 2>/dev/null || true
}

is_ab() { [ -f "$CONFIG_DIR/autoboot.txt" ]; }

data_is_real() {
    [ "${RQ_CARRY_SKIP_MOUNT_CHECK:-0}" = "1" ] && return 0
    mountpoint -q "$DATA" 2>/dev/null || return 1
    local size
    size=$(df -B1 --output=size "$DATA" 2>/dev/null | tail -1 | tr -d ' ')
    [ "${size:-0}" -ge "$DATA_MIN_BYTES" ]
}

# Copy the entries of directory $1 into $2 without overwriting anything there:
# what is already on /data wins (it is the shared, newer copy). Returns non-zero
# on a real copy error - callers check it before deleting the source.
# (Explicit checks throughout: "boot" calls this under "|| warn", where bash
# ignores set -e.)
merge_dir() {
    local src="$1" dst="$2"
    [ -d "$src" ] || return 0
    mkdir -p "$dst" || return 1
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --ignore-existing "$src/" "$dst/"
    else
        cp -an "$src/." "$dst/"
    fi
}

dir_has_entries() { [ -d "$1" ] && [ -n "$(ls -A "$1" 2>/dev/null)" ]; }

# Like merge_dir, for ~/My-Quantum-Programs (<src> <dst> <starter dir>). Every
# image ships this folder with the starter files (rq_learner_setup.sh at build
# time). The first time, everything moves to /data. Once /data holds the
# learner's folder, a slot's copy brings only what the learner made or changed:
# a starter file identical to the shipped one is skipped, so a starter the
# learner deleted or renamed does not come back with every update. Nothing on
# /data is overwritten. Reads <src> only (it may be a read-only slot).
merge_programs() {
    local src="$1" dst="$2" starters="$3" rel rc=0
    [ -d "$src" ] || return 0
    dir_has_entries "$dst" || { merge_dir "$src" "$dst"; return; }
    while IFS= read -r -d '' rel; do
        rel="${rel#./}"
        [ -e "$dst/$rel" ] || [ -L "$dst/$rel" ] && continue
        if [ -f "$starters/$rel" ] && cmp -s "$src/$rel" "$starters/$rel"; then
            continue
        fi
        mkdir -p "$dst/$(dirname "$rel")" && cp -pP "$src/$rel" "$dst/$rel" || rc=1
    done < <(cd "$src" && find . \( -type f -o -type l \) -print0)
    return "$rc"
}

# ----------------------------------------------------------------------------
# link: user data lives on /data
# ----------------------------------------------------------------------------

link_home_dir() {
    # <name in home> <dir on /data> [mode]
    local name="$1" target="$2" mode="${3:-755}"
    local home path moved=false
    home=$(desktop_home)
    path="$ROOT$home/$name"
    if [ -L "$path" ]; then
        return 0                       # already a link (ours, or the user's own)
    fi
    if [ ! -d "$target" ]; then
        mkdir -p "$target"
        chmod "$mode" "$target"
    fi
    if [ -d "$path" ]; then
        if [ "$name" = "Shared" ] && dir_has_entries "$path"; then
            # The image never ships ~/Shared: this is the user's own folder
            say "~/$name is a normal folder with files - left alone (the shared folder is $target)"
            return 0
        fi
        local merged=0
        if [ "$name" = "$PROGRAMS" ]; then
            merge_programs "$path" "$target" "$STARTERS" || merged=$?
        else
            merge_dir "$path" "$target" || merged=$?
        fi
        if [ "$merged" -ne 0 ]; then
            warn "could not copy ~/$name to $target - left as it is"
            return 1
        fi
        rm -rf "$path"
        moved=true
        say "moved ~/$name to $target"
    fi
    chmod "$mode" "$target"          # after the copy: rsync -a takes the source's mode
    if $moved; then give_to_user -R "$target"; else give_to_user "$target"; fi
    ln -s "$target" "$path" || { warn "could not link ~/$name"; return 1; }
    am_root && chown -h "$(stat -c %u:%g "$ROOT$home" 2>/dev/null || echo 1000:1000)" "$path" 2>/dev/null || true
    say "~/$name -> $target"
}

link_nm_connections() {
    local local_dir="$ROOT$NM_DIR"
    [ -d "$local_dir" ] || return 0
    if mountpoint -q "$local_dir" 2>/dev/null; then
        return 0                       # already bound
    fi
    mkdir -p "$DATA_NM"
    # Once per slot: bring this slot's own profiles (made before /data held
    # them, or by Imager's first-run script) onto /data. Only once, so a
    # profile deleted later on /data is not brought back from the slot.
    if [ ! -e "$NM_MIGRATED" ]; then
        if dir_has_entries "$local_dir"; then
            merge_dir "$local_dir" "$DATA_NM" || { warn "could not copy the network profiles to $DATA_NM"; return 1; }
            say "Wi-Fi/network profiles of this system copied to $DATA_NM"
        fi
        mkdir -p "$(dirname "$NM_MIGRATED")"
        date -Iseconds > "$NM_MIGRATED"
    fi
    chmod 700 "$DATA_NM"             # Wi-Fi passwords: root only
    find "$DATA_NM" -type f -exec chmod 600 {} + 2>/dev/null || true
    if [ "${RQ_CARRY_NO_BIND:-0}" = "1" ]; then
        say "bind $DATA_NM -> $local_dir (skipped: RQ_CARRY_NO_BIND)"
        return 0
    fi
    mount --bind "$DATA_NM" "$local_dir" || { warn "could not bind $DATA_NM"; return 1; }
    say "network profiles: $local_dir is $DATA_NM"
    if $LIVE && systemctl is-active --quiet NetworkManager 2>/dev/null; then
        nmcli connection reload 2>/dev/null || true
    fi
}

cmd_link() {
    is_ab || { say "not an A/B card - nothing to link"; return 0; }
    data_is_real || { say "$DATA is not a prepared data partition - user data stays on this system"; return 0; }
    local user home
    user=$(desktop_user); home=$(desktop_home)
    if [ -n "$user" ] && [ -n "$home" ] && [ -d "$ROOT$home" ]; then
        mkdir -p "$DATA/home/$user"
        give_to_user "$DATA/home/$user"
        link_home_dir Shared "$DATA/home/$user/Shared" 755 || true
        link_home_dir .qiskit "$DATA/home/$user/.qiskit" 700 || true
        # Own programs (B10's starter folder, Jan Q33c): when the folder exists
        # in this slot or on /data, and on the first start before the learner
        # setup made it - that runs at the desktop login, seconds after this,
        # and its folder stayed a normal one until the next restart (item 27);
        # it now fills the linked folder. A learner who deleted the folder
        # (the setup's stamp is there) does not get an empty one back.
        if [ -e "$ROOT$home/$PROGRAMS" ] || [ -L "$ROOT$home/$PROGRAMS" ] \
            || [ -d "$DATA/home/$user/$PROGRAMS" ] \
            || [ ! -e "$ROOT$home/$LEARNER_STAMP" ]; then
            link_home_dir "$PROGRAMS" "$DATA/home/$user/$PROGRAMS" 755 || true
        fi
    fi
    link_nm_connections || true
    return 0
}

# ----------------------------------------------------------------------------
# pull: a freshly written slot takes over the other slot's identity
# ----------------------------------------------------------------------------

copy_if_different() {
    # <other root> <path> -> 0 if copied
    local other="$1" path="$2"
    [ -f "$other$path" ] || return 1
    if [ -f "$ROOT$path" ] && cmp -s "$other$path" "$ROOT$path"; then
        return 1
    fi
    mkdir -p "$(dirname "$ROOT$path")"
    cp -p "$other$path" "$ROOT$path"
}

pull_password() {
    local other="$1" user hash lastchg cur tmp
    user=$(desktop_user)
    [ -n "$user" ] && [ -f "$other/etc/shadow" ] && [ -f "$ROOT/etc/shadow" ] || return 1
    hash=$(awk -F: -v u="$user" '$1 == u { print $2; exit }' "$other/etc/shadow")
    lastchg=$(awk -F: -v u="$user" '$1 == u { print $3; exit }' "$other/etc/shadow")
    cur=$(awk -F: -v u="$user" '$1 == u { print $2; exit }' "$ROOT/etc/shadow")
    [ -n "$hash" ] || return 1
    grep -q "^${user}:" "$ROOT/etc/shadow" || return 1
    [ "$hash" != "$cur" ] || return 1
    tmp="$ROOT/etc/shadow.rq-carry.$$"
    cp -p "$ROOT/etc/shadow" "$tmp"
    RQ_H="$hash" RQ_C="$lastchg" awk -F: -v OFS=: -v u="$user" \
        '$1 == u { $2 = ENVIRON["RQ_H"]; if (ENVIRON["RQ_C"] != "") $3 = ENVIRON["RQ_C"] } { print }' \
        "$ROOT/etc/shadow" > "$tmp"
    mv -f "$tmp" "$ROOT/etc/shadow"
}

pull_timezone() {
    local other="$1" changed=1 link
    copy_if_different "$other" /etc/timezone && changed=0
    if [ -L "$other/etc/localtime" ]; then
        link=$(readlink "$other/etc/localtime")
        if [ "$(readlink "$ROOT/etc/localtime" 2>/dev/null)" != "$link" ] && [ -e "$ROOT$link" ]; then
            ln -sfn "$link" "$ROOT/etc/localtime"
            changed=0
        fi
    fi
    return "$changed"
}

pull_locale() {
    local other="$1" changed=1 lang norm
    copy_if_different "$other" /etc/default/locale && changed=0
    copy_if_different "$other" /etc/locale.gen && changed=0
    if [ "$changed" = 0 ] && $LIVE; then
        lang=$(sed -n 's/^LANG=//p' "$ROOT/etc/default/locale" | tr -d '"' | head -1)
        norm=$(echo "$lang" | sed -e 's/UTF-8/utf8/' -e 's/utf-8/utf8/')
        if [ -n "$lang" ] && ! locale -a 2>/dev/null | grep -qix "$norm"; then
            say "generating locale $lang (once)..."
            locale-gen >/dev/null 2>&1 || warn "locale-gen failed"
        fi
    fi
    return "$changed"
}

pull_env_keys() {
    local other="$1" env="/usr/config/rasqberry_environment.env" key line changed=1
    [ -f "$other$env" ] && [ -f "$ROOT$env" ] || return 1
    for key in $ENV_KEYS; do
        line=$(grep -E "^${key}=" "$other$env" | tail -1 || true)
        [ -n "$line" ] || continue
        grep -qxF -- "$line" "$ROOT$env" && continue
        if grep -q "^${key}=" "$ROOT$env"; then
            RQ_L="$line" awk -v k="$key" 'index($0, k "=") == 1 { print ENVIRON["RQ_L"]; next } { print }' \
                "$ROOT$env" > "$ROOT$env.rq-carry.$$" && cat "$ROOT$env.rq-carry.$$" > "$ROOT$env"
            rm -f "$ROOT$env.rq-carry.$$"
        else
            echo "$line" >> "$ROOT$env"
        fi
        changed=0
    done
    return "$changed"
}

pull_vnc_off() {
    # VNC is switched on once, at the first desktop login, unless this marker
    # exists (rasqberry-enable-vnc.sh, Q17). The old system had VNC off after
    # that first time: the user switched it off, so the new one keeps it off.
    # VNC on there (or no marker - a release that always switched it on):
    # nothing to do, the new system switches it on once.
    local other="$1" marker=/var/lib/rasqberry/vnc-auto-enabled
    [ -e "$other$marker" ] && [ ! -e "$ROOT$marker" ] || return 1
    compgen -G "$other/etc/systemd/system/*.wants/wayvnc.service" >/dev/null && return 1
    mkdir -p "$(dirname "$ROOT$marker")"
    cp -p "$other$marker" "$ROOT$marker"
}

pull_old_slot_data() {
    # From a slot that predates /data: its ~/.qiskit, ~/My-Quantum-Programs
    # and Wi-Fi profiles
    local other="$1" user home carried=""
    data_is_real || return 1
    user=$(desktop_user); home=$(desktop_home)
    if [ -n "$user" ] && [ -d "$other$home/.qiskit" ] && [ ! -L "$other$home/.qiskit" ] \
        && merge_dir "$other$home/.qiskit" "$DATA/home/$user/.qiskit"; then
        chmod 700 "$DATA/home/$user/.qiskit"
        give_to_user "$DATA/home/$user"
        give_to_user -R "$DATA/home/$user/.qiskit"
        carried="IBM Quantum account (~/.qiskit)"
    fi
    if [ -n "$user" ] && [ -d "$other$home/$PROGRAMS" ] && [ ! -L "$other$home/$PROGRAMS" ] \
        && dir_has_entries "$other$home/$PROGRAMS" \
        && merge_programs "$other$home/$PROGRAMS" "$DATA/home/$user/$PROGRAMS" \
            "$other/usr/config/my-quantum-programs"; then
        chmod 755 "$DATA/home/$user/$PROGRAMS"
        give_to_user "$DATA/home/$user"
        give_to_user -R "$DATA/home/$user/$PROGRAMS"
        carried="${carried:+$carried, }own programs (~/$PROGRAMS)"
    fi
    if [ ! -e "$other/var/lib/rasqberry/nm-connections-on-data" ] && dir_has_entries "$other$NM_DIR" \
        && merge_dir "$other$NM_DIR" "$DATA_NM"; then
        chmod 700 "$DATA_NM"
        find "$DATA_NM" -type f -exec chmod 600 {} + 2>/dev/null || true
        carried="${carried:+$carried, }Wi-Fi/network profiles"
    fi
    [ -n "$carried" ] || return 1
    echo "$carried"
}

cmd_pull() {
    local other="${1:-}"
    [ -n "$other" ] && [ -d "$other/etc" ] || { echo "Usage: $(basename "$0") pull <other-root>" >&2; return 2; }
    local carried=() what
    if copy_if_different "$other" /etc/hostname; then
        copy_if_different "$other" /etc/hosts || true
        carried+=("hostname ($(tr -d '[:space:]' < "$ROOT/etc/hostname"))")
        $LIVE && hostname "$(tr -d '[:space:]' < /etc/hostname)" 2>/dev/null || true
    fi
    pull_password "$other" && carried+=("password")
    pull_timezone "$other" && carried+=("time zone")
    pull_locale "$other" && carried+=("locale")
    copy_if_different "$other" /etc/default/keyboard && carried+=("keyboard layout")
    pull_env_keys "$other" && carried+=("browser/checklist/Demo Loop choices")
    pull_vnc_off "$other" && carried+=("VNC off")
    if what=$(pull_old_slot_data "$other"); then
        carried+=("$what")
    fi
    local summary="" item
    for item in "${carried[@]+"${carried[@]}"}"; do
        summary="${summary:+$summary, }$item"
    done
    say "copied from the other system: ${summary:-nothing (already the same)}"
    mkdir -p "$(dirname "$DONE_FILE")"
    {
        echo "time=$(date -Iseconds)"
        echo "from=$(cat "$other/etc/rasqberry-version" 2>/dev/null || echo unknown)"
        echo "carried=${summary}"
    } > "$DONE_FILE"
}

# ----------------------------------------------------------------------------
# boot
# ----------------------------------------------------------------------------

other_slot_device() {
    local root
    root=$(findmnt -n -o SOURCE / 2>/dev/null || true)
    case "$root" in
        *5) get_ab_system_partition B ;;
        *6) get_ab_system_partition A ;;
        *)  return 1 ;;
    esac
}

cmd_boot() {
    is_ab || return 0
    if [ -e "$PENDING" ]; then
        local dev mnt=/run/rasqberry/other-slot
        if dev=$(other_slot_device) && [ -b "$dev" ]; then
            mkdir -p "$mnt"
            if mount -o ro,noload "$dev" "$mnt" 2>/dev/null; then
                if [ -f "$mnt/etc/rasqberry-version" ]; then
                    say "first start of this system: taking over settings from $(cat "$mnt/etc/rasqberry-version") ($dev)"
                    cmd_pull "$mnt" || warn "carry-over from $dev incomplete"
                else
                    say "first start of this system: the other slot holds no system - nothing to take over"
                fi
                umount "$mnt" || umount -l "$mnt" || true
            fi
        fi
        rm -f "$PENDING"
    fi
    cmd_link || warn "could not set up the shared user data on $DATA"
    return 0
}

cmd_list() {
    cat <<'EOF'
Kept across an update, on the data partition (both systems use one copy):
  - the Shared folder in your home (~/Shared)
  - your own programs (~/My-Quantum-Programs)
  - your IBM Quantum account (~/.qiskit)
  - Wi-Fi networks
  - LED panel settings
Copied from the old system when the new one starts for the first time:
  - your password, the hostname, time zone, language and keyboard layout
  - SSH host keys and authorized_keys
  - "Browser at login" and the setup checklist's "Don't ask again"
  - VNC switched off
Not kept (they stay in the old system):
  - other files in your home folder - put files you want to keep in ~/Shared
    or ~/My-Quantum-Programs
  - installed demos, Docker images and Python packages you added
EOF
}

case "${1:-}" in
    boot) cmd_boot ;;
    link) cmd_link ;;
    pull) shift; cmd_pull "$@" ;;
    list) cmd_list ;;
    *)    echo "Usage: $(basename "$0") boot|link|pull <other-root>|list" >&2; exit 2 ;;
esac
