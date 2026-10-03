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

# Matplotlib picks the first Qt binding it finds. PySide6 from pip (older LED
# Painter installs put it into the shared venv) bundles a Qt that dies with a
# bus error on the Pi 5 kernel (16 KB pages); Quantum Fractals crashed at its
# first window. Pin matplotlib to PyQt5, the system Qt linked into the venv
# (#234, #302), unless the user chose otherwise.
export QT_API="${QT_API:-pyqt5}"

# Tracking variables for cleanup
JUPYTER_PID=""
CONTAINER_NAME=""
DOCKER_STOP_ON_EXIT=0
HTTP_SERVER_PID=""
# The demo's name, for messages (set in main)
DEMO_TITLE="the demo"
# Checkout of a first install still in progress (removed if it does not finish)
INSTALLING_DIR=""
# Helper processes a demo starts that outlive it (manifest
# .entrypoint.stop_on_exit, e.g. Raspberry Tie's SenseHAT emulator window, #104)
STOP_ON_EXIT=()

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
#
# The browser's own console chatter ("Opening in existing browser session.")
# went to the terminal and was drawn over the raspi-config menu (R-137).
launch_browser() {
    local url="$1"

    if command -v chromium-browser &>/dev/null; then
        info "Opening browser..."
        run_as_user chromium-browser --password-store=basic "$url" >/dev/null 2>&1 &
    elif command -v firefox &>/dev/null; then
        info "Opening browser..."
        run_as_user firefox "$url" >/dev/null 2>&1 &
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
# (.variants[].args), the main manifest under .entrypoint.args. A variant
# with "args": [] has none (it does not inherit the main manifest's).
get_demo_args() {
    if [ -n "${VARIANT:-}" ]; then
        local vargs
        vargs=$(jq -r ".variants[] | select(.id == \"$VARIANT\") | (.args // [])[]" "$MANIFEST_FILE" 2>/dev/null)
        if [ -n "$vargs" ]; then
            printf '%s\n' "$vargs"
            return 0
        fi
        if jq -e ".variants[] | select(.id == \"$VARIANT\") | has(\"args\")" "$MANIFEST_FILE" >/dev/null 2>&1; then
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
                die "This demo needs a screen: start it on the Pi's desktop or over VNC (no display, DISPLAY is not set)"
            fi
            ;;
        optional)
            # Server demos start headless over SSH and print their address
            # (Jan, Q19)
            check_display || info "No screen in this session: the demo prints its address instead of opening a browser."
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

# The Docker image a docker demo runs, when it names one: the release pin, or
# the newer version chosen under "Update demos"
demo_docker_image() {
    [ "$(get_field '.entrypoint.type' '')" = "docker" ] || return 0
    rq_demo_image "$DEMO_ID" "$MANIFEST_FILE"
}

# Is Docker usable here? (If not, the demo's launcher explains why.)
docker_usable() {
    command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

# Check if demo is installed
check_installed() {
    local marker_file working_dir preinstalled installed_flag image

    marker_file=$(get_field '.install.marker_file' '')
    working_dir=$(get_field '.entrypoint.working_dir' '')
    preinstalled=$(get_bool '.install.preinstalled' 'false')
    installed_flag=$(get_field '.install.installed_flag' '')

    # If preinstalled, no check needed
    if [ "$preinstalled" = "true" ]; then
        return 0
    fi

    # A Docker demo is there when its image is. Its flag (if any) says nothing
    # once the image was removed to free space, and doQumentation and the
    # Quantum Lab have no flag at all: they pulled ~1 GB on first start
    # without asking (R-030).
    image=$(demo_docker_image)
    if [ -n "$image" ] && docker_usable; then
        docker image inspect "$image" >/dev/null 2>&1 || return 1
        [ -z "$marker_file" ] && return 0
    fi

    # Check marker file if specified. When the checkout is there, the demo is
    # installed even if its flag says otherwise: Lights Out and Raspberry Tie
    # had no flag before (R-087), and an older engine did not set it.
    if [ -n "$marker_file" ] && [ -n "$working_dir" ]; then
        local check_path="$USER_HOME/$REPO/demos/$working_dir/$marker_file"
        if [ ! -f "$check_path" ]; then
            return 1
        fi
        return 0
    fi

    # Check the recorded flag if the manifest names one.
    #
    # A demo whose install is not a checkout - a Docker image built on the Pi -
    # has no marker file to look for, so it records its state in the env file
    # instead. install_demo has always WRITTEN this flag; nothing ever read it,
    # so those demos fell through to the "return 0" below and reported installed
    # when nothing was there. quantum-mixer then skipped its consent prompt and
    # went straight to a 10-15 minute Docker build from source (finding F19),
    # which is exactly the build that filled a 10GB slot in F28.
    if [ -n "$installed_flag" ]; then
        local flag_value
        eval "flag_value=\${${installed_flag}:-false}"
        [ "$flag_value" = "true" ] || return 1
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
    # the release pin, or the newer commit chosen under "Update demos"
    ref=$(rq_demo_ref "$DEMO_ID" "$MANIFEST_FILE")
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

    # Until the install has finished, the cleanup trap removes the checkout:
    # a failed patch or post-install, or Ctrl+C, used to leave a tree whose
    # marker file made the demo look installed - and it then ran unpatched or
    # half set up (R-057).
    INSTALLING_DIR="$demo_dir"

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
        # (a previous partial/failed checkout may be lying around - root-owned
        # if the menu made it, which a plain rm as the user could not remove:
        # 25 "Permission denied" lines and a silent exit, R-057).
        rq_remove_tree "$demo_dir" \
            || die "An earlier, incomplete download of $DEMO_ID is in the way and cannot be removed: $demo_dir"
        fetch_pinned_repo "$repo_url" "$ref" "$demo_dir" \
            || die "Failed to fetch pinned commit $ref for demo '$DEMO_ID'"
    else
        # clone_demo cleans up partial clones and fixes ownership
        rq_remove_tree "$demo_dir" \
            || die "An earlier, incomplete download of $DEMO_ID is in the way and cannot be removed: $demo_dir"
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
    # this launcher, else /usr/bin) run as `<script> --path <demo_dir>`, as the
    # user: a .py script with the venv python, any other with bash (LED-Painter's
    # launcher converts its checkout this way, so its first start needs no second
    # download and "Download all demos" leaves it ready offline, R-138).
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
        case "$post_install" in
            *.py)
                if venv_path=$(find_venv "$STD_VENV"); then
                    run_as_user "$venv_path/bin/python3" "$post_script" --path "$demo_dir" \
                        || die "Post-install step failed for demo '$DEMO_ID': $post_install"
                else
                    die "Virtual environment not found - cannot run post-install for '$DEMO_ID'"
                fi
                ;;
            *)
                run_as_user bash "$post_script" --path "$demo_dir" \
                    || die "Post-install step failed for demo '$DEMO_ID': $post_install"
                ;;
        esac
    fi

    # Record the demo as installed in the environment file. The raspi-config menu
    # reads these *_INSTALLED flags, so the manifest path must set them too or its
    # view of what is installed drifts from reality.
    if [ -n "$installed_flag" ]; then
        update_env_var "$installed_flag" "true" \
            || warn "Could not set $installed_flag in the environment file"
    fi

    INSTALLING_DIR=""
    info "Demo installed successfully"
}

# The installed flag follows the checkout: set it when the demo is there but
# the flag is not (a demo installed before it had one, R-087). Quiet, and a
# write that fails changes nothing.
sync_installed_flag() {
    local installed_flag flag_value
    installed_flag=$(get_field '.install.installed_flag' '')
    [ -n "$installed_flag" ] || return 0
    eval "flag_value=\${${installed_flag}:-false}"
    [ "$flag_value" = "true" ] && return 0
    update_env_var "$installed_flag" "true" >/dev/null 2>&1 || true
}

# Is the demo's checkout there (its marker file, else its directory)?
checkout_present() {
    local marker_file working_dir
    marker_file=$(get_field '.install.marker_file' '')
    working_dir=$(get_field '.entrypoint.working_dir' '')
    [ -n "$working_dir" ] || return 1
    if [ -n "$marker_file" ]; then
        [ -f "$USER_HOME/$REPO/demos/$working_dir/$marker_file" ]
    else
        [ -d "$USER_HOME/$REPO/demos/$working_dir" ]
    fi
}

# Download the demo's Docker image (a docker demo with nothing else to install)
install_docker_image() {
    local image="$1"
    docker_usable || die "Docker is not available, so $DEMO_ID cannot be downloaded (the image may be misbuilt)."
    info "Downloading the Docker image $image. This takes several minutes..."
    if ! docker pull "$image"; then
        die "Could not download the Docker image $image. Check the internet connection and the free space, then try again."
    fi
}

# Ensure demo is installed; on its first start, ask (one dialog with size,
# time and free space, Jan's Q27) and install it.
ensure_installed() {
    if check_installed; then
        sync_installed_flag
        return 0
    fi

    rq_require_demo_consent "$DEMO_ID" "$MANIFEST_FILE"

    # A demo whose setup cannot be expressed as "clone a repo" names its own
    # installer instead. The IBM learning pair is the live case: one shared
    # sparse checkout of Qiskit/documentation feeding two demos, with generated
    # marker notebooks. Delegating keeps that special case in one place while
    # this engine still owns WHEN installs happen, so every entry point (menu,
    # desktop icon, demo loop) goes through here.
    local installer repo_url image
    installer=$(get_field '.install.installer' '')
    if [ -n "$installer" ]; then
        info "Installing via $installer ..."
        install_demo_raspiconfig "$installer" \
            || die "Installation failed for demo '$DEMO_ID' ($installer)"
        return 0
    fi

    repo_url=$(get_field '.install.repo_url' '')
    image=$(demo_docker_image)

    if [ -z "$repo_url" ] && [ -z "$image" ]; then
        die "Demo not installed and no install.repo_url specified. Please install via raspi-config or the RasQberry menu."
    fi

    # (a catalogue Docker demo keeps its checkout when only the image is gone)
    if [ -n "$repo_url" ] && ! checkout_present; then
        info "Installing..."
        install_demo
    fi
    if [ -n "$image" ] && docker_usable && ! docker image inspect "$image" >/dev/null 2>&1; then
        install_docker_image "$image"
    fi
    return 0
}

# ============================================================================
# TYPE-SPECIFIC LAUNCHERS
# ============================================================================

# Jupyter notebook launcher
run_jupyter() {
    local working_dir port notebook demo_dir launcher

    working_dir=$(demo_field '.entrypoint.working_dir' '')
    port=$(demo_field '.entrypoint.jupyter_port' '8888')
    notebook=$(demo_field '.entrypoint.notebook' '')
    launcher=$(demo_field '.entrypoint.launcher' '')

    # A declared launcher wins, exactly as in run_python/run_docker/run_browser.
    # These launchers do per-demo work the generic server start cannot know about
    # (app-mode/voila, notebook selection, token prompts). Ignoring them here was
    # why the menu (which calls the launcher) and the desktop icon (which came
    # through this engine) behaved differently for the same jupyter demo.
    if [ -n "$launcher" ]; then
        delegate_launcher "$launcher"
        return 0
    fi

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

    # Start Jupyter notebook in background (as the user, not root).
    #
    # nbserver_extensions disables the jupyterlab server extension: the venv ships
    # JupyterLab 4 alongside the classic notebook 6 server, and pip's jupyterlab
    # config enables its extension for NotebookApp, where a Lab 4 extension cannot
    # load. The result was a full traceback on launch that made a working demo
    # look crashed. Demos wanting the Lab UI should declare a launcher that runs
    # `jupyter lab` (as the IBM and paradoxes demos do); this generic path serves
    # the classic notebook.
    info "Starting Jupyter notebook server..."
    run_as_user "$jupyter_bin" notebook \
        --no-browser \
        --port="$port" \
        --ip=127.0.0.1 \
        --NotebookApp.token='' \
        --NotebookApp.password='' \
        --NotebookApp.open_browser=False \
        --NotebookApp.nbserver_extensions="{'jupyterlab':False}" \
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
        echo "Press Enter or close this window to stop $DEMO_TITLE."
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

    docker_image=$(demo_docker_image)
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
        --label "org.rasqberry.demo=$DEMO_ID" \
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

    # Interactive wait if TTY available. Closing the window stops it too
    # (cleanup), so the rule is the same as for every other demo (R-099).
    if [ -t 0 ]; then
        DOCKER_STOP_ON_EXIT=1
        echo "Press Enter or close this window to stop $DEMO_TITLE."
        read -r
        info "Stopping container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        DOCKER_STOP_ON_EXIT=0
    else
        echo "To stop it: docker stop $CONTAINER_NAME"
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

    url="http://localhost:${port}"

    # Started before (an icon without a window keeps its server): open it
    # again instead of failing on the port, which a click without a terminal
    # did invisibly (R-106).
    if pgrep -f -- "http.server $port --directory $abs_serve" >/dev/null 2>&1; then
        info "$DEMO_TITLE is already running at $url"
        launch_browser "$url"
        return 0
    fi

    # Refuse rather than kill the current holder of the port
    if port_in_use "$port"; then
        die "Port $port is already in use - refusing to start the static web server"
    fi

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
        echo "Press Enter or close this window to stop $DEMO_TITLE."
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

    # Terminal demos run until stopped; say how (#104). LED demos re-run this
    # launcher as root, so only that pass prints it.
    if [ -t 1 ] && { [ "$needs_leds" != "true" ] || [ "$(id -u)" = "0" ]; }; then
        echo "Press Ctrl+C or close this window to stop $DEMO_TITLE."
        echo
    fi

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

    # Put the demo API on sys.path. A demo runs from its own checkout, and
    # /usr/bin - where rq_led_utils.py ships - is not a Python path, so
    # "from rq_led_utils import get_led_config" fails there even though we ask
    # external LED demos to use exactly that. Internal demos never noticed:
    # they live next to the module and sys.path[0] covers them.
    local demo_pythonpath="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

    # LED demos require root for GPIO access
    if [ "$needs_leds" = "true" ]; then
        # Re-exec with sudo if needed
        if [ "$(id -u)" != "0" ]; then
            info "LED/GPIO operations require root access"
            info "Re-executing with sudo..."
            exec sudo -E DISPLAY="${DISPLAY:-:0}" "$0" "$DEMO_ID" "${VARIANT:-}"
        fi

        # Another program on the LED panel? On a Pi 4 both would draw at
        # once without an error (R-162): name it and offer to stop it.
        led_panel_ready || exit 0
        # Ctrl+C, a closed window: the panel is cleared in cleanup() (R-158)
        LED_DEMO_RAN=1
        info "Running with LED support (as root)..."
        prepare_user_home_for_root_run
        # PYTHONDONTWRITEBYTECODE: this is the user's venv. A root run that
        # writes __pycache__ leaves root-owned files behind, and the user's
        # next pip install into the venv then fails with EACCES (#285).
        # HOME: the desktop user's, from the menu (where sudo set /root) as from
        # the desktop icon (sudo -E kept it), so the IBM Quantum account is the
        # user's own in ~/.qiskit on every path (Q26).
        HOME="${ROOT_RUN_HOME:-$HOME}" PYTHONPATH="$demo_pythonpath" PYTHONDONTWRITEBYTECODE=1 \
            "$venv_python" -W ignore::DeprecationWarning "$script" ${script_args[@]+"${script_args[@]}"}
    else
        # Regular Python script, run as user. sudo resets the environment, so
        # PYTHONPATH has to travel through env(1) rather than an export.
        info "Running Python script..."
        run_as_user env PYTHONPATH="$demo_pythonpath" \
            "$venv_python" "$script" ${script_args[@]+"${script_args[@]}"}
    fi
}

# ============================================================================
# ROOT RUNS AND THE USER'S HOME
# ============================================================================
# LED demos run as root (GPIO), but with the desktop user's HOME, so they use
# the user's IBM Quantum account in ~/.qiskit (Q26). Whatever root creates
# there is the user's afterwards: qiskit-ibm-runtime creates
# ~/.qiskit/qiskit-ibm.json on any account lookup, and one Raspberry Tie run on
# a real backend left it root-owned - the learner's own
# QiskitRuntimeService.save_account() then failed with Errno 13 (R-147).

ROOT_RUN_HOME=""
ROOT_RUN_MARK=""

# Set ROOT_RUN_HOME to the desktop user's home when this is a root run for a
# desktop user, and create the IBM account file as that user beforehand.
prepare_user_home_for_root_run() {
    local user_name
    [ "$(id -u)" = "0" ] || return 0
    user_name=$(get_user_name)
    [ "$user_name" != "root" ] || return 0
    [ -n "${USER_HOME:-}" ] && [ "$USER_HOME" != "/root" ] && [ -d "$USER_HOME" ] || return 0
    ROOT_RUN_HOME="$USER_HOME"
    # what root creates in the home from now on is handed back afterwards
    ROOT_RUN_MARK=$(mktemp) || ROOT_RUN_MARK=""
    if [ "$(get_field '.needs_ibm_token' 'none')" != "none" ]; then
        sudo -u "$user_name" -H sh -c \
            'mkdir -p "$1/.qiskit" && { [ -e "$1/.qiskit/qiskit-ibm.json" ] || printf "{}" > "$1/.qiskit/qiskit-ibm.json"; }' \
            _ "$ROOT_RUN_HOME" 2>/dev/null || true
    fi
}

# Hand back to the user what the root run created in the home (new top-level
# entries such as ~/.dbus from the SenseHAT emulator), and anything root-owned
# in the places Python, Qiskit, matplotlib and the emulator write to.
restore_user_home_after_root_run() {
    [ -n "$ROOT_RUN_HOME" ] || return 0
    local user_name d
    user_name=$(get_user_name)
    if [ -n "$ROOT_RUN_MARK" ] && [ -e "$ROOT_RUN_MARK" ]; then
        find "$ROOT_RUN_HOME" -mindepth 1 -maxdepth 1 -user root -newer "$ROOT_RUN_MARK" \
            -exec chown -hR "$user_name:" {} + 2>/dev/null || true
        rm -f "$ROOT_RUN_MARK"
    fi
    for d in .qiskit .cache .config .matplotlib .sensehat .dbus; do
        [ -e "$ROOT_RUN_HOME/$d" ] || continue
        find "$ROOT_RUN_HOME/$d" -maxdepth 3 -user root -exec chown -h "$user_name:" {} + 2>/dev/null || true
    done
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

    # Pass the demo/variant args on to the launcher. Without this a launcher that
    # takes a parameter could not be driven from a manifest at all, which is why
    # per-notebook demos needed their own bespoke wrapper scripts and desktop
    # icons that bypassed this engine entirely.
    local launcher_args=()
    local a
    while IFS= read -r a; do
        [ -n "$a" ] && launcher_args+=("$a")
    done < <(get_demo_args)

    info "Delegating to: $launcher${launcher_args[*]:+ ${launcher_args[*]}}"
    exec "$launcher_path" "${launcher_args[@]}"
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

    # Helper windows/processes the demo started (only those that were not
    # already running when it launched)
    local pat
    for pat in ${STOP_ON_EXIT[@]+"${STOP_ON_EXIT[@]}"}; do
        if pgrep -f -- "$pat" >/dev/null 2>&1; then
            info "Closing $pat..."
            pkill -f -- "$pat" 2>/dev/null || sudo -n pkill -f -- "$pat" 2>/dev/null || true
        fi
    done

    restore_user_home_after_root_run

    if [ -n "$INSTALLING_DIR" ]; then
        info "Removing the unfinished download: $INSTALLING_DIR"
        rq_remove_tree "$INSTALLING_DIR" || warn "Could not remove $INSTALLING_DIR"
        INSTALLING_DIR=""
    fi

    # A container this run waited on is stopped when its window closes; one
    # started without a terminal keeps running (stop it with docker stop).
    if [ "$DOCKER_STOP_ON_EXIT" = "1" ] && [ -n "$CONTAINER_NAME" ]; then
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi

    # An LED demo leaves its last frame on the panel when it is stopped with
    # Ctrl+C or its window is closed (R-158). Quietly: the terminal may be gone.
    if [ -n "${LED_DEMO_RAN:-}" ]; then
        LED_DEMO_RAN=""
        led_clear_quietly
    fi
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

Options:
  --install-only   Install the demo if needed, then exit without launching it.
                   Lets callers that only want the demo on disk (the raspi-config
                   menu, batch "download all demos") share this one install path
                   instead of keeping their own.

A first install asks first (size, time, free space). RQ_AUTO_INSTALL=1 skips
the question (the caller asked already); the free-space check still runs.
  --is-installed   Exit 0 if the demo is installed, 1 if not. Prints nothing.
                   Lets callers decide whether to prompt before a download
                   without re-implementing this engine's install check.

Examples:
  rq_demo_run.sh fun-with-quantum       # Launch Fun with Quantum notebooks
  rq_demo_run.sh quantum-mixer          # Launch Quantum Mixer Docker demo
  rq_demo_run.sh grok-bloch-web         # Open Grok Bloch in browser
  rq_demo_run.sh led-demos ibm-logo     # Run IBM Logo LED demo
  rq_demo_run.sh grok-bloch --install-only   # Install only, do not launch

Available demos can be found in: /usr/config/demo-manifests/

EOF
}

# Re-run this engine as the desktop user when it runs as root for a demo that
# does not need the LED panel. Keeps the display (only if there is one, so the
# "needs a screen" check still sees an SSH login) and the menu's error file.
drop_to_desktop_user() {
    local user_name
    [ "$(id -u)" = "0" ] || return 0
    [ "$(demo_field '.needs_hw.leds' 'false')" != "true" ] || return 0
    user_name=$(get_user_name)
    [ "$user_name" != "root" ] || return 0
    local -a keep=()
    local v
    for v in DISPLAY RQ_ERROR_FILE RQ_AUTO_INSTALL RQ_NO_MESSAGES RQ_DEBUG \
             RQ_CONFIRMED_DEMO RQ_SPACE_RESERVE_MB RQ_TEST_FREE_MB RQ_TEST_OFFLINE; do
        [ -n "${!v:-}" ] && keep+=("$v=${!v}")
    done
    info "Starting as $user_name (only LED demos run as root)..."
    exec sudo -u "$user_name" -H ${keep[@]+"${keep[@]}"} -- "$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")" "$@"
}

main() {
    check_jq
    local -a orig_args=("$@")

    # Parse arguments
    if [ $# -lt 1 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        usage
        exit 0
    fi

    # Collect flags from anywhere in the argument list, so both
    # "<id> --install-only" and "<id> <variant> --install-only" work.
    local INSTALL_ONLY=0
    local IS_INSTALLED_CHECK=0
    local positional=""
    local arg
    for arg in "$@"; do
        case "$arg" in
            --install-only) INSTALL_ONLY=1 ;;
            --is-installed) IS_INSTALLED_CHECK=1 ;;
            -*) die "Unknown option: $arg" ;;
            *) positional="$positional $arg" ;;
        esac
    done
    # shellcheck disable=SC2086 # deliberate word splitting of collected args
    set -- $positional

    [ $# -lt 1 ] && { usage; exit 0; }

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

    # A pure query: answer and leave, before the banner, trap or any other
    # output. Callers use this to decide whether to prompt for a download, so it
    # must stay silent - stray output would land in their whiptail dialogs.
    if [ "$IS_INSTALLED_CHECK" = "1" ]; then
        check_installed && exit 0
        exit 1
    fi

    # Demos that do not drive the LED panel run as the desktop user (Q26).
    #
    # From the RasQberry menu this engine runs as root (sudo raspi-config).
    # Jupyter refuses to start as root, so all four notebook demos failed there
    # while their desktop icons, which run as the user, worked (R-025); and
    # whatever a root run downloads or saves lands root-owned in the user's
    # home. Only LED demos need root, for the GPIO, and they get it below.
    drop_to_desktop_user "${orig_args[@]}"

    # Get demo info (variant-aware: variants may override the entrypoint,
    # and carry their own args and needs_hw; everything else falls back
    # to the main manifest)
    local demo_name entrypoint_type
    demo_name=$(get_field '.name' "$DEMO_ID")
    entrypoint_type=$(demo_field '.entrypoint.type' '')
    DEMO_TITLE="$demo_name"
    # The window's title: the demo's name, not the command line (R-135)
    [ -t 1 ] && printf '\033]0;%s\007' "$demo_name"

    echo
    echo "=== $demo_name${VARIANT:+ ($VARIANT)} ==="
    echo

    # Setup cleanup trap (HUP: the demo's window was closed)
    trap cleanup EXIT INT TERM HUP

    # Install-only runs BEFORE check_requirements on purpose: installing a demo
    # only needs the network, not the hardware it will eventually run on. The
    # raspi-config menu installs from the console with no DISPLAY, and demanding
    # a display here would refuse to download a demo the user just asked for.
    if [ "$INSTALL_ONLY" = "1" ]; then
        ensure_installed
        info "$demo_name is installed"
        exit 0
    fi

    # Check requirements
    check_requirements

    # Remember which declared helper processes the demo will start itself
    local pat
    while IFS= read -r pat; do
        [ -n "$pat" ] || continue
        pgrep -f -- "$pat" >/dev/null 2>&1 || STOP_ON_EXIT+=("$pat")
    done < <(jq -r '.entrypoint.stop_on_exit[]? // empty' "$MANIFEST_FILE" 2>/dev/null)

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
