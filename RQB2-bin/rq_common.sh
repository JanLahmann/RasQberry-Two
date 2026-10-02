#!/bin/bash
# ============================================================================
# RasQberry Common Library (rq_common.sh)
# ============================================================================
# Shared utilities and functions for all RQB2 scripts
#
# Usage:
#   #!/bin/bash
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "${SCRIPT_DIR}/rq_common.sh"
#   load_rqb2_env
#
# Functions provided:
#   - Error handling: die, warn, info, debug
#   - Environment: load_rqb2_env, verify_env_vars
#   - Venv: activate_venv, ensure_venv, find_venv
#   - Dialogs: show_yesno, show_msgbox, show_infobox, show_menu
#   - Git: clone_demo, update_demo, fix_ownership
#   - LED: clear_leds, find_led_script
#   - Dependencies: require_command, check_docker, check_display
#   - Process: cleanup_demo_processes, setup_cleanup_trap
#   - Paths: get_demo_dir, ensure_demo_dir
#   - Users: get_user_name, run_as_user
#   - Browser: open_browser
# ============================================================================

# Prevent multiple sourcing
if [ -n "${RQ_COMMON_LOADED:-}" ]; then
    return 0
fi
RQ_COMMON_LOADED=1
# Where this library lives: /usr/bin when installed, RQB2-bin in a checkout
_RQ_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default paths
RQ_CONFIG_FILE="${RQ_CONFIG_FILE:-/usr/config/rasqberry_env-config.sh}"
RQ_ENV_FILE="${RQ_ENV_FILE:-/usr/config/rasqberry_environment.env}"

# Whiptail dimensions (can be overridden)
WT_HEIGHT="${WT_HEIGHT:-20}"
WT_WIDTH="${WT_WIDTH:-78}"
WT_MENU_HEIGHT="${WT_MENU_HEIGHT:-12}"

# ============================================================================
# 1. ERROR HANDLING & LOGGING
# ============================================================================

# Print error message and exit
# Usage: die "Error message"
die() {
    echo "ERROR: $*" >&2
    # The RasQberry menu passes a file here (RQB2_menu.sh run_engine_demo), so
    # the reason survives the menu redrawing over this terminal output.
    if [ -n "${RQ_ERROR_FILE:-}" ]; then
        printf '%s\n' "$*" >> "$RQ_ERROR_FILE" 2>/dev/null || true
    fi
    exit 1
}

# --help / -h for scripts that otherwise act on any argument: print the
# script's header comment and exit, before anything is downloaded, installed
# or started (R-107: --help used to clone, install Qiskit "--help" or start
# the demo loop).
# Usage (right after sourcing this file): rq_help_guard "$@"
rq_help_guard() {
    case "${1:-}" in
        -h|--help) ;;
        *) return 0 ;;
    esac
    local script="${BASH_SOURCE[1]:-$0}"
    # The first comment block after the shebang, without rulers and "#"
    awk 'NR == 1 && /^#!/ { next }
         /^#/ { sub(/^# ?/, ""); if ($0 !~ /^[=#-]+$/) print; seen = 1; next }
         seen { exit }' "$script"
    exit 0
}

# Print warning message
# Usage: warn "Warning message"
warn() {
    echo "WARNING: $*" >&2
}

# Print info message
# Usage: info "Info message"
info() {
    echo "INFO: $*"
}

# Print debug message (only if RQ_DEBUG=1)
# Usage: debug "Debug message"
debug() {
    if [ "${RQ_DEBUG:-0}" = "1" ]; then
        echo "DEBUG: $*" >&2
    fi
}

# ============================================================================
# 2. ENVIRONMENT MANAGEMENT
# ============================================================================

# Load RQB2 environment configuration
# This is the CANONICAL way to load environment - use this everywhere!
# Usage: load_rqb2_env
load_rqb2_env() {
    debug "Loading RQB2 environment from: $RQ_CONFIG_FILE"

    if [ ! -f "$RQ_CONFIG_FILE" ]; then
        die "Environment config not found at: $RQ_CONFIG_FILE"
    fi

    # shellcheck disable=SC1090
    . "$RQ_CONFIG_FILE" || die "Failed to load environment config"

    debug "Environment loaded: REPO=$REPO, USER_HOME=$USER_HOME"
}

# Verify required environment variables are set
# Usage: verify_env_vars REPO USER_HOME STD_VENV
verify_env_vars() {
    local missing_vars=()

    for var in "$@"; do
        if [ -z "${!var:-}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        die "Missing required environment variables: ${missing_vars[*]}"
    fi
}

# Run a command as root: directly when we are root, else through sudo.
_rq_as_root() {
    if [ "$(id -u)" = "0" ]; then "$@"; else sudo "$@"; fi
}

# Update a variable in the environment file
# Usage: update_env_var "VARIABLE_NAME" "new_value"
#
# The new file is written next to the old one and renamed over it only when it
# is complete. This used to be `sudo sed ... > tmp; sudo mv tmp env` with no
# check: on a full disk sed wrote nothing, the empty file replaced the settings
# and every demo then failed on unset variables (R-058). A failed write now
# leaves the file as it was and returns 1.
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    local env_dir tmp lines_before lines_after
    # Key and value come in through the environment, so no character in the
    # value (/ | & \) is special (the menu's _rq_env_write does the same).
    local prog='BEGIN { k = ENVIRON["RQ_EW_KEY"]; v = ENVIRON["RQ_EW_VALUE"]; done = 0 }
        index($0, k "=") == 1 { print k "=" v; done = 1; next }
        { print }
        END { if (!done) print k "=" v }'

    env_dir=$(dirname "$RQ_ENV_FILE")
    tmp=$(_rq_as_root mktemp "$env_dir/.rasqberry_environment.XXXXXX" 2>/dev/null) || tmp=""
    if [ -z "$tmp" ]; then
        warn "Could not save $var_name: cannot write in $env_dir (is the SD card full?)"
        return 1
    fi
    lines_before=$(wc -l < "$RQ_ENV_FILE" 2>/dev/null | tr -d ' ')
    if RQ_EW_KEY="$var_name" RQ_EW_VALUE="$var_value" awk "$prog" "$RQ_ENV_FILE" \
            | _rq_as_root tee "$tmp" > /dev/null; then
        lines_after=$(_rq_as_root wc -l "$tmp" 2>/dev/null | awk '{ print $1 }')
    else
        lines_after=0
    fi
    if [ "${lines_after:-0}" -lt "${lines_before:-1}" ] \
        || ! _rq_as_root chmod 644 "$tmp" \
        || ! _rq_as_root mv -f "$tmp" "$RQ_ENV_FILE"; then
        _rq_as_root rm -f "$tmp" 2>/dev/null || true
        warn "Could not save $var_name in $RQ_ENV_FILE (is the SD card full?). The settings were left as they were."
        return 1
    fi
    _rq_as_root chown root:root "$RQ_ENV_FILE" 2>/dev/null || true

    # LED settings also go to the store both A/B slots share (#290)
    case "$var_name" in
        *_INSTALLED) ;;
        LED_*|RASQ_LED_*) sudo /usr/bin/rq_device_settings.sh save >/dev/null 2>&1 || true ;;
    esac

    # Reload environment
    load_rqb2_env
}

# ============================================================================
# 3. VIRTUAL ENVIRONMENT MANAGEMENT
# ============================================================================

# Find virtual environment (tries multiple locations)
# Usage: venv_path=$(find_venv)
find_venv() {
    local venv_name="${1:-$STD_VENV}"
    local locations=(
        "$USER_HOME/$REPO/venv/$venv_name"
        "$USER_HOME/.local/venv/$venv_name"
        "$USER_HOME/venv/$venv_name"
    )

    for location in "${locations[@]}"; do
        if [ -f "$location/bin/activate" ]; then
            echo "$location"
            return 0
        fi
    done

    return 1
}

# Activate virtual environment (tries multiple locations)
# Usage: activate_venv [venv_name]
activate_venv() {
    local venv_name="${1:-$STD_VENV}"
    local venv_path

    venv_path=$(find_venv "$venv_name") || {
        warn "Virtual environment not found: $venv_name"
        return 1
    }

    debug "Activating venv: $venv_path"
    # shellcheck disable=SC1091
    . "$venv_path/bin/activate" || die "Failed to activate venv"

    # Root using the user's venv must not leave root-owned __pycache__ in it:
    # a later pip upgrade there fails half-way (#285, R-059). Exported, so it
    # also covers the python processes this script starts.
    if [ "$(id -u)" -eq 0 ]; then
        export PYTHONDONTWRITEBYTECODE=1
    fi
}

# Ensure virtual environment exists and has required packages
# Usage: ensure_venv [venv_name] [packages...]
ensure_venv() {
    local venv_name="${1:-$STD_VENV}"
    shift
    local required_packages=("$@")

    if ! activate_venv "$venv_name"; then
        die "Virtual environment not found. Please run setup first."
    fi

    # Verify required packages if specified
    for package in "${required_packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            die "Required package not found in venv: $package"
        fi
    done
}

# ============================================================================
# 4. WHIPTAIL DIALOGS
# ============================================================================

# Show yes/no dialog
# Usage: show_yesno "Title" "Question text" && echo "User said yes"
# Height that fits <text> in a whiptail box of <width>, at least <min>.
# whiptail cuts off text that does not fit instead of wrapping into view, so
# fixed heights truncated longer messages (e.g. the third-party demo
# disclaimer). Capped at the terminal height; the caller adds --scrolltext
# when the text is longer than that.
_rq_dialog_height() {
    local text="$1" width="$2" min="$3" lines rows
    lines=$(printf '%b\n' "$text" | fold -s -w $((width - 4)) | wc -l)
    rows=$(tput lines 2>/dev/null || echo 24)
    [ "$rows" -ge 10 ] 2>/dev/null || rows=24
    lines=$((lines + 7))
    [ "$lines" -lt "$min" ] && lines="$min"
    [ "$lines" -gt "$rows" ] && lines="$rows"
    echo "$lines"
}

# --scrolltext when <text> does not fit the chosen height
_rq_dialog_scroll() {
    local text="$1" width="$2" height="$3"
    [ "$(printf '%b\n' "$text" | fold -s -w $((width - 4)) | wc -l)" -gt $((height - 7)) ] && echo "--scrolltext"
    return 0
}

show_yesno() {
    local title="$1"
    local text="$2"
    local width="${4:-65}"
    local height
    height=$(_rq_dialog_height "$text" "$width" "${3:-12}")

    if command -v whiptail >/dev/null 2>&1; then
        # shellcheck disable=SC2046  # empty or --scrolltext
        whiptail --title "$title" $(_rq_dialog_scroll "$text" "$width" "$height") \
            --yesno "$text" "$height" "$width" 3>&1 1>&2 2>&3
    else
        # Fallback to read if whiptail not available
        echo "$text"
        read -rp "Continue? (y/n) " -n 1
        echo
        [[ $REPLY =~ ^[Yy]$ ]]
    fi
}

# Show message box
# Usage: show_msgbox "Title" "Message text"
show_msgbox() {
    local title="$1"
    local text="$2"
    local width="${4:-60}"
    local height
    height=$(_rq_dialog_height "$text" "$width" "${3:-10}")

    if command -v whiptail >/dev/null 2>&1; then
        # shellcheck disable=SC2046  # empty or --scrolltext
        whiptail --title "$title" $(_rq_dialog_scroll "$text" "$width" "$height") \
            --msgbox "$text" "$height" "$width" 3>&1 1>&2 2>&3
    else
        echo "=== $title ==="
        echo "$text"
        read -rp "Press Enter to continue..." -s
        echo
    fi
}

# Show info box (doesn't wait for user)
# Usage: show_infobox "Title" "Message text"
show_infobox() {
    local title="$1"
    local text="$2"
    local height="${3:-8}"
    local width="${4:-60}"

    if command -v whiptail >/dev/null 2>&1; then
        whiptail --title "$title" --infobox "$text" "$height" "$width"
    else
        echo "=== $title ==="
        echo "$text"
    fi
}

# Show menu (returns selected option)
# Usage: choice=$(show_menu "Title" "Choose option:" "1" "First" "2" "Second")
show_menu() {
    local title="$1"; shift
    local prompt="$1"; shift

    if command -v whiptail >/dev/null 2>&1; then
        whiptail --title "$title" --menu "$prompt" "$WT_HEIGHT" "$WT_WIDTH" "$WT_MENU_HEIGHT" "$@" 3>&1 1>&2 2>&3
    else
        echo "=== $title ==="
        echo "$prompt"
        select opt in "$@"; do
            echo "$opt"
            break
        done
    fi
}

# ============================================================================
# 5. GIT OPERATIONS
# ============================================================================

# Clone a demo repository with proper ownership
# Usage: clone_demo "https://github.com/user/repo.git" "/path/to/dest"
clone_demo() {
    local git_url="$1"
    local dest_dir="$2"
    local depth="${3:-1}"  # Default shallow clone

    info "Cloning repository: $git_url"
    debug "Destination: $dest_dir"

    mkdir -p "$(dirname "$dest_dir")" || die "Failed to create parent directory"

    if ! git clone --depth "$depth" "$git_url" "$dest_dir"; then
        rm -rf "$dest_dir"  # Clean up incomplete clone
        die "Failed to clone repository from: $git_url"
    fi

    # Fix ownership if cloned as root
    fix_root_ownership "$dest_dir"

    info "Repository cloned successfully"
}

# Update demo repository (git pull)
# Usage: update_demo "/path/to/demo"
update_demo() {
    local demo_dir="$1"
    local branch="${2:-main}"

    if [ ! -d "$demo_dir/.git" ]; then
        warn "Not a git repository: $demo_dir"
        return 1
    fi

    debug "Updating repository: $demo_dir"

    (
        cd "$demo_dir" || return 1
        git pull --quiet origin "$branch" 2>/dev/null || {
            warn "Could not update repository, using existing version"
            return 1
        }
    )
}

# Fix ownership of files/directories created as root
# Usage: fix_root_ownership "/path/to/file_or_dir"
fix_root_ownership() {
    local target="$1"
    local owner

    if [ ! -e "$target" ]; then
        warn "Target does not exist: $target"
        return 1
    fi

    # Detect owner (cross-platform: Linux and macOS)
    if command -v stat >/dev/null 2>&1; then
        owner=$(stat -c '%U' "$target" 2>/dev/null || stat -f '%Su' "$target" 2>/dev/null)
    else
        owner="unknown"
    fi

    if [ "$owner" = "root" ]; then
        local user_name
        user_name=$(get_user_name)

        debug "Fixing ownership of $target (was owned by root)"
        sudo chown -R "$user_name:$user_name" "$target" || warn "Failed to fix ownership"
    fi
}

# ============================================================================
# 6. LED CONTROL
# ============================================================================

# Find LED control script
# Usage: led_script=$(find_led_script)
find_led_script() {
    local script_name="${1:-turn_off_LEDs.py}"
    local locations=(
        "$BIN_DIR/$script_name"
        "$USER_HOME/.local/bin/$script_name"
        "/usr/bin/$script_name"
        "/usr/local/bin/$script_name"
    )

    for location in "${locations[@]}"; do
        if [ -f "$location" ]; then
            echo "$location"
            return 0
        fi
    done

    return 1
}

# Clear all LEDs
# Usage: clear_leds
clear_leds() {
    local led_script

    led_script=$(find_led_script "turn_off_LEDs.py") || {
        debug "LED script not found, skipping LED clear"
        return 0
    }

    # The LED libraries (board, neopixel) live in the venv; the system
    # python3 only printed "No module named 'board'" and left the LEDs on
    local py="python3" venv
    if venv=$(find_venv 2>/dev/null) && [ -x "$venv/bin/python3" ]; then
        py="$venv/bin/python3"
    fi
    debug "Clearing LEDs using: $py $led_script"
    "$py" "$led_script" 2>/dev/null || warn "Failed to clear LEDs"
}

# ============================================================================
# 7. DEPENDENCY CHECKING
# ============================================================================

# Require a command to be available
# Usage: require_command docker "Please install Docker first"
require_command() {
    local cmd="$1"
    local msg="${2:-Command not found: $cmd}"

    if ! command -v "$cmd" >/dev/null 2>&1; then
        die "$msg"
    fi
}

# Check if Docker is available
# Usage: check_docker || die "Docker required"
check_docker() {
    if command -v docker >/dev/null 2>&1; then
        debug "Docker found: $(docker --version 2>/dev/null | head -1)"
        return 0
    else
        return 1
    fi
}

# Check if display is available (for GUI apps)
# Usage: check_display || die "GUI display required"
check_display() {
    if [ -n "${DISPLAY:-}" ]; then
        debug "Display available: $DISPLAY"
        return 0
    else
        return 1
    fi
}

# ============================================================================
# 8. PROCESS MANAGEMENT
# ============================================================================

# Cleanup demo processes by name pattern
# Usage: cleanup_demo_processes "QuantumLightsOut" "RasQ-LED"
cleanup_demo_processes() {
    local patterns=("$@")

    for pattern in "${patterns[@]}"; do
        debug "Killing processes matching: $pattern"
        pkill -f "$pattern" 2>/dev/null || true
    done
}

# Setup cleanup trap for script exit
# Usage: setup_cleanup_trap cleanup_function
setup_cleanup_trap() {
    local cleanup_func="$1"

    # Ensure function exists
    if ! declare -f "$cleanup_func" >/dev/null; then
        die "Cleanup function not found: $cleanup_func"
    fi

    # Set up trap for common signals
    # shellcheck disable=SC2064
    trap "$cleanup_func" EXIT INT TERM
    debug "Cleanup trap registered: $cleanup_func"
}

# Default demo cleanup (can be called from custom cleanup functions)
# Usage: default_demo_cleanup "DemoProcessName"
default_demo_cleanup() {
    local process_pattern="${1:-}"

    debug "Running default demo cleanup..."

    # Kill demo processes if pattern provided
    if [ -n "$process_pattern" ]; then
        cleanup_demo_processes "$process_pattern"
    fi

    # Clear LEDs
    clear_leds
}

# ============================================================================
# 8b. NETWORK / PORT HELPERS
# ============================================================================
# Shared by rq_demo_run.sh and the standalone docker launchers so that every
# demo picks a FREE host port from its own base instead of hard-coding one -
# otherwise two demos collide (e.g. doQumentation + a Jupyter demo both wanting
# :8888). Give each demo a distinct base and these shift past a taken port.

# Find a free TCP port at or above the given base (default 8888).
# Usage: port=$(find_available_port 8896)
find_available_port() {
    local port="${1:-8888}"
    while true; do
        if command -v lsof &>/dev/null; then
            if ! lsof -i ":$port" &>/dev/null; then echo "$port"; return 0; fi
        elif command -v ss &>/dev/null; then
            if ! ss -tuln 2>/dev/null | grep -q ":$port "; then echo "$port"; return 0; fi
        elif command -v netstat &>/dev/null; then
            if ! netstat -tuln 2>/dev/null | grep -q ":$port "; then echo "$port"; return 0; fi
        else
            echo "$port"; return 0   # no tool available - assume free
        fi
        port=$((port + 1))
        if [ "$port" -gt 65535 ]; then die "Could not find an available port"; fi
    done
}

# Report whether a TCP port is currently in use. Returns 0 if in use.
port_in_use() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        lsof -i ":$port" &>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tuln 2>/dev/null | grep -q ":$port "
    elif command -v netstat &>/dev/null; then
        netstat -tuln 2>/dev/null | grep -q ":$port "
    else
        return 1   # no tool available - cannot tell, assume free
    fi
}

# ============================================================================
# 9. PATH & DIRECTORY HELPERS
# ============================================================================

# Get demo directory path
# Usage: demo_dir=$(get_demo_dir "Quantum-Lights-Out")
get_demo_dir() {
    local demo_name="$1"

    # Ensure REPO and USER_HOME are set
    : "${REPO:?REPO not set}"
    : "${USER_HOME:?USER_HOME not set}"

    echo "$USER_HOME/$REPO/demos/$demo_name"
}

# Ensure demo directory exists
# Usage: ensure_demo_dir "Quantum-Lights-Out" || die "Demo not installed"
ensure_demo_dir() {
    local demo_name="$1"
    local demo_dir

    demo_dir=$(get_demo_dir "$demo_name")

    if [ ! -d "$demo_dir" ]; then
        warn "Demo directory not found: $demo_dir"
        return 1
    fi

    debug "Demo directory verified: $demo_dir"
    echo "$demo_dir"
}

# ============================================================================
# 10. USER CONTEXT HELPERS
# ============================================================================

# Get non-root user name
# Usage: user=$(get_user_name)
get_user_name() {
    if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
        echo "$SUDO_USER"
    elif [ -n "${USER:-}" ] && [ "${USER}" != "root" ]; then
        echo "$USER"
    else
        whoami
    fi
}

# Run command as non-root user
# Usage: run_as_user command args...
run_as_user() {
    local user_name
    user_name=$(get_user_name)

    if [ "$(whoami)" = "root" ] && [ "$user_name" != "root" ]; then
        debug "Running as user: $user_name"
        # Preserve DISPLAY environment variable for GUI applications
        sudo -u "$user_name" -H DISPLAY="${DISPLAY:-:0}" -- "$@"
    else
        "$@"
    fi
}

# Ensure script is running as root (re-exec with sudo if needed)
# Usage: ensure_root "$@"
# Call this early in scripts that require root access (LED control, GPIO, etc.)
ensure_root() {
    if [ "$(id -u)" != "0" ]; then
        info "LED/GPIO operations require root access"
        info "Re-executing with sudo..."
        exec sudo -E "$0" "$@"
    fi
}

# ============================================================================
# 11. BROWSER LAUNCHING
# ============================================================================

# Open URL in available browser
# Usage: open_browser "http://localhost:8080"
open_browser() {
    local url="$1"
    local browsers=("chromium-browser" "firefox" "google-chrome" "xdg-open")

    for browser in "${browsers[@]}"; do
        if command -v "$browser" >/dev/null 2>&1; then
            info "Opening browser: $browser"

            # Run as user if we're root
            if [ "$(whoami)" = "root" ]; then
                local user_name
                user_name=$(get_user_name)
                su - "$user_name" -c "DISPLAY=${DISPLAY:-:0} $browser '$url' >/dev/null 2>&1 &" >/dev/null 2>&1 &
            else
                "$browser" "$url" &>/dev/null &
            fi

            return 0
        fi
    done

    warn "No browser found. Please open manually: $url"
    return 1
}

# ============================================================================
# 12. DEMO INSTALLATION HELPERS
# ============================================================================

# ----------------------------------------------------------------------------
# Consent and free space for downloads (Jan, Q27; R-030, R-166)
# ----------------------------------------------------------------------------
# Every first install asks once - the same dialog from the menu, a desktop icon
# or the command line: what is fetched, how big, how long, and free space now
# and afterwards. It refuses with a plain message when the space is too low or
# the download source cannot be reached. A first start used to download or
# build several GB without asking (one click could fill an A/B slot), and with
# outside traffic blocked git hung without a word.

# Space kept free on top of what a download needs (MB)
RQ_SPACE_RESERVE_MB="${RQ_SPACE_RESERVE_MB:-1000}"

# Free space in MB (1 MB = 1,000,000 bytes, as card sizes are sold) on the
# file system holding PATH, or its nearest existing parent.
# RQ_TEST_FREE_MB replaces the measurement (tests, lab).
# Usage: free=$(rq_free_mb /var/lib/docker)
rq_free_mb() {
    local p="${1:-/}"
    if [ -n "${RQ_TEST_FREE_MB:-}" ]; then
        echo "$RQ_TEST_FREE_MB"
        return 0
    fi
    while [ ! -e "$p" ] && [ "$p" != "/" ] && [ -n "$p" ]; do p=$(dirname "$p"); done
    df -Pk "$p" 2>/dev/null | awk 'NR == 2 { printf "%d\n", $4 * 1024 / 1000000 }'
}

# "850 MB", "3.9 GB"
# Usage: rq_fmt_mb 3900
rq_fmt_mb() {
    awk -v m="${1:-0}" 'BEGIN { if (m < 1000) printf "%d MB\n", m; else printf "%.1f GB\n", m / 1000 }'
}

# The URL to check before pulling a Docker image: its registry
# ("ghcr.io/x/y:tag" -> https://ghcr.io/v2/, "python:3" -> Docker Hub).
rq_image_registry_url() {
    local first="${1%%/*}"
    case "$1" in
        */*) case "$first" in *.*|*:*) echo "https://$first/v2/"; return 0 ;; esac ;;
    esac
    echo "https://registry-1.docker.io/v2/"
}

# Is URL reachable? Any HTTP answer counts (a registry answers 401). Short
# timeouts, so a network that drops outside traffic fails in seconds instead
# of hanging in git (R-166). RQ_TEST_OFFLINE=1 makes every check fail.
rq_reachable() {
    local url="${1:-}"
    [ "${RQ_TEST_OFFLINE:-0}" = "1" ] && return 1
    [ -n "$url" ] || return 0
    command -v curl >/dev/null 2>&1 || return 0   # cannot tell; let the download try
    curl -s -o /dev/null -I --connect-timeout 5 --max-time 10 "$url"
}

# Ask before a download. Shared by the demo engine, "Download all demos", the
# Docker launchers and other one-off downloads (e.g. a newer Docker image).
#
#   rq_confirm_download NAME DOWNLOAD_MB DISK_MB [options]
#     --what TEXT      what is fetched, e.g. "Jupyter notebooks from GitHub"
#     --time TEXT      rough duration, e.g. "1 minute", "10-15 minutes"
#     --path DIR       where the data goes; free space is measured there
#                      (default: $USER_HOME)
#     --url URL        checked first with a short timeout
#     --peak MB        extra space needed only while installing (a build cache)
#     --title TEXT     dialog title (default "Download NAME?")
#     --intro TEXT     first line (default "NAME is not on this Pi yet.")
#     --question TEXT  last line (default "Download now?")
#
# DOWNLOAD_MB/DISK_MB 0 = unknown. Returns 0 to go ahead, 1 declined, 2 not
# enough space, 3 source not reachable, 4 no terminal to ask on. For 1-4,
# RQ_CONSENT_MSG holds a sentence for the user. With RQ_AUTO_INSTALL=1 (the
# caller has already asked, e.g. "Download all demos") there is no question,
# but the space and network checks still run.
rq_confirm_download() {
    local name="$1" dl="${2:-0}" disk="${3:-0}"
    shift 3 || true
    local what="" time="" path="${USER_HOME:-/}" url="" peak=0 title="" intro="" question=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --what) what="$2"; shift 2 ;;
            --time) time="$2"; shift 2 ;;
            --path) path="$2"; shift 2 ;;
            --url) url="$2"; shift 2 ;;
            --peak) peak="$2"; shift 2 ;;
            --title) title="$2"; shift 2 ;;
            --intro) intro="$2"; shift 2 ;;
            --question) question="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    case "$dl" in ''|*[!0-9]*) dl=0 ;; esac
    case "$disk" in ''|*[!0-9]*) disk=0 ;; esac
    case "$peak" in ''|*[!0-9]*) peak=0 ;; esac
    RQ_CONSENT_MSG=""

    local free need space_txt
    free=$(rq_free_mb "$path")
    case "$free" in ''|*[!0-9]*) free="" ;; esac
    need=$((disk + peak + RQ_SPACE_RESERVE_MB))
    space_txt="about $(rq_fmt_mb "$disk")"
    [ "$disk" -gt 0 ] || space_txt="unknown"
    [ "$peak" -gt 0 ] && space_txt="$space_txt ($(rq_fmt_mb $((disk + peak))) while installing)"
    local card_txt="$space_txt on the SD card"
    [ "$disk" -gt 0 ] || card_txt="unknown"
    if [ -n "$free" ] && [ "$free" -lt "$need" ]; then
        RQ_CONSENT_MSG="Not enough free space for $name: it needs $space_txt plus $(rq_fmt_mb "$RQ_SPACE_RESERVE_MB") to spare, and $(rq_fmt_mb "$free") is free. Remove demos you do not use (RasQberry menu: Quantum Demos > Remove a demo) and try again."
        return 2
    fi

    if ! rq_reachable "$url"; then
        local host="${url#*://}"
        host="${host%%/*}"
        RQ_CONSENT_MSG="$name has to be downloaded first, and ${host:-the internet} cannot be reached. Connect the Pi to the internet and try again."
        return 3
    fi

    [ "${RQ_AUTO_INSTALL:-0}" = "1" ] && return 0

    local text dl_txt free_txt
    dl_txt="about $(rq_fmt_mb "$dl")"
    [ "$dl" -gt 0 ] || dl_txt="size unknown"
    free_txt="unknown"
    [ -n "$free" ] && free_txt="$(rq_fmt_mb "$free") now, $(rq_fmt_mb $((free > disk ? free - disk : 0))) afterwards"
    text="${intro:-$name is not on this Pi yet.}\n\n"
    [ -n "$what" ] && text="${text}What:      $what\n"
    text="${text}Download:  $dl_txt (needs the internet)\n"
    text="${text}Space:     $card_txt\n"
    [ -n "$time" ] && text="${text}Time:      about $time\n"
    text="${text}Free:      $free_txt\n\n${question:-Download now?}"

    # Ask on the terminal itself, so a caller that pipes our output (a log
    # tee) still gets the dialog drawn. (RQ_TEST_TTY: tests use a file.)
    local tty="${RQ_TEST_TTY:-/dev/tty}"
    if ! { : < "$tty" > "$tty"; } 2>/dev/null; then
        RQ_CONSENT_MSG="$name is not on this Pi yet. Start it from its desktop icon or the RasQberry menu, which ask before downloading."
        return 4
    fi
    if command -v whiptail >/dev/null 2>&1; then
        local width=72 height
        height=$(_rq_dialog_height "$text" "$width" 12)
        # shellcheck disable=SC2046  # empty or --scrolltext
        if whiptail --title "${title:-Download $name?}" --yes-button "Download" --no-button "Not now" \
                $(_rq_dialog_scroll "$text" "$width" "$height") \
                --yesno "$text" "$height" "$width" < "$tty" > "$tty" 2>&1; then
            return 0
        fi
    else
        local reply=""
        printf '%b\n' "$text" > "$tty"
        printf '(y/n) ' > "$tty"
        read -r reply < "$tty" || reply=""
        case "$reply" in [Yy]*) return 0 ;; esac
    fi
    RQ_CONSENT_MSG="$name was not downloaded."
    return 1
}

# Echo the shipped manifest directory (installed or repo checkout)
rq_shipped_manifest_dir() {
    if [ "$_RQ_COMMON_DIR" = "/usr/bin" ]; then
        echo "/usr/config/demo-manifests"
    else
        echo "$(dirname "$_RQ_COMMON_DIR")/RQB2-config/demo-manifests"
    fi
}

# Ask for a demo's first install, with the sizes from its manifest
# (install.download). Asks once per demo per run: a launcher the engine hands
# over to does not ask again (RQ_CONFIRMED_DEMO).
#   rq_confirm_demo_install DEMO_ID [MANIFEST_FILE]
# Returns like rq_confirm_download.
rq_confirm_demo_install() {
    local id="$1" mf="${2:-}"
    [ -n "$id" ] && [ "${RQ_CONFIRMED_DEMO:-}" = "$id" ] && return 0
    if [ -z "$mf" ]; then
        mf=$(rq_find_manifest "$(rq_shipped_manifest_dir)" "$id") || mf=""
    fi
    local name="$id" dl=0 disk=0 peak=0 what="" time="" url="" path="${USER_HOME:-/}"
    local type="" image="" repo=""
    if [ -n "$mf" ] && [ -f "$mf" ]; then
        name=$(jq -r '.name // .id' "$mf" 2>/dev/null) || name="$id"
        dl=$(jq -r '.install.download.download_mb // 0' "$mf" 2>/dev/null) || dl=0
        disk=$(jq -r '.install.download.disk_mb // .install.download.download_mb // 0' "$mf" 2>/dev/null) || disk=0
        peak=$(jq -r '.install.download.peak_mb // 0' "$mf" 2>/dev/null) || peak=0
        what=$(jq -r '.install.download.what // empty' "$mf" 2>/dev/null) || what=""
        time=$(jq -r '.install.download.time // empty' "$mf" 2>/dev/null) || time=""
        url=$(jq -r '.install.download.url // empty' "$mf" 2>/dev/null) || url=""
        type=$(jq -r '.entrypoint.type // empty' "$mf" 2>/dev/null) || type=""
        image=$(jq -r '.entrypoint.docker_image // empty' "$mf" 2>/dev/null) || image=""
        repo=$(jq -r '.install.repo_url // empty' "$mf" 2>/dev/null) || repo=""
    fi
    if [ "$type" = "docker" ] && [ -n "$image" ]; then
        path="/var/lib/docker"
        [ -n "$what" ] || what="Docker image ($image)"
        [ -n "$url" ] || url=$(rq_image_registry_url "$image")
    fi
    [ -n "$url" ] || url="${repo:-https://github.com}"
    rq_confirm_download "$name" "$dl" "$disk" --what "$what" --time "$time" \
        --path "$path" --peak "$peak" --url "$url" || return $?
    RQ_CONFIRMED_DEMO="$id"
    export RQ_CONFIRMED_DEMO
    return 0
}

# For scripts: ask for DEMO_ID's first install; a "Not now" ends the script
# quietly (exit 0), anything else that stops the download dies with the
# reason (shown by the menu, or by the desktop icon's window).
#   rq_require_demo_consent DEMO_ID [MANIFEST_FILE]
rq_require_demo_consent() {
    local rc=0
    rq_confirm_demo_install "$@" || rc=$?
    case "$rc" in
        0) return 0 ;;
        1) info "${RQ_CONSENT_MSG:-Not downloaded.}"; exit 0 ;;
        *) die "${RQ_CONSENT_MSG:-The download was stopped.}" ;;
    esac
}

# Old name, kept for scripts written from the template: ask_demo_install
# "LED-Painter" "5MB" "500MB" (sizes in MB or GB).
ask_demo_install() {
    rq_confirm_download "$1" "$(_rq_size_to_mb "${2:-0}")" "$(_rq_size_to_mb "${3:-0}")"
}
_rq_size_to_mb() {
    awk -v s="$1" 'BEGIN { n = s + 0; if (s ~ /[Gg][Bb]?$/) n *= 1000; printf "%d\n", n }'
}

# Remove a directory tree, also one a root run left behind (a half download
# from the menu is root-owned and a user's rm fails on it, R-057).
# Usage: rq_remove_tree DIR || die "..."
rq_remove_tree() {
    local d="$1"
    [ -n "$d" ] && [ "$d" != "/" ] || return 1
    [ -e "$d" ] || return 0
    rm -rf "$d" 2>/dev/null && return 0
    [ "$(id -u)" != "0" ] && sudo -n rm -rf "$d" 2>/dev/null && return 0
    [ ! -e "$d" ]
}

# Install demo by calling RQB2_menu.sh function directly
# Usage: install_demo_raspiconfig do_qlo_install || die "Install failed"
# Note: This sources RQB2_menu.sh and calls the install function directly,
#       which is more reliable than raspi-config nonint (which doesn't work
#       well with whiptail-based interactive functions)
install_demo_raspiconfig() {
    local install_func="$1"

    # Source RQB2_menu.sh to get access to install_demo functions
    local menu_script="/usr/config/RQB2_menu.sh"
    if [ ! -f "$menu_script" ]; then
        warn "RQB2_menu.sh not found at $menu_script"
        return 1
    fi

    # Enable auto-install mode (skip whiptail prompts for standalone launchers)
    export RQ_AUTO_INSTALL=1

    # Source the menu script (which in turn sources env-config.sh)
    # This gives us access to install_demo() and all do_*_install() functions
    if ! source "$menu_script"; then
        warn "Failed to source $menu_script"
        return 1
    fi

    # Call the install function directly
    if ! "$install_func"; then
        warn "Failed to run $install_func"
        return 1
    fi

    return 0
}

# ============================================================================
# 13. MANIFEST SEARCH PATH (external demos)
# ============================================================================
# Demo manifests are read from a two-entry search path:
#   1. the shipped directory (trusted, /usr/config/demo-manifests)
#   2. the user directory   ($USER_HOME/.local/config/demo-manifests)
# Shipped manifests always WIN on id collision (they are the trust anchor);
# a user manifest that reuses a shipped id is ignored (with a warning).
#
# The shipped directory differs between installed (/usr/config) and repo
# (RQB2-config) contexts, so callers pass it in. The user directory derives
# from USER_HOME and is skipped silently when USER_HOME is unset (dev/CI) or
# the directory does not exist - so everything degrades to shipped-only.

# Echo the user manifest directory. Returns non-zero (no output) when
# USER_HOME is not set, so callers can treat it as "no user dir".
rq_user_manifest_dir() {
    [ -n "${USER_HOME:-}" ] || return 1
    echo "$USER_HOME/.local/config/demo-manifests"
}

# Echo the existing manifest search directories, shipped first then user.
# Usage: rq_manifest_dirs "<shipped_dir>"
rq_manifest_dirs() {
    local shipped="$1" user_dir
    [ -d "$shipped" ] && echo "$shipped"
    if user_dir=$(rq_user_manifest_dir) \
        && [ -d "$user_dir" ] && [ "$user_dir" != "$shipped" ]; then
        echo "$user_dir"
    fi
}

# Resolve the manifest file for a demo id across the search path.
# Shipped wins. Echoes the path and returns 0 if found, else returns 1.
# Usage: file=$(rq_find_manifest "<shipped_dir>" "<id>")
rq_find_manifest() {
    local shipped="$1" id="$2" dir file
    while IFS= read -r dir; do
        [ -z "$dir" ] && continue
        file="$dir/rq_demo_${id}.json"
        if [ -f "$file" ]; then
            echo "$file"
            return 0
        fi
    done <<EOF
$(rq_manifest_dirs "$shipped")
EOF
    return 1
}

# List every manifest file across the search path, deduped by id with shipped
# precedence. Emits one path per line on stdout; warns (stderr) when a user
# manifest is shadowed by a shipped id.
# Usage: rq_list_manifests "<shipped_dir>"
rq_list_manifests() {
    local shipped="$1" dir file id seen_ids=" "
    while IFS= read -r dir; do
        [ -z "$dir" ] && continue
        while IFS= read -r -d '' file; do
            id=$(jq -r '.id // empty' "$file" 2>/dev/null)
            [ -z "$id" ] && id=$(basename "$file" .json | sed 's/^rq_demo_//')
            case "$seen_ids" in
                *" $id "*)
                    warn "Manifest id collision: '$id' from $file is shadowed by a shipped manifest (ignored)"
                    continue
                    ;;
            esac
            seen_ids="$seen_ids$id "
            echo "$file"
        done < <(find "$dir" -maxdepth 1 -name 'rq_demo_*.json' -not -name '*schema*' -print0 2>/dev/null | sort -z)
    done <<EOF
$(rq_manifest_dirs "$shipped")
EOF
}

# ============================================================================
# 14. PINNED REPOSITORY FETCH (external demos)
# ============================================================================
# A plain "git clone --depth 1" cannot fetch an arbitrary commit SHA, so we
# init an empty repo and fetch exactly the pinned ref. This is the install
# path for external demos, whose registry entry pins a full commit SHA.

# Fetch a single pinned commit into a fresh checkout.
# Usage: fetch_pinned_repo "<https-url>" "<full-sha>" "<dest-dir>"
fetch_pinned_repo() {
    local url="$1" sha="$2" dest="$3"

    case "$url" in
        https://*) : ;;
        *) die "Refusing non-https repo_url: $url" ;;
    esac
    if ! echo "$sha" | grep -qE '^[0-9a-fA-F]{40}$'; then
        die "Registry ref must be a full 40-character commit SHA, got: $sha"
    fi

    mkdir -p "$dest" || die "Cannot create destination: $dest"
    # A failed or interrupted fetch must not leave a half checkout: run as root
    # (the menu) it was root-owned, and every later install - from a desktop
    # icon as the user, or the catalogue - failed on it (R-057).
    # The low-speed limit ends a transfer that stalls (traffic dropped by a
    # filter) instead of hanging without a word (R-166).
    if ! (
        cd "$dest" || die "Cannot enter destination: $dest"
        git init -q || die "git init failed in $dest"
        git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 \
            fetch -q --depth 1 "$url" "$sha" 2>/dev/null \
            || die "Failed to fetch pinned commit $sha from $url"
        git checkout -q FETCH_HEAD || die "Failed to checkout pinned commit $sha"
    ); then
        rq_remove_tree "$dest" || warn "Could not remove the incomplete download: $dest"
        return 1
    fi

    # Keep the checkout user-owned when this runs as root (raspi-config context)
    fix_root_ownership "$dest"
}

# ============================================================================
# A/B BOOT PARTITION HELPERS
# ============================================================================
# Single source of truth for slot -> device resolution (issue #229).
# Resolves by partition label first (works on SD, NVMe and USB boot),
# falling back to partition-number naming on the boot device.

ab_boot_device() {
    # Print the parent block device of the running root fs (e.g. mmcblk0, sda)
    lsblk -no pkname "$(findmnt / -o source -n)"
}

ab_partition_by_number() {
    # Print partition device <n> of the boot device, handling both
    # mmcblk0p<n> and sda<n> naming
    local num="$1" dev
    dev=$(ab_boot_device)
    if [ -b "/dev/${dev}p${num}" ]; then
        echo "/dev/${dev}p${num}"
    else
        echo "/dev/${dev}${num}"
    fi
}

ab_partition_by_label() {
    # Print the partition device with the given label (case-insensitive),
    # searching only the device the system booted from. Empty if not found.
    local label="$1" dev
    dev=$(ab_boot_device)
    lsblk -lnpo NAME,LABEL "/dev/${dev}" 2>/dev/null \
        | awk -v want="$(echo "$label" | tr '[:lower:]' '[:upper:]')" \
          'toupper($2) == want { print $1; exit }'
}

get_ab_system_partition() {
    # System (root) partition for slot A or B. Label first, number fallback
    # (v3 layout: p5=SYSTEM-A, p6=SYSTEM-B).
    local slot="$1" part
    case "$slot" in
        A) part=$(ab_partition_by_label "SYSTEM-A"); echo "${part:-$(ab_partition_by_number 5)}" ;;
        B) part=$(ab_partition_by_label "SYSTEM-B"); echo "${part:-$(ab_partition_by_number 6)}" ;;
        *) return 1 ;;
    esac
}

get_ab_boot_partition() {
    # Boot (firmware) partition for slot A or B. Label first, number fallback
    # (v3 layout: p2=BOOT-A, p3=boot-b).
    local slot="$1" part
    case "$slot" in
        A) part=$(ab_partition_by_label "BOOT-A"); echo "${part:-$(ab_partition_by_number 2)}" ;;
        B) part=$(ab_partition_by_label "BOOT-B"); echo "${part:-$(ab_partition_by_number 3)}" ;;
        *) return 1 ;;
    esac
}

# Release channel of a version/tag, as RQB-releases.json names its streams
# (rq_update_check.sh, rq_ab_releases.sh):
#   beta-*                 -> beta
#   development-*, dev-*   -> dev    (feature-branch builds follow development)
#   anything else          -> stable (main releases are tagged v{version})
rq_release_channel() {
    case "$1" in
        beta-*)                echo beta ;;
        development-*|dev-*)   echo dev ;;
        *)                     echo stable ;;
    esac
}

# ============================================================================
# INITIALIZATION
# ============================================================================

debug "RasQberry common library loaded (v1.0)"
