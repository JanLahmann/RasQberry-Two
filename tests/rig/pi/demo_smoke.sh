#!/bin/bash
# ============================================================================
# RasQberry rig test: smoke-test one demo the way a person runs it
# ============================================================================
# Runs ON the Pi, in the desktop session (issue #234). Opens a real terminal
# window (lxterminal) running `rq_demo_run.sh <id>`, as the desktop icons do,
# lets the demo run, takes a screenshot, then types Ctrl+C into that terminal
# and checks that the demo and its helper windows are gone.
#
# Why a real terminal and real keystrokes: LED demos run under sudo, which puts
# the terminal in raw mode and forwards the keystroke into its own pty, so a
# SIGINT sent from outside does not behave like the key; and Jupyter needs the
# key twice. The keystroke is injected into the terminal's input queue
# (TIOCSTI, as root) rather than typed with a keyboard tool, because demos that
# open a window (SenseHAT emulator, browser) take the keyboard focus.
# Usage: demo_smoke.sh <demo-id[:variant]> [seconds] [out-dir]
# Prints one line: "<PASS|FAIL|SKIP> demo:<id> | <detail>"
# Env: RIG_ALLOW_DOCKER=1 also runs docker demos (large image pulls).
#      RIG_KEYS="<delay>:<keys> ..." types keys into the demo (see below).

spec="$1"; secs="${2:-30}"; out="${3:-/tmp/rigtest}"
id="${spec%%:*}"; variant=""; [ "$spec" != "$id" ] && variant="${spec#*:}"
mkdir -p "$out"
manifest=$(ls /usr/config/demo-manifests/rq_demo_"$id".json "$HOME"/.local/config/demo-manifests/rq_demo_"$id".json 2>/dev/null | head -1)
[ -n "$manifest" ] || { echo "FAIL demo:$spec | no manifest"; exit 0; }
type=$(jq -r '.entrypoint.type // "?"' "$manifest")
mapfile -t helpers < <(jq -r '.entrypoint.stop_on_exit[]? // empty' "$manifest")
name="$id${variant:+-$variant}"
log="$out/$name.log"; shot="$out/$name.png"

if [ "$type" = docker ] && [ "${RIG_ALLOW_DOCKER:-0}" != 1 ]; then
    echo "SKIP demo:$spec | docker demo (set RIG_ALLOW_DOCKER=1)"; exit 0
fi

export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u)
rm -f "$log"
cmd="rq_demo_run.sh $id${variant:+ $variant}"
setsid lxterminal -t "RIGTEST-$name" -e script -qfc "$cmd" "$log" >/dev/null 2>&1 &
sleep 3
spid=$(pgrep -f "^script -qfc $cmd( |$)" | head -1)
tpid=$(pgrep -f "^lxterminal -t RIGTEST-$name " | head -1)

gone() { ! kill -0 "$spid" 2>/dev/null; }
# type <bytes> into the demo's terminal, as if pressed on its keyboard
press() {
    local tty; tty=$(ps -o tty= -p "$spid" 2>/dev/null | tr -d ' ')
    [ -n "$tty" ] && [ "$tty" != "?" ] || return 1
    sudo python3 -c 'import fcntl, os, sys, termios
fd = os.open("/dev/" + sys.argv[1], os.O_RDWR)
for ch in sys.argv[2].encode().decode("unicode_escape").encode("latin-1"):
    fcntl.ioctl(fd, termios.TIOCSTI, bytes([ch]))' "$tty" "$1"
}
# scripted input (RIG_KEYS="<delay>:<keys> ...", e.g. "5:\\r 2:\\r"): answers a
# demo's dialogs the way a person would, so it gets to its LED output
if [ -n "${RIG_KEYS:-}" ]; then
    ( for item in $RIG_KEYS; do sleep "${item%%:*}"; press "${item#*:}"; done ) &
fi

sleep "$secs"
grim -s 0.5 "$shot" 2>/dev/null || true
alive=no; [ -n "$spid" ] && kill -0 "$spid" 2>/dev/null && alive=yes
errors=$(tr -d '\r' < "$log" 2>/dev/null | grep -av '^INFO' | grep -avE '^\[[0-9]+:[0-9]+:[0-9]+/' | grep -aE 'Traceback|ERROR:|Error:|GPIO busy|No module named|Bus error|Segmentation fault|core dumped' | head -2 | tr '\n' ' ' | cut -c1-160)
# a whiptail dialog is on screen (box drawing in the terminal output)
dialog=no; grep -aq '┌' "$log" 2>/dev/null && dialog=yes
exitcode=$(tr -d '\r' < "$log" 2>/dev/null | sed -n 's/.*COMMAND_EXIT_CODE="\([0-9]*\)".*/\1/p' | tail -1)
http=""
if [ "$type" = jupyter ]; then
    url=$(tr -d '\r' < "$log" | grep -aoE 'http://(localhost|127\.0\.0\.1):[0-9]+/[^ ]*' | head -1)
    [ -n "$url" ] && http=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url")
fi
if [ "$type" = browser ] || [ "$type" = web-static ]; then
    url=$(tr -d '\r' < "$log" | grep -aoE 'https?://[^ ]+' | head -1)
    [ -n "$url" ] && http=$(curl -sL -o /dev/null -w '%{http_code}' --max-time 15 "$url")
fi

stopped="n/a"
if [ "$alive" = yes ]; then
    press '\x03'
    [ "$type" = jupyter ] && { sleep 1; press '\x03'; }
    for _ in $(seq 1 15); do gone && break; sleep 1; done
    if ! gone; then  # a launcher may wait for Enter after the demo stopped
        press '\r'
        for _ in $(seq 1 10); do gone && break; sleep 1; done
    fi
    if ! gone && [ "$dialog" = yes ]; then  # whiptail: Escape cancels, Ctrl+C does not
        press '\x1b'; sleep 1; press '\x1b'
        for _ in $(seq 1 10); do gone && break; sleep 1; done
    fi
    left=""
    gone || left="demo "
    for pat in "${helpers[@]}"; do pgrep -f -- "$pat" >/dev/null && left="$left$(basename "$pat") "; done
    stopped=${left:-clean}
fi

# leave nothing behind for the next demo (explicit PIDs and patterns only)
[ -n "$spid" ] && sudo pkill -9 -P "$spid" 2>/dev/null
[ -n "$spid" ] && sudo kill -9 "$spid" 2>/dev/null
sudo pkill -9 -f "rq_demo_run.sh $id( |$)" 2>/dev/null
for pat in "${helpers[@]}"; do sudo pkill -9 -f -- "$pat" 2>/dev/null; done
[ -n "$tpid" ] && kill "$tpid" 2>/dev/null

dlg=""; [ "$dialog" = yes ] && dlg=" dialog=yes"
detail="type=$type ran=${secs}s alive=$alive$dlg stop=$stopped${exitcode:+ exit=$exitcode}${http:+ http=$http}${errors:+ errors: $errors}"
verdict=PASS
case "$type" in
    python|script|jupyter)
        if [ "$alive" = yes ]; then
            [ "$stopped" = clean ] || verdict=FAIL
        elif [ "$exitcode" != 0 ]; then
            verdict=FAIL   # ended by itself, but not successfully
        fi ;;
esac
[ -n "$errors" ] && verdict=FAIL
case "$http" in ""|2*|3*) ;; *) verdict=FAIL ;; esac
echo "$verdict demo:$spec | $detail"
