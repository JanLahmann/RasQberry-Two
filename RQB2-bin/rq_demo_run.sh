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
#   - web-static: Serves a static dir over http.server (as user) + browser
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

# Find manifest and patches directories
if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    MANIFEST_DIR="/usr/config/demo-manifests"
    PATCHES_DIR="/usr/config/demo-patches"
else
    MANIFEST_DIR="$(dirname "$SCRIPT_DIR")/RQB2-config/demo-manifests"
    PATCHES_DIR="$(dirname "$SCRIPT_DIR")/RQB2-config/demo-patches"
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

# find_available_port() / port_in_use() now live in rq_common.sh (section 8b),
# shared with the standalone docker launchers so all demos allocate distinct
# host ports.

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

# Variant-aware field lookup: the selected variant's value wins, the main
# manifest is the fallback. Variants use the same paths as the manifest
# (.entrypoint.launcher, .needs_hw.display, ...) relative to the variant object.
demo_field() {
    local field="$1"
    local default="${2:-}"
    local value=""

    if [ -n "${VARIANT:-}" ]; then
        value=$(jq -r ".variants[] | select(.id == \"$VARIANT\") | $field // empty" "$MANIFEST_FILE" 2>/dev/null)
    fi
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        value=$(get_field "$field" "$default")
    fi
    echo "$value"
}

# Script arguments, one per line. Variants carry args at their top level
# (.variants[].args), the main manifest under .entrypoint.args.
get_demo_args() {
    if [ -n "${VARIANT:-}" ]; then
        local vargs
        vargs=$(jq -r ".variants[] | select(.id == \"$VARIANT\") | (.args // [])[]" "$MANIFEST_FILE" 2>/dev/null)
        if [ -n "$vargs" ]; then
            printf '%s\n' "$vargs"
            return 0
        fi
    fi
    jq -r '(.entrypoint.args // [])[]' "$MANIFEST_FILE" 2>/dev/null
}

# ============================================================================
# REQUIREMENT CHECKS
# ============================================================================

check_requirements() {
    local display_req needs_leds needs_network

    display_req=$(demo_field '.needs_hw.display' 'none')
    needs_leds=$(demo_field '.needs_hw.leds' 'false')
    needs_network=$(demo_field '.needs_hw.network' 'false')

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
    local repo_url ref working_dir patch_file pip_requirements
    local post_install installed_flag
    local demo_dir

    repo_url=$(get_field '.install.repo_url' '')
    ref=$(get_field '.install.ref' '')
    working_dir=$(get_field '.entrypoint.working_dir' '')
    patch_file=$(get_field '.install.patch_file' '')
    pip_requirements=$(get_bool '.install.pip_requirements' 'false')
    post_install=$(get_field '.install.post_install' '')
    installed_flag=$(get_field '.install.installed_flag' '')

    if [ -z "$repo_url" ]; then
        die "No install.repo_url specified in manifest"
    fi

    if [ -z "$working_dir" ]; then
        die "No entrypoint.working_dir specified in manifest"
    fi

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"

    # Create demos directory if needed (keep it user-owned when run as root)
    mkdir -p "$USER_HOME/$REPO/demos"
    fix_root_ownership "$USER_HOME/$REPO/demos"

    # Acquire the sources.
    #
    # A manifest that pins install.ref gets exactly that upstream commit, via the
    # same fetch_pinned_repo() primitive the external-demo registry uses. This
    # matters most for the demos we PATCH: a patch is written against specific
    # lines of a specific upstream version, so tracking a moving HEAD lets an
    # unrelated upstream commit break our install (the patch then fails to apply
    # and the demo refuses to run). Pinning makes installs reproducible and puts
    # us in control of when upstream changes are taken.
    #
    # Unpinned manifests keep the old behaviour (track the default branch).
    if [ -n "$ref" ]; then
        info "Fetching pinned commit ${ref} ..."
        # fetch_pinned_repo git-inits in place, so hand it a clean destination
        # (a previous partial/failed checkout may be lying around).
        [ -d "$demo_dir" ] && rm -rf "$demo_dir"
        fetch_pinned_repo "$repo_url" "$ref" "$demo_dir" \
            || die "Failed to fetch pinned commit $ref for demo '$DEMO_ID'"
    else
        # clone_demo cleans up partial clones and fixes ownership
        clone_demo "$repo_url" "$demo_dir"
    fi

    # Apply patch if specified.
    #
    # A patch failure is fatal: running a demo unpatched silently ships broken
    # behaviour (a corrupt patch went unnoticed for months precisely because
    # this only warned). If a manifest declares a patch_file it must exist and
    # apply cleanly.
    if [ -n "$patch_file" ]; then
        if [ ! -f "$PATCHES_DIR/$patch_file" ]; then
            die "Patch file declared in the manifest but not found: $PATCHES_DIR/$patch_file (demo '$DEMO_ID')"
        fi
        info "Applying patch: $patch_file"
        cd "$demo_dir"
        # Upstream repos sometimes ship CRLF and/or trailing whitespace (e.g.
        # KPRoche/quantum-raspberry-tie v8_0), which makes an LF patch's context
        # fail to match and git apply reject every hunk. Normalize the files this
        # patch targets (strip CR + trailing whitespace) first — Python is
        # line-ending agnostic, so this is safe and keeps our patches robust to
        # upstream whitespace drift. Our patches are generated against the same
        # normalization (see RQB2-config/demo-patches/).
        grep '^+++ b/' "$PATCHES_DIR/$patch_file" | sed 's|^+++ b/||' | while IFS= read -r _pf; do
            [ -f "$_pf" ] && sed -i 's/\r$//; s/[[:blank:]]*$//' "$_pf"
        done
        if ! git apply "$PATCHES_DIR/$patch_file" 2>/dev/null; then
            # Try with -3 for 3-way merge
            if ! git apply -3 "$PATCHES_DIR/$patch_file" 2>/dev/null; then
                die "Failed to apply patch '$patch_file' for demo '$DEMO_ID' (tried plain and 3-way git apply). Refusing to run the demo unpatched."
            fi
        fi
    fi

    # Install pip requirements if specified (as the user, into the user's venv)
    if [ "$pip_requirements" = "true" ] && [ -f "$demo_dir/requirements.txt" ]; then
        info "Installing Python requirements..."
        local venv_path
        if venv_path=$(find_venv "$STD_VENV"); then
            run_as_user "$venv_path/bin/pip" install -r "$demo_dir/requirements.txt" \
                || warn "Some requirements may have failed"
        else
            warn "Virtual environment not found - skipping pip requirements"
        fi
    fi

    # git apply run as root recreates files root-owned even inside a
    # user-owned tree, and fix_root_ownership only checks the top-level
    # owner - chown the whole tree unconditionally when running as root
    if [ "$(id -u)" = "0" ]; then
        local owner
        owner=$(get_user_name)
        [ "$owner" != "root" ] && chown -R "$owner:$owner" "$demo_dir"
    fi

    # Optional post-install step. Some demos need setup after the checkout before
    # they are usable - and for those the marker_file is GENERATED here rather
    # than shipped by upstream (e.g. quantum-paradoxes' WELCOME.ipynb), so the
    # demo would look permanently "not installed" without this.
    #
    # Contract: install.post_install names a RasQberry script (resolved next to
    # this launcher, else /usr/bin) run as `<script> --path <demo_dir>` with the
    # venv python, as the user.
    if [ -n "$post_install" ]; then
        local post_script="" venv_path
        if [ -f "$SCRIPT_DIR/$post_install" ]; then
            post_script="$SCRIPT_DIR/$post_install"
        elif [ -f "/usr/bin/$post_install" ]; then
            post_script="/usr/bin/$post_install"
        else
            die "install.post_install script not found: $post_install (demo '$DEMO_ID')"
        fi
        info "Running post-install: $post_install"
        if venv_path=$(find_venv "$STD_VENV"); then
            run_as_user "$venv_path/bin/python3" "$post_script" --path "$demo_dir" \
                || die "Post-install step failed for demo '$DEMO_ID': $post_install"
        else
            die "Virtual environment not found - cannot run post-install for '$DEMO_ID'"
        fi
    fi

    # Record the demo as installed in the environment file. The raspi-config menu
    # reads these *_INSTALLED flags, so the manifest path must set them too or its
    # view of what is installed drifts from reality.
    if [ -n "$installed_flag" ]; then
        update_env_var "$installed_flag" "true" \
            || warn "Could not set $installed_flag in the environment file"
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

    working_dir=$(demo_field '.entrypoint.working_dir' '')
    port=$(demo_field '.entrypoint.jupyter_port' '8888')
    notebook=$(demo_field '.entrypoint.notebook' '')

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"

    if [ ! -d "$demo_dir" ]; then
        die "Demo directory not found: $demo_dir"
    fi

    # Locate Jupyter in the virtual environment
    local venv_path jupyter_bin
    venv_path=$(find_venv "$STD_VENV") || die "Virtual environment not found"
    jupyter_bin="$venv_path/bin/jupyter"
    if [ ! -x "$jupyter_bin" ]; then
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

    # Start Jupyter notebook in background (as the user, not root)
    info "Starting Jupyter notebook server..."
    run_as_user "$jupyter_bin" notebook \
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
    local docker_image docker_port container_name launcher

    # A dedicated launcher wins over the generic docker path (pull, ports,
    # volumes, tokens are demo-specific — e.g. qoffee-maker.sh,
    # rq_quantum_lab.sh). External demos cannot set launcher (forbidden by
    # the external manifest rules), so they always take the generic path.
    launcher=$(demo_field '.entrypoint.launcher' '')
    if [ -n "$launcher" ]; then
        delegate_launcher "$launcher"
        return 0
    fi

    docker_image=$(get_field '.entrypoint.docker_image' '')
    docker_port=$(get_field '.entrypoint.docker_port' '8080')
    container_name=$(get_field '.id' 'rasqberry-demo')

    if [ -z "$docker_image" ]; then
        die "No docker_image specified in manifest"
    fi

    # Check Docker is installed
    check_docker || die "Docker is not installed (the image may be misbuilt)."

    # Check Docker group membership
    local user_name
    user_name=$(get_user_name)
    if ! groups "$user_name" | grep -q docker && [ "$user_name" != "root" ]; then
        die "User '$user_name' is not in the docker group (the image may be misbuilt)."
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

    # Check if image exists locally; pull from the registry if it is absent.
    # Registry-backed demos (e.g. the QuBins Quantum Lab) ship no local image
    # and must be pulled on first run. Locally-built images (e.g. quantum-mixer)
    # are already present, so this pull is skipped entirely and their build
    # path stays untouched. If a pull is attempted but fails (image not on a
    # registry, offline, etc.) we fall back to the original "build it first"
    # error. run_docker() uses plain info/die messages (no whiptail dialogs),
    # so progress is reported with info.
    if ! docker images -q "$docker_image" 2>/dev/null | grep -q .; then
        info "Docker image not found locally: $docker_image"
        info "Attempting to pull from registry (this may take a while)..."
        if ! docker pull "$docker_image"; then
            die "Docker image not found: $docker_image. Please build it first."
        fi
    fi

    # Find an available HOST port. The container-side port stays at the
    # manifest's docker_port — images serve on a fixed internal port, so a
    # bumped host port must still map onto it (host:host would dangle).
    local host_port
    host_port=$(find_available_port "$docker_port")

    # Start container
    info "Starting container: $CONTAINER_NAME"
    if ! docker run -d \
        --name "$CONTAINER_NAME" \
        --rm \
        -p "${host_port}:${docker_port}" \
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

    local url="http://127.0.0.1:${host_port}"
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

    browser_url=$(demo_field '.entrypoint.browser_url' '')
    launcher=$(demo_field '.entrypoint.launcher' '')

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

# Static web launcher (declarative; no per-demo launcher script)
#
# Serves a directory inside the demo checkout over http.server AS THE USER,
# then opens the browser. Refuses to start if the port is already in use
# (never takes over another process's port). The server is torn down via the
# EXIT/INT/TERM cleanup trap when the browser/demo session ends.
run_web_static() {
    local working_dir serve_dir port demo_dir abs_serve url

    working_dir=$(demo_field '.entrypoint.working_dir' '')
    serve_dir=$(demo_field '.entrypoint.serve_dir' '')
    port=$(demo_field '.entrypoint.port' '')

    [ -n "$working_dir" ] || die "No entrypoint.working_dir specified for web-static type"
    [ -n "$port" ] || die "No entrypoint.port specified for web-static type"
    case "$port" in
        ''|*[!0-9]*) die "entrypoint.port must be an integer: $port" ;;
    esac
    if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
        die "entrypoint.port must be in range 1024-65535: $port"
    fi

    demo_dir="$USER_HOME/$REPO/demos/$working_dir"
    [ -d "$demo_dir" ] || die "Demo directory not found: $demo_dir"

    if [ -n "$serve_dir" ]; then
        abs_serve="$demo_dir/$serve_dir"
    else
        abs_serve="$demo_dir"
    fi
    [ -d "$abs_serve" ] || die "serve_dir not found: $abs_serve"

    # Refuse rather than kill the current holder of the port
    if port_in_use "$port"; then
        die "Port $port is already in use - refusing to start the static web server"
    fi

    url="http://localhost:${port}"

    info "Starting static web server on port $port ..."
    run_as_user python3 -m http.server "$port" --directory "$abs_serve" >/dev/null 2>&1 &
    HTTP_SERVER_PID=$!

    info "Waiting for server to become ready..."
    if ! wait_for_http "$url" 15; then
        kill "$HTTP_SERVER_PID" 2>/dev/null || true
        HTTP_SERVER_PID=""
        die "Static web server did not become ready within 15s on port $port"
    fi

    echo
    echo "Demo is running at: $url"
    echo

    launch_browser "$url"

    echo "============================================"
    echo "  Demo is running (static web)"
    echo "============================================"
    echo

    # Interactive wait if TTY available; otherwise wait on the server.
    # Either way, the cleanup trap stops the http.server on exit.
    if [ -t 0 ]; then
        echo "Press Enter to stop the server..."
        read -r
        info "Stopping static web server..."
    else
        wait "$HTTP_SERVER_PID" 2>/dev/null || true
    fi
}

# Python script launcher
run_python() {
    local working_dir script launcher needs_leds demo_dir venv_python

    working_dir=$(demo_field '.entrypoint.working_dir' '')
    script=$(demo_field '.entrypoint.script' '')
    launcher=$(demo_field '.entrypoint.launcher' '')
    needs_leds=$(demo_field '.needs_hw.leds' 'false')

    # A dedicated launcher WINS when the manifest declares one: it exists
    # precisely because the demo needs pre-launch work the generic path cannot do
    # (LED-Painter converts to the PWM/PIO driver and must run its Qt GUI as the
    # user against the root renderer). Running .entrypoint.script directly in that
    # case silently bypassed the launcher and its setup.
    #
    # The generic script path is for demos that need nothing extra - they simply
    # declare no launcher (e.g. quantum-raspberry-tie, quantum-lights-out).
    if [ -n "$launcher" ]; then
        delegate_launcher "$launcher"
        return 0
    fi
    if [ -z "$script" ]; then
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

    # Collect script arguments (variant args override .entrypoint.args)
    local -a script_args=()
    local arg
    while IFS= read -r arg; do
        [ -n "$arg" ] && script_args+=("$arg")
    done < <(get_demo_args)

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
        "$venv_python" -W ignore::DeprecationWarning "$script" ${script_args[@]+"${script_args[@]}"}
    else
        # Regular Python script, run as user
        info "Running Python script..."
        run_as_user "$venv_python" "$script" ${script_args[@]+"${script_args[@]}"}
    fi
}

# Delegate to existing launcher script
# Used as fallback when type-specific handler can't run directly
delegate_launcher() {
    local launcher="${1:-}"

    if [ -z "$launcher" ]; then
        launcher=$(demo_field '.entrypoint.launcher' '')
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

    # Find manifest file across the search path (shipped dir, then the user
    # dir where external demos are added; shipped wins on id collision).
    MANIFEST_FILE=$(rq_find_manifest "$MANIFEST_DIR" "$DEMO_ID") \
        || die "Manifest not found for demo '$DEMO_ID' (searched shipped and user manifest dirs)"

    # Validate the variant exists before any lookups use it
    if [ -n "$VARIANT" ]; then
        local variant_exists
        variant_exists=$(jq -r ".variants[] | select(.id == \"$VARIANT\") | .id // null" "$MANIFEST_FILE" 2>/dev/null)
        if [ "$variant_exists" = "null" ] || [ -z "$variant_exists" ]; then
            die "Unknown variant: $VARIANT"
        fi
    fi

    # Get demo info (variant-aware: variants may override the entrypoint,
    # and carry their own args and needs_hw; everything else falls back
    # to the main manifest)
    local demo_name entrypoint_type
    demo_name=$(get_field '.name' "$DEMO_ID")
    entrypoint_type=$(demo_field '.entrypoint.type' '')

    echo
    echo "=== $demo_name${VARIANT:+ ($VARIANT)} ==="
    echo

    # Setup cleanup trap
    trap cleanup EXIT INT TERM

    # Check requirements
    check_requirements

    # Ensure demo is installed (auto-install if possible)
    ensure_installed

    # Dispatch based on entrypoint type
    # If a launcher is specified, it can be used as fallback for any type
    local launcher
    launcher=$(demo_field '.entrypoint.launcher' '')

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
        web-static)
            run_web_static
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
