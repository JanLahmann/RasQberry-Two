#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Update demos
# ============================================================================
# Description: Every demo is pinned per RasQberry release (a git commit or a
#   Docker image digest, Jan Q8/Q32). This moves a downloaded demo to a newer
#   upstream version on request, after the usual download dialog:
#   - a Docker demo to a newer image build on ghcr.io: the latest and the
#     versions in between, with date, size and Qiskit version;
#   - a notebook demo to a newer commit of its upstream repository (the
#     earlier copy, with any changes made to it, is kept next to it).
#   "Back to the release version" undoes it. A newer RasQberry release
#   brings its own tested pins, and those win.
# Usage: rq_demo_update.sh [--list]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

TITLE="Update demos"
SHIPPED="$(rq_shipped_manifest_dir)"
DOCKER_OK=no
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && DOCKER_OK=yes

# Updatable pins of downloaded demos: "KEY<TAB>NAME<TAB>MANIFEST" lines,
# KEY = ID:image or ID:ref
updatable() {
    local mf id name type image ref wd
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        id=$(jq -r '.id' "$mf")
        name=$(jq -r '.name // .id' "$mf")
        type=$(jq -r '.entrypoint.type // ""' "$mf")
        image=$(rq_demo_image "$id" "$mf")
        # downloaded: the version in use or the release version is here
        if [ "$type" = "docker" ] && [ -n "$image" ] && [ "$DOCKER_OK" = yes ] \
                && { docker image inspect "$image" >/dev/null 2>&1 \
                     || docker image inspect "$(release_pin "$id:image" "$mf")" >/dev/null 2>&1; } \
                && jq -e '.install.update.docker_tags' "$mf" >/dev/null 2>&1; then
            printf '%s:image\t%s\t%s\n' "$id" "$name" "$mf"
        fi
        ref=$(rq_demo_ref "$id" "$mf")
        wd=$(jq -r '.entrypoint.working_dir // ""' "$mf")
        if [ -n "$ref" ] && [ -n "$wd" ] && [ -d "$USER_HOME/$REPO/demos/$wd/.git" ]; then
            printf '%s:ref\t%s\t%s\n' "$id" "$name" "$mf"
        fi
    done < <(rq_list_manifests "$SHIPPED" 2>/dev/null)
}

release_pin() {   # KEY MANIFEST
    case "$1" in
        *:image) jq -r '.entrypoint.docker_image // empty' "$2" ;;
        *)       jq -r '.install.ref // .install.source.ref // empty' "$2" ;;
    esac
}

# The version in use: the image the demo runs, or the commit its checkout is
# at (an older RasQberry may have cloned it unpinned)
current_pin() {   # KEY MANIFEST
    local wd head=""
    case "$1" in
        *:image) rq_demo_image "${1%:*}" "$2" ;;
        *)
            wd=$(jq -r '.entrypoint.working_dir // ""' "$2")
            [ -n "$wd" ] && head=$(git -C "$USER_HOME/$REPO/demos/$wd" rev-parse HEAD 2>/dev/null) || head=""
            [ -n "$head" ] && echo "$head" || rq_demo_ref "${1%:*}" "$2" ;;
    esac
}

state_text() {    # KEY MANIFEST
    local cur
    cur=$(current_pin "$1" "$2")
    if [ "$cur" = "$(release_pin "$1" "$2")" ]; then
        echo "release version"
    elif [ "$cur" = "$(_rq_demo_chosen "$1" "$(release_pin "$1" "$2")" || true)" ]; then
        echo "newer: $(rq_demo_chosen_label "$1" || echo chosen)"
    else
        echo "other version (${cur:0:7})"
    fi
}

if [ "${1:-}" = "--list" ]; then
    updatable | while IFS=$'\t' read -r key name mf; do
        printf '%s\t%s\t%s\n' "$key" "$(current_pin "$key" "$mf")" "$(state_text "$key" "$mf")"
    done
    exit 0
fi

# ----------------------------------------------------------------------------
# Docker image
# ----------------------------------------------------------------------------
update_image() {
    local key="$1" name="$2" mf="$3" id="${1%:*}" cur rel tags latest out rc=0
    cur=$(current_pin "$key" "$mf")
    rel=$(release_pin "$key" "$mf")
    tags=$(jq -r '.install.update.docker_tags' "$mf")
    latest=$(jq -r '.install.update.docker_latest // ""' "$mf")

    show_infobox "$TITLE" "Looking for newer versions of $name on ghcr.io..."
    out=$(python3 "$BIN_DIR/rq_image_versions.py" "$cur" --tags "$tags" --latest "$latest" 2>&1) || rc=$?
    if [ "$rc" -ne 0 ]; then
        show_msgbox "$TITLE" "The versions of $name could not be listed:\n\n$out"
        return 0
    fi

    set --
    local line ref t date mb note state cur_line=""
    while IFS=$'\t' read -r ref t date mb note state; do
        [ -n "$ref" ] || continue
        if [ "$state" = current ]; then
            cur_line="$date  $t  ($note)"
            continue
        fi
        set -- "$@" "$ref" "$date  ${t}  ~${mb} MB  ${note}"
    done <<< "$out"
    [ "$cur" != "$rel" ] && set -- "$@" "RELEASE" "Back to the version this release ships"
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "$name is up to date.\n\nIn use: $cur_line"
        return 0
    fi

    local choice
    choice=$(whiptail --title "$TITLE: $name" --menu \
        "In use: $cur_line\nNewest first. The new version is used from the next start." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || return 0

    local target="$choice" label="" dl=0 disk=0
    if [ "$choice" = "RELEASE" ]; then
        target="$rel"
        label=""
    else
        line=$(grep -F "$choice" <<< "$out" | head -1)
        IFS=$'\t' read -r ref t date mb note state <<< "$line"
        label="$t, $date"
        dl="$mb"
        disk=$(jq -r --argjson dl "$mb" \
            '(.install.download.disk_mb // 0) as $d | (.install.download.download_mb // 0) as $m
             | if $m > 0 then ($dl * $d / $m | floor) else $dl end' "$mf")
    fi

    if ! docker image inspect "$target" >/dev/null 2>&1; then
        rc=0
        rq_confirm_download "$name" "$dl" "$disk" --path /var/lib/docker \
            --url "https://ghcr.io/v2/" --time "5-20 minutes" \
            --title "Update $name?" \
            --intro "$name: ${label:-the version this release ships}." \
            --question "Download it now? The version in use is removed afterwards." || rc=$?
        case "$rc" in
            0) ;;
            1) return 0 ;;
            *) show_msgbox "$TITLE" "$RQ_CONSENT_MSG"; return 0 ;;
        esac
        rq_docker_access
        ( rq_docker_pull "$target" "$name" "$dl" ) || { show_msgbox "$TITLE" "$name was not updated: the download failed."; return 0; }
    fi
    if [ "$target" = "$rel" ]; then
        rq_demo_set_version "$key" "$rel" ""
    else
        rq_demo_set_version "$key" "$rel" "$target" "$label"
    fi
    rq_docker_drop_old "$target"
    show_msgbox "$TITLE" "$name now uses: ${label:-the version this release ships}.\n\nIt is used the next time $name starts (a running one keeps its version until then)."
}

# ----------------------------------------------------------------------------
# Git checkout
# ----------------------------------------------------------------------------
update_ref() {
    local key="$1" name="$2" mf="$3" id="${1%:*}" cur rel url wd demo_dir head slug api rc=0
    cur=$(current_pin "$key" "$mf")
    rel=$(release_pin "$key" "$mf")
    url=$(rq_demo_repo "$id" "$mf")
    wd=$(jq -r '.entrypoint.working_dir' "$mf")
    demo_dir="$USER_HOME/$REPO/demos/$wd"

    show_infobox "$TITLE" "Looking for newer versions of $name on GitHub..."
    head=$(git ls-remote "$url" HEAD 2>/dev/null | cut -f1) || head=""
    [ -n "$head" ] || { show_msgbox "$TITLE" "GitHub cannot be reached, so $name cannot be updated now."; return 0; }

    # The newer commits, newest first (GitHub API; without it only the newest)
    set --
    slug=$(printf '%s' "$url" | sed -n 's#^https://github.com/\([^/]*/[^/.]*\).*#\1#p')
    if [ "$head" != "$cur" ] && [ -n "$slug" ]; then
        api=$(curl -s --max-time 15 "https://api.github.com/repos/$slug/compare/$cur...$head" 2>/dev/null) || api=""
        while IFS=$'\t' read -r sha date msg; do
            [ -n "$sha" ] && set -- "$@" "$sha" "${date:0:10}  ${sha:0:7}  ${msg:0:50}"
        done < <(jq -r '.commits // [] | reverse | .[:10][]
                 | [.sha, .commit.committer.date, (.commit.message | split("\n")[0])] | @tsv' <<< "$api" 2>/dev/null)
        [ $# -gt 0 ] || set -- "$head" "Newest version (${head:0:7})"
    fi
    [ "$cur" != "$rel" ] && set -- "$@" "RELEASE" "Back to the version this release ships"
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "$name is up to date (${cur:0:7})."
        return 0
    fi

    local choice target label
    choice=$(whiptail --title "$TITLE: $name" --menu \
        "In use: ${cur:0:7}. Newest first.\nYour changes to its files are kept in a copy next to it." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || return 0
    if [ "$choice" = "RELEASE" ]; then
        target="$rel"; label=""
    else
        target="$choice"; label="${choice:0:7}"
    fi

    local backup="$demo_dir.before-update"
    rq_remove_tree "$backup" || { show_msgbox "$TITLE" "An old copy is in the way: $backup"; return 0; }
    mv "$demo_dir" "$backup"
    if [ "$target" = "$rel" ]; then
        rq_demo_set_version "$key" "$rel" ""
    else
        rq_demo_set_version "$key" "$rel" "$target" "$label"
    fi

    # The engine installs the chosen commit with the demo's patch and setup
    # steps (no second download dialog)
    if RQ_CONFIRMED_DEMO="$id" "$BIN_DIR/rq_demo_run.sh" "$id" --install-only; then
        # Files the user added (own notebooks, a settings file) come along
        ( cd "$backup" && git ls-files --others -z 2>/dev/null ) \
            | while IFS= read -r -d '' f; do
                [ -e "$demo_dir/$f" ] && continue
                mkdir -p "$demo_dir/$(dirname "$f")"
                cp -p "$backup/$f" "$demo_dir/$f"
            done
        fix_root_ownership "$demo_dir" >/dev/null 2>&1 || true
        show_msgbox "$TITLE" "$name is now at ${label:-the version this release ships}.\n\nThe earlier copy is kept in:\n$backup"
    else
        rc=$?
        rq_remove_tree "$demo_dir" || true
        mv "$backup" "$demo_dir"
        rq_demo_set_version "$key" "$rel" "$( [ "$cur" = "$rel" ] || echo "$cur")" "$(rq_demo_chosen_label "$key" || true)"
        show_msgbox "$TITLE" "$name could not be updated (error $rc), so the version in use was put back."
    fi
}

# ----------------------------------------------------------------------------
# Menu
# ----------------------------------------------------------------------------
while true; do
    set --
    while IFS=$'\t' read -r key name mf; do
        [ -n "$key" ] || continue
        # what an update brings: only the notebook demos are notebooks (#31)
        case "$key" in
            *:image) kind="Docker image" ;;
            *) if [ "$(jq -r '.entrypoint.type // ""' "$mf")" = "jupyter" ]; then
                   kind="notebooks"
               else
                   kind="program"
               fi ;;
        esac
        set -- "$@" "$key" "$name ($kind): $(state_text "$key" "$mf")"
    done < <(updatable)
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "No downloaded demo can be updated.\n\nDemos are downloaded the first time they start."
        exit 0
    fi
    pick=$(whiptail --title "$TITLE" --menu \
        "Each RasQberry Two release pins tested demo versions. Choose a demo to look for a newer version." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || exit 0
    line=$(updatable | awk -F'\t' -v k="$pick" '$1 == k')
    IFS=$'\t' read -r key name mf <<< "$line"
    case "$key" in
        *:image) update_image "$key" "$name" "$mf" ;;
        *:ref)   update_ref "$key" "$name" "$mf" ;;
    esac
done
