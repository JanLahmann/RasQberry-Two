#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Fun with Quantum website (offline copy)
# ============================================================================
# Description: Serves the copy of fun-with-quantum.org that was downloaded
#   with the notebooks (portal/dist, the build of the pinned commit) on
#   127.0.0.1 and opens it in the browser. Without a copy (not published for
#   this version yet) it opens the online website, or the offline page.
# Usage: rq_fwq_portal.sh   (normally: rq_demo_run.sh fun-with-quantum website)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

load_rqb2_env
verify_env_vars REPO USER_HOME

DEMO_DIR=$(get_demo_dir "fun-with-quantum")
SITE="$DEMO_DIR/portal/dist"
ONLINE_URL="https://fun-with-quantum.org"
OFFLINE_PAGE="file:///usr/share/rasqberry/offline.html"
FWQ_PY=(python3 "$SCRIPT_DIR/rq_fwq.py")
SERVER_PID=""

cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM HUP

# Installed before the website was bundled: fetch it now if it is published
if [ ! -f "$SITE/index.html" ] && [ -d "$DEMO_DIR/.git" ] \
        && "${FWQ_PY[@]}" portal --check --path "$DEMO_DIR" >/dev/null 2>&1; then
    rc=0
    rq_confirm_download "Fun with Quantum website" 4 10 \
        --what "The Fun with Quantum website, to use without the internet" \
        --time "under a minute" --path "$DEMO_DIR" --url "https://github.com" \
        --intro "The Fun with Quantum website is not on this Pi yet." || rc=$?
    if [ "$rc" = 0 ]; then
        "${FWQ_PY[@]}" portal --path "$DEMO_DIR" || warn "Opening the online website instead."
    fi
fi

if [ ! -f "$SITE/index.html" ]; then
    if rq_reachable "$ONLINE_URL"; then
        info "No copy of the website for this version yet: opening $ONLINE_URL"
        rq_show_url "$ONLINE_URL"
    else
        info "No copy of the website on this Pi, and no internet."
        rq_show_url "$OFFLINE_PAGE"
    fi
    exit 0
fi

port=$(find_available_port 8100)
url="http://127.0.0.1:${port}/"
info "Starting the Fun with Quantum website on $url ..."
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$SITE" >/dev/null 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 30); do
    curl -sf -o /dev/null "$url" && break
    kill -0 "$SERVER_PID" 2>/dev/null || die "The web server for the Fun with Quantum website did not start."
    sleep 0.5
done
rq_show_url "$url" "$port"

echo
echo "Fun with Quantum website: $url (games in the browser work without the internet)"
if [ -t 0 ]; then
    echo "Press Enter or close this window to stop it."
    read -r || true
else
    wait "$SERVER_PID" 2>/dev/null || true
fi
