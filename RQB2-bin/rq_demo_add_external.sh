#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: rq_demo_add_external.sh
# ============================================================================
# Description:
#   Install (or update) an external demo from the curated registry
#   (known-demos.json). Each registry entry pins a repo to a full commit SHA.
#   The demo is shallow-fetched at that exact SHA, its manifest is validated
#   with the hardened external constraints, and on success the manifest is
#   copied into the user manifest directory so the universal launcher can
#   dispatch it like any other demo. No per-demo code is shipped by RasQberry.
#
# Usage:
#   rq_demo_add_external.sh                 # interactive: pick an uninstalled demo
#   rq_demo_add_external.sh <id>            # install demo <id> from the registry
#   rq_demo_add_external.sh --update <id>   # re-fetch the current registry SHA
#   rq_demo_add_external.sh --list          # list registry entries + status
#
# Requires: jq, git, curl (via the launcher)

# ============================================================================
# SETUP
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

load_rqb2_env
verify_env_vars REPO USER_HOME

# ----------------------------------------------------------------------------
# Path resolution: installed (/usr/*) vs repo (dev)
# ----------------------------------------------------------------------------
if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    REGISTRY_FILE="/usr/config/known-demos.json"
    CACHE_FILE="/usr/config/demo-menu-cache.sh"
    VALIDATOR="/usr/bin/rq_demo_validate.sh"
    GENERATOR="/usr/bin/rq_demo_generate_menu.sh"
else
    _repo_root="$(dirname "$SCRIPT_DIR")"
    REGISTRY_FILE="$_repo_root/RQB2-config/known-demos.json"
    CACHE_FILE="$_repo_root/RQB2-config/demo-menu-cache.sh"
    VALIDATOR="$SCRIPT_DIR/rq_demo_validate.sh"
    GENERATOR="$SCRIPT_DIR/rq_demo_generate_menu.sh"
fi

USER_MANIFEST_DIR="$USER_HOME/.local/config/demo-manifests"
DEMOS_ROOT="$USER_HOME/$REPO/demos"

# ============================================================================
# HELPERS
# ============================================================================

check_prereqs() {
    command -v jq  >/dev/null 2>&1 || die "jq is required but not installed"
    command -v git >/dev/null 2>&1 || die "git is required but not installed"
    [ -f "$REGISTRY_FILE" ] || die "Registry not found: $REGISTRY_FILE"
    jq empty "$REGISTRY_FILE" 2>/dev/null || die "Registry is not valid JSON: $REGISTRY_FILE"
}

# Read a field for a registry entry by id. Echoes empty if absent.
registry_field() {
    local id="$1" field="$2"
    jq -r --arg id "$id" --arg f "$field" \
        '.demos[] | select(.id == $id) | .[$f] // empty' "$REGISTRY_FILE"
}

# Does the registry contain this id?
registry_has() {
    local id="$1"
    [ -n "$(jq -r --arg id "$id" '.demos[] | select(.id == $id) | .id' "$REGISTRY_FILE")" ]
}

# All registry ids (one per line)
registry_ids() {
    jq -r '.demos[].id' "$REGISTRY_FILE"
}

# Is a demo already installed (user manifest present)?
is_installed() {
    local id="$1"
    [ -f "$USER_MANIFEST_DIR/rq_demo_${id}.json" ]
}

# Repo directory name for an entry (basename of repo_url, without .git)
repo_dir_name() {
    local url="$1" base
    base=$(basename "$url")
    echo "${base%.git}"
}

# Chown a path tree to the target user when running as root
chown_to_user() {
    local target="$1" owner
    if [ "$(id -u)" = "0" ]; then
        owner=$(get_user_name)
        [ "$owner" != "root" ] && [ -e "$target" ] && chown -R "$owner:$owner" "$target"
    fi
    return 0
}

# Regenerate the demo menu cache so the new demo appears in the menu.
# Install the demo's Python requirements into the user venv without touching
# packages the image already provides. rq_pip_extras.py (run with the venv
# interpreter, as the user) splits requirements.txt into extras.txt (missing
# distributions) and constraints.txt (every installed one, ==-pinned); pip then
# installs the extras under those constraints. Root-owned files left in the
# venv by root-run LED demos are repaired first, since user pip cannot replace
# them. Returns non-zero, after showing the pip output, on any failure.
install_pip_extras() {
    local id="$1" dest="$2"
    local venv_path splitter work log rc

    if ! venv_path=$(find_venv "$STD_VENV"); then
        warn "Virtual environment not found - cannot install Python requirements"
        return 1
    fi
    if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
        splitter="/usr/bin/rq_pip_extras.py"
    else
        splitter="$SCRIPT_DIR/rq_pip_extras.py"
    fi
    [ -f "$splitter" ] || { warn "Missing helper: $splitter"; return 1; }

    # Root-run demos leave root-owned __pycache__ in the user venv (#285).
    # fix_root_ownership only acts when the top directory itself is root-owned,
    # which the venv never is, so hand the whole tree back to the user here.
    if [ "$(id -u)" = "0" ] && [ -n "$(find "$venv_path" -user root -print -quit 2>/dev/null)" ]; then
        info "Repairing root-owned files in the venv..."
        chown_to_user "$venv_path"
    fi

    work=$(mktemp -d /tmp/rq_ext_pip.XXXXXX)
    chmod 755 "$work"
    log="$work/pip.log"
    cp "$dest/requirements.txt" "$work/requirements.txt"
    chmod 644 "$work/requirements.txt"
    chown_to_user "$work"

    info "Resolving Python requirements against the venv..."
    if ! run_as_user "$venv_path/bin/python" "$splitter" "$work/requirements.txt" "$work" 2>&1 | tee "$log"; then
        show_msgbox "Requirements not installed" "Could not read requirements.txt for '$id':\n\n$(tail -n 8 "$log")"
        rm -rf "$work"
        return 1
    fi

    rc=0
    if [ -s "$work/extras.txt" ]; then
        info "Installing the packages the venv is missing (as user)..."
        # set -o pipefail: the pipeline's status is pip's, not tee's
        run_as_user "$venv_path/bin/pip" install -c "$work/constraints.txt" -r "$work/extras.txt" 2>&1 | tee -a "$log" || rc=$?
    else
        info "All Python requirements already present in the venv"
    fi

    if [ "$rc" -ne 0 ]; then
        show_msgbox "Requirements not installed" "pip failed for '$id' (exit $rc). The demo was NOT installed.\n\nLast lines:\n$(tail -n 10 "$log" | cut -c1-110)"
        rm -rf "$work"
        return 1
    fi
    rm -rf "$work"
    return 0
}

# Write ~/Desktop/rq-ext-<id>.desktop from the manifest when desktop.show is
# true (#287). Shipped demos keep their icons in desktop-bookmarks/.
write_desktop_entry() {
    local id="$1" manifest_file="$2" dest="$3"
    local writer out rc=0

    if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
        writer="/usr/bin/rq_demo_desktop_entry.sh"
    else
        writer="$SCRIPT_DIR/rq_demo_desktop_entry.sh"
    fi
    [ -x "$writer" ] || [ -f "$writer" ] || { warn "Missing helper: $writer"; return 1; }

    out="$USER_HOME/Desktop/rq-ext-${id}.desktop"
    bash "$writer" "$manifest_file" "$out" "$dest" || rc=$?
    case "$rc" in
        0) chown_to_user "$out" ;;
        3) rm -f "$out" ;;   # desktop.show false: make sure no stale icon remains
        *) warn "Could not write desktop entry for '$id' (exit $rc)"; return 1 ;;
    esac
    return 0
}

refresh_cache() {
    if [ -x "$GENERATOR" ]; then
        info "Refreshing demo menu cache..."
        "$GENERATOR" --cache "$CACHE_FILE" >/dev/null 2>&1 \
            || warn "Failed to refresh demo menu cache (regenerate manually)"
    else
        warn "Menu generator not found: $GENERATOR (menu cache not refreshed)"
    fi
}

# List registry entries with install status
list_registry() {
    local id
    echo "Registry: $REGISTRY_FILE"
    echo "----------------------------------------"
    if [ -z "$(registry_ids)" ]; then
        echo "(no external demos registered)"
        return 0
    fi
    while IFS= read -r id; do
        [ -z "$id" ] && continue
        if is_installed "$id"; then
            printf "  [installed] %s\n" "$id"
        else
            printf "  [available] %s\n" "$id"
        fi
    done < <(registry_ids)
}

# Interactive picker: registry entries not yet installed
pick_demo_interactive() {
    local id args=() count=0
    while IFS= read -r id; do
        [ -z "$id" ] && continue
        if ! is_installed "$id"; then
            local note
            note=$(registry_field "$id" "note")
            args+=("$id" "${note:-external demo}")
            count=$((count + 1))
        fi
    done < <(registry_ids)

    if [ "$count" -eq 0 ]; then
        show_msgbox "Add demo from catalog" "All registered external demos are already installed."
        return 1
    fi

    show_menu "Add demo from catalog" "Select a demo to install:" "${args[@]}"
}

# ============================================================================
# CORE: install / update one demo
# ============================================================================

# add_demo <id> <mode>  ; mode = install | update
add_demo() {
    local id="$1" mode="${2:-install}"
    local repo_url ref manifest_path repo_name dest manifest_file

    registry_has "$id" || die "Demo '$id' is not in the registry: $REGISTRY_FILE"

    repo_url=$(registry_field "$id" "repo_url")
    ref=$(registry_field "$id" "ref")
    manifest_path=$(registry_field "$id" "manifest_path")
    [ -n "$manifest_path" ] || manifest_path="rqb-demo.json"

    [ -n "$repo_url" ] || die "Registry entry '$id' has no repo_url"
    [ -n "$ref" ] || die "Registry entry '$id' has no ref (pinned SHA)"
    case "$repo_url" in
        https://*) : ;;
        *) die "Registry repo_url must be https:// : $repo_url" ;;
    esac

    repo_name=$(repo_dir_name "$repo_url")
    dest="$DEMOS_ROOT/$repo_name"

    if [ "$mode" = "install" ] && [ -d "$dest" ]; then
        die "Demo directory already exists: $dest (use --update to re-fetch)"
    fi

    # Third-party disclaimer - must come before anything destructive
    # (in update mode the existing checkout is removed below)
    if ! show_yesno "Third-party demo" \
        "'$id' is provided by an external contributor and is NOT part of the RasQberry project:\n\n$repo_url\n\nThe RasQberry team reviews and pins a specific version, but does not maintain this software and takes no responsibility for its content, behavior, or security. Install at your own risk.\n\nContinue?"; then
        info "Installation cancelled by user"
        return 1
    fi

    # Fresh checkout for both install and update (explicit, never git pull)
    if [ -d "$dest" ]; then
        info "Removing previous checkout: $dest"
        rm -rf "$dest"
    fi

    mkdir -p "$DEMOS_ROOT"
    chown_to_user "$DEMOS_ROOT"

    info "Fetching '$id' at pinned commit ${ref:0:12}..."
    fetch_pinned_repo "$repo_url" "$ref" "$dest"

    manifest_file="$dest/$manifest_path"
    [ -f "$manifest_file" ] || { rm -rf "$dest"; die "Manifest not found in checkout: $manifest_path"; }

    # Validate with the hardened external constraints
    info "Validating manifest against external constraints..."
    if ! "$VALIDATOR" --external "$manifest_file" >/tmp/rq_ext_validate.$$ 2>&1; then
        cat /tmp/rq_ext_validate.$$ >&2 || true
        rm -f /tmp/rq_ext_validate.$$
        rm -rf "$dest"
        die "Manifest failed external validation - demo '$id' not installed"
    fi
    rm -f /tmp/rq_ext_validate.$$

    # Manifest id must match the registry id
    local m_id m_wd m_marker m_leds
    m_id=$(jq -r '.id // empty' "$manifest_file")
    m_wd=$(jq -r '.entrypoint.working_dir // empty' "$manifest_file")
    m_marker=$(jq -r '.install.marker_file // empty' "$manifest_file")
    m_leds=$(jq -r '.needs_hw.leds // false' "$manifest_file")

    if [ "$m_id" != "$id" ]; then
        rm -rf "$dest"
        die "Manifest id '$m_id' does not match registry id '$id'"
    fi
    # working_dir must equal the repo directory name
    if [ "$m_wd" != "$repo_name" ]; then
        rm -rf "$dest"
        die "entrypoint.working_dir '$m_wd' must equal the repo directory name '$repo_name'"
    fi
    # marker_file must exist in the checkout (proves integrity)
    if [ -z "$m_marker" ] || [ ! -e "$dest/$m_marker" ]; then
        rm -rf "$dest"
        die "install.marker_file '$m_marker' not found in checkout - refusing to install"
    fi

    # LED demos run with root privileges - confirm explicitly
    if [ "$m_leds" = "true" ]; then
        if ! show_yesno "LED demo - root privileges" \
            "The demo '$id' drives the LED hardware and will run with root privileges.\n\nInstall and allow it to run as root?"; then
            rm -rf "$dest"
            info "Installation cancelled by user"
            return 1
        fi
    fi

    # Install pip requirements as the user, if declared. Only packages the
    # venv lacks are installed, everything already present is held at its
    # installed version, and a failure fails the whole install (#285).
    local pip_req
    pip_req=$(jq -r '.install.pip_requirements // false' "$manifest_file")
    if [ "$pip_req" = "true" ] && [ -f "$dest/requirements.txt" ]; then
        if ! install_pip_extras "$id" "$dest"; then
            rm -rf "$dest"
            die "Python requirements for '$id' could not be installed - demo not installed"
        fi
    fi

    # Copy the manifest into the user manifest directory (never /usr/config)
    mkdir -p "$USER_MANIFEST_DIR"
    cp "$manifest_file" "$USER_MANIFEST_DIR/rq_demo_${id}.json"
    chown_to_user "$USER_MANIFEST_DIR"
    chown_to_user "$dest"

    # Desktop icon, when the manifest asks for one (#287). Non-fatal: the demo
    # is fully usable from the menu without it.
    write_desktop_entry "$id" "$manifest_file" "$dest" || true

    refresh_cache

    if [ "$mode" = "update" ]; then
        info "Demo '$id' updated to pinned commit ${ref:0:12}"
        show_msgbox "Demo updated" "External demo '$id' updated successfully.\n\nPinned commit: ${ref:0:12}"
    else
        info "Demo '$id' installed successfully"
        show_msgbox "Demo installed" "External demo '$id' installed successfully.\n\nLaunch it from the Quantum Demos menu."
    fi
    return 0
}

# ============================================================================
# MAIN
# ============================================================================

usage() {
    cat << 'EOF'
Usage: rq_demo_add_external.sh [options] [id]

Install or update an external demo from the curated registry.

  (no args)          Interactive menu of registry demos not yet installed
  <id>               Install the demo with this registry id
  --update <id>      Re-fetch the current registry SHA for an installed demo
  --list             List registry entries with install status
  --help, -h         Show this help
EOF
}

main() {
    check_prereqs

    case "${1:-}" in
        --help|-h)
            usage
            exit 0
            ;;
        --list)
            list_registry
            exit 0
            ;;
        --update)
            [ -n "${2:-}" ] || die "--update requires a demo id"
            add_demo "$2" update
            ;;
        "")
            local id
            id=$(pick_demo_interactive) || exit 0
            [ -n "$id" ] || exit 0
            add_demo "$id" install
            ;;
        -*)
            die "Unknown option: $1"
            ;;
        *)
            add_demo "$1" install
            ;;
    esac
}

main "$@"
