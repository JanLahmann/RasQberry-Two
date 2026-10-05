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
#   - Browser: rq_open_browser, rq_show_url, open_browser
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

# Clear all LEDs (--close-window: also close the on-screen view)
# Usage: clear_leds [--close-window]
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
    "$py" "$led_script" "$@" 2>/dev/null || warn "Failed to clear LEDs"
}

# ----------------------------------------------------------------------------
# Who holds the LED panel (R-103, R-148, R-162)
# ----------------------------------------------------------------------------
# A demo left running (an icon, an earlier menu session, the IP scroll at
# start-up) keeps the panel. On a Pi 5 the next LED program then fails with
# "GPIO busy"; on a Pi 4 the PWM driver claims nothing, so the next one draws
# over the first without any error (R-162). STOP and Clear LEDs used to report
# success either way (R-148).
#
# The devices: /dev/pio0 and /dev/gpiochip* (Pi 5), /dev/mem and /dev/gpiomem
# (the Pi 4 PWM driver maps both), /dev/spidev0.0 (the retired SPI driver).
# Needs root to see other users' processes.

# A short name for a holder's command line: the demo's name as the menus
# show it, not its script (#31: "rq_led_ibm_logo.py")
_rq_led_holder_label() {
    case "$1" in
        *rq_display_ip.py*)      echo "the IP address scroll at start-up" ;;
        *rq_led_renderer.py*)    echo "the LED renderer service" ;;
        *rq_led_wizard_probe.py*|*rq_led_setup_wizard*) echo "the LED setup wizard" ;;
        *lights_out.py*)         echo "Quantum Lights Out" ;;
        *QuantumRaspberryTie*)   echo "Quantum Raspberry Tie" ;;
        *RasQ-LED*)              echo "RasQ-LED Demo" ;;
        *rq_demo_loop*)          echo "the demo loop" ;;
        *rq_led_ibm_logo.py*|*rq_led_ibm_demo.sh*) echo "IBM LED Demo" ;;
        *rq_led_simpletest.py*)  echo "Simple LED Demo" ;;
        *rq_test_leds.py*)       echo "Quick LED Test" ;;
        *rq_led_test.py*|*rq_led_test.sh*) echo "LED Test & Diagnostics" ;;
        *demo_led_*|*rq_led_logo.py*|*rq_led_display_text*|*rq_led_display_logo*)
                                 echo "Text & Logo Display" ;;
        *LED_painter.py*|*rq_led_painter*) echo "LED-Painter" ;;
        *turn_off_LEDs.py*)      echo "turning the LEDs off" ;;
        *)
            # the script it runs: the demo whose manifest names it, else the
            # script; else the program
            local word name
            for word in $1; do
                case "$word" in
                    *.py|*.sh)
                        name=$(_rq_demo_name_of_script "$(basename "$word")") || name=$(basename "$word")
                        echo "$name"
                        return 0 ;;
                esac
            done
            # shellcheck disable=SC2086
            set -- $1
            basename "${1:-unknown}"
            ;;
    esac
}

# The name of the demo whose manifest runs SCRIPT (its entrypoint script or a
# launcher, also a variant's): catalogue demos and demos added later
_rq_demo_name_of_script() {
    local script="$1" file name
    command -v jq >/dev/null 2>&1 || return 1
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        name=$(jq -r --arg s "$script" '
            if ([.entrypoint.script, .entrypoint.launcher,
                 (.variants // [] | .[] | .entrypoint.launcher, .entrypoint.script)]
                | index($s)) != null then .name else empty end' "$file" 2>/dev/null) || continue
        [ -n "$name" ] && { echo "$name"; return 0; }
    done < <(rq_list_manifests "$(rq_shipped_manifest_dir)" 2>/dev/null)
    return 1
}

# The calling process and its parents: never a holder to stop
_rq_led_self_chain() {
    local pid=$$ n=0
    while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null && [ "$n" -lt 30 ]; do
        printf ' %s' "$pid"
        pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
        n=$((n + 1))
    done
    printf ' '
}

# Usage: holders=$(led_holders)   ->  "PID label" per line, nothing if free
led_holders() {
    local dev pids="" pid args self
    self=$(_rq_led_self_chain)
    for dev in /dev/pio0 /dev/gpiochip* /dev/gpiomem /dev/mem /dev/spidev0.0; do
        [ -e "$dev" ] || continue
        pids="$pids $(fuser "$dev" 2>/dev/null || true)"
    done
    # shellcheck disable=SC2086
    for pid in $(printf '%s\n' $pids | grep -E '^[0-9]+$' | sort -un); do
        case "$self" in *" $pid "*) continue ;; esac
        args=$(ps -o args= -p "$pid" 2>/dev/null) || continue
        [ -n "$args" ] || continue
        # In service mode the renderer IS the panel's driver, not a rival
        if [ "${LED_RENDER_MODE:-direct}" = "service" ]; then
            case "$args" in *rq_led_renderer.py*) continue ;; esac
        fi
        echo "$pid $(_rq_led_holder_label "$args")"
    done
}

# Stop the holders listed by led_holders (one "PID label" per line). A
# RasQberry service is stopped through systemd, so it does not restart.
# Usage: stop_led_holders "$holders"
stop_led_holders() {
    local pid unit waited=0 left=""
    while read -r pid _; do
        [ -n "$pid" ] || continue
        unit=$(ps -o unit= -p "$pid" 2>/dev/null | tr -d ' ' || true)
        case "$unit" in
            rasqberry-*.service) systemctl stop "$unit" 2>/dev/null || kill "$pid" 2>/dev/null || true ;;
            *) kill "$pid" 2>/dev/null || true ;;
        esac
    done <<< "$1"
    while [ "$waited" -lt 30 ]; do
        left=""
        while read -r pid _; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then left="$left $pid"; fi
        done <<< "$1"
        [ -z "$left" ] && break
        sleep 0.1
        waited=$((waited + 1))
    done
    # shellcheck disable=SC2086
    [ -z "$left" ] || { kill -9 $left 2>/dev/null || true; sleep 0.5; }
    # The stopped demo's launcher clears the panel as it ends (its exit trap)
    # and holds it for a moment: wait for that. A clear started meanwhile
    # failed with "GPIO busy" (Pi 5) or drew over it (Pi 4) - item 30.
    waited=0
    while [ -n "$(led_holders)" ] && [ "$waited" -lt 50 ]; do
        sleep 0.2
        waited=$((waited + 1))
    done
}

# Before an LED demo: if another program holds the panel, name it and offer to
# stop it. Returns 1 when it keeps running - then do not start the demo.
# Without a terminal it only warns and returns 0 (as before).
# Usage: led_panel_ready || exit 0
led_panel_ready() {
    local holders
    holders=$(led_holders)
    [ -n "$holders" ] || return 0
    if ! { [ -t 0 ] && [ -t 1 ]; }; then
        warn "The LED panel is in use by: $(echo "$holders" | cut -d' ' -f2- | paste -sd, -)"
        return 0
    fi
    if whiptail --title "LED Panel in Use" --yes-button "Stop It" --no-button "Cancel" --yesno \
"Another program is using the LED panel:

$(echo "$holders" | sed 's/^[0-9]* /  /')

Stop it and continue?" $(( $(echo "$holders" | wc -l) + 10 )) 70; then
        stop_led_holders "$holders"
        return 0
    fi
    return 1
}

# An LED layout id (LED_LAYOUT) in plain words, for what the person reads
# (#29: "Saved: LED_LAYOUT = quad-4x12" was a variable name). The wizard names
# a flipped kit layout <id>-flipy/-flipx/-rot180 and its own one custom-WxH.
# Usage: rq_led_layout_name quad-4x12   ->  four 4x12 panels
rq_led_layout_name() {
    local id="$1" base turn=""
    case "$id" in
        *-flipy)  base="${id%-flipy}";  turn=", mounted upside down" ;;
        *-flipx)  base="${id%-flipx}";  turn=", mounted mirrored" ;;
        *-rot180) base="${id%-rot180}"; turn=", rotated 180°" ;;
        *)        base="$id" ;;
    esac
    case "$base" in
        single-24x8)   echo "one 24x8 panel$turn" ;;
        quad-4x12)     echo "four 4x12 panels$turn" ;;
        quad-2x2-12x4) echo "four 4x12 panels, mounted upside down" ;;
        triple-8x8)    echo "three 8x8 panels$turn" ;;
        single-8x32)   echo "one 32x8 panel$turn" ;;
        custom-*)      echo "your own layout (${base#custom-})$turn" ;;
        "")            echo "not set" ;;
        *)             echo "$id" ;;
    esac
}

# Run a command so that it finishes even if this script is killed: when a
# demo's window is closed, script(1) (rq_hold_on_error.sh) asks the demo to
# stop and kills it 2 s later. A cleanup that took longer - stopping a
# container, clearing the LEDs on a Pi 4 - was cut off (item 33). Waits for
# the command as long as this script lives. Quiet: the terminal may be gone.
# Usage: rq_run_detached COMMAND [ARGS...]
rq_run_detached() {
    if command -v setsid >/dev/null 2>&1; then
        setsid -w "$@" </dev/null >/dev/null 2>&1 &
        wait $! 2>/dev/null || true
    else
        "$@" </dev/null >/dev/null 2>&1 || true
    fi
}

# Clear the panel and say nothing: for exit traps, where the terminal may
# already be gone (a closed window) and any output would fail. The demo has
# ended, so the on-screen LED view it opened closes too (R-100), unless
# RQ_LED_KEEP_WINDOW=1: the demo loop keeps one view for all its demos.
led_clear_quietly() {
    local py="python3" venv script close="--close-window"
    script=$(find_led_script "turn_off_LEDs.py") || return 0
    if venv=$(find_venv 2>/dev/null) && [ -x "$venv/bin/python3" ]; then
        py="$venv/bin/python3"
    fi
    [ "${RQ_LED_KEEP_WINDOW:-}" = "1" ] && close=""
    rq_run_detached env PYTHONDONTWRITEBYTECODE=1 \
        PYTHONPATH="$(dirname "$script")${PYTHONPATH:+:$PYTHONPATH}" "$py" "$script" ${close:+"$close"}
}

# Stop and remove a container, to the end even if this script is killed
# (see rq_run_detached)
rq_docker_stop_detached() {
    rq_run_detached bash -c '. "$1" && rq_docker_stop "$2"' _ "$_RQ_COMMON_DIR/rq_common.sh" "$1"
}

# The Pi's throttling bits now (vcgencmd get_throttled, e.g. 0x50000), or
# nothing when they cannot be read. Read when an LED demo starts, so that the
# stall check after it counts only what is new (#6).
rq_throttled() {
    command -v vcgencmd >/dev/null 2>&1 || return 0
    vcgencmd get_throttled 2>/dev/null | sed -n 's/^throttled=//p' | head -1
}

# After an LED demo: if the Pi 5's LED driver stalled during it (a power
# supply too weak for the LEDs, item 31), say so and offer a lower brightness.
# Only with a terminal to ask on.
# Usage: rq_led_stall_check START_EPOCH [THROTTLED_AT_START]
rq_led_stall_check() {
    [ -t 0 ] && [ -t 1 ] || return 0
    "$_RQ_COMMON_DIR/rq_led_brightness.sh" --after-stall "${1:-0}" "${2:-}" 2>/dev/null || true
}

# An LED launcher clears the panel once when it ends, however it ends: Enter,
# Ctrl+C, a closed window (HUP) or a stop from the menu (TERM). The signals
# only end the script; the EXIT trap clears. A closed window (R-158) left the
# panel lit when a launcher exec'd its demo or trapped only some signals.
# Usage: rq_led_clear_on_exit
rq_led_clear_on_exit() {
    RQ_LED_RUN_START=$(date +%s)
    RQ_LED_THROTTLED_START=$(rq_throttled)
    trap '_rq_led_on_exit' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
}

_rq_led_on_exit() {
    local rc=$?
    # A closed window ends script(1) too, and the hangup that follows must not
    # cut this short
    trap '' HUP INT TERM
    # the demo first, or it draws on while the panel is cleared
    rq_stop_demo_child
    led_clear_quietly
    [ "$rc" = 129 ] || rq_led_stall_check "${RQ_LED_RUN_START:-0}" "${RQ_LED_THROTTLED_START:-}"
}

# ----------------------------------------------------------------------------
# Stopping a demo: one rule for all (items 5, 33)
# ----------------------------------------------------------------------------
# Every demo window stops its demo the same way: Enter or Ctrl+C, or closing
# the window - from a desktop icon and from the RasQberry menu (also over SSH).
# A program that does not read Enter itself runs through rq_run_demo, which
# reads it for it (items 4, 8). Only a demo that needs the keyboard (a text
# prompt, e.g. Raspberry Tie asking for an IBM Quantum key) stops with Ctrl+C
# or by closing the window. Docker demos stop with their window too; only the
# Workshop & Qiskit Server keeps running by design.

# Usage: rq_stop_hint NAME [keys]
rq_stop_hint() {
    if [ "${2:-}" = "keys" ]; then
        echo "To stop $1: press Ctrl+C or close this window."
    else
        echo "To stop $1: press Enter or Ctrl+C, or close this window."
    fi
    # The demo's browser window opened maximised over this one (#15)
    [ -z "${_RQ_DEMO_TABS[*]:-}" ] || echo "$RQ_BROWSER_BACK_HINT"
}

# Chromium opens maximised (#15), over the window that started it: where
# that window is now, under a stop line or a "Press Enter" line
RQ_BROWSER_BACK_HINT="The browser covers this window: to get back here, click it in the taskbar."

# Is process PID still there (not a zombie)? Works for children started
# through sudo, where kill -0 fails with "not permitted".
_rq_pid_alive() {
    case "$(ps -o stat= -p "$1" 2>/dev/null)" in
        ""|Z*) return 1 ;;
    esac
    return 0
}

# Show the stop hint and wait until Enter, or until the demo ends by itself
# (PID, or the Docker container named after --container). Ctrl+C and a closed
# window end the calling script through its traps. Without a terminal there
# is nobody to press Enter: wait for the PID (if any) and return.
# Usage: rq_wait_for_stop NAME [PID | --container CONTAINER]
rq_wait_for_stop() {
    local name="$1" pid="" container="" rc
    case "${2:-}" in
        --container) container="${3:-}" ;;
        *) pid="${2:-}" ;;
    esac
    if ! [ -t 0 ]; then
        if [ -n "$pid" ]; then wait "$pid" 2>/dev/null || true; fi
        return 0
    fi
    echo
    rq_stop_hint "$name"
    while :; do
        if [ -n "$pid" ]; then _rq_pid_alive "$pid" || return 0; fi
        if [ -n "$container" ]; then rq_docker_running "$container" || return 0; fi
        rc=0
        read -r -t 2 _ || rc=$?
        [ "$rc" -eq 0 ] && return 0      # Enter
        [ "$rc" -gt 128 ] || return 0    # no more input
    done
}

# The processes PID started, and theirs (one per line)
_rq_descendants() {
    local c
    for c in $(pgrep -P "$1" 2>/dev/null); do
        echo "$c"
        _rq_descendants "$c"
    done
}

# Stop PID and what it started: SIGTERM (a Python demo then runs its own
# cleanup, e.g. Fractals closes its browser window), SIGKILL after SECONDS
# (default 5). Quiet: no "Killed jupyter-lab" line for a child of this shell
# (#27). Usage: rq_stop_pid PID [SECONDS]
rq_stop_pid() {
    local pid="$1" secs="${2:-5}" kids k left
    [ -n "$pid" ] || return 0
    if _rq_pid_alive "$pid"; then
        kids=$(_rq_descendants "$pid")
        kill -TERM "$pid" 2>/dev/null || sudo -n kill -TERM "$pid" 2>/dev/null || true
        _rq_wait_gone "$secs" "$pid"
        # what it started and left behind (e.g. the program a shell function
        # ran), then whatever does not stop
        for k in $kids; do
            _rq_pid_alive "$k" && { kill -TERM "$k" 2>/dev/null || sudo -n kill -TERM "$k" 2>/dev/null || true; }
        done
        # shellcheck disable=SC2086
        _rq_wait_gone "$secs" $kids
        left=""
        for k in "$pid" $kids; do
            _rq_pid_alive "$k" && left="$left $k"
        done
        # shellcheck disable=SC2086
        [ -z "$left" ] || { kill -KILL $left || sudo -n kill -KILL $left; } 2>/dev/null || true
    fi
    { wait "$pid"; } 2>/dev/null || true
}

# Wait up to SECONDS until none of the PIDs runs any more
_rq_wait_gone() {
    local secs="$1" n=0 k busy
    shift
    while [ "$n" -lt $((secs * 10)) ]; do
        busy=""
        for k in "$@"; do
            _rq_pid_alive "$k" && { busy=1; break; }
        done
        [ -n "$busy" ] || return 0
        sleep 0.1
        n=$((n + 1))
    done
    return 0
}

# Lines on a demo's error output that look like faults but are none (#27):
# Qt finds the runtime directory "0770 instead of 0700" because Raspberry Pi
# OS's VNC server gives it an ACL; the group has no access all the same.
_RQ_HARMLESS_STDERR='^QStandardPaths: wrong permissions on runtime directory '

# Run a command without those lines on its error output; everything else
# stays. Usage: rq_quiet_stderr COMMAND [ARGS...]
rq_quiet_stderr() {
    "$@" 2> >(grep -Ev --line-buffered "$_RQ_HARMLESS_STDERR" >&2)
}

# The demo program rq_run_demo runs (for the exit traps)
RQ_DEMO_CHILD=""

# Stop the program rq_run_demo started, if it still runs. For exit traps:
# the demo first, then its LEDs, server or container.
rq_stop_demo_child() {
    [ -n "${RQ_DEMO_CHILD:-}" ] || return 0
    local pid="$RQ_DEMO_CHILD"
    RQ_DEMO_CHILD=""
    rq_stop_pid "$pid"
}

# Run a demo program in this window so that Enter stops it as well as Ctrl+C
# or closing the window (items 4, 8). Quantum Lights Out, Raspberry Tie,
# Fractals, LED-Painter, LED Test and catalogue programs do not read Enter
# themselves: the program runs in the background with no keyboard (its input
# is empty), and this window reads Enter. Prints the stop line first. Ctrl+C,
# a closed window or a stop from the menu (INT, HUP, TERM) stop the program
# and end the script with 130, 129 or 143, so its EXIT trap clears the LEDs
# or stops the server. A background program ignores Ctrl+C itself, so a
# Python demo ends without a KeyboardInterrupt traceback (#13). Without a
# terminal (the demo loop, a menu run without a window) the program simply
# runs. Returns its exit status, or 0 when Enter stopped it.
# Usage: rq_run_demo NAME COMMAND [ARGS...]
rq_run_demo() {
    local name="$1" rc=0 old_hup old_int old_term
    shift
    if ! { [ -t 0 ] && [ -t 1 ]; }; then
        "$@" || rc=$?
        return "$rc"
    fi
    rq_stop_hint "$name"
    echo
    old_hup=$(trap -p HUP)
    old_int=$(trap -p INT)
    old_term=$(trap -p TERM)
    trap 'rq_stop_demo_child; exit 129' HUP
    trap 'rq_stop_demo_child; exit 130' INT
    trap 'rq_stop_demo_child; exit 143' TERM
    "$@" </dev/null &
    RQ_DEMO_CHILD=$!
    # until Enter (or no more input: Ctrl+D), or the program ends by itself
    while _rq_pid_alive "$RQ_DEMO_CHILD"; do
        rc=0
        read -r -t 2 _ || rc=$?
        [ "$rc" -gt 128 ] || break
    done
    rc=0
    if _rq_pid_alive "$RQ_DEMO_CHILD"; then
        rq_stop_demo_child               # Enter: stopped, not an error
    else
        { wait "$RQ_DEMO_CHILD"; } 2>/dev/null || rc=$?
        RQ_DEMO_CHILD=""
    fi
    eval "${old_hup:-trap - HUP}"
    eval "${old_int:-trap - INT}"
    eval "${old_term:-trap - TERM}"
    return "$rc"
}

# A Docker demo started in a window stops with it (item 33): Enter, Ctrl+C or
# closing the window stops the container. All four used to keep running after
# their windows were gone - on a 2 GB Pi 4 too. Without a terminal it keeps
# running; RasQberry menu > Quantum Demos > Stop Docker demos stops it.
# Usage: rq_docker_stop_with_window CONTAINER NAME
rq_docker_stop_with_window() {
    if ! { [ -t 0 ] && [ -t 1 ]; }; then
        info "$2 keeps running in the background. To stop it: RasQberry menu > Quantum Demos > Stop Docker demos."
        return 0
    fi
    RQ_WINDOW_CONTAINER="$1"
    RQ_WINDOW_NAME="$2"
    trap '_rq_window_container_stop' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    rq_wait_for_stop "$2" --container "$1"
    _rq_window_container_stop
    trap - EXIT HUP INT TERM
}

# Quietly where needed: after a closed window, writing to it fails.
_rq_window_container_stop() {
    [ -n "${RQ_WINDOW_CONTAINER:-}" ] || return 0
    # The hangup that follows a closed window must not cut the stop short:
    # the container was stopped but left behind
    trap '' HUP INT TERM
    local name="$RQ_WINDOW_CONTAINER"
    RQ_WINDOW_CONTAINER=""
    { info "Stopping $RQ_WINDOW_NAME..."; } 2>/dev/null || true
    rq_close_demo_tabs
    rq_docker_stop_detached "$name"
    { info "$RQ_WINDOW_NAME stopped."; } 2>/dev/null || true
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
        # ss first: it sees every listening socket, lsof run as the user misses
        # root-owned ones (docker-proxy), so a "free" port could be taken (R-109)
        if command -v ss &>/dev/null; then
            if ! ss -tuln 2>/dev/null | grep -q ":$port "; then echo "$port"; return 0; fi
        elif command -v lsof &>/dev/null; then
            if ! lsof -i ":$port" &>/dev/null; then echo "$port"; return 0; fi
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
    if command -v ss &>/dev/null; then
        ss -tuln 2>/dev/null | grep -q ":$port "
    elif command -v lsof &>/dev/null; then
        lsof -i ":$port" &>/dev/null
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
        # Technical detail: only with RQ_DEBUG=1 (R-133)
        debug "LED/GPIO operations require root access; re-executing with sudo"
        exec sudo -E "$0" "$@"
    fi
}

# ============================================================================
# 11. BROWSER LAUNCHING
# ============================================================================

# Longest wait (seconds) for the browser command to hand its address over
RQ_BROWSER_HANDOFF_WAIT="${RQ_BROWSER_HANDOFF_WAIT:-10}"

# The browser command on this Pi; fails if there is none
_rq_find_browser() {
    local b
    for b in chromium-browser chromium firefox xdg-open; do
        if command -v "$b" >/dev/null 2>&1; then
            echo "$b"
            return 0
        fi
    done
    return 1
}

# Open URL in the desktop user's browser, so that the tab outlives the demo
# window that opened it. Extra arguments are Chromium flags
# (--start-fullscreen). Prints nothing; returns 1 when there is no browser.
#
# A demo window is a terminal session (lxterminal; script(1) under
# rq_hold_on_error.sh). A command started there with & stays in the
# terminal's foreground process group, and the kernel sends that group SIGHUP
# when the session leader ends - under rq_hold_on_error.sh, the demo itself -
# and when the window closes. Composer and Grok Bloch online end right after
# starting `chromium-browser URL`, so in a window of their own (an icon
# running rq_demo_run.sh) the hangup killed it before it had handed the
# address to the running Chromium: no tab. And a Chromium that a demo had
# started itself (none was running) closed, all tabs, with the demo's window.
# So the browser command gets a session of its own (setsid): no terminal, and
# no process group that a closed window or a demo's cleanup reaches - those
# still stop the demo's own server, LEDs and containers. This then waits until
# the command has handed the address over and exited, at most
# RQ_BROWSER_HANDOFF_WAIT seconds (a browser it had to start keeps running).
#
# A demo served on this Pi (http://127.0.0.1:PORT, http://localhost:PORT)
# opens in a Chromium window of its own, on top of the demo's terminal and
# maximised, or full screen with --start-fullscreen (#15; a running Chromium
# ignores that flag, so rq_browser_tab.py sets it). Its tab closes when the
# demo's server stops - at once through rq_close_demo_tabs, else as soon as
# the server is gone - instead of staying behind with "Dead kernel" and
# asking "Leave site?" when closed (#9). Websites (Composer) open as before.
# Usage: rq_open_browser URL [CHROMIUM_FLAGS...]
rq_open_browser() {
    local url="$1" browser pid user_name ticks=0 before="" state=""
    local -a cmd
    shift
    browser=$(_rq_find_browser) || return 1
    case "$browser" in
        chromium*)
            if _rq_local_demo_url "$url"; then
                before=$(_rq_browser_tab ids 2>/dev/null) || before=""
                state=maximized
                case " $* " in *" --start-fullscreen "*|*" --kiosk "*) state=fullscreen ;; esac
                cmd=("$browser" --password-store=basic --new-window "$@" "$url")
            else
                cmd=("$browser" --password-store=basic "$@" "$url")
            fi
            ;;
        *)  cmd=("$browser" "$url") ;;
    esac
    # As the desktop user, as run_as_user does. sudo goes inside setsid: it
    # passes the signals it gets on to the browser.
    user_name=$(get_user_name)
    if [ "$(id -u)" = "0" ] && [ "$user_name" != "root" ]; then
        cmd=(sudo -u "$user_name" -H DISPLAY="${DISPLAY:-:0}" -- "${cmd[@]}")
    fi
    if command -v setsid >/dev/null 2>&1; then
        # -w: should setsid have to fork (as a process group leader), $! still
        # ends with the browser command
        setsid -w "${cmd[@]}" </dev/null >/dev/null 2>&1 &
    else
        nohup "${cmd[@]}" </dev/null >/dev/null 2>&1 &
    fi
    pid=$!
    while _rq_pid_alive "$pid" && [ "$ticks" -lt $((RQ_BROWSER_HANDOFF_WAIT * 5)) ]; do
        sleep 0.2
        ticks=$((ticks + 1))
    done
    _rq_pid_alive "$pid" || wait "$pid" 2>/dev/null || true
    if [ -n "$state" ]; then
        _RQ_DEMO_TABS+=("$url")
        _rq_browser_tab_watch --before "$before" --window-state "$state" "$url"
    fi
    return 0
}

# Is URL a demo served on this Pi (its tab is of no use once the demo stops)?
_rq_local_demo_url() {
    case "$1" in
        http://127.0.0.1:[0-9]*|http://localhost:[0-9]*) return 0 ;;
    esac
    return 1
}

# The demo-tab helper (Chromium's DevTools port, 127.0.0.1 only)
_rq_browser_tab() {
    python3 "$_RQ_COMMON_DIR/rq_browser_tab.py" "$@"
}

# Look after a demo's new tab in the background, in a session of its own: it
# outlives the demo's window and closes the tab once the server has stopped
_rq_browser_tab_watch() {
    if command -v setsid >/dev/null 2>&1; then
        setsid python3 "$_RQ_COMMON_DIR/rq_browser_tab.py" watch "$@" </dev/null >/dev/null 2>&1 &
    else
        nohup python3 "$_RQ_COMMON_DIR/rq_browser_tab.py" watch "$@" </dev/null >/dev/null 2>&1 &
    fi
    disown "$!" 2>/dev/null || true
}

# The addresses of the demo tabs this script opened
_RQ_DEMO_TABS=()

# Close the tabs this script's demo opened, before its server stops, so they
# do not show "Dead kernel" or "Connection failed" first (#9). Quiet, and
# nothing without the DevTools port. Usage: rq_close_demo_tabs
rq_close_demo_tabs() {
    local u
    for u in ${_RQ_DEMO_TABS[@]+"${_RQ_DEMO_TABS[@]}"}; do
        _rq_browser_tab close "$u" </dev/null >/dev/null 2>&1 || true
    done
    _RQ_DEMO_TABS=()
}

# Open URL in available browser (see rq_open_browser), or say where to go
# Usage: open_browser "http://localhost:8080"
open_browser() {
    if _rq_find_browser >/dev/null; then
        info "Opening the browser..."
        rq_open_browser "$1"
        return 0
    fi
    warn "No browser found. Please open manually: $1"
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
    local docker=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --docker) docker=1; shift ;;
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
    [ "$docker" = 1 ] && text="${text}$(_rq_docker_space_note)"
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

# Is / one slot of an A/B card? (RQ_TEST_AB=1/0 in tests)
_rq_root_is_ab_slot() {
    if [ -n "${RQ_TEST_AB:-}" ]; then [ "$RQ_TEST_AB" = 1 ]; return; fi
    case "$(lsblk -no LABEL "$(findmnt -no SOURCE / 2>/dev/null)" 2>/dev/null)" in
        SYSTEM-A|SYSTEM-B|system-a|system-b) return 0 ;;
    esac
    return 1
}

# Size of the root file system in whole GB (RQ_TEST_ROOT_GB in tests)
_rq_root_size_gb() {
    if [ -n "${RQ_TEST_ROOT_GB:-}" ]; then echo "$RQ_TEST_ROOT_GB"; return; fi
    df -P -k / 2>/dev/null | awk 'NR == 2 { printf "%d\n", $2 / 1000000 }'
}

# Extra lines under "Space:" for a Docker demo (item 32): the images live in
# the running system, so on an A/B card each slot keeps its own and an update
# downloads them again; a 16 GB card fits one Docker demo.
# Prints dialog text with literal \n, like the rest of the consent text.
_rq_docker_space_note() {
    local gb
    if _rq_root_is_ab_slot; then
        printf '%s' "           Docker images stay in this system's slot: after an\n"
        printf '%s' "           update into the other slot they download again.\n"
    fi
    gb=$(_rq_root_size_gb)
    case "$gb" in ''|*[!0-9]*) gb=0 ;; esac
    if [ "$gb" -gt 0 ] && [ "$gb" -lt 20 ]; then
        printf '%s' "           A 16 GB card has room for one Docker demo (not the\n"
        printf '%s' "           Workshop & Qiskit Server).\n"
    fi
    return 0
}

# The IBM Quantum content (Qiskit/documentation, demos/ibm-quantum-learning)
# holds only what the demos use (#18). A checkout made before also held every
# file at the top of the repository (package.json, tox.ini ...), which the
# notebooks' file browser showed first: narrow it, with no download (the
# files are in the clone). The same list as clone_ibm_learning_content in
# RQB2_menu.sh.
# Usage: rq_ibm_learning_tidy DIR
RQ_IBM_LEARNING_PATHS="/docs/tutorials/ /docs/guides/hello-world.ipynb /learning/courses/ /LICENSE /LICENSE-DOCS"
rq_ibm_learning_tidy() {
    [ -f "$1/package.json" ] && [ -d "$1/.git" ] || return 0
    # shellcheck disable=SC2086  # one pattern per word
    git -C "$1" sparse-checkout set --no-cone $RQ_IBM_LEARNING_PATHS >/dev/null 2>&1 || true
    return 0
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
    local docker_opt=""
    if [ "$type" = "docker" ] && [ -n "$image" ]; then
        docker_opt="--docker"
        path="/var/lib/docker"
        [ -n "$what" ] || what="Docker image ($image)"
        [ -n "$url" ] || url=$(rq_image_registry_url "$image")
    fi
    [ -n "$url" ] || url="${repo:-https://github.com}"
    rq_confirm_download "$name" "$dl" "$disk" --what "$what" --time "$time" \
        --path "$path" --peak "$peak" --url "$url" $docker_opt || return $?
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

# Before scripts that mount partitions (the slot update): mount prints
# "(hint) your fstab has been modified, but systemd still uses the old
# version" for EVERY mount when /etc/fstab is newer than systemd's last
# reload - which happens when the clock was behind at start-up (no RTC battery,
# NTP not there yet). One reload ends it (H-34: the hint appeared twice).
rq_refresh_fstab_view() {
    local loaded=/run/systemd/systemd-units-load
    [ -e /etc/fstab ] && [ -e "$loaded" ] || return 0
    if [ /etc/fstab -nt "$loaded" ]; then
        systemctl daemon-reload >/dev/null 2>&1 || true
    fi
    return 0
}

# Release channel (stream) of a version/tag, as RQB-releases.json names its
# streams. The one shell copy of the rule: rq_slot_manager.sh plan-update
# (Jan's guard), rq_slot_status.sh, rq_update_check.sh and rq_ab_releases.sh
# use it; rq_release_notice.py has the Python copy, and
# tests/unit/data/plan_update_cases.json tests both.
#   beta-*                    -> beta
#   development-*, dev-*      -> dev     (feature-branch builds follow development)
#   v1.2.3, 1.2.3, stable-*   -> stable  (main releases are tagged v{version})
#   anything else             -> unknown (never stable: it ranks like dev and
#                                         takes its updates from dev)
rq_release_channel() {
    case "$1" in
        beta-*)                    echo beta ;;
        development-*|dev-*)       echo dev ;;
        v[0-9]*|[0-9]*|stable-*)   echo stable ;;
        *)                         echo unknown ;;
    esac
}

# The channel an image takes its updates from: its own; an image of no known
# channel (a version file of any other name, or none) follows dev
rq_update_channel() {
    local channel
    channel=$(rq_release_channel "$1")
    [ "$channel" = "unknown" ] && channel=dev
    echo "$channel"
}

# Release controls (#242): rasqberry.org/RQB-release-controls.json maps a
# release tag to {"notify_after", "rollout", "withdrawn", "reason"}. Only
# "withdrawn" matters to the shell tools: the update check and the release
# picker do not offer a withdrawn release. No file (404), no network or a
# broken file all mean: nothing is withdrawn.
# Environment (tests): RQ_RELEASE_CONTROLS_FILE, RQ_RELEASE_CONTROLS_URL; a
# release list read from a file (RQ_RELEASES_FILE, RQ_GITHUB_RELEASES_FILE)
# never goes online for the controls either
rq_release_controls() {
    local json=""
    if [ -n "${RQ_RELEASE_CONTROLS_FILE:-}" ]; then
        json=$(cat "$RQ_RELEASE_CONTROLS_FILE" 2>/dev/null || true)
    elif [ -n "${RQ_RELEASES_FILE:-}${RQ_GITHUB_RELEASES_FILE:-}" ]; then
        json='{}'
    else
        json=$(curl -fsSL --max-time 10 \
            "${RQ_RELEASE_CONTROLS_URL:-https://rasqberry.org/RQB-release-controls.json}" 2>/dev/null || true)
    fi
    # jq 1.6 (Raspberry Pi OS) reports success for EMPTY input even with -e,
    # so a missing file (404, offline) must be caught before jq sees it
    if [ -n "$json" ] && printf '%s' "$json" | jq -e 'type == "object"' >/dev/null 2>&1; then
        printf '%s\n' "$json"
    else
        echo '{}'
    fi
}

# rq_release_withdrawn TAG [CONTROLS_JSON]: prints the reason (or "no reason
# given") and returns 0 when TAG was withdrawn, else returns 1
rq_release_withdrawn() {
    local json="${2:-}" reason
    [ -n "$json" ] || json=$(rq_release_controls)
    [ -n "$json" ] || return 1
    # decide on the printed reason, not jq's exit status: jq 1.6 says
    # "success" for empty input even with -e
    reason=$(printf '%s' "$json" | jq -r --arg t "$1" '
        (if (.releases | type) == "object" then .releases else . end)[$t]
        | select(type == "object" and .withdrawn == true)
        | (.reason // "" | if . == "" then "no reason given" else . end)' 2>/dev/null) || return 1
    [ -n "$reason" ] || return 1
    printf '%s\n' "$reason"
}

# ============================================================================
# 16. DEMO VERSIONS: release pins and the user's updates (Jan, Q8/Q32)
# ============================================================================
# Every downloaded demo is pinned per RasQberry release: a git commit
# (install.ref, or install.source.ref for a demo with its own installer) and/or
# a Docker image digest (entrypoint.docker_image "repo@sha256:..."). "Update
# demos" (rq_demo_update.sh) moves a demo to a newer upstream version on
# request. That choice is kept in demos/.demo-versions, one line per pin:
#   ID:image|ID:ref <TAB> RELEASE_PIN <TAB> CHOSEN <TAB> LABEL
# It holds only while the release still ships the pin it replaced: a newer
# RasQberry release brings a newer tested pin, and that one wins.

rq_demo_versions_file() {
    echo "${USER_HOME:-$HOME}/${REPO:-RasQberry-Two}/demos/.demo-versions"
}

# Manifest file of a demo (the given one, else the shipped/user search path)
_rq_demo_mf() {
    if [ -n "${2:-}" ]; then echo "$2"; return 0; fi
    rq_find_manifest "$(rq_shipped_manifest_dir)" "$1"
}

# The version chosen for KEY while the release pin is PIN; non-zero if none
_rq_demo_chosen() {
    local f
    f=$(rq_demo_versions_file)
    [ -f "$f" ] || return 1
    awk -F'\t' -v k="$1" -v p="$2" '$1 == k && $2 == p && $3 != "" { v = $3 }
        END { if (v == "") exit 1; print v }' "$f" 2>/dev/null
}

# Label of the chosen version for KEY (e.g. "bc4229e-jupyter, 2026-10-02")
rq_demo_chosen_label() {
    local f
    f=$(rq_demo_versions_file)
    [ -f "$f" ] || return 1
    awk -F'\t' -v k="$1" '$1 == k { v = $4 } END { if (v == "") exit 1; print v }' "$f" 2>/dev/null
}

# The Docker image a demo runs: its release pin, or the newer version chosen
# under "Update demos". Empty for a demo without an image.
# Usage: image=$(rq_demo_image doqumentation [MANIFEST])
rq_demo_image() {
    local mf pin
    mf=$(_rq_demo_mf "$1" "${2:-}") || return 0
    pin=$(jq -r '.entrypoint.docker_image // empty' "$mf" 2>/dev/null)
    [ -n "$pin" ] || return 0
    _rq_demo_chosen "$1:image" "$pin" || echo "$pin"
}

# The git commit a demo installs (install.ref or install.source.ref), likewise
rq_demo_ref() {
    local mf pin
    mf=$(_rq_demo_mf "$1" "${2:-}") || return 0
    pin=$(jq -r '.install.ref // .install.source.ref // empty' "$mf" 2>/dev/null)
    [ -n "$pin" ] || return 0
    _rq_demo_chosen "$1:ref" "$pin" || echo "$pin"
}

# The git repository a demo installs from (install.repo_url or install.source)
rq_demo_repo() {
    local mf
    mf=$(_rq_demo_mf "$1" "${2:-}") || return 0
    jq -r '.install.repo_url // .install.source.repo_url // empty' "$mf" 2>/dev/null
}

# Record (or, with an empty CHOSEN, drop) a newer version for KEY.
# Usage: rq_demo_set_version "doqumentation:image" RELEASE_PIN CHOSEN LABEL
rq_demo_set_version() {
    local key="$1" pin="$2" chosen="${3:-}" label="${4:-}" f tmp
    f=$(rq_demo_versions_file)
    mkdir -p "$(dirname "$f")" || return 1
    tmp="$f.tmp.$$"
    {
        if [ -f "$f" ]; then awk -F'\t' -v k="$key" '$1 != k' "$f"; fi
        if [ -n "$chosen" ]; then printf '%s\t%s\t%s\t%s\n' "$key" "$pin" "$chosen" "$label"; fi
    } > "$tmp" && mv "$tmp" "$f" || { rm -f "$tmp"; return 1; }
    fix_root_ownership "$f" >/dev/null 2>&1 || true
}

# Where new and less-tested demos ask for feedback (a GitHub issue form)
RQ_FEEDBACK_URL="https://github.com/JanLahmann/RasQberry-Two/issues/new?template=demo-feedback.yml"

# Echo "beta" for a new or less-tested demo (field "maturity"), else nothing.
# The variant's value wins, then the manifest's, then the catalogue entry's
# (known-demos.json), so a catalogue demo installed before it was marked
# shows it too.
# Usage: [ -n "$(rq_demo_maturity ID [MANIFEST] [VARIANT])" ]
rq_demo_maturity() {
    local id="$1" variant="${3:-}" mf m="" registry
    if mf=$(_rq_demo_mf "$id" "${2:-}") && [ -f "$mf" ]; then
        [ -n "$variant" ] && m=$(jq -r --arg v "$variant" \
            '.variants[]? | select(.id == $v) | .maturity // empty' "$mf" 2>/dev/null)
        [ -n "$m" ] || m=$(jq -r '.maturity // empty' "$mf" 2>/dev/null)
    fi
    registry="$(dirname "$(rq_shipped_manifest_dir)")/known-demos.json"
    if [ -z "$m" ] && [ -f "$registry" ]; then
        m=$(jq -r --arg id "$id" '.demos[]? | select(.id == $id) | .maturity // empty' \
            "$registry" 2>/dev/null)
    fi
    [ "$m" = "beta" ] && echo beta
    return 0
}

# The invitation at the start of a beta demo.
# Usage: rq_beta_notice DEMO_ID
rq_beta_notice() {
    echo "This demo is new - please try it and tell us what works and what doesn't."
    echo "Your feedback helps a lot (needs a free GitHub account): ${RQ_FEEDBACK_URL}&demo=$1"
    echo
}

# How a demo start came, for its usage count: RQ_DEMO_HOW from the caller
# (rq_hold_on_error.sh for desktop icons, rq_learning_paths.sh, the demo loop),
# else the RasQberry menu when its error file is set (run_engine_demo), else
# nothing (a terminal, SSH)
rq_demo_start_how() {
    if [ -n "${RQ_DEMO_HOW:-}" ]; then
        echo "$RQ_DEMO_HOW"
    elif [ -n "${RQ_ERROR_FILE:-}" ]; then
        echo menu
    fi
}

# Anonymous usage count for the project's statistics (rq_umami_event.py; no
# IDs): in the background, so the caller never waits, and it never fails.
# RQ_UMAMI=0 sends nothing (the rig tests set it).
# Usage: rq_count_event demo-start ID[:VARIANT] [HOW]
#        rq_count_event learning-path ID start|finish
rq_count_event() {
    local sender="$_RQ_COMMON_DIR/rq_umami_event.py"
    [ "${RQ_UMAMI:-}" != "0" ] && [ -f "$sender" ] && command -v python3 >/dev/null 2>&1 || return 0
    if command -v setsid >/dev/null 2>&1; then
        ( PYTHONDONTWRITEBYTECODE=1 setsid python3 "$sender" "$@" </dev/null >/dev/null 2>&1 & ) 2>/dev/null || true
    else
        ( PYTHONDONTWRITEBYTECODE=1 python3 "$sender" "$@" </dev/null >/dev/null 2>&1 & ) 2>/dev/null || true
    fi
    return 0
}

# ============================================================================
# 17. DOCKER DEMO HELPERS (doQumentation, Quantum Lab, Qoffee-Maker, Mixer)
# ============================================================================

# Make docker usable in this script. The user is in the docker group from the
# image build; a session older than that membership is re-run with it (sg).
# Usage: rq_docker_access "$@"
rq_docker_access() {
    check_docker || die "Docker is not installed (the image may be misbuilt)."
    local user_name
    user_name=$(get_user_name)
    if [ "$user_name" != "root" ] && ! id -nG "$user_name" 2>/dev/null | grep -qw docker; then
        die "User '$user_name' is not in the docker group (the image may be misbuilt)."
    fi
    if [ "$(id -u)" != "0" ] && ! id -nG | grep -qw docker && [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
        export DOCKER_GROUP_ACTIVATED=1
        exec sg docker -c "$(printf '%q ' "$0" "$@")"
    fi
    docker ps >/dev/null 2>&1 \
        || die "Docker does not answer: $(docker ps 2>&1 | tail -1)"
}

# Is the container running?
rq_docker_running() {
    [ "$(docker container inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]
}

# Stop and remove a container, and wait until it is really gone: docker stop
# returns before --rm has removed it, and a docker run with the same name then
# failed with "Conflict" and left no server at all (R-145).
# Usage: rq_docker_stop NAME [TIMEOUT_S]
rq_docker_stop() {
    local name="$1" n=0
    docker stop "$name" >/dev/null 2>&1 || true
    docker rm -f "$name" >/dev/null 2>&1 || true
    while docker container inspect "$name" >/dev/null 2>&1; do
        [ "$n" -ge "${2:-30}" ] && return 1
        sleep 1
        n=$((n + 1))
    done
    return 0
}

# Why a container failed: keep its log (the containers no longer run with
# --rm, so `docker logs` still works, R-109), show the end, then die.
# Usage: rq_docker_fail NAME "message"
rq_docker_fail() {
    local name="$1" msg="$2" log
    log="${USER_HOME:-$HOME}/.cache/rasqberry/${name}.log"
    mkdir -p "$(dirname "$log")" 2>/dev/null || true
    if docker logs "$name" > "$log" 2>&1; then
        fix_root_ownership "$log" >/dev/null 2>&1 || true
        echo
        echo "Last lines of the $name log (all of it: $log):"
        tail -15 "$log"
    fi
    die "$msg"
}

# MB received so far on the network (not lo or Docker's own interfaces), for
# a download's progress line. Empty when it cannot be told. RQ_NET_DIR: tests.
# Usage: mb=$(rq_rx_mb)
rq_rx_mb() {
    local f n sum=0 any=""
    for f in "${RQ_NET_DIR:-/sys/class/net}"/*/statistics/rx_bytes; do
        [ -r "$f" ] || continue
        n=${f%/statistics/rx_bytes}; n=${n##*/}
        case "$n" in lo|docker*|br-*|veth*|virbr*) continue ;; esac
        sum=$((sum + $(cat "$f" 2>/dev/null || echo 0)))
        any=1
    done
    [ -z "$any" ] || echo $((sum / 1000000))
}

# The progress line of rq_docker_pull, every 2 s while shell PARENT runs
# Usage: _rq_pull_progress NAME DOWNLOAD_MB PARENT &
_rq_pull_progress() {
    local name="$1" mb="$2" parent="$3" start=$SECONDS rx0 now got
    rx0=$(rq_rx_mb) || rx0=""
    while kill -0 "$parent" 2>/dev/null; do
        got=""
        if [ -n "$rx0" ] && now=$(rq_rx_mb) && [ -n "$now" ]; then
            got=$((now - rx0))
            case "$mb" in
                ''|*[!0-9]*|0) got="$got MB, " ;;
                *) if [ "$got" -le "$mb" ]; then got="$got of about $mb MB, "; else got="$got MB, "; fi ;;
            esac
        fi
        printf '\rDownloading %s ... %s%ds   ' "$name" "$got" $((SECONDS - start))
        sleep 2
    done
}

# Download an image. In a terminal one line shows the MB received so far
# ("Downloading traQmania ... 120 of about 530 MB, 45s") instead of Docker's
# list of layers (#23); on failure Docker's own reason, not "check your
# internet connection" (R-038).
# Usage: rq_docker_pull IMAGE "Name" [DOWNLOAD_MB]
rq_docker_pull() {
    local image="$1" name="${2:-$1}" mb="${3:-}" err rc=0 why printer start
    err=$(mktemp)
    if [ -t 1 ]; then
        start=$SECONDS
        # The line comes from a helper beside the pull, which stays in the
        # foreground so that Ctrl+C stops it; the helper ends with this shell
        _rq_pull_progress "$name" "$mb" "${BASHPID:-$$}" &
        printer=$!
        docker pull -q "$image" > /dev/null 2> "$err" || rc=$?
        kill "$printer" 2>/dev/null || true
        wait "$printer" 2>/dev/null || true
        printf '\rDownloading %s ... %s                         \n' "$name" \
            "$([ "$rc" -eq 0 ] && echo "done ($((SECONDS - start))s)" || echo failed)"
    else
        info "Downloading $name: $image"
        docker pull -q "$image" > /dev/null 2> "$err" || rc=$?
    fi
    why=$(grep -v '^[[:space:]]*$' "$err" | tail -2 | tr '\n' ' ') || why=""
    rm -f "$err"
    [ "$rc" -eq 0 ] && return 0
    case "$why" in
        *"no space left"*)
            die "Not enough free space for $name. Remove demos you do not use (Quantum Demos > Remove a demo) and try again." ;;
        *"manifest unknown"*|*"not found"*|*"denied"*)
            die "The registry does not offer $image (any more): $why" ;;
        *)
            die "Could not download $name: ${why:-docker pull failed}" ;;
    esac
}

# After a new version is there, remove the other versions of the same image
# that no container uses (a release with a new pin, or "Update demos", would
# otherwise keep every old version on the SD card).
# Usage: rq_docker_drop_old IMAGE_IN_USE
rq_docker_drop_old() {
    local keep="$1" repo keep_id id
    repo="${keep%%@*}"
    case "${repo##*/}" in *:*) repo="${repo%:*}" ;; esac
    keep_id=$(docker image inspect -f '{{.Id}}' "$keep" 2>/dev/null) || return 0
    for id in $(docker images --no-trunc -q "$repo" 2>/dev/null | sort -u); do
        [ "$id" = "$keep_id" ] && continue
        docker image rm "$id" >/dev/null 2>&1 \
            && info "Removed an older version of $repo"
    done
    return 0
}

# The name other computers reach this Pi by: the one avahi announces. When
# another device on the network has <hostname>.local already, avahi calls
# this Pi <hostname>-2.local (R-063), and <hostname>.local reaches the other
# one (#3). rq_remote_access.sh mdns uses it too; rq_display_ip.py does the same.
# Usage: name=$(rq_mdns_name)
rq_mdns_name() {
    local fqdn="" t=""
    if command -v busctl >/dev/null 2>&1; then
        command -v timeout >/dev/null 2>&1 && t="timeout 3"
        fqdn=$($t busctl --system call org.freedesktop.Avahi / \
            org.freedesktop.Avahi.Server GetHostNameFqdn 2>/dev/null) || fqdn=""
        fqdn=$(printf '%s\n' "$fqdn" | sed -n 's/^s "\(.*\)"$/\1/p')
    fi
    echo "${fqdn:-$(hostname 2>/dev/null).local}"
}

# Open URL in the desktop user's browser (rq_open_browser: the tab stays when
# the demo's window closes) - or, without a screen (an SSH session), say how
# to reach it from another computer (Jan, Q19). PORT is the
# Pi-side port behind URL, for an ssh -L tunnel to a server on 127.0.0.1.
# Usage: rq_show_url URL [PORT]
rq_show_url() {
    local url="$1" port="${2:-}"
    if check_display; then
        if _rq_find_browser >/dev/null; then
            info "Opening the browser..."
            rq_open_browser "$url"
        else
            info "No browser found. Open this address: $url"
        fi
        return 0
    fi
    echo
    echo "No screen in this session, so no browser opens here."
    if [ -n "$port" ]; then
        echo "To use the demo from your computer:"
        echo "  1. On your computer, run:"
        echo "       ssh -N -L ${port}:127.0.0.1:${port} $(get_user_name)@$(rq_mdns_name)"
        echo "  2. Open in its browser:"
        echo "       $(printf '%s' "$url" | sed 's#//127\.0\.0\.1:#//localhost:#')"
    else
        echo "Open this address: $url"
    fi
    echo
}

# ============================================================================
# INITIALIZATION
# ============================================================================

debug "RasQberry common library loaded (v1.0)"
