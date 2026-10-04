#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: learner setup (write and run your own programs)
# ============================================================================
# Description: Prepares the current user for writing their own Qiskit and LED
#   programs. Idempotent and quiet enough to run at every desktop login.
#
#   Every run:
#   - venv extras (from /usr/config/venv-extras) in the user's RQB2 venv:
#     00-rasqberry.pth puts /usr/bin (rq_led_utils, ...) on the import path and
#     keeps root runs from writing bytecode into the venv (R-072, R-059);
#     zz-rasqberry.json turns off the JupyterLab server extension that
#     `jupyter notebook` cannot load, which printed a traceback (R-127).
#   Once per user (a stamp in ~/.local/state/rasqberry/learner-setup/):
#   - Thonny runs programs with the venv python, so `import qiskit` works (R-074).
#     An interpreter the user picked in Thonny is left alone.
#   - Geany's Execute runs Python files through rq_python (R-074).
#   - ~/My-Quantum-Programs with the starter programs (R-071). On an A/B card
#     with a data partition the folder lives on /data and ~/My-Quantum-Programs
#     is a link to it (rq_carry_over.sh, Jan Q33c), so it survives updates; the
#     starter files go where the link points. A file already there is never
#     replaced. A starter added in a later release (the Hello World notebook)
#     is copied into an existing folder once; one the learner deleted stays
#     deleted.
#
#   Callers: the image build (stage 03-install-qiskit), the XDG autostart
#   entry rasqberry-learner-setup.desktop (every desktop login, which covers
#   upgraded devices and new users), rq_my_programs.sh, rq_venv_repair.sh.
#
# Usage: rq_learner_setup.sh [--quiet]          set up the current user
#        rq_learner_setup.sh --venv-only DIR    only the venv extras, into DIR
#                                               (image build, venv recovery)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Shipped files: /usr/config on the image, RQB2-config next to RQB2-bin in a checkout.
if [ -n "${RQ_LEARNER_CONFIG_DIR:-}" ]; then
    CONFIG_DIR="$RQ_LEARNER_CONFIG_DIR"
elif [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    CONFIG_DIR="/usr/config"
else
    CONFIG_DIR="$(dirname "$SCRIPT_DIR")/RQB2-config"
fi
EXTRAS_DIR="$CONFIG_DIR/venv-extras"
STARTER_DIR="$CONFIG_DIR/my-quantum-programs"
PROGRAMS_DIRNAME="My-Quantum-Programs"

QUIET=false
say() { $QUIET || info "$*"; }

# Copy src to dest unless dest already has the same content.
# Returns 0 if it copied, 1 if dest was up to date, 2 on an error.
_install_if_changed() {
    local src="$1" dest="$2"
    [ -f "$src" ] || { warn "Missing shipped file: $src"; return 2; }
    cmp -s "$src" "$dest" 2>/dev/null && return 1
    if mkdir -p "$(dirname "$dest")" && cp "$src" "$dest.rq-new.$$" \
            && chmod 644 "$dest.rq-new.$$" && mv -f "$dest.rq-new.$$" "$dest"; then
        return 0
    fi
    rm -f "$dest.rq-new.$$" 2>/dev/null
    warn "Could not install $dest"
    return 2
}

# Install the venv extras into the venv at $1. Returns non-zero on an error.
install_venv_extras() {
    local venv="$1" site rc
    [ -d "$venv" ] || { warn "No venv at $venv"; return 1; }
    site=$(find "$venv/lib" -maxdepth 2 -type d -name site-packages 2>/dev/null | head -1)
    [ -n "$site" ] || { warn "No site-packages in $venv"; return 1; }

    rc=0; _install_if_changed "$EXTRAS_DIR/00-rasqberry.pth" "$site/00-rasqberry.pth" || rc=$?
    case $rc in
        0) say "Installed $site/00-rasqberry.pth" ;;
        2) return 1 ;;
    esac
    rc=0; _install_if_changed "$EXTRAS_DIR/zz-rasqberry.json" \
        "$venv/etc/jupyter/jupyter_notebook_config.d/zz-rasqberry.json" || rc=$?
    case $rc in
        0) say "Installed the Jupyter notebook settings in $venv/etc/jupyter" ;;
        2) return 1 ;;
    esac
    return 0
}

# Stamps for the once-per-user steps (set in main, after the environment).
STAMP_DIR=""
_done() { [ -f "$STAMP_DIR/$1" ]; }
_mark() { mkdir -p "$STAMP_DIR" && date '+%Y-%m-%dT%H:%M:%S%z' > "$STAMP_DIR/$1"; }

# Thonny: use the venv python, unless the user already picked another one.
configure_thonny() {
    local python="$1" ini="${USER_HOME}/.config/Thonny/configuration.ini"
    _done thonny && return 0
    if pgrep -u "$(id -u)" -x thonny >/dev/null 2>&1; then
        say "Thonny is running - its interpreter is set at the next login"
        return 0
    fi
    mkdir -p "$(dirname "$ini")" || return 1
    # configparser keeps every other Thonny setting. Only a missing interpreter
    # or Thonny's default (the system python, which has no Qiskit) is replaced.
    /usr/bin/python3 - "$ini" "$python" <<'PYEOF'
import configparser, os, sys
ini, python = sys.argv[1], sys.argv[2]
cp = configparser.ConfigParser(interpolation=None)
cp.optionxform = str
if os.path.exists(ini):
    with open(ini, encoding="utf-8") as fh:
        cp.read_file(fh)
for section in ("run", "LocalCPython"):
    if not cp.has_section(section):
        cp.add_section(section)
if not cp.get("run", "backend_name", fallback=""):
    cp.set("run", "backend_name", "LocalCPython")
current = cp.get("LocalCPython", "executable", fallback="")
if current in ("", "/usr/bin/python3", "/usr/bin/python3.11", "/usr/bin/python"):
    cp.set("LocalCPython", "executable", python)
with open(ini + ".rq-new", "w", encoding="utf-8") as fh:
    cp.write(fh)
os.replace(ini + ".rq-new", ini)
PYEOF
    [ $? -eq 0 ] || return 1
    _mark thonny
    say "Thonny runs programs with $python"
}

# Geany: Build > Execute runs Python files through rq_python (venv, LEDs).
configure_geany() {
    local ft="${USER_HOME}/.config/geany/filedefs/filetypes.python"
    _done geany && return 0
    if [ ! -e "$ft" ]; then
        mkdir -p "$(dirname "$ft")" || return 1
        cat > "$ft" <<'EOF'
# RasQberry: run Python files with the RasQberry Python environment (Qiskit,
# LED libraries). rq_python also handles the LEDs on a Raspberry Pi 4.
[build-menu]
EX_00_LB=_Execute
EX_00_CM=/usr/bin/rq_python "%f"
EX_00_WD=
EOF
        [ $? -eq 0 ] || return 1
        say "Geany runs Python files with rq_python"
    fi
    _mark geany
}

# ~/My-Quantum-Programs with the starter programs, created once. On an A/B
# card ~/My-Quantum-Programs may be a link to /data (rq_carry_over.sh): the
# starter files then land on /data, next to the learner's own files, and
# survive updates. Files that are already there are never overwritten.
seed_programs() {
    local dest="${USER_HOME}/${PROGRAMS_DIRNAME}" target
    _done programs && return 0
    [ -d "$STARTER_DIR" ] || { warn "Starter programs not found: $STARTER_DIR"; return 0; }
    if [ -L "$dest" ] && [ ! -e "$dest" ]; then
        # A link to a folder that is gone: recreate it only where its parent
        # exists (/data/home/<user> on a mounted data partition)
        target=$(readlink "$dest")
        if [ ! -d "$(dirname "$target")" ]; then
            warn "~/${PROGRAMS_DIRNAME} points to $target, which is not available - starter programs not copied"
            return 0
        fi
        mkdir -p "$target" || return 1
    fi
    if [ ! -e "$dest" ] || [ -z "$(ls -A "$dest/" 2>/dev/null)" ]; then
        # Only into a new or empty folder: nothing of the learner's to overwrite
        mkdir -p "$dest/" || return 1
        cp -R "$STARTER_DIR"/. "$dest"/ || return 1
        # /usr/config is installed 755 throughout; these are documents to edit.
        # "$dest/": follow the link to /data.
        find "$dest/" -type f -exec chmod 644 {} + || return 1
        find "$dest/" -type d -exec chmod 755 {} + || return 1
        say "Created $dest with starter programs"
    fi
    _mark programs
}

# The starter files shipped before the offered-list existed: a folder seeded
# by those releases already had the chance to keep or delete them.
LEGACY_STARTERS="01_bell_state.py 02_ghz_histogram.py 03_led_hello.py 04_bell_on_leds.py My-First-Circuit.ipynb README.md"

# Starter files that are new since the folder was seeded (item 9): copied once
# into an existing ~/My-Quantum-Programs, never over a file of the same name.
# programs.offered in the stamp directory lists what was offered already.
offer_new_starters() {
    local dest="${USER_HOME}/${PROGRAMS_DIRNAME}" list="$STAMP_DIR/programs.offered" src name
    _done programs || return 0
    [ -d "$dest/" ] && [ -d "$STARTER_DIR" ] || return 0
    if [ ! -f "$list" ]; then
        mkdir -p "$STAMP_DIR" || return 1
        printf '%s\n' $LEGACY_STARTERS > "$list" || return 1
    fi
    for src in "$STARTER_DIR"/*; do
        [ -f "$src" ] || continue
        name=$(basename "$src")
        grep -qxF "$name" "$list" && continue
        if [ ! -e "$dest/$name" ]; then
            cp "$src" "$dest/$name" && chmod 644 "$dest/$name" || return 1
            say "Added $name to ~/${PROGRAMS_DIRNAME}"
        fi
        echo "$name" >> "$list" || return 1
    done
}

main() {
    case "${1:-}" in
        --venv-only)
            [ -n "${2:-}" ] || die "Usage: $(basename "$0") --venv-only <venv dir>"
            install_venv_extras "$2"
            return 0
            ;;
        --quiet) QUIET=true ;;
        "") ;;
        *) die "Usage: $(basename "$0") [--quiet] | --venv-only <venv dir>" ;;
    esac

    [ "$(id -u)" -ne 0 ] || die "Run this as the user, not as root"
    load_rqb2_env
    verify_env_vars REPO USER_HOME STD_VENV
    STAMP_DIR="${USER_HOME}/.local/state/rasqberry/learner-setup"

    local venv
    if venv=$(find_venv "$STD_VENV"); then
        install_venv_extras "$venv" || warn "Could not update the venv extras in $venv"
        configure_thonny "$venv/bin/python3" || warn "Could not configure Thonny"
    else
        say "No RasQberry venv yet - Thonny is configured once it exists"
    fi
    configure_geany || warn "Could not configure Geany"
    seed_programs || warn "Could not create ~/${PROGRAMS_DIRNAME}"
    offer_new_starters || warn "Could not add the new starter files to ~/${PROGRAMS_DIRNAME}"
}

main "$@"
