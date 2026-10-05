#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: My Quantum Programs (JupyterLab in your own folder)
# ============================================================================
# Description: Opens JupyterLab in ~/My-Quantum-Programs, the learner's own
#   folder with the starter notebooks and programs (R-071), at the Hello
#   World notebook (doQumentation's, item 9). Unlike the demo launchers, which
#   start Jupyter inside a demo checkout, new notebooks land in a folder that
#   belongs to the user. Creates the folder first if needed
#   (rq_learner_setup.sh). Runs as the user; started as root it re-runs itself
#   as the desktop user.
# Usage: rq_my_programs.sh            (desktop icon "My Quantum Programs")

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"
rq_help_guard "$@"

# Anonymous usage count of this start, as the demo engine counts demos (it has
# no manifest). Once: the re-run as the desktop user inherits RQ_DEMO_COUNTED.
if [ -z "${RQ_DEMO_COUNTED:-}" ]; then
    export RQ_DEMO_COUNTED=my-quantum-programs
    how=$(rq_demo_start_how)
    rq_count_event demo-start my-quantum-programs ${how:+"$how"}
fi

if [ "$(id -u)" -eq 0 ]; then
    user_name=$(get_user_name)
    [ "$user_name" != "root" ] || die "Run this as the desktop user, not as root"
    exec sudo -u "$user_name" -H -- env DISPLAY="${DISPLAY:-:0}" RQ_DEMO_COUNTED="$RQ_DEMO_COUNTED" "$0" "$@"
fi

load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

PROGRAMS_DIR="$USER_HOME/My-Quantum-Programs"
PORT=$(find_available_port "${MY_PROGRAMS_JUPYTER_PORT:-8893}")

"${SCRIPT_DIR}/rq_learner_setup.sh" --quiet || warn "Learner setup reported a problem (see above)"
# The folder is created once; if the user removed it, start an empty one.
# On an A/B card it is a link to /data (rq_carry_over.sh): "$PROGRAMS_DIR/".
mkdir -p "$PROGRAMS_DIR/" 2>/dev/null || \
    die "Cannot open $PROGRAMS_DIR (on the A/B image it lives on the data partition, /data)"

activate_venv || die "RasQberry Python environment not found"
command -v jupyter-lab >/dev/null 2>&1 || \
    die "JupyterLab not found in the RasQberry Python environment (rq_venv_repair.sh --reset restores it)"

JUPYTER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
# Jupyter first (item 9): open the Hello World notebook, else the guide
START_PAGE="lab"
if [ -f "$PROGRAMS_DIR/Hello-World.ipynb" ]; then
    START_PAGE="lab/tree/Hello-World.ipynb"
elif [ -f "$PROGRAMS_DIR/README.md" ]; then
    START_PAGE="lab/tree/README.md"
fi
URL="http://localhost:${PORT}/${START_PAGE}?token=${JUPYTER_TOKEN}"

cd "$PROGRAMS_DIR"
info "Starting JupyterLab in $PROGRAMS_DIR ..."
# expose_app_in_browser: the stop can save the open notebooks (#12)
jupyter-lab \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --ServerApp.token="$JUPYTER_TOKEN" \
    --ServerApp.password="" \
    --LabApp.expose_app_in_browser=True \
    >/dev/null 2>&1 &
JUPYTER_PID=$!

# Stopping JupyterLab lost the edits it had not saved yet ("Saving failed",
# #12). Before it stops, the notebooks open in the Pi's browser are saved
# (rq_browser_tab.py, through Chromium's DevTools port).
SAVED=""
save_open_notebooks() {
    python3 "$SCRIPT_DIR/rq_browser_tab.py" save "$URL" </dev/null >/dev/null 2>&1
}

cleanup() {
    set +e   # a closed window cannot show messages: still stop the server
    trap '' HUP INT TERM
    if kill -0 "$JUPYTER_PID" 2>/dev/null; then
        info "Stopping JupyterLab..."
        # Ctrl+C or a closed window: save what is open, then close its tab
        # (no dead tab, #9), then stop the server, which stops its kernels
        # first (#27). Detached, so that a closed window does not cut it short.
        rq_run_detached bash -c '. "$1"; [ -n "$2" ] || python3 "$3" save "$4"
            python3 "$3" close "$4"; rq_stop_pid "$5" 10' \
            _ "$SCRIPT_DIR/rq_common.sh" "$SAVED" "$SCRIPT_DIR/rq_browser_tab.py" "$URL" "$JUPYTER_PID"
    fi
}
setup_cleanup_trap cleanup

# JupyterLab needs about 15 s to start on a Pi 4.
waited=0
until curl -s "http://localhost:${PORT}/" >/dev/null 2>&1; do
    kill -0 "$JUPYTER_PID" 2>/dev/null || die "JupyterLab exited during startup"
    [ "$waited" -lt 60 ] || die "JupyterLab did not answer within 60 seconds"
    sleep 1
    waited=$((waited + 1))
done

if check_display || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    open_browser "$URL" || true
fi

echo ""
echo "======================================"
echo "  My Quantum Programs (JupyterLab)"
echo "======================================"
echo ""
echo "Folder: $PROGRAMS_DIR"
echo "URL:    $URL"
echo ""
echo "Start with Hello-World.ipynb. Your notebooks and programs are saved in this folder,"
echo "and the open notebooks are saved when you stop JupyterLab here."
rq_wait_for_stop "JupyterLab" "$JUPYTER_PID"

# Enter: save first; if that is not possible, ask before the edits are lost
if [ -t 0 ] && _rq_pid_alive "$JUPYTER_PID"; then
    info "Saving the open notebooks..."
    if ! save_open_notebooks; then
        echo "The open notebooks could not be saved from here. Save them in the browser"
        printf '(Ctrl+S), then press Enter to stop JupyterLab. '
        read -r _ || true
    fi
    SAVED=1
fi
