#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: QuBins (beta)
# ============================================================================
# Description: JupyterLab with the Qiskit version you choose, in a QuBins
#   Docker container (ghcr.io/qubins/images), with the notebooks you choose.
#   1. Which image: QuBins' monthly snapshots (Qiskit version, xl or small,
#      date, download size); the tested one (the manifest's pin) first, the
#      ones on this Pi marked. Offline: the images known from earlier.
#   2. What goes into the lab: IBM Quantum Tutorials, IBM Quantum Courses
#      (one shared download), Quantum Paradoxes, Fun with Quantum - or
#      nothing extra. my-work (writable, kept on the Pi) is always there.
#   Missing content is downloaded through the demo engine (its usual
#   question with the size), the image after its own question. The lab gets
#   the user's own, editable copy of each chosen notebook folder
#   (~/RasQberry-Two/work/qubins, made on first use and kept), with the
#   untouched originals read-only in originals/; "Reset notebooks to the
#   original" in the first dialog makes a copy again. The choices
#   are kept: the next start offers "Start with last settings" first. The
#   image chosen is also recorded as the version in use (.demo-versions), so
#   Update demos and Remove a demo see it.
#   Will replace Qiskit Live (quantum-lab) and the IBM Tutorials and Courses
#   demos after a test; until then they stay as they are.
# Usage: rq_demo_run.sh qubins   (or this script directly)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

rq_demo_header "QuBins (beta)"

load_rqb2_env
verify_env_vars REPO USER_HOME BIN_DIR

DEMO_ID="qubins"
TITLE="QuBins"
HELPER="$SCRIPT_DIR/rq_qubins.py"
MANIFEST=$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$DEMO_ID") \
    || die "The QuBins manifest is missing (the image may be misbuilt)."
PIN=$(jq -r '.entrypoint.docker_image' "$MANIFEST")
PIN_TAG=$(jq -r '.entrypoint.docker_image_tag // empty' "$MANIFEST")
PIN_MB=$(jq -r '.install.download.download_mb // 0' "$MANIFEST")
# The image QuBins runs: the tested one, or the one chosen last
IN_USE=$(rq_demo_image "$DEMO_ID" "$MANIFEST")
CONTAINER_NAME="qubins"
PORT="${QUBINS_PORT:-8894}"
# Shared with Qiskit Live, which QuBins is to replace: nothing to move then
WORK_DIR="$USER_HOME/$REPO/work/quantum-lab"
DEMOS_DIR="$USER_HOME/$REPO/demos"
# The user's editable copies of the notebooks (never my-work)
COPIES_DIR="$USER_HOME/$REPO/work/qubins"
STATE_FILE="${XDG_STATE_HOME:-$USER_HOME/.local/state}/rasqberry/qubins.json"
CACHE_FILE="$USER_HOME/.cache/rasqberry/qubins-images.json"
WELCOME_SRC="$(dirname "$(rq_shipped_manifest_dir)")/qubins/WELCOME.ipynb"
LAB_OVERRIDES="${RQ_LAB_OVERRIDES:-/etc/jupyter/labconfig/default_setting_overrides.json}"
# Hides the image's own empty "work" folder next to my-work
HIDE_WORK_HOOK="$(dirname "$(rq_shipped_manifest_dir)")/qubins/hide-work.sh"
# See rq_quantum_lab.sh: a known token in the URL; the port is loopback only
LAB_TOKEN="rasqberry"
CONTENT_IDS="ibm-tutorials ibm-courses quantum-paradoxes fun-with-quantum"

rq_docker_access "$@"
rq_stop_if_card_too_small "$TITLE" "$IN_USE"

# Can we ask? (a terminal, or the tests' stand-in)
can_ask() {
    command -v whiptail >/dev/null 2>&1 || return 1
    [ -n "${RQ_TEST_TTY:-}" ] || { [ -t 0 ] && [ -t 1 ]; }
}

content_name() {
    case "$1" in
        ibm-tutorials) echo "IBM Quantum Tutorials" ;;
        ibm-courses) echo "IBM Quantum Courses" ;;
        quantum-paradoxes) echo "Quantum Paradoxes" ;;
        fun-with-quantum) echo "Fun with Quantum" ;;
        *) echo "$1" ;;
    esac
}

content_names() {   # comma-separated ids -> "A, B" or "only my-work"
    local out="" c
    for c in $(echo "$1" | tr ',' ' '); do
        out="${out:+$out, }$(content_name "$c")"
    done
    echo "${out:-only my-work}"
}

installed() {
    "$SCRIPT_DIR/rq_demo_run.sh" "$1" --is-installed >/dev/null 2>&1
}

# "Reset notebooks to the original": choose which content, confirm, copy
# again. Nothing of the changes in that content is kept; my-work is never
# touched.
reset_dialog() {
    local have c picked items=()
    have=$(python3 "$HELPER" copies --copies "$COPIES_DIR" 2>/dev/null) || have=""
    if [ -z "$have" ]; then
        show_msgbox "$TITLE: reset notebooks" "There are no notebooks to reset yet." || true
        return 0
    fi
    for c in $(echo "$have" | tr ',' ' '); do
        items+=("$c" "$(content_name "$c")" OFF)
    done
    picked=$(whiptail --title "$TITLE: reset notebooks" --checklist \
        "Which notebooks go back to the original? (Space: select)\nYour changes in them are lost. my-work is not touched." \
        14 76 4 "${items[@]}" 3>&1 1>&2 2>&3) || return 0
    picked=$(echo "$picked" | tr -d '"' | tr ' ' ',' | sed 's/^,*//; s/,*$//')
    [ -n "$picked" ] || return 0
    show_yesno "$TITLE: reset notebooks" \
        "Reset $(content_names "$picked") to the original?\n\nAll your changes in these notebooks are lost. my-work is not touched." \
        || return 0
    if python3 "$HELPER" reset --content "$picked" --demos "$DEMOS_DIR" --copies "$COPIES_DIR" >/dev/null; then
        show_msgbox "$TITLE: reset notebooks" "Back to the original: $(content_names "$picked")." || true
    else
        show_msgbox "$TITLE: reset notebooks" "The reset did not work." || true
    fi
}

# The digests of the QuBins images on this Pi, space-separated
local_digests() {
    docker images --digests --format '{{.Digest}}' ghcr.io/qubins/images 2>/dev/null \
        | grep '^sha256:' | sort -u | tr '\n' ' ' || true
}

# ----------------------------------------------------------------------------
# 1. The last settings, or a new choice
# ----------------------------------------------------------------------------
IMAGE="" LABEL="" CONTENT="" MB=0 LAST_LINE="" CHOOSE=1
LAST_LINE=$(python3 "$HELPER" last --state "$STATE_FILE" 2>/dev/null) || LAST_LINE=""
if [ -n "$LAST_LINE" ]; then
    IFS=$'\t' read -r last_image LABEL CONTENT <<< "$LAST_LINE"
    # A newer RasQberry release brings a newer tested image: that one wins
    # (rq_demo_image); the label fits only the image it was saved with
    [ "$last_image" = "$IN_USE" ] || LABEL=""
    [ "$LABEL" != "-" ] || LABEL=""
    if [ -z "$LABEL" ]; then
        if [ "$IN_USE" = "$PIN" ]; then LABEL="$PIN_TAG"; else LABEL="${IN_USE##*@}"; LABEL="${LABEL:0:19}"; fi
    fi
    IMAGE="$IN_USE"
    CHOOSE=0
    while can_ask; do
        pick=$(whiptail --title "$TITLE (beta)" --menu \
            "Start QuBins:" 13 76 3 \
            "LAST" "Start with last settings: $LABEL, $(content_names "$CONTENT")" \
            "CHOOSE" "Choose the image and the content" \
            "RESET" "Reset notebooks to the original" \
            3>&1 1>&2 2>&3) || exit 0
        case "$pick" in
            LAST) break ;;
            CHOOSE) CHOOSE=1; break ;;
            RESET) reset_dialog ;;
        esac
    done
fi

if [ "$CHOOSE" = 1 ] && ! can_ask; then
    # No terminal to ask on: the tested image, only my-work
    info "No terminal to ask which image and content: starting the tested image with only my-work."
    IMAGE="$IN_USE"
    LABEL="$PIN_TAG"
    [ "$IN_USE" = "$PIN" ] || LABEL="${IN_USE##*@}"
    CONTENT=""
    CHOOSE=0
fi

# ----------------------------------------------------------------------------
# 2. Which image
# ----------------------------------------------------------------------------
if [ "$CHOOSE" = 1 ]; then
    whiptail --title "$TITLE" --infobox "Looking for QuBins images on ghcr.io..." 7 60 || true
    list_rc=0
    list=$(python3 "$HELPER" images --pin "$PIN" --pin-tag "$PIN_TAG" --pin-mb "$PIN_MB" \
        --in-use "$IN_USE" --in-use-label "$(rq_demo_chosen_label "$DEMO_ID:image" 2>/dev/null | sed 's/,.*//' || true)" \
        --local "$(local_digests)" --cache "$CACHE_FILE" 2>/dev/null) || list_rc=$?
    [ -n "$list" ] || die "No QuBins image to offer (the QuBins manifest may be broken)."

    refs=() tags=() mbs=() items=() n=0 default_item=1
    while IFS=$'\t' read -r ref tag qiskit variant date mb marks; do
        [ -n "$ref" ] || continue
        n=$((n + 1))
        refs+=("$ref"); tags+=("$tag"); mbs+=("$mb")
        note=""
        case ",$marks," in *,tested,*) note="tested" ;; esac
        case ",$marks," in *,downloaded,*) note="${note:+$note, }on this Pi" ;; esac
        case ",$marks," in *,in-use,*) default_item=$n ;; esac
        size="~$mb MB"
        [ "$mb" -gt 0 ] 2>/dev/null || size="size ?"
        items+=("$n" "$(printf '%-6s %-5s %s  %8s  %s' "$qiskit" "$variant" "$date" "$size" "${note:+[$note]}")")
    done <<< "$list"

    prompt="Which Qiskit version? xl: for tutorials and courses (the usual pick). small: core Qiskit only."
    [ "$list_rc" -eq 2 ] && prompt="$prompt\nOffline: only the images known from earlier."
    pick=$(whiptail --title "$TITLE: image" --default-item "$default_item" --menu \
        "$prompt" 20 76 10 "${items[@]}" 3>&1 1>&2 2>&3) || exit 0
    i=$((pick - 1))
    IMAGE="${refs[$i]}"
    LABEL="${tags[$i]}"
    MB="${mbs[$i]}"

    # ------------------------------------------------------------------------
    # 3. What goes into the lab
    # ------------------------------------------------------------------------
    ibm_here=""
    if installed ibm-tutorials || installed ibm-courses; then ibm_here=1; fi
    # First start: the courses, as in Qiskit Live
    [ -n "$LAST_LINE" ] || CONTENT="ibm-courses"
    checks=()
    for c in $CONTENT_IDS; do
        if installed "$c"; then
            what="on this Pi"
        elif [ -n "$ibm_here" ] && [ "${c#ibm-}" != "$c" ]; then
            what="no download"
        else
            what="download ~$(jq -r '.install.download.download_mb // 0' \
                "$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$c")" 2>/dev/null || echo "?") MB"
        fi
        state=OFF
        case ",$CONTENT," in *",$c,"*) state=ON ;; esac
        checks+=("$c" "$(content_name "$c") ($what)" "$state")
    done
    picked=$(whiptail --title "$TITLE: content" --checklist \
        "What goes into the lab? (Space: select)\nYour my-work folder is always there. Choose nothing for only my-work.\nYou can change the notebooks: your changes are kept." \
        16 76 4 "${checks[@]}" 3>&1 1>&2 2>&3) || exit 0
    CONTENT=$(echo "$picked" | tr -d '"' | tr ' ' ',' | sed 's/^,*//; s/,*$//')
fi

# ----------------------------------------------------------------------------
# 4. Download what is missing: the content, then the image
# ----------------------------------------------------------------------------
kept=""
for c in $(echo "$CONTENT" | tr ',' ' '); do
    if ! installed "$c"; then
        info "Downloading $(content_name "$c")..."
        rc=0
        "$SCRIPT_DIR/rq_demo_run.sh" "$c" --install-only || rc=$?
        case "$rc" in
            0) ;;
            130|129|143) exit "$rc" ;;
            *) warn "$(content_name "$c") was not downloaded: QuBins starts without it." ;;
        esac
        installed "$c" || continue
    fi
    kept="${kept:+$kept,}$c"
done
CONTENT="$kept"
case ",$CONTENT," in
    *,ibm-*) rq_ibm_learning_tidy "$DEMOS_DIR/ibm-quantum-learning" ;;
esac
# The user's copies: made on first use, kept afterwards (a newer original is
# named once)
if [ -n "$CONTENT" ]; then
    mkdir -p "$COPIES_DIR"
    notes=$(python3 "$HELPER" prepare --content "$CONTENT" --demos "$DEMOS_DIR" --copies "$COPIES_DIR") \
        || die "Could not make your copies of the notebooks in $COPIES_DIR."
    while IFS= read -r note; do
        [ -n "$note" ] && info "$note"
    done <<< "$notes"
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    [ "$MB" -gt 0 ] 2>/dev/null || MB="$PIN_MB"
    rc=0
    rq_confirm_download "$TITLE $LABEL" "$MB" $((MB * 45 / 10)) --docker \
        --what "QuBins image $LABEL from ghcr.io" --path /var/lib/docker \
        --url "https://ghcr.io/v2/" --image "$IMAGE" || rc=$?
    case "$rc" in
        0) ;;
        1) info "${RQ_CONSENT_MSG:-Not downloaded.}"; exit 0 ;;
        5) rq_card_note; exit 0 ;;
        *) die "${RQ_CONSENT_MSG:-The download was stopped.}" ;;
    esac
    if [ "$IMAGE" = "$PIN" ]; then
        # the manifest's fallback tag when QuBins no longer offers the pin
        rq_demo_docker_pull "$DEMO_ID" "$IMAGE" "$TITLE $LABEL" "$MB" "$MANIFEST"
    else
        # a snapshot gone meanwhile: its moving tag (2.6-xl-20261020 -> 2.6-xl)
        fallback=""
        case "$LABEL" in *-20[0-9][0-9][0-9][0-9][0-9][0-9]) fallback="ghcr.io/qubins/images:${LABEL%-*}" ;; esac
        rq_docker_pull "$IMAGE" "$TITLE $LABEL" "$MB" "$fallback"
    fi
    IMAGE="$RQ_DOCKER_PULLED"
    # Other QuBins images stay (dropping the older ones would remove Qiskit
    # Live's too): Remove a demo frees the space
fi

# ----------------------------------------------------------------------------
# 5. Remember the choices
# ----------------------------------------------------------------------------
if [ "$IMAGE" = "$PIN" ]; then
    rq_demo_set_version "$DEMO_ID:image" "$PIN" "" "" || true
elif [ "$IMAGE" != "$(rq_demo_image "$DEMO_ID" "$MANIFEST")" ]; then
    rq_demo_set_version "$DEMO_ID:image" "$PIN" "$IMAGE" "$LABEL" \
        || warn "Could not record that QuBins uses $LABEL."
fi
python3 "$HELPER" remember --state "$STATE_FILE" --image "$IMAGE" --label "$LABEL" \
    --content "$CONTENT" 2>/dev/null || warn "Could not save the choices for the next start."
fix_root_ownership "$(dirname "$STATE_FILE")" >/dev/null 2>&1 || true

# ----------------------------------------------------------------------------
# 6. Start the container
# ----------------------------------------------------------------------------
rq_docker_stop "$CONTAINER_NAME" \
    || die "The previous QuBins container did not go away; try again in a minute."
if port_in_use "$PORT"; then
    PORT=$(find_available_port $((PORT + 1)))
    warn "Port ${QUBINS_PORT:-8894} is taken; QuBins uses $PORT this time."
fi

mkdir -p "$WORK_DIR"
fix_root_ownership "$USER_HOME/$REPO/work" >/dev/null 2>&1 || true
# jovyan in the container is uid 1000 (see rq_quantum_lab.sh)
[ "$(stat -c %u "$WORK_DIR" 2>/dev/null || echo 1000)" = "1000" ] || chmod 777 "$WORK_DIR" 2>/dev/null || true

MOUNTS=()
while IFS= read -r arg; do
    [ -n "$arg" ] && MOUNTS+=("$arg")
done < <(python3 "$HELPER" mounts --content "$CONTENT" --demos "$DEMOS_DIR" --work "$WORK_DIR" \
    --welcome "$WELCOME_SRC" --overrides "$LAB_OVERRIDES" --copies "$COPIES_DIR" \
    --hook "$HIDE_WORK_HOOK")
START_PAGE="lab"
[ -f "$WELCOME_SRC" ] && START_PAGE="lab/tree/WELCOME.ipynb"

echo
info "Starting QuBins ($LABEL)..."
if ! docker run -d \
    --name "$CONTAINER_NAME" \
    --label "org.rasqberry.demo=$DEMO_ID" \
    -p "127.0.0.1:${PORT}:8888" \
    -e JUPYTER_TOKEN="$LAB_TOKEN" \
    ${MOUNTS[@]+"${MOUNTS[@]}"} \
    "$IMAGE" >/dev/null; then
    rq_docker_fail "$CONTAINER_NAME" "The QuBins container did not start."
fi

info "Waiting for JupyterLab to start..."
LAB_URL="http://127.0.0.1:${PORT}/${START_PAGE}?token=${LAB_TOKEN}"
MAX_WAIT=60
WAIT_COUNT=0
until curl -sf "http://127.0.0.1:${PORT}/lab" >/dev/null 2>&1; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    rq_docker_running "$CONTAINER_NAME" \
        || rq_docker_fail "$CONTAINER_NAME" "QuBins stopped while starting."
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        rq_docker_fail "$CONTAINER_NAME" "JupyterLab did not answer within ${MAX_WAIT} seconds."
    fi
done

echo
echo "✓ QuBins is running: $LABEL"
echo
echo "  Access via browser: $LAB_URL"
if [ -n "$CONTENT" ]; then
    echo "  In the lab: $(content_names "$CONTENT"), and my-work"
    echo "  The notebooks are your own copies (kept in $COPIES_DIR);"
    echo "  originals/ has the untouched ones. Reset: the QuBins start dialog."
fi
echo "  Save your own work in my-work/ - it is kept on the Pi in:"
echo "    $WORK_DIR"
echo "  Anything saved elsewhere in the lab is lost when it stops."
echo

rq_show_url "$LAB_URL" "$PORT"

rq_docker_stop_with_window "$CONTAINER_NAME" "QuBins"
