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
#   The service is installed on demand (install --no-enable: not at boot).
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
# Environment: ENTANGIBLE_START_WAIT    seconds to wait for the service (default 90)
#              ENTANGIBLE_READY_SETTLE  seconds the camera state must hold (default 5)
#              RQ_DATA_DIR              the DATA partition (default /data)
#
# Exit status: 0 ok, 130 stopped with Ctrl+C, anything else a failure.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

NAME="Entangible"
DEMO_ID="entangible"
UNIT="entangible-host"
START_WAIT="${ENTANGIBLE_START_WAIT:-90}"
READY_SETTLE="${ENTANGIBLE_READY_SETTLE:-5}"
DATA_DIR="${RQ_DATA_DIR:-/data}"

load_rqb2_env
verify_env_vars REPO USER_HOME

STATE_DIR="$USER_HOME/.cache/rasqberry"
# What RasQberry set up last: "<checkout commit> <web bundle tag>"
STAMP="$STATE_DIR/entangible.rasqberry"
LOG_FILE="$STATE_DIR/entangible.log"          # Entangible's own log
# (the window's transcript is entangible-window.log, rq_hold_on_error.sh)
UV_MARK="$STATE_DIR/entangible.uv"             # uv was installed for Entangible
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

# Entangible's download cache on the DATA partition of an A/B card
# (/data/rasqberry/cache/entangible): it survives an A/B update, so the
# install afterwards needs no network. /data/rasqberry belongs to root
# (rq_after_update.sh checks that), so the cache directory is made for the
# desktop user here, with sudo. Without a DATA partition, or without sudo,
# Entangible installs without a cache.
prepare_cache() {
    local dir="$DATA_DIR/rasqberry/cache/entangible" user
    [ -d "$DATA_DIR/rasqberry" ] || return 0
    [ -w "$dir" ] && return 0
    user=$(get_user_name)
    if [ "$(id -u)" = "0" ]; then
        install -d -m 755 "$DATA_DIR/rasqberry/cache" 2>/dev/null \
            && install -d -m 755 -o "$user" -g "$(id -gn "$user")" "$dir" 2>/dev/null && return 0
    elif sudo -n install -d -m 755 "$DATA_DIR/rasqberry/cache" 2>/dev/null \
            && sudo -n install -d -m 755 -o "$user" -g "$(id -gn)" "$dir" 2>/dev/null; then
        return 0
    fi
    warn "No download cache for $NAME on $DATA_DIR: after a system update it downloads again."
    return 0
}

# Is uv (Entangible's Python installer) here already, i.e. not Entangible's?
have_uv() {
    command -v uv >/dev/null 2>&1 || [ -x "$USER_HOME/.local/bin/uv" ]
}

# Run `entangible install` in checkout DIR; on success record what was set
# up. Returns the command's exit code (130: stopped with Ctrl+C).
ent_install() {
    local dir="$1" rc=0 had_uv=yes
    prepare_cache
    have_uv || had_uv=""
    info "Setting up $NAME: its web app, a Python environment and the $UNIT service."
    info "This takes a few minutes; later starts are quick."
    # --no-enable: the service runs only while the demo is open (this
    # launcher starts and stops it), not from every boot
    "$(ent_cmd "$dir")" install --no-enable || rc=$?
    if [ "$rc" -eq 0 ]; then
        mkdir -p "$STATE_DIR" 2>/dev/null || true
        printf '%s %s\n' "$(checkout_commit "$dir")" "$(bundle_tag "$dir")" > "$STAMP" 2>/dev/null || true
        # uv came with Entangible: Remove takes it away again (N3)
        if [ -z "$had_uv" ] && have_uv; then : > "$UV_MARK" 2>/dev/null || true; fi
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
            # Its "checkout is kept" lines are left out: Remove deletes the
            # checkout right after this (N4). So are its "kept (shared ...) uv"
            # lines (uv, ~/.cache/uv) when uv came with Entangible: it goes
            # below. The line about the uv cache on /data stays: so does that.
            rc=0
            out=$("$(ent_cmd "$3")" uninstall --purge 2>&1) || rc=$?
            drop='checkout .* is kept|kept: the checkout'
            [ -f "$UV_MARK" ] && drop="$drop|^ *kept \(shared[^)]*\) uv"
            printf '%s\n' "$out" | grep -v -E "$drop" || true
            [ "$rc" -eq 0 ] || warn "$NAME's own uninstall failed (exit $rc); removing its files anyway."
        fi
        # uv and its cache, when Entangible brought them (no other demo uses uv)
        if [ -f "$UV_MARK" ]; then
            rm -f "$USER_HOME/.local/bin/uv" "$USER_HOME/.local/bin/uvx" 2>/dev/null || true
            rm -rf "$USER_HOME/.cache/uv" 2>/dev/null || true
            rm -f "$UV_MARK" 2>/dev/null || true
            echo "    removed  uv (installed for $NAME)"
        fi
        rmdir "$USER_HOME/.qamposer-physical" 2>/dev/null || true
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
[ -x "$ENT" ] || die "$NAME is not downloaded. Start it from its desktop icon or the RasQberry menu > Quantum Demos > Beta: try & tell us, which ask before downloading."

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

# The address phones are sent to (QAMPOSER_ADVERTISE_HOST in
# /etc/default/entangible): the hotspot's own while the hotspot runs, the
# network's otherwise. rq_hotspot.sh sets it when it starts the hotspot and
# takes it out when it stops it - but a hotspot that ended another way (the
# Pi switched off, the taskbar's network menu) left it, and Entangible set
# up after the hotspot started (or anew after an A/B update) did not get it:
# phones on the school Wi-Fi were sent to 10.42.0.1 (review C1). So the
# hotspot's own rule runs again here, from its real state; as root, the file
# is root's. It restarts a running service when the address changes.
sync_hotspot_address() {
    local hs="$SCRIPT_DIR/rq_hotspot.sh"
    local -a su=()
    [ -r "$hs" ] && command -v nmcli >/dev/null 2>&1 || return 0
    [ "$(id -u)" = "0" ] || su=(sudo -n)
    # shellcheck disable=SC2016
    ${su[@]+"${su[@]}"} bash -c '. "$1" || exit 0
        if nmcli -t -f NAME connection show --active 2>/dev/null | grep -qx "$PROFILE"; then
            advertise on
        else
            advertise off
        fi' _ "$hs" >/dev/null 2>&1 || true
}
sync_hotspot_address

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
# Started here or already running (another window, a booth install that
# starts at boot): ending the demo stops it either way, like the Docker demos
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

# The camera state settles first: right after the start the service reports
# a camera as connected for about 2 s, also when there is none (rig test
# 2026-10-11, F1; Entangible E1). Watch it for READY_SETTLE seconds; once it
# says false, that is the answer.
settle_ready() {
    local end=$((SECONDS + READY_SETTLE))
    while [ "$SECONDS" -lt "$end" ]; do
        [ "$(st .ready)" = "false" ] && return 0
        sleep 1
        ent_status
    done
    return 0
}
[ "$(st .ready)" = "null" ] || settle_ready

KIOSK_URL=$(st .urls.kiosk)
VISITOR_URL=$(st .urls.visitor)
SOURCE=$(st .source)

# The hint line of `entangible doctor` when the configured camera source does
# not fit the cameras found (e.g. cv2:0 on a Pi with only a camera module)
source_hint() {
    local t=""
    command -v timeout >/dev/null 2>&1 && t="timeout 20"
    $t "$ENT" doctor 2>/dev/null </dev/null | sed -n 's/^hint: //p' | head -1 || true
}

# The camera, from status.ready (null: the service did not say)
camera_text() {
    local hint
    case "$(st .ready)" in
        true)  echo "Camera: connected ($SOURCE)." ;;
        false) echo "Camera: none found ($SOURCE). $NAME runs without one, but reads no tiles."
               hint=$(source_hint)
               if [ -n "$hint" ]; then
                   echo "  $hint"
               else
                   echo "  Connect a USB webcam or the Pi camera, then end $NAME and start it again."
               fi ;;
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

# The screen size as "W,H" for --window-size (rq_desktop_session.py asks
# the compositor, as the desktop user), or nothing
booth_window_size() {
    local size="" user_name
    local -a run=()
    user_name=$(get_user_name)
    if [ "$(id -u)" = "0" ] && [ "$user_name" != "root" ]; then
        run=(sudo -u "$user_name" -H XDG_RUNTIME_DIR="/run/user/$(id -u "$user_name")"
             WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" --)
    fi
    size=$(${run[@]+"${run[@]}"} python3 "$SCRIPT_DIR/rq_desktop_session.py" --screen 2>/dev/null) || size=""
    case "$size" in
        [1-9]*x[1-9]*) echo "${size/x/,}" ;;
    esac
    return 0
}

# The booth screen: a browser of its own (its own profile), so that it
# accepts the service's self-signed certificate (a running desktop Chromium
# ignores new flags) and closes when the demo ends.
# Full screen over the whole screen: it often filled only the middle half,
# on black, or sat 480 px to the right (rig recheck 2026-10-11). labwc's
# rule for the homepage window (rc.xml: identifier "chromium", MoveTo
# 480,45, matchOnce) also caught the booth window whenever no other Chromium
# window was open, and Chromium came up at the size its profile remembered
# (945 px wide). So the window gets a class of its own (no rule matches it)
# and starts at 0,0 at the size of the screen. Not --kiosk: F11 still leaves
# full screen.
open_booth_screen() {
    local browser user_name size
    browser=$(command -v chromium || command -v chromium-browser || true)
    if [ -z "$browser" ]; then
        info "No browser found. Open the booth screen yourself: $KIOSK_URL"
        return 0
    fi
    mkdir -p "$BOOTH_PROFILE" 2>/dev/null || true
    local -a cmd=("$browser" --user-data-dir="$BOOTH_PROFILE" --password-store=basic
                  --no-first-run --noerrdialogs --disable-session-crashed-bubble
                  --ignore-certificate-errors --test-type --class=entangible-booth)
    size=$(booth_window_size)
    [ -z "$size" ] || cmd+=(--window-position=0,0 --window-size="$size")
    cmd+=(--start-fullscreen "$KIOSK_URL")
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
[ -z "$BOOTH_OPEN" ] || echo "The booth screen covers this window: press F11 to leave full screen, then click this window in the taskbar."
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
