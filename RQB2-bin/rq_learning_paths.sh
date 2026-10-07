#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Learning paths (beta)
# ============================================================================
# Description: Short tours through the demos for one audience (#309): pick a
#   path, then go step by step - "Step 2 of 4: Quantum Coin Game" with what to
#   try and what to notice - and start each demo from there. A demo starts
#   through the demo engine (rq_demo_run.sh, which asks before a first
#   download), and its step comes back when it stops. The paths are in
#   learning-paths.json next to the demo manifests; the website's Learning
#   paths page is made from the same file. After the last step, Keep going
#   offers what to do next (another path or a page), and Where to go next
#   lists six steps from playing to building your own. Opened from the
#   RasQberry menu (Quantum Demos -> Learning paths) and from the Learning
#   paths icon.
# Usage: rq_learning_paths.sh           choose a path
#        rq_learning_paths.sh --menu    the same, started from the RasQberry menu
#        rq_learning_paths.sh --list    print the paths and their steps

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

MODE="${1:-}"
case "$MODE" in
    ""|--menu|--list) ;;
    *) die "Usage: $(basename "$0") [--menu | --list]" ;;
esac

command -v jq >/dev/null 2>&1 || die "jq is required but not installed"
# The demos load the environment themselves; this script only reads the paths
if [ -f "$RQ_CONFIG_FILE" ]; then
    load_rqb2_env
fi

PATHS_FILE="${RQ_LEARNING_PATHS:-$(rq_shipped_manifest_dir)/learning-paths.json}"
[ -f "$PATHS_FILE" ] || die "The learning paths are missing ($PATHS_FILE)"
jq -e '.paths | length > 0' "$PATHS_FILE" >/dev/null 2>&1 \
    || die "The learning paths cannot be read ($PATHS_FILE)"

FEEDBACK="${RQ_FEEDBACK_URL}&demo=learning-paths"
WIDTH=78
US=$'\x1f'   # field separator for jq output (never in the texts)

# ============================================================================
# DATA
# ============================================================================

path_count() { jq -r '.paths | length' "$PATHS_FILE"; }

# One path: id, title, audience, minutes, goal, number of steps
# Usage: path_info INDEX  -> sets P_ID P_TITLE P_AUDIENCE P_MINUTES P_GOAL P_STEPS
path_info() {
    IFS="$US" read -r P_ID P_TITLE P_AUDIENCE P_MINUTES P_GOAL P_STEPS < <(
        jq -r --argjson i "$1" '.paths[$i]
            | [.id, .title, .audience, (.minutes | tostring), .goal, (.steps | length | tostring)]
            | join("\u001f")' "$PATHS_FILE")
}

# The name a demo has everywhere (docs/STYLE.md): its manifest's
demo_name() {
    local mf
    if mf=$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$1" 2>/dev/null); then
        jq -r '.name // empty' "$mf" 2>/dev/null && return 0
    fi
    echo "$1"
}

# One step of a path
# Usage: step_info PATH_INDEX STEP_INDEX
#   -> sets S_DEMO S_VARIANT S_COMMAND S_URL S_NAME S_TRY S_NOTICE
step_info() {
    IFS="$US" read -r S_DEMO S_VARIANT S_COMMAND S_URL S_NAME S_TRY S_NOTICE < <(
        jq -r --argjson i "$1" --argjson s "$2" '.paths[$i].steps[$s]
            | [.demo, .variant, .command, .url, .name, .try, .notice]
            | map(. // "") | join("\u001f")' "$PATHS_FILE")
    if [ -z "$S_NAME" ]; then
        if [ -n "$S_DEMO" ]; then S_NAME=$(demo_name "$S_DEMO"); else S_NAME="${S_COMMAND:-$S_URL}"; fi
    fi
}

# What comes after path INDEX (Keep going): one entry per array element.
# N_KIND is "path" (N_TARGET = that path's index, N_NAME its title) or "url".
# Usage: next_info INDEX  -> sets N_KIND N_TARGET N_NAME N_WHY
next_info() {
    local kind target name why
    N_KIND=(); N_TARGET=(); N_NAME=(); N_WHY=()
    while IFS="$US" read -r kind target name why; do
        [ -n "$kind" ] || continue
        N_KIND+=("$kind"); N_TARGET+=("$target"); N_NAME+=("$name"); N_WHY+=("$why")
    done < <(jq -r --argjson i "$1" '.paths as $all | .paths[$i].next[]?
        | if .path then (.path as $p | ["path", ($all | map(.id) | index($p) | tostring),
                                        ($all[] | select(.id == $p) | .title), .why])
          else ["url", .url, .name, .why] end
        | join("\u001f")' "$PATHS_FILE")
}

# The rungs of Where to go next. Usage: ladder_info -> sets L_RUNG L_TEXT
ladder_info() {
    local rung text
    L_RUNG=(); L_TEXT=()
    while IFS="$US" read -r rung text; do
        [ -n "$rung" ] || continue
        L_RUNG+=("$rung"); L_TEXT+=("$text")
    done < <(jq -r '.ladder[]? | [.rung, .text] | join("\u001f")' "$PATHS_FILE")
}

# The links of rung INDEX. Usage: rung_links INDEX -> sets K_NAME K_URL K_NOTE
rung_links() {
    local name url note
    K_NAME=(); K_URL=(); K_NOTE=()
    while IFS="$US" read -r name url note; do
        [ -n "$name" ] || continue
        K_NAME+=("$name"); K_URL+=("$url"); K_NOTE+=("$note")
    done < <(jq -r --argjson r "$1" '.ladder[$r].links[] | [.name, .url, (.note // "")]
        | join("\u001f")' "$PATHS_FILE")
}

# ============================================================================
# PLAIN TEXT (--list, and without whiptail or a terminal)
# ============================================================================

list_paths() {
    local i s n
    n=$(path_count)
    for ((i = 0; i < n; i++)); do
        path_info "$i"
        echo "$P_TITLE (beta) - $P_AUDIENCE, about $P_MINUTES minutes"
        echo "  $P_GOAL"
        for ((s = 0; s < P_STEPS; s++)); do
            step_info "$i" "$s"
            echo "  $((s + 1)). $S_NAME"
            echo "     Try: $S_TRY"
            echo "     Notice: $S_NOTICE"
        done
        next_info "$i"
        echo "  Keep going:"
        for ((s = 0; s < ${#N_KIND[@]}; s++)); do
            if [ "${N_KIND[s]}" = path ]; then
                echo "   - the path \"${N_NAME[s]}\": ${N_WHY[s]}"
            else
                echo "   - ${N_NAME[s]} (${N_TARGET[s]}): ${N_WHY[s]}"
            fi
        done
        echo
    done
    echo "Where to go next:"
    ladder_info
    for ((i = 0; i < ${#L_RUNG[@]}; i++)); do
        echo "  $((i + 1)). ${L_RUNG[i]}: ${L_TEXT[i]}"
        rung_links "$i"
        for ((s = 0; s < ${#K_NAME[@]}; s++)); do
            echo "     ${K_NAME[s]} (${K_URL[s]})"
            [ -z "${K_NOTE[s]}" ] || echo "       ${K_NOTE[s]}"
        done
    done
    echo
    echo "Learning paths are new. Your feedback helps a lot (needs a free GitHub account):"
    echo "  $FEEDBACK"
}

# ============================================================================
# DIALOGS
# ============================================================================

# Height of the terminal (24 when it cannot be told)
term_rows() {
    local rows
    rows=$(stty size </dev/tty 2>/dev/null | cut -d' ' -f1) || rows=""
    case "$rows" in ''|*[!0-9]*) rows=24 ;; esac
    echo "$rows"
}

# A menu sized so its prompt is visible (whiptail cuts what does not fit),
# like show_menu in the RasQberry menu; `--` keeps an item from being read
# as an option (R-024).
# Usage: lp_menu TITLE PROMPT OK_BUTTON CANCEL_BUTTON DEFAULT TAG ITEM ...
lp_menu() {
    local title="$1" prompt="$2" ok="$3" cancel="$4" default="$5"
    shift 5
    local items=$(($# / 2)) lines rows height list
    lines=$(printf '%s\n' "$prompt" | fold -s -w $((WIDTH - 4)) | wc -l)
    rows=$(term_rows)
    list=$items
    height=$((lines + items + 7))
    if [ "$height" -gt "$rows" ]; then
        height=$rows
        list=$((rows - lines - 7))
        [ "$list" -lt 2 ] && list=2
    fi
    whiptail --title "$title" --notags ${default:+--default-item "$default"} \
        --ok-button "$ok" --cancel-button "$cancel" \
        --menu "$prompt" "$height" "$WIDTH" "$list" -- "$@" 3>&1 1>&2 2>&3
}

pause() {
    echo
    read -rp "${1:-Press Enter to go back.} " _ || true
}

# The invitation every beta demo gives (rq_beta_notice), for the paths
feedback_notice() {
    echo "Learning paths are new: please tell us what works and what doesn't."
    echo "Your feedback helps a lot (needs a free GitHub account): ${FEEDBACK}${1:+/$1}"
}

# The browser opens maximised over this window (#15): say where it is now.
# Only when a browser opened (not over SSH).
back_hint() {
    if check_display && _rq_find_browser >/dev/null; then
        echo "$RQ_BROWSER_BACK_HINT"
    fi
    return 0
}

# The feedback form: in the browser on the desktop, its address over SSH
# (a long address in a terminal is hard to use, #30). It is a GitHub issue
# form, so the labels say it needs an account (#11).
# Usage: open_feedback [PATH_ID]
open_feedback() {
    clear 2>/dev/null || true
    feedback_notice "${1:-}"
    rq_show_url "${FEEDBACK}${1:+/$1}"
    back_hint
    pause "Press Enter to go back."
}

# The window's title (R-135). A demo started from a step sets its own, so
# it is set again when the demo is back (#30).
set_title() {
    [ -t 1 ] && printf '\033]0;%s\007' "Learning paths"
    return 0
}

# Open a page: the browser on the desktop, the address over SSH
# Usage: open_page NAME URL
open_page() {
    clear 2>/dev/null || true
    echo "$1: $2"
    rq_show_url "$2"
    back_hint
    pause "Press Enter to go back."
}

# ============================================================================
# KEEP GOING AND WHERE TO GO NEXT
# ============================================================================

# Where to go next: six rungs from playing to building your own; a rung
# shows its links, and a link opens its page.
show_ladder() {
    local r k choice last="" prompt
    ladder_info
    [ "${#L_RUNG[@]}" -gt 0 ] || return 0
    while true; do
        set --
        for ((r = 0; r < ${#L_RUNG[@]}; r++)); do
            set -- "$@" "r$r" "$((r + 1)) ${L_RUNG[r]}: ${L_TEXT[r]}"
        done
        choice=$(lp_menu "RasQberry: Where to Go Next" \
            "From playing to building your own. Pick a step for its links." \
            "Select" "Back" "$last" "$@") || return 0
        last="$choice"
        r="${choice#r}"
        rung_links "$r"
        local klast=""
        while true; do
            prompt="${L_RUNG[r]}: ${L_TEXT[r]}"
            for ((k = 0; k < ${#K_NAME[@]}; k++)); do
                [ -n "${K_NOTE[k]}" ] && prompt+=$'\n\n'"${K_NOTE[k]}"
            done
            set --
            for ((k = 0; k < ${#K_NAME[@]}; k++)); do
                set -- "$@" "k$k" "Open ${K_NAME[k]}"
            done
            choice=$(lp_menu "RasQberry: ${L_RUNG[r]}" "$prompt" "Open" "Back" "$klast" "$@") || break
            klast="$choice"
            k="${choice#k}"
            open_page "${K_NAME[k]}" "${K_URL[k]}"
        done
    done
}

# Keep going after path INDEX: its next entries (another path or a page)
# and Where to go next. Picking a path sets JUMP to it and returns.
keep_going() {
    local i="$1" e choice last="" prompt
    path_info "$i"
    next_info "$i"
    prompt="Keep going after \"$P_TITLE\":"
    set --
    for ((e = 0; e < ${#N_KIND[@]}; e++)); do
        prompt+=$'\n\n'"${N_NAME[e]}: ${N_WHY[e]}"
        if [ "${N_KIND[e]}" = path ]; then
            set -- "$@" "n$e" "Next path: ${N_NAME[e]}"
        else
            set -- "$@" "n$e" "Open ${N_NAME[e]}"
        fi
    done
    set -- "$@" more "More ideas: where to go next" feedback "Tell us how it went (needs a free GitHub account)"
    while true; do
        choice=$(lp_menu "RasQberry: Keep Going" "$prompt" "Select" "Done" "$last" "$@") || return 0
        last="$choice"
        case "$choice" in
            more) show_ladder ;;
            feedback) open_feedback "$P_ID" ;;
            n*)
                e="${choice#n}"
                if [ "${N_KIND[e]}" = path ]; then
                    JUMP="${N_TARGET[e]}"
                    return 0
                fi
                open_page "${N_NAME[e]}" "${N_TARGET[e]}"
                ;;
        esac
    done
}

# ============================================================================
# A PATH, STEP BY STEP
# ============================================================================

# Start a step: a demo through the engine, a tool, or a page in the browser.
# The engine prints why a demo could not start; keep that on the screen and
# return 1, so the step offers Start again.
start_step() {
    clear 2>/dev/null || true
    # the demo engine's usage count says where the start came from
    local RQ_DEMO_HOW=learning-path
    export RQ_DEMO_HOW
    if [ -n "$S_DEMO" ]; then
        local rc=0
        if [ -n "$S_VARIANT" ]; then
            "$SCRIPT_DIR/rq_demo_run.sh" "$S_DEMO" "$S_VARIANT" || rc=$?
        else
            "$SCRIPT_DIR/rq_demo_run.sh" "$S_DEMO" || rc=$?
        fi
        # finished, or stopped with Ctrl+C (130) / closed (129, 143)
        case "$rc" in 0|129|130|143) return 0 ;; esac
    elif [ -n "$S_COMMAND" ]; then
        # only RasQberry's own tools next to this script
        case "$S_COMMAND" in
            rq_*.sh) ;;
            *) die "Not a RasQberry tool: $S_COMMAND" ;;
        esac
        [ -x "$SCRIPT_DIR/$S_COMMAND" ] || die "$S_NAME is not on this Pi ($S_COMMAND)"
        "$SCRIPT_DIR/$S_COMMAND" && return 0
    else
        echo "$S_NAME: $S_URL"
        rq_show_url "$S_URL"
        back_hint
        pause "Press Enter to go back to the learning path."
        return 0
    fi
    pause "It stopped with an error (see above). Press Enter to go back to the learning path."
    return 1
}

# Walk path INDEX from the step it was left at. Done leaves it (the step is
# remembered while this window is open); Finish after the last step says so,
# invites feedback and offers Keep going (which may set JUMP to another path).
walk_path() {
    local i="$1" s default choice prompt start next back
    path_info "$i"
    s="${LAST_STEP[i]:-0}"
    default="start"
    # Anonymous usage count: the path's first step opened
    if [ "$s" -eq 0 ]; then
        rq_count_event learning-path "$P_ID" start
    fi
    while true; do
        step_info "$i" "$s"
        prompt=""
        [ "$s" -eq 0 ] && prompt="$P_GOAL"$'\n\n'
        prompt+="Step $((s + 1)) of $P_STEPS: $S_NAME"$'\n\n'"Try: $S_TRY"$'\n'"Notice: $S_NOTICE"
        if [ -n "$S_URL" ]; then start="Open $S_NAME"; else start="Start $S_NAME"; fi
        if [ $((s + 1)) -lt "$P_STEPS" ]; then
            next="Next step: $(step_info "$i" $((s + 1)); echo "$S_NAME")"
        else
            next="Finish this path"
        fi
        set -- start "$start" next "$next"
        if [ "$s" -gt 0 ]; then
            back="Back to step $s: $(step_info "$i" $((s - 1)); echo "$S_NAME")"
            set -- "$@" back "$back"
        fi
        choice=$(lp_menu "RasQberry: $P_TITLE (beta)" "$prompt" "Select" "Done" "$default" "$@") || {
            LAST_STEP[i]=$s
            return 0
        }
        case "$choice" in
            start)
                if start_step; then default="next"; else default="start"; fi
                set_title
                ;;
            next)
                if [ $((s + 1)) -lt "$P_STEPS" ]; then
                    s=$((s + 1))
                    default="start"
                else
                    LAST_STEP[i]=0
                    rq_count_event learning-path "$P_ID" finish
                    clear 2>/dev/null || true
                    echo "That was the last step of \"$P_TITLE\". Well done!"
                    echo
                    feedback_notice "$P_ID"
                    pause "Press Enter to keep going."
                    keep_going "$i"
                    return 0
                fi
                ;;
            back)
                s=$((s - 1))
                default="start"
                ;;
        esac
    done
}

# ============================================================================
# MAIN
# ============================================================================

if [ "$MODE" = "--list" ] || ! command -v whiptail >/dev/null 2>&1 || [ ! -t 0 ]; then
    list_paths
    exit 0
fi

set_title

# Ctrl+C stops the running demo and comes back here (a handler, not an
# ignored signal: the demo must still get it)
trap ':' INT

CLOSE="Close"
[ "$MODE" = "--menu" ] && CLOSE="Back"

declare -a LAST_STEP=()
JUMP=""
last=""
while true; do
    set --
    n=$(path_count)
    for ((i = 0; i < n; i++)); do
        path_info "$i"
        # "First 15 minutes: visitors at a stand, 15 min"
        audience="$(printf '%s' "${P_AUDIENCE:0:1}" | tr '[:upper:]' '[:lower:]')${P_AUDIENCE:1}"
        set -- "$@" "$i" "$P_TITLE: $audience, $P_MINUTES min"
    done
    set -- "$@" ladder "Where to go next" feedback "Tell us how it went (needs a free GitHub account)"
    choice=$(lp_menu "RasQberry: Learning Paths (beta)" \
        "Short tours through the demos. Each step says what to try and what to notice, and starts the demo for you." \
        "Select" "$CLOSE" "$last" "$@") || break
    last="$choice"
    case "$choice" in
        feedback) open_feedback ;;
        ladder) show_ladder ;;
        *)
            # Keep going may lead from one path to the next (JUMP)
            JUMP="$choice"
            while [ -n "$JUMP" ]; do
                choice="$JUMP"
                JUMP=""
                walk_path "$choice"
            done
            last="$choice"
            ;;
    esac
done
exit 0
