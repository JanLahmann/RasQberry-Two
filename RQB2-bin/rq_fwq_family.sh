#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Fun with Quantum family
# ============================================================================
# Description: A menu of the Fun with Quantum family, read from family.json of
#   the installed Fun-with-Quantum version. Projects that are RasQberry demos
#   start here through the demo engine; the others open their website (needs
#   the internet). "About the family" opens a page that works offline.
# Usage: rq_fwq_family.sh   (normally: rq_demo_run.sh fun-with-quantum family)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

load_rqb2_env
verify_env_vars REPO USER_HOME

DEMO_DIR=$(get_demo_dir "fun-with-quantum")
FWQ_PY=(python3 "$SCRIPT_DIR/rq_fwq.py")
TITLE="Fun with Quantum family"

[ -f "$DEMO_DIR/family/family.json" ] \
    || die "The Fun with Quantum family list is missing. Update Fun with Quantum (Quantum Demos > Manage demos > Update demos)."

items=$("${FWQ_PY[@]}" family-menu --path "$DEMO_DIR") || die "Could not read the Fun with Quantum family list."
declare -A ACTION=()
args=()
while IFS=$'\t' read -r tag label action; do
    [ -n "$tag" ] || continue
    ACTION[$tag]="$action"
    args+=("$tag" "$label")
done <<< "$items"

last=""
while true; do
    if ! command -v whiptail >/dev/null 2>&1; then
        printf '%s\n' "$items" | cut -f2
        exit 0
    fi
    choice=$(whiptail --title "$TITLE" --notags ${last:+--default-item "$last"} \
        --ok-button "Select" --cancel-button "Back" --menu "Start a project on this Pi, or open its website:" \
        20 78 12 "${args[@]}" 3>&1 1>&2 2>&3) || break
    last="$choice"
    action="${ACTION[$choice]:-}"
    case "$action" in
        page)
            page=$("${FWQ_PY[@]}" family-page --path "$DEMO_DIR") || { warn "Could not write the page."; continue; }
            rq_show_url "file://$page"
            check_display || { read -rp "Press Enter to go back. " _ || true; }
            ;;
        demo:*)
            "$SCRIPT_DIR/rq_demo_run.sh" "${action#demo:}" || {
                echo; read -rp "It stopped with an error (see above). Press Enter to continue. " _ || true; }
            ;;
        url:*)
            if rq_reachable "${action#url:}"; then
                rq_show_url "${action#url:}"
                check_display || { read -rp "Press Enter to go back. " _ || true; }
            else
                whiptail --title "$TITLE" --msgbox \
                    "This website needs the internet, and the Pi is offline.\n\n${action#url:}" 10 70
            fi
            ;;
    esac
done
