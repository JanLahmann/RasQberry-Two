#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Is a newer image available? (#139)
# ============================================================================
# Description: Compares this image (/etc/rasqberry-version) with the latest
#   release of the same channel in rasqberry.org/RQB-releases.json
#   (rq_release_channel in rq_common.sh):
#     beta-*                    -> beta
#     development-*, dev-*      -> dev
#     v1.2.3, 1.2.3, stable-*   -> stable
#     anything else             -> no known channel: compared with dev
#   Release tags end in YYYY-MM-DD-HHMMSS, which is what gets compared.
#   A release withdrawn in rasqberry.org/RQB-release-controls.json is not
#   offered (#242).
#
# Usage:
#   rq_update_check.sh            check now, print the result
#   rq_update_check.sh --refresh  check now, print the result and store it for
#                                 --notice (root; daily timer and the menu's CHECK)
#   rq_update_check.sh --notice   print one line if the stored result says an update exists
#                                 (the login message uses rq_release_notice.py now, #242)
#
# Exit: 0 up to date (or nothing to compare), 10 newer image available, 1 error.
#
# Environment overrides (tests): RQ_VERSION_FILE, RQ_RELEASES_URL, RQ_RELEASES_FILE,
#   RQ_UPDATE_STATE, RQ_RELEASE_CONTROLS_FILE, RQ_RELEASE_CONTROLS_URL

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

VERSION_FILE="${RQ_VERSION_FILE:-/etc/rasqberry-version}"
RELEASES_URL="${RQ_RELEASES_URL:-https://rasqberry.org/RQB-releases.json}"
STATE_FILE="${RQ_UPDATE_STATE:-/var/lib/rasqberry/update-available}"

stamp_of() { echo "$1" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}' | tail -1; }

channel_of() { rq_update_channel "$1"; }    # rq_common.sh: unknown follows dev

fetch_releases() {
    if [ -n "${RQ_RELEASES_FILE:-}" ]; then
        cat "$RQ_RELEASES_FILE"
    else
        curl -fsSL --max-time 20 "$RELEASES_URL"
    fi
}

# Prints the result; returns 0 / 10 / 1 as documented above
check() {
    local current channel json latest cur_stamp new_stamp note=""
    [ -r "$VERSION_FILE" ] || { echo "Cannot read $VERSION_FILE"; return 1; }
    current=$(head -1 "$VERSION_FILE" | tr -d '[:space:]')
    channel=$(channel_of "$current")

    json=$(fetch_releases 2>/dev/null) || {
        printf '%-15s %s\n' "This image:" "$current"
        echo "Could not reach rasqberry.org to ask for the latest release."
        echo "Check the network connection and try again."
        return 1
    }
    latest=$(echo "$json" | jq -r --arg c "$channel" '.streams[$c].tag // empty' 2>/dev/null) \
        || { echo "Unexpected release list format"; return 1; }

    if [ -z "$latest" ]; then
        printf '%-15s %s\n' "This image:" "$current"
        echo "No $channel release is published yet."
        return 0
    fi
    case "$(rq_release_channel "$current")" in
        unknown) note=" (this image belongs to no release stream; comparing with the latest development release)" ;;
        *) case "$current" in
               dev-*) note=" (this image was built from a feature branch; comparing with the latest development release)" ;;
           esac ;;
    esac

    cur_stamp=$(stamp_of "$current")
    new_stamp=$(stamp_of "$latest")
    printf '%-15s %s\n' "This image:" "$current"
    printf '%-15s %s\n' "Latest $channel:" "$latest$note"
    # A development image follows the dev channel, but a newer beta is worth
    # one line (H-34: CHECK said nothing about it). Not an install offer: the
    # beta is another channel (Slot Manager -> Install an update -> Other).
    local beta beta_stamp beta_line=""
    if [ "$channel" = "dev" ]; then
        beta=$(echo "$json" | jq -r '.streams.beta.tag // empty' 2>/dev/null || true)
        beta_stamp=$(stamp_of "$beta")
        if [ -n "$beta_stamp" ] && [ -n "$cur_stamp" ] && [[ "$beta_stamp" > "$cur_stamp" ]]; then
            beta_line=$(printf '%-15s %s' "Newer beta:" "$beta (beta channel)")
        fi
    fi
    if [ -n "$cur_stamp" ] && [ -n "$new_stamp" ] && [[ "$new_stamp" > "$cur_stamp" ]]; then
        [ -n "$beta_line" ] && echo "$beta_line"
        local reason
        if reason=$(rq_release_withdrawn "$latest"); then
            echo "$latest was withdrawn: $reason"
            echo "There is no newer image to install."
            return 0
        fi
        echo "A newer image is available."
        return 10
    fi
    [ -n "$beta_line" ] && echo "$beta_line"
    echo "This image is up to date."
    return 0
}

case "${1:-}" in
    "")
        rc=0; check || rc=$?; exit "$rc" ;;
    --refresh)
        # Prints the result too: the menu's CHECK shows it (R-048 - it used
        # to print nothing, so the box was empty when up to date or offline)
        out=$(check) && rc=0 || rc=$?
        echo "$out"
        mkdir -p "$(dirname "$STATE_FILE")"
        if [ "$rc" -eq 10 ]; then
            echo "$out" | sed -n 's/^Latest [a-z]*: *//p' | head -n 1 | cut -d' ' -f1 > "$STATE_FILE"
        elif [ "$rc" -eq 0 ]; then
            rm -f "$STATE_FILE"
        fi
        exit "$rc" ;;
    --notice)
        [ -s "$STATE_FILE" ] || exit 0
        # Two lines that fit 80 columns (R-090: one line broke mid-word)
        echo "A newer RasQberry Two image is available: $(cat "$STATE_FILE")"
        echo "Update: sudo raspi-config -> 0 RasQberry -> Software & Image Updates"
        exit 0 ;;
    -h|--help)
        sed -n '/^# Usage:/,/^# Exit:/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)
        echo "Unknown option: $1" >&2; exit 1 ;;
esac
