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
#   rq_demo_add_external.sh --remove <id>   # uninstall (checkout, manifest, icon)
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

# One menu line of at most MAX characters: whiptail cuts what is wider at
# the right edge, so a longer text ends at a word, with "..." (#23)
# Usage: fit_line TEXT [MAX]
fit_line() {
    local text="$1" max="${2:-66}"
    if [ "${#text}" -le "$max" ]; then
        printf '%s' "$text"
    else
        text="${text:0:$((max - 3))}"
        printf '%s...' "${text% *}"
    fi
}

# Picker text: "Name - summary" (one line of the menu), else the curator
# note. The note is maintainer prose, cut mid-word, so the two SAP entries
# looked the same (R-105).
registry_label() {
    local id="$1" name summary
    name=$(registry_field "$id" "name")
    summary=$(registry_field "$id" "summary")
    [ -n "$summary" ] || summary=$(registry_field "$id" "note")
    [ "$(registry_field "$id" "maturity")" = "beta" ] && name="${name:-$id} (beta)"
    fit_line "${name:-$id}${summary:+ - $summary}"
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
    local venv_path splitter work log rc label

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
        label=$(registry_field "$id" "name")
        show_msgbox "Demo not installed" "The Python packages that ${label:-$id} needs could not be installed, so the demo was not installed. Check the internet connection and the free space, then try again.\n\nThe last lines of the installer:\n$(tail -n 10 "$log" | cut -c1-110)"
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
    DESKTOP_ICON=0
    local writer out rc=0

    if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
        writer="/usr/bin/rq_demo_desktop_entry.sh"
    else
        writer="$SCRIPT_DIR/rq_demo_desktop_entry.sh"
    fi
    [ -x "$writer" ] || [ -f "$writer" ] || { warn "Missing helper: $writer"; return 1; }

    # pcmanfm parses a launcher on the create event and never re-reads it, so
    # a file that is written in place (empty at creation, root-owned until the
    # chown) stays labelled with its file name until the desktop is reloaded.
    # Write a hidden temp file in the same directory with the final owner and
    # mode, then rename it into place: one create event, complete content.
    out="$USER_HOME/Desktop/rq-ext-${id}.desktop"
    tmp="$USER_HOME/Desktop/.rq-ext-${id}.desktop.tmp"
    mkdir -p "$USER_HOME/Desktop"
    chown_to_user "$USER_HOME/Desktop"
    bash "$writer" "$manifest_file" "$tmp" "$dest" || rc=$?
    case "$rc" in
        0) chown_to_user "$tmp"; mv -f "$tmp" "$out"; DESKTOP_ICON=1; relayout_desktop ;;
        3) rm -f "$tmp" "$out" ;;   # desktop.show false: make sure no stale icon remains
        *) rm -f "$tmp"; warn "Could not write desktop entry for '$id' (exit $rc)"; return 1 ;;
    esac
    return 0
}

# The desktop lays the launchers out in its grid at every login; a catalogue
# launcher added or removed now joins it (or leaves a gap closed) at once,
# instead of landing apart at the bottom left (T5). Only with a running
# desktop; quiet and never fatal.
relayout_desktop() {
    local user uid run helper="$SCRIPT_DIR/rq_desktop_session.py"
    [ -f "$helper" ] || return 0
    user=$(stat -c %U "$USER_HOME" 2>/dev/null) || return 0
    uid=$(id -u "$user" 2>/dev/null) || return 0
    run="/run/user/$uid"
    [ -S "$run/wayland-0" ] || return 0
    if [ "$(id -u)" -eq 0 ] && [ "$user" != root ]; then
        sudo -u "$user" -H env XDG_RUNTIME_DIR="$run" WAYLAND_DISPLAY=wayland-0 \
            python3 "$helper" --relayout
    else
        env XDG_RUNTIME_DIR="$run" WAYLAND_DISPLAY=wayland-0 python3 "$helper" --relayout
    fi >/dev/null 2>&1 || true
}

refresh_cache() {
    if [ -x "$GENERATOR" ]; then
        info "Refreshing demo menu cache..."
        # The cache in /usr/config is root's: run as the user (--remove from a
        # terminal) the refresh failed and the removed demo stayed in the
        # menu (R-160)
        if [ -w "$CACHE_FILE" ] || { [ ! -e "$CACHE_FILE" ] && [ -w "$(dirname "$CACHE_FILE")" ]; }; then
            "$GENERATOR" --cache "$CACHE_FILE" >/dev/null 2>&1
        else
            sudo -n "$GENERATOR" --cache "$CACHE_FILE" >/dev/null 2>&1
        fi || warn "Failed to refresh demo menu cache (regenerate manually)"
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
            local label
            label=$(registry_label "$id")
            args+=("$id" "$label")
            count=$((count + 1))
        fi
    done < <(registry_ids)

    if [ "$count" -eq 0 ]; then
        show_msgbox "Add demo from catalogue" "All registered external demos are already installed."
        return 1
    fi

    # Without the ids in front, the text has the whole width (78 - 10)
    whiptail --title "Add demo from catalogue" --notags --ok-button Select --cancel-button Back \
        --menu "Select a demo to install:" 20 78 10 -- "${args[@]}" 3>&1 1>&2 2>&3
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

    if [ "$mode" = "install" ] && is_installed "$id"; then
        die "'$id' is already installed (use --update to fetch it again)"
    fi
    # A directory without an installed manifest is what a failed download
    # left behind; it blocked every later install (R-057). It is replaced
    # below, after the question.

    # Who provides it, with what the install takes - must come before
    # anything destructive (in update mode the existing checkout is removed
    # below). The provider comes from the registry: Jan's own traQmania was
    # "an external contributor ... NOT part of the RasQberry project" (R-163).
    local name summary provider dl disk size_txt=""
    name=$(registry_field "$id" "name")
    summary=$(registry_field "$id" "summary")
    provider=$(registry_field "$id" "provider")
    dl=$(jq -r --arg id "$id" '.demos[] | select(.id == $id) | .download.download_mb // empty' "$REGISTRY_FILE")
    disk=$(jq -r --arg id "$id" '.demos[] | select(.id == $id) | .download.disk_mb // empty' "$REGISTRY_FILE")
    # An LED demo runs as root: said in this one question, not a second one
    # that named the id (user test 2026-10-08, F5)
    local reg_leds root_txt=""
    reg_leds=$(jq -r --arg id "$id" '.demos[] | select(.id == $id) | .leds // false' "$REGISTRY_FILE")
    [ "$reg_leds" = true ] && root_txt="It drives the LED panel, so it runs with root privileges.\n\n"
    [ -n "$dl" ] && size_txt="Download: about $(rq_fmt_mb "$dl")${disk:+, $(rq_fmt_mb "$disk") on the SD card} (needs the internet). Free: $(rq_fmt_mb "$(rq_free_mb "$USER_HOME")").\n\n"
    if ! show_yesno "Demo from the Catalogue" \
        "${name:-$id}${summary:+: $summary}\n\n${size_txt}Provided by ${provider:-an external contributor}. From its own repository:\n$repo_url\n\nThe RasQberry team has reviewed this version and installs exactly it. Its makers maintain the demo and answer for its content and security.\n\n${root_txt}Install it?"; then
        # "No" is an answer, not an error: it ended in "It stopped with an
        # error" and an Error box (user test 2026-10-07, S3)
        info "Nothing was installed."
        return 0
    fi
    if [ -n "$disk" ] && [ "$(rq_free_mb "$USER_HOME")" -lt $((disk + RQ_SPACE_RESERVE_MB)) ]; then
        die "Not enough free space for '$id': it needs about $(rq_fmt_mb "$disk") plus $(rq_fmt_mb "$RQ_SPACE_RESERVE_MB") to spare. Remove demos you do not use (RasQberry menu: Quantum Demos > Manage demos > Remove a demo) and try again."
    fi
    rq_reachable "$repo_url" \
        || die "'$id' has to be downloaded, and github.com cannot be reached. Connect the Pi to the internet and try again."

    # Fresh checkout for both install and update (explicit, never git pull)
    if [ -e "$dest" ]; then
        info "Removing previous checkout: $dest"
        rq_remove_tree "$dest" || die "Cannot remove the previous checkout: $dest"
    fi

    mkdir -p "$DEMOS_ROOT"
    chown_to_user "$DEMOS_ROOT"

    info "Fetching '$id' at pinned commit ${ref:0:12}..."
    fetch_pinned_repo "$repo_url" "$ref" "$dest" \
        || die "Could not download '$id' from $repo_url. Check the internet connection and try again."

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

    # LED demos run with root privileges - confirm explicitly, unless the
    # install question already said so (registry "leds")
    if [ "$m_leds" = "true" ] && [ "$reg_leds" != true ]; then
        if ! show_yesno "LED demo - root privileges" \
            "${name:-$id} drives the LED panel and will run with root privileges.\n\nInstall it and let it run as root?"; then
            rm -rf "$dest"
            info "Nothing was installed."
            return 0
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

    # Copy the manifest into the user manifest directory (never /usr/config).
    # Created as the user: run as root from the menu, mkdir -p made
    # ~/.local/config root-owned, and user tools then failed there (R-161).
    run_as_user mkdir -p "$USER_MANIFEST_DIR" 2>/dev/null || mkdir -p "$USER_MANIFEST_DIR"
    # The registry's sizes go with it, for the first start's consent dialog
    local reg_download
    reg_download=$(jq -c --arg id "$id" '.demos[] | select(.id == $id) | .download // empty' "$REGISTRY_FILE")
    if [ -n "$reg_download" ]; then
        jq --argjson d "$reg_download" '.install.download = (.install.download // $d)' "$manifest_file" \
            > "$USER_MANIFEST_DIR/rq_demo_${id}.json"
    else
        cp "$manifest_file" "$USER_MANIFEST_DIR/rq_demo_${id}.json"
    fi
    chown_to_user "$USER_MANIFEST_DIR"
    chown_to_user "$USER_HOME/.local/config"
    chown_to_user "$dest"

    # Desktop icon, when the manifest asks for one (#287). Non-fatal: the demo
    # is fully usable from the menu without it.
    write_desktop_entry "$id" "$manifest_file" "$dest" || true

    refresh_cache

    # where it is: its group (demo-groups.json) in the menu and on the desktop
    local where="the Quantum Demos menu" m_image group_title
    group_title=$(jq -r --arg g "$(rq_demo_group "$id" "$USER_MANIFEST_DIR/rq_demo_${id}.json")" \
        '.groups[]? | select(.id == $g) | .title' "$(rq_shipped_manifest_dir)/demo-groups.json" 2>/dev/null)
    [ -n "$group_title" ] && where="the RasQberry menu (Quantum Demos > $group_title)"
    if [ "${DESKTOP_ICON:-0}" = 1 ]; then
        where="${group_title:+the $group_title folder on the desktop}"
        where="${where:-its desktop icon} or the RasQberry menu (Quantum Demos${group_title:+ > $group_title})"
    fi
    m_image=""
    [ "$(jq -r '.entrypoint.type // empty' "$manifest_file")" = "docker" ] \
        && m_image=$(jq -r '.entrypoint.docker_image // empty' "$manifest_file")
    if [ "$mode" = "update" ]; then
        info "Demo '$id' updated to pinned commit ${ref:0:12}"
        show_msgbox "Demo updated" "External demo '$id' updated successfully.\n\nPinned commit: ${ref:0:12}"
    elif [ -n "$m_image" ] && ! { command -v docker >/dev/null 2>&1 \
            && docker image inspect "$m_image" >/dev/null 2>&1; }; then
        # Its Docker image comes on the first start, after its own question:
        # "installed successfully" and then a 530 MB download read like a
        # second install (#23)
        info "Demo '$id' registered; its Docker image downloads on its first start"
        show_msgbox "Demo added" "Registered: ${name:-$id}. On its first start it downloads its Docker image${dl:+, about $(rq_fmt_mb "$dl")}.\n\nStart it from $where."
    else
        info "Demo '$id' installed successfully"
        show_msgbox "Demo added" "${name:-$id} is installed.\n\nStart it from $where."
    fi
    return 0
}

# remove_demo <id> - uninstall a catalog demo: checkout, user manifest,
# desktop icon, menu entry. Works from the installed manifest, so it also
# removes demos that have since been withdrawn from the registry. Python
# packages installed as extras stay in the venv (other demos may use them).
remove_demo() {
    local id="$1" manifest dir

    manifest="$USER_MANIFEST_DIR/rq_demo_${id}.json"
    [ -f "$manifest" ] || die "Demo '$id' is not installed (no $manifest)"

    dir=$(jq -r '.entrypoint.working_dir // empty' "$manifest")
    [ -n "$dir" ] || dir=$(repo_dir_name "$(jq -r '.install.repo_url // empty' "$manifest")")
    # Only ever a single directory name below DEMOS_ROOT
    case "$dir" in
        ""|.|..|*/*) die "Cannot determine the checkout directory for '$id' (got '$dir')" ;;
    esac

    local image="" name
    name=$(jq -r '.name // .id // empty' "$manifest")
    [ "$(jq -r '.entrypoint.type // empty' "$manifest")" = "docker" ] \
        && image=$(jq -r '.entrypoint.docker_image // empty' "$manifest")

    if [ -d "$DEMOS_ROOT/$dir" ]; then
        info "Removing checkout: $DEMOS_ROOT/$dir"
        rq_remove_tree "${DEMOS_ROOT:?}/$dir" || die "Could not remove $DEMOS_ROOT/$dir"
    fi
    # the launcher: on the desktop, in its group's folder (rq_desktop_session.py)
    # or in the More folder of older desktops
    rm -f "$manifest" "$USER_HOME/Desktop/rq-ext-${id}.desktop" "$USER_HOME/Desktop/More/rq-ext-${id}.desktop" \
        "$USER_HOME"/.local/share/rasqberry/desktop-groups/*/"rq-ext-${id}.desktop"
    relayout_desktop
    refresh_cache

    # Its Docker image is most of the space (traQmania: 3.2 GB) and stayed
    # behind (R-160)
    if [ -n "$image" ] && command -v docker >/dev/null 2>&1 \
        && docker image inspect "$image" >/dev/null 2>&1; then
        local mb
        mb=$(docker image inspect -f '{{.Size}}' "$image" 2>/dev/null | awk '{ printf "%d", $1 / 1000000 }')
        if [ "${RQ_ASSUME_YES:-no}" = yes ] || { [ -t 0 ] && show_yesno "Remove the Docker image?" \
                "Also remove the Docker image of '$id' ($image, about $(rq_fmt_mb "${mb:-0}"))?"; }; then
            docker rmi "$image" >/dev/null && info "Removed the Docker image $image" \
                || warn "Could not remove the Docker image $image (is the demo still running?)"
        else
            info "Kept the Docker image $image (remove it with: docker rmi $image)"
        fi
    fi
    info "Demo '$id' removed"
    # Back in the menu without a word looked like nothing happened (#23)
    if [ "${RQ_ASSUME_YES:-no}" != yes ] && [ -t 0 ] && [ -t 1 ]; then
        show_msgbox "Demo removed" "${name:-$id} was removed. Free space now: $(rq_fmt_mb "$(rq_free_mb "$USER_HOME")")."
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
  --remove <id>      Uninstall a catalogue demo (also one withdrawn from the registry)
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
        --remove)
            [ -n "${2:-}" ] || die "--remove requires a demo id"
            remove_demo "$2"
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
