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
#   --tested ID:image|ID:ref installs the tested update the demo catalogue
#   offers for this Pi (rq_catalogue.py, "tested_updates"; the taskbar badge
#   runs it).
# Usage: rq_demo_update.sh [--list | --tested ID:KIND]

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
# KEY = ID:image or ID:ref. Demos that share one checkout (the IBM pair:
# ibm-quantum-learning) are one line under the first one's id, named after
# all of them: one version for both.
updatable() {
    local mf id name type image ref wd other seen=" "
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
        if [ -n "$ref" ] && [ -n "$wd" ] && [ "${seen#* "$wd" }" = "$seen" ] \
                && [ -d "$USER_HOME/$REPO/demos/$wd/.git" ]; then
            seen="$seen$wd "
            for other in $(sharers "$wd" "$id"); do
                name=$(join_names "$name" "$(jq -r '.name // .id' "$(rq_find_manifest "$SHIPPED" "$other")")")
            done
            printf '%s:ref\t%s\t%s\n' "$id" "$name" "$mf"
        fi
    done < <(rq_list_manifests "$SHIPPED" 2>/dev/null)
}

# "A and B" without the words they start with twice: "IBM Quantum Courses
# and Tutorials" (it was cut off at 80 columns, user test 2026-10-26)
join_names() {    # A B
    local a="$1" b="$2" rest_a rest_b
    rest_a="$a"; rest_b="$b"
    while [[ "$rest_a" == *" "* ]] && [[ "$rest_b" == *" "* ]] \
            && [ "${rest_a%% *}" = "${rest_b%% *}" ]; do
        rest_a="${rest_a#* }"; rest_b="${rest_b#* }"
    done
    echo "$a and $rest_b"
}

# The other shipped demos with the checkout WD (their ids, one per line)
sharers() {       # WD ID
    local mf
    while IFS= read -r mf; do
        [ -n "$mf" ] || continue
        jq -r --arg wd "$1" --arg id "$2" \
            'select(.entrypoint.working_dir == $wd and .id != $id) | .id' "$mf" 2>/dev/null
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

# A version's label for the user ("tested: " marks it for rq_catalogue.py only)
shown_label() {   # LABEL
    local l="${1#tested: }"
    echo "${l:-the version this release ships}"
}

state_text() {    # KEY MANIFEST
    local cur
    cur=$(current_pin "$1" "$2")
    if [ "$cur" = "$(release_pin "$1" "$2")" ]; then
        echo "as released"
    elif [ "$cur" = "$(_rq_demo_chosen "$1" "$(release_pin "$1" "$2")" || true)" ]; then
        echo "newer: $(shown_label "$(rq_demo_chosen_label "$1" || echo chosen)")"
    else
        echo "other version (${cur:0:7})"
    fi
}

# --- menu texts (user test 2026-10-26: technical tags, full SHAs and digests
# glued to the date, texts cut off at 80 columns) ---------------------------

# A menu line that fits an 80-column window (whiptail --notags, 78 wide)
fit() {           # TEXT [MAX]
    local t="$1" n="${2:-68}"
    if [ "${#t}" -gt "$n" ]; then printf '%s...\n' "${t:0:$((n - 3))}"; else printf '%s\n' "$t"; fi
}

# A short name for an image version: a tag such as 2.5-xl-20261008, else
# the first 7 characters of a commit tag or of the digest
short_id() {      # TAGS IMAGE_REF
    local t hex="" d
    local -a tags=()
    IFS=',' read -ra tags <<< "$1"
    for t in ${tags[@]+"${tags[@]}"}; do
        t="${t# }"
        case "$t" in -|""|*"(latest)") continue ;; esac
        if [[ "$t" =~ ^[0-9a-f]{12,}$ ]]; then
            [ -n "$hex" ] || hex="${t:0:7}"
            continue
        fi
        echo "$t"
        return 0
    done
    [ -n "$hex" ] && { echo "$hex"; return 0; }
    d="${2##*sha256:}"
    echo "${d:0:7}"
}

# One version in a picker: date, short id, size, marks, what is in it
version_item() { # DATE SHORT_ID MB MARKS NOTE
    local text="$1  $2"
    [ "${3:-0}" -gt 0 ] 2>/dev/null && text="$text  ~$3 MB"
    [ -n "$4" ] && text="$text  $4"
    [ -n "$5" ] && [ "$5" != "-" ] && text="$text  $5"
    fit "$text"
}
# --- end of menu texts ---

# The tested version the demo catalogue offers for KEY (nothing if none)
tested_pin() {    # KEY
    RQ_USER_HOME="$USER_HOME" python3 "$BIN_DIR/rq_catalogue.py" --tested "$1" 2>/dev/null | cut -f1 || true
}

# The versions of an image on ghcr.io (rq_image_versions.py lines)
image_versions() { # KEY MANIFEST
    local tags latest order
    tags=$(jq -r '.install.update.docker_tags' "$2")
    latest=$(jq -r '.install.update.docker_latest // ""' "$2")
    order=$(jq -r '.install.update.docker_order // "date"' "$2")
    python3 "$BIN_DIR/rq_image_versions.py" "$(current_pin "$1" "$2")" --tags "$tags" --latest "$latest" --order "$order" 2>&1
}

# What is newer for a demo, in a few words; status 1 when nothing is
newer_text() {    # KEY MANIFEST
    local key="$1" mf="$2" cur tested what="" out head
    cur=$(current_pin "$key" "$mf")
    tested=$(tested_pin "$key")
    case "$key" in
        *:image)
            if out=$(image_versions "$key" "$mf"); then
                what=$(awk -F'\t' '$6 == "newer" { print "newer version from " $3; exit }' <<< "$out")
            fi ;;
        *:ref)
            head=$(git ls-remote "$(rq_demo_repo "${key%:*}" "$mf")" HEAD 2>/dev/null | cut -f1) || head=""
            [ -n "$head" ] && [ "$head" != "$cur" ] && what="newer version on GitHub" ;;
    esac
    if [ -n "$tested" ] && [ "$tested" != "$cur" ]; then
        what="${what:+$what, }tested update"
    fi
    [ -n "$what" ] || return 1
    echo "$what"
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
    local key="$1" name="$2" mf="$3" id="${1%:*}" cur rel tested out rc=0
    cur=$(current_pin "$key" "$mf")
    rel=$(release_pin "$key" "$mf")
    tested=$(tested_pin "$key")

    show_infobox "$TITLE" "Looking for newer versions of $name on ghcr.io..."
    out=$(image_versions "$key" "$mf") || rc=$?
    if [ "$rc" -ne 0 ]; then
        show_msgbox "$TITLE" "The versions of $name could not be listed:\n\n$out"
        return 0
    fi

    # whiptail --notags: numbers as tags, the image refs in a list
    set --
    local -a refs=()
    local line ref t date mb note state marks cur_line="" i=0
    while IFS=$'\t' read -r ref t date mb note state; do
        [ -n "$ref" ] || continue
        marks=""
        [ "$ref" = "$rel" ] && marks="release"
        [ -n "$tested" ] && [ "$ref" = "$tested" ] && marks="${marks:+$marks, }tested"
        if [ "$state" = current ]; then
            cur_line=$(version_item "$date" "$(short_id "$t" "$ref")" 0 "$marks" "$note")
            continue
        fi
        i=$((i + 1))
        refs[i]="$ref"
        set -- "$@" "$i" "$(version_item "$date" "$(short_id "$t" "$ref")" "$mb" "$marks" "$note")"
    done <<< "$out"
    [ "$cur" != "$rel" ] && set -- "$@" "RELEASE" "Back to the version this release ships"
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "$name is up to date.\n\nIn use: $cur_line"
        return 0
    fi

    local choice
    choice=$(whiptail --title "$TITLE: $name" --notags --menu \
        "In use: $cur_line\nNewest first. The one you choose is downloaded and used from the next start." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || return 0

    local target label="" dl=0
    if [ "$choice" = "RELEASE" ]; then
        target="$rel"
    else
        target="${refs[choice]}"
        line=$(awk -F'\t' -v r="$target" '$1 == r' <<< "$out" | head -1)
        IFS=$'\t' read -r ref t date mb note state <<< "$line"
        label="$(short_id "$t" "$ref"), $date"
        [ "$target" = "$tested" ] && label="tested: $label"
        dl="$mb"
    fi
    apply_image "$key" "$name" "$mf" "$target" "$label" "$dl"
}

# Move a Docker demo to TARGET (download it first, after the usual dialog)
apply_image() {   # KEY NAME MANIFEST TARGET LABEL DOWNLOAD_MB
    local key="$1" name="$2" mf="$3" target="$4" label="$5" dl="${6:-0}" rel disk=0 rc
    rel=$(release_pin "$key" "$mf")
    [ "$dl" -gt 0 ] 2>/dev/null && disk=$(jq -r --argjson dl "$dl" \
        '(.install.download.disk_mb // 0) as $d | (.install.download.download_mb // 0) as $m
         | if $m > 0 then ($dl * $d / $m | floor) else $dl end' "$mf")

    if ! docker image inspect "$target" >/dev/null 2>&1; then
        rc=0
        rq_confirm_download "$name" "$dl" "$disk" --path /var/lib/docker \
            --url "https://ghcr.io/v2/" --image "$target" \
            --title "Update $name?" \
            --intro "$name: ${label:-the version this release ships}." \
            --question "Download it now? The version in use is removed afterwards." || rc=$?
        case "$rc" in
            0) ;;
            1) return 0 ;;
            *) show_msgbox "$TITLE" "$RQ_CONSENT_MSG"; return 0 ;;
        esac
        rq_docker_access
        rc=0
        ( rq_docker_pull "$target" "$name" "$dl" ) || rc=$?
        case "$rc" in
            0) ;;
            130) show_msgbox "$TITLE" "Download stopped. $name keeps the version in use."; return 0 ;;
            *) show_msgbox "$TITLE" "$name was not updated: the download failed."; return 0 ;;
        esac
    fi
    if [ "$target" = "$rel" ]; then
        rq_demo_set_version "$key" "$rel" ""
    else
        rq_demo_set_version "$key" "$rel" "$target" "$label"
    fi
    rq_docker_drop_old "$target"
    show_msgbox "$TITLE" "$name now uses: $(shown_label "$label").\n\nIt is used the next time $name starts (a running one keeps its version until then)."
    return 0
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

    # The newer commits, newest first (GitHub API; without it only the
    # newest), numbered for whiptail --notags
    set --
    local -a shas=()
    local i=0 tested marks cur_marks=""
    tested=$(tested_pin "$key")
    slug=$(printf '%s' "$url" | sed -n 's#^https://github.com/\([^/]*/[^/.]*\).*#\1#p')
    if [ "$head" != "$cur" ] && [ -n "$slug" ]; then
        api=$(curl -s --max-time 15 "https://api.github.com/repos/$slug/compare/$cur...$head" 2>/dev/null) || api=""
        while IFS=$'\t' read -r sha date msg; do
            [ -n "$sha" ] || continue
            marks=""
            [ -n "$tested" ] && [ "$sha" = "$tested" ] && marks="tested"
            i=$((i + 1))
            shas[i]="$sha"
            set -- "$@" "$i" "$(version_item "${date:0:10}" "${sha:0:7}" 0 "$marks" "$msg")"
        done < <(jq -r '.commits // [] | reverse | .[:10][]
                 | [.sha, .commit.committer.date, (.commit.message | split("\n")[0])] | @tsv' <<< "$api" 2>/dev/null)
        if [ $# -eq 0 ]; then
            shas[1]="$head"
            set -- 1 "Newest version (${head:0:7})"
        fi
    fi
    [ "$cur" != "$rel" ] && set -- "$@" "RELEASE" "Back to the version this release ships"
    [ "$cur" = "$rel" ] && cur_marks=", release"
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "$name is up to date (${cur:0:7}$cur_marks)."
        return 0
    fi

    local choice target label
    choice=$(whiptail --title "$TITLE: $name" --notags --menu \
        "In use: ${cur:0:7}$cur_marks. Newest first.\nThe one you choose is installed now; your changes are kept in a copy." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || return 0
    if [ "$choice" = "RELEASE" ]; then
        target="$rel"; label=""
    else
        target="${shas[choice]}"; label="${target:0:7}"
        [ "$target" = "$tested" ] && label="tested: $label"
    fi
    apply_ref "$key" "$name" "$mf" "$target" "$label"
}

# Move a notebook or program demo to commit TARGET (the earlier copy is kept)
apply_ref() {     # KEY NAME MANIFEST TARGET LABEL
    local key="$1" name="$2" mf="$3" target="$4" label="$5" id="${1%:*}" cur rel wd demo_dir rc=0
    cur=$(current_pin "$key" "$mf")
    rel=$(release_pin "$key" "$mf")
    wd=$(jq -r '.entrypoint.working_dir' "$mf")
    demo_dir="$USER_HOME/$REPO/demos/$wd"

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
    local ok=1 other
    RQ_CONFIRMED_DEMO="$id" "$BIN_DIR/rq_demo_run.sh" "$id" --install-only || ok=0
    # a demo sharing the checkout sets up its part again (the IBM Tutorials'
    # welcome page), with nothing to download
    if [ "$ok" = 1 ]; then
        for other in $(sharers "$wd" "$id"); do
            RQ_CONFIRMED_DEMO="$other" "$BIN_DIR/rq_demo_run.sh" "$other" --install-only || ok=0
        done
    fi
    if [ "$ok" = 1 ]; then
        # Files the user added (own notebooks, a settings file) come along;
        # Python's caches do not (rig check 2026-10-24: copied as root, a
        # root-owned GHZGame/__pycache__ blocked removing the checkout)
        ( cd "$backup" && git ls-files --others -z 2>/dev/null ) \
            | while IFS= read -r -d '' f; do
                case "/$f" in */__pycache__/*) continue ;; esac
                [ -e "$demo_dir/$f" ] && continue
                mkdir -p "$demo_dir/$(dirname "$f")"
                cp -p "$backup/$f" "$demo_dir/$f"
            done
        # the whole tree, not only a root-owned top (fix_root_ownership)
        if [ "$(id -u)" = "0" ] && [ "$(get_user_name)" != "root" ]; then
            chown -R "$(get_user_name):" "$demo_dir" 2>/dev/null || true
        fi
        show_msgbox "$TITLE" "$name is now at $(shown_label "$label").\n\nThe earlier copy is kept in:\n$backup"
    else
        rq_remove_tree "$demo_dir" || true
        mv "$backup" "$demo_dir"
        rq_demo_set_version "$key" "$rel" "$( [ "$cur" = "$rel" ] || echo "$cur")" "$(rq_demo_chosen_label "$key" || true)"
        show_msgbox "$TITLE" "$name could not be updated, so the version in use was put back."
    fi
}

# ----------------------------------------------------------------------------
# A tested update from the demo catalogue (--tested ID:KIND)
# ----------------------------------------------------------------------------
apply_tested() {  # ID:KIND
    local key="$1" line name mf pin label dl
    [[ "$key" =~ ^[a-z0-9][a-z0-9-]*:(image|ref)$ ]] || die "Usage: rq_demo_update.sh --tested ID:image|ID:ref"
    line=$(updatable | awk -F'\t' -v k="$key" '$1 == k')
    if [ -z "$line" ]; then
        show_msgbox "$TITLE" "${key%:*} is not downloaded here, so there is nothing to update.\n\nStart it once to download it; the taskbar then offers the update."
        return 0
    fi
    IFS=$'\t' read -r key name mf <<< "$line"
    if ! line=$(RQ_USER_HOME="$USER_HOME" python3 "$BIN_DIR/rq_catalogue.py" --tested "$key"); then
        show_msgbox "$TITLE" "There is no tested update for $name on this RasQberry (any more): it is up to date, or a version was chosen under Update demos."
        return 0
    fi
    IFS=$'\t' read -r pin label dl <<< "$line"
    [ "${dl:-0}" -gt 0 ] 2>/dev/null || dl=$(jq -r '.install.download.download_mb // 0' "$mf")
    case "$key" in
        *:image)
            apply_image "$key" "$name" "$mf" "$pin" "tested: $label" "${dl:-0}" ;;
        *:ref)
            show_yesno "Update $name?" "A tested update for $name is available: $label.\n\nYour changes to its files are kept in a copy next to it, and Update demos can take it back to the version this release ships.\n\nUpdate now?" || return 0
            apply_ref "$key" "$name" "$mf" "$pin" "tested: $label" ;;
    esac
}

# ----------------------------------------------------------------------------
# Menu (or --tested)
# ----------------------------------------------------------------------------
if [ "${1:-}" = "--tested" ]; then
    apply_tested "${2:-}"
    exit $?
fi

# Choose a demo by its menu number (KEY<TAB>NAME<TAB>MANIFEST lines in $1)
open_picker() {   # LINE
    local key name mf
    IFS=$'\t' read -r key name mf <<< "$1"
    case "$key" in
        *:image) update_image "$key" "$name" "$mf" ;;
        *:ref)   update_ref "$key" "$name" "$mf" ;;
    esac
}

# "Check all for newer versions": only the demos with a newer or tested one
check_all() {
    local key name mf what pick i=0
    local -a lines=()
    show_infobox "$TITLE" "Looking for newer versions of the downloaded demos..."
    set --
    while IFS=$'\t' read -r key name mf; do
        [ -n "$key" ] || continue
        what=$(newer_text "$key" "$mf") || continue
        i=$((i + 1))
        lines[i]="$key"$'\t'"$name"$'\t'"$mf"
        set -- "$@" "$i" "$(fit "$name: $what")"
    done < <(updatable)
    if [ $# -eq 0 ]; then
        show_msgbox "$TITLE" "All downloaded demos have the newest version."
        return 0
    fi
    pick=$(whiptail --title "$TITLE" --notags --menu \
        "These demos have a newer or tested version. Choose one to see its versions." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || return 0
    open_picker "${lines[pick]}"
}

while true; do
    set -- CHECK "Check all for newer versions"
    lines=()
    i=0
    while IFS=$'\t' read -r key name mf; do
        [ -n "$key" ] || continue
        # what an update brings: only the notebook demos are notebooks (#31)
        case "$key" in
            *:image) kind="Docker" ;;
            *) if [ "$(jq -r '.entrypoint.type // ""' "$mf")" = "jupyter" ]; then
                   kind="notebooks"
               else
                   kind="program"
               fi ;;
        esac
        state=$(fit "$(state_text "$key" "$mf")" 30)
        i=$((i + 1))
        lines[i]="$key"$'\t'"$name"$'\t'"$mf"
        # the name gives way, the state stays whole
        set -- "$@" "$i" "$(fit "$name" $((66 - ${#kind} - ${#state} - 5))) ($kind): $state"
    done < <(updatable)
    if [ "$i" -eq 0 ]; then
        show_msgbox "$TITLE" "No downloaded demo can be updated.\n\nDemos are downloaded the first time they start."
        exit 0
    fi
    pick=$(whiptail --title "$TITLE" --notags --menu \
        "Each RasQberry release ships tested demo versions. Check all, or choose a demo to see its versions." \
        20 78 10 "$@" 3>&1 1>&2 2>&3) || exit 0
    if [ "$pick" = CHECK ]; then
        check_all
    else
        open_picker "${lines[pick]}"
    fi
done
