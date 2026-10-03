#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: A/B images that can be installed into a slot (R-049)
# ============================================================================
# Description: The release lists behind the Slot Manager's update picker in
#   RQB2_menu.sh. Only A/B images (-ab.img.xz) are listed: the standard image
#   has no A/B layout and cannot fill a slot.
#   - "latest" reads rasqberry.org/RQB-releases.json (one request, no GitHub
#     rate limit) and defaults to this image's own channel.
#   - "list" asks the GitHub API for every release of a stream (100 per
#     page; the picker used to read page 1 only, where a beta falls off after
#     a few dozen dev builds).
#   - Every image comes with its SHA256, so the update can be checked before
#     it is written: "latest" takes ab_image_sha256 from RQB-releases.json,
#     "list" the digest GitHub computes for every release asset when it is
#     uploaded (the same value; the manifest has it only for the newest
#     release of each stream). A release whose image has no checksum is not
#     listed: it cannot be verified (H-34: older releases used to install
#     unchecked).
#
# Usage:
#   rq_ab_releases.sh channel              this image's release channel: beta, dev or stable
#   rq_ab_releases.sh latest [CHANNEL]     newest A/B image of CHANNEL (default: this image's)
#   rq_ab_releases.sh list STREAM [--repo USER/REPO]
#                                          A/B images on GitHub for STREAM (beta, dev,
#                                          stable), newest first, at most 15
#
# Output of latest and list: one line per image, tab-separated:
#   tag  ab_image_url  date (YYYY-MM-DD)  download size in bytes  sha256 of the .img.xz
#
# Streams: beta = beta-*, dev = development-* and dev-* (feature-branch
#   builds), stable = v* (main releases are tagged v{version}) and stable-*.
#
# Exit: 0 ok, 1 cannot fetch or unexpected answer, 2 nothing to offer
#   (the reason is printed on stderr, ready for a dialog)
#
# Environment overrides (tests): RQ_VERSION_FILE, RQ_RELEASES_URL,
#   RQ_RELEASES_FILE, RQ_GITHUB_RELEASES_FILE, RQ_GITHUB_API

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

VERSION_FILE="${RQ_VERSION_FILE:-/etc/rasqberry-version}"
RELEASES_URL="${RQ_RELEASES_URL:-https://rasqberry.org/RQB-releases.json}"
GITHUB_API="${RQ_GITHUB_API:-https://api.github.com}"
DEFAULT_REPO="${RQB_GIT_USER:-JanLahmann}/${REPO:-RasQberry-Two}"
MAX_LISTED=15

fail() {   # <exit code> <message>
    local rc="$1"; shift
    echo "$*" >&2
    exit "$rc"
}

own_version() {
    head -1 "$VERSION_FILE" 2>/dev/null | tr -d '[:space:]' || true
}

own_channel() {
    rq_release_channel "$(own_version)"
}

stream_regex() {
    case "$1" in
        beta)   echo '^beta-' ;;
        dev)    echo '^(development|dev)-' ;;
        stable) echo '^(v[0-9]|stable-)' ;;
        *)      fail 1 "Unknown stream: $1 (beta, dev or stable)" ;;
    esac
}

cmd_latest() {
    local channel="${1:-}" json tag line
    [ -n "$channel" ] || channel=$(own_channel)
    stream_regex "$channel" >/dev/null

    if [ -n "${RQ_RELEASES_FILE:-}" ]; then
        json=$(cat "$RQ_RELEASES_FILE")
    else
        json=$(curl -fsSL --max-time 20 "$RELEASES_URL" 2>/dev/null) \
            || fail 1 "Could not reach rasqberry.org to ask for the latest release. Check the network connection."
    fi

    tag=$(echo "$json" | jq -r --arg c "$channel" '.streams[$c].tag // empty' 2>/dev/null) \
        || fail 1 "rasqberry.org sent a release list this version does not understand."
    [ -n "$tag" ] || fail 2 "No $channel release is published yet."

    line=$(echo "$json" | jq -r --arg c "$channel" '
        .streams[$c] | select(.ab_image_url != null and .ab_image_url != "")
        | [.tag, .ab_image_url, ((.release_date // "") | .[0:10]),
           ((.ab_image_download_size // 0) | tostring), (.ab_image_sha256 // "")] | @tsv' 2>/dev/null || true)
    [ -n "$line" ] || fail 2 "The latest $channel release ($tag) has no A/B image."
    echo "$line"
}

cmd_list() {
    local stream="${1:-}" repo="$DEFAULT_REPO" regex json message
    [ -n "$stream" ] || fail 1 "Usage: $(basename "$0") list STREAM [--repo USER/REPO]"
    shift
    while [ $# -gt 0 ]; do
        case "$1" in
            --repo) repo="${2:-}"; shift 2 ;;
            *) fail 1 "Unknown option: $1" ;;
        esac
    done
    case "$repo" in
        */*) ;;
        *) fail 1 "Repository must be USER/REPO, not '$repo'" ;;
    esac
    regex=$(stream_regex "$stream")

    if [ -n "${RQ_GITHUB_RELEASES_FILE:-}" ]; then
        json=$(cat "$RQ_GITHUB_RELEASES_FILE")
    else
        json=$(curl -sSL --max-time 30 -H "Accept: application/vnd.github+json" \
            "${GITHUB_API}/repos/${repo}/releases?per_page=100" 2>/dev/null) \
            || fail 1 "Could not reach GitHub to list the releases. Check the network connection."
    fi

    # An error answer is an object with a message, not a list
    if [ "$(echo "$json" | jq -r 'type' 2>/dev/null)" != "array" ]; then
        message=$(echo "$json" | jq -r '.message // empty' 2>/dev/null || true)
        case "$message" in
            *"rate limit"*)
                fail 1 "GitHub allows 60 release lookups per hour from one network, and they are used up (common in a classroom). Try again in an hour, or install the latest release instead." ;;
            "Not Found")
                fail 1 "GitHub has no repository $repo." ;;
            "")
                fail 1 "GitHub sent an answer this version does not understand." ;;
            *)
                fail 1 "GitHub answered: $message" ;;
        esac
    fi

    echo "$json" | jq -r --arg re "$regex" --argjson max "$MAX_LISTED" '
        [ .[]
          | select((.draft // false) | not)
          | select(.tag_name | test($re))
          | . as $r
          | ([ ($r.assets // [])[] | select(.name | endswith("-ab.img.xz")) ] | .[0]) as $a
          | select($a != null)
          | (($a.digest // "") | if startswith("sha256:") then .[7:] else "" end) as $sum
          | select($sum | test("^[0-9a-f]{64}$"))
          | { tag: $r.tag_name,
              url: $a.browser_download_url,
              date: (($r.published_at // $r.created_at // "") | .[0:10]),
              size: ($a.size // 0),
              sha: $sum,
              created: ($r.created_at // "") } ]
        | sort_by(.created) | reverse | .[0:$max][]
        | [.tag, .url, .date, (.size | tostring), .sha] | @tsv'
}

case "${1:-}" in
    channel)
        own_channel ;;
    latest)
        shift
        cmd_latest "${1:-}" ;;
    list)
        shift
        cmd_list "$@" ;;
    -h|--help)
        sed -n '/^# Usage:/,/^# Environment/p' "$0" | sed 's/^# \{0,1\}//' ;;
    *)
        echo "Usage: $(basename "$0") {channel|latest [CHANNEL]|list STREAM [--repo USER/REPO]}" >&2
        exit 1 ;;
esac
