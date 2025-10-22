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
    exit 1
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

# Update a variable in the environment file
# Usage: update_env_var "VARIABLE_NAME" "new_value"
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    local temp_file

    temp_file=$(mktemp) || die "Failed to create temp file"

    if grep -q "^${var_name}=" "$RQ_ENV_FILE"; then
        # Variable exists - update it
        sed "s|^${var_name}=.*|${var_name}=${var_value}|" "$RQ_ENV_FILE" > "$temp_file"
        sudo mv "$temp_file" "$RQ_ENV_FILE" || die "Failed to update $var_name"
    else
        # Variable doesn't exist - append it
        echo "${var_name}=${var_value}" | sudo tee -a "$RQ_ENV_FILE" > /dev/null || die "Failed to add $var_name"
    fi

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
show_yesno() {
    local title="$1"
    local text="$2"
    local height="${3:-12}"
    local width="${4:-65}"

    if command -v whiptail >/dev/null 2>&1; then
        whiptail --title "$title" --yesno "$text" "$height" "$width" 3>&1 1>&2 2>&3
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
    local height="${3:-10}"
    local width="${4:-60}"

    if command -v whiptail >/dev/null 2>&1; then
        whiptail --title "$title" --msgbox "$text" "$height" "$width" 3>&1 1>&2 2>&3
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

    debug "Clearing LEDs using: $led_script"
    python3 "$led_script" 2>/dev/null || warn "Failed to clear LEDs"
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
        sudo -u "$user_name" -H -- "$@"
    else
        "$@"
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
                su - "$user_name" -c "DISPLAY=${DISPLAY:-:0} $browser '$url' &" 2>/dev/null &
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

# Ask user to install demo with size info
# Usage: ask_demo_install "LED-Painter" "5MB" "500MB" || exit 0
ask_demo_install() {
    local demo_name="$1"
    local download_size="${2:-unknown}"
    local install_size="${3:-unknown}"

    local message="$demo_name is not installed yet.

Download: ~$download_size
Install size: ~$install_size

Requires internet connection.

Install now?"

    if show_yesno "$demo_name Not Installed" "$message" 14 65; then
        return 0
    else
        info "Installation cancelled by user"
        return 1
    fi
}

# Install demo using raspi-config nonint function
# Usage: install_demo_raspiconfig do_qlo_install || die "Install failed"
install_demo_raspiconfig() {
    local install_func="$1"

    if ! sudo raspi-config nonint "$install_func"; then
        return 1
    fi
}

# ============================================================================
# INITIALIZATION
# ============================================================================

debug "RasQberry common library loaded (v1.0)"
