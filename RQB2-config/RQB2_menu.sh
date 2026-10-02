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
# This keeps the parts that belong to the menu (consent before a download,
# success/error dialogs) and hands the actual acquisition - pin, patch, pip,
# post-install, installed flag - to the engine.
install_via_engine() {
    DEMO_ID="$1"    # manifest id, e.g. grok-bloch
    TITLE="$2"      # title for dialog messages

    RUNNER="$BIN_DIR/rq_demo_run.sh"
    if [ ! -x "$RUNNER" ]; then
        echo "ERROR: demo engine not found at $RUNNER"
        return 1
    fi

    # Everything below writes to stderr, never stdout. "Download all demos" pipes
    # this into `whiptail --gauge`, which parses its stdin as the gauge protocol -
    # a stray line there garbles the progress bar. It silences stderr per demo
    # (do_*_install 2>/dev/null), so stderr is the channel that stays out of the
    # way while remaining visible for a single interactive install.

    # Already installed? Ask the engine rather than second-guessing it here.
    if "$RUNNER" "$DEMO_ID" --is-installed 2>/dev/null; then
        return 0
    fi

    # Confirm before using the network (unless a caller enabled auto-install)
    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
        if command -v whiptail > /dev/null 2>&1; then
            whiptail --title "$TITLE Not Installed" \
                     --yesno "$TITLE is not installed yet.\n\nRequires internet connection.\n\nInstall now?" \
                     10 65 3>&1 1>&2 2>&3
            if [ $? -ne 0 ]; then
                return 1
            fi
        else
            # Fallback if whiptail not available (POSIX-compliant for dash)
            echo "$TITLE is not installed." >&2
            echo "This requires downloading from GitHub." >&2
            printf "Install now? (y/n) " >&2
            read REPLY
            case "$REPLY" in
                [Yy]|[Yy][Ee][Ss]) ;;
                *) return 1 ;;
            esac
        fi
    else
        echo "Auto-installing $TITLE..." >&2
    fi

    if "$RUNNER" "$DEMO_ID" --install-only >&2; then
        if [ "${RQ_AUTO_INSTALL:-0}" != "1" ] && [ "$RQ_NO_MESSAGES" = false ]; then
            whiptail --title "$TITLE" --msgbox "Demo installed successfully." 8 60
        else
            echo "✓ $TITLE installed successfully" >&2
        fi
        return 0
    fi

    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
        whiptail --title "Installation Error" --msgbox "Failed to install $TITLE.\n\nPossible causes:\n- No internet connection\n- Repository unavailable\n- Network firewall blocking access\n\nPlease check your connection and try again." 12 70
    else
        echo "ERROR: Failed to install $TITLE demo" >&2
    fi
    return 1
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
run_quantum_paradoxes_demo() {
    # Ensure installation
    do_quantum_paradoxes_install || return 1

    # Launch the demo using the dedicated launcher script
    "$BIN_DIR/rq_quantum_paradoxes.sh"
}

# Clone IBM Quantum Learning content (shared by tutorials and courses)
# Content licensed under CC BY-SA 4.0 by IBM/Qiskit
# Source: https://github.com/Qiskit/documentation
clone_ibm_learning_content() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    if [ -d "$DEST/.git" ]; then
        return 0  # Already cloned
    fi

    # Show confirmation dialog before downloading (unless auto-install is enabled)
    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ]; then
        if command -v whiptail > /dev/null 2>&1; then
            whiptail --title "IBM Quantum Learning Content" \
                     --yesno "IBM Quantum Tutorials & Courses are not installed yet.\n\nThis will download content from:\nhttps://github.com/Qiskit/documentation\n\nContent is licensed under CC BY-SA 4.0.\nRequires internet connection.\n\nInstall now?" \
                     14 70 3>&1 1>&2 2>&3

            if [ $? -ne 0 ]; then
                return 1
            fi
        fi
    else
        echo "Auto-installing IBM Quantum Learning content..."
    fi

    echo "Cloning IBM Quantum Learning content (sparse checkout)..."
    echo "This may take a few minutes..."

    # Sparse clone - only tutorials and courses directories
    mkdir -p "$DEST"
    cd "$DEST"
    git init
    git remote add origin "$GIT_REPO_DEMO_IBM_LEARNING"
    git sparse-checkout init --cone
    git sparse-checkout set docs/tutorials docs/guides/hello-world.ipynb learning/courses LICENSE LICENSE-DOCS
    # Pin to a reviewed commit instead of tracking main. Qiskit/documentation is a
    # third-party repo (we do not own it) that changes constantly, so following
    # main makes installs irreproducible and lets an upstream change alter the
    # shipped content underneath us. Bump GIT_REF_DEMO_IBM_LEARNING deliberately.
    if [ -n "${GIT_REF_DEMO_IBM_LEARNING:-}" ]; then
        git fetch --depth=1 origin "$GIT_REF_DEMO_IBM_LEARNING" || return 1
        git checkout -q FETCH_HEAD || return 1
    else
        echo "WARNING: GIT_REF_DEMO_IBM_LEARNING unset - falling back to main (unpinned)"
        git pull --depth=1 origin main
    fi
    cd - > /dev/null

    # Copy credentials setup notebook
    if [ -f "/usr/config/00-Save-Credentials.ipynb" ]; then
        cp "/usr/config/00-Save-Credentials.ipynb" "$DEST/"
        echo "Added credentials setup notebook."
    fi

    # Fix ownership if needed
    if [ "$(stat -c '%U' "$DEST")" = "root" ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        chown -R "$SUDO_USER":"$SUDO_USER" "$DEST"
    fi

    echo "IBM Quantum Learning content downloaded successfully."
}

# Install IBM Quantum Tutorials
do_ibm_tutorials_install() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    if [ -f "$DEST/$MARKER_IBM_TUTORIALS" ]; then
        return 0
    fi

    # Clone content if needed
    clone_ibm_learning_content || return 1

    # Generate WELCOME-tutorials.ipynb
    echo "Generating tutorials welcome notebook..."
    . "$VENV_ACTIVATE"
    python3 "$BIN_DIR/setup_ibm_tutorials.py" --tutorials --path "$DEST"

    update_environment_file "IBM_TUTORIALS_INSTALLED" "true"

    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ] && [ "$RQ_NO_MESSAGES" = false ]; then
        whiptail --title "IBM Quantum Tutorials" --msgbox "Tutorials installed successfully." 8 60
    else
        echo "IBM Quantum Tutorials installed successfully."
    fi
}

# Install IBM Quantum Courses
do_ibm_courses_install() {
    DEST="$DEMO_ROOT/ibm-quantum-learning"

    if [ -f "$DEST/$MARKER_IBM_COURSES" ]; then
        return 0
    fi

    # Clone content if needed
    clone_ibm_learning_content || return 1

    # Generate WELCOME-courses.ipynb
    echo "Generating courses welcome notebook..."
    . "$VENV_ACTIVATE"
    python3 "$BIN_DIR/setup_ibm_tutorials.py" --courses --path "$DEST"

    update_environment_file "IBM_COURSES_INSTALLED" "true"

    if [ "${RQ_AUTO_INSTALL:-0}" != "1" ] && [ "$RQ_NO_MESSAGES" = false ]; then
        whiptail --title "IBM Quantum Courses" --msgbox "Courses installed successfully." 8 60
    else
        echo "IBM Quantum Courses installed successfully."
    fi
}

# Run IBM Quantum Tutorials demo
run_ibm_tutorials_demo() {
    do_ibm_tutorials_install || return 1
    "$BIN_DIR/rq_ibm_tutorials.sh"
}

# Run IBM Quantum Courses demo
run_ibm_courses_demo() {
    do_ibm_courses_install || return 1
    "$BIN_DIR/rq_ibm_courses.sh"
}

# LED-Painter installation is handled by rq_led_painter.sh
# (uses conversion script instead of patch file)

# -----------------------------------------------------------------------------
# Download All Demos - Batch install all available demos
# -----------------------------------------------------------------------------

# Check network connectivity
check_network_connectivity() {
    # Try to reach GitHub (most reliable for our use case)
    if curl -s --connect-timeout 5 https://github.com > /dev/null 2>&1; then
        return 0
    fi
    # Fallback: try ping to Google DNS
    if ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Check available disk space in MB
check_disk_space_mb() {
    df -m "$USER_HOME" 2>/dev/null | awk 'NR==2 {print $4}'
}

# Install Qoffee-Maker for batch install (setup + pull image)
do_qoffee_install() {
    if [ "$QOFFEE_MAKER_INSTALLED" = "true" ]; then
        return 0  # Already installed
    fi

    # Check if Docker is available
    if ! command -v docker > /dev/null 2>&1; then
        echo "Skipping Qoffee-Maker: Docker not installed"
        return 1
    fi

    echo "Setting up Qoffee-Maker (Docker)..."
    if ! "$BIN_DIR/qoffee-setup.sh"; then
        echo "ERROR: Qoffee-Maker setup failed"
        return 1
    fi

    # Pull Docker image with retry logic (large images can fail on slow connections)
    echo "Pulling Qoffee-Maker Docker image..."
    QOFFEE_IMAGE="ghcr.io/janlahmann/qoffee-maker"
    MAX_RETRIES=3
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Pull attempt $RETRY_COUNT of $MAX_RETRIES..."
        if docker pull "$QOFFEE_IMAGE"; then
            update_environment_file "QOFFEE_MAKER_INSTALLED" "true"
            echo "✓ Qoffee-Maker setup complete"
            return 0
        else
            echo "Pull attempt $RETRY_COUNT failed"
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Waiting 10 seconds before retry..."
                sleep 10
                # Clean up any partial/corrupted layers
                docker system prune -f >/dev/null 2>&1 || true
            fi
        fi
    done
    echo "ERROR: Failed to pull Qoffee-Maker image after $MAX_RETRIES attempts"
    return 1
}

# Install Quantum-Mixer for batch install (setup + build image)
do_quantum_mixer_install() {
    if [ "$QUANTUM_MIXER_INSTALLED" = "true" ]; then
        return 0  # Already installed
    fi

    # Check if Docker is available
    if ! command -v docker > /dev/null 2>&1; then
        echo "Skipping Quantum-Mixer: Docker not installed"
        return 1
    fi

    echo "Setting up Quantum-Mixer (Docker)..."
    if ! "$BIN_DIR/qoffee-setup.sh"; then
        echo "ERROR: Quantum-Mixer setup failed"
        return 1
    fi

    # Build Docker image for ARM64
    MIXER_DIR="$DEMO_ROOT/quantum-mixer"
    MIXER_IMAGE="quantum-mixer:arm64"

    # Clone quantum-mixer repo if not present
    if [ ! -d "$MIXER_DIR" ]; then
        echo "Cloning Quantum-Mixer repository..."
        git clone --depth 1 "$GIT_REPO_DEMO_QUANTUM_MIXER" "$MIXER_DIR" || {
            echo "ERROR: Failed to clone Quantum-Mixer"
            return 1
        }
    fi

    echo "Building Quantum-Mixer Docker image (this may take 10-15 minutes)..."
    cd "$MIXER_DIR" || return 1
    MAX_RETRIES=3
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Build attempt $RETRY_COUNT of $MAX_RETRIES..."
        # Use --no-cache on retries to avoid corrupted cached layers
        if [ $RETRY_COUNT -eq 1 ]; then
            BUILD_OPTS=""
        else
            BUILD_OPTS="--no-cache"
        fi
        if docker build $BUILD_OPTS -f Dockerfile.arm64 -t "$MIXER_IMAGE" .; then
            cd - > /dev/null
            update_environment_file "QUANTUM_MIXER_INSTALLED" "true"
            echo "✓ Quantum-Mixer setup complete"
            return 0
        else
            echo "Build attempt $RETRY_COUNT failed"
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "Waiting 10 seconds before retry..."
                sleep 10
                # Clean up any partial/corrupted layers
                docker system prune -f >/dev/null 2>&1 || true
            fi
        fi
    done
    cd - > /dev/null 2>/dev/null
    echo "ERROR: Failed to build Quantum-Mixer image after $MAX_RETRIES attempts"
    return 1
}

# Download all demos at once
do_download_all_demos() {
    # Pre-flight check: Network connectivity
    if ! check_network_connectivity; then
        whiptail --title "Network Error" --msgbox \
            "No internet connection detected.\n\nPlease connect to the internet and try again." \
            10 60
        return 1
    fi

    # Pre-flight check: Disk space (require at least 500MB free)
    AVAILABLE_MB=$(check_disk_space_mb)
    if [ "${AVAILABLE_MB:-0}" -lt 500 ]; then
        whiptail --title "Low Disk Space" --msgbox \
            "Insufficient disk space.\n\nAvailable: ${AVAILABLE_MB:-0} MB\nRequired: ~500 MB minimum\n\nPlease free up some space and try again." \
            12 60
        return 1
    fi

    # Count demos: already installed vs to-install
    TO_INSTALL=0
    ALREADY_INSTALLED=0

    # Git-clone demos (7 total, excluding LED-Painter)
    [ "$QUANTUM_LIGHTS_OUT_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$QUANTUM_RASPBERRY_TIE_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$GROK_BLOCH_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$FUN_WITH_QUANTUM_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$QUANTUM_PARADOXES_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$IBM_TUTORIALS_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    [ "$IBM_COURSES_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))

    # Docker demos (2 total)
    DOCKER_AVAILABLE="no"
    if command -v docker > /dev/null 2>&1; then
        DOCKER_AVAILABLE="yes"
        [ "$QOFFEE_MAKER_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
        [ "$QUANTUM_MIXER_INSTALLED" = "true" ] && ALREADY_INSTALLED=$((ALREADY_INSTALLED + 1)) || TO_INSTALL=$((TO_INSTALL + 1))
    fi

    TOTAL_DEMOS=$((ALREADY_INSTALLED + TO_INSTALL))

    # If all already installed, inform and exit
    if [ "$TO_INSTALL" -eq 0 ]; then
        whiptail --title "All Demos Installed" --msgbox \
            "All $TOTAL_DEMOS demos are already installed!\n\nNothing to do." \
            10 50
        return 0
    fi

    # Build confirmation message
    CONFIRM_MSG="This will download and install quantum demos.\n\n"
    CONFIRM_MSG="${CONFIRM_MSG}Demos to install: $TO_INSTALL\n"
    CONFIRM_MSG="${CONFIRM_MSG}Already installed: $ALREADY_INSTALLED\n"
    CONFIRM_MSG="${CONFIRM_MSG}Available disk space: ${AVAILABLE_MB} MB\n\n"
    if [ "$DOCKER_AVAILABLE" = "yes" ]; then
        CONFIRM_MSG="${CONFIRM_MSG}Docker demos included (may take 10-15 min to build).\n\n"
    else
        CONFIRM_MSG="${CONFIRM_MSG}Docker demos skipped (Docker not installed).\n\n"
    fi
    CONFIRM_MSG="${CONFIRM_MSG}Proceed with installation?"

    # Show confirmation dialog
    if ! whiptail --title "Download All Demos" --yesno "$CONFIRM_MSG" 18 65; then
        return 0
    fi

    # Enable auto-install mode to skip individual confirmations
    export RQ_AUTO_INSTALL=1
    export RQ_NO_MESSAGES=true

    # Create temp file for tracking results from subshell
    RESULTS_FILE=$(mktemp)

    # Process git-clone demos with progress display (7 demos)
    {
        # Initialize counters inside subshell
        INSTALLED_COUNT=0
        SKIPPED_COUNT=0
        FAILED_COUNT=0
        FAILED_DEMOS=""
        CURRENT=0
        TOTAL=7

        # 1. Quantum Lights Out
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$QUANTUM_LIGHTS_OUT_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping Quantum Lights Out (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing Quantum Lights Out..."; echo "XXX"
            if do_qlo_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Quantum Lights Out\n"
            fi
        fi

        # 2. Quantum Raspberry-Tie
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$QUANTUM_RASPBERRY_TIE_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping Quantum Raspberry-Tie (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing Quantum Raspberry-Tie..."; echo "XXX"
            if do_rasp_tie_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Quantum Raspberry-Tie\n"
            fi
        fi

        # 3. Grok Bloch
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$GROK_BLOCH_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping Grok Bloch (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing Grok Bloch..."; echo "XXX"
            if do_grok_bloch_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Grok Bloch\n"
            fi
        fi

        # 4. Fun with Quantum
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$FUN_WITH_QUANTUM_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping Fun with Quantum (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing Fun with Quantum..."; echo "XXX"
            if do_fwq_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Fun with Quantum\n"
            fi
        fi

        # 5. Quantum Paradoxes
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$QUANTUM_PARADOXES_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping Quantum Paradoxes (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing Quantum Paradoxes..."; echo "XXX"
            if do_quantum_paradoxes_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Quantum Paradoxes\n"
            fi
        fi

        # 6. IBM Quantum Tutorials
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$IBM_TUTORIALS_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping IBM Quantum Tutorials (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing IBM Quantum Tutorials..."; echo "XXX"
            if do_ibm_tutorials_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}IBM Quantum Tutorials\n"
            fi
        fi

        # 7. IBM Quantum Courses
        CURRENT=$((CURRENT + 1))
        PERCENT=$((CURRENT * 100 / TOTAL))
        if [ "$IBM_COURSES_INSTALLED" = "true" ]; then
            echo "XXX"; echo "$PERCENT"; echo "Skipping IBM Quantum Courses (already installed)..."; echo "XXX"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            echo "XXX"; echo "$PERCENT"; echo "Installing IBM Quantum Courses..."; echo "XXX"
            if do_ibm_courses_install 2>/dev/null; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}IBM Quantum Courses\n"
            fi
        fi

        # Write results to temp file
        echo "${INSTALLED_COUNT}:${SKIPPED_COUNT}:${FAILED_COUNT}:${FAILED_DEMOS}" > "$RESULTS_FILE"
        echo "100"
    } | whiptail --title "Downloading Demos" --gauge "Preparing..." 8 70 0

    # Read results from temp file
    INSTALLED_COUNT=0
    SKIPPED_COUNT=0
    FAILED_COUNT=0
    FAILED_DEMOS=""
    if [ -f "$RESULTS_FILE" ]; then
        IFS=: read -r INSTALLED_COUNT SKIPPED_COUNT FAILED_COUNT FAILED_DEMOS < "$RESULTS_FILE"
        rm -f "$RESULTS_FILE"
    fi

    # --- Docker demos (run OUTSIDE gauge to allow their own dialogs) ---
    if [ "$DOCKER_AVAILABLE" = "yes" ]; then
        # Qoffee-Maker
        if [ "$QOFFEE_MAKER_INSTALLED" = "true" ]; then
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            whiptail --title "Docker Demos" --infobox "Setting up Qoffee-Maker...\n\nThis may take several minutes." 8 50
            if do_qoffee_install; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Qoffee-Maker\n"
            fi
        fi

        # Quantum-Mixer
        if [ "$QUANTUM_MIXER_INSTALLED" = "true" ]; then
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        else
            whiptail --title "Docker Demos" --infobox "Setting up Quantum-Mixer...\n\nThis may take several minutes." 8 50
            if do_quantum_mixer_install; then
                INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
            else
                FAILED_COUNT=$((FAILED_COUNT + 1))
                FAILED_DEMOS="${FAILED_DEMOS}Quantum-Mixer\n"
            fi
        fi
    fi

    # Restore normal mode
    unset RQ_AUTO_INSTALL
    export RQ_NO_MESSAGES=false

    # Build summary message
    SUMMARY="Installation Complete!\n\n"
    SUMMARY="${SUMMARY}Installed: ${INSTALLED_COUNT:-0}\n"
    SUMMARY="${SUMMARY}Skipped (already installed): ${SKIPPED_COUNT:-0}\n"
    SUMMARY="${SUMMARY}Failed: ${FAILED_COUNT:-0}"

    if [ "${FAILED_COUNT:-0}" -gt 0 ] && [ -n "$FAILED_DEMOS" ]; then
        SUMMARY="${SUMMARY}\n\nFailed demos:\n${FAILED_DEMOS}"
        SUMMARY="${SUMMARY}\nYou can try installing failed demos individually."
    fi

    whiptail --title "Download All Demos - Summary" --msgbox "$SUMMARY" 16 60

    return 0
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
stop_last_demo() {
  if [ -z "${LAST_DEMO_PGID:-}" ]; then
    whiptail --title "Stop demo" --msgbox "No demo has been started in this session." 8 60
    return 0
  fi
  # Negative PID targets the whole process group (setsid session leader).
  kill -TERM -"$LAST_DEMO_PGID" 2>/dev/null
  sleep 1
  kill -KILL -"$LAST_DEMO_PGID" 2>/dev/null || true
  do_led_off 2>/dev/null || true
  whiptail --title "Stop demo" --msgbox "Stopped the last running demo and cleared the LEDs." 8 65
  LAST_DEMO_PGID=""
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
            _ex="The SD card is full. Free some space, then try again." ;;
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
    _rq_pause "The demo stopped with an error (see above). Press Enter to continue."
    return 1
}

# Generic runner for Quantum-Lights-Out demo (POSIX sh compatible)
run_qlo_demo() {
    MODE="${1:-}"  # empty for GUI, "console" for console mode
    DEMO_DIR="$DEMO_ROOT/Quantum-Lights-Out"
    # Ensure installed (install_via_engine shows its own dialog on failure)
    do_qlo_install || return 0
    # Launch appropriate mode.
    #
    # The console variant IS played in the terminal, so it runs in the
    # foreground. The default variant plays on the LEDs and its stdout is just
    # noise - the solver's progress and Qiskit's deprecation warnings - so it
    # goes to the log under the stop dialog.
    if [ "$MODE" = "console" ]; then
        run_demo "Quantum Lights Out Demo (console)" "$DEMO_DIR" python3 lights_out.py --console
    else
        run_demo bg "Quantum Lights Out Demo" "$DEMO_DIR" python3 lights_out.py
    fi
    _qlo_rc=$?
    # Turn off LEDs when demo ends (the demo's status is what the caller needs)
    do_led_off
    return $_qlo_rc
}

# Run grok-bloch demo local version (ensures install first)
run_grok_bloch_demo() {
    # Ensure installation
    do_grok_bloch_install || return 1

    # Launch the demo using the dedicated launcher script
    # (Script will check for DISPLAY and show appropriate error if needed)
    "$BIN_DIR/rq_grok_bloch.sh"
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
    run_demo bg "RasQ-LED Demo" "$BIN_DIR" python3 RasQ-LED.py
    # Turn off LEDs when demo ends
    do_led_off
}

# Run Qoffee-Maker demo
run_qoffee_demo() {
    # Check if setup has been run (Docker installed)
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Setup Required" --msgbox \
            "Qoffee-Maker requires Docker, which is not installed.\n\nSetup will now run to install Docker and configure Qoffee-Maker.\n\nNote: This requires internet connection and may take 5-10 minutes." \
            12 70
        "$BIN_DIR/qoffee-setup.sh" || return 1
    fi

    # Launch the Qoffee-Maker demo
    "$BIN_DIR/qoffee-maker.sh"
}

# Stop Qoffee-Maker containers
stop_qoffee_containers() {
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Docker Not Found" --msgbox "Docker is not installed. No containers to stop." 8 60
        return 0
    fi

    # Check if any qoffee containers are running
    if docker ps -q --filter name=qoffee 2>/dev/null | grep -q .; then
        echo "Stopping Qoffee-Maker containers..."
        docker stop $(docker ps -q --filter name=qoffee) 2>/dev/null || true
        whiptail --title "Qoffee-Maker Stopped" --msgbox "All Qoffee-Maker containers have been stopped." 8 60
    else
        whiptail --title "No Containers" --msgbox "No running Qoffee-Maker containers found." 8 60
    fi
}

# Run Quantum-Mixer demo
run_quantum_mixer_demo() {
    # Ask before installing, like every other demo.
    #
    # This used to drop straight into quantum-mixer.sh, which cloned and then
    # ran a Docker build FROM SOURCE with no prompt and no dialog - raw build
    # output over the TUI for several minutes. On a 10GB A/B slot that build ran
    # the disk to 100% and left the system unusable (finding F28), so of all the
    # demos this is the one that should ask first. install_via_engine gives it
    # the same consent prompt and error dialog as the rest.
    install_via_engine "quantum-mixer" "Quantum-Mixer" || return 1

    # Launch the Quantum-Mixer demo
    "$BIN_DIR/quantum-mixer.sh"
}

# Stop Quantum-Mixer containers
stop_quantum_mixer_containers() {
    if ! command -v docker > /dev/null 2>&1; then
        whiptail --title "Docker Not Found" --msgbox "Docker is not installed. No containers to stop." 8 60
        return 0
    fi

    # Check if any quantum-mixer containers are running
    if docker ps -q --filter name=quantum-mixer 2>/dev/null | grep -q .; then
        echo "Stopping Quantum-Mixer containers..."
        docker stop $(docker ps -q --filter name=quantum-mixer) 2>/dev/null || true
        whiptail --title "Quantum-Mixer Stopped" --msgbox "All Quantum-Mixer containers have been stopped." 8 60
    else
        whiptail --title "No Containers" --msgbox "No running Quantum-Mixer containers found." 8 60
    fi
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
        "$BIN_DIR/rq_demo_add_external.sh"
        # The add script regenerates the cache; reload it in this session
        _rq_load_demo_cache || :
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
    printf ' INTERACTIVE ASK_TO_REBOOT CONFIG '
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
do_led_off() {
  (
    [ -f "$VENV_ACTIVATE" ] && . "$VENV_ACTIVATE"
    python3 "$BIN_DIR/turn_off_LEDs.py"
  )
}

# -----------------------------------------------------------------------------
# 3c) LED Display Menu (Text & Logo Display)
# -----------------------------------------------------------------------------

do_led_custom_text() {
    run_demo "LED Text Display" "$BIN_DIR" bash rq_led_display_text.sh
}

do_led_choose_logo() {
    run_demo "LED Logo Display" "$BIN_DIR" bash rq_led_display_logo.sh
}

do_led_demo_scroll_welcome() {
    run_demo bg "Scrolling Welcome" "$BIN_DIR" python3 demo_led_text_scroll_welcome.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_status() {
    run_demo bg "Status Messages" "$BIN_DIR" python3 demo_led_text_status.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_alert() {
    run_demo bg "Alert Flash" "$BIN_DIR" python3 demo_led_text_alert.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_rainbow_scroll() {
    run_demo bg "Rainbow Scroll" "$BIN_DIR" python3 demo_led_text_rainbow_scroll.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_rainbow_static() {
    run_demo bg "Rainbow Color Cycle" "$BIN_DIR" python3 demo_led_text_rainbow_static.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_gradient() {
    run_demo bg "Color Gradient" "$BIN_DIR" python3 demo_led_text_gradient.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_ibm_logo() {
    run_demo bg "IBM Logo" "$BIN_DIR" python3 rq_led_ibm_logo.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_rasqberry_logo() {
    run_demo bg "RasQberry Logo" "$BIN_DIR" python3 demo_led_rasqberry_logo.py
    _led_rc=$?
    do_led_off
    return $_led_rc
}

do_led_demo_logo_slideshow() {
    run_demo bg "Logo Slideshow" "$BIN_DIR" python3 demo_led_logo_slideshow.py
    _led_rc=$?
    do_led_off
    return $_led_rc
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
            CLEAR ) do_led_off                   || { handle_error "Failed to clear LEDs."; continue; } ;;
            " "|"  "|"   "|"    " ) continue ;;  # Ignore separator items
            *) break ;;
        esac
    done
}

# Directly-callable LED-layout verify (plan R1). Runs the one-look "is this your
# panel?" check when the shipped default hasn't been confirmed yet, then reloads
# the env so the corrected LED_LAYOUT / LED_LAYOUT_VERIFIED are visible. Called on
# first LED-menu open (below), and reused by the first-login + desktop-autostart
# triggers via rq_led_verify_prompt.sh. Gated on LED_LAYOUT_VERIFIED, so it is a
# no-op once the user has answered.
do_led_verify() {
    if [ "${LED_LAYOUT_VERIFIED:-false}" != "true" ]; then
        bash "$BIN_DIR/rq_led_setup_wizard.sh" --verify || true
        # keeps raspi-config's INTERACTIVE etc. (R-001)
        _rq_load_env 2>/dev/null || true
    fi
}

do_select_led_option() {
    # First-visit verification (plan R1): the image ships a default LED_LAYOUT,
    # so the first time this menu opens we offer a quick "is this your panel?"
    # check (render an 'F' through the current layout) instead of a from-scratch
    # setup. The wizard persists LED_LAYOUT_VERIFIED=true when the user answers,
    # so it never nags again. _RQ_LED_VERIFY_DONE guards against re-prompting
    # within this menu session if they cancelled without answering.
    if [ -z "${_RQ_LED_VERIFY_DONE:-}" ]; then
        _RQ_LED_VERIFY_DONE=1
        do_led_verify
    fi
    _led_last=""
    while true; do
        FUN=$(show_menu ${_led_last:+--default-item "$_led_last"} "RasQberry: LEDs" "LED options" \
           OFF "Turn off all LEDs" \
           DISP "Text & Logo Display" \
           quicktest "Quick LED Test (6 colors)" \
           test "LED Test & Diagnostics" \
           simple "Simple LED Demo" \
           IBM "IBM LED Demo" \
           layout "Configure Matrix Layout" \
           targets "Output Targets (strip / virtual / web)" \
           wizard "LED Setup Wizard (auto-detect layout)") || break
        _led_last="$FUN"
        case "$FUN" in
            OFF ) do_led_off || { handle_error "Turning off all LEDs failed."; continue; } ;;
            DISP ) do_led_display_menu || { handle_error "Failed to open text/logo display menu."; continue; } ;;
            quicktest )
                run_demo bg "Quick LED Test" "$BIN_DIR" python3 rq_test_leds.py || { handle_error "Quick LED test failed."; continue; }
                do_led_off
                ;;
            test )
                run_demo "LED Test" "$BIN_DIR" bash rq_led_test.sh || { handle_error "LED test failed."; continue; }
                do_led_off
                ;;
            simple )
                run_demo bg "Simple LED Demo" "$BIN_DIR" python3 rq_led_simpletest.py || { handle_error "Simple LED demo failed."; continue; }
                do_led_off
                ;;
            IBM )
                run_demo bg "IBM LED Demo" "$BIN_DIR" python3 rq_led_ibm_logo.py || { handle_error "IBM LED demo failed."; continue; }
                do_led_off
                ;;
            layout )
                do_select_led_layout || { handle_error "Failed to update LED layout."; continue; }
                ;;
            targets )
                do_led_output_menu || { handle_error "Failed to update LED output targets."; continue; }
                ;;
            wizard )
                # Interactive whiptail walkthrough (own process); auto-detects
                # the physical layout and writes LED_LAYOUT.
                bash "$BIN_DIR/rq_led_setup_wizard.sh" || { handle_error "LED setup wizard failed."; continue; }
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
                do_rasp_tie_install || continue
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
       LOOP "Continuous Demo Loop (Conference)" \
       STOP "Stop last running demo and clear LEDs" \
       QSTP "Stop Qoffee-Maker" \
       QMXS "Stop Quantum-Mixer") || break
    _qd_last="$FUN"
    case "$FUN" in
      LED)  do_select_led_option       || { handle_error "Failed to open LED options."; continue; } ;;
      QLO)  do_select_qlo_option       || { handle_error "Failed to open QLO options."; continue; } ;;
      QRT)  do_select_qrt_option       || { handle_error "Failed to open QRT options."; continue; } ;;
      DALL) do_download_all_demos      || continue ;;
      ADDX) do_add_external_demo       || { handle_error "Failed to add demo from catalogue."; continue; } ;;
      LOOP) run_demo_loop
            # 130/143: stopped with Ctrl+C - the loop's own emergency stop
            case $? in 0|130|143) ;; *) handle_error "The demo loop stopped with an error."; continue ;; esac ;;
      STOP) stop_last_demo             || { handle_error "Failed to stop demo."; continue; } ;;
      QSTP) stop_qoffee_containers     || { handle_error "Failed to stop Qoffee-Maker."; continue; } ;;
      QMXS) stop_quantum_mixer_containers || { handle_error "Failed to stop Quantum-Mixer."; continue; } ;;
      "")   continue ;;
      # Any other tag is a manifest demo id -> universal dispatch (via the cache).
      *)    run_engine_demo dispatch_demo_by_id "$FUN" \
                || { handle_error "Could not run $(_rq_demo_label "$FUN")."; continue; } ;;
    esac
  done
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
  whiptail --title "RasQberry System Information" --msgbox \
    "$info\n\nFor bug reports: rq_info.sh --json" 18 78
}

# -----------------------------------------------------------------------------
# A/B Boot Partition Expansion
# -----------------------------------------------------------------------------

# Expand A/B partitions for 64GB+ SD cards
do_expand_ab_partitions() {
    # Check if this is an AB boot image
    if ! lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qi "config"; then
        whiptail --title "Not AB Boot Image" --msgbox \
            "This system is not running an A/B boot image.\n\nPartition expansion is only available for AB boot layouts." \
            10 60
        return 1
    fi

    # Get SD card size in bytes
    SD_SIZE_BYTES=$(lsblk -bno SIZE /dev/mmcblk0 2>/dev/null | head -1)
    SD_SIZE_GB=$((SD_SIZE_BYTES / 1024 / 1024 / 1024))

    # Minimum 58 GiB. A "64GB" card is only ~59.6 GiB (decimal marketing vs
    # binary GiB), so the old 63-GiB cutoff wrongly refused genuine 64GB cards.
    # 58 GiB accepts them and still rejects 32GB cards (~29.8 GiB).
    if [ "$SD_SIZE_GB" -lt 58 ]; then
        whiptail --title "SD Card Too Small" --msgbox \
            "SD card size: ${SD_SIZE_GB}GB\n\nPartition expansion requires a 64GB or larger SD card.\n\nYour current 10GB system partition is sufficient for basic use." \
            12 60
        return 1
    fi

    # Check if already expanded (system-b > 1GB indicates expansion)
    SYSTEM_B_SIZE=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    SYSTEM_B_SIZE_GB=$((SYSTEM_B_SIZE / 1024 / 1024 / 1024))
    if [ "$SYSTEM_B_SIZE_GB" -gt 1 ]; then
        whiptail --title "Already Expanded" --msgbox \
            "Partitions appear to already be expanded.\n\nSystem-B size: ${SYSTEM_B_SIZE_GB}GB" \
            10 60
        return 0
    fi

    # Calculate partition sizes
    # Fixed partitions: config (512MB) + boot-a (512MB) + boot-b (512MB) = 1536MB
    FIXED_MB=1536
    SD_SIZE_MB=$((SD_SIZE_BYTES / 1024 / 1024))
    AVAILABLE_MB=$((SD_SIZE_MB - FIXED_MB))

    # Calculate: data=10%, system-a=45%, system-b=45%
    DATA_MB=$((AVAILABLE_MB * 10 / 100))
    SYSTEM_MB=$(((AVAILABLE_MB - DATA_MB) / 2))

    DATA_GB=$((DATA_MB / 1024))
    SYSTEM_GB=$((SYSTEM_MB / 1024))

    # Show confirmation dialog
    if ! whiptail --title "Expand A/B Partitions" --yesno \
        "SD Card Size: ${SD_SIZE_GB}GB\n\nProposed partition sizes:\n  System-A: ${SYSTEM_GB}GB\n  System-B: ${SYSTEM_GB}GB\n  Data:     ${DATA_GB}GB\n\nThis will:\n- Expand system-a from 10GB to ${SYSTEM_GB}GB\n- Expand system-b from 16MB to ${SYSTEM_GB}GB\n- Expand data from 16MB to ${DATA_GB}GB\n\nThis operation cannot be undone.\n\nProceed with expansion?" \
        23 60; then
        return 0
    fi

    # Show progress
    # Say what is happening, step by step.
    #
    # The steps below log to /var/log/rasqberry-expand.log and print nothing, and
    # an --infobox does not block - so this used to draw one static "may take a
    # few minutes" box and then sit there, silent, for the whole run. Formatting
    # two ~100GB partitions (step 7) is minutes on its own, and a frozen box with
    # no output is indistinguishable from a hang, on an operation we also tell
    # people not to interrupt.
    # Plain text, NOT whiptail --infobox.
    #
    # An infobox does not block, and whiptail restores the screen when it exits -
    # so the box flashes and is gone. That is why this operation looked silent
    # with one infobox, and still looked silent when I gave it nine. The --yesno
    # dialogs work only because they block waiting for an answer.
    #
    # Once the confirmation closes, the screen is a plain terminal until the
    # final msgbox, which is exactly where the user is sitting and waiting - so
    # print there. Nine steps, several minutes, and formatting two ~50GB
    # partitions in step 7 with no output at all is indistinguishable from a
    # hang, on the one operation we also tell people not to interrupt.
    expand_progress() {
        printf '  [%s/9] %s\n' "$1" "$2"
    }

    echo ""
    echo "Expanding partitions. This takes several minutes on a large card -"
    echo "formatting the new partitions (step 7) is the slow part."
    echo "Do NOT power off the system."
    echo ""


    # Initialize log file
    echo "=== AB Partition Expansion $(date) ===" > /var/log/rasqberry-expand.log

    # Step 1: Unmount partitions that will be modified
    expand_progress 1 "Unmounting the placeholder partitions..."
    echo "Step 1: Unmounting partitions..." >> /var/log/rasqberry-expand.log
    umount /dev/mmcblk0p7 2>/dev/null || true
    umount /dev/mmcblk0p6 2>/dev/null || true
    # Also unmount any automounted locations
    umount /media/*/system-b 2>/dev/null || true
    umount /media/*/data 2>/dev/null || true

    # Get current partition boundaries
    # p5 = system-a, p6 = system-b, p7 = data
    SYSTEM_A_START=$(parted -s /dev/mmcblk0 unit MiB print | grep "^ 5" | awk '{print $2}' | tr -d 'MiB')

    # Calculate new boundaries
    SYSTEM_A_END=$((SYSTEM_A_START + SYSTEM_MB))
    SYSTEM_B_START=$((SYSTEM_A_END + 2))  # 2 MiB gap for alignment
    SYSTEM_B_END=$((SYSTEM_B_START + SYSTEM_MB))
    DATA_START=$((SYSTEM_B_END + 2))  # 2 MiB gap for alignment

    echo "Calculated boundaries:" >> /var/log/rasqberry-expand.log
    echo "  SYSTEM_A: ${SYSTEM_A_START} - ${SYSTEM_A_END} MiB" >> /var/log/rasqberry-expand.log
    echo "  SYSTEM_B: ${SYSTEM_B_START} - ${SYSTEM_B_END} MiB" >> /var/log/rasqberry-expand.log
    echo "  DATA: ${DATA_START} - 100%" >> /var/log/rasqberry-expand.log

    # Step 2: Delete p7 and p6 first (must be done before resizing p5)
    expand_progress 2 "Removing the 16MB placeholders..."
    echo "Step 2: Deleting old partitions..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 rm 7 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Warning: Failed to delete partition 7" >> /var/log/rasqberry-expand.log
    fi
    if ! parted -s /dev/mmcblk0 rm 6 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Warning: Failed to delete partition 6" >> /var/log/rasqberry-expand.log
    fi

    # Step 3: Expand extended partition (p4) to fill disk
    expand_progress 3 "Expanding the extended partition..."
    echo "Step 3: Expanding extended partition..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 resizepart 4 100% >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to expand extended partition" >> /var/log/rasqberry-expand.log
    fi

    # Step 4: Resize system-a (p5)
    expand_progress 4 "Resizing Slot A..."
    echo "Step 4: Resizing system-a partition..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 resizepart 5 ${SYSTEM_A_END}MiB >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to resize partition 5" >> /var/log/rasqberry-expand.log
    fi

    # Step 5: Create new system-b and data partitions
    expand_progress 5 "Creating Slot B and the data partition..."
    echo "Step 5: Creating new partitions..." >> /var/log/rasqberry-expand.log
    if ! parted -s /dev/mmcblk0 mkpart logical ext4 ${SYSTEM_B_START}MiB ${SYSTEM_B_END}MiB >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to create system-b partition" >> /var/log/rasqberry-expand.log
    fi
    if ! parted -s /dev/mmcblk0 mkpart logical ext4 ${DATA_START}MiB 100% >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to create data partition" >> /var/log/rasqberry-expand.log
    fi

    # Wait for kernel to recognize new partitions
    partprobe /dev/mmcblk0
    sleep 2

    # Step 6: Resize system-a filesystem
    expand_progress 6 "Growing the Slot A filesystem..."
    echo "Step 6: Resizing system-a filesystem..." >> /var/log/rasqberry-expand.log
    resize2fs /dev/mmcblk0p5 >> /var/log/rasqberry-expand.log 2>&1 || true

    # Step 7: Format new partitions
    expand_progress 7 "Formatting Slot B and the data partition (the slow step)..."
    echo "Step 7: Formatting new partitions..." >> /var/log/rasqberry-expand.log
    if ! mkfs.ext4 -F -L "system-b" /dev/mmcblk0p6 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to format system-b" >> /var/log/rasqberry-expand.log
    fi
    if ! mkfs.ext4 -F -L "data" /dev/mmcblk0p7 >> /var/log/rasqberry-expand.log 2>&1; then
        echo "Error: Failed to format data" >> /var/log/rasqberry-expand.log
    fi

    # Step 8: Set up system-b structure
    expand_progress 8 "Preparing Slot B..."
    echo "Step 8: Setting up system-b structure..." >> /var/log/rasqberry-expand.log
    TEMP_MOUNT=$(mktemp -d)
    if mount /dev/mmcblk0p6 "$TEMP_MOUNT" 2>> /var/log/rasqberry-expand.log; then
        # Create directory structure (no brace expansion - POSIX sh compatible)
        mkdir -p "$TEMP_MOUNT/boot/config"
        mkdir -p "$TEMP_MOUNT/boot/firmware"
        mkdir -p "$TEMP_MOUNT/data"
        mkdir -p "$TEMP_MOUNT/etc"

        # Create fstab for slot B
        cat > "$TEMP_MOUNT/etc/fstab" << EOF
proc                        /proc           proc    defaults          0   0
/dev/mmcblk0p1              /boot/config    vfat    defaults          0   2
/dev/mmcblk0p3              /boot/firmware  vfat    defaults          0   2
/dev/mmcblk0p6              /               ext4    defaults,noatime  0   1
/dev/mmcblk0p7              /data           ext4    defaults,noatime  0   2
EOF
        umount "$TEMP_MOUNT"
    fi
    rmdir "$TEMP_MOUNT" 2>/dev/null || true

    # Step 9: Set up data partition structure
    expand_progress 9 "Preparing the data partition..."
    echo "Step 9: Setting up data partition..." >> /var/log/rasqberry-expand.log
    TEMP_MOUNT=$(mktemp -d)
    if mount /dev/mmcblk0p7 "$TEMP_MOUNT" 2>> /var/log/rasqberry-expand.log; then
        # Create directory structure (no brace expansion - POSIX sh compatible)
        mkdir -p "$TEMP_MOUNT/home"
        mkdir -p "$TEMP_MOUNT/var/log"
        umount "$TEMP_MOUNT"
    fi
    rmdir "$TEMP_MOUNT" 2>/dev/null || true

    # Remount /data for current session
    mount /dev/mmcblk0p7 /data 2>/dev/null || true
    # /data was just reformatted: save this slot's LED settings there again
    /usr/bin/rq_device_settings.sh save >> /var/log/rasqberry-expand.log 2>&1 || true

    echo "=== Expansion complete ===" >> /var/log/rasqberry-expand.log

    # Verify expansion
    NEW_SYSTEM_B_SIZE=$(lsblk -bno SIZE /dev/mmcblk0p6 2>/dev/null)
    NEW_SYSTEM_B_GB=$((NEW_SYSTEM_B_SIZE / 1024 / 1024 / 1024))

    if [ "$NEW_SYSTEM_B_GB" -gt 1 ]; then
        whiptail --title "Expansion Complete" --msgbox \
            "Partitions expanded successfully!\n\nNew sizes:\n  System-A: ${SYSTEM_GB}GB\n  System-B: ${SYSTEM_GB}GB\n  Data:     ${DATA_GB}GB\n\nYour A/B boot system is now fully configured." \
            14 60
    else
        whiptail --title "Expansion Failed" --msgbox \
            "Partition expansion may have failed.\n\nPlease check /var/log/rasqberry-expand.log for details." \
            10 60
        return 1
    fi
}

# LED Matrix Layout Configuration
do_select_led_layout() {
  # Get current layout setting
  CURRENT_LAYOUT=$(check_environment_variable "LED_MATRIX_LAYOUT")

  # Show current setting in menu
  if [ "$CURRENT_LAYOUT" = "quad" ]; then
    CURRENT_DESC="Current: 4× 4×12 panels (quad layout)"
  else
    CURRENT_DESC="Current: Single 8×24 panel (serpentine)"
  fi

  FUN=$(show_menu "LED Matrix Layout Configuration" "$CURRENT_DESC\n\nSelect your LED matrix layout:\nBoth layouts use 192 LEDs (8 rows × 24 columns)" \
     single "Single 8×24 serpentine panel" \
     quad   "4× 4×12 panels (2×2 grid)") || return 0

  case "$FUN" in
    single)
      update_environment_file "LED_MATRIX_LAYOUT" "single"
      update_environment_file "LED_MATRIX_Y_FLIP" "true"
      whiptail --title "LED Layout Updated" --msgbox \
        "LED matrix layout set to:\n\nSingle 8×24 serpentine panel\n- Total: 192 LEDs (8 rows × 24 columns)\n- Wiring: Serpentine (zigzag) pattern\n- Y-axis: Flipped (upside down)\n\nRestart demos for changes to take effect." \
        13 60
      ;;
    quad)
      update_environment_file "LED_MATRIX_LAYOUT" "quad"
      update_environment_file "LED_MATRIX_Y_FLIP" "false"
      whiptail --title "LED Layout Updated" --msgbox \
        "LED matrix layout set to:\n\n4× 4×12 panels (quad layout)\n- Total: 192 LEDs (8 rows × 24 columns)\n- Each panel: 4×12 LEDs\n- Arrangement: 2×2 grid\n- Wiring: TL→TR→BR→BL\n\nRestart demos for changes to take effect." \
        14 60
      ;;
    *)
      return 0
      ;;
  esac
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

    # Step 1: Repository selection
    local tmpfile=$(mktemp)
    exec 4>"$tmpfile"

    whiptail --output-fd 4 --title "Update from GitHub Branch" --menu \
        "Select repository source:\n\nDetected: $detected_repo" \
        14 70 2 \
        "detected" "Use detected repository ($detected_repo)" \
        "custom"   "Enter custom repository" \
        1>/dev/tty 2>/dev/tty </dev/tty

    local exit_code=$?
    exec 4>&-

    if [ $exit_code -ne 0 ]; then
        rm -f "$tmpfile"
        return 0
    fi

    local repo_choice=$(cat "$tmpfile")
    rm -f "$tmpfile"

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
    local branch default_branch="${RQB_BUILD_BRANCH:-main}" built_from=""
    [ -f /etc/rasqberry-version ] && built_from="\n\nThis image: $(cat /etc/rasqberry-version)"
    [ -n "${RQB_BUILD_BRANCH:-}" ] && built_from="$built_from\nBuilt from: ${RQB_BUILD_REPO:-?} @ $RQB_BUILD_BRANCH"
    branch=$(whiptail --inputbox "Enter branch name to update from:$built_from\n\nCommon branches: main, beta, development" 14 70 "$default_branch" 3>&1 1>&2 2>&3)
    if [ $? -ne 0 ] || [ -z "$branch" ]; then
        return 0
    fi

    # Step 3: Confirmation
    if ! whiptail --title "Confirm Update" --yesno \
        "This will update RasQberry scripts and configuration.\n\nRepository: $repo\nBranch: $branch\n\nThis updates:\n  - Scripts in /usr/bin/\n  - Config files in /usr/config/ (your settings are kept)\n  - Boot scripts, services, autostart entries\n\nThis does NOT update:\n  - System packages or kernel\n  - Python virtual environment\n\nA backup will be created before updating.\n\nProceed with update?" \
        20 70; then
        return 0
    fi

    # Step 4: Run update
    whiptail --title "Updating..." --infobox \
        "Updating from GitHub...\n\nRepository: $repo\nBranch: $branch\n\nThis may take a minute.\nPlease wait..." \
        12 60

    local update_output
    local update_result

    # Run the update script and capture output
    update_output=$("$BIN_DIR/rq_update_from_branch.sh" --repo "$repo" --branch "$branch" 2>&1) || update_result=$?

    if [ "${update_result:-0}" -eq 0 ]; then
        whiptail --title "Update Complete" --msgbox \
            "Update completed successfully!\n\nRepository: $repo\nBranch: $branch\n\nChanges applied:\n  - Scripts updated in /usr/bin/\n  - Config files updated in /usr/config/\n  - Environment reloaded\n\nYou may need to exit and re-enter raspi-config\nfor menu changes to take effect." \
            18 70
    else
        whiptail --title "Update Failed" --msgbox \
            "Update failed!\n\nError output:\n$update_output\n\nCheck /var/log/rasqberry-branch-update.log for details." \
            16 70
        return 1
    fi
}

# Is a newer image published for this image's channel? (#139)
do_check_for_update() {
    local out rc=0 how
    whiptail --title "Checking for updates" --infobox "Asking rasqberry.org for the latest release..." 8 60
    out=$(/usr/bin/rq_update_check.sh --refresh 2>&1) || rc=$?
    if [ "$rc" -eq 10 ]; then
        if lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE "^config$"; then
            how="Install it into the other slot:\nSlot Manager -> Update Slot B with new image."
        else
            how="Download it from rasqberry.org/latest/ and write it to a card\n(the standard image has no second slot to update into)."
        fi
        whiptail --title "Update available" --msgbox "$out\n\n$how" 16 76
    else
        whiptail --title "Check for updates" --msgbox "$out" 12 76
    fi
    return 0
}

# Software & Image Updates Menu
do_ab_boot_menu() {
    while true; do
        # Check if this is an AB boot image
        local is_ab_image="No"
        if lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE "^config$"; then
            is_ab_image="Yes"
        fi

        # The A/B entries only make sense on an A/B partition layout
        set -- CHECK "Check for a newer image"
        if [ "$is_ab_image" = "Yes" ]; then
            set -- "$@" EXPAND "Expand A/B Partitions (64GB+ SD)" \
                SLOTS "Slot Manager (switch, confirm, promote)"
        fi
        # "Update from GitHub Branch" is under RasQberry -> Advanced (Q35)
        FUN=$(show_menu "RasQberry: Software & Image Updates" "A/B Image: ${is_ab_image}" "$@") || break

        case "$FUN" in
            CHECK)  do_check_for_update     || continue ;;
            EXPAND) do_expand_ab_partitions || continue ;;
            SLOTS)  do_slot_manager_menu    || continue ;;
            *)      continue ;;
        esac
    done
}

# GitHub Release Picker Helper Functions
# Fetch releases from GitHub and select image via menus

# Pick stream (dev/beta/stable)
pick_stream() {
    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    # Use temp file with --output-fd to separate selection from display
    local tmpfile=$(mktemp)

    # Open tmpfile for writing as fd 4 (avoid conflict with parent menu's fd 3)
    exec 4>"$tmpfile"

    # Use --output-fd 4 to write selection to tmpfile
    # Redirect UI (stdout/stderr) to the tty; only the selection goes to fd 4
    whiptail --output-fd 4 --title "Select Release Stream" --menu \
        "Choose the release stream:\n\n  dev    - Development builds (latest features)\n  beta   - Beta releases (testing)\n  stable - Stable releases (production)" \
        16 60 3 \
        "dev"    "Development builds" \
        "beta"   "Beta releases" \
        "stable" "Stable releases" \
        1>/dev/tty 2>/dev/tty </dev/tty

    local exit_code=$?
    exec 4>&-

    if [ $exit_code -eq 0 ]; then
        cat "$tmpfile"
        rm -f "$tmpfile"
        return 0
    else
        rm -f "$tmpfile"
        return 1
    fi
}

# Pick release from stream
pick_release() {
    local stream="$1"
    local github_user_param="$2"
    local github_repo_param="$3"
    local releases_json
    local menu_items
    local selected

    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    # Use provided parameters or fall back to environment variables
    # Environment variables are set by the workflow during build and stored in rasqberry_environment.env
    local github_user="${github_user_param:-${RQB_GIT_USER:-JanLahmann}}"
    local github_repo="${github_repo_param:-${REPO:-RasQberry-Two}}"

    # Fetch releases from GitHub
    whiptail --title "Fetching Releases" --infobox \
        "Fetching releases from GitHub...\n\nPlease wait." 8 50 \
        1>/dev/tty 2>/dev/tty </dev/tty

    # Download directly to temp file to avoid command substitution issues
    local releases_file=$(mktemp)
    if ! curl -s "https://api.github.com/repos/$github_user/$github_repo/releases" -o "$releases_file" 2>/dev/null; then
        rm -f "$releases_file"
        whiptail --title "Error" --msgbox "Failed to fetch releases from GitHub.\n\nPlease check your internet connection." 10 60 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Check if download was successful and has content
    if [ ! -s "$releases_file" ] || grep -q '"message"' "$releases_file"; then
        rm -f "$releases_file"
        whiptail --title "Error" --msgbox "Failed to fetch releases from GitHub.\n\nPlease check your internet connection." 10 60 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Filter releases by stream prefix and build menu items
    # Format: tag_name + created_at for display
    menu_items=$(jq -r --arg stream "$stream" '
        [.[] | select(.tag_name | startswith($stream + "-"))] |
        sort_by(.created_at) | reverse |
        .[0:10] |
        .[] |
        "\(.tag_name)\n\(.created_at | split("T")[0])"
    ' < "$releases_file" 2>/dev/null)

    # Clean up temp file
    rm -f "$releases_file"

    if [ -z "$menu_items" ]; then
        whiptail --title "No Releases" --msgbox "No releases found for stream: $stream\n\nTry a different stream." 10 50 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Convert to whiptail menu format (tag date tag date ...)
    # Build args safely without xargs to preserve spaces and provide TTY
    local tmpfile=$(mktemp)
    exec 4>"$tmpfile"

    # Build argument list from menu_items (one arg per line)
    set --
    while IFS= read -r line; do
        set -- "$@" "$line"
    done <<EOF
$menu_items
EOF

    # Use --output-fd to separate selection from display
    whiptail --output-fd 4 --title "Select Release" --menu \
        "Choose a release from the '$stream' stream:" \
        20 70 10 "$@" </dev/tty 1>/dev/tty 2>/dev/tty

    local exit_code=$?
    exec 4>&-

    if [ $exit_code -eq 0 ]; then
        selected=$(cat "$tmpfile")
        rm -f "$tmpfile"
        echo "$selected"
        return 0
    else
        rm -f "$tmpfile"
        return 1
    fi
}

# Pick image from release assets
pick_image() {
    local release_tag="$1"
    local github_user_param="$2"
    local github_repo_param="$3"
    local assets_json
    local menu_items
    local selected

    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    # Use provided parameters or fall back to environment variables
    # Environment variables are set by the workflow during build and stored in rasqberry_environment.env
    local github_user="${github_user_param:-${RQB_GIT_USER:-JanLahmann}}"
    local github_repo="${github_repo_param:-${REPO:-RasQberry-Two}}"

    # Fetch release assets
    whiptail --title "Fetching Images" --infobox \
        "Fetching available images for release:\n$release_tag\n\nPlease wait." 10 60 \
        1>/dev/tty 2>/dev/tty </dev/tty

    # Download directly to temp file to avoid command substitution issues
    local assets_file=$(mktemp)
    if ! curl -s "https://api.github.com/repos/$github_user/$github_repo/releases/tags/$release_tag" -o "$assets_file" 2>/dev/null; then
        rm -f "$assets_file"
        whiptail --title "Error" --msgbox "Failed to fetch release details.\n\nPlease check your connection." 10 60 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Check if download was successful and has content
    if [ ! -s "$assets_file" ] || grep -q '"message"' "$assets_file"; then
        rm -f "$assets_file"
        whiptail --title "Error" --msgbox "Failed to fetch release details.\n\nPlease check your connection." 10 60 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Filter for .img.xz files and build menu items
    # Create a mapping of short tags to filenames for display
    # Format: filename|tag|description (one per line)
    # AB boot images end with -ab.img.xz (display shows: xxx-ab)
    local image_map
    image_map=$(jq -r '
        .assets[] |
        select(.name | endswith(".img.xz")) |
        if (.name | test("-ab\\.img\\.xz$")) then
            "\(.name)|[AB]|\(.name | sub(".*rasqberry-"; "") | sub(".img.xz$"; "")) (\(.size / 1024 / 1024 | floor)MB)"
        else
            "\(.name)| |\(.name | sub(".*rasqberry-"; "") | sub(".img.xz$"; "")) (\(.size / 1024 / 1024 | floor)MB)"
        end
    ' < "$assets_file" 2>/dev/null)

    # Build menu_items in whiptail format (tag description pairs)
    menu_items=$(echo "$image_map" | awk -F'|' '{print $2 "\n" $3}')

    # Clean up temp file
    rm -f "$assets_file"

    if [ -z "$menu_items" ]; then
        whiptail --title "No Images" --msgbox "No image files found in release: $release_tag" 10 50 \
            1>/dev/tty 2>/dev/tty </dev/tty
        return 1
    fi

    # Count number of images (count tags)
    local image_count
    image_count=$(echo "$image_map" | wc -l)

    if [ "$image_count" -eq 1 ]; then
        # Only one image, return URL directly
        local filename
        filename=$(echo "$image_map" | cut -d'|' -f1)
        # Reconstruct URL from filename
        echo "https://github.com/$github_user/$github_repo/releases/download/$release_tag/$filename"
        return 0
    else
        # Multiple images, show selection menu using --output-fd
        # Build args safely without xargs to preserve spaces and provide TTY
        local tmpfile=$(mktemp)
        exec 4>"$tmpfile"

        # Build argument list from menu_items (one arg per line)
        set --
        while IFS= read -r line; do
            set -- "$@" "$line"
        done <<EOF
$menu_items
EOF

        # Use --output-fd to separate selection from display
        whiptail --output-fd 4 --title "Select Image" --menu \
            "Multiple images available.\nChoose the image type:" \
            16 80 5 "$@" </dev/tty 1>/dev/tty 2>/dev/tty

        local exit_code=$?
        exec 4>&-

        if [ $exit_code -eq 0 ]; then
            local selected_tag
            selected_tag=$(cat "$tmpfile")
            rm -f "$tmpfile"

            # Look up filename from tag in image_map
            local filename
            filename=$(echo "$image_map" | awk -F'|' -v tag="$selected_tag" '$2 == tag {print $1; exit}')

            if [ -z "$filename" ]; then
                return 1
            fi

            # Reconstruct URL from filename
            echo "https://github.com/$github_user/$github_repo/releases/download/$release_tag/$filename"
            return 0
        else
            rm -f "$tmpfile"
            return 1
        fi
    fi
}

# Ask user for GitHub repository source (default or custom)
# Returns: "default" or "user/repo" format
pick_repo_source() {
    # Ensure TERM is set for whiptail
    [ -z "$TERM" ] && export TERM=linux

    local tmpfile=$(mktemp)
    exec 4>"$tmpfile"

    # Show default repo from environment
    local default_repo="${RQB_GIT_USER:-JanLahmann}/${REPO:-RasQberry-Two}"

    whiptail --output-fd 4 --title "Select Repository" --menu \
        "Choose the GitHub repository to fetch releases from:\n\nDefault: $default_repo" \
        16 70 2 \
        "default" "Use default repository ($default_repo)" \
        "custom"  "Enter custom GitHub repository" \
        1>/dev/tty 2>/dev/tty </dev/tty

    local exit_code=$?
    exec 4>&-

    if [ $exit_code -eq 0 ]; then
        local choice=$(cat "$tmpfile")
        rm -f "$tmpfile"

        if [ "$choice" = "custom" ]; then
            # Prompt for custom GitHub repository in user/repo format
            local custom_repo
            custom_repo=$(whiptail --inputbox "Enter GitHub repository in format:\nusername/repository\n\nExample: JanLahmann/RasQberry-Two" 12 60 "$default_repo" 3>&1 1>&2 2>&3)

            if [ $? -eq 0 ] && [ -n "$custom_repo" ]; then
                # Validate format (should contain exactly one /)
                if echo "$custom_repo" | grep -q '^[^/]\+/[^/]\+$'; then
                    echo "$custom_repo"
                    return 0
                else
                    whiptail --title "Invalid Format" --msgbox "Invalid repository format.\n\nPlease use: username/repository" 10 50 \
                        1>/dev/tty 2>/dev/tty </dev/tty
                    return 1
                fi
            else
                return 1
            fi
        else
            echo "default"
            return 0
        fi
    else
        rm -f "$tmpfile"
        return 1
    fi
}

# Main release picker function - returns "url|tag" or empty on cancel
do_pick_release_image() {
    local stream
    local release_tag
    local image_url
    local github_user
    local github_repo

    # Step 0: Ask for repository source (default or custom)
    local repo_choice
    repo_choice=$(pick_repo_source) || return 1

    if [ "$repo_choice" = "default" ]; then
        # Use environment variables
        github_user="${RQB_GIT_USER:-JanLahmann}"
        github_repo="${REPO:-RasQberry-Two}"
    else
        # Parse custom repo (format: user/repo)
        github_user=$(echo "$repo_choice" | cut -d'/' -f1)
        github_repo=$(echo "$repo_choice" | cut -d'/' -f2)
    fi

    # Step 1: Pick stream
    stream=$(pick_stream) || return 1

    # Step 2: Pick release from stream (pass repo info)
    release_tag=$(pick_release "$stream" "$github_user" "$github_repo") || return 1

    # Step 3: Pick image from release (pass repo info)
    image_url=$(pick_image "$release_tag" "$github_user" "$github_repo") || return 1

    # Return url|tag format
    echo "${image_url}|${release_tag}"
}

# A/B Boot Slot Manager Menu
do_slot_manager_menu() {
    # Check if this is an AB boot image
    if ! lsblk -no LABEL /dev/mmcblk0p1 2>/dev/null | grep -qiE "^config$"; then
        whiptail --title "Not AB Boot Image" --msgbox \
            "This system is not running an A/B boot image.\n\nSlot management is only available for AB boot layouts." \
            10 60
        return 1
    fi

    while true; do
        # Get current status for menu display
        local current_slot
        current_slot=$(/usr/bin/rq_slot_manager.sh status 2>&1 | grep "Current Slot:" | awk '{print $NF}')
        local slot_status
        slot_status=$(/usr/bin/rq_slot_manager.sh status 2>&1 | grep "Slot Status:" | sed 's/.*Slot Status: //')

        FUN=$(show_menu "RasQberry: A/B Boot Slot Manager" "Current: Slot ${current_slot} (${slot_status})" \
            STATUS    "Show detailed slot status" \
            CONFIRM   "Confirm current slot (prevent rollback)" \
            TRYBOOT_A "Switch to Slot A and reboot now" \
            TRYBOOT_B "Switch to Slot B and reboot now" \
            UPDATE    "Update Slot B with new image" \
            ROLLBACK  "Force rollback to other slot" \
            PROMOTE   "Promote Slot B to Slot A") || break

        case "$FUN" in
            STATUS)
                local status_output
                status_output=$(/usr/bin/rq_slot_manager.sh status 2>&1)
                whiptail --title "A/B Boot Status" --msgbox "$status_output" 20 70
                ;;
            CONFIRM)
                local confirm_output
                confirm_output=$(/usr/bin/rq_slot_manager.sh confirm 2>&1)
                whiptail --title "Confirm Slot" --msgbox "$confirm_output" 12 60
                ;;
            TRYBOOT_A)
                if whiptail --title "Switch to Slot A" --yesno \
                    "This will switch to Slot A and reboot immediately.\n\nIf the boot fails, the system will automatically rollback.\n\nContinue?" 12 60; then
                    whiptail --title "Switching to Slot A" --infobox \
                        "Configuring tryboot and rebooting to Slot A..." 6 50
                    exec /usr/bin/rq_slot_manager.sh switch-to A --reboot
                fi
                ;;
            TRYBOOT_B)
                if whiptail --title "Switch to Slot B" --yesno \
                    "This will switch to Slot B and reboot immediately.\n\nNote: Slot B must have a valid system image installed.\nIf the boot fails, the system will automatically rollback.\n\nContinue?" 14 60; then
                    whiptail --title "Switching to Slot B" --infobox \
                        "Configuring tryboot and rebooting to Slot B..." 6 50
                    exec /usr/bin/rq_slot_manager.sh switch-to B --reboot
                fi
                ;;
            UPDATE)
                # Use release picker to select image from GitHub
                local picker_result
                picker_result=$(do_pick_release_image) || continue

                # Parse result (url|tag format)
                local image_url
                local release_tag
                image_url=$(echo "$picker_result" | cut -d'|' -f1)
                release_tag=$(echo "$picker_result" | cut -d'|' -f2)

                if [ -z "$image_url" ] || [ -z "$release_tag" ]; then
                    whiptail --title "Error" --msgbox "Failed to get image selection." 8 50
                    continue
                fi

                # Extract just the filename for display
                local image_name
                image_name=$(basename "$image_url")

                if whiptail --title "Confirm Update" --yesno \
                    "This will download and install:\n\nRelease: $release_tag\nImage: $image_name\n\nThis will take 10-20 minutes and reboot automatically.\n\nContinue?" 16 70; then

                    whiptail --title "Updating Slot B" --infobox \
                        "Downloading and installing image to Slot B...\n\nThis will take 10-20 minutes.\nSystem will reboot automatically when complete." 10 60

                    # Run update script (reboots automatically via slot manager)
                    exec /usr/bin/rq_update_slot.sh "$image_url" "$release_tag" --slot B
                fi
                ;;
            ROLLBACK)
                if whiptail --title "Force Rollback" --yesno \
                    "This will force a rollback to the other slot.\n\nUse this if the current slot is having problems.\n\nContinue?" 12 60; then
                    local rollback_output
                    rollback_output=$(/usr/bin/rq_slot_manager.sh rollback 2>&1)
                    whiptail --title "Rollback" --msgbox "$rollback_output\n\nReboot required for changes to take effect." 14 60
                fi
                ;;
            PROMOTE)
                if whiptail --title "Promote Slot B" --yesno \
                    "This will promote Slot B to become the new Slot A.\n\nThis copies the tested Slot B system to Slot A.\n\nWARNING: This will overwrite Slot A!\n\nContinue?" 14 60; then
                    whiptail --title "Promoting Slot B" --infobox \
                        "Promoting Slot B to Slot A...\n\nThis may take several minutes." 8 50
                    local promote_output
                    promote_output=$(/usr/bin/rq_slot_manager.sh promote 2>&1)
                    whiptail --title "Promote Result" --msgbox "$promote_output" 16 70
                fi
                ;;
            *)
                continue
                ;;
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
                "$BIN_DIR/rq_touch_mode.sh" enable
                current_status="enabled"
                offer_desktop_restart
                ;;
            DISABLE)
                "$BIN_DIR/rq_touch_mode.sh" disable
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
offer_desktop_restart() {
    if whiptail --title "Restart Desktop?" --yesno \
        "Touch mode settings have been changed.\n\nRestart desktop session now for all changes to take effect?\n\n(You can also logout/login manually later)" \
        12 60; then
        whiptail --title "Restarting..." --infobox "Restarting desktop session..." 6 40
        sleep 2
        systemctl restart lightdm 2>/dev/null || true
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
        _ia_text="No IBM Quantum account is saved on this Pi.\n\nRaspberry Tie asks for your API key the first time you run it on a real quantum computer; notebooks and your own programs use QiskitRuntimeService.save_account()."
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

do_ibm_account_menu() {
    while true; do
        FUN=$(show_menu "RasQberry: IBM Quantum account" \
            "The account (API key) used for real IBM Quantum computers." \
            SHOW   "Show the saved account" \
            FORGET "Forget the saved account") || break
        case "$FUN" in
            SHOW)   do_ibm_account_show ;;
            FORGET) do_ibm_account_forget || continue ;;
            *)      break ;;
        esac
    done
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
    set -- QD "Quantum Demos" TOUCH "Touch Mode Settings" \
        BROWSER "Browser at login: $(browser_autostart_state)" \
        IBMQ "IBM Quantum account" \
        AB_BOOT "Software & Image Updates" INFO "System Info" \
        ADV "Advanced"
    FUN=$(show_menu ${_main_last:+--default-item "$_main_last"} "RasQberry: Main Menu" "System Options" "$@") || break
    _main_last="$FUN"
    case "$FUN" in
      QD)      do_quantum_demo_menu           || { handle_error "Failed to open Quantum Demos menu."; continue; } ;;
      TOUCH)   do_touch_mode_menu             || continue ;;
      BROWSER) do_toggle_browser_autostart    || continue ;;
      IBMQ)    do_ibm_account_menu            || continue ;;
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

$RQ_LAST_DEMO_ERROR" 76
        RQ_LAST_DEMO_ERROR=""
        return 1
    fi
    show_msgbox_fit "Error" "$_he_msg" 64
    return 1
}
