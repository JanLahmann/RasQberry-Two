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
# Prints one line: "<PASS|FAIL|WARN|SKIP> demo:<id> | <detail>"
#   (icon:<file.desktop> instead of demo:<id> with RIG_ICON)
# Env: RIG_ALLOW_DOCKER=1 also runs docker demos (large image pulls).
#      RIG_KEYS="<delay>:<keys> ..." types keys into the demo (see below).
#      RIG_ICON=<file.desktop> starts the demo by double-clicking its desktop
#        icon with a real (uinput) mouse instead of a terminal command;
#        RIG_ICON_OFFSET="dx,dy" (default 60,67) is the icon's centre from
#        its position in pcmanfm's desktop-items-0.conf.
#      RIG_CDP_PORT=9222 checks web/Jupyter pages in the desktop Chromium
#        (started with remote debugging by webcheck.py browser-debug) and
#        closes the demo's tabs; RIG_WEB='{"title":text,"wait":sel,"click":sel}'
#        hints (with RIG_WEB, a script demo's page is checked too). Around the
#        check, ~/.qiskit/qiskit-ibm.json is backed up and put back if changed.

spec="$1"; secs="${2:-30}"; out="${3:-/tmp/rigtest}"
id="${spec%%:*}"; variant=""; [ "$spec" != "$id" ] && variant="${spec#*:}"
mkdir -p "$out"
manifest=$(ls /usr/config/demo-manifests/rq_demo_"$id".json "$HOME"/.local/config/demo-manifests/rq_demo_"$id".json 2>/dev/null | head -1)
[ -n "$manifest" ] || { echo "FAIL demo:$spec${RIG_ICON:+ (icon $RIG_ICON)} | no manifest"; exit 0; }
# a variant may start something else than its demo (Fun with Quantum: the
# notebooks are Jupyter, the website variant is a script that opens a page)
type=$(jq -r --arg v "$variant" '(if $v != "" then ([.variants[]? | select(.id == $v) | .entrypoint.type // empty] | first) else null end) // .entrypoint.type // "?"' "$manifest")
mapfile -t helpers < <(jq -r '.entrypoint.stop_on_exit[]? // empty' "$manifest")
name="$id${variant:+-$variant}"
label="demo:$spec"
[ -n "${RIG_ICON:-}" ] && { name="icon-$name"; label="icon:$RIG_ICON"; }
log="$out/$name.log"; shot="$out/$name.png"

if [ "$type" = docker ] && [ "${RIG_ALLOW_DOCKER:-0}" != 1 ]; then
    echo "SKIP $label | docker demo (set RIG_ALLOW_DOCKER=1)"; exit 0
fi

export DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/$(id -u)
# rig starts are not counted (rq_umami_event.py; the harness also sets it in
# the environment file, for the desktop icons)
export RQ_UMAMI=0
hpid=""; launched=""
# Browser checks (webcheck.py) when the harness turned on Chromium's remote
# debugging (RIG_CDP_PORT): note the open tabs, to find and close the demo's
VPY="$HOME/RasQberry-Two/venv/RQB2/bin/python"
webcheck() { RIG_OUT="$out" timeout 300 "$VPY" "$out/webcheck.py" "$@" 2>/dev/null; }

# The web check runs notebook code. Besides its own credential filter: keep a
# root-only copy (mode 600) of the saved IBM Quantum account and put it back
# if anything changed it - the check once ran a credentials notebook and
# replaced the real API key on both rig Pis. Never print the file's content.
qfile="$HOME/.qiskit/qiskit-ibm.json"
qbak="$out/qiskit-backup"
qsum=""; qmeta=""; qnote=""
qiskit_backup() {
    sudo rm -rf "$qbak"
    [ -f "$qfile" ] || return 0
    qmeta=$(stat -L -c '%u:%g %a' "$qfile")
    if sudo install -d -m 700 -o root -g root "$qbak" &&
       sudo install -m 600 -o root -g root "$qfile" "$qbak/qiskit-ibm.json"; then
        qsum=$(sudo sha256sum "$qfile" | cut -d' ' -f1)
        trap qiskit_restore EXIT; trap 'exit 129' HUP; trap 'exit 143' TERM
    else
        qnote="qiskit-backup=failed "
    fi
}
qiskit_restore() {
    [ -n "$qsum" ] || return 0
    if [ "$(sudo sha256sum "$qfile" 2>/dev/null | cut -d' ' -f1)" != "$qsum" ]; then
        mkdir -p "$(dirname "$qfile")"
        if sudo cp "$qbak/qiskit-ibm.json" "$qfile" && sudo chown "${qmeta% *}" "$qfile" &&
           sudo chmod "${qmeta#* }" "$qfile"; then
            qnote="restored ~/.qiskit after $spec "
        else
            qnote="COULD NOT restore ~/.qiskit after $spec (root-only copy kept in $qbak) "
            qsum=""; return 0
        fi
    fi
    sudo rm -rf "$qbak"
    qsum=""
}
[ -n "${RIG_CDP_PORT:-}" ] && webcheck tabs "$out/$name.tabs"
if [ -n "${RIG_ICON:-}" ]; then
    # Double-click the icon, as a person does. Its position comes from the
    # desktop layout; the icon command runs under rq_hold_on_error.sh, whose
    # script(1) copies the demo's output to ~/.cache/rasqberry/<name>.log.
    desk="$HOME/Desktop/$RIG_ICON"
    conf="$HOME/.config/pcmanfm/LXDE-pi/desktop-items-0.conf"
    [ -f "$desk" ] || { echo "FAIL $label | no such desktop icon"; exit 0; }
    pos=$(awk -v s="[$RIG_ICON]" '$0==s{f=1;next} /^\[/{f=0} f&&/^x=/{x=substr($0,3)} f&&/^y=/{y=substr($0,3)} END{if(x!=""&&y!="")print x, y}' "$conf" 2>/dev/null)
    [ -n "$pos" ] || { echo "FAIL $label | no position in $conf"; exit 0; }
    read -r ix iy <<< "$pos"
    off="${RIG_ICON_OFFSET:-60,67}"
    cx=$((ix + ${off%,*})); cy=$((iy + ${off#*,}))
    read -r sw sh < <(wlr-randr 2>/dev/null | awk '/current/{split($1,a,"x"); print a[1], a[2]; exit}')
    # the log name rq_hold_on_error.sh uses: the demo id (-variant), else the command
    logname=$(python3 -c 'import os, shlex, sys
w = shlex.split(sys.argv[1])
if w and w[0].endswith("rq_hold_on_error.sh"):
    w = w[3:] if w[1:2] == ["-t"] else w[1:]
n = os.path.basename(w[0]) if w else ""
n = n[:-3] if n.endswith(".sh") else n
print("-".join(w[1:3]) if n == "rq_demo_run" and len(w) > 1 else n)' "$(sed -n 's/^Exec=//p' "$desk" | head -1)")
    log="${XDG_CACHE_HOME:-$HOME/.cache}/rasqberry/$logname.log"
    sudo python3 "$out/mouse.py" dblclick "$cx" "$cy" "${sw:-1920}" "${sh:-1080}"
    spid=""
    for _ in $(seq 1 20); do
        spid=$(pgrep -n -f "^script -qefc .* ${log}\$")
        [ -n "$spid" ] && break
        sleep 1
    done
    if [ -z "$spid" ]; then
        grim -c -s 0.5 "$shot" 2>/dev/null || true
        echo "FAIL $label | double-click at $cx,$cy started nothing (no script for $log)"
        exit 0
    fi
    hpid=$(ps -o ppid= -p "$spid" 2>/dev/null | tr -d ' ')   # rq_hold_on_error.sh
    tpid=""
    launched="launched=dblclick@$cx,$cy "
else
    rm -f "$log"
    cmd="rq_demo_run.sh $id${variant:+ $variant}"
    setsid lxterminal -t "RIGTEST-$name" -e script -qfc "$cmd" "$log" >/dev/null 2>&1 &
    sleep 3
    spid=$(pgrep -f "^script -qfc $cmd( |$)" | head -1)
    tpid=$(pgrep -f "^lxterminal -t RIGTEST-$name " | head -1)
fi

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
# answers by a dialog's text (RIG_ANSWERS="<text>|<keys>;..."): each is pressed
# once, two seconds after its text first shows in the demo's log - for dialogs
# that come after a first-start download, when a timer would be long gone
if [ -n "${RIG_ANSWERS:-}" ]; then
    # (a counter, not $(seq ...): with IFS=';' that would be one word, one pass)
    ( IFS=';'; set -f; pending="$RIG_ANSWERS"; tries=0
      while [ "$tries" -lt 900 ]; do
          tries=$((tries + 1))
          [ -n "$pending" ] || break
          kill -0 "$spid" 2>/dev/null || break   # the demo has ended: nothing left to answer
          next=""
          for answer in $pending; do
              [ -n "$answer" ] || continue
              if grep -aqF -- "${answer%%|*}" "$log" 2>/dev/null; then
                  sleep 2; press "${answer#*|}"   # 1 s was too early for whiptail
              else
                  next="$next$answer;"
              fi
          done
          pending="$next"; sleep 1
      done ) &
fi

# First start of a demo that is not installed yet: the consent dialog asks
# "Download now?" (default button: Download). Answer it like a person and give
# the install time to finish before the run timer starts (up to 10 min).
consent=""
for _ in $(seq 1 10); do
    grep -aq "is not on this Pi yet" "$log" 2>/dev/null && { consent=yes; break; }
    sleep 1
done
if [ -n "$consent" ]; then
    press '\r'
    for _ in $(seq 1 300); do
        kill -0 "$spid" 2>/dev/null || break
        tr -d '\r' < "$log" 2>/dev/null | grep -aqE "Delegating to:|Starting|Running|Launching|Using port|Press Ctrl\+C" && break
        sleep 2
    done
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
if [ "$type" = browser ] || [ "$type" = web-static ] || { [ "$type" = script ] && [ -n "${RIG_WEB:-}" ]; }; then
    # a script's log may name other sites first (a download dialog): its own
    # local page wins
    [ "$type" = script ] && url=$(tr -d '\r' < "$log" | grep -aoE 'http://(localhost|127\.0\.0\.1):[0-9]+/[^ ]*' | head -1)
    [ -n "${url:-}" ] || url=$(tr -d '\r' < "$log" | grep -aoE 'https?://[^ ]+' | head -1)
    [ -n "$url" ] && http=$(curl -sL -o /dev/null -w '%{http_code}' --max-time 15 "$url")
fi
# Does the page work, not just answer? Check the demo's own tab (webcheck.py:
# loads, a key control responds; Jupyter: the first safe code cell runs)
web=""
if [ -n "${RIG_CDP_PORT:-}" ]; then
    check=""
    case "$type" in
        jupyter|browser|web-static|docker) check=yes ;;
        script) [ -n "${RIG_WEB:-}" ] && check=yes ;;   # a script that opens a page
    esac
    if [ -n "$check" ]; then
        [ "$type" = docker ] && url=$(tr -d '\r' < "$log" | grep -aoE 'http://(localhost|127\.0\.0\.1):[0-9]+/[^ ]*' | head -1)
        qiskit_backup
        web=$(webcheck check "$type" "$out/$name.tabs" "${url:-}" "${RIG_WEB:-}" | grep -a '^web=' | tail -1)
        [ -n "$web" ] || web="web=fail the check gave no answer (timeout?)"
    fi
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
# an icon's rq_hold_on_error.sh may wait for Enter after a failure: end it
# (its window closes with it)
[ -n "$hpid" ] && kill "$hpid" 2>/dev/null
# and close the tabs the demo opened
[ -n "${RIG_CDP_PORT:-}" ] && webcheck close-new "$out/$name.tabs" >/dev/null
# the demo and its kernels are gone: put the IBM Quantum account back if changed
qiskit_restore

dlg=""; [ "$dialog" = yes ] && dlg=" dialog=yes"
detail="${qnote}${launched}type=$type ran=${secs}s${consent:+ installed=first-start} alive=$alive$dlg stop=$stopped${exitcode:+ exit=$exitcode}${http:+ http=$http}${web:+ $web}${errors:+ errors: $errors}"
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
case "$web" in
    web=fail*) verdict=FAIL ;;
    web=warn*) [ "$verdict" = PASS ] && verdict=WARN ;;
esac   # web=info: fine (e.g. an empty JupyterLab workspace)
case "$qnote" in
    COULD*) verdict=FAIL ;;
    ?*) [ "$verdict" = PASS ] && verdict=WARN ;;   # something changed the account
esac
echo "$verdict $label | $detail"
