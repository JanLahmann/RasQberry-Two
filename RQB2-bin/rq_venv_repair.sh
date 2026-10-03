#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: check and repair the RasQberry Python environment (RQB2 venv)
# ============================================================================
# Description: Checks the user's RQB2 venv and repairs the two ways it breaks:
#   --fix-ownership  Root runs used to leave root-owned files in the venv, and a
#                    later `pip install -U` or reinstall then failed half-way
#                    with "Permission denied" (#285, R-059). Gives every file
#                    back to the user (sudo chown).
#   --reset          Replaces the venv with a fresh copy of the image's template
#                    (/usr/venv), bin/ included, so jupyter and the other
#                    commands work again. The old venv is KEPT as
#                    <venv>.previous (one copy; an older one is removed), and
#                    the packages it had beyond the template are listed (R-128).
#                    Also creates the venv for a user who has none.
#   Without an option it only reports.
#
# Usage: rq_venv_repair.sh [--fix-ownership] [--reset] [--yes]
#   --yes  no confirmation question (setup_qiskit_env.sh uses it for the
#          automatic recovery when Qiskit is missing)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

usage() {
    sed -n 's/^# Usage: /Usage: /p' "$0"
    echo "  (no option)      report the state of the environment"
    echo "  --fix-ownership  give root-owned files in the venv back to you (pip 'Permission denied')"
    echo "  --reset          fresh venv from the image template; the old one is kept as .previous"
    echo "  --yes            do not ask before --reset"
}

FIX_OWNERSHIP=false
RESET=false
ASSUME_YES=false
for arg in "$@"; do
    case "$arg" in
        --fix-ownership) FIX_OWNERSHIP=true ;;
        --reset) RESET=true ;;
        --yes) ASSUME_YES=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "Unknown option: $arg" ;;
    esac
done

load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

USER_NAME=$(get_user_name)
VENV="$USER_HOME/$REPO/venv/$STD_VENV"
PREVIOUS="$VENV.previous"
TEMPLATE="${RQ_VENV_TEMPLATE:-/usr/venv/$REPO/venv/$STD_VENV}"

as_user() {
    if [ "$(id -u)" -eq 0 ]; then
        sudo -u "$USER_NAME" -H -- "$@"
    else
        "$@"
    fi
}

confirm() {
    $ASSUME_YES && return 0
    [ -t 0 ] || die "Not confirmed (no terminal): add --yes"
    local answer
    read -r -p "$1 [y/N] " answer
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

root_owned_count() {
    find "$1" -user root 2>/dev/null | wc -l | tr -d ' '
}

report() {
    echo "RasQberry Python environment: $VENV"
    if [ ! -x "$VENV/bin/python3" ]; then
        echo "  missing - create it with: $(basename "$0") --reset"
        return 0
    fi
    local qiskit
    qiskit=$("$VENV/bin/python3" -c "import importlib.metadata as m; print(m.version('qiskit'))" 2>/dev/null || echo "MISSING")
    echo "  qiskit:            $qiskit"
    if [ -x "$VENV/bin/jupyter-lab" ]; then
        echo "  jupyter-lab:       ok"
    else
        echo "  jupyter-lab:       MISSING"
    fi
    echo "  root-owned files:  $(root_owned_count "$VENV")"
    [ -d "$PREVIOUS" ] && echo "  previous copy:     $PREVIOUS"
    echo ""
    echo "Repairs: --fix-ownership (pip 'Permission denied'), --reset (missing Qiskit or commands)"
}

fix_ownership() {
    local count
    count=$(root_owned_count "$VENV")
    if [ "$count" = "0" ]; then
        info "No root-owned files in $VENV"
        return 0
    fi
    info "Giving $count root-owned file(s) in $VENV back to $USER_NAME"
    sudo chown -R "$USER_NAME:$USER_NAME" "$VENV" || die "chown failed (needs sudo rights)"
}

# Package names (dist-info/egg-info) in a site-packages directory.
_packages() {
    local site
    site=$(find "$1/lib" -maxdepth 2 -type d -name site-packages 2>/dev/null | head -1)
    [ -n "$site" ] || return 0
    local d
    for d in "$site"/*.dist-info "$site"/*.egg-info; do
        [ -e "$d" ] && basename "$d"
    done | sed -E 's/-[0-9][^-]*\.(dist|egg)-info$//; s/\.(dist|egg)-info$//' | tr 'A-Z_' 'a-z-' | sort -u
}

reset_venv() {
    [ -x "$TEMPLATE/bin/python3" ] || [ -L "$TEMPLATE/bin/python3" ] || die "Template venv not found: $TEMPLATE"

    # Space: the copy needs about the template's size; the old venv only moves.
    local need avail
    need=$(du -sk "$TEMPLATE" | cut -f1)
    mkdir -p "$(dirname "$VENV")"
    avail=$(df -Pk "$(dirname "$VENV")" | awk 'NR==2 {print $4}')
    if [ -d "$PREVIOUS" ]; then
        avail=$((avail + $(du -sk "$PREVIOUS" | cut -f1)))
    fi
    if [ "$avail" -lt $((need + 204800)) ]; then
        die "Not enough free space: the fresh copy needs $((need / 1024)) MB plus 200 MB, $((avail / 1024)) MB are free. Your environment was not changed."
    fi

    # One repair at a time: every new terminal sources setup_qiskit_env.sh.
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$(dirname "$VENV")/.rq-venv-repair.lock"
        flock -n 9 || die "Another repair of $VENV is running"
    fi

    if [ -d "$VENV" ]; then
        confirm "Replace $VENV with a fresh copy? The current one is kept as $PREVIOUS" \
            || { info "Nothing changed"; return 0; }
        if [ -d "$PREVIOUS" ]; then
            info "Removing the older copy $PREVIOUS"
            rm -rf "$PREVIOUS" 2>/dev/null || sudo rm -rf "$PREVIOUS"
        fi
        mv "$VENV" "$PREVIOUS" || sudo mv "$VENV" "$PREVIOUS"
        info "Kept the old environment as $PREVIOUS"
    fi

    info "Copying the RasQberry Python environment (about $((need / 1024)) MB, this takes a few minutes)..."
    # -P keeps the venv's symlinks (python3 -> /usr/bin/python3, the system
    # gi/cairo/PyQt5). -p keeps modes and times; the owner it cannot keep as a
    # user, so the copy belongs to the user.
    as_user cp -RPp "$TEMPLATE" "$VENV"

    # The template was built at the first user's path. Scripts in bin/ (pip,
    # jupyter, activate, ...) carry that path; point them at this venv.
    local old
    old=$(grep -m1 '^VIRTUAL_ENV=' "$TEMPLATE/bin/activate" 2>/dev/null | cut -d= -f2- | tr -d "\"'")
    if [ -n "$old" ] && [ "$old" != "$VENV" ]; then
        grep -rlI -F "$old" "$VENV/bin" "$VENV/pyvenv.cfg" 2>/dev/null \
            | while IFS= read -r file; do
                as_user sh -c 'sed "s|$1|$2|g" "$3" > "$3.rq-new" && cat "$3.rq-new" > "$3" && rm -f "$3.rq-new"' \
                    sh "$old" "$VENV" "$file"
            done
    fi

    as_user "${SCRIPT_DIR}/rq_learner_setup.sh" --venv-only "$VENV" >/dev/null \
        || warn "Could not install the RasQberry venv extras"

    if [ -d "$PREVIOUS" ]; then
        local extra
        extra=$(comm -23 <(_packages "$PREVIOUS") <(_packages "$VENV") | tr '\n' ' ')
        if [ -n "$extra" ]; then
            echo ""
            echo "Packages you had added (still in $PREVIOUS):"
            echo "  $extra"
            echo "Reinstall what you need with: pip install <name>"
            echo "Delete the old copy when done: rm -rf $PREVIOUS"
        fi
    fi
    info "Fresh RasQberry Python environment ready: $VENV"
}

if ! $FIX_OWNERSHIP && ! $RESET; then
    report
    exit 0
fi
$FIX_OWNERSHIP && fix_ownership
$RESET && reset_venv
exit 0
