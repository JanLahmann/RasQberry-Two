#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Entangible (tangible quantum-circuit composer)
# ============================================================================
# Description: Visitors lay printed gate tiles on a printed board, a camera
#   (USB webcam or Pi camera) reads them, and the booth screen shows the
#   circuit and its simulation live. Phones on the same network join over
#   HTTPS (port 8443). Entangible runs as a system service (entangible-host)
#   behind one command in its checkout, deploy/rasqberry/entangible; this
#   launcher only calls that command (contract: docs/rasqberry-integration.md
#   in github.com/JanLahmann/entangible, pinned in rq_demo_entangible.json).
#
#   Start: (re)installs when the service is not set up or does not match the
#   checkout (after an A/B update /home is new and the demo is downloaded
#   again; the download cache on /data/rasqberry/cache/entangible makes that
#   quick), starts the service, shows the visitors' address with a QR code
#   and the camera state, and opens the booth screen. Enter, Ctrl+C or
#   closing the window stops the service again. Without a camera it starts
#   all the same and says so.
#
# Usage: rq_entangible.sh                     start (the demo engine runs it)
#        rq_entangible.sh --path DIR          set up a fresh checkout (install.post_install)
#        rq_entangible.sh --remove --path DIR remove the service before the checkout goes
#                                             (install.pre_remove)
# Environment: ENTANGIBLE_START_WAIT  seconds to wait for the service (default 90)
#
# Exit status: 0 ok, 130 stopped with Ctrl+C, anything else a failure.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

NAME="Entangible"
DEMO_ID="entangible"
UNIT="entangible-host"
START_WAIT="${ENTANGIBLE_START_WAIT:-90}"

load_rqb2_env
verify_env_vars REPO USER_HOME

STATE_DIR="$USER_HOME/.cache/rasqberry"
# What RasQberry set up last: "<checkout commit> <web bundle tag>"
STAMP="$STATE_DIR/entangible.rasqberry"
LOG_FILE="$STATE_DIR/entangible.log"          # Entangible's own log
BOOTH_PROFILE="$STATE_DIR/entangible-browser"  # the booth screen's browser profile

# ----------------------------------------------------------------------------
# The entangible command
# ----------------------------------------------------------------------------
ent_cmd() { echo "$1/deploy/rasqberry/entangible"; }

# The web bundle the checkout expects (deploy/rasqberry/BUNDLE_TAG)
bundle_tag() {
    tr -d ' \t\r\n' < "$1/deploy/rasqberry/BUNDLE_TAG" 2>/dev/null || true
}

checkout_commit() {
    git -C "$1" rev-parse HEAD 2>/dev/null || echo unknown
}

# Why the entangible command failed, from its exit code (contract)
failure_text() {
    case "$1" in
        2) echo "$NAME did not accept RasQberry's call (exit 2): this RasQberry and the pinned $NAME version do not fit together." ;;
        3) echo "$NAME is not set up on this Pi (exit 3)." ;;
        4) echo "$NAME could not download what it needs (exit 4). Connect the Pi to the internet and try again." ;;
        5) echo "$NAME needs Raspberry Pi OS Trixie (64-bit) on a Raspberry Pi 4 or 5 (exit 5)." ;;
        *) echo "$NAME failed (exit $1)." ;;
    esac
}

# Run `entangible install` in checkout DIR; on success record what was set
# up. Returns the command's exit code (130: stopped with Ctrl+C).
ent_install() {
    local dir="$1" rc=0
    info "Setting up $NAME: its web app, a Python environment and the $UNIT service."
    info "This takes a few minutes; later starts are quick."
    "$(ent_cmd "$dir")" install || rc=$?
    if [ "$rc" -eq 0 ]; then
        mkdir -p "$STATE_DIR" 2>/dev/null || true
        printf '%s %s\n' "$(checkout_commit "$dir")" "$(bundle_tag "$dir")" > "$STAMP" 2>/dev/null || true
        return 0
    fi
    if [ "$rc" -eq 130 ]; then
        info "The setup of $NAME was stopped."
    else
        warn "$(failure_text "$rc") Details: $LOG_FILE"
    fi
    return "$rc"
}

# ----------------------------------------------------------------------------
# --path DIR: set up the checkout the demo engine has just fetched
# --remove --path DIR: take the service away before the checkout is removed
# ----------------------------------------------------------------------------
case "${1:-}" in
    --path)
        [ -n "${2:-}" ] || die "--path needs the checkout directory"
        [ -x "$(ent_cmd "$2")" ] || die "Not an Entangible checkout: $2"
        rc=0
        ent_install "$2" || rc=$?
        exit "$rc"
        ;;
    --remove)
        [ "${2:-}" = "--path" ] && [ -n "${3:-}" ] || die "Usage: $(basename "$0") --remove --path DIR"
        if [ -x "$(ent_cmd "$3")" ]; then
            info "Removing the $UNIT service and $NAME's settings..."
            # --purge: also the settings, venv, web bundle and certificate.
            # The download cache on /data stays: it makes a later install quick.
            "$(ent_cmd "$3")" uninstall --purge || warn "$NAME's own uninstall failed; removing its files anyway."
        fi
        rm -f "$STAMP" 2>/dev/null || true
        rm -rf "$BOOTH_PROFILE" 2>/dev/null || true
        exit 0
        ;;
    "") ;;
    *) die "Usage: $(basename "$0") [--path DIR | --remove --path DIR]" ;;
esac

# ----------------------------------------------------------------------------
# Start
# ----------------------------------------------------------------------------
rq_demo_header "$NAME"

DEMO_DIR=$(get_demo_dir "$DEMO_ID")
ENT=$(ent_cmd "$DEMO_DIR")
[ -x "$ENT" ] || die "$NAME is not downloaded. Start it from its desktop icon or RasQberry menu > Quantum Demos > Big projects, which ask before downloading."

# The checkout is the version this release pins (or the one chosen under
# Update demos)? A different one still runs.
PIN=$(rq_demo_ref "$DEMO_ID")
HEAD=$(checkout_commit "$DEMO_DIR")
if [ -n "$PIN" ] && [ "$HEAD" != "$PIN" ]; then
    warn "This $NAME (${HEAD:0:7}) is not the version this RasQberry uses (${PIN:0:7}). To change it: Quantum Demos > Manage demos > Update demos."
fi

# One line of JSON from `entangible status`; "{}" when there is none
STATUS_JSON="{}"
ent_status() {
    local out=""
    out=$("$ENT" status 2>/dev/null) || out=""
    out=$(printf '%s\n' "$out" | head -1)
    if printf '%s' "$out" | jq -e 'type == "object"' >/dev/null 2>&1; then
        STATUS_JSON="$out"
    else
        STATUS_JSON="{}"
    fi
}

# A field of the status: true/false/null, a string, or "" when absent
st() {
    jq -r "($1) as \$v | if \$v == null then \"null\" else (\$v | tostring) end" \
        <<< "$STATUS_JSON" 2>/dev/null || echo null
}

# Set up (again) when the service is missing (first start, A/B update, an
# uninstall), the web bundle is not the one the checkout expects, or the
# checkout changed since the last setup (Update demos)
needs_install() {
    [ "$(st .installed)" = "true" ] || return 0
    [ "$(st .bundle)" = "$(bundle_tag "$DEMO_DIR")" ] || return 0
    [ "$(cat "$STAMP" 2>/dev/null)" = "$HEAD $(bundle_tag "$DEMO_DIR")" ] || return 0
    return 1
}

ent_status
if needs_install; then
    # Nothing set up at all: the download question first (the engine asked
    # already when it has just downloaded the checkout)
    if [ "$(st .installed)" != "true" ]; then
        rq_require_demo_consent "$DEMO_ID"
    fi
    rc=0
    ent_install "$DEMO_DIR" || rc=$?
    case "$rc" in
        0) ;;
        130) exit 130 ;;
        *) die "$(failure_text "$rc") Details: $LOG_FILE" ;;
    esac
    ent_status
fi

# ----------------------------------------------------------------------------
# From here on the service goes with this window
# ----------------------------------------------------------------------------
STOP_SERVICE=""
cleanup() {
    set +e
    trap '' HUP INT TERM   # a closed window: still stop the service
    close_booth_screen
    if [ -n "$STOP_SERVICE" ]; then
        STOP_SERVICE=""
        { info "Stopping $NAME..."; } 2>/dev/null || true
        rq_run_detached "$ENT" stop
        { info "$NAME stopped."; } 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

BOOTH_OPEN=""
close_booth_screen() {
    [ -n "$BOOTH_OPEN" ] || return 0
    BOOTH_OPEN=""
    pkill -f -- "--user-data-dir=$BOOTH_PROFILE" 2>/dev/null || true
}

if [ "$(st .running)" != "true" ]; then
    info "Starting $NAME..."
    rc=0
    "$ENT" start >/dev/null || rc=$?
    case "$rc" in
        0) ;;
        130) exit 130 ;;
        *) die "$(failure_text "$rc") Details: $LOG_FILE" ;;
    esac
fi
# Started here or already running (the service also starts with the Pi):
# ending the demo stops it either way, like the Docker demos
STOP_SERVICE=1

info "Waiting for $NAME to answer..."
deadline=$((SECONDS + START_WAIT))
while :; do
    ent_status
    [ "$(st .health)" = "ok" ] && break
    if [ "$(st .running)" != "true" ]; then
        die "$NAME stopped while starting. Its log: journalctl -u $UNIT -n 50"
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
        die "$NAME did not answer within $START_WAIT seconds. Its log: journalctl -u $UNIT -n 50"
    fi
    sleep 1
done

KIOSK_URL=$(st .urls.kiosk)
VISITOR_URL=$(st .urls.visitor)
SOURCE=$(st .source)

# The camera, from status.ready (null: the service did not say)
camera_text() {
    case "$(st .ready)" in
        true)  echo "Camera: connected ($SOURCE)." ;;
        false) echo "Camera: none found ($SOURCE). $NAME runs without one, but reads no tiles."
               echo "  Connect a USB webcam, or set QAMPOSER_SOURCE=picamera2 in /etc/default/entangible"
               echo "  for the Pi camera, then end $NAME and start it again." ;;
        *)     echo "Camera: unknown ($SOURCE)." ;;
    esac
}

# A QR code of the visitors' address: 15 lines, above the stop line
print_qr() {
    command -v qrencode >/dev/null 2>&1 || return 0
    echo "Phones can scan this code:"
    qrencode -t ANSIUTF8 -m 2 "$1" 2>/dev/null || true
}

ON_NETWORK=yes
case "$VISITOR_URL" in
    ""|null|*://localhost*|*://127.*) ON_NETWORK="" ;;
esac

echo
echo "$NAME is running."
echo
if [ -n "$ON_NETWORK" ]; then
    echo "Visitors open this address on a phone on the same network as this Pi:"
    echo "    $VISITOR_URL"
    echo "  Phones show a certificate warning once: tap Advanced, then Proceed."
else
    echo "This Pi is not on a network, so phones cannot join. The booth screen works."
fi
echo "Booth screen on this Pi: $KIOSK_URL"
echo
camera_text
echo

# The booth screen: a browser of its own (its own profile), so that it
# accepts the service's self-signed certificate (a running desktop Chromium
# ignores new flags) and closes when the demo ends
open_booth_screen() {
    local browser user_name
    browser=$(command -v chromium || command -v chromium-browser || true)
    if [ -z "$browser" ]; then
        info "No browser found. Open the booth screen yourself: $KIOSK_URL"
        return 0
    fi
    mkdir -p "$BOOTH_PROFILE" 2>/dev/null || true
    local -a cmd=("$browser" --user-data-dir="$BOOTH_PROFILE" --password-store=basic
                  --no-first-run --noerrdialogs --disable-session-crashed-bubble
                  --ignore-certificate-errors --test-type --start-fullscreen "$KIOSK_URL")
    user_name=$(get_user_name)
    if [ "$(id -u)" = "0" ] && [ "$user_name" != "root" ]; then
        cmd=(sudo -u "$user_name" -H DISPLAY="${DISPLAY:-:0}" -- "${cmd[@]}")
    fi
    info "Opening the booth screen (F11 leaves full screen)..."
    # a session of its own: no hangup from this window reaches it
    if command -v setsid >/dev/null 2>&1; then
        setsid "${cmd[@]}" </dev/null >/dev/null 2>&1 &
    else
        nohup "${cmd[@]}" </dev/null >/dev/null 2>&1 &
    fi
    BOOTH_OPEN=1
}

if check_display || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    open_booth_screen
else
    echo "No screen in this session: open the booth screen on the Pi's own display,"
    echo "or the visitors' address above in any browser on the network."
    echo
fi

[ -n "$ON_NETWORK" ] && print_qr "$VISITOR_URL"

# Without a terminal nobody can press Enter: the service keeps running
if ! { [ -t 0 ] && [ -t 1 ]; }; then
    STOP_SERVICE=""
    BOOTH_OPEN=""
    info "$NAME keeps running. To stop it: start $NAME again and press Enter, or run: $ENT stop"
    exit 0
fi

rq_stop_hint "$NAME"
[ -z "$BOOTH_OPEN" ] || echo "The booth screen covers this window: to get back here, click it in the taskbar."
# Until Enter, or until the service is stopped elsewhere
while :; do
    rc=0
    rq_read_deferred -r -t 3 _ || rc=$?
    [ "$rc" -eq 0 ] && break           # Enter
    [ "$rc" -gt 128 ] || break         # no more input
    ent_status
    if [ "$(st .running)" != "true" ]; then
        STOP_SERVICE=""
        info "$NAME was stopped."
        break
    fi
done
exit 0
