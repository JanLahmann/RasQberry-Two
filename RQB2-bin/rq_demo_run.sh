#!/bin/bash
#
# rq_demo_run.sh - Universal RasQberry Demo Launcher
#
# Usage:
#   rq_demo_run.sh <demo-id> [variant]
#
# Description:
#   Reads demo manifest and launches the demo based on entrypoint.type.
#   Replaces individual launcher scripts with a unified approach.
#
# Demo Types Supported:
#   - jupyter:  Jupyter notebook server with browser
#   - docker:   Docker container with web interface
#   - browser:  Opens URL in browser (or delegates to launcher for local server)
#   - python:   Python script (GUI or LED-based)
#
# If entrypoint.launcher is specified, it serves as a fallback for any type.
#
# Examples:
#   rq_demo_run.sh fun-with-quantum       # Launch Fun with Quantum
#   rq_demo_run.sh led-demos ibm-logo     # Launch IBM Logo LED demo
#   rq_demo_run.sh grok-bloch-web         # Open Grok Bloch in browser
#
# Requires: jq
#

set -euo pipefail

# ============================================================================
# INITIALIZATION
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load environment
load_rqb2_env

# Find manifest directory
if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    MANIFEST_DIR="/usr/config/demo-manifests"
else
    MANIFEST_DIR="$(dirname "$SCRIPT_DIR")/RQB2-config/demo-manifests"
fi

# Tracking variables for cleanup
JUPYTER_PID=""
CONTAINER_NAME=""
HTTP_SERVER_PID=""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Check if jq is available
check_jq() {
    if ! command -v jq &>/dev/null; then
        die "jq is required but not installed. Install with: sudo apt-get install jq"
    fi
}

# Find an available port starting from the given port
find_available_port() {
    local port="${1:-8888}"

    while true; do
        # Check using lsof (most reliable on Raspberry Pi)
        if command -v lsof &>/dev/null; then
            if ! lsof -i ":$port" &>/dev/null; then
                echo "$port"
                return 0
            fi
        # Fallback to ss
        elif command -v ss &>/dev/null; then
            if ! ss -tuln 2>/dev/null | grep -q ":$port "; then
                echo "$port"
                return 0
            fi
        # Fallback to netstat
        elif command -v netstat &>/dev/null; then
            if ! netstat -tuln 2>/dev/null | grep -q ":$port "; then
                echo "$port"
                return 0
            fi
        else
            # No tool available, assume port is free
            echo "$port"
            return 0
        fi
        port=$((port + 1))
        # Safety limit
        if [ $port -gt 65535 ]; then
            die "Could not find available port"
        fi
    done
}

# Launch browser with URL
launch_browser() {
    local url="$1"

    if command -v chromium-browser &>/dev/null; then
        info "Opening browser..."
        run_as_user chromium-browser --password-store=basic "$url" &
    elif command -v firefox &>/dev/null; then
        info "Opening browser..."
        run_as_user firefox "$url" &
    else
        info "No browser found. Please open manually: $url"
    fi
}

# Wait for HTTP endpoint to become available
wait_for_http() {
    local url="$1"
    local max_wait="${2:-30}"
    local count=0

    while ! curl -sf "$url" >/dev/null 2>&1; do
        sleep 1
        count=$((count + 1))
        if [ $count -ge $max_wait ]; then
            return 1
        fi
    done
    return 0
}

# Get manifest field with default
get_field() {
    local field="$1"
    local default="${2:-}"
    local value
    value=$(jq -r "$field // \"$default\"" "$MANIFEST_FILE" 2>/dev/null)
    echo "$value"
}

# Get manifest field as boolean string ("true" or "false")
get_bool() {
    local field="$1"
    local default="${2:-false}"
    local value
    value=$(jq -r "$field // $default" "$MANIFEST_FILE" 2>/dev/null)
    if [ "$value" = "true" ]; then
        echo "true"
    else
        echo "false"
    fi
}

# ============================================================================
# REQUIREMENT CHECKS
# ============================================================================

check_requirements() {
    local display_req needs_leds needs_network

    display_req=$(get_field '.needs_hw.display' 'none')
    needs_leds=$(get_field '.needs_hw.leds' 'false')
    needs_network=$(get_field '.needs_hw.network' 'false')

    # Check display requirement
    case "$display_req" in
        required)
            if ! check_display; then
                die "This demo requires a display (DISPLAY not set)"
            fi
            ;;
        optional)
            check_display || warn "No display detected. Some features may not work."
            ;;
        none)
            # No display requirement
            ;;
    esac

    # Check LED hardware (just a warning, actual root check happens in run_python)
    if [ "$needs_leds" = "true" ]; then
        debug "Demo requires LED hardware"
    fi

    # Check network connectivity
    if [ "$needs_network" = "true" ]; then
        if ! ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
            warn "Network connectivity may be unavailable"
        fi
    fi
}

# Check if demo is installed
check_installed() {
    local marker_file working_dir preinstalled

    marker_file=$(get_field '.install.marker_file' '')
    working_dir=$(get_field '.entrypoint.working_dir' '')
    preinstalled=$(get_bool '.install.preinstalled' 'false')

    # If preinstalled, no check needed
    if [ "$preinstalled" = "true" ]; then
        return 0
    fi

    # Check marker file if specified
    if [ -n "$marker_file" ] && [ -n "$working_dir" ]; then
        local check_path="$USER_HOME/$REPO/demos/$working_dir/$marker_file"
        if [ ! -f "$check_path" ]; then
            return 1
        fi
    fi

    return 0
}

# Install demo from manifest
# Clones repo, applies patches, installs pip requirements
install_demo() {
    local repo_url working_dir patch_file pip_requirements
    local demo_dir patches_dir

    repo_url=$(get_field '.install.repo_url' '')
    working_dir=$(get_field '.entrypoint.working_dir' '')
    patch_file=$(get_field '.install.patch_file' '')
    pip_requirements=$(get_bool '.install.pip_requirements' 'false')

    if [ -z "$repo_url" ]; then
        die "No install.repo_url specified in manifest"
    fi

    if [ -z "$working_dir" ]; then
        die "No entrypoint.working_dir specified in manifest"
    fi

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"
    patches_dir="$USER_HOME/$REPO/RQB2-config/patches"

    # Create demos directory if needed
    mkdir -p "$USER_HOME/$REPO/demos"

    # Clone the repository
    info "Cloning demo from $repo_url..."
    if ! git clone "$repo_url" "$demo_dir"; then
        die "Failed to clone demo repository"
    fi

    # Apply patch if specified
    if [ -n "$patch_file" ] && [ -f "$patches_dir/$patch_file" ]; then
        info "Applying patch: $patch_file"
        cd "$demo_dir"
        if ! git apply "$patches_dir/$patch_file" 2>/dev/null; then
            # Try with -3 for 3-way merge
            if ! git apply -3 "$patches_dir/$patch_file" 2>/dev/null; then
                warn "Patch may not have applied cleanly: $patch_file"
            fi
        fi
    fi

    # Install pip requirements if specified
    if [ "$pip_requirements" = "true" ] && [ -f "$demo_dir/requirements.txt" ]; then
        info "Installing Python requirements..."
        activate_venv || warn "Could not activate venv for pip install"
        pip install -r "$demo_dir/requirements.txt" || warn "Some requirements may have failed"
    fi

    info "Demo installed successfully"
}

# Ensure demo is installed, auto-install if missing
ensure_installed() {
    if check_installed; then
        return 0
    fi

    # Check if we can auto-install
    local repo_url
    repo_url=$(get_field '.install.repo_url' '')

    if [ -z "$repo_url" ]; then
        die "Demo not installed and no install.repo_url specified. Please install via raspi-config or the RasQberry menu."
    fi

    info "Demo not installed. Auto-installing..."
    install_demo
}

# ============================================================================
# TYPE-SPECIFIC LAUNCHERS
# ============================================================================

# Jupyter notebook launcher
run_jupyter() {
    local working_dir port notebook demo_dir

    working_dir=$(get_field '.entrypoint.working_dir' '')
    port=$(get_field '.entrypoint.jupyter_port' '8888')
    notebook=$(get_field '.entrypoint.notebook' '')

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"

    if [ ! -d "$demo_dir" ]; then
        die "Demo directory not found: $demo_dir"
    fi

    # Activate virtual environment
    info "Activating Python virtual environment..."
    activate_venv || die "Failed to activate virtual environment"

    # Check if Jupyter is available
    if ! command -v jupyter &>/dev/null; then
        die "Jupyter is not installed. Please run the Qiskit installation first."
    fi

    # Find available port
    port=$(find_available_port "$port")
    info "Using port: $port"

    # Build Jupyter URL
    local jupyter_url
    if [ -n "$notebook" ]; then
        jupyter_url="http://127.0.0.1:${port}/notebooks/${notebook}"
    else
        jupyter_url="http://127.0.0.1:${port}/tree"
    fi

    # Change to demo directory
    cd "$demo_dir"

    # Start Jupyter notebook in background
    info "Starting Jupyter notebook server..."
    jupyter notebook \
        --no-browser \
        --port="$port" \
        --ip=127.0.0.1 \
        --NotebookApp.token='' \
        --NotebookApp.password='' \
        --NotebookApp.open_browser=False \
        2>&1 &
    JUPYTER_PID=$!

    # Wait for Jupyter to start
    info "Waiting for Jupyter to start..."
    sleep 3

    # Verify Jupyter is running
    if ! kill -0 "$JUPYTER_PID" 2>/dev/null; then
        die "Jupyter failed to start"
    fi

    echo
    echo "Jupyter URL: $jupyter_url"
    echo

    # Launch browser
    launch_browser "$jupyter_url"

    echo
    echo "============================================"
    echo "  Demo is running"
    echo "============================================"
    echo

    # Interactive wait if TTY available
    if [ -t 0 ]; then
        echo "Press Enter to stop the Jupyter server..."
        read -r
        info "Stopping Jupyter server..."
    else
        info "Jupyter server running in background (PID: $JUPYTER_PID)"
        wait "$JUPYTER_PID" 2>/dev/null || true
    fi
}

# Docker container launcher
run_docker() {
    local docker_image docker_port container_name

    docker_image=$(get_field '.entrypoint.docker_image' '')
    docker_port=$(get_field '.entrypoint.docker_port' '8080')
    container_name=$(get_field '.id' 'rasqberry-demo')

    if [ -z "$docker_image" ]; then
        die "No docker_image specified in manifest"
    fi

    # Check Docker is installed
    check_docker || die "Docker is not installed. Run docker-setup.sh first."

    # Check Docker group membership
    local user_name
    user_name=$(get_user_name)
    if ! groups "$user_name" | grep -q docker && [ "$user_name" != "root" ]; then
        die "User '$user_name' is not in the docker group. Run docker-setup.sh first."
    fi

    # Activate Docker group if not active
    if ! groups | grep -q docker && [ "$(whoami)" != "root" ]; then
        info "Docker group not active in current session"
        info "Activating Docker group permissions..."
        if [ -z "${DOCKER_GROUP_ACTIVATED:-}" ]; then
            export DOCKER_GROUP_ACTIVATED=1
            exec sg docker -c "$0 $DEMO_ID ${VARIANT:-}"
        fi
    fi

    CONTAINER_NAME="$container_name"

    # Stop any existing container
    info "Checking for existing containers..."
    if docker ps -q --filter name="$CONTAINER_NAME" 2>/dev/null | grep -q .; then
        info "Stopping existing container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
    fi
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    # Check if image exists
    if ! docker images -q "$docker_image" 2>/dev/null | grep -q .; then
        die "Docker image not found: $docker_image. Please build it first."
    fi

    # Find available port
    docker_port=$(find_available_port "$docker_port")

    # Start container
    info "Starting container: $CONTAINER_NAME"
    if ! docker run -d \
        --name "$CONTAINER_NAME" \
        --rm \
        -p "${docker_port}:${docker_port}" \
        "$docker_image"; then
        die "Failed to start Docker container"
    fi

    # Wait for container to start
    info "Waiting for container to start..."
    sleep 5

    # Verify container is running
    if ! docker ps --filter name="$CONTAINER_NAME" --filter status=running | grep -q "$CONTAINER_NAME"; then
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        die "Container failed to start"
    fi

    local url="http://127.0.0.1:${docker_port}"
    echo
    echo "Demo is running at: $url"
    echo

    # Launch browser
    launch_browser "$url"

    echo
    echo "============================================"
    echo "  Demo is running in Docker"
    echo "============================================"
    echo
    echo "To stop: docker stop $CONTAINER_NAME"
    echo

    # Interactive wait if TTY available
    if [ -t 0 ]; then
        echo "Press Enter to stop the container..."
        read -r
        info "Stopping container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
    fi
}

# Browser-only launcher (external URLs or local HTTP server)
run_browser_type() {
    local browser_url launcher

    browser_url=$(get_field '.entrypoint.browser_url' '')
    launcher=$(get_field '.entrypoint.launcher' '')

    # If browser_url is specified, just open it
    if [ -n "$browser_url" ]; then
        echo
        echo "Opening: $browser_url"
        echo
        launch_browser "$browser_url"
        return 0
    fi

    # If launcher is specified, delegate to it (e.g., local HTTP server demos)
    if [ -n "$launcher" ]; then
        delegate_launcher "$launcher"
        return 0
    fi

    die "No browser_url or launcher specified for browser type"
}

# Python script launcher
run_python() {
    local working_dir script launcher needs_leds demo_dir venv_python

    working_dir=$(get_field '.entrypoint.working_dir' '')
    script=$(get_field '.entrypoint.script' '')
    launcher=$(get_field '.entrypoint.launcher' '')
    needs_leds=$(get_field '.needs_hw.leds' 'false')

    # If no script specified, fallback to launcher
    if [ -z "$script" ]; then
        if [ -n "$launcher" ]; then
            delegate_launcher "$launcher"
            return 0
        fi
        die "No script or launcher specified for python type"
    fi

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"

    if [ ! -d "$demo_dir" ]; then
        die "Demo directory not found: $demo_dir"
    fi

    # Find venv
    local venv_path
    venv_path=$(find_venv "$STD_VENV") || die "Virtual environment not found"
    venv_python="$venv_path/bin/python3"

    # Change to demo directory
    cd "$demo_dir"

    # LED demos require root for GPIO access
    if [ "$needs_leds" = "true" ]; then
        # Re-exec with sudo if needed
        if [ "$(id -u)" != "0" ]; then
            info "LED/GPIO operations require root access"
            info "Re-executing with sudo..."
            exec sudo -E DISPLAY="${DISPLAY:-:0}" "$0" "$DEMO_ID" "${VARIANT:-}"
        fi

        info "Running with LED support (as root)..."
        "$venv_python" -W ignore::DeprecationWarning "$script"
    else
        # Regular Python script, run as user
        info "Running Python script..."
        run_as_user "$venv_python" "$script"
    fi
}

# Delegate to existing launcher script
# Used as fallback when type-specific handler can't run directly
delegate_launcher() {
    local launcher="${1:-}"

    if [ -z "$launcher" ]; then
        launcher=$(get_field '.entrypoint.launcher' '')
    fi

    if [ -z "$launcher" ]; then
        die "No launcher specified"
    fi

    # Find the launcher script
    local launcher_path=""
    if [ -f "$SCRIPT_DIR/$launcher" ]; then
        launcher_path="$SCRIPT_DIR/$launcher"
    elif [ -f "/usr/bin/$launcher" ]; then
        launcher_path="/usr/bin/$launcher"
    else
        die "Launcher script not found: $launcher"
    fi

    info "Delegating to: $launcher"
    exec "$launcher_path"
}

# ============================================================================
# VARIANT HANDLING
# ============================================================================

# Get variant-specific field, falling back to main manifest
get_variant_field() {
    local variant_id="$1"
    local field="$2"
    local default="${3:-}"
    local value

    # Try variant-specific field first
    value=$(jq -r ".variants[] | select(.id == \"$variant_id\") | $field // null" "$MANIFEST_FILE" 2>/dev/null)

    if [ "$value" = "null" ] || [ -z "$value" ]; then
        # Fall back to main manifest
        value=$(get_field "$field" "$default")
    fi

    echo "$value"
}

# Run variant using its specific entrypoint
run_variant() {
    local variant_id="$1"
    local launcher

    # Get variant-specific launcher
    launcher=$(jq -r ".variants[] | select(.id == \"$variant_id\") | .entrypoint.launcher // null" "$MANIFEST_FILE" 2>/dev/null)

    if [ "$launcher" = "null" ] || [ -z "$launcher" ]; then
        die "Variant '$variant_id' has no launcher specified"
    fi

    # Find and run the launcher
    local launcher_path=""
    if [ -f "$SCRIPT_DIR/$launcher" ]; then
        launcher_path="$SCRIPT_DIR/$launcher"
    elif [ -f "/usr/bin/$launcher" ]; then
        launcher_path="/usr/bin/$launcher"
    else
        die "Launcher script not found: $launcher"
    fi

    info "Running variant '$variant_id' via: $launcher"
    exec "$launcher_path"
}

# ============================================================================
# CLEANUP
# ============================================================================

cleanup() {
    debug "Running cleanup..."

    # Stop Jupyter if running
    if [ -n "$JUPYTER_PID" ] && kill -0 "$JUPYTER_PID" 2>/dev/null; then
        info "Stopping Jupyter server..."
        kill "$JUPYTER_PID" 2>/dev/null || true
        wait "$JUPYTER_PID" 2>/dev/null || true
    fi

    # Stop HTTP server if running
    if [ -n "$HTTP_SERVER_PID" ] && kill -0 "$HTTP_SERVER_PID" 2>/dev/null; then
        info "Stopping HTTP server..."
        kill "$HTTP_SERVER_PID" 2>/dev/null || true
    fi

    # Note: Docker containers are not stopped here - they use --rm and stop on their own
    # or user explicitly stops them
}

# ============================================================================
# MAIN
# ============================================================================

usage() {
    cat << 'EOF'
Usage: rq_demo_run.sh <demo-id> [variant]

Launch a RasQberry demo by reading its manifest.

Arguments:
  demo-id    The demo identifier (e.g., fun-with-quantum, led-demos)
  variant    Optional variant for demos with multiple modes (e.g., ibm-logo)

Examples:
  rq_demo_run.sh fun-with-quantum       # Launch Fun with Quantum notebooks
  rq_demo_run.sh quantum-mixer          # Launch Quantum Mixer Docker demo
  rq_demo_run.sh grok-bloch-web         # Open Grok Bloch in browser
  rq_demo_run.sh led-demos ibm-logo     # Run IBM Logo LED demo

Available demos can be found in: /usr/config/demo-manifests/

EOF
}

main() {
    check_jq

    # Parse arguments
    if [ $# -lt 1 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        usage
        exit 0
    fi

    DEMO_ID="$1"
    VARIANT="${2:-}"

    # Find manifest file
    MANIFEST_FILE="$MANIFEST_DIR/rq_demo_${DEMO_ID}.json"
    if [ ! -f "$MANIFEST_FILE" ]; then
        die "Manifest not found: $MANIFEST_FILE"
    fi

    # Get demo info
    local demo_name entrypoint_type
    demo_name=$(get_field '.name' "$DEMO_ID")
    entrypoint_type=$(get_field '.entrypoint.type' '')

    echo
    echo "=== $demo_name ==="
    echo

    # Setup cleanup trap
    trap cleanup EXIT INT TERM

    # Check requirements
    check_requirements

    # Ensure demo is installed (auto-install if possible)
    ensure_installed

    # Handle variants
    if [ -n "$VARIANT" ]; then
        # Check variant exists
        local variant_exists
        variant_exists=$(jq -r ".variants[] | select(.id == \"$VARIANT\") | .id // null" "$MANIFEST_FILE" 2>/dev/null)
        if [ "$variant_exists" = "null" ] || [ -z "$variant_exists" ]; then
            die "Unknown variant: $VARIANT"
        fi
        run_variant "$VARIANT"
        exit 0
    fi

    # Dispatch based on entrypoint type
    # If a launcher is specified, it can be used as fallback for any type
    local launcher
    launcher=$(get_field '.entrypoint.launcher' '')

    case "$entrypoint_type" in
        jupyter)
            run_jupyter
            ;;
        docker)
            run_docker
            ;;
        browser)
            run_browser_type
            ;;
        python)
            run_python
            ;;
        ""|script)
            # No type or legacy "script" type - delegate to launcher
            if [ -n "$launcher" ]; then
                delegate_launcher "$launcher"
            else
                die "No entrypoint.type or entrypoint.launcher specified in manifest"
            fi
            ;;
        *)
            # Unknown type - try launcher fallback
            if [ -n "$launcher" ]; then
                warn "Unknown type '$entrypoint_type', delegating to launcher"
                delegate_launcher "$launcher"
            else
                die "Unknown entrypoint type: $entrypoint_type"
            fi
            ;;
    esac
}

main "$@"
