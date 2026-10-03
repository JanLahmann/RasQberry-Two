#!/bin/bash
# Not -e: the point of this script is to look at the command's exit status.
set -uo pipefail

# ============================================================================
# RasQberry: keep a desktop icon's window open when its demo fails
# ============================================================================
# Description: Runs a demo (an icon's command) and, if it fails, keeps the
#   terminal window open with the log's path until Enter is pressed. The
#   terminal Pi OS opens for icons (lxterminal) has no "hold" option, so a demo
#   that failed - offline on its first start, say - closed its window at once
#   and the error was never seen (R-029). A copy of the output is kept in
#   ~/.cache/rasqberry/<name>.log (rq_info.sh --report collects it).
# Usage: rq_hold_on_error.sh [-t TITLE] COMMAND [ARGS...]
#   e.g. Exec=/usr/bin/rq_hold_on_error.sh /usr/bin/rq_demo_run.sh grok-bloch
#   -t sets the window title (else the terminal shows the command line, R-135;
#   rq_demo_run.sh sets the demo's name itself).

case "${1:-}" in
    ""|-h|--help)
        sed -n '6p;8,17p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    -t)
        [ -t 1 ] && printf '\033]0;%s\007' "${2:-RasQberry}"
        shift 2 2>/dev/null && [ $# -gt 0 ] || exit 2
        ;;
esac

# Log name: the demo id for the engine, else the command's name
name=$(basename "$1" .sh)
if [ "$name" = "rq_demo_run" ] && [ -n "${2:-}" ]; then
    name="$2"
fi
log_dir="${XDG_CACHE_HOME:-$HOME/.cache}/rasqberry"
log="$log_dir/$name.log"

rc=0
if [ -t 0 ] && [ -t 1 ] && command -v script >/dev/null 2>&1 \
    && mkdir -p "$log_dir" 2>/dev/null && : > "$log" 2>/dev/null; then
    # script(1) keeps the demo on a terminal (dialogs, Ctrl+C) and copies its
    # output to the log; -e returns the demo's own exit status.
    script -qefc "$(printf '%q ' "$@")" "$log"
    rc=$?
else
    log=""
    "$@"
    rc=$?
fi

case "$rc" in
    # finished, or stopped with Ctrl+C (130) / window closed (129, 143)
    0|129|130|143) exit "$rc" ;;
esac

echo
echo "------------------------------------------------------------"
echo "The demo stopped with an error (status $rc). The lines above say why."
[ -n "$log" ] && echo "Log: $log"
echo "For a bug report: rq_info.sh --report"
echo
printf 'Press Enter to close this window.'
read -r _ || true
exit "$rc"
