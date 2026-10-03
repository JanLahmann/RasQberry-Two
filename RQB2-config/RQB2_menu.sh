#!/bin/sh
# Note: removed set -eu to prevent raspi-config crashes from unset variables
#
# This file is SOURCED into raspi-config (#!/bin/sh, dash on Raspberry Pi OS),
# so everything at file scope runs in raspi-config's own shell. Do not change
# shell-wide state here. A file-scope IFS without a space used to live on this
# line: it broke raspi-config's own word splitting ("Network Proxy -> All"
# died with "bad variable name", R-017) and the LED Output Targets checklist
# (R-018).

# -----------------------------------------------------------------------------
# RasQberry-Two: RQB2_menu.sh
# Table of Contents:
# 1. Environment & Bootstrap
# 2. Helpers
# 3. Menu Functions
#    a) Environment Variable Menu
#    b) Qiskit Install Menu
#    c) LED Demo Menu
#    d) Quantum Lights Out Menu
#    e) Quantum Raspberry-Tie Menu
#    f) Main Menu
# 4. Error Handling
# -----------------------------------------------------------------------------

# load RasQberry environment and constants with error handling
# (RQ_CONFIG_FILE: same override as rq_common.sh; the unit tests use it)
ENV_CONFIG_FILE="${RQ_CONFIG_FILE:-/usr/config/rasqberry_env-config.sh}"

# Load (or reload) the RasQberry environment without touching raspi-config's
# own globals.
#
# raspi-config tests [ "$INTERACTIVE" = True ] before every dialog. The env file
# used to assign INTERACTIVE=true, ASK_TO_REBOOT=0 and CONFIG=/boot/config.txt,
# so every reload after a RasQberry setting changed switched raspi-config to
# non-interactive mode: S4 Hostname then set an EMPTY hostname without asking,
# SSH/VNC only said "There was an error", and a queued reboot was dropped
# (R-001). The lines are gone from the shipped defaults, but env files on
# devices keep them (a branch update carries device keys over), so keep
# whatever raspi-config had set - or not set - across every load.
_rq_load_env() {
    [ -f "$ENV_CONFIG_FILE" ] || return 1
    _rq_sv_int="${INTERACTIVE-_rq_unset_}"
    _rq_sv_atr="${ASK_TO_REBOOT-_rq_unset_}"
    _rq_sv_cfg="${CONFIG-_rq_unset_}"
    . "$ENV_CONFIG_FILE"
    _rq_load_rc=$?
    if [ "$_rq_sv_int" = _rq_unset_ ]; then unset INTERACTIVE; else INTERACTIVE="$_rq_sv_int"; fi
    if [ "$_rq_sv_atr" = _rq_unset_ ]; then unset ASK_TO_REBOOT; else ASK_TO_REBOOT="$_rq_sv_atr"; fi
    if [ "$_rq_sv_cfg" = _rq_unset_ ]; then unset CONFIG; else CONFIG="$_rq_sv_cfg"; fi
    return $_rq_load_rc
}

if [ -f "$ENV_CONFIG_FILE" ]; then
    _rq_load_env
else
    echo "Warning: RasQberry environment config not found at $ENV_CONFIG_FILE"
    # Set minimal defaults to prevent crashes
    USER_HOME="${USER_HOME:-/home/${SUDO_USER:-$USER}}"
    REPO="${REPO:-RasQberry-Two}"
    STD_VENV="${STD_VENV:-RQB2}"
fi

# Constants and reusable paths
REPO_DIR="$USER_HOME/$REPO"
DEMO_ROOT="$REPO_DIR/demos"
BIN_DIR="/usr/bin"  # System-wide bin directory (accessible to both root and normal users)
VENV_ACTIVATE="$REPO_DIR/venv/$STD_VENV/bin/activate"

# Demo menu cache (auto-generated from manifests, provides DEMO_MENU_ITEMS and dispatch_demo_by_id)
# TODO: Use global directory variable once defined (see issue #246)
DEMO_MENU_CACHE="${RQ_DEMO_MENU_CACHE:-/usr/config/demo-menu-cache.sh}"

# Source the generated demo list, but only if it parses.
#
# raspi-config sources this file before anything else, so a cache that dash
# cannot parse (cut short, or generated from a bad user manifest) stopped ALL of
# raspi-config: Wi-Fi, VNC, `raspi-config nonint`, and the Refresh item that
# would rebuild the cache (R-120). Check it with `sh -n` first; if it is broken
# or missing, carry on with an empty generated list (the Quantum Demos menu says
# so) and a dispatcher that still runs any demo through the engine.
_rq_load_demo_cache() {
    if [ ! -f "$DEMO_MENU_CACHE" ]; then
        _RQ_DEMO_CACHE_STATE=missing
    elif /bin/sh -n "$DEMO_MENU_CACHE" 2>/dev/null && . "$DEMO_MENU_CACHE"; then
        _RQ_DEMO_CACHE_STATE=ok
        return 0
    else
        _RQ_DEMO_CACHE_STATE=broken
    fi
    DEMO_MENU_ITEMS=""
    DEMO_COUNT=0
    dispatch_demo_by_id() { "$BIN_DIR/rq_demo_run.sh" "$1"; }
    return 1
}
_rq_load_demo_cache || :

#
# -----------------------------------------------------------------------------
# 1. Environment & Bootstrap
# -----------------------------------------------------------------------------
#
# Note: No longer need to create symlinks - all scripts are in /usr/bin

# -----------------------------------------------------------------------------
# 2. Helpers
# -----------------------------------------------------------------------------

# POSIX-compatible generic whiptail menu helper.
# Deliberately NOT the one from rq_common.sh (#230): raspi-config runs this file
# under /bin/sh (dash on Raspberry Pi OS), and rq_common.sh uses bash-only syntax
# (arrays), so sourcing it here would stop raspi-config from parsing at all.
#
#   show_menu [--default-item TAG] [--tags] TITLE PROMPT TAG DESC [TAG DESC ...]
#
# - The box is sized so the PROMPT is visible. With raspi-config's fixed 18x11
#   newt leaves 0 lines for it ((H-2)-4-1-L), so the state several menus put
#   there ("Current: Slot B", the current layout) was never shown (R-019).
# - `--` ends whiptail's option parsing before the items: whiptail (popt) reads
#   options anywhere, so an item starting with "-" made it fail with
#   "unknown option" and the menu silently never opened (R-024).
# - --default-item keeps the cursor on the last choice (R-152).
# - The tags are internal ids (QD, AB_BOOT, TRYBOOT_A, grok-bloch-web), so they
#   are hidden and the item text alone says what an entry is (R-092); --tags
#   shows them where the tag IS the information (the settings editor).
# - If whiptail fails with a message instead of a choice, show it rather than
#   behaving as if the user pressed Back.
show_menu() {
    _sm_default=""; _sm_notags="--notags"
    while :; do
        case "$1" in
            --default-item) _sm_default="$2"; shift 2 ;;
            --tags) _sm_notags=""; shift ;;
            --notags) _sm_notags="--notags"; shift ;;
            *) break ;;
        esac
    done
    title="$1"; shift
    prompt="$1"; shift

    _sm_w="${WT_WIDTH:-80}"
    _sm_mh="${WT_MENU_HEIGHT:-11}"
    _sm_n=$(( $# / 2 ))
    [ "$_sm_n" -lt "$_sm_mh" ] && [ "$_sm_n" -gt 0 ] && _sm_mh="$_sm_n"
    _sm_pl=0
    [ -n "$prompt" ] && _sm_pl=$(printf '%b\n' "$prompt" | fold -s -w $((_sm_w - 4)) | wc -l)
    _sm_rows=$(stty size </dev/tty 2>/dev/null | cut -d' ' -f1)
    case "$_sm_rows" in ''|*[!0-9]*) _sm_rows=24 ;; esac
    _sm_h=$((_sm_mh + _sm_pl + 7))
    if [ "$_sm_h" -gt $((_sm_rows - 1)) ]; then
        _sm_h=$((_sm_rows - 1))
        _sm_mh=$((_sm_h - 7 - _sm_pl))
        [ "$_sm_mh" -lt 3 ] && _sm_mh=3
    fi

    _sm_out=$(whiptail --title "$title" ${_sm_default:+--default-item "$_sm_default"} $_sm_notags \
        --ok-button Select --cancel-button Back \
        --menu "$prompt" "$_sm_h" "$_sm_w" "$_sm_mh" -- "$@" 3>&1 1>&2 2>&3)
    _sm_rc=$?
    if [ "$_sm_rc" -ne 0 ] && [ "$_sm_rc" -ne 255 ] && [ -n "$_sm_out" ]; then
        whiptail --title "Menu error" --msgbox \
            "The menu \"$title\" could not be shown:\n\n$_sm_out" 12 70 </dev/tty >/dev/tty 2>&1
        return 2
    fi
    [ "$_sm_rc" -eq 0 ] && printf '%s' "$_sm_out"
    return $_sm_rc
}

# msgbox sized to its text, scrolling when it does not fit (a POSIX port of
# _rq_dialog_height/_rq_dialog_scroll from rq_common.sh). A whiptail msgbox
# shows H-6 lines and silently cuts the rest, so fixed-size boxes lost their
# last lines (R-020).
#   show_msgbox_fit TITLE TEXT [WIDTH]
show_msgbox_fit() {
    _mf_w="${3:-70}"
    _mf_lines=$(printf '%b\n' "$2" | fold -s -w $((_mf_w - 4)) | wc -l)
    _mf_rows=$(stty size </dev/tty 2>/dev/null | cut -d' ' -f1)
    case "$_mf_rows" in ''|*[!0-9]*) _mf_rows=24 ;; esac
    _mf_h=$((_mf_lines + 7))
    [ "$_mf_h" -lt 8 ] && _mf_h=8
    _mf_scroll=""
    if [ "$_mf_h" -gt "$_mf_rows" ]; then
        _mf_h="$_mf_rows"
        _mf_scroll="--scrolltext"
    fi
    whiptail --title "$1" $_mf_scroll --msgbox "$2" "$_mf_h" "$_mf_w"
}

# Generic installer for demos: name, git URL, marker file, env var, dialog title, optional size
# The generic demo installer that used to live here has been removed.
# Demo installation is now owned by ONE engine, rq_demo_run.sh, which every
# entry point (this menu, desktop icons, the demo loop) calls. Having a
# second installer here meant this menu cloned demos unpinned into the very
# directories the engine installs pinned, so the upstream revision a user got
# depended on which path they happened to use first. See install_via_engine().

# Install a demo through the single install engine (rq_demo_run.sh).
#
# Why this exists: this menu used to clone demos itself, into the SAME
# directories the engine uses but WITHOUT the manifest's upstream SHA pin. Two
# installers writing one directory meant whoever ran first decided which upstream
# revision the user got - so a pinned demo silently became unpinned when it was
# installed from this menu, which is how a patch could break against upstream
# drift even though the manifest pinned it.
#
# The consent dialog (size, time, free space; refused when the space is too
# low) is the engine's, the same as from a desktop icon (Jan, Q27); the engine
# gets the pin, patch, pip, post-install and installed flag right.
#
# Returns 0 when the demo is installed, 2 when the user chose "Not now",
# 1 on failure with RQ_LAST_DEMO_ERROR set (handle_error shows it).
install_via_engine() {
    DEMO_ID="$1"    # manifest id, e.g. grok-bloch
    TITLE="$2"      # title for messages

    RUNNER="$BIN_DIR/rq_demo_run.sh"
    if [ ! -x "$RUNNER" ]; then
        RQ_LAST_DEMO_ERROR="The demo engine is missing: $RUNNER"
        return 1
    fi

    # Already installed? Ask the engine rather than second-guessing it here.
    if "$RUNNER" "$DEMO_ID" --is-installed 2>/dev/null; then
        return 0
    fi

    # Everything goes to stderr: "Download all demos" used to pipe this into a
    # whiptail gauge, and stray stdout garbled it.
    run_engine_demo "$RUNNER" "$DEMO_ID" --install-only >&2 || return 1
    "$RUNNER" "$DEMO_ID" --is-installed 2>/dev/null && return 0
    return 2    # "Not now"
}

# Install Quantum-Lights-Out demo if needed
do_qlo_install() {
    install_via_engine "quantum-lights-out" "Quantum Lights Out"
}

# Install Quantum Raspberry-Tie demo if needed
do_rasp_tie_install() {
    install_via_engine "quantum-raspberry-tie" "Quantum Raspberry-Tie"
}

# Install Grok Bloch demo if needed
do_grok_bloch_install() {
    install_via_engine "grok-bloch" "Grok Bloch Sphere"
}

# Install Fun-with-Quantum notebooks if needed
do_fwq_install() {
    install_via_engine "fun-with-quantum" "Fun with Quantum"
}

# Install Quantum Paradoxes demo if needed
#
# The setup step that creates WELCOME.ipynb and fixes the Qiskit imports is no
# longer invoked here: it is declared as install.post_install in the manifest and
# run by the engine, so every entry point gets it rather than just this one.
do_quantum_paradoxes_install() {
    install_via_engine "quantum-paradoxes" "Quantum Paradoxes"
}

# Run Quantum Paradoxes demo
# (through the engine: it asks before a first download, like every entry point)
run_quantum_paradoxes_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-paradoxes
}

# Clone IBM Quantum Learning content (shared by tutorials and courses)
# Content licensed under CC BY-SA 4.0 by IBM/Qiskit
# Source: https://github.com/Qiskit/documentation
#
# The demo engine asks before this runs (the consent dialog names the licence).
# A download that was interrupted or failed offline used to leave a .git with
# no commit; every retry then took it for "cloned", reported success and set
# the installed flag, and IBM Tutorials, IBM Courses and the Quantum Lab stayed
# broken until someone ran rm -rf (R-056). The checkout counts only with a
# commit and the content; anything else is removed and fetched again, and a
# failure leaves nothing behind.
_rq_ibm_content_ok() {
    # safe.directory: as root, git refuses to look into the user's checkout
    git -c safe.directory='*' -C "$1" rev-parse -q --verify HEAD >/dev/null 2>&1 \
        && [ -d "$1/docs/tutorials" ] && [ -d "$1/learning/courses" ]
}

# Run a command as the desktop user when this menu runs as root, so what it
# creates in the home stays the user's (R-138: the WELCOME notebooks were
# root-owned and could not be saved).
_rq_as_desktop_user() {
    if [ "$(id -u)" = "0" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        sudo -u "$SUDO_USER" -H "$@"
    else
        "$@"
    fi
}

clone_ibm_learning_content() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    _rq_ibm_content_ok "$DEST" && return 0
    if [ -e "$DEST" ]; then
        echo "Removing an incomplete download of the IBM Quantum content..."
        rm -rf "$DEST" 2>/dev/null || sudo -n rm -rf "$DEST" 2>/dev/null
        if [ -e "$DEST" ]; then
            echo "ERROR: Cannot remove the incomplete download: $DEST" >&2
            return 1
        fi
    fi

    echo "Downloading IBM Quantum Learning content (sparse checkout). This may take a few minutes..."
    _rq_as_desktop_user mkdir -p "$DEST" || return 1
    # Pin to a reviewed commit instead of tracking main. Qiskit/documentation is a
    # third-party repo (we do not own it) that changes constantly, so following
    # main makes installs irreproducible and lets an upstream change alter the
    # shipped content underneath us. Bump GIT_REF_DEMO_IBM_LEARNING deliberately.
    _ibm_ref="${GIT_REF_DEMO_IBM_LEARNING:-main}"
    [ -n "${GIT_REF_DEMO_IBM_LEARNING:-}" ] || echo "WARNING: GIT_REF_DEMO_IBM_LEARNING unset - falling back to main (unpinned)"
    if ! _rq_as_desktop_user sh -c '
        cd "$1" &&
        git init -q &&
        git remote add origin "$2" &&
        git sparse-checkout init --cone &&
        git sparse-checkout set docs/tutorials docs/guides/hello-world.ipynb learning/courses LICENSE LICENSE-DOCS &&
        git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 fetch -q --depth=1 origin "$3" &&
        git checkout -q FETCH_HEAD' _ "$DEST" "$GIT_REPO_DEMO_IBM_LEARNING" "$_ibm_ref" \
        || ! _rq_ibm_content_ok "$DEST"; then
        rm -rf "$DEST" 2>/dev/null || sudo -n rm -rf "$DEST" 2>/dev/null
        echo "ERROR: Failed to download the IBM Quantum content from $GIT_REPO_DEMO_IBM_LEARNING" >&2
        return 1
    fi

    # Copy credentials setup notebook
    if [ -f "/usr/config/00-Save-Credentials.ipynb" ]; then
        _rq_as_desktop_user cp "/usr/config/00-Save-Credentials.ipynb" "$DEST/"
        echo "Added credentials setup notebook."
    fi

    echo "IBM Quantum Learning content downloaded."
}

# Write the WELCOME notebook (the demo's marker) for "--tutorials"/"--courses"
_rq_ibm_welcome() {
    _iw_py="$REPO_DIR/venv/$STD_VENV/bin/python3"
    [ -x "$_iw_py" ] || _iw_py=python3
    _rq_as_desktop_user env PYTHONDONTWRITEBYTECODE=1 \
        "$_iw_py" "$BIN_DIR/setup_ibm_tutorials.py" "$1" --path "$DEMO_ROOT/ibm-quantum-learning"
}

# Install IBM Quantum Tutorials
do_ibm_tutorials_install() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    if [ -f "$DEST/$MARKER_IBM_TUTORIALS" ] && _rq_ibm_content_ok "$DEST"; then
        return 0
    fi

    # Clone content if needed
    clone_ibm_learning_content || return 1

    echo "Generating tutorials welcome notebook..."
    if ! _rq_ibm_welcome --tutorials || [ ! -f "$DEST/$MARKER_IBM_TUTORIALS" ]; then
        echo "ERROR: Could not set up the IBM Quantum Tutorials (no tutorials found in the download)" >&2
        return 1
    fi

    update_environment_file "IBM_TUTORIALS_INSTALLED" "true"
    echo "IBM Quantum Tutorials installed."
}

# Install IBM Quantum Courses
do_ibm_courses_install() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    if [ -f "$DEST/$MARKER_IBM_COURSES" ] && _rq_ibm_content_ok "$DEST"; then
        return 0
    fi

    # Clone content if needed
    clone_ibm_learning_content || return 1

    echo "Generating courses welcome notebook..."
    if ! _rq_ibm_welcome --courses || [ ! -f "$DEST/$MARKER_IBM_COURSES" ]; then
        echo "ERROR: Could not set up the IBM Quantum Courses (no courses found in the download)" >&2
        return 1
    fi

    update_environment_file "IBM_COURSES_INSTALLED" "true"
    echo "IBM Quantum Courses installed."
}

# Run IBM Quantum Tutorials demo
run_ibm_tutorials_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" ibm-tutorials
}

# Run IBM Quantum Courses demo
run_ibm_courses_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" ibm-courses
}

# LED-Painter installation is handled by rq_led_painter.sh
# (uses conversion script instead of patch file)

# -----------------------------------------------------------------------------
# Download All Demos - Batch install all available demos
# -----------------------------------------------------------------------------

# Install Qoffee-Maker (notebooks, settings file, Docker image) and
# Quantum-Mixer (its prebuilt image, Jan Q27c) at the versions pinned for this
# release. Run by the demo engine (manifest install.installer) after its
# consent dialog; the launchers own the install steps (--install-only).
do_qoffee_install() {
    "$BIN_DIR/qoffee-maker.sh" --install-only
}

do_quantum_mixer_install() {
    "$BIN_DIR/quantum-mixer.sh" --install-only
}

# Download all demos at once (rq_download_all.sh: the list comes from the demo
# manifests, sizes included; the Docker demos are asked for separately, R-031)
do_download_all_demos() {
    "$BIN_DIR/rq_download_all.sh"
}

# Turn a demo log into the few lines worth showing a user: strip the CR/escape
# noise a pty log carries, drop the Python stack frames ('File "..."' and the
# caret lines under them) which say nothing to a user, and keep the last lines -
# the message that matters ("GPIO busy", "No module named ...") is at the end.
#   _rq_log_tail LOGFILE STATUS
_rq_log_tail() {
    _lt=$(sed 's/\r//g; s/\x1b\[[0-9;]*[a-zA-Z]//g' "$1" 2>/dev/null \
        | grep -v '^[[:space:]]*$' \
        | grep -vE '^[[:space:]]*(File "|\^+[[:space:]]*$|~+[[:space:]]*$)' \
        | grep -vE '^Script (started|done) on ' \
        | tail -n 5)
    [ -z "$_lt" ] && _lt="It stopped with status $2 and printed nothing."
    printf '%s' "$_lt"
}

# Wait for Enter before the menu redraws over what a demo printed.
_rq_pause() {
    printf '\n%s ' "${1:-Press Enter to return to the menu.}"
    read _rq_pause_answer
}

# Helper: run a demo from this menu.
#
#   run_demo [bg] TITLE DIR CMD [ARGS...]
#
# Default (console) mode: the demo runs in the FOREGROUND on this terminal,
# through `script -e` so it has a pty and a copy of its output lands in
# DEMO_LOG. The terminal is the demo's UI (Lights Out console, the LED test, the
# text/logo prompts): it gets the keyboard, Ctrl+C stops it and only it, and
# nothing is drawn over it. These demos used to run in the background under a
# "Demo is running" dialog: their output scrolled the dialog away, keys went to
# the dialog instead of the demo, and - `script` without -e always exits 0 - a
# demo that crashed looked like one that finished (R-028, R-156).
#
# bg mode: for demos whose output is the LEDs. Output goes to DEMO_LOG, a dialog
# offers to stop the demo, and an exit before the user answered is reported
# instead of being taken for a clean finish (R-102).
#
# Returns non-zero with RQ_LAST_DEMO_ERROR set when the demo failed.
run_demo() {
  # Mode selection: default is pty; allow "bg" as first arg
  MODE="pty"
  if [ "$1" = bg ]; then MODE="bg"; shift; fi
  DEMO_TITLE="$1"; shift
  DEMO_DIR="$1"; shift
  # Build the command string from all remaining args (preserving spaces)
  CMD="$1"
  shift
  for arg in "$@"; do
      CMD="$CMD $arg"
  done
  # Ensure commands run inside the Python virtual environment
  if [ -f "$VENV_ACTIVATE" ]; then
    CMD=". \"$VENV_ACTIVATE\" && exec $CMD"
  fi
  RQ_LAST_DEMO_ERROR=""
  # Save current terminal settings
  OLD_STTY=$(stty -g 2>/dev/null)
  # Reset terminal state before launching
  stty sane 2>/dev/null
  # Both modes keep a copy of the output in DEMO_LOG so that if the demo dies we
  # can tell the user WHY.
  DEMO_LOG="${RQ_DEMO_LOG:-/tmp/rqb-demo.log}"

  if [ "$MODE" = "pty" ]; then
      printf '\n=== %s ===   (Ctrl+C stops the demo)\n\n' "$DEMO_TITLE"
      ( cd "$DEMO_DIR" && exec script -qefc "$CMD" "$DEMO_LOG" )
      DEMO_RC=$?
      stty sane 2>/dev/null
      [ -n "$OLD_STTY" ] && stty "$OLD_STTY" 2>/dev/null
      case "$DEMO_RC" in
          # finished, or stopped with Ctrl+C (130) / closed (129, 143)
          0|129|130|143) ;;
          *) RQ_LAST_DEMO_ERROR=$(_rq_log_tail "$DEMO_LOG" "$DEMO_RC") ;;
      esac
      _rq_pause
      [ -n "$RQ_LAST_DEMO_ERROR" ] && return 1
      return 0
  fi

  # bg mode: send the demo's stdout+stderr to a log, NOT the terminal -
  # otherwise a background demo's output (and LED library messages) prints
  # over the "Demo is running" whiptail dialog and corrupts the TUI. It runs in
  # its own session so we can kill the full process group.
  ( trap '' INT; cd "$DEMO_DIR" && exec setsid sh -c "$CMD" < /dev/null >"$DEMO_LOG" 2>&1 ) &
  DEMO_PID=$!
  LAST_DEMO_PGID="$DEMO_PID"

  # Did it actually start?
  #
  # Nothing used to check. The dialog below announced "Demo is running" whether
  # or not the demo was there, so a demo that died on startup - GPIO already
  # held by another demo, a missing module, an unpatched upstream - looked
  # identical to one that worked, except the panel stayed dark. In bg mode the
  # traceback went to the log, which no user reads. Give it a moment to fall
  # over, and if it did, report the real error instead of a comfortable lie.
  sleep 2
  if ! kill -0 "$DEMO_PID" 2>/dev/null; then
      wait "$DEMO_PID"
      DEMO_RC=$?
      LAST_DEMO_PGID=""
      stty sane 2>/dev/null
      [ -n "$OLD_STTY" ] && stty "$OLD_STTY" 2>/dev/null
      if [ "$DEMO_RC" -ne 0 ]; then
          RQ_LAST_DEMO_ERROR=$(_rq_log_tail "$DEMO_LOG" "$DEMO_RC")
          return 1
      fi
      # Exited cleanly and quickly: it ran, it finished. Not an error.
      return 0
  fi

  # Ask user when to stop
  whiptail --title "${DEMO_TITLE}" --yes-button "Stop demo" --no-button "Keep running" --yesno \
      "The demo is running.\n\nStop demo: end it now.\nKeep running: back to the menu, the demo goes on (end it later with \"Stop last running demo\")." \
      12 70
  RESPONSE=$?
  # Restore terminal state before killing demo
  stty sane 2>/dev/null
  if ! kill -0 "$DEMO_PID" 2>/dev/null; then
      # It ended by itself while the dialog was up. A slow start (a Qiskit
      # import on a Pi 4 takes several seconds) can fail after the 2-second
      # check above, and that used to vanish without a word (R-102).
      wait "$DEMO_PID"
      DEMO_RC=$?
      LAST_DEMO_PGID=""
      [ "$DEMO_RC" -ne 0 ] && RQ_LAST_DEMO_ERROR=$(_rq_log_tail "$DEMO_LOG" "$DEMO_RC")
  elif [ "$RESPONSE" -eq 0 ]; then
      # Terminate the entire demo process group only if user chose Stop
      kill -TERM -"$DEMO_PID" 2>/dev/null || true
      wait "$DEMO_PID" 2>/dev/null || true
      LAST_DEMO_PGID=""
  fi
  # Restore original terminal settings
  [ -n "$OLD_STTY" ] && stty "$OLD_STTY" 2>/dev/null
  stty intr ^C 2>/dev/null
  [ -n "$RQ_LAST_DEMO_ERROR" ] && return 1
  return 0
}

# Stop the most recently launched demo (its whole setsid process group) and
# blank the LEDs. run_demo records LAST_DEMO_PGID; a demo left running (user
# chose "Keep running" at the stop prompt) can be stopped here later.
#
# A demo started elsewhere (a desktop icon, an earlier menu session, the IP
# scroll at start-up) is not in LAST_DEMO_PGID: STOP used to say "Stopped the
# last running demo and cleared the LEDs." while it kept the panel lit, or
# "No demo has been started" (R-103, R-148). Whatever holds the panel is now
# named and stopped too, and the result says what really happened.
stop_last_demo() {
  _sd_done=""
  if [ -n "${LAST_DEMO_PGID:-}" ] && kill -0 "$LAST_DEMO_PGID" 2>/dev/null; then
    # Negative PID targets the whole process group (setsid session leader).
    kill -TERM -"$LAST_DEMO_PGID" 2>/dev/null
    sleep 1
    kill -KILL -"$LAST_DEMO_PGID" 2>/dev/null || true
    _sd_done="yes"
  fi
  LAST_DEMO_PGID=""
  _sd_h=$(_rq_led_holders)
  if [ -n "$_sd_h" ]; then
    _sd_n=$(printf '%s\n' "$_sd_h" | sed 's/^[0-9]* /  /')
    _sd_rows=$(printf '%s\n' "$_sd_h" | wc -l)
    if whiptail --title "Stop Demo" --yes-button "Stop It" --no-button "Leave It" --yesno \
        "This program is using the LED panel:\n\n$_sd_n\n\nStop it too?" $((_sd_rows + 10)) 70; then
      "$BIN_DIR/rq_clear_leds.sh" --stop >/dev/null 2>&1
      _sd_done="yes"
    else
      [ -n "$_sd_done" ] && whiptail --title "Stop Demo" --msgbox \
        "Stopped the last demo started here. The LED panel is still in use by:\n\n$_sd_n" $((_sd_rows + 9)) 70
      return 0
    fi
  fi
  if [ -z "$_sd_done" ]; then
    whiptail --title "Stop Demo" --msgbox "No demo is running." 8 50
    return 0
  fi
  if do_led_off; then
    whiptail --title "Stop Demo" --msgbox "Stopped. The LEDs are off." 8 50
  else
    whiptail --title "Stop Demo" --msgbox \
      "Stopped, but the LEDs could not be turned off:\n\n${RQ_LAST_DEMO_ERROR:-unknown error}" 12 70
    RQ_LAST_DEMO_ERROR=""
  fi
  return 0
}

# Plain-language reason for a demo the engine could not run.
#   _rq_explain_demo_error MESSAGE STATUS
# MESSAGE is what the engine (or the launcher it handed over to) gave as its
# reason; the common causes get a sentence that says what to do.
_rq_explain_demo_error() {
    case "$1" in
        *"needs a screen"*|*"requires a display"*)
            _ex="This demo opens a window on the Pi's desktop, and this terminal has none (an SSH login, for example). Start it on the desktop - its icon, or this menu in a terminal there - or over VNC." ;;
        *"Failed to fetch pinned commit"*|*"Failed to clone"*|*"Could not resolve host"*|*"unable to access"*|*"Network is unreachable"*)
            _ex="The demo could not be downloaded. Check that the Pi is online (Wi-Fi or network cable) and try again." ;;
        *"No space left on device"*)
            _ex="The SD card is full. Free some space (Quantum Demos > Remove a demo), then try again." ;;
        *) _ex="" ;;
    esac
    if [ -n "$1" ]; then
        if [ -n "$_ex" ]; then printf '%s\n\nDetails: %s' "$_ex" "$1"; else printf '%s' "$1"; fi
    else
        printf 'It stopped with status %s. The messages it printed (shown before this box) say why.' "$2"
    fi
}

# Run a demo through the demo engine (rq_demo_run.sh), in the foreground.
#
#   run_engine_demo COMMAND [ARGS...]
#   e.g. run_engine_demo dispatch_demo_by_id grok-bloch
#        run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-raspberry-tie real
#
# The engine prints why it stops ("needs a display", "could not download", a
# traceback), and the menu used to redraw over it at once, leaving only
# "Failed to run demo: <id>" (R-026). Its reason now also goes to a file
# (RQ_ERROR_FILE, written by die() in rq_common.sh), a failure keeps the output
# on screen until Enter, and the caller's error box gets the reason in plain
# words. Ctrl+C (exit 130) stops the demo; that is not an error.
run_engine_demo() {
    RQ_LAST_DEMO_ERROR=""
    _ed_err=$(mktemp /tmp/rqb-demo-error.XXXXXX 2>/dev/null) || _ed_err=""
    # Non-LED demos run as the desktop user (rq_demo_run.sh drops root) and
    # their die() appends here too, LED demos as root. Keep the file root's
    # (in sticky /tmp, protected_regular stops root from opening a file another
    # user owns) and let everyone append, but only root read.
    [ -n "$_ed_err" ] && chmod 622 "$_ed_err" 2>/dev/null
    RQ_ERROR_FILE="$_ed_err"
    export RQ_ERROR_FILE
    "$@"
    _ed_rc=$?
    unset RQ_ERROR_FILE
    stty sane 2>/dev/null
    case "$_ed_rc" in
        0|130|143) [ -n "$_ed_err" ] && rm -f "$_ed_err"; return 0 ;;
    esac
    _ed_msg=""
    if [ -n "$_ed_err" ]; then
        _ed_msg=$(tail -n 3 "$_ed_err" 2>/dev/null)
        rm -f "$_ed_err"
    fi
    RQ_LAST_DEMO_ERROR=$(_rq_explain_demo_error "$_ed_msg" "$_ed_rc")
    _rq_pause "It stopped with an error (see above). Press Enter to continue."
    return 1
}

# Generic runner for Quantum-Lights-Out demo (POSIX sh compatible)
run_qlo_demo() {
    MODE="${1:-}"  # empty for GUI, "console" for console mode
    DEMO_DIR="$DEMO_ROOT/Quantum-Lights-Out"
    # Ensure installed: the engine asks first; "Not now" (2) is not an error,
    # a failure leaves its reason for handle_error
    do_qlo_install
    case $? in 0) ;; 2) return 0 ;; *) return 1 ;; esac
    # Launch appropriate mode.
    #
    # The console variant IS played in the terminal, so it runs in the
    # foreground. The default variant plays on the LEDs and its stdout is just
    # noise - the solver's progress and Qiskit's deprecation warnings - so it
    # goes to the log under the stop dialog.
    # run_led_demo checks the panel is free and turns the LEDs off afterwards
    if [ "$MODE" = "console" ]; then
        run_led_demo "Quantum Lights Out Demo (console)" "$DEMO_DIR" python3 lights_out.py --console
    else
        run_led_demo bg "Quantum Lights Out Demo" "$DEMO_DIR" python3 lights_out.py
    fi
}

# Run grok-bloch demo local version (ensures install first)
run_grok_bloch_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" grok-bloch
}

# Run grok-bloch web version (no installation needed)
run_grok_bloch_web_demo() {
    # Check if chromium-browser is available
    if ! command -v chromium-browser >/dev/null 2>&1; then
        whiptail --title "Browser Not Found" --msgbox \
            "Chromium browser is not installed.\n\nThe web version requires a web browser." \
            10 60
        return 1
    fi

    whiptail --title "Grok Bloch Sphere (Web)" --msgbox \
        "Opening the online version of Grok Bloch Sphere in your browser.\n\nURL: https://javafxpert.github.io/grok-bloch/\n\nPress OK to continue." \
        12 70

    # Launch browser with web version (as user if running as root)
    GROK_URL="https://javafxpert.github.io/grok-bloch/"
    if [ "$(whoami)" = "root" ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        su - "$SUDO_USER" -c "DISPLAY=${DISPLAY:-:0} chromium-browser --password-store=basic '$GROK_URL' >/dev/null 2>&1 &"
    else
        chromium-browser --password-store=basic "$GROK_URL" >/dev/null 2>&1 &
    fi
}

# Run quantum fractals demo
run_fractals_demo() {
    # Launch the fractals demo using the dedicated launcher script
    "$BIN_DIR/fractals.sh"
}

# Run LED-Painter demo
run_led_painter_demo() {
    # Launch the LED-Painter demo using the dedicated launcher script
    "$BIN_DIR/rq_led_painter.sh"
}

# Run RasQ-LED demo
run_rasq_led_demo() {
    # Launch the RasQ-LED quantum circuit demo directly.
    #
    # bg: this demo's output is the LEDs, not the terminal. Its raw console
    # output used to replace the TUI entirely (the other LED demos already run
    # this way).
    run_led_demo bg "RasQ-LED Demo" "$BIN_DIR" python3 RasQ-LED.py
}

# Run Qoffee-Maker demo
run_qoffee_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" qoffee-maker
}

# Run Quantum-Mixer demo (the engine asks before its 15-30 minute build)
run_quantum_mixer_demo() {
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-mixer
}

# Stop the Docker demos that are running (doQumentation, Quantum Lab,
# Qoffee-Maker, Quantum-Mixer, catalogue demos): closing their window keeps
# them running, and only Qoffee and the Mixer had a stop entry (R-110).
do_stop_docker_demos() {
    "$BIN_DIR/rq_docker_demos.sh" --stop-menu
}

# Move a demo to a newer upstream version, or back to the one this release
# ships (Jan, Q8/Q32)
do_update_demos() {
    run_engine_demo "$BIN_DIR/rq_demo_update.sh"
}

# Refresh demo menu cache from manifests
# This regenerates the demo-menu-cache.sh file from demo manifest files
refresh_demo_menu_cache() {
    if [ -x "$BIN_DIR/rq_demo_generate_menu.sh" ]; then
        # Plain text, not an --infobox: whiptail restores the screen when it
        # exits, so an infobox vanished at once and the rebuild looked frozen.
        printf '\nRebuilding the demo list from the demo descriptions. This can take a minute...\n'
        if "$BIN_DIR/rq_demo_generate_menu.sh" --cache "$DEMO_MENU_CACHE" > /dev/null 2>&1 \
            && _rq_load_demo_cache; then
            whiptail --title "Demo List Refreshed" --msgbox "The demo list was rebuilt.\n\n$DEMO_COUNT demos are in the Quantum Demos menu." 10 60
        else
            whiptail --title "Error" --msgbox "The demo list could not be rebuilt.\n\nOne of the demo descriptions (manifest files) may be damaged." 10 60
            return 1
        fi
    else
        whiptail --title "Error" --msgbox "Menu generator script not found.\n\nExpected: $BIN_DIR/rq_demo_generate_menu.sh" 10 60
        return 1
    fi
}

# Remove a downloaded demo to free space (rq_demo_remove.sh; catalogue demos
# lose their menu entry too)
do_remove_demo() {
    if [ -x "$BIN_DIR/rq_demo_remove.sh" ]; then
        run_engine_demo "$BIN_DIR/rq_demo_remove.sh"
        _rm_rc=$?
        _rq_load_demo_cache || :
        return $_rm_rc
    fi
    whiptail --title "Error" --msgbox "Remove script not found.\n\nExpected: $BIN_DIR/rq_demo_remove.sh" 10 60
    return 1
}

# Run continuous demo loop for conference showcases
run_demo_loop() {
    # Launch the demo loop script
    "$BIN_DIR/rq_demo_loop.sh"
}

# Add an external demo from the curated registry (known-demos.json).
# Delegates to rq_demo_add_external.sh (interactive picker), then reloads the
# regenerated menu cache so the new demo shows up without leaving the menu.
do_add_external_demo() {
    if [ -x "$BIN_DIR/rq_demo_add_external.sh" ]; then
        # run_engine_demo keeps the script's reason when it fails: a failed
        # install used to return to the menu without a word (R-057)
        run_engine_demo "$BIN_DIR/rq_demo_add_external.sh"
        _ax_rc=$?
        # The add script regenerates the cache; reload it in this session
        _rq_load_demo_cache || :
        return $_ax_rc
    else
        whiptail --title "Error" --msgbox "Add-demo script not found.\n\nExpected: $BIN_DIR/rq_demo_add_external.sh" 10 60
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 3a) Environment Variable Menu
# -----------------------------------------------------------------------------

# Keys that must not be edited here: raspi-config's own globals (old env files
# still carry them, see _rq_load_env) and the ones the env file marks
# "# DEPRECATED: KEY ..." (nothing reads them any more).
_rq_hidden_env_keys() {
    # + the retired LED_MATRIX_* keys (Q22), which older files still carry
    printf ' INTERACTIVE ASK_TO_REBOOT CONFIG LED_MATRIX_LAYOUT LED_MATRIX_WIDTH LED_MATRIX_HEIGHT'
    printf ' LED_MATRIX_Y_FLIP LED_MATRIX_PANEL_WIDTH LED_MATRIX_PANEL_HEIGHT '
    sed -n 's/^# DEPRECATED: *//p' "$ENV_FILE" 2>/dev/null \
        | sed 's/ - .*//; s/(.*//; s/\. .*//' \
        | grep -oE '[A-Z][A-Z0-9_]+' | tr '\n' ' '
}

# "Advanced: edit a setting" - change one value in rasqberry_environment.env.
# Shows the current value as the item text and pre-fills it, hides keys that
# must not be edited here, and refuses values the shell-sourced file cannot
# hold (R-093).
do_select_environment_variable() {

  if [ ! -f "$ENV_FILE" ]; then
    whiptail --title "Error" --msgbox "Settings file not found:\n$ENV_FILE" 9 70
    return 1
  fi

  # Build menu items as positional parameters from environment file (POSIX-compliant)
  _hidden=$(_rq_hidden_env_keys)
  set --
  while IFS='=' read -r key value; do
    # Skip comments, empty lines and hidden keys
    case "$key" in
      ''|'#'*|' #'*|'	#'*|*[!A-Za-z0-9_]*) continue ;;
    esac
    case "$_hidden" in *" $key "*) continue ;; esac
    set -- "$@" "$key" "${value:- }"
  done < "$ENV_FILE"

  # Create a menu with the environment variables
  FUN=$(show_menu --tags ${_uef_last:+--default-item "$_uef_last"} "Advanced: RasQberry Two settings" \
        "Pick a setting to change. Wrong values can stop demos or the LEDs from working." "$@")
  RET=$?
  [ "$RET" -ne 0 ] && return 0
  _uef_last="$FUN"
  current=$(check_environment_variable "$FUN")
  # Prompt for the new value and update the environment file
  new_value=$(whiptail --title "Advanced: RasQberry Two settings" --inputbox \
      "New value for ${FUN}:\n\n(Current value is filled in. Letters, digits and . _ - : / @ % + , = ~ only.)" \
      12 "${WT_WIDTH:-78}" "$current" 3>&1 1>&2 2>&3)
  RET=$?
  [ "$RET" -ne 0 ] && return 0
  case "$new_value" in
    *[!A-Za-z0-9._:/@%+,=~-]*)
      whiptail --title "Value not saved" --msgbox \
        "The value for ${FUN} was not saved: it contains a space, quote or other character the settings file cannot hold.\n\nAllowed: letters, digits and . _ - : / @ % + , = ~" 12 70
      return 0 ;;
  esac
  [ "$new_value" = "$current" ] && return 0
  if [ "$FUN" = "LED_DEFAULT_BRIGHTNESS" ]; then
    if ! printf '%s\n' "$new_value" | grep -Eq '^(0(\.[0-9]+)?|1(\.0+)?|\.[0-9]+)$'; then
      whiptail --title "Value not saved" --msgbox \
        "LED_DEFAULT_BRIGHTNESS is a number from 0 to 1, for example 0.3." 9 70
      return 0
    fi
    # No hard limit (Q21 is open), but say what it costs (R-007)
    if awk -v b="$new_value" 'BEGIN { exit !(b + 0 > 0.4) }'; then
      whiptail --title "Brighter LED Panel" --yes-button "Save" --no-button "Cancel" --yesno \
        "Above 0.4 a bright demo can draw more current than the Pi's power supply has left over for a panel powered from the Pi. The Pi can then restart or flicker.\n\nUse more than 0.4 only with a separate 5V supply for the panel. Save ${new_value}?" 13 70 || return 0
    fi
  fi
  update_environment_file "${FUN}" "$new_value"
}

# Write KEY=VALUE into the env file: replace the key's lines, or append it.
#
# This used to be `sed -i "s/^$1=.*/$1=$2/gm"`, which failed on a "/" in the
# value (any URL) while returning 0, and turned "&" into the matched text -
# 'a&b' became 'aLED_LAYOUT=...b' (R-093). awk takes the key and value
# from the environment, so no character in them is special. The new file is
# written next to the old one and renamed over it, so a full disk cannot leave
# a half-written file behind.
_rq_env_write() {
    _ew_dir=$(dirname "$ENV_FILE")
    _ew_prog='BEGIN { k = ENVIRON["RQ_EW_KEY"]; v = ENVIRON["RQ_EW_VALUE"]; done = 0 }
        index($0, k "=") == 1 { print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }'
    if [ -w "$ENV_FILE" ] && [ -w "$_ew_dir" ]; then
        _ew_tmp=$(mktemp "$_ew_dir/.rasqberry_environment.XXXXXX") || return 1
        if RQ_EW_KEY="$1" RQ_EW_VALUE="$2" awk "$_ew_prog" "$ENV_FILE" > "$_ew_tmp" \
            && [ -s "$_ew_tmp" ] && chmod 644 "$_ew_tmp" && mv -f "$_ew_tmp" "$ENV_FILE"; then
            return 0
        fi
        rm -f "$_ew_tmp"
        return 1
    fi
    # Not writable (run standalone as the user against the root-owned file):
    # build the new file in /tmp and let sudo copy it into place.
    _ew_tmp=$(mktemp) || return 1
    if RQ_EW_KEY="$1" RQ_EW_VALUE="$2" awk "$_ew_prog" "$ENV_FILE" > "$_ew_tmp" \
        && [ -s "$_ew_tmp" ] && sudo cp "$_ew_tmp" "$ENV_FILE"; then
        rm -f "$_ew_tmp"
        return 0
    fi
    rm -f "$_ew_tmp"
    return 1
}

# Function to update values stored in the rasqberry_environment.env file
update_environment_file () {
  #check whether string is empty
  if [ -z "$2" ] || [ -z "$1" ]; then
    # whiptail message box to show error
    [ "${RQ_NO_MESSAGES:-false}" = false ] && whiptail --title "Error" --msgbox "Error: No value provided. Environment variable not updated" 8 78
    return 1
  fi
  if ! _rq_env_write "$1" "$2"; then
    [ "${RQ_NO_MESSAGES:-false}" = false ] && whiptail --title "Error" --msgbox \
      "Could not save $1 to $ENV_FILE (is the SD card full?)." 9 78
    return 1
  fi
  # LED settings also go to the store both A/B slots share (#290)
  case "$1" in
    *_INSTALLED) ;;
    LED_*|RASQ_LED_*)
      if [ "$(id -u)" = "0" ]; then /usr/bin/rq_device_settings.sh save >/dev/null 2>&1 || true
      else sudo /usr/bin/rq_device_settings.sh save >/dev/null 2>&1 || true; fi ;;
  esac
  # reload environment file (keeping raspi-config's INTERACTIVE etc., R-001)
  _rq_load_env
}


# Function to check the value of a variable in the environment file
check_environment_variable() {
    VARIABLE_NAME="$1"

    # Check if the environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        whiptail --msgbox "Environment file not found. Please ensure it exists." 20 60 1
        return 1
    fi

    # Retrieve the value of the variable (the last assignment wins, as when
    # the file is sourced; values may contain "=")
    VALUE=$(sed -n "s/^${VARIABLE_NAME}=//p" "$ENV_FILE" | tail -n 1)

    # Return the value
    echo "$VALUE"
}


# -----------------------------------------------------------------------------
# 3b) Qiskit Install Menu
# -----------------------------------------------------------------------------

# Install any version of Qiskit using consolidated script
# $1 = version (latest, 1.0, 1.1)
# $2 = silent (optional, suppresses whiptail popup)
do_rqb_install_qiskit() {
  sudo -u "$SUDO_USER" -H -- sh -c "$BIN_DIR/rq_install_qiskit.sh $1"
  if { [ "$INTERACTIVE" = true ] || [ "$INTERACTIVE" = True ]; } && ! [ "$2" = silent ]; then
    [ "$RQ_NO_MESSAGES" = false ] && whiptail --msgbox "Qiskit $1 installed" 20 60 1
  fi
}

do_rqb_qiskit_menu() {
    while true; do
        FUN=$(show_menu "Qiskit Install" "Choose version to install" \
           Qnew  "Install Qiskit (latest)" \
           Q11   "Install Qiskit v1.1" \
           Q10   "Install Qiskit v1.0") || break
        case "$FUN" in
            Q11)   do_rqb_install_qiskit 1.1 || { handle_error "Failed to install Qiskit v1.1."; continue; } ;;
            Q10)   do_rqb_install_qiskit 1.0 || { handle_error "Failed to install Qiskit v1.0."; continue; } ;;
            Qnew)  do_rqb_install_qiskit latest || { handle_error "Failed to install latest Qiskit."; continue; } ;;
            *)      break ;;
        esac
    done
}


# -----------------------------------------------------------------------------
# 3c) LED Demo Menu
# -----------------------------------------------------------------------------

#Turn off all LEDs
# In a subshell: sourcing the venv here used to activate it in raspi-config's
# own shell for the rest of the session (PATH, VIRTUAL_ENV).
# turn_off_LEDs.py exits 1 when the panel could not be cleared ("GPIO busy"
# while another program holds it); its message is kept for handle_error, so a
# failure is reported as one (R-148).
do_led_off() {
  _lo_out=$(
    [ -f "$VENV_ACTIVATE" ] && . "$VENV_ACTIVATE"
    python3 "$BIN_DIR/turn_off_LEDs.py" 2>&1
  )
  _lo_rc=$?
  if [ "$_lo_rc" -ne 0 ]; then
    RQ_LAST_DEMO_ERROR=$(printf '%s\n' "$_lo_out" | grep -v '^Turning off' | tail -n 3)
  fi
  return "$_lo_rc"
}

# Programs holding the LED panel, one "PID name" per line; empty when it is
# free (rq_clear_leds.sh --holders, the same check the wizard uses).
_rq_led_holders() {
  "$BIN_DIR/rq_clear_leds.sh" --holders 2>/dev/null || true
}

# Before an LED demo: if another program holds the panel, name it and offer to
# stop it (R-162). On a Pi 4 a second LED program used to draw over the first
# without any error. Returns 1 when the person keeps it - then do not start.
_rq_led_ready() {
  _lr_h=$(_rq_led_holders)
  [ -n "$_lr_h" ] || return 0
  _lr_n=$(printf '%s\n' "$_lr_h" | sed 's/^[0-9]* /  /')
  _lr_rows=$(printf '%s\n' "$_lr_h" | wc -l)
  if whiptail --title "LED Panel in Use" --yes-button "Stop It" --no-button "Cancel" --yesno \
      "Another program is using the LED panel:\n\n$_lr_n\n\nStop it and start this demo?" \
      $((_lr_rows + 10)) 70; then
    "$BIN_DIR/rq_clear_leds.sh" --stop >/dev/null 2>&1
    return 0
  fi
  return 1
}

# run_demo for a demo that drives the LED panel: the panel must be free first,
# and it is cleared afterwards - unless the demo was left running ("Keep
# running"). Same arguments as run_demo.
run_led_demo() {
  _rq_led_ready || return 0
  run_demo "$@"
  _rld_rc=$?
  if [ -n "${LAST_DEMO_PGID:-}" ] && kill -0 "$LAST_DEMO_PGID" 2>/dev/null; then
    return "$_rld_rc"
  fi
  _rld_err="${RQ_LAST_DEMO_ERROR:-}"
  do_led_off >/dev/null 2>&1
  RQ_LAST_DEMO_ERROR="$_rld_err"
  return "$_rld_rc"
}

# "Turn off all LEDs" / "Clear LEDs": a program that still holds the panel is
# named and, if the person agrees, stopped first. Says so when it fails.
do_led_clear() {
  _lc_h=$(_rq_led_holders)
  if [ -n "$_lc_h" ]; then
    _lc_n=$(printf '%s\n' "$_lc_h" | sed 's/^[0-9]* /  /')
    _lc_rows=$(printf '%s\n' "$_lc_h" | wc -l)
    if ! whiptail --title "LED Panel in Use" --yes-button "Stop It" --no-button "Cancel" --yesno \
        "Another program is using the LED panel:\n\n$_lc_n\n\nStop it and turn the LEDs off?" \
        $((_lc_rows + 10)) 70; then
      return 0
    fi
    "$BIN_DIR/rq_clear_leds.sh" --stop >/dev/null 2>&1
  fi
  do_led_off
}

# -----------------------------------------------------------------------------
# 3c) LED Display Menu (Text & Logo Display)
# -----------------------------------------------------------------------------

do_led_custom_text() {
    run_led_demo "LED Text Display" "$BIN_DIR" bash rq_led_display_text.sh
}

do_led_choose_logo() {
    run_led_demo "LED Logo Display" "$BIN_DIR" bash rq_led_display_logo.sh
}

do_led_demo_scroll_welcome() {
    run_led_demo bg "Scrolling Welcome" "$BIN_DIR" python3 demo_led_text_scroll_welcome.py
}

do_led_demo_status() {
    run_led_demo bg "Status Messages" "$BIN_DIR" python3 demo_led_text_status.py
}

do_led_demo_alert() {
    run_led_demo bg "Alert Flash" "$BIN_DIR" python3 demo_led_text_alert.py
}

do_led_demo_rainbow_scroll() {
    run_led_demo bg "Rainbow Scroll" "$BIN_DIR" python3 demo_led_text_rainbow_scroll.py
}

do_led_demo_rainbow_static() {
    run_led_demo bg "Rainbow Color Cycle" "$BIN_DIR" python3 demo_led_text_rainbow_static.py
}

do_led_demo_gradient() {
    run_led_demo bg "Color Gradient" "$BIN_DIR" python3 demo_led_text_gradient.py
}

do_led_demo_ibm_logo() {
    run_led_demo bg "IBM Logo" "$BIN_DIR" python3 rq_led_ibm_logo.py
}

do_led_demo_rasqberry_logo() {
    run_led_demo bg "RasQberry Logo" "$BIN_DIR" python3 demo_led_rasqberry_logo.py
}

do_led_demo_logo_slideshow() {
    run_led_demo bg "Logo Slideshow" "$BIN_DIR" python3 demo_led_logo_slideshow.py
}

# The separator rows have blank tags. Their old tags ("---1") and texts start
# with "-", which whiptail took for unknown options: it failed with
# "---1: unknown option" and this menu never opened (R-024). show_menu now also
# passes "--" before the items.
do_led_display_menu() {
    _disp_last=""
    while true; do
        FUN=$(show_menu ${_disp_last:+--default-item "$_disp_last"} \
           "RasQberry: LED Text & Logo Display" "Display Options" \
           TEXT    "Display Custom Text" \
           LOGO    "Display Logo from Library" \
           " "     "--- Text Demos ---" \
           SWEL    "Demo: Scrolling Welcome" \
           STAT    "Demo: Status Messages" \
           ALRT    "Demo: Alert Flash" \
           "  "    "--- Color Effect Demos ---" \
           RSCR    "Demo: Rainbow Scroll" \
           RSTA    "Demo: Rainbow Color Cycle" \
           GRAD    "Demo: Color Gradient" \
           "   "   "--- Logo Demos ---" \
           IBML    "Demo: IBM Logo" \
           RQBL    "Demo: RasQberry Logo" \
           SLID    "Demo: Logo Slideshow" \
           "    "  "---" \
           CLEAR   "Clear LEDs") || break
        _disp_last="$FUN"
        case "$FUN" in
            TEXT  ) do_led_custom_text           || { handle_error "Text display failed."; continue; } ;;
            LOGO  ) do_led_choose_logo           || { handle_error "Logo display failed."; continue; } ;;
            SWEL  ) do_led_demo_scroll_welcome   || { handle_error "Demo failed."; continue; } ;;
            STAT  ) do_led_demo_status           || { handle_error "Demo failed."; continue; } ;;
            ALRT  ) do_led_demo_alert            || { handle_error "Demo failed."; continue; } ;;
            RSCR  ) do_led_demo_rainbow_scroll   || { handle_error "Demo failed."; continue; } ;;
            RSTA  ) do_led_demo_rainbow_static   || { handle_error "Demo failed."; continue; } ;;
            GRAD  ) do_led_demo_gradient         || { handle_error "Demo failed."; continue; } ;;
            IBML  ) do_led_demo_ibm_logo         || { handle_error "Demo failed."; continue; } ;;
            RQBL  ) do_led_demo_rasqberry_logo   || { handle_error "Demo failed."; continue; } ;;
            SLID  ) do_led_demo_logo_slideshow   || { handle_error "Demo failed."; continue; } ;;
            CLEAR ) do_led_clear                 || { handle_error "The LEDs could not be turned off."; continue; } ;;
            " "|"  "|"   "|"    " ) continue ;;  # Ignore separator items
            *) break ;;
        esac
    done
}

# The LED panel check (plan R1): "which kit is this, and which way up?", the
# same check as the setup checklist's. The first visit to the LED menu runs it
# while LED_LAYOUT_VERIFIED is false; "skipped" (no panel) and "true" are not
# asked again - the menu item "Check the LED Panel" runs it any time. The env
# is reloaded so the new LED_LAYOUT / LED_LAYOUT_VERIFIED are visible.
do_led_verify() {
    case "${LED_LAYOUT_VERIFIED:-false}" in
        true|skipped) [ "${1:-}" = "--again" ] || return 0 ;;
    esac
    bash "$BIN_DIR/rq_led_setup_wizard.sh" --verify || true
    # keeps raspi-config's INTERACTIVE etc. (R-001)
    _rq_load_env 2>/dev/null || true
}

do_select_led_option() {
    # First visit: the check, while the panel has not been checked. The wizard
    # saves LED_LAYOUT_VERIFIED, so it is asked once; _RQ_LED_VERIFY_DONE also
    # keeps a cancelled check from coming back within this menu session.
    if [ -z "${_RQ_LED_VERIFY_DONE:-}" ]; then
        _RQ_LED_VERIFY_DONE=1
        do_led_verify
    fi
    _led_last=""
    while true; do
        # One layout setting (Q22): "Configure Matrix Layout" wrote the retired
        # LED_MATRIX_LAYOUT, which only text and logos read - they came out
        # scrambled on the four-panel kit (R-022). The check and the wizard
        # set LED_LAYOUT, which everything uses.
        FUN=$(show_menu ${_led_last:+--default-item "$_led_last"} "RasQberry: LEDs" "LED options" \
           OFF "Turn off all LEDs" \
           DISP "Text & Logo Display" \
           quicktest "Quick LED Test (6 colours)" \
           test "LED Test & Diagnostics" \
           simple "Simple LED Demo" \
           IBM "IBM LED Demo" \
           check "Check the LED Panel (which kit, which way up)" \
           targets "Output Targets (panel / on-screen / browser)" \
           wizard "LED Setup Wizard (other panels, wiring check)") || break
        _led_last="$FUN"
        case "$FUN" in
            OFF ) do_led_clear || { handle_error "The LEDs could not be turned off."; continue; } ;;
            DISP ) do_led_display_menu || { handle_error "Failed to open text/logo display menu."; continue; } ;;
            quicktest )
                run_led_demo bg "Quick LED Test" "$BIN_DIR" python3 rq_test_leds.py || { handle_error "Quick LED test failed."; continue; }
                ;;
            test )
                run_led_demo "LED Test" "$BIN_DIR" bash rq_led_test.sh || { handle_error "LED test failed."; continue; }
                ;;
            simple )
                run_led_demo bg "Simple LED Demo" "$BIN_DIR" python3 rq_led_simpletest.py || { handle_error "Simple LED demo failed."; continue; }
                ;;
            IBM )
                run_led_demo bg "IBM LED Demo" "$BIN_DIR" python3 rq_led_ibm_logo.py || { handle_error "IBM LED demo failed."; continue; }
                ;;
            check )
                do_led_verify --again
                ;;
            targets )
                do_led_output_menu || { handle_error "Failed to update LED output targets."; continue; }
                ;;
            wizard )
                # Interactive whiptail walkthrough (own process); finds the
                # physical layout and writes LED_LAYOUT. It ends with status 0
                # after its own messages (a stopped check, a busy panel), so
                # the box below is only for real errors (R-133).
                bash "$BIN_DIR/rq_led_setup_wizard.sh" || { _rq_load_env 2>/dev/null; handle_error "The LED setup wizard stopped with an error."; continue; }
                _rq_load_env 2>/dev/null || true
                ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3d) Quantum Lights Out Menu
# -----------------------------------------------------------------------------

do_select_qlo_option() {
    _qlo_last=""
    while true; do
        FUN=$(show_menu ${_qlo_last:+--default-item "$_qlo_last"} "RasQberry: Quantum Lights Out" "Options" \
           QLO  "Run Demo (LED panel)" \
           QLOC "Run Demo (console)") || break
        _qlo_last="$FUN"
        case "$FUN" in
            QLO  ) run_qlo_demo      || { handle_error "QLO demo failed."; continue; } ;;
            QLOC ) run_qlo_demo console    || { handle_error "QLO console demo failed."; continue; } ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3e) Quantum Raspberry-Tie Menu
# -----------------------------------------------------------------------------

# The entries are the manifest's variants (rq_demo_quantum-raspberry-tie.json),
# run through the demo engine like the desktop icons. The menu used to start
# QuantumRaspberryTie.v7_1.py itself, a file the pinned checkout does not have,
# so every backend failed silently (R-023). An IBM Quantum account is needed for
# "real" only: Raspberry Tie asks for it when none is saved, and it is read from
# and saved to the desktop user's ~/.qiskit like everywhere else.
do_select_qrt_option() {
    _qrt_last=""
    while true; do
        FUN=$(show_menu ${_qrt_last:+--default-item "$_qrt_last"} \
           "RasQberry: Quantum Raspberry Tie" "Where should the circuit run?" \
           simulator "Local simulator (no account needed)" \
           noise     "Local simulator with a noise model" \
           real      "Real IBM Quantum computer (IBM Quantum account)") || break
        _qrt_last="$FUN"
        case "$FUN" in
            simulator|noise|real)
                # the engine asks before a first download, then runs it
                run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-raspberry-tie "$FUN" \
                    || { handle_error "Raspberry Tie could not run."; continue; }
                ;;
            *) break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 3f) Main Quantum Demo Menu
# -----------------------------------------------------------------------------

# Main quantum demo menu - FULLY GENERATED from the demo manifests.
#
# The demo list is built from the auto-generated cache (DEMO_MENU_ITEMS +
# dispatch_demo_by_id, produced by rq_demo_generate_menu.sh from every manifest,
# ordered by menu.order). Any newly installed or externally-added catalog demo
# (e.g. traqmania) appears automatically - there is no curated hardcoded list to
# keep in sync. Only demos that have their OWN multi-option submenu (or aren't
# directly launchable) are excluded from the generated list and handled
# explicitly: LED (setup wizard / tests), QLO (GUI vs console), QRT (backends);
# led-demos has no launcher and lives under the LED submenu.
_SUBMENU_DEMO_IDS="quantum-lights-out quantum-raspberry-tie led-demos"

do_quantum_demo_menu() {
  _qd_last=""
  while true; do
    # Build the generated demo list, dropping the submenu-handled ids (so they
    # don't appear twice). POSIX-safe: consume the original pairs and re-append
    # the kept ones, tracking the original count so appended pairs aren't reread.
    # NOTE: DEMO_MENU_ITEMS is emitted one "tag" "desc" pair per line; newlines
    # are shell command separators, so collapse them to spaces before eval or
    # `set --` gets zero args and every generated demo silently disappears.
    eval "set -- $(printf '%s' "${DEMO_MENU_ITEMS:-}" | tr '\n' ' ')"
    _pairs=$(( $# / 2 )); _i=0
    while [ "$_i" -lt "$_pairs" ]; do
      _tag="$1"; _desc="$2"; shift 2
      case " $_SUBMENU_DEMO_IDS " in
        *" $_tag "*) : ;;                       # skip: has its own submenu
        *) set -- "$@" "$_tag" "$_desc" ;;      # keep
      esac
      _i=$(( _i + 1 ))
    done

    # The generated list could not be loaded (see _rq_load_demo_cache): say so
    # once instead of quietly showing a short menu.
    if [ "${_RQ_DEMO_CACHE_STATE:-ok}" != ok ] && [ -z "${_RQ_DEMO_CACHE_WARNED:-}" ]; then
        _RQ_DEMO_CACHE_WARNED=1
        whiptail --title "Demo list" --msgbox \
            "The list of demos could not be loaded, so only the fixed entries are shown.\n\nTo rebuild it: RasQberry -> Advanced -> Refresh the demo list." 11 70
    fi

    FUN=$(show_menu ${_qd_last:+--default-item "$_qd_last"} \
       "RasQberry: Quantum Demos" "Select a demo or option" \
       LED  "LEDs: setup, tests and LED demos" \
       QLO  "Quantum Lights Out (LED panel / console)" \
       QRT  "Quantum Raspberry Tie (simulator or real quantum computer)" \
       "$@" \
       DALL "Download all demos (one-time setup)" \
       ADDX "Add demo from catalogue" \
       REM  "Remove a demo (free space)" \
       UPD  "Update demos (newer versions)" \
       LOOP "Continuous Demo Loop (Conference)" \
       STOP "Stop last running demo and clear LEDs" \
       DSTP "Stop Docker demos (Workshop & Qiskit Server, Quantum Lab...)") || break
    _qd_last="$FUN"
    case "$FUN" in
      LED)  do_select_led_option       || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option       || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option       || { handle_error "Failed to open QRT options."; continue; } ;;
      DALL) do_download_all_demos      || continue ;;
      ADDX) do_add_external_demo       || { handle_error "Failed to add demo from catalogue."; continue; } ;;
      REM)  do_remove_demo             || { handle_error "Could not remove the demo."; continue; } ;;
      LOOP) run_demo_loop
            # 130/143: stopped with Ctrl+C - the loop's own emergency stop
            case $? in 0|130|143) ;; *) handle_error "The demo loop stopped with an error."; continue ;; esac ;;
      STOP) stop_last_demo             || { handle_error "Failed to stop demo."; continue; } ;;
      UPD)  do_update_demos            || { handle_error "Could not update the demo."; continue; } ;;
      DSTP) do_stop_docker_demos       || continue ;;
      "")   continue ;;
      # Any other tag is a manifest demo id -> universal dispatch (via the
      # cache), or its submenu of variants (menu.variant_menu).
      *)    if _dv_items=$(demo_variant_items "$FUN" 2>/dev/null) && [ -n "$_dv_items" ]; then
                do_demo_variant_menu "$FUN" "$_dv_items"
            else
                run_engine_demo dispatch_demo_by_id "$FUN" \
                    || { handle_error "Could not run $(_rq_demo_label "$FUN")."; continue; }
            fi ;;
    esac
  done
}

# Submenu of a demo's variants (from the cache: demo_variant_items), each run
# through the demo engine like the desktop icons, e.g. Fun with Quantum: one
# entry per notebook game, the website and the family.
#   do_demo_variant_menu DEMO_ID ITEMS
do_demo_variant_menu() {
  _dv_id="$1"; _dv_list="$2"; _dv_last=""
  _dv_name=$(_rq_demo_label "$_dv_id")
  while true; do
    eval "set -- $(printf '%s' "$_dv_list" | tr '\n' ' ')"
    _dv_sel=$(show_menu ${_dv_last:+--default-item "$_dv_last"} \
       "RasQberry: $_dv_name" "Select an entry" "$@") || break
    [ -n "$_dv_sel" ] || continue
    _dv_last="$_dv_sel"
    run_engine_demo "$BIN_DIR/rq_demo_run.sh" "$_dv_id" "$_dv_sel" \
        || handle_error "Could not run $_dv_name ($_dv_sel)."
  done
  return 0
}

# Menu text of a generated demo entry (its name), for messages.
_rq_demo_label() {
    _dl=$(printf '%s\n' "${DEMO_MENU_ITEMS:-}" | sed -n "s/^\"$1\" \"\(.*\)\"\$/\1/p" | head -n 1)
    printf '%s' "${_dl:-$1}"
}

# -----------------------------------------------------------------------------
# 3g) Main Raspi Config Menu
# -----------------------------------------------------------------------------

do_show_system_info() {
  local info
  if [ -x /usr/bin/rq_info.sh ]; then
    info=$(/usr/bin/rq_info.sh 2>/dev/null)
  else
    info="RasQberry version: $(cat /etc/rasqberry-version 2>/dev/null || echo unknown)"
  fi
  # Name, address, power and the rest come first; a long list scrolls
  show_msgbox_fit "RasQberry System Information" \
    "$info\n\nFor a bug report: rq_info.sh --report (saves the logs to a file)" 78
}

# -----------------------------------------------------------------------------
# A/B Boot Partition Expansion
# -----------------------------------------------------------------------------

# What this card can do: dual | dual-pending | single | single-pending |
# standard (rq_expand_ab.sh decides from the card and partition sizes)
ab_card_mode() {
    local mode
    mode=$("$BIN_DIR/rq_expand_ab.sh" mode 2>/dev/null) || mode=""
    echo "${mode:-standard}"
}

# Prepare an A/B card by hand: two systems on a 64GB+ card, or one system
# using the whole card on a smaller one. A newly written card does this by
# itself on its first start (rasqberry-ab-layout.service) unless the CONFIG
# partition holds "no-auto-expand"; this is for that case and for cards
# written from older images. The work is done by rq_expand_ab.sh.
do_expand_ab_partitions() {
    local mode how title plan rc=0
    mode=$(ab_card_mode)
    case "$mode" in
        dual-pending)   how=--dual;   title="Prepare the card for A/B updates" ;;
        single-pending) how=--single; title="Use the whole card" ;;
        *)
            whiptail --title "This SD card" --msgbox "$("$BIN_DIR/rq_expand_ab.sh" explain 2>&1)" 18 78
            return 0 ;;
    esac
    if ! plan=$("$BIN_DIR/rq_expand_ab.sh" plan "$how" --text 2>&1); then
        whiptail --title "$title" --msgbox "$plan" 12 72
        return 1
    fi
    whiptail --title "$title" --yesno "$plan\n\nProceed?" 18 72 || return 0

    clear
    echo ""
    echo "$title - this takes a few minutes. Do NOT switch off the Pi."
    echo ""
    "$BIN_DIR/rq_expand_ab.sh" apply "$how" --yes || rc=$?
    if [ "$rc" -eq 0 ]; then
        whiptail --title "Done" --msgbox "$("$BIN_DIR/rq_expand_ab.sh" explain 2>&1)" 18 78
    else
        whiptail --title "Not finished" --msgbox \
            "Setting up the card did not finish.\n\nThe details are in /var/log/rasqberry-expand.log.\nIf the Pi is restarted, the next start finishes the job by itself." \
            12 72
        return 1
    fi
}

# -----------------------------------------------------------------------------
# LED output targets (#231): choose WHERE LED output appears - the physical
# strip, the on-screen virtual GUI, and/or the browser emulator (LED_WEB). The
# three are independent booleans, so a checklist is the natural widget: it shows
# and edits all three at once, pre-ticked from the current env. Only the flags
# that actually change are written back (each write reloads the env file).
# -----------------------------------------------------------------------------
do_led_output_menu() {
  cur_phys=$(check_environment_variable "LED_PHYSICAL")
  cur_virt=$(check_environment_variable "LED_VIRTUAL")
  cur_web=$(check_environment_variable "LED_WEB")

  web_port=$(check_environment_variable "LED_WEB_PORT")
  [ -z "$web_port" ] && web_port="8098"

  # Map a "true"/other value to the checklist ON/OFF state.
  on_state() { [ "$1" = "true" ] && echo "ON" || echo "OFF"; }

  SEL=$(whiptail --title "LED Output Targets" --checklist \
    "Choose where LED output appears.\nSpace toggles an item, Tab to <Ok>, Enter confirms." 12 74 3 \
    PHYSICAL "Physical LED strip" "$(on_state "$cur_phys")" \
    VIRTUAL  "On-screen virtual matrix (GUI window)" "$(on_state "$cur_virt")" \
    WEB      "Browser view (http://<pi>:${web_port})" "$(on_state "$cur_web")" \
    3>&1 1>&2 2>&3) || return 0

  # whiptail returns the ticked tags quoted and space-separated
  # ("PHYSICAL" "VIRTUAL"). Match each tag in that string instead of word
  # splitting it: the split depended on IFS, and with the old file-scope IFS
  # (no space) two ticks came back as one word, so confirming the default
  # silently turned the virtual view off (R-018).
  new_phys="false"; new_virt="false"; new_web="false"
  _sel=" $(printf '%s' "$SEL" | tr -d '"' | tr '\n\t' '  ') "
  case "$_sel" in *" PHYSICAL "*) new_phys="true" ;; esac
  case "$_sel" in *" VIRTUAL "*)  new_virt="true" ;; esac
  case "$_sel" in *" WEB "*)      new_web="true" ;; esac

  # Guard against turning EVERYTHING off (no output anywhere) - keep the strip.
  if [ "$new_phys" = "false" ] && [ "$new_virt" = "false" ] && [ "$new_web" = "false" ]; then
    whiptail --title "LED Output Targets" --msgbox \
      "At least one output target is required.\n\nKeeping the physical LED strip enabled." 9 66
    new_phys="true"
  fi

  # Write only the flags that changed (each write reloads the env file).
  [ "$new_phys" != "$cur_phys" ] && update_environment_file "LED_PHYSICAL" "$new_phys"
  [ "$new_virt" != "$cur_virt" ] && update_environment_file "LED_VIRTUAL" "$new_virt"
  [ "$new_web" != "$cur_web" ] && update_environment_file "LED_WEB" "$new_web"

  # When the browser view is on, start it now and show the URL so the user does
  # not have to launch a demo first just to discover the address.
  if [ "$new_web" = "true" ]; then
    # rq_led_utils lives in BIN_DIR (/usr/bin when installed), not on Python's
    # default path - set PYTHONPATH like the wizard does for its reap call.
    PYTHONPATH="${BIN_DIR}:${PYTHONPATH:-}" python3 -c \
      'import rq_led_utils; rq_led_utils._ensure_virtual_led_web_running()' 2>/dev/null || true
    lan_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    [ -z "$lan_ip" ] && lan_ip="<pi-ip>"
    whiptail --title "LED Browser View" --msgbox \
      "Browser view enabled.\n\nOpen from any device on the network:\n  http://${lan_ip}:${web_port}\n\nThe view updates whenever an LED demo runs.\nRestart a running demo for target changes to take effect." \
      13 74
  fi
}

# -----------------------------------------------------------------------------
# Update from GitHub Branch
# -----------------------------------------------------------------------------

# Detect current repository from git config or environment
detect_git_repo() {
    local repo=""

    # Method 0: the repository this image was built from (#289)
    if [ -n "${RQB_BUILD_REPO:-}" ]; then
        echo "$RQB_BUILD_REPO"
        return 0
    fi

    # Method 1: Check git remote in user's repo directory
    local git_config="${REPO_DIR}/.git/config"

    if [ -f "$git_config" ]; then
        local origin_url
        origin_url=$(grep -A2 '\[remote "origin"\]' "$git_config" 2>/dev/null | grep 'url' | sed 's/.*= //' | head -1)

        if [ -n "$origin_url" ]; then
            if echo "$origin_url" | grep -q "github.com"; then
                repo=$(echo "$origin_url" | sed 's|.*github\.com[:/]||' | sed 's|\.git$||')
            fi
        fi
    fi

    # Method 2: Use environment variables
    if [ -z "$repo" ]; then
        local git_user="${RQB_GIT_USER:-}"
        local git_repo="${REPO:-}"
        if [ -n "$git_user" ] && [ -n "$git_repo" ]; then
            repo="${git_user}/${git_repo}"
        fi
    fi

    # Method 3: Default fallback
    if [ -z "$repo" ]; then
        repo="JanLahmann/RasQberry-Two"
    fi

    echo "$repo"
}

# Update from GitHub branch menu handler
do_update_from_branch() {
    local detected_repo
    detected_repo=$(detect_git_repo)

    # Step 1: Repository selection (or undo the last branch update, R-115)
    local tmpfile=$(mktemp)
    exec 4>"$tmpfile"

    set -- "detected" "Use detected repository ($detected_repo)" \
        "custom"   "Enter custom repository"
    if [ -s /var/tmp/rasqberry-last-backup ]; then
        set -- "$@" "restore" "Undo the last update from a branch"
    fi
    whiptail --output-fd 4 --title "Update from GitHub Branch" --menu \
        "Select repository source:\n\nDetected: $detected_repo" \
        15 70 $(($# / 2)) "$@" \
        1>/dev/tty 2>/dev/tty </dev/tty

    local exit_code=$?
    exec 4>&-

    if [ $exit_code -ne 0 ]; then
        rm -f "$tmpfile"
        return 0
    fi

    local repo_choice=$(cat "$tmpfile")
    rm -f "$tmpfile"

    if [ "$repo_choice" = "restore" ]; then
        if ! whiptail --title "Undo branch update" --yesno \
            "Put back the scripts and configuration saved before the last update from a branch?\n\nSaved: $(cat /var/tmp/rasqberry-last-backup)" 12 70; then
            return 0
        fi
        local restore_output restore_result=0
        printf '\nRestoring the saved scripts and configuration...\n'
        restore_output=$("$BIN_DIR/rq_update_from_branch.sh" --restore 2>&1) || restore_result=$?
        if [ "$restore_result" -eq 0 ]; then
            whiptail --title "Restored" --msgbox \
                "The saved scripts and configuration are back.\n\nExit and re-enter raspi-config for menu changes to take effect." 11 70
        else
            whiptail --title "Restore Failed" --msgbox \
                "Restoring failed:\n\n$(printf '%s\n' "$restore_output" | tail -n 8)" 18 76
        fi
        return 0
    fi

    local repo="$detected_repo"
    if [ "$repo_choice" = "custom" ]; then
        repo=$(whiptail --inputbox "Enter GitHub repository (user/repo):" 10 60 "$detected_repo" 3>&1 1>&2 2>&3)
        if [ $? -ne 0 ] || [ -z "$repo" ]; then
            return 0
        fi
        # Validate format
        if ! echo "$repo" | grep -q '^[^/]\+/[^/]\+$'; then
            whiptail --title "Invalid Format" --msgbox "Invalid repository format.\n\nPlease use: username/repository" 10 50
            return 1
        fi
    fi

    # Step 2: Branch selection
    # Default to the branch this image was built from (#289)
    # main holds no RasQberry Two scripts (website only), so it is not offered
    local branch default_branch="${RQB_BUILD_BRANCH:-beta}" built_from=""
    [ "$default_branch" = "main" ] && default_branch="beta"
    [ -f /etc/rasqberry-version ] && built_from="\n\nThis image: $(cat /etc/rasqberry-version)"
    [ -n "${RQB_BUILD_BRANCH:-}" ] && built_from="$built_from\nBuilt from: ${RQB_BUILD_REPO:-?} @ $RQB_BUILD_BRANCH"
    branch=$(whiptail --inputbox "Enter branch name to update from:$built_from\n\nCommon branches: beta, development" 14 70 "$default_branch" 3>&1 1>&2 2>&3)
    if [ $? -ne 0 ] || [ -z "$branch" ]; then
        return 0
    fi

    # Step 3: Confirmation
    if ! whiptail --title "Confirm Update" --yesno \
        "Update the RasQberry Two scripts and configuration?\n\nRepository: $repo\nBranch: $branch\n\nUpdates: scripts in /usr/bin, config files in /usr/config (your settings are kept), boot scripts, services and autostart entries.\nNot updated: system packages, kernel, Python environment.\n\nThe current scripts and configuration are saved first; 'Undo the last update from a branch' puts them back." \
        19 72; then
        return 0
    fi

    # Step 4: Run update. A plain line, not an infobox: an infobox vanishes
    # at once in most terminals and the screen looks frozen (R-021)
    printf '\nUpdating from GitHub (%s, branch %s). This may take a minute...\n' "$repo" "$branch"

    local update_output
    local update_result

    # Run the update script and capture output
    update_output=$("$BIN_DIR/rq_update_from_branch.sh" --repo "$repo" --branch "$branch" 2>&1) || update_result=$?

    if [ "${update_result:-0}" -eq 0 ]; then
        whiptail --title "Update Complete" --msgbox \
            "Update completed successfully!\n\nRepository: $repo\nBranch: $branch\n\nChanges applied:\n  - Scripts updated in /usr/bin/\n  - Config files updated in /usr/config/\n  - Environment reloaded\n\nYou may need to exit and re-enter raspi-config\nfor menu changes to take effect." \
            18 70
    else
        # The cause is at the end of the output: show that part (R-115)
        whiptail --title "Update Failed" --msgbox \
            "Update failed:\n\n$(printf '%s\n' "$update_output" | grep -v '^\[' | tail -n 8)\n\nFull log: /var/log/rasqberry-branch-update.log" \
            20 76
        return 1
    fi
}

# -----------------------------------------------------------------------------
# A/B updates: helpers
# -----------------------------------------------------------------------------
# The A/B model (Jan, 2026-10-02): Slot A is the stable system, Slot B the
# testing slot. Updates always go into Slot B; a tested Slot B is copied to
# Slot A with PROMOTE. The logic lives in rq_slot_manager.sh, rq_update_slot.sh
# and rq_ab_releases.sh; these functions only ask and explain. POSIX sh, no
# set -e: this file runs inside raspi-config.
#
# Long operations (download, PROMOTE) run in the foreground of this terminal
# and print their own progress. A whiptail --infobox would vanish at once
# (whiptail restores the screen when it exits), and output captured with
# $( ) hides any prompt and any progress (R-051).

# Value of <key> in `rq_slot_manager.sh summary` output
ab_value() {
    printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n 1
}

# What a slot holds, in words
ab_describe() {
    case "$1" in
        EMPTY)      echo "empty (no system)" ;;
        INCOMPLETE) echo "unfinished (an update or copy was interrupted)" ;;
        UNKNOWN|"") echo "unknown" ;;
        SYSTEM)     echo "a system without version information" ;;
        *)          echo "$1" ;;
    esac
}

# True when a slot content value is something the Pi can start
ab_has_system() {
    case "$1" in
        EMPTY|INCOMPLETE|UNKNOWN|"") return 1 ;;
        *) return 0 ;;
    esac
}

# Bytes -> "1.7 GB" (decimal, as card and download sizes are sold)
ab_gb() {
    case "${1:-0}" in
        ""|0|*[!0-9]*) echo "about 2 GB" ;;
        *) awk -v b="$1" 'BEGIN { printf "%.1f GB\n", b / 1000000000 }' ;;
    esac
}

ab_width() {
    _ab_cols=$(tput cols 2>/dev/null || echo 80)
    [ "$_ab_cols" -ge 64 ] 2>/dev/null || _ab_cols=80
    [ "$_ab_cols" -gt 80 ] && _ab_cols=80
    echo $((_ab_cols - 4))
}

# Height for a box showing <text> at <width>, plus <extra> rows, capped at
# the terminal height (whiptail cuts off text that does not fit)
ab_box_height() {
    _ab_h=$(printf '%b\n' "$1" | fold -s -w $(($2 - 4)) | wc -l)
    _ab_h=$((_ab_h + $3))
    _ab_rows=$(tput lines 2>/dev/null || echo 24)
    [ "$_ab_rows" -ge 12 ] 2>/dev/null || _ab_rows=24
    [ "$_ab_h" -gt "$_ab_rows" ] && _ab_h=$_ab_rows
    echo "$_ab_h"
}

ab_msgbox() {
    _ab_w=$(ab_width)
    _ab_hh=$(ab_box_height "$2" "$_ab_w" 7)
    if [ "$(printf '%b\n' "$2" | fold -s -w $((_ab_w - 4)) | wc -l)" -gt $((_ab_hh - 7)) ]; then
        whiptail --title "$1" --scrolltext --msgbox "$2" "$_ab_hh" "$_ab_w"
    else
        whiptail --title "$1" --msgbox "$2" "$_ab_hh" "$_ab_w"
    fi
}

# ab_yesno <title> <yes label> <no label> <text> [--defaultno]
ab_yesno() {
    _ab_w=$(ab_width)
    _ab_hh=$(ab_box_height "$4" "$_ab_w" 7)
    if [ "${5:-}" = "--defaultno" ]; then
        whiptail --title "$1" --yes-button "$2" --no-button "$3" --defaultno --yesno "$4" "$_ab_hh" "$_ab_w"
    else
        whiptail --title "$1" --yes-button "$2" --no-button "$3" --yesno "$4" "$_ab_hh" "$_ab_w"
    fi
}

# ab_menu <title> <text> <tag> <item>... ; prints the chosen tag.
# AB_MENU_DEFAULT=<tag> puts the cursor on that item.
ab_menu() {
    _ab_title="$1"; _ab_text="$2"; shift 2
    _ab_n=$(($# / 2))
    _ab_w=$(ab_width)
    _ab_hh=$(ab_box_height "$_ab_text" "$_ab_w" $((_ab_n + 7)))
    whiptail --title "$_ab_title" --default-item "${AB_MENU_DEFAULT:-}" \
        --menu "$_ab_text" "$_ab_hh" "$_ab_w" "$_ab_n" "$@" 3>&1 1>&2 2>&3
}

ab_pause() {
    printf '\n%s' "${1:-Press Enter to return to the menu.}"
    read -r _ab_dummy < /dev/tty
}

# What to do when Slot B is not set up (the 16MB placeholder). [summary]:
# `rq_slot_manager.sh summary` output; its card_mode says whether the card is
# not prepared yet or runs one system (single-system mode, R-006).
ab_not_expanded_text() {
    _ab_mode=$(ab_value "${1:-}" card_mode)
    case "$_ab_mode" in ""|unknown) _ab_mode=$(ab_card_mode) ;; esac
    case "$_ab_mode" in
        single|single-pending)
            "$BIN_DIR"/rq_expand_ab.sh explain --update 2>/dev/null && return 0 ;;
        dual-pending)
            echo "Slot B is not set up yet: it is still the small placeholder the A/B image ships with.\n\nPrepare the card first (Software & Image Updates -> Prepare the card for A/B updates), then install the update into Slot B."
            return 0 ;;
    esac
    _ab_dev=$(lsblk -no pkname "$(findmnt / -o source -n)" 2>/dev/null | head -n 1)
    _ab_size=$(lsblk -bno SIZE "/dev/${_ab_dev:-mmcblk0}" 2>/dev/null | head -n 1)
    # 58 GiB: the same limit as rq_expand_ab.sh (a "64GB" card is about 59.6 GiB)
    if [ "$((${_ab_size:-0} / 1024 / 1024 / 1024))" -ge 58 ]; then
        echo "Slot B is not set up yet: it is still the small placeholder the A/B image ships with.\n\nPrepare the card first (Software & Image Updates -> Prepare the card for A/B updates), then install the update into Slot B."
    else
        echo "This card is too small for two systems, so an update cannot be installed into Slot B.\n\nDownload the new image from rasqberry.org/latest/ and write it to a card. Writing a new image erases the card: copy your notebooks and your IBM Quantum account (~/.qiskit) first, or use a second card."
    fi
}

# Title for that text
ab_not_expanded_title() {
    _ab_mode=$(ab_value "${1:-}" card_mode)
    case "$_ab_mode" in ""|unknown) _ab_mode=$(ab_card_mode) ;; esac
    case "$_ab_mode" in
        single|single-pending) echo "One system on this card" ;;
        *)                     echo "Slot B is not set up" ;;
    esac
}

# How a slot gets a system
ab_fill_hint() {
    if [ "$1" = "B" ]; then
        echo "Install a system into Slot B first: Slot Manager -> Install an update into Slot B."
    else
        echo "Slot A gets a system when you PROMOTE a tested Slot B."
    fi
}

ab_slot_label() {
    if [ "$1" = "A" ]; then echo "stable"; else echo "testing"; fi
}

# The other slot
ab_other() {
    if [ "$1" = "A" ]; then echo "B"; else echo "A"; fi
}

# True right after PROMOTE, before the restart: running a confirmed Slot B,
# the next start is Slot A, and both slots hold the same version
ab_promoted() {
    [ "$(ab_value "$1" current)" = "B" ] && [ "$(ab_value "$1" default)" = "A" ] \
        && [ "$(ab_value "$1" confirmed)" = "yes" ] \
        && ab_has_system "$(ab_value "$1" slot_a)" \
        && [ "$(ab_value "$1" slot_a)" = "$(ab_value "$1" slot_b)" ]
}

# What the user should do next, from the summary
ab_next_step() {
    _ab_cur=$(ab_value "$1" current)
    _ab_def=$(ab_value "$1" default)
    if [ "$(ab_value "$1" expanded)" != "yes" ]; then
        echo "Slot B is not set up yet: prepare the card first (Software & Image Updates -> Prepare the card for A/B updates)."
    elif ab_promoted "$1"; then
        echo "PROMOTE is done: restart to start from Slot A. Then Slot B is free for the next update."
    elif [ "$_ab_cur" = "B" ] && [ "$(ab_value "$1" confirmed)" != "yes" ]; then
        echo "Slot B is on trial: the health check confirms it after a good start. Otherwise the next restart returns to Slot A."
    elif [ "$_ab_def" = "A" ] || [ "$_ab_def" = "B" ] && [ "$_ab_def" != "$_ab_cur" ]; then
        echo "The next restart starts Slot ${_ab_def}."
    elif [ "$_ab_cur" = "A" ]; then
        if ab_has_system "$(ab_value "$1" slot_b)"; then
            echo "Next: install a newer update into Slot B, or restart into Slot B to use it."
        else
            echo "Next: install an update into Slot B."
        fi
    else
        echo "If this version works well, PROMOTE copies it to Slot A. Then Slot B is free for the next update."
    fi
}

# -----------------------------------------------------------------------------
# Check for a newer image (#139, R-048)
# -----------------------------------------------------------------------------

do_check_for_update() {
    local out rc=0 summary prc=0
    # A plain line: an infobox would vanish at once
    printf '\nAsking rasqberry.org for the latest release...\n'
    out=$("$BIN_DIR"/rq_update_check.sh --refresh 2>&1) || rc=$?
    if [ "$rc" -eq 0 ]; then
        ab_msgbox "Check for updates" "$out"
        return 0
    fi
    if [ "$rc" -ne 10 ]; then
        ab_msgbox "Check for updates" "Could not check for updates.\n\n$out"
        return 0
    fi

    summary=$("$BIN_DIR"/rq_slot_manager.sh summary 2>/dev/null)
    if [ "$(ab_value "$summary" layout)" != "ab" ]; then
        # Standard image: no second slot - a new card is the way (R-045)
        ab_msgbox "Update available" "$out\n\nTo install it, download it from rasqberry.org/latest/ and write it to a card.\n\nWriting a new image erases this card: copy your notebooks and your IBM Quantum account (~/.qiskit) first, or use a second card."
        return 0
    fi

    "$BIN_DIR"/rq_update_slot.sh --preflight >/dev/null 2>&1 || prc=$?
    if [ "$prc" -eq 21 ]; then
        ab_msgbox "Update available" "$out\n\n$(ab_not_expanded_text "$summary")"
        return 0
    fi
    if ab_yesno "Update available" "Install now" "Later" \
        "$out\n\nInstall it into Slot B (testing) now? Slot A (stable) stays as it is, so you can go back to it."; then
        do_ab_install_update
    fi
    return 0
}

# Software & Image Updates Menu
do_ab_boot_menu() {
    while true; do
        # What this card can do decides the A/B entries (R-006): the Slot
        # Manager only where there are two systems; on a small card one entry
        # that explains single-system mode instead of dead ends.
        local ab_mode card_text
        ab_mode=$(ab_card_mode)
        set -- CHECK "Check for a newer image"
        case "$ab_mode" in
            dual)
                card_text="A/B image: two systems on this card"
                set -- "$@" SLOTS "Slot Manager (install updates, switch, promote)" ;;
            dual-pending)
                card_text="A/B image: second system not set up yet"
                set -- "$@" EXPAND "Prepare the card for A/B updates (64GB+ card)" ;;
            single-pending)
                card_text="A/B image on a card under 64GB: one system"
                set -- "$@" EXPAND "Use the whole card (one system)" ;;
            single)
                card_text="A/B image on a card under 64GB: one system"
                set -- "$@" ABOUT "Why there are no A/B updates on this card" ;;
            *)
                card_text="Standard image (one system)" ;;
        esac
        # "Update from GitHub Branch" is under RasQberry -> Advanced (Q35)
        FUN=$(show_menu "RasQberry: Software & Image Updates" "$card_text" "$@") || break

        case "$FUN" in
            CHECK)  do_check_for_update     || continue ;;
            EXPAND|ABOUT) do_expand_ab_partitions || continue ;;
            SLOTS)  do_slot_manager_menu    || continue ;;
            *)      continue ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Release picker for Slot B (R-049)
# -----------------------------------------------------------------------------
# Offers the latest A/B image of this image's own channel first (from
# RQB-releases.json); other releases, channels and repositories are behind
# "Other". Standard images are never offered: they cannot fill a slot.
# Prints "url|tag|size"; returns 1 when the user cancels.

ab_pick_image() {
    local current channel latest lrc=0 ltag="" lurl="" ldate lsize="" note prompt choice
    current=$(head -n 1 /etc/rasqberry-version 2>/dev/null | tr -d '[:space:]')
    channel=$("$BIN_DIR"/rq_ab_releases.sh channel 2>/dev/null)
    # stdout is the result of this function: progress goes to stderr (the terminal)
    printf '\nAsking rasqberry.org for the latest %s release...\n' "$channel" >&2
    latest=$("$BIN_DIR"/rq_ab_releases.sh latest 2>&1) || lrc=$?

    set --
    if [ "$lrc" -eq 0 ]; then
        ltag=$(printf '%s\n' "$latest" | cut -f1)
        lurl=$(printf '%s\n' "$latest" | cut -f2)
        ldate=$(printf '%s\n' "$latest" | cut -f3)
        lsize=$(printf '%s\n' "$latest" | cut -f4)
        note="latest ${channel}, ${ldate}, $(ab_gb "$lsize") (recommended)"
        [ "$ltag" = "$current" ] && note="latest ${channel} (the version you are running)"
        set -- "$ltag" "$note"
        prompt="This system: ${current:-unknown} (channel: ${channel})\n\nChoose the release to install into Slot B (testing):"
    else
        prompt="This system: ${current:-unknown} (channel: ${channel})\n\n${latest}\n\nYou can still choose a release from GitHub:"
    fi
    set -- "$@" OTHER "Other release or channel..."

    choice=$(ab_menu "Install an update into Slot B" "$prompt" "$@") || return 1
    if [ "$choice" = "OTHER" ]; then
        ab_pick_other "$channel" "$current"
        return $?
    fi
    echo "${lurl}|${ltag}|${lsize}"
}

ab_pick_other() {
    local channel="$1" current="$2" stream repo="" list lrc=0 choice line t d s note
    # The device's own channel is the default (Q6 is open: the others stay)
    stream=$(AB_MENU_DEFAULT="$channel" ab_menu "Other release" \
        "Choose a release channel. This system follows: ${channel}" \
        beta   "Beta releases" \
        dev    "Development builds (newest, less tested)" \
        stable "Stable releases" \
        REPO   "Another GitHub repository...") || return 1
    if [ "$stream" = "REPO" ]; then
        repo=$(whiptail --title "Other repository" --inputbox \
            "GitHub repository (user/repository):" 10 60 \
            "${RQB_GIT_USER:-JanLahmann}/${REPO:-RasQberry-Two}" 3>&1 1>&2 2>&3) || return 1
        stream=$(AB_MENU_DEFAULT="$channel" ab_menu "Other repository" \
            "Release channel in ${repo}:" \
            beta   "Beta releases" \
            dev    "Development builds (newest, less tested)" \
            stable "Stable releases") || return 1
    fi

    printf '\nAsking GitHub for the %s releases...\n' "$stream" >&2
    if [ -n "$repo" ]; then
        list=$("$BIN_DIR"/rq_ab_releases.sh list "$stream" --repo "$repo" 2>&1) || lrc=$?
    else
        list=$("$BIN_DIR"/rq_ab_releases.sh list "$stream" 2>&1) || lrc=$?
    fi
    if [ "$lrc" -ne 0 ]; then
        ab_msgbox "Release list" "$list"
        return 1
    fi
    if [ -z "$list" ]; then
        ab_msgbox "Release list" "No A/B images found in the '${stream}' channel${repo:+ of $repo}."
        return 1
    fi

    set --
    while IFS= read -r line; do
        [ -n "$line" ] || continue
        t=$(printf '%s\n' "$line" | cut -f1)
        d=$(printf '%s\n' "$line" | cut -f3)
        s=$(printf '%s\n' "$line" | cut -f4)
        note="${d}, $(ab_gb "$s")"
        [ "$t" = "$current" ] && note="${note} (running now)"
        set -- "$@" "$t" "$note"
    done <<EOF
$list
EOF
    choice=$(ab_menu "Choose a release" "A/B images in the '${stream}' channel, newest first:" "$@") || return 1
    line=$(printf '%s\n' "$list" | awk -F '\t' -v t="$choice" '$1 == t { print; exit }')
    [ -n "$line" ] || return 1
    echo "$(printf '%s\n' "$line" | cut -f2)|${choice}|$(printf '%s\n' "$line" | cut -f4)"
}

# -----------------------------------------------------------------------------
# A/B actions (R-050, R-051, R-055)
# -----------------------------------------------------------------------------

# Install an update into Slot B: checks first, then the picker, then the
# update itself in this terminal (it shows its own progress)
do_ab_install_update() {
    local pre prc=0 summary picked url tag size rest slot_a slot_b rc=0
    printf '\nChecking whether Slot B can take an update...\n'
    pre=$("$BIN_DIR"/rq_update_slot.sh --preflight 2>&1) || prc=$?
    pre=$(printf '%s\n' "$pre" | sed 's/^ERROR: //')
    summary=$("$BIN_DIR"/rq_slot_manager.sh summary 2>/dev/null)
    case "$prc" in
        0)  ;;
        20) ab_offer_free_slot_b "$summary"; return 0 ;;
        21) ab_msgbox "$(ab_not_expanded_title "$summary")" "$(ab_not_expanded_text "$summary")"; return 0 ;;
        *)  ab_msgbox "Cannot install an update now" "$pre"; return 0 ;;
    esac

    picked=$(ab_pick_image) || return 0
    url=${picked%%|*}
    rest=${picked#*|}
    tag=${rest%%|*}
    size=${rest#*|}
    if [ -z "$url" ] || [ -z "$tag" ]; then
        ab_msgbox "Install an update" "No image was selected."
        return 0
    fi

    slot_a=$(ab_describe "$(ab_value "$summary" slot_a)")
    slot_b=$(ab_describe "$(ab_value "$summary" slot_b)")
    ab_has_system "$(ab_value "$summary" slot_b)" && slot_b="${slot_b} - will be replaced"
    ab_yesno "Install an update into Slot B" "Install" "Cancel" \
        "Install ${tag} into Slot B (testing)?\n\nSlot B (testing) now: ${slot_b}\nSlot A (stable): ${slot_a} - not touched\n\nDownload: $(ab_gb "$size"). With unpacking and writing it takes about 20-30 minutes. Progress is shown on this screen; keep the Pi switched on.\n\nWhen it is done, the Pi restarts into Slot B. If Slot B does not start properly, the Pi goes back to Slot A by itself (at the latest after 15 minutes). If the screen stays black, switch the Pi off and on." \
        || return 0

    clear
    printf 'Installing %s into Slot B (testing).\nKeep the Pi switched on. It restarts by itself when the update is done.\n\n' "$tag"
    "$BIN_DIR"/rq_update_slot.sh "$url" "$tag" --slot B || rc=$?
    if [ "$rc" -eq 0 ]; then
        # rq_update_slot.sh ends by asking for the restart into Slot B
        printf '\nThe update is installed. The Pi is restarting into Slot B...\n'
        sleep 120
    fi
    printf '\nThe update did not finish (see the message above; log:\n/var/log/rasqberry-update-slot.log). The running system is unchanged.\n'
    ab_pause
    return 0
}

# UPDATE while running Slot B: Slot B cannot be overwritten, so offer the
# two ways to free it (R-050)
ab_offer_free_slot_b() {
    local summary="$1" a b choice
    a=$(ab_describe "$(ab_value "$summary" slot_a)")
    b=$(ab_describe "$(ab_value "$summary" slot_b)")
    if ab_promoted "$summary"; then
        if ab_yesno "Restart into Slot A first" "Restart now" "Later" \
            "PROMOTE is done: Slot A holds ${a}, but the Pi is still running Slot B.\n\nRestart now? The Pi then starts from Slot A. After the restart, choose 'Install an update into Slot B' again."; then
            clear
            printf 'Restarting into Slot A...\n'
            reboot
            sleep 120
        fi
        return 0
    fi
    set -- PROMOTE "Keep this version: copy it to Slot A, then restart"
    if ab_has_system "$(ab_value "$summary" slot_a)"; then
        set -- "$@" SLOT_A "Go back to the version in Slot A, then restart"
    fi
    choice=$(ab_menu "Slot B is in use" \
        "Updates are always installed into Slot B (testing). You are running Slot B right now, so it cannot be overwritten.\n\nSlot A (stable): ${a}\nSlot B (testing, running): ${b}\n\nFree Slot B first. After the restart, choose 'Install an update into Slot B' again." \
        "$@") || return 0
    case "$choice" in
        PROMOTE) do_ab_promote "$summary" ;;
        SLOT_A)  ab_restart_into A "$summary" ;;
    esac
    return 0
}

# PROMOTE: copy the running, confirmed Slot B to Slot A (R-051: a proper
# dialog instead of an invisible typed prompt, progress on screen)
do_ab_promote() {
    local summary="$1" current a b b_raw rc=0
    current=$(ab_value "$summary" current)
    b_raw=$(ab_value "$summary" slot_b)
    a=$(ab_describe "$(ab_value "$summary" slot_a)")
    b=$(ab_describe "$b_raw")

    if [ "$current" != "B" ]; then
        if ab_has_system "$b_raw"; then
            ab_msgbox "PROMOTE" "PROMOTE copies Slot B to Slot A. It works only while the Pi is running Slot B.\n\nYou are running Slot A (stable): ${a}\nSlot B (testing) holds: ${b}\n\nTo use the version in Slot B, choose 'Restart into Slot B'. Once it has started properly, come back here and PROMOTE it."
        else
            ab_msgbox "PROMOTE" "PROMOTE copies Slot B to Slot A. It works only while the Pi is running Slot B.\n\nYou are running Slot A (stable): ${a}\nSlot B (testing) holds: ${b}\n\n$(ab_fill_hint B)"
        fi
        return 0
    fi
    if [ "$(ab_value "$summary" confirmed)" != "yes" ]; then
        ab_msgbox "PROMOTE" "Slot B has not been confirmed yet. The health check confirms it shortly after a good start.\n\nWait a moment and try again, or choose CONFIRM in the Slot Manager."
        return 0
    fi

    ab_yesno "Make Slot B the stable system" "Promote" "Cancel" \
        "Copy the running system to Slot A?\n\nSlot B (testing, running): ${b}\nSlot A (stable): ${a} - will be replaced\n\nCopying takes 10-15 minutes. Progress is shown on this screen; do not switch the Pi off.\n\nAfterwards the Pi starts from Slot A, and Slot B is free for the next update." \
        --defaultno || return 0

    clear
    printf 'PROMOTE: copying Slot B (%s) to Slot A.\nDo not switch the Pi off.\n\n' "$b"
    "$BIN_DIR"/rq_slot_manager.sh promote --yes || rc=$?
    if [ "$rc" -ne 0 ]; then
        printf '\nPROMOTE did not finish (see the message above). The Pi keeps starting from Slot B.\n'
        ab_pause
        return 0
    fi
    if ab_yesno "Slot A updated" "Restart now" "Later" \
        "Slot A (stable) now holds ${b}.\n\nRestart now? The Pi then starts from Slot A.\n\nFor the next update: Software & Image Updates -> Slot Manager -> Install an update into Slot B."; then
        clear
        printf 'Restarting into Slot A...\n'
        reboot
        sleep 120
    fi
    return 0
}

# Restart into <slot> on trial (tryboot); refused for a slot without a system
ab_restart_into() {
    local slot="$1" summary="$2" content other rc=0
    other=$(ab_other "$slot")
    if [ "$slot" = "A" ]; then
        content=$(ab_value "$summary" slot_a)
    else
        content=$(ab_value "$summary" slot_b)
    fi
    if ! ab_has_system "$content"; then
        ab_msgbox "Slot $slot cannot be started" "Slot ${slot} holds: $(ab_describe "$content"). The Pi cannot start from it.\n\nStarting a slot without a system leaves the Pi hanging at a black screen until it is switched off and on, so this is not offered.\n\n$(ab_fill_hint "$slot")"
        return 0
    fi
    ab_yesno "Restart into Slot $slot" "Restart" "Cancel" \
        "Restart now into Slot ${slot} ($(ab_slot_label "$slot")): ${content}?\n\nThe Pi starts Slot ${slot} on trial. If it starts properly, the health check makes it the default. If it does not start properly, the Pi goes back to Slot ${other} by itself (at the latest after 15 minutes). If the screen stays black, switch the Pi off and on." \
        || return 0
    clear
    printf 'Restarting into Slot %s...\n\n' "$slot"
    "$BIN_DIR"/rq_slot_manager.sh switch-to "$slot" --reboot || rc=$?
    [ "$rc" -eq 0 ] && sleep 120
    printf '\nThe switch to Slot %s did not happen (see the message above).\n' "$slot"
    ab_pause
    return 0
}

# Rollback: make the other slot the permanent default
ab_rollback() {
    local summary="$1" current other content out rc=0
    current=$(ab_value "$summary" current)
    other=$(ab_other "$current")
    if [ "$other" = "A" ]; then
        content=$(ab_value "$summary" slot_a)
    else
        content=$(ab_value "$summary" slot_b)
    fi
    if ! ab_has_system "$content"; then
        ab_msgbox "Rollback not possible" "Slot ${other} holds: $(ab_describe "$content"). A rollback would make the Pi try to start from it at every start, and it would hang at a black screen.\n\n$(ab_fill_hint "$other")"
        return 0
    fi
    ab_yesno "Go back to Slot $other" "Roll back" "Cancel" \
        "Make Slot ${other} ($(ab_slot_label "$other")): ${content} the default for every start from now on?\n\nRunning now: Slot ${current}.\n\nUse this when the running system has problems. To only try the other slot once, choose 'Restart into Slot ${other}' instead." \
        --defaultno || return 0
    out=$("$BIN_DIR"/rq_slot_manager.sh rollback 2>&1) || rc=$?
    if [ "$rc" -ne 0 ]; then
        ab_msgbox "Rollback" "$(printf '%s\n' "$out" | sed 's/^ERROR: //')"
        return 0
    fi
    if ab_yesno "Rollback" "Restart now" "Later" \
        "Slot ${other} is now the default.\n\nRestart now to start it?"; then
        clear
        printf 'Restarting into Slot %s...\n' "$other"
        reboot
        sleep 120
    fi
    return 0
}

# A/B Boot Slot Manager Menu
do_slot_manager_menu() {
    local summary current other prompt FUN out
    while true; do
        summary=$("$BIN_DIR"/rq_slot_manager.sh summary 2>/dev/null)
        if [ "$(ab_value "$summary" layout)" != "ab" ]; then
            whiptail --title "Not AB Boot Image" --msgbox \
                "This system is not running an A/B boot image.\n\nSlot management is only available for AB boot layouts." \
                10 60
            return 1
        fi
        current=$(ab_value "$summary" current)
        other=$(ab_other "$current")

        prompt="Running: Slot ${current} ($(ab_slot_label "$current"))"
        [ "$(ab_value "$summary" confirmed)" = "yes" ] || prompt="${prompt}, not confirmed yet"
        prompt="${prompt}\nSlot A (stable):  $(ab_describe "$(ab_value "$summary" slot_a)")\nSlot B (testing): $(ab_describe "$(ab_value "$summary" slot_b)")\n\n$(ab_next_step "$summary")"

        FUN=$(ab_menu "RasQberry: A/B Boot Slot Manager" "$prompt" \
            UPDATE    "Install an update into Slot B (testing)" \
            PROMOTE   "Make Slot B the stable system (copy B to A)" \
            "TRYBOOT_${other}" "Restart into Slot ${other} ($(ab_slot_label "$other"))" \
            STATUS    "Show slot details" \
            CONFIRM   "Keep the running slot as the default" \
            ROLLBACK  "Go back to Slot ${other} for good (rollback)") || break

        case "$FUN" in
            UPDATE)    do_ab_install_update ;;
            PROMOTE)   do_ab_promote "$summary" ;;
            TRYBOOT_A) ab_restart_into A "$summary" ;;
            TRYBOOT_B) ab_restart_into B "$summary" ;;
            STATUS)
                out=$("$BIN_DIR"/rq_slot_manager.sh status 2>&1 | sed 's/^INFO: //; s/^WARNING: //')
                ab_msgbox "A/B Boot Status" "$out"
                ;;
            CONFIRM)
                out=$("$BIN_DIR"/rq_slot_manager.sh confirm 2>&1 | sed 's/^INFO: //; s/^WARNING: //')
                ab_msgbox "Confirm Slot" "$out"
                ;;
            ROLLBACK)  ab_rollback "$summary" ;;
            *)         continue ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Touch Mode Menu
# -----------------------------------------------------------------------------

do_touch_mode_menu() {
    # Get current status
    local current_status
    current_status=$("$BIN_DIR/rq_touch_mode.sh" status --quiet 2>/dev/null || echo "disabled")

    while true; do
        FUN=$(show_menu "RasQberry: Touch Mode" "Current: $current_status" \
           ENABLE  "Enable Touch Mode" \
           DISABLE "Disable Touch Mode" \
           STATUS  "Show Current Settings") || break

        case "$FUN" in
            ENABLE)
                # --no-restart: the script must not end the desktop under this
                # menu; offer_desktop_restart asks first (R-032)
                "$BIN_DIR/rq_touch_mode.sh" enable --no-restart >/dev/null
                current_status="enabled"
                offer_desktop_restart
                ;;
            DISABLE)
                "$BIN_DIR/rq_touch_mode.sh" disable --no-restart >/dev/null
                current_status="disabled"
                offer_desktop_restart
                ;;
            STATUS)
                local status_output
                status_output=$("$BIN_DIR/rq_touch_mode.sh" status 2>&1)
                whiptail --title "Touch Mode Status" --msgbox "$status_output" 20 70
                ;;
            *)
                break
                ;;
        esac
    done
}

# Offer to restart the desktop session
# (restarting lightdm logs the desktop user straight back in and leaves SSH
# sessions alone; ending the session left the password screen, R-149)
offer_desktop_restart() {
    systemctl is-active --quiet lightdm 2>/dev/null || return 0
    if whiptail --title "Restart the desktop?" --yesno \
        "Touch mode changes when the desktop restarts.\n\nRestart it now? All windows on the desktop close, this one too if it is on the desktop. SSH stays connected.\n\nOr later: at the next login." \
        13 64; then
        whiptail --title "Restarting..." --infobox "Restarting the desktop..." 6 40
        sleep 2
        systemctl --no-block restart lightdm 2>/dev/null || true
    fi
}

# Chromium opening rasqberry.org at desktop login (#227)
browser_autostart_state() {
    [ "$(sed -n 's/^BROWSER_AUTOSTART=//p' "$ENV_FILE" | tail -1)" = "false" ] \
        && echo "off" || echo "on"
}

do_toggle_browser_autostart() {
    local new=false
    [ "$(browser_autostart_state)" = "off" ] && new=true
    # update_environment_file adds the key when the file does not have it yet
    update_environment_file "BROWSER_AUTOSTART" "$new" || return 0
    whiptail --title "Browser at login" --msgbox \
        "Chromium will $([ "$new" = true ] && echo "open" || echo "no longer open") at the next desktop login." 8 60
    return 0
}

# -----------------------------------------------------------------------------
# IBM Quantum account
# -----------------------------------------------------------------------------
# The account lives in the desktop user's ~/.qiskit for every path - the menu,
# the notebooks and the learner's own code (Jan, Q26). Older versions of this
# menu saved it for root (/root/.qiskit), so "forget" removes that copy too.
_rq_ibm_account_files() {
    printf '%s\n' "$USER_HOME/.qiskit/qiskit-ibm.json"
    [ "$USER_HOME" != /root ] && printf '%s\n' "/root/.qiskit/qiskit-ibm.json"
}

# Echo a short description of the accounts saved in FILE; non-zero if none.
_rq_ibm_account_summary() {
    [ -s "$1" ] || return 1
    _ias=$(jq -r 'to_entries[] | "  \(.key): \(.value.channel // "unknown channel")"
        + (if .value.instance then ", instance set" else "" end)
        + (if .value.is_default_account then " (default)" else "" end)' "$1" 2>/dev/null)
    if [ -z "$_ias" ]; then
        # unreadable, or "{}" (qiskit-ibm-runtime creates that on a lookup)
        [ "$(tr -d ' \n\t' < "$1" 2>/dev/null)" = "{}" ] && return 1
        _ias="  (a saved account file that could not be read)"
    fi
    printf '%s' "$_ias"
}

do_ibm_account_show() {
    _ia_text=""
    for _ia_f in $(_rq_ibm_account_files); do
        if _ia_sum=$(_rq_ibm_account_summary "$_ia_f"); then
            _ia_text="${_ia_text}${_ia_f}:\n${_ia_sum}\n\n"
        fi
    done
    if [ -z "$_ia_text" ]; then
        _ia_text="No IBM Quantum account is saved on this Pi.\n\nEvery demo runs on a simulator without one. For real quantum computers, create your own free account at quantum.cloud.ibm.com, create an API key and save it with \"Save my API key\"."
    else
        _ia_text="${_ia_text}The API key itself is not shown."
    fi
    show_msgbox_fit "IBM Quantum account" "$_ia_text" 74
}

do_ibm_account_forget() {
    _ia_found=""
    for _ia_f in $(_rq_ibm_account_files); do
        [ -e "$_ia_f" ] && _ia_found="${_ia_found} $_ia_f"
    done
    if [ -z "$_ia_found" ]; then
        whiptail --title "IBM Quantum account" --msgbox "No IBM Quantum account is saved on this Pi." 8 60
        return 0
    fi
    whiptail --title "Forget IBM Quantum account" --defaultno --yesno \
        "Delete the IBM Quantum account (API key) saved on this Pi?\n\nUse this before handing the Pi to the next person. Notebooks, Raspberry Tie and your own programs then need an API key again before they can use IBM Quantum computers." \
        13 74 || return 0
    _ia_failed=""
    for _ia_f in $_ia_found; do
        rm -f "$_ia_f" 2>/dev/null || _ia_failed="${_ia_failed} $_ia_f"
    done
    if [ -n "$_ia_failed" ]; then
        whiptail --title "IBM Quantum account" --msgbox "Could not delete:${_ia_failed}" 9 74
        return 1
    fi
    whiptail --title "IBM Quantum account" --msgbox "The saved IBM Quantum account was deleted." 8 60
}

# Save or check the account as the desktop user, with the venv's Qiskit
# (rq_set_qiskit_ibm_token.py): the key is checked with IBM Quantum before it
# is saved, and it goes to the user's ~/.qiskit (Jan, Q26/Q31).
_rq_ibm_token_tool() {
    _it_py="$REPO_DIR/venv/$STD_VENV/bin/python3"
    [ -x "$_it_py" ] || _it_py=python3
    clear
    _rq_as_desktop_user "$_it_py" "$BIN_DIR/rq_set_qiskit_ibm_token.py" "$@"
    _it_rc=$?
    printf '\nPress Enter to return to the menu.'
    read -r _it_x || :
    return $_it_rc
}

do_ibm_account_menu() {
    while true; do
        FUN=$(show_menu "RasQberry: IBM Quantum account" \
            "Every demo runs on a simulator without an account. For real IBM Quantum computers, each student uses their own free account (quantum.cloud.ibm.com)." \
            SAVE   "Save my API key (checked first)" \
            CHECK  "Check the saved account" \
            SHOW   "Show the saved account" \
            FORGET "Forget the saved account") || break
        case "$FUN" in
            SAVE)   _rq_ibm_token_tool || continue ;;
            CHECK)  _rq_ibm_token_tool --check || continue ;;
            SHOW)   do_ibm_account_show ;;
            FORGET) do_ibm_account_forget || continue ;;
            *)      break ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Remote Access & Security (R-013, R-014, R-063): the password, SSH, VNC and
# this Pi's name in one place. Every card starts with the published password,
# and SSH and VNC accept it. VNC is switched on once at the first start (Q17);
# switched off here it stays off. The work is done by rq_remote_access.sh.
# -----------------------------------------------------------------------------
_rq_remote() { "$BIN_DIR/rq_remote_access.sh" "$@"; }

# One field of `rq_remote_access.sh status` (ssh=on vnc=off name=... mdns=...)
_rq_remote_field() {
    printf '%s\n' "$1" | tr ' ' '\n' | sed -n "s/^$2=//p" | head -n 1
}

do_change_password() {
    _cp_user="${SUDO_USER:-$USER}"
    clear
    echo "New password for $_cp_user: type it twice. Nothing is shown while you type."
    echo
    if passwd "$_cp_user"; then
        whiptail --title "Password" --msgbox \
            "Password changed. Use the new one for SSH, VNC and the login screen." 8 72
    else
        whiptail --title "Password" --msgbox "The password was not changed." 8 50
    fi
    return 0
}

# Switch SSH or VNC on or off. $1 = ssh|vnc, $2 = its state now (on|off)
do_toggle_remote() {
    _tr_what="$1"; _tr_now="$2"
    if [ "$_tr_what" = ssh ]; then
        _tr_name="SSH"
        _tr_off="Nobody can log in from another computer with SSH then."
        [ -n "${SSH_CONNECTION:-}" ] && _tr_off="$_tr_off\n\nYou are connected over SSH: this session stays open, but the next SSH login fails. Switching SSH on again then needs a screen and keyboard."
        _tr_on="Anyone on this network who knows the password can then log in."
    else
        _tr_name="VNC"
        _tr_off="Nobody can see or use the desktop from another computer then. It stays off, also after a restart."
        _tr_on="Anyone on this network who knows the password can then see and use the desktop."
    fi
    if [ "$_tr_now" = on ]; then
        whiptail --title "$_tr_name" --yes-button "Switch off" --no-button "Cancel" \
            --yesno "Switch $_tr_name off?\n\n$_tr_off" 13 72 || return 0
        _tr_new=off
    else
        whiptail --title "$_tr_name" --yes-button "Switch on" --no-button "Cancel" \
            --yesno "Switch $_tr_name on?\n\n$_tr_on" 11 72 || return 0
        _tr_new=on
    fi
    if _tr_out=$(_rq_remote "$_tr_what" "$_tr_new" 2>&1); then
        whiptail --title "$_tr_name" --msgbox "$(printf '%s\n' "$_tr_out" | tail -n 1)" 8 50
    else
        show_msgbox_fit "$_tr_name" "Could not switch $_tr_name $_tr_new:\n\n$_tr_out" 72
    fi
    return 0
}

# $1 = the name now
do_name_this_rasqberry() {
    _nr_old="$1"
    _nr_new=$(whiptail --title "Name this RasQberry" --inputbox \
"With several RasQberry Two kits on one network, give each its own name, e.g. rasqberry-01. Other computers then reach it as <name>.local.

Lowercase letters, digits and hyphens." 13 72 "$_nr_old" 3>&1 1>&2 2>&3) || return 0
    _nr_new=$(printf '%s' "$_nr_new" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
    [ -n "$_nr_new" ] && [ "$_nr_new" != "$_nr_old" ] || return 0
    if ! _rq_remote check-name "$_nr_new"; then
        whiptail --title "Name this RasQberry" --msgbox \
            "'$_nr_new' cannot be used. Use lowercase letters, digits and hyphens (up to 63), not starting or ending with a hyphen." 9 72
        return 0
    fi
    if _nr_out=$(_rq_remote name "$_nr_new" 2>&1); then
        whiptail --title "Name this RasQberry" --msgbox \
            "$(printf '%s\n' "$_nr_out" | tail -n 1)\n\nPrograms that are already open keep the old name until the next restart." 10 72
    else
        show_msgbox_fit "Name this RasQberry" "The name was not changed:\n\n$_nr_out" 72
    fi
    return 0
}

do_remote_access_menu() {
    _ra_last=""
    while true; do
        _ra_status=$(_rq_remote status 2>/dev/null) || _ra_status=""
        _ra_ssh=$(_rq_remote_field "$_ra_status" ssh)
        _ra_vnc=$(_rq_remote_field "$_ra_status" vnc)
        _ra_name=$(_rq_remote_field "$_ra_status" name)
        _ra_mdns=$(_rq_remote_field "$_ra_status" mdns)
        FUN=$(show_menu ${_ra_last:+--default-item "$_ra_last"} "RasQberry: Remote Access & Security" \
            "Anyone on the same network who knows the password can log in over SSH and VNC." \
            PASS "Change the password" \
            SSH  "SSH (log in from another computer): ${_ra_ssh:-unknown}" \
            VNC  "VNC (the desktop on another computer): ${_ra_vnc:-unknown}" \
            NAME "Name: ${_ra_name:-unknown}${_ra_mdns:+ (network: $_ra_mdns)}") || break
        _ra_last="$FUN"
        case "$FUN" in
            PASS) do_change_password ;;
            SSH)  do_toggle_remote ssh "$_ra_ssh" ;;
            VNC)  do_toggle_remote vnc "$_ra_vnc" ;;
            NAME) do_name_this_rasqberry "$_ra_name" ;;
            *)    break ;;
        esac
    done
    return 0
}

# -----------------------------------------------------------------------------
# The setup checklist (rq_firstlogin.sh). It opens by itself only once, at the
# first desktop login (Jan, Q12); from then on here and under the RasQberry
# Setup icon. It runs as the desktop user: its notes and the steps it starts
# (they use sudo where they need root) are theirs.
# -----------------------------------------------------------------------------
do_setup_checklist() {
  if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
    sudo -u "$SUDO_USER" -H "$BIN_DIR/rq_firstlogin.sh" --all
  else
    "$BIN_DIR/rq_firstlogin.sh" --all
  fi
  _rq_load_env 2>/dev/null || true
  return 0
}

# -----------------------------------------------------------------------------
# Shut down safely (R-043). The LEDs go off first (rasqberry-led-clear.service
# also clears them at every shutdown), and the text says when the power may be
# switched off - the kit's only switch is the inline power switch.
# -----------------------------------------------------------------------------
do_shutdown_safely() {
  whiptail --title "Shut Down" --yes-button "Shut Down" --no-button "Cancel" --yesno \
    "Shut the Raspberry Pi down now?\n\nThe LEDs go off first. Wait about 10 seconds, until the green light on the Pi stays off, then switch the power off." \
    11 66 || return 0
  "$BIN_DIR/rq_clear_leds.sh" --stop >/dev/null 2>&1 || true
  sync
  systemctl poweroff
}

# -----------------------------------------------------------------------------
# Advanced: expert tools, kept out of the everyday menus (Jan, Q35)
# -----------------------------------------------------------------------------
do_rasqberry_advanced_menu() {
    _adv_last=""
    while true; do
        FUN=$(show_menu ${_adv_last:+--default-item "$_adv_last"} "RasQberry: Advanced" \
            "Tools for experts. Changes here can stop demos from working." \
            UEF    "Edit a RasQberry Two setting (settings file)" \
            REFR   "Refresh the demo list" \
            BRANCH "Update from a GitHub branch") || break
        _adv_last="$FUN"
        case "$FUN" in
            UEF)    do_select_environment_variable || { handle_error "Failed to update the settings file."; continue; } ;;
            REFR)   refresh_demo_menu_cache        || continue ;;
            BRANCH) do_update_from_branch          || continue ;;
            *)      break ;;
        esac
    done
}

do_rasqberry_menu() {
  # Ctrl+C is how most demos are stopped. raspi-config is a /bin/sh script, and
  # dash exits on SIGINT while it waits for a foreground child, so stopping a
  # demo that way also quit raspi-config (R-027). A no-op trap keeps raspi-config
  # alive while the demo still gets the signal (`trap '' INT` would be inherited
  # as "ignore" and make demos unstoppable). raspi-config sets no INT trap of
  # its own; restore the default when leaving.
  trap ':' INT
  _main_last=""
  while true; do
    # Software & Image Updates is on every image: checking for a newer image
    # works on the standard image too; the A/B-only entries inside are hidden
    # there.
    set -- QD "Quantum Demos" SETUP "Setup Checklist" TOUCH "Touch Mode Settings" \
        BROWSER "Browser at login: $(browser_autostart_state)" \
        IBMQ "IBM Quantum account" REMOTE "Remote Access & Security" \
        AB_BOOT "Software & Image Updates" INFO "System Info" \
        ADV "Advanced" OFF "Shut Down Safely"
    FUN=$(show_menu ${_main_last:+--default-item "$_main_last"} "RasQberry: Main Menu" "System Options" "$@") || break
    _main_last="$FUN"
    case "$FUN" in
      QD)      do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      SETUP)   do_setup_checklist             || continue ;;
      OFF)     do_shutdown_safely             || continue ;;
      TOUCH)   do_touch_mode_menu             || continue ;;
      BROWSER) do_toggle_browser_autostart    || continue ;;
      IBMQ)    do_ibm_account_menu            || continue ;;
      REMOTE)  do_remote_access_menu          || continue ;;
      AB_BOOT) do_ab_boot_menu                || continue ;;
      INFO)    do_show_system_info            || { handle_error "Failed to show system info."; continue; } ;;
      ADV)     do_rasqberry_advanced_menu     || continue ;;
      *)       handle_error "Programmer error: unrecognized main menu option ${FUN}."; continue ;;
    esac
  done
  trap - INT
}

# -----------------------------------------------------------------------------
# 4. Error Handling
# -----------------------------------------------------------------------------

# Function for graceful error handling in menus
handle_error() {
    _he_msg="$1"
    # Every caller passes a generic sentence ("Could not run X"), which told the
    # user nothing about the actual cause - the traceback, the "GPIO busy", the
    # "requires a display". run_demo and run_engine_demo leave that here when a
    # demo fails, so show it with the message rather than instead of it.
    if [ -n "${RQ_LAST_DEMO_ERROR:-}" ]; then
        show_msgbox_fit "Error" "$_he_msg

$RQ_LAST_DEMO_ERROR

(For a bug report: rq_info.sh --report)" 76
        RQ_LAST_DEMO_ERROR=""
        return 1
    fi
    show_msgbox_fit "Error" "$_he_msg" 64
    return 1
}
