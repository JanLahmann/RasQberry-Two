#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Remove a demo (free space)
# ============================================================================
# Description: Removes a downloaded demo - its checkout and its Docker image -
#   to free space on the SD card. It downloads again (after asking) when it is
#   next started. Catalogue demos are removed with rq_demo_add_external.sh
#   --remove. There used to be no way to free the space a demo took except
#   docker rmi and rm -rf over SSH (R-047, R-160).
# Usage: rq_demo_remove.sh               pick a demo (shows what each takes)
#        rq_demo_remove.sh ID [--yes]    remove one demo (--yes: do not ask)
#        rq_demo_remove.sh --list        downloaded demos and their sizes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

rq_help_guard "$@"
load_rqb2_env
verify_env_vars REPO USER_HOME

SHIPPED_DIR=$(rq_shipped_manifest_dir)
USER_MANIFEST_DIR=$(rq_user_manifest_dir || true)
DEMOS_ROOT="$USER_HOME/$REPO/demos"

docker_ok() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}
DOCKER_OK=no
docker_ok && DOCKER_OK=yes

# Fields of a manifest, separated by \037:
# id name type image working_dir installed_flag shares preinstalled
fields() {
    jq -r '[.id, (.name // .id), (.entrypoint.type // ""), (.entrypoint.docker_image // ""),
            (.entrypoint.working_dir // ""), (.install.installed_flag // ""),
            (.install.download.shares // ""), (.install.preinstalled // false | tostring)]
           | join("\u001f")' "$1"
}

# MB a checkout takes (0 if absent), at least 1: Quantum Lights Out (250 KB)
# was listed as "0 MB" and "frees about 0 MB" (user test 2026-10-07)
dir_mb() {
    [ -n "$1" ] && [ -d "$DEMOS_ROOT/$1" ] || { echo 0; return 0; }
    du -sk "$DEMOS_ROOT/$1" 2>/dev/null \
        | awk '{ n = $1 * 1024 / 1000000; printf "%d\n", (n < 1 ? 1 : n + 0.5) }'
}

# MB a Docker image takes (0 if absent). Always one number and status 0: a
# missing image made the pipeline fail under pipefail, the caller's
# "|| echo 0" added a second 0, and "0 + 0\n0" ended the whole list at the
# first Docker demo not downloaded (Quantum Lab, N2).
image_mb() {
    local bytes
    [ -n "$1" ] && [ "$DOCKER_OK" = yes ] || { echo 0; return 0; }
    bytes=$(docker image inspect -f '{{.Size}}' "$1" 2>/dev/null) || bytes=0
    case "$bytes" in ''|*[!0-9]*) bytes=0 ;; esac
    echo $(( bytes / 1000000 ))
}

# MB a demo takes on the card: its checkout, and its image for a Docker demo
# Usage: demo_mb TYPE WORKING_DIR IMAGE
demo_mb() {
    local mb
    mb=$(dir_mb "$2")
    [ "$1" = docker ] && mb=$(( mb + $(image_mb "$3") ))
    echo "$mb"
}

# Downloaded demos: "id<TAB>MB<TAB>label" lines. Demos that share a download
# (the IBM tutorials and courses) are one entry. A demo whose lookup fails
# is left out, not the rest of the list with it (N2: the list stopped at
# Quantum Lab, and the catalogue demos after it could not be removed).
list_downloaded() {
    local mf line shares seen=" "
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        line=$(downloaded_entry "$mf") || continue
        [ -n "$line" ] || continue
        shares=${line%%$'\t'*}
        if [ -n "$shares" ]; then
            case "$seen" in *" $shares "*) continue ;; esac
            seen="$seen$shares "
        fi
        printf '%s\n' "${line#*$'\t'}"
    done < <(rq_list_manifests "$SHIPPED_DIR" 2>/dev/null)
}

# One manifest: "shares<TAB>id<TAB>MB<TAB>label" when the demo is downloaded,
# nothing otherwise
downloaded_entry() {
    local id name type image wd flag shares pre mb label other
    IFS=$'\037' read -r id name type image wd flag shares pre <<< "$(fields "$1")"
    [ -n "$id" ] || return 1
    [ "$pre" = "true" ] && return 0
    [ -n "$image" ] && image=$(rq_demo_image "$id" "$1")   # the version in use
    mb=$(demo_mb "$type" "$wd" "$image") || return 1
    [ "$mb" -gt 0 ] || [ -d "$DEMOS_ROOT/${wd:-/nonexistent}" ] || return 0
    label="$name"
    if [ -n "$shares" ]; then
        other=$(sharing_names "$shares" "$id")
        [ -n "$other" ] && label="$name + $other"
    fi
    printf '%s\t%s\t%s\t%s\n' "$shares" "$id" "$mb" "$label"
}

# Names of the other demos with the same download
sharing_names() {
    local want="$1" self="$2" mf id name s out=""
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        IFS=$'\037' read -r id name s <<< "$(jq -r '[.id, (.name // .id), (.install.download.shares // "")] | join("\u001f")' "$mf")"
        [ "$s" = "$want" ] && [ "$id" != "$self" ] && out="${out:+$out + }$name"
    done < <(rq_list_manifests "$SHIPPED_DIR" 2>/dev/null)
    echo "$out"
}

is_catalog() {
    [ -n "$USER_MANIFEST_DIR" ] && [ -f "$USER_MANIFEST_DIR/rq_demo_$1.json" ] \
        && ! [ -f "$SHIPPED_DIR/rq_demo_$1.json" ]
}

remove_demo() {
    local id="$1" assume_yes="$2" mf id_ name type image wd flag shares pre mb
    mf=$(rq_find_manifest "$SHIPPED_DIR" "$id") || die "Unknown demo: $id"

    IFS=$'\037' read -r id_ name type image wd flag shares pre <<< "$(fields "$mf")"
    [ -n "$image" ] && image=$(rq_demo_image "$id" "$mf")   # the version in use

    if is_catalog "$id"; then
        if [ "$assume_yes" != yes ]; then
            show_yesno "Remove $name?" "Remove the catalogue demo $name (its files, icon and menu entry)?" \
                || { info "Nothing removed."; return 0; }
        fi
        RQ_ASSUME_YES="$assume_yes" exec "$SCRIPT_DIR/rq_demo_add_external.sh" --remove "$id"
    fi

    [ "$pre" != "true" ] || die "$name is part of the system image and cannot be removed."
    mb=$(demo_mb "$type" "$wd" "$image")
    [ "$mb" -gt 0 ] || [ -d "$DEMOS_ROOT/${wd:-/nonexistent}" ] || die "$name is not downloaded."

    local also=""
    [ -n "$shares" ] && also=$(sharing_names "$shares" "$id")
    if [ "$assume_yes" != yes ]; then
        show_yesno "Remove $name?" "Remove ${name}${also:+ and $also}? This frees about $(rq_fmt_mb "$mb").\n\nIt downloads again (after asking) the next time it is started." \
            || { info "Nothing removed."; return 0; }
    fi

    # The checkout. A Qoffee-Maker checkout holds the user's settings (.env)
    # and is small: it stays, only its image goes.
    if [ -n "$wd" ] && [ -d "$DEMOS_ROOT/$wd" ]; then
        case "$wd" in */*|.|..) die "Unexpected demo directory: $wd" ;; esac
        if [ "$type" = docker ] && [ -f "$DEMOS_ROOT/$wd/.env" ]; then
            info "Keeping $DEMOS_ROOT/$wd (it holds your settings)"
        else
            info "Removing $DEMOS_ROOT/$wd"
            rq_remove_tree "$DEMOS_ROOT/$wd" || die "Could not remove $DEMOS_ROOT/$wd"
        fi
    fi
    # A Docker demo built from source keeps its source checkout under its id
    if [ "$type" = docker ] && [ -z "$wd" ] && [ -d "$DEMOS_ROOT/$id" ]; then
        rq_remove_tree "$DEMOS_ROOT/$id" || warn "Could not remove $DEMOS_ROOT/$id"
    fi
    if [ "$type" = docker ] && [ -n "$image" ] && [ "$DOCKER_OK" = yes ] \
        && docker image inspect "$image" >/dev/null 2>&1; then
        info "Removing the Docker image $image"
        # a stopped container kept for its log would block the removal
        docker ps -aq --filter "ancestor=$image" --filter status=exited --filter status=created \
            | xargs -r docker rm >/dev/null 2>&1 || true
        docker rmi "$image" >/dev/null || warn "Could not remove the Docker image $image (is the demo still running?)"
        docker builder prune -f >/dev/null 2>&1 || true
    fi

    # Its installed flag, and those of the demos that shared the download
    local f
    for f in $(installed_flags "$flag" "$shares"); do
        update_env_var "$f" "false" >/dev/null || true
    done
    info "$name removed."
    if [ "$assume_yes" != yes ]; then
        show_msgbox "Demo removed" "$name was removed. Free space now: $(rq_fmt_mb "$(rq_free_mb "$USER_HOME")")."
    fi
}

installed_flags() {
    local flag="$1" shares="$2" mf
    [ -n "$flag" ] && echo "$flag"
    [ -n "$shares" ] || return 0
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        jq -r --arg s "$shares" 'select(.install.download.shares == $s) | .install.installed_flag // empty' "$mf"
    done < <(rq_list_manifests "$SHIPPED_DIR" 2>/dev/null)
}

pick() {
    local args=() id mb label
    while IFS=$'\t' read -r id mb label; do
        [ -n "$id" ] || continue
        args+=("$id" "$(printf '%-44s %8s' "$label" "$(rq_fmt_mb "$mb")")")
    done < <(list_downloaded)
    if [ "${#args[@]}" -eq 0 ]; then
        show_msgbox "Remove a demo" "No downloaded demos to remove."
        return 1
    fi
    whiptail --title "Remove a demo" --notags --ok-button Remove --cancel-button Back \
        --menu "Free space: $(rq_fmt_mb "$(rq_free_mb "$USER_HOME")"). Removed demos download again when started." \
        20 72 10 -- "${args[@]}" 3>&1 1>&2 2>&3
}

case "${1:-}" in
    --list)
        list_downloaded
        ;;
    "")
        id=$(pick) || exit 0
        [ -n "$id" ] || exit 0
        remove_demo "$id" no
        ;;
    -*)
        die "Unknown option: $1 (see --help)"
        ;;
    *)
        remove_demo "$1" "$([ "${2:-}" = "--yes" ] && echo yes || echo no)"
        ;;
esac
