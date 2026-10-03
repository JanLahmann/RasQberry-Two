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

if [ "$(id -u)" -eq 0 ]; then
    user_name=$(get_user_name)
    [ "$user_name" != "root" ] || die "Run this as the desktop user, not as root"
    exec sudo -u "$user_name" -H -- env DISPLAY="${DISPLAY:-:0}" "$0" "$@"
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
jupyter-lab \
    --no-browser \
    --port="$PORT" \
    --ip=127.0.0.1 \
    --ServerApp.token="$JUPYTER_TOKEN" \
    --ServerApp.password="" \
    >/dev/null 2>&1 &
JUPYTER_PID=$!

cleanup() {
    set +e   # a closed window cannot show messages: still stop the server
    trap '' HUP INT TERM
    if kill -0 "$JUPYTER_PID" 2>/dev/null; then
        info "Stopping JupyterLab..."
        kill "$JUPYTER_PID" 2>/dev/null || true
        sleep 1
        kill -9 "$JUPYTER_PID" 2>/dev/null || true
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
echo "Start with Hello-World.ipynb. Your notebooks and programs are saved in this folder."
rq_wait_for_stop "JupyterLab" "$JUPYTER_PID"
