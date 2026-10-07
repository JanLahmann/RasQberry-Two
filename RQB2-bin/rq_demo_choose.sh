#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: choose a demo's variant (desktop icon chooser)
# ============================================================================
# Description: The desktop and Applications menu counterpart of the RasQberry
#   menu's variant submenu (menu.variant_menu): one icon opens a list of the
#   demo's variants, e.g. Fun with Quantum's games, its website and the family
#   (item 11). Each runs through the demo engine (rq_demo_run.sh <id>
#   <variant>); the list comes back afterwards, Back/Esc closes it. Without
#   whiptail or a terminal it starts the first variant.
# Usage: rq_demo_choose.sh <demo-id>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

[ $# -eq 1 ] || die "Usage: $(basename "$0") <demo-id>"
DEMO_ID="$1"
command -v jq >/dev/null 2>&1 || die "jq is required but not installed"

load_rqb2_env
MANIFEST=$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$DEMO_ID") \
    || die "No demo '$DEMO_ID' on this Pi"
NAME=$(jq -r '.name // empty' "$MANIFEST")

TAGS=()
ITEMS=()
while IFS=$'\t' read -r vid vname vmaturity; do
    [ -n "$vid" ] || continue
    [ "$vmaturity" = "beta" ] && vname="$vname (beta)"
    TAGS+=("$vid")
    ITEMS+=("$vid" "$vname")
done < <(jq -r '.variants[]? | [.id, .name, (.maturity // "")] | @tsv' "$MANIFEST")
[ ${#TAGS[@]} -gt 0 ] || exec "$SCRIPT_DIR/rq_demo_run.sh" "$DEMO_ID"

# The window's title: the demo's name (R-135)
[ -t 1 ] && printf '\033]0;%s\007' "$NAME"

if ! command -v whiptail >/dev/null 2>&1 || [ ! -t 0 ]; then
    exec "$SCRIPT_DIR/rq_demo_run.sh" "$DEMO_ID" "${TAGS[0]}"
fi

# Ctrl+C stops the running entry and returns to the list (a handler, not an
# ignored signal: the demo must still get it)
trap ':' INT

last=""
while true; do
    rows=$(( ${#TAGS[@]} < 12 ? ${#TAGS[@]} : 12 ))
    choice=$(whiptail --title "RasQberry: $NAME" --notags ${last:+--default-item "$last"} \
        --ok-button "Start" --cancel-button "Close" --menu "Choose:" \
        $(( rows + 8 )) 74 "$rows" "${ITEMS[@]}" 3>&1 1>&2 2>&3) || break
    last="$choice"
    clear 2>/dev/null || true
    rc=0
    "$SCRIPT_DIR/rq_demo_run.sh" "$DEMO_ID" "$choice" || rc=$?
    case "$rc" in
        # finished, or stopped with Ctrl+C (130) / closed (129, 143): back
        # to the list. Ctrl+C said "It stopped with an error" (Fun with
        # Quantum, user tests 2026-10-05 and 2026-10-07).
        0|129|130|143) ;;
        *)
            echo
            read -rp "It stopped with an error (see above). Press Enter to go back to the list. " _ || true
            ;;
    esac
done
