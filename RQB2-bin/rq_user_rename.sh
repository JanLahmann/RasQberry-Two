#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: give the desktop user the name typed in Raspberry Pi Imager (#319)
# ============================================================================
# Description: Renames the desktop user (uid 1000, "rasqberry" on every image)
#   to NEW and moves its home folder to /home/NEW, then rewrites everything on
#   the system that names the old user or its home:
#     - the account: usermod -l, groupmod -n, usermod -d -m (as Raspberry Pi
#       OS's userconf does); /etc/subuid, /etc/subgid
#     - text files that hold the old home path: the home folder itself (the
#       RQB2 venv's scripts and pyvenv.cfg, Thonny, Chromium/NSS, ...),
#       /etc (the LED renderer, LED clear and IP display units, ...) and the
#       crontabs; symlinks in the home that point into the old home or to
#       /data/home/OLD
#     - the old name: desktop autologin (lightdm, getty@tty1), sudoers.d,
#       linger (Raspberry Pi Connect), the user's crontab, lightdm's and
#       AccountsService's per-user folders
#     - A/B cards: /data/home/OLD -> /data/home/NEW (~/Shared, ~/.qiskit,
#       ~/My-Quantum-Programs); the name is kept in /data/rasqberry/desktop-user
#   Not changed: the venv template /usr/venv (rq_venv_repair.sh moves a copy
#   to the user's path itself). No /home/rasqberry compatibility link: the
#   RasQberry scripts find the user by uid 1000 / $HOME.
#
#   Runs when nothing runs as the user: at the first start of a new card
#   (rq_imager_userconf.sh, from Imager's firstrun.sh, before any login) and
#   on the first start of an A/B update (rq_carry_over.sh, before logins).
#   Any failure undoes every step done so far, so the system keeps working
#   with the old name; the reason is logged and kept in
#   /var/lib/rasqberry/user-rename-failed (the first login says so).
#   An interrupted run (power cut) is finished by the next "apply NEW".
#
# Usage: rq_user_rename.sh apply NEW [--dry-run] [--why TEXT]   (as root)
#        rq_user_rename.sh plan NEW      what apply would change (= --dry-run)
#        rq_user_rename.sh check NEW     exit 0 when NEW can be used, else why
#
# Environment (tests): RQ_RENAME_ROOT (a fake root: no pgrep, systemctl or
#   ownership changes; RQ_USERMOD/RQ_GROUPMOD edit its files), RQ_RENAME_DATA
#   (/data), RQ_RENAME_LOG, RQ_USERMOD (usermod), RQ_GROUPMOD (groupmod),
#   RQ_RENAME_FAIL_AT=account|paths|links|names (that step fails: rollback)

ROOT="${RQ_RENAME_ROOT:-}"
ROOT="${ROOT%/}"
DATA="${RQ_RENAME_DATA:-/data}"
LOG_FILE="${RQ_RENAME_LOG:-$ROOT/var/log/rasqberry-user-rename.log}"
STATE="$ROOT/var/lib/rasqberry"
JOURNAL="$STATE/user-rename.journal"
FAILED="$STATE/user-rename-failed"
DONE_FILE="$STATE/user-renamed"
USERMOD="${RQ_USERMOD:-usermod}"
GROUPMOD="${RQ_GROUPMOD:-groupmod}"
UID_DESKTOP=1000
LIVE=true
[ -n "$ROOT" ] && LIVE=false

DRY=false
WHY=""
UNDO=()
BACKUP=""
UNITS_CHANGED=false

log() {
    echo "rq_user_rename: $*"
    $DRY && return 0
    { mkdir -p "$(dirname "$LOG_FILE")" && echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; } 2>/dev/null || true
}
plan() { echo "  would $*"; }

# ---------------------------------------------------------------------------
# Accounts (read from the files: every RasQberry account is a local one)
# ---------------------------------------------------------------------------
pw_by_uid() { awk -F: -v u="$1" -v f="$2" '$3 == u { print $f; exit }' "$ROOT/etc/passwd" 2>/dev/null; }
pw_by_name() { awk -F: -v n="$1" -v f="$2" '$1 == n { print $f; exit }' "$ROOT/etc/passwd" 2>/dev/null; }
group_by_name() { awk -F: -v n="$1" -v f="$2" '$1 == n { print $f; exit }' "$ROOT/etc/group" 2>/dev/null; }

name_exists() {
    [ -n "$(pw_by_name "$1" 1)" ] && return 0
    [ -n "$(group_by_name "$1" 1)" ] && return 0
    if $LIVE; then
        getent passwd "$1" >/dev/null 2>&1 && return 0
        getent group "$1" >/dev/null 2>&1 && return 0
    fi
    return 1
}

# Why NEW cannot be the desktop user's name (empty: it can). OLD is the
# current name, which NEW may of course equal.
why_not() {
    local new="$1" old="$2"
    if [ -z "$new" ]; then echo "no name given"; return; fi
    if [ "$new" = "$old" ]; then return; fi
    if ! printf '%s' "$new" | grep -Eq '^[a-z][a-z0-9_-]{0,31}$'; then
        echo "'$new' is not a valid Linux user name (lower-case letters, digits, - and _, starting with a letter, at most 32)"
        return
    fi
    case "$new" in
        root|daemon|bin|sys|sync|games|man|lp|mail|news|uucp|proxy|www-data|backup|list|irc|nobody|systemd-*|messagebus|sshd|lightdm|vnc|docker|admin|sudo|users|staff)
            echo "'$new' is a system account name"; return ;;
    esac
    if name_exists "$new"; then echo "'$new' already exists on this system (user or group)"; return; fi
    if [ -e "$ROOT/home/$new" ] || [ -L "$ROOT/home/$new" ]; then echo "/home/$new already exists"; return; fi
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
re_escape() { printf '%s' "$1" | sed 's/[][\.*^$+?(){}|/#]/\\&/g'; }
sub_escape() { printf '%s' "$1" | sed 's/[\\&#]/\\&/g'; }

push_undo() { UNDO+=("$(printf '%q ' "$@")"); }

rollback() {
    local i
    [ "${#UNDO[@]}" -gt 0 ] || return 0
    log "Undoing ${#UNDO[@]} step(s)"
    for (( i=${#UNDO[@]}-1; i>=0; i-- )); do
        eval "${UNDO[$i]}" >/dev/null 2>&1 || log "WARNING: could not undo: ${UNDO[$i]}"
    done
    UNDO=()
    $LIVE && $UNITS_CHANGED && systemctl daemon-reload >/dev/null 2>&1 || true
}

# Keep a copy of FILE (its path on the system) before changing it; the undo
# step puts it back
backup_file() {
    local f="$1" rel
    rel="${f#"$ROOT"}"
    mkdir -p "$BACKUP$(dirname "$rel")"
    cp -p "$f" "$BACKUP$rel"
    push_undo cp -p "$BACKUP$rel" "$f"
}

# Point the symlink LINK at TARGET, keeping its owner (OWNER uid:gid)
relink() {
    ln -sfn "$1" "$2"
    if $LIVE && [ -n "${3:-}" ]; then chown -h "$3" "$2" 2>/dev/null || true; fi
}

# Tests: RQ_RENAME_FAIL_AT=<step> makes that step fail (rollback tests)
checkpoint() {
    if [ "${RQ_RENAME_FAIL_AT:-}" = "$1" ]; then
        echo "test: failing after the step '$1'" >&2
        return 1
    fi
    return 0
}

# Rename a path (file or folder) OLD -> NEW, with its undo
move_path() {
    local from="$1" to="$2"
    [ -e "$from" ] || [ -L "$from" ] || return 0
    if [ -e "$to" ] || [ -L "$to" ]; then
        log "WARNING: $to exists - $from left as it is"
        return 0
    fi
    if $DRY; then plan "move ${from#"$ROOT"} -> ${to#"$ROOT"}"; return 0; fi
    mv "$from" "$to"
    push_undo mv "$to" "$from"
}

# sed EXPR over FILE (GNU sed -i keeps mode and owner), after a backup
sed_file() {
    local expr="$1" f="$2"
    if $DRY; then plan "rewrite ${f#"$ROOT"}"; return 0; fi
    backup_file "$f"
    sed -E -i "$expr" "$f"
    case "$f" in "$ROOT"/etc/systemd/*) UNITS_CHANGED=true ;; esac
}

# Files under DIR (no symlinks followed) whose text holds the old home path
files_with_path() {
    local dir="$1" re="$2"
    [ -d "$dir" ] || return 0
    grep -rlIZ -E --exclude-dir=.cache --exclude-dir=.git -e "$re" "$dir" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# The steps
# ---------------------------------------------------------------------------
step_account() {
    local old="$1" new="$2" old_home="$3" new_home="$4" f
    # Undo = these copies of the account files, exactly as they were
    if ! $DRY; then
        for f in passwd shadow group gshadow; do
            [ -f "$ROOT/etc/$f" ] && backup_file "$ROOT/etc/$f"
        done
    fi
    # The login name (also in the supplementary groups' member lists)
    if [ -n "$(pw_by_name "$old" 1)" ] && [ "$old" != "$new" ]; then
        if $DRY; then plan "rename the user $old -> $new (usermod -l)"; else
            "$USERMOD" -l "$new" "$old"
        fi
    fi
    # Its own group (gid 1000, named like the user)
    local gid
    gid=$(pw_by_uid "$UID_DESKTOP" 4)
    if [ "$(group_by_name "$old" 3)" = "${gid:-1000}" ] && [ "$old" != "$new" ]; then
        if $DRY; then plan "rename the group $old -> $new (groupmod -n)"; else
            "$GROUPMOD" -n "$new" "$old"
        fi
    fi
    # The home folder (as the account says now: an interrupted run may have
    # moved it already)
    local home_field
    home_field=$(pw_by_uid "$UID_DESKTOP" 6)
    if $DRY; then home_field="$old_home"; fi
    if [ "$home_field" != "$new_home" ]; then
        if $DRY; then plan "move the home folder $old_home -> $new_home (usermod -d -m)"; else
            "$USERMOD" -d "$new_home" -m "$new"
            # undone before the account files come back
            [ -d "$ROOT$new_home" ] && [ ! -e "$ROOT$home_field" ] && push_undo mv "$ROOT$new_home" "$ROOT$home_field"
        fi
    fi
    # subuid/subgid (usermod renames them on newer shadow versions only)
    for f in "$ROOT/etc/subuid" "$ROOT/etc/subgid"; do
        [ -f "$f" ] && grep -q "^$(re_escape "$old"):" "$f" || continue
        sed_file "s#^$(re_escape "$old"):#$(sub_escape "$new"):#" "$f"
    done
}

step_paths() {
    local old_home="$1" new_home="$2" home_now="$3"
    local re sub f n=0 list=()
    re="$(re_escape "$old_home")([^A-Za-z0-9._-]|\$)"
    sub="$(sub_escape "$new_home")\\1"
    # The home (as it is now: moved already, unless this is a dry run), /etc
    # (systemd units, ...) and the crontabs. Account files are usermod's.
    while IFS= read -r -d '' f; do
        case "$f" in
            "$ROOT"/etc/passwd|"$ROOT"/etc/passwd-|"$ROOT"/etc/shadow|"$ROOT"/etc/shadow-) continue ;;
            "$ROOT"/etc/group|"$ROOT"/etc/group-|"$ROOT"/etc/gshadow|"$ROOT"/etc/gshadow-) continue ;;
            "$ROOT"/etc/subuid*|"$ROOT"/etc/subgid*|*.rq-rename-*) continue ;;
        esac
        [ -f "$f" ] && [ ! -L "$f" ] || continue
        list+=("$f")
    done < <(files_with_path "$ROOT$home_now" "$re"; files_with_path "$ROOT/etc" "$re"; \
             files_with_path "$ROOT/var/spool/cron/crontabs" "$re")
    for f in "${list[@]+"${list[@]}"}"; do
        sed_file "s#${re}#${sub}#g" "$f"
        n=$((n + 1))
    done
    if [ "$n" -gt 0 ] && ! $DRY; then log "Paths rewritten: $old_home -> $new_home in $n file(s)"; fi
    return 0
}

# Symlinks in the home that point into the old home or to /data/home/OLD
step_links() {
    local old_home="$1" new_home="$2" old="$3" new="$4" home_now="$5"
    local link target to owner
    [ -d "$ROOT$home_now" ] || return 0
    while IFS= read -r -d '' link; do
        target=$(readlink "$link")
        to=""
        case "$target" in
            "$old_home"|"$old_home"/*) to="$new_home${target#"$old_home"}" ;;
            "$DATA/home/$old"|"$DATA/home/$old"/*) to="$DATA/home/$new${target#"$DATA/home/$old"}" ;;
        esac
        [ -n "$to" ] || continue
        if $DRY; then plan "relink ${link#"$ROOT"} -> $to"; continue; fi
        owner=$(stat -c %u:%g "$link" 2>/dev/null || echo "")
        relink "$to" "$link" "$owner"
        push_undo relink "$target" "$link" "$owner"
    done < <(find "$ROOT$home_now" -xdev -type l -print0 2>/dev/null || true)
}

step_names() {
    local old="$1" new="$2" o n f
    o=$(re_escape "$old"); n=$(sub_escape "$new")
    # Desktop autologin
    for f in "$ROOT/etc/lightdm/lightdm.conf" "$ROOT"/etc/lightdm/lightdm.conf.d/*.conf; do
        [ -f "$f" ] && grep -Eq "^autologin-user=${o}[[:space:]]*\$" "$f" || continue
        sed_file "s#^autologin-user=${o}[[:space:]]*\$#autologin-user=${n}#" "$f"
    done
    # Console autologin (raspi-config's getty@tty1 drop-in, serial consoles)
    for f in "$ROOT"/etc/systemd/system/*getty@*.service.d/*.conf; do
        [ -f "$f" ] && grep -Eq -- "--autologin[ =]${o}([[:space:]]|\$)" "$f" || continue
        sed_file "s#(--autologin[ =])${o}([[:space:]]|\$)#\\1${n}\\2#g" "$f"
    done
    # sudo rules (010_rasqberry-nopasswd: "rasqberry ALL=(ALL) NOPASSWD: ALL")
    for f in "$ROOT"/etc/sudoers.d/*; do
        [ -f "$f" ] && grep -Eq "^${o}[[:space:]]" "$f" || continue
        sed_file "s#^${o}([[:space:]])#${n}\\1#" "$f"
        if ! $DRY && command -v visudo >/dev/null 2>&1 && ! visudo -cqf "$f" >/dev/null 2>&1; then
            echo "the sudo rule in $f does not check out after the rename" >&2
            return 1
        fi
    done
    # Per-user state named after the user
    move_path "$ROOT/var/lib/systemd/linger/$old" "$ROOT/var/lib/systemd/linger/$new"
    move_path "$ROOT/var/spool/cron/crontabs/$old" "$ROOT/var/spool/cron/crontabs/$new"
    move_path "$ROOT/var/lib/lightdm/data/$old" "$ROOT/var/lib/lightdm/data/$new"
    move_path "$ROOT/var/lib/AccountsService/users/$old" "$ROOT/var/lib/AccountsService/users/$new"
    move_path "$ROOT/var/lib/AccountsService/icons/$old" "$ROOT/var/lib/AccountsService/icons/$new"
    # A/B: the user's files on the data partition (only where no folder of
    # the new name is there already - the other slot's, after an update)
    if [ -d "$DATA/home/$old" ] && [ ! -L "$DATA/home/$old" ] && [ ! -e "$DATA/home/$new" ]; then
        move_path "$DATA/home/$old" "$DATA/home/$new"
    fi
}

# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------
NEW_NAME=""
MAIN_PID=$$

# Not renamed: undo what was done, keep the reason for the first login
fail() {
    local reason="$1"
    log "NOT renamed to '$NEW_NAME': $reason"
    $DRY && return 1
    rollback
    { mkdir -p "$STATE" && printf '%s\n%s\n' "$NEW_NAME" "$reason" > "$FAILED"; } 2>/dev/null || true
    rm -f "$JOURNAL" 2>/dev/null || true
    if [ -n "$BACKUP" ]; then
        rm -rf "$BACKUP" 2>/dev/null || true
        rmdir "$STATE/user-rename-backup" 2>/dev/null || true
    fi
    return 1
}

on_error() {
    local rc=$? cmd="$BASH_COMMAND" line="${BASH_LINENO[0]:-?}"
    # A subshell ($(...)) only ends: its caller sees the failure
    [ "${BASHPID:-$$}" = "$MAIN_PID" ] || exit "$rc"
    trap - ERR
    set +e
    fail "a step failed (line $line: $cmd, exit $rc)"
    exit 1
}

finish() {
    local old="$1" new="$2"
    if $LIVE && $UNITS_CHANGED && [ -d /run/systemd/system ]; then
        systemctl daemon-reload >/dev/null 2>&1 || log "WARNING: systemctl daemon-reload failed"
    fi
    printf 'from=%s\nto=%s\ntime=%s\nwhy=%s\n' "$old" "$new" "$(date -Iseconds)" "$WHY" > "$DONE_FILE"
    # Both A/B systems use this name: rq_carry_over.sh reads it when the
    # other system cannot be read
    if [ -d "$DATA/rasqberry" ]; then
        printf '%s\n' "$new" > "$DATA/rasqberry/desktop-user" 2>/dev/null || true
    fi
    rm -f "$FAILED" "$JOURNAL"
    rm -rf "$BACKUP"
    rmdir "$STATE/user-rename-backup" 2>/dev/null || true
    sync
    log "The desktop user is now '$new' (home /home/$new)"
}

cmd_apply() {
    local new="$1" cur cur_home old old_home new_home home_now reason resume=false
    NEW_NAME="$new"
    cur=$(pw_by_uid "$UID_DESKTOP" 1)
    cur_home=$(pw_by_uid "$UID_DESKTOP" 6)
    [ -n "$cur" ] || { log "no user with uid $UID_DESKTOP - nothing to rename"; return 1; }
    old="$cur"; old_home="$cur_home"
    new_home="/home/$new"

    # An interrupted run (power cut): finish it
    if [ -f "$JOURNAL" ]; then
        local j_old j_new j_home
        j_old=$(sed -n 's/^from=//p' "$JOURNAL" | head -1)
        j_home=$(sed -n 's/^from_home=//p' "$JOURNAL" | head -1)
        j_new=$(sed -n 's/^to=//p' "$JOURNAL" | head -1)
        if [ "$j_new" = "$new" ] && [ -n "$j_old" ] && { [ "$cur" = "$new" ] || [ "$cur" = "$j_old" ]; }; then
            old="$j_old"; old_home="${j_home:-/home/$j_old}"; resume=true
            log "Finishing an interrupted rename $old -> $new"
        elif ! $DRY; then
            rm -f "$JOURNAL"
        fi
    fi

    if ! $resume; then
        if [ "$cur" = "$new" ] && [ "$cur_home" = "$new_home" ]; then
            log "The user is already called '$new' - nothing to do"
            return 0
        fi
        reason=$(why_not "$new" "$cur")
        [ -z "$reason" ] || { fail "$reason"; return 1; }
    fi
    if $LIVE && ! $DRY && [ "$(id -u)" != 0 ]; then fail "needs root"; return 1; fi
    if $LIVE && pgrep -u "$UID_DESKTOP" >/dev/null 2>&1; then
        fail "programs of the user $cur are running (the rename runs before anyone logs in)"
        return 1
    fi
    if [ ! -d "$ROOT$old_home" ] && [ ! -d "$ROOT$new_home" ]; then
        fail "the home folder $old_home is missing"; return 1
    fi

    if $DRY; then
        echo "Renaming the desktop user $old -> $new (home $old_home -> $new_home) would:"
        home_now="$old_home"
    else
        log "Renaming the desktop user $old -> $new (home $old_home -> $new_home)${WHY:+ - $WHY}"
        mkdir -p "$STATE/user-rename-backup"
        chmod 700 "$STATE/user-rename-backup"
        BACKUP="$STATE/user-rename-backup/$(date '+%Y%m%d-%H%M%S')"
        mkdir -p "$BACKUP"
        printf 'from=%s\nfrom_home=%s\nto=%s\ntime=%s\n' "$old" "$old_home" "$new" "$(date -Iseconds)" > "$JOURNAL"
        sync
        home_now="$new_home"
    fi

    set -E
    trap on_error ERR
    step_account "$old" "$new" "$old_home" "$new_home"; checkpoint account
    step_paths "$old_home" "$new_home" "$home_now";      checkpoint paths
    step_links "$old_home" "$new_home" "$old" "$new" "$home_now"; checkpoint links
    step_names "$old" "$new";                            checkpoint names
    trap - ERR
    set +E

    if $DRY; then
        echo "(dry run: nothing changed)"
    else
        finish "$old" "$new"
    fi
}

usage() {
    sed -n 's/^# Usage: /Usage: /p; s/^#        rq_user_rename/       rq_user_rename/p' "$0"
}

case "${1:-}" in
    apply|plan)
        sub="$1"; shift
        new="${1:-}"; shift || true
        [ "$sub" = plan ] && DRY=true
        while [ $# -gt 0 ]; do
            case "$1" in
                --dry-run) DRY=true ;;
                --why) WHY="${2:-}"; shift ;;
                *) usage >&2; exit 2 ;;
            esac
            shift
        done
        [ -n "$new" ] || { usage >&2; exit 2; }
        cmd_apply "$new"
        ;;
    check)
        old=$(pw_by_uid "$UID_DESKTOP" 1)
        reason=$(why_not "${2:-}" "$old")
        if [ -n "$reason" ]; then echo "$reason"; exit 1; fi
        exit 0
        ;;
    -h|--help) usage ;;
    *) usage >&2; exit 2 ;;
esac
