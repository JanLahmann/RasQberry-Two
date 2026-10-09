#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: your own scripts after an A/B update (after-update hook)
# ============================================================================
# Description: An A/B update writes a fresh system into the other slot,
#   without the packages and extras you installed yourself. Executable files
#   in /data/rasqberry/after-update.d/ (on the DATA partition both systems
#   share) run once on each system after it starts with a new release: as
#   root, in name order - so your extras come back by themselves.
#
#   When: rasqberry-after-update.service, at every start, after the health
#   check (rasqberry-health-check.service) and the network. Only when
#   - this is an A/B card with a real DATA partition (not the placeholder),
#   - this slot is confirmed (slot-confirmed, autoboot.txt starts it, no trial
#     start pending): a script can never cause, delay or prevent a rollback;
#     on a trial start it runs at the next start, once the slot is confirmed,
#   - this slot's marker (/var/lib/rasqberry/after-update.done, on the slot's
#     own root) is missing or names another release than
#     /etc/rasqberry-version. Going back to the other slot runs nothing: it
#     has its marker. A fresh card follows the same rule; its DATA partition
#     is new and holds no scripts yet.
#
#   Safety: the folder, /data/rasqberry and /data must be owned by root and
#   not writable by group or others - else nothing runs, a warning is logged
#   and the scripts stay due. A file runs only when it is a regular,
#   executable file (no symlink) owned by root and not writable by group or
#   others. Ignored, like run-parts: dotfiles, *~, *.dpkg-*.
#
#   Each script: a timeout of 30 minutes (TIMEOUT_MINUTES=<n> in
#   /data/rasqberry/after-update.conf), no input, DEBIAN_FRONTEND=noninteractive
#   and RQ_RELEASE (this release), RQ_PREVIOUS_RELEASE (if known),
#   RQ_DESKTOP_USER, RQ_DESKTOP_HOME (uid 1000), RQ_VENV (the demos' Python
#   environment). Output: /var/log/rasqberry/after-update.log, every line
#   with its time, and the journal. A failing or timed-out script is logged
#   and the next one runs; the marker is written at the end either way. A run
#   cut short (power off, a script that restarts the Pi) is tried once more,
#   not after that.
#
# Usage: rq_after_update.sh run [--force] | status        (as root)
#   run          what the service does: the scripts, if they are due
#   run --force  run them again now, whatever the marker says
#   status       the scripts, the marker and the last run's log
#
# Environment overrides (tests): RQ_AU_DATA (default /data), RQ_AU_CONFIG_DIR
#   (/boot/config), RQ_AU_STATE_DIR (/var/lib/rasqberry), RQ_AU_LOG,
#   RQ_AU_VERSION_FILE (/etc/rasqberry-version), RQ_AU_SLOT (A or B),
#   RQ_AU_SKIP_MOUNT_CHECK=1, RQ_AU_OWNER_UID (owner of folder and scripts,
#   0), RQ_AU_TIMEOUT (seconds), RQ_AU_CLOCK_WAIT (seconds, 120),
#   RQ_AU_LOCK, RQ_AU_DESKTOP_USER, RQ_AU_DESKTOP_HOME

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

DATA="${RQ_AU_DATA:-/data}"
CONFIG_DIR="${RQ_AU_CONFIG_DIR:-/boot/config}"
STATE_DIR="${RQ_AU_STATE_DIR:-/var/lib/rasqberry}"
MARKER="$STATE_DIR/after-update.done"
CARRY_DONE="$STATE_DIR/carry-over.done"
LOG="${RQ_AU_LOG:-/var/log/rasqberry/after-update.log}"
VERSION_FILE="${RQ_AU_VERSION_FILE:-/etc/rasqberry-version}"
HOOK_DIR="$DATA/rasqberry/after-update.d"
CONF="$DATA/rasqberry/after-update.conf"
OWNER_UID="${RQ_AU_OWNER_UID:-0}"
LOCK="${RQ_AU_LOCK:-/run/lock/rasqberry-after-update.lock}"
ENV_FILE=/usr/config/rasqberry_environment.env
SYNC_FLAG=/run/systemd/timesync/synchronized
DATA_MIN_BYTES=268435456    # 256 MiB: smaller is the image's placeholder
DEFAULT_TIMEOUT_MINUTES=30
MAX_ATTEMPTS=2              # a run cut short is tried once more

export LC_ALL=C             # name order = byte order

# A line with its time, to the journal (stdout) and the log
log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') $*"
    printf '%s\n' "$line"
    printf '%s\n' "$line" >> "$LOG" 2>/dev/null || true
}

# The value of key <1> in the key=value file <2>
kv() { sed -n "s/^$1=//p" "$2" 2>/dev/null | head -n 1; }

# "<uid> <octal mode>" of a path, without following a symlink
owner_mode() { stat -c '%u %a' "$1" 2>/dev/null || stat -f '%u %Lp' "$1" 2>/dev/null; }

# Owned by the expected owner (root) and not writable by group or others
safe_owner_mode() {
    local uid mode
    read -r uid mode <<< "$(owner_mode "$1")" || return 1
    [ -n "${uid:-}" ] && [ "$uid" = "$OWNER_UID" ] && [ $(( 8#${mode:-777} & 8#022 )) -eq 0 ]
}

is_ab() { [ -f "$CONFIG_DIR/autoboot.txt" ]; }

data_is_real() {
    [ "${RQ_AU_SKIP_MOUNT_CHECK:-0}" = "1" ] && return 0
    mountpoint -q "$DATA" 2>/dev/null || return 1
    local size
    size=$(df -B1 --output=size "$DATA" 2>/dev/null | tail -1 | tr -d ' ')
    [ "${size:-0}" -ge "$DATA_MIN_BYTES" ]
}

current_slot() {
    if [ -n "${RQ_AU_SLOT:-}" ]; then echo "$RQ_AU_SLOT"; return; fi
    case "$(findmnt -n -o SOURCE / 2>/dev/null || true)" in
        *5) echo A ;;
        *6) echo B ;;
    esac
}

# The boot partition autoboot.txt starts without the tryboot flag ([all])
default_boot_partition() {
    awk '/^\[/ { sec = $0; next }
         sec == "[all]" && /^boot_partition=/ { sub(/^boot_partition=/, ""); print; exit }' \
        "$CONFIG_DIR/autoboot.txt" 2>/dev/null | tr -d '[:space:]'
}

# Confirmed by the health check: slot-confirmed is there, no trial start of
# this slot is pending, and a normal start starts this slot
slot_confirmed() {
    local slot="$1" want=2
    [ "$slot" = B ] && want=3
    [ -f "$CONFIG_DIR/slot-confirmed" ] || return 1
    [ "$(head -n 1 "$CONFIG_DIR/target-slot" 2>/dev/null | tr -d '[:space:]')" = "$slot" ] && return 1
    [ "$(default_boot_partition)" = "$want" ]
}

this_release() { head -n 1 "$VERSION_FILE" 2>/dev/null | tr -d '[:space:]'; }

# The release this slot ran before: the marker's (the same slot, another
# release), else the release a freshly written slot was written over
# (carry-over.done from=)
previous_release() {
    local cur="$1" prev=""
    if [ -f "$MARKER" ]; then
        prev=$(kv release "$MARKER")
        [ "$prev" = "$cur" ] && prev=$(kv previous "$MARKER")
    elif [ -f "$CARRY_DONE" ]; then
        prev=$(kv from "$CARRY_DONE" | tr -d '[:space:]')
    fi
    [ "$prev" = unknown ] && prev=""
    echo "$prev"
}

timeout_seconds() {
    local m=""
    if [ -n "${RQ_AU_TIMEOUT:-}" ]; then echo "$RQ_AU_TIMEOUT"; return; fi
    [ -f "$CONF" ] && m=$(kv TIMEOUT_MINUTES "$CONF" | tr -d '[:space:]"')
    case "$m" in ''|*[!0-9]*|0) m=$DEFAULT_TIMEOUT_MINUTES ;; esac
    echo $(( m * 60 ))
}

desktop_user() { echo "${RQ_AU_DESKTOP_USER:-$( (getent passwd 1000 2>/dev/null || true) | cut -d: -f1)}"; }
desktop_home() { echo "${RQ_AU_DESKTOP_HOME:-$( (getent passwd 1000 2>/dev/null || true) | cut -d: -f6)}"; }

venv_path() {
    local home="$1" repo venv
    repo=$(kv REPO "$ENV_FILE" | tr -d '"'); venv=$(kv STD_VENV "$ENV_FILE" | tr -d '"')
    echo "$home/${repo:-RasQberry-Two}/venv/${venv:-RQB2}"
}

write_marker() {
    # <release> <previous> <state> <attempts> <result>
    mkdir -p "$STATE_DIR"
    {
        echo "release=$1"
        echo "previous=$2"
        echo "state=$3"
        echo "attempts=$4"
        echo "time=$(date -Iseconds 2>/dev/null || date)"
        echo "result=$5"
    } > "$MARKER.tmp.$$"
    mv -f "$MARKER.tmp.$$" "$MARKER"
}

# The folder and the folders it is in may only be changed by root
folder_safe() {
    local d
    for d in "$DATA" "$DATA/rasqberry" "$HOOK_DIR"; do
        if [ -L "$d" ]; then
            warn "$d is a symbolic link - no after-update script runs"
            return 1
        fi
        if ! safe_owner_mode "$d"; then
            warn "$d must belong to root and must not be writable by group or others" \
                 "(sudo chown root:root $d; sudo chmod go-w $d) - no after-update script runs"
            return 1
        fi
    done
}

# Prefix every line of the output of script <1> with the time
stamp() {
    local name="$1" line ts
    while IFS= read -r line || [ -n "$line" ]; do
        ts=$(date '+%Y-%m-%d %H:%M:%S')
        printf '%s [%s] %s\n' "$ts" "$name" "$line"
        printf '%s [%s] %s\n' "$ts" "$name" "$line" >> "$LOG" 2>/dev/null || true
    done
}

# Run script <1> with timeout <2> (seconds); its exit status
run_one() {
    local path="$1" secs="$2" name fifo reader rc i
    name=$(basename "$path")
    fifo="$(mktemp -d "${TMPDIR:-/tmp}/rq-after-update.XXXXXX")/out"
    mkfifo "$fifo"
    stamp "$name" < "$fifo" &
    reader=$!
    set +e
    if [ -n "$TIMEOUT_CMD" ]; then
        (cd / && exec "$TIMEOUT_CMD" --kill-after=30 "$secs" "$path") < /dev/null > "$fifo" 2>&1 9>&-
    else
        (cd / && exec "$path") < /dev/null > "$fifo" 2>&1 9>&-
    fi
    rc=$?
    set -e
    # A process the script left running may keep the output open: wait 5 s
    for i in $(seq 1 50); do
        kill -0 "$reader" 2>/dev/null || break
        sleep 0.1
    done
    kill "$reader" 2>/dev/null || true
    wait "$reader" 2>/dev/null || true
    rm -rf "$(dirname "$fifo")"
    return "$rc"
}

trim_log() {
    local size
    [ -f "$LOG" ] || return 0
    size=$(wc -c < "$LOG" | tr -d ' ')
    if [ "${size:-0}" -gt 1048576 ]; then
        tail -n 2000 "$LOG" > "$LOG.tmp.$$" && mv -f "$LOG.tmp.$$" "$LOG"
    fi
}

wait_for_clock() {
    # apt refuses package lists "not valid yet" while the clock is behind:
    # a freshly written slot starts at its build time until NTP answers
    local n="${RQ_AU_CLOCK_WAIT:-120}" i=0
    [ "$n" -gt 0 ] || return 0
    [ -e "$SYNC_FLAG" ] && return 0
    systemctl is-active --quiet systemd-timesyncd 2>/dev/null || return 0
    while [ "$i" -lt "$n" ]; do
        sleep 1
        [ -e "$SYNC_FLAG" ] && return 0
        i=$((i + 1))
    done
    log "the clock is not synchronised yet (NTP) - running anyway"
}

cmd_run() {
    local force=false
    [ "${1:-}" = "--force" ] && force=true
    # (tests set RQ_AU_OWNER_UID and run unprivileged)
    [ "$(id -u)" = 0 ] || [ -n "${RQ_AU_OWNER_UID:-}" ] || die "run as root: sudo $(basename "$0") run${1:+ $1}"

    is_ab || { info "not an A/B card - nothing to do"; return 0; }
    data_is_real || { info "$DATA is not a prepared data partition - nothing to do"; return 0; }
    local slot release
    slot=$(current_slot)
    case "$slot" in A|B) ;; *) info "cannot tell which slot is running - nothing to do"; return 0 ;; esac
    if ! slot_confirmed "$slot"; then
        info "Slot $slot is not confirmed yet (trial start) - the scripts run once it is"
        return 0
    fi
    release=$(this_release)
    [ -n "$release" ] || { warn "no release in $VERSION_FILE - nothing to do"; return 0; }

    if command -v flock >/dev/null 2>&1; then
        mkdir -p "$(dirname "$LOCK")" 2>/dev/null || true
        exec 9> "$LOCK"
        flock -n 9 || { info "the after-update scripts are already running"; return 0; }
    fi

    local attempts=0 previous
    previous=$(previous_release "$release")
    if [ -f "$MARKER" ] && [ "$(kv release "$MARKER")" = "$release" ]; then
        attempts=$(kv attempts "$MARKER"); attempts=${attempts//[!0-9]/}; attempts=${attempts:-0}
        if ! $force; then
            [ "$(kv state "$MARKER")" = started ] || { info "already done for $release (sudo $(basename "$0") run --force runs them again)"; return 0; }
            if [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
                mkdir -p "$(dirname "$LOG")"
                log "=== after-update run for $release: cut short $attempts times - not again (sudo $(basename "$0") run --force)"
                write_marker "$release" "$previous" done "$attempts" "cut short $attempts times, given up"
                return 0
            fi
        fi
    else
        attempts=0
    fi
    $force && attempts=0

    mkdir -p "$(dirname "$LOG")"
    chmod 755 "$(dirname "$LOG")" 2>/dev/null || true
    ( umask 027; touch "$LOG" ) 2>/dev/null || true
    trim_log

    if [ ! -d "$HOOK_DIR" ] && [ ! -L "$HOOK_DIR" ]; then
        write_marker "$release" "$previous" done 0 "no scripts"
        info "no after-update scripts ($HOOK_DIR) - $release noted"
        return 0
    fi
    if ! folder_safe; then
        log "=== after-update run for $release: the folder is not safe - nothing ran (see the warning; tried again at the next start)"
        return 0
    fi

    wait_for_clock
    local secs user home venv
    secs=$(timeout_seconds)
    user=$(desktop_user); home=$(desktop_home)
    venv=""
    [ -n "$home" ] && venv=$(venv_path "$home")
    [ -n "$venv" ] && [ -d "$venv" ] || venv=""
    TIMEOUT_CMD=$(command -v timeout || true)
    [ -n "$TIMEOUT_CMD" ] || warn "timeout(1) not found - the scripts run without a time limit"

    write_marker "$release" "$previous" started $((attempts + 1)) "running"
    local how=""
    $force && how=", forced"
    log "=== after-update run for $release (previous: ${previous:-unknown}; Slot $slot$how)"

    export RQ_RELEASE="$release" RQ_PREVIOUS_RELEASE="$previous" RQ_DESKTOP_USER="$user" \
        RQ_DESKTOP_HOME="$home" RQ_VENV="$venv" DEBIAN_FRONTEND=noninteractive
    export HOME="${HOME:-/root}"
    export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin${PATH:+:$PATH}"

    local f name ran=0 failed=0 skipped=0 rc
    for f in "$HOOK_DIR"/*; do
        [ -e "$f" ] || [ -L "$f" ] || continue
        name=$(basename "$f")
        case "$name" in
            .*|*~|*.dpkg-*) continue ;;
        esac
        if [ -L "$f" ]; then
            log "$name: skipped (a symbolic link - put the script itself in the folder)"
            skipped=$((skipped + 1)); continue
        fi
        [ -f "$f" ] || continue
        if [ ! -x "$f" ]; then
            log "$name: skipped (not executable: sudo chmod +x $f)"
            skipped=$((skipped + 1)); continue
        fi
        if ! safe_owner_mode "$f"; then
            log "$name: skipped - it must belong to root and must not be writable by group or others (sudo chown root:root $f; sudo chmod go-w $f)"
            skipped=$((skipped + 1)); continue
        fi
        log "$name: start (time limit $((secs / 60)) min)"
        rc=0
        run_one "$f" "$secs" || rc=$?
        ran=$((ran + 1))
        if [ "$rc" -eq 0 ]; then
            log "$name: done"
        elif [ -n "$TIMEOUT_CMD" ] && { [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; }; then
            log "$name: stopped after the time limit of $((secs / 60)) min"
            failed=$((failed + 1))
        else
            log "$name: failed (exit code $rc)"
            failed=$((failed + 1))
        fi
    done

    local result="ran $ran, failed $failed, skipped $skipped"
    write_marker "$release" "$previous" done $((attempts + 1)) "$result"
    log "=== after-update run for $release finished: $result"
    return 0
}

cmd_status() {
    local n=0 f release
    release=$(this_release)
    echo "After-update scripts: $HOOK_DIR"
    if [ -d "$HOOK_DIR" ]; then
        for f in "$HOOK_DIR"/*; do
            [ -f "$f" ] && [ -x "$f" ] || continue
            case "$(basename "$f")" in .*|*~|*.dpkg-*) continue ;; esac
            echo "  $(basename "$f")"
            n=$((n + 1))
        done
        [ "$n" -gt 0 ] || echo "  (no executable scripts)"
    else
        echo "  (the folder does not exist)"
    fi
    echo "This system: ${release:-unknown}"
    if [ -f "$MARKER" ]; then
        echo "Last run on this system ($MARKER):"
        sed 's/^/  /' "$MARKER"
    else
        echo "Last run on this system: none yet"
    fi
    if [ -r "$LOG" ]; then
        echo "Log of the last run ($LOG):"
        awk '/ === after-update run for / && !/ finished: / { buf = "" } { buf = buf "  " $0 "\n" }
             END { printf "%s", buf }' "$LOG"
    elif [ -e "$LOG" ]; then
        echo "Log: $LOG (sudo to read it)"
    fi
}

TIMEOUT_CMD=""
case "${1:-}" in
    run)    shift; cmd_run "$@" ;;
    status) cmd_status ;;
    *)      echo "Usage: $(basename "$0") run [--force] | status" >&2; exit 2 ;;
esac
