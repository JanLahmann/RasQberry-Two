#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: install the system files from RQB2-system/ (#294)
# ============================================================================
# Description: RQB2-system/ mirrors the root filesystem: boot scripts in
#   /usr/local/bin, systemd units, autostart entries, profile.d, the XDG menu.
#   This one script installs it, for the image build (01-deploy-files) and for
#   "Update from GitHub Branch" alike, so both put the same files in the same
#   places. Before #294 these were written by heredocs and copies scattered
#   over five build stages, and a branch update never refreshed them.
#
#   - Files keep their repository mode (scripts executable, the rest 644).
#   - @USER@, @REPO@, @VENV@ are replaced (the LED renderer unit uses them).
#   - Units in enabled-units.txt are enabled: all of them with --build; with
#     --update only those that did not exist before, so a unit the user turned
#     off stays off.
#
# Usage: rq_install_system_files.sh <RQB2-system dir> --build|--update [--root DIR]
#   --root installs below DIR instead of / (tests); systemctl is skipped then.
# Environment: RQ_SYS_USER, RQ_SYS_REPO, RQ_SYS_VENV override the placeholders.

src="${1:-}"
mode="${2:-}"
root="/"
[ "${3:-}" = "--root" ] && root="${4:?--root needs a directory}"
[ -d "$src" ] || { echo "Usage: $(basename "$0") <RQB2-system dir> --build|--update [--root DIR]" >&2; exit 2; }
case "$mode" in --build|--update) ;; *) echo "Mode must be --build or --update" >&2; exit 2 ;; esac

user="${RQ_SYS_USER:-$( (getent passwd 1000 2>/dev/null || true) | cut -d: -f1)}"
user="${user:-rasqberry}"
repo="${RQ_SYS_REPO:-${REPO:-RasQberry-Two}}"
venv="${RQ_SYS_VENV:-${STD_VENV:-RQB2}}"
use_systemctl=false
[ "$root" = "/" ] && command -v systemctl >/dev/null 2>&1 && use_systemctl=true

new_units=()
count=0
while IFS= read -r -d '' file; do
    rel="${file#"$src"/}"
    [ "$rel" = "enabled-units.txt" ] && continue
    dest="${root%/}/$rel"
    [ -e "$dest" ] || case "$rel" in etc/systemd/system/*) new_units+=("$(basename "$rel")") ;; esac
    mode_bits=644
    [ -x "$file" ] && mode_bits=755
    mkdir -p "$(dirname "$dest")"
    tmp="$dest.rq-new.$$"
    sed -e "s|@USER@|${user}|g" -e "s|@REPO@|${repo}|g" -e "s|@VENV@|${venv}|g" "$file" > "$tmp"
    chmod "$mode_bits" "$tmp"
    mv -f "$tmp" "$dest"
    count=$((count + 1))
done < <(find "$src" -type f -print0 | sort -z)
echo "Installed $count system file(s) from $src"

$use_systemctl && systemctl daemon-reload 2>/dev/null || true

enabled=0
while IFS= read -r unit; do
    unit="${unit%%#*}"; unit="${unit//[[:space:]]/}"
    [ -n "$unit" ] || continue
    if [ "$mode" = "--update" ]; then
        printf '%s\n' "${new_units[@]:-}" | grep -qx "$unit" || continue
    fi
    if $use_systemctl; then
        systemctl enable "$unit" >/dev/null 2>&1 || echo "WARNING: could not enable $unit" >&2
    fi
    echo "Enabled: $unit"
    enabled=$((enabled + 1))
done < "$src/enabled-units.txt"
[ "$mode" = "--update" ] && [ "$enabled" -eq 0 ] && echo "No new units to enable"
exit 0
