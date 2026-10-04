#!/usr/bin/env python3
"""
RasQberry rig test (issue #234): test a real image on the test Pis.

Runs from a machine on the rig's network (not in CI: the Pis and the camera
are on a local LAN). For every Pi in rig.json it

  1. optionally installs a release into the other A/B slot and boots it
     (--update TAG: OTA the release into the slot that is not running),
  2. runs the system checks (tests/rig/pi/checks.sh),
  3. smoke-tests each demo the way a person does - desktop terminal, runs,
     Ctrl+C, nothing left behind (tests/rig/pi/demo_smoke.sh),
  4. for LED demos, checks with the camera that the Pi's panel actually lights,
  5. for web/Jupyter/docker demos, checks the page in the demo's own Chromium
     tab (tests/rig/pi/webcheck.py): it renders, a control responds, a
     notebook's first safe code cell runs - never one that touches the IBM
     Quantum account; ~/.qiskit is backed up and restored around the check,
  6. with --icons, starts demos by double-clicking their desktop icons with a
     real (uinput) mouse (tests/rig/pi/mouse.py),

and writes results/<timestamp>/report.md with screenshots and camera frames.
Exit status 1 if anything failed.

Usage:
    python3 tests/rig/rig_test.py                       # all Pis, all demos
    python3 tests/rig/rig_test.py --pi pi5 --demos quantum-lights-out,rasq-led
    python3 tests/rig/rig_test.py --update beta-2026-09-30-142314
    python3 tests/rig/rig_test.py --checks-only
    python3 tests/rig/rig_test.py --demos none --icons --docker

Needs on this machine: ssh (key login to the Pis), ffmpeg, Python 3 + Pillow.
Needs on the Pis: nothing beyond the image (key login for the rig user).
"""

import argparse
import atexit
import contextlib
import datetime
import fcntl
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
REMOTE_DIR = "/tmp/rigtest"
VENV_PY = "/home/*/RasQberry-Two/venv/RQB2/bin/python3"
CLEAR_LEDS = f"sudo {VENV_PY} /usr/bin/turn_off_LEDs.py >/dev/null 2>&1"
HOLDER_PID = f"{REMOTE_DIR}/led_fill.pid"
CDP_PORT = 9222   # the desktop Chromium's debugging port during web checks (127.0.0.1)
# Rig runs stay out of the project's usage counts (rq_umami_event.py): RQ_UMAMI=0
# in the Pi's environment file reaches demos started from the desktop icons too,
# the health check and the timers, and an update carries it into the new slot
ENV_FILE = "/usr/config/rasqberry_environment.env"
NO_USAGE_COUNTS = (f"grep -qx RQ_UMAMI=0 {ENV_FILE} || {{ sudo sed -i '/^RQ_UMAMI=/d' {ENV_FILE} "
                   f"&& echo RQ_UMAMI=0 | sudo tee -a {ENV_FILE} >/dev/null; }}")


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def ssh(host, command, timeout=600, check=False):
    """Run a command on a Pi; returns (rc, stdout)."""
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
        capture_output=True, text=True, timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"{host}: {command!r} failed: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout


def scp(host, sources, dest):
    """Copy local files to the Pi."""
    subprocess.run(["scp", "-q", *map(str, sources), f"{host}:{dest}"], check=True, timeout=120)


def fetch(host, remote, local):
    """Copy a file from the Pi; ignore missing files."""
    subprocess.run(["scp", "-q", f"{host}:{remote}", str(local)], timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# A demo that needs an IBM Quantum account fails like this when the Pi's saved
# key is missing or invalid: that is the rig's set-up, not the image - WARN
ACCOUNT_ERRORS = re.compile(r"InvalidAccountError|IBMNotAuthorizedError|AccountNotFoundError|"
                            r"Unable to retrieve instances|API key could not be found")


def parse_lines(text):
    """Parse 'VERDICT name | detail' lines into dicts."""
    out = []
    for line in text.splitlines():
        head, _, detail = line.partition(" | ")
        parts = head.split(None, 1)
        if len(parts) == 2 and parts[0] in ("PASS", "FAIL", "WARN", "INFO", "SKIP"):
            verdict, detail = parts[0], detail.strip()
            if verdict == "FAIL" and ACCOUNT_ERRORS.search(detail):
                verdict, detail = "WARN", detail + " (needs a valid IBM Quantum account on this Pi)"
            # the demo's own tab loaded, only the test click timed out (IBM's
            # Composer is heavy for the 2 GB Pi 4): the demo worked
            elif verdict == "FAIL" and "tab=demo" in detail and "check error: TimeoutError" in detail:
                verdict, detail = "WARN", detail + " (page loaded; the test click timed out)"
            out.append({"verdict": verdict, "name": parts[1], "detail": detail})
    return out


def wait_for(host, predicate_cmd, timeout, interval=10):
    """Poll until the command succeeds on the Pi (e.g. after a reboot)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            if ssh(host, predicate_cmd, timeout=30)[0] == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
        time.sleep(interval)
    return False


# ----------------------------------------------------------------------------
# camera
# ----------------------------------------------------------------------------
class Camera:
    """A persistent RTSP reader that keeps one fresh frame on disk (~1 fps)."""

    def __init__(self, url, workdir):
        self.url = url
        self.latest = Path(workdir) / "camera_latest.png"
        self.proc = None

    def start(self):
        """Start ffmpeg and wait for the first frame (keyframe wait ~10 s)."""
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "quiet", "-rtsp_transport", "tcp", "-i", self.url,
             "-vf", "fps=1", "-update", "1", "-y", str(self.latest)],
            stdin=subprocess.DEVNULL,
        )
        # an aborted or killed run must not leave the stream behind: stale
        # readers hold RTSP sessions and garble later runs' frames
        atexit.register(self.stop)
        for _ in range(40):
            if self.latest.exists() and self.latest.stat().st_size > 0:
                return True
            time.sleep(1)
        return False

    def grab(self, dest):
        """Copy the current frame to dest (after ~2 s so it is fresh)."""
        from PIL import Image
        time.sleep(2)
        for _ in range(10):  # ffmpeg rewrites the file in place: retry partial reads
            dest.write_bytes(self.latest.read_bytes())
            try:
                with Image.open(dest) as im:
                    im.load()
                return dest
            except OSError:
                time.sleep(0.3)
        raise RuntimeError("camera: could not read a complete frame")

    def stop(self):
        """Stop ffmpeg (also at exit, and on SIGTERM/SIGHUP via main)."""
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class PanelLock:
    """
    One camera judgement at a time.

    The Pis' panels share the camera view: while one Pi's LED demo is judged,
    no other Pi may light its panel or change it. Held across threads and
    across harness processes run side by side (--pi pi5 & --pi pi4).
    """

    def __init__(self):
        self.path = Path(tempfile.gettempdir()) / "rasqberry-rigtest-panels.lock"
        self.local = threading.Lock()
        self.fh = None

    def __enter__(self):
        self.local.acquire()
        self.fh = open(self.path, "w")
        fcntl.flock(self.fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.fh, fcntl.LOCK_UN)
        self.fh.close()
        self.local.release()


PANEL_LOCK = PanelLock()


def clear_all_panels(pis):
    """
    Switch every Pi's LEDs off (in parallel).

    Returns:
        list: names of the Pis whose panel could not be cleared.
    """
    failed = []

    def one(p):
        try:
            if ssh(p["host"], CLEAR_LEDS, timeout=60)[0] != 0:
                failed.append(p["name"])
        except subprocess.TimeoutExpired:
            failed.append(p["name"])

    threads = [threading.Thread(target=one, args=(p,)) for p in pis]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return failed


def fresh_baseline(pis, camera, dest):
    """
    A frame with every panel off, taken now.

    A baseline from the start of the run goes stale: daylight and the camera's
    auto exposure drift, and a stale one made a dark panel score 0.01-0.04
    ("partly lit"). Take it right before each judgement, under PANEL_LOCK.

    Returns:
        tuple: (frame path, list of Pis that could not be cleared)
    """
    failed = clear_all_panels(pis)
    time.sleep(3)   # last frame out, camera exposure settled
    return camera.grab(dest), failed


def lit_score(frame, baseline, crop):
    """
    How much brighter the panel region is than with the LEDs off.

    Args:
        frame, baseline (Path): camera frames with the demo running / LEDs off.
        crop (list): [x1, y1, x2, y2] as fractions of the frame size.

    Returns:
        float: share of pixels in the crop that got clearly brighter (0..1).
    """
    from PIL import Image, ImageChops
    a, b = Image.open(frame).convert("L"), Image.open(baseline).convert("L")
    w, h = a.size
    box = tuple(int(v * (w if i % 2 == 0 else h)) for i, v in enumerate(crop))
    diff = ImageChops.subtract(a.crop(box), b.crop(box))
    hist = diff.histogram()
    bright = sum(hist[40:])
    return bright / max(1, sum(hist))


# ----------------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------------
def no_usage_counts(pi):
    """Switch the usage counts off on this Pi (NO_USAGE_COUNTS)."""
    if ssh(pi["host"], NO_USAGE_COUNTS, timeout=60)[0] != 0:
        raise RuntimeError("could not set RQ_UMAMI=0 (usage counts off)")


def update_slot(pi, tag):
    """OTA `tag` into the slot that is not running (ping-pong) with this
    repo's updater; the running slot stays as the way back."""
    host = pi["host"]
    rel = subprocess.run(["gh", "api", f"repos/JanLahmann/RasQberry-Two/releases/tags/{tag}",
                          "--jq", '.assets[]|select(.name|endswith("-ab.img.xz"))|.browser_download_url+" "+.digest'],
                         capture_output=True, text=True, check=True).stdout.split()
    url, digest = rel[0], rel[1].split(":", 1)[1]
    # a slot still on trial refuses updates (exit 28): wait for its health check
    if not wait_for(host, "sudo rq_slot_manager.sh status 2>&1 | grep -q 'Slot Status: CONFIRMED'", 600):
        raise RuntimeError("the running slot is not confirmed")
    # the root partition before the update: the new slot is the other one
    # (the same tag may already run here, so the version alone proves nothing)
    _, before = ssh(host, "findmnt -no SOURCE /")
    before = before.strip()
    ssh(host, f"mkdir -p {REMOTE_DIR}/ota", check=True)
    scp(host, [REPO / "RQB2-bin" / f for f in ("rq_update_slot.sh", "rq_slot_manager.sh",
                                               "rq_carry_ssh_identity.sh", "rq_common.sh")],
        f"{REMOTE_DIR}/ota/")
    print(f"  {pi['name']}: installing {tag} into the other slot (15-25 min)")
    # The operator chose the release: the guard's questions (downgrade, last
    # beta/stable slot) are answered yes, as nobody is at the Pi to type them
    ssh(host, f"chmod +x {REMOTE_DIR}/ota/*.sh; sudo setsid nohup {REMOTE_DIR}/ota/rq_update_slot.sh "
              f"{shlex.quote(url)} {shlex.quote(tag)} --sha256 {digest} "
              f"--allow-downgrade --force-replace-safe-slot "
              f"</dev/null >{REMOTE_DIR}/ota.log 2>&1 &", timeout=60)
    time.sleep(120)
    if not wait_for(host, f"grep -qx {shlex.quote(tag)} /etc/rasqberry-version && "
                          f"[ \"$(findmnt -no SOURCE /)\" != {shlex.quote(before)} ]", 3600, interval=30):
        raise RuntimeError("new slot did not come up with the release")
    # the health check confirms the new slot a minute or two after boot; the
    # service may not have started yet when the release first answers
    wait_for(host, "sudo rq_slot_manager.sh status 2>&1 | grep -q 'Slot Status: CONFIRMED'", 600)


def run_checks(pi):
    """Copy the Pi-side scripts and run the system checks."""
    host = pi["host"]
    ssh(host, f"mkdir -p {REMOTE_DIR}", check=True)
    scp(host, [HERE / "pi" / f for f in ("checks.sh", "demo_smoke.sh", "led_fill.py", "mouse.py", "webcheck.py")], f"{REMOTE_DIR}/")
    _, out = ssh(host, f"bash {REMOTE_DIR}/checks.sh", timeout=300)
    return parse_lines(out)


def list_demos(pi):
    """
    Demo ids with their type, LED need and launcher, from the Pi's manifests
    (a variant's own type and launcher win: Fun with Quantum's website variant
    is a script that opens a page, its notebooks are Jupyter).
    """
    # built-in demos, plus demos added from the catalogue (user manifests)
    _, out = ssh(pi["host"], "for f in /usr/config/demo-manifests/rq_demo_*.json "
                             "$HOME/.local/config/demo-manifests/*.json; do [ -f \"$f\" ] || continue; "
                             "jq -r 'select(.id) | . as $m | [$m.entrypoint.type, ($m.needs_hw.leds // false|tostring)] as $c "
                             "| if ([.variants[]?] | length) == 0 then [$m.id] + $c + [$m.entrypoint.launcher // \"\"] "
                             "else ($m.variants[] | [\"\\($m.id):\\(.id)\", (.entrypoint.type // $c[0]), $c[1]] "
                             "+ [.entrypoint.launcher // $m.entrypoint.launcher // \"\"]) end | @tsv' \"$f\"; done")
    demos = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        # a manifest with variants is a menu; each variant is its own demo
        demos.append({"id": parts[0], "type": parts[1], "leds": parts[2] == "true", "launcher": parts[3]})
    return demos


# desktop icons --icons double-clicks by default: an LED demo, a Jupyter
# demo and a docker demo (the docker one runs only with --docker)
DEFAULT_ICONS = "rasq-led.desktop,quantum-paradoxes.desktop,qoffee-maker.desktop"


def icon_demos(pi, icons, demos):
    """
    The demo each desktop icon starts, read from the icon's Exec line.

    Args:
        icons (list): desktop file names, e.g. "rasq-led.desktop".
        demos (list): list_demos() of this Pi.

    Returns:
        list: demo dicts with an "icon" key (unknown icons: id "?").
    """
    out = []
    for icon in icons:
        _, line = ssh(pi["host"], f"sed -n 's/^Exec=//p' ~/Desktop/{shlex.quote(icon)} | head -1")
        words = shlex.split(line.strip()) if line.strip() else []
        spec = None
        runner = [i for i, w in enumerate(words) if w.endswith("rq_demo_run.sh")]
        if runner:
            spec = ":".join(words[runner[0] + 1:runner[0] + 3])
        else:   # a demo's own launcher script
            scripts = {os.path.basename(w) for w in words if w.endswith(".sh")}
            spec = next((d["id"] for d in demos if d["launcher"] and d["launcher"] in scripts), None)
        demo = next((d for d in demos if d["id"] == spec), None)
        if demo is None and spec:   # a menu of variants: the icon asks which
            demo = next(({**d, "id": spec} for d in demos if d["id"].startswith(spec + ":")), None)
        out.append(dict(demo or {"id": "?", "type": "?", "leds": False, "launcher": ""}, icon=icon))
    return out


# Per-demo test hints, for demos a plain "start and watch" cannot judge:
#   keys:    typed into the demo's terminal ("<delay>:<keys>" ...) - accepts the
#            defaults of the text/logo dialogs so the demo reaches its LED output
#   seconds: minimum run time - Lights Out computes its solution before it
#            lights up, which takes ~20 s on a Pi 4
#   dark:    the demo's job is to switch the panel off - lit is the failure.
#            A helper (led_fill.py --hold) lights the panel and keeps holding
#            it, like a program a person forgot; the demo must stop that
#            holder and leave the panel dark (last frame vs. a fresh baseline)
#   service: the panel stays dark by design (Painter starts with an empty
#            canvas), so check instead that the unit driving the LEDs runs at
#            some point (a first start installs the demo first: 90 s)
DEMO_HINTS = {
    "led-demos:text-display": {"keys": r"5:\r 2:\r 2:\r 2:\r"},
    "led-demos:logo-display": {"keys": r"5:\r 2:\r 2:\r 2:\r"},
    "quantum-lights-out:gui": {"seconds": 60},
    "quantum-lights-out:console": {"seconds": 60},
    # a holder owns the panel: Clear LEDs asks "Stop it ...? [Y/n]" - Enter
    "led-demos:clear-leds": {"dark": True, "keys": r"4:\r"},
    "led-painter": {"service": "rasqberry-led-renderer", "seconds": 90},
    # without an IBM account the real backend waits at its account prompt
    "quantum-raspberry-tie:real": {"led_optional": True},
    # web:     what webcheck.py checks on the demo's page - wait: a selector
    #          that must appear; click: the key control; click_at: [x, y] in a
    #          canvas app (negative = from the right/bottom), judged by the
    #          picture changing. Grok Bloch is a Babylon.js canvas: its "X"
    #          gate button sits 140 px from the right edge.
    "grok-bloch:local": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    "grok-bloch:web": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    "grok-bloch-web": {"web": {"wait": "canvas#renderCanvas", "click_at": [-140, 226]}},
    # title: text the page title must have. The Fun with Quantum website is a
    # web page (a script variant of a Jupyter demo), not a Jupyter UI
    "fun-with-quantum:website": {"web": {"title": "Fun with Quantum"}},
    # answers: "<dialog text>|<keys>;..." - pressed when the text shows. The
    # Workshop & Qiskit Server asks how many participants, then shows their
    # addresses and opens its page after Ok
    "doqumentation": {"answers": r"How many participants|\r;Participants open (same|\r"},
}

# a first start installs the demo after the consent dialog: allow for it
INSTALL_ALLOWANCE = 600


def demo_tag(demo):
    """File-name tag of a demo run (as demo_smoke.sh names its files)."""
    return ("icon-" if demo.get("icon") else "") + demo["id"].replace(":", "-")


def browser_debug(pi, on):
    """
    Turn the remote debugging of the Pi's desktop Chromium on (restart it with
    a 127.0.0.1 debugging port, same profile and page) or off again (restore).

    Returns:
        bool: True if debugging is on (web checks possible).
    """
    sub = "browser-debug" if on else "browser-restore"
    rc, out = ssh(pi["host"], f"RIG_OUT={REMOTE_DIR} RIG_CDP_PORT={CDP_PORT} timeout 90 "
                              f"$HOME/RasQberry-Two/venv/RQB2/bin/python {REMOTE_DIR}/webcheck.py {sub}", timeout=120)
    print(f"   {out.strip()}")
    return on and rc == 0


def smoke_demo(pi, demo, seconds, camera, outdir, all_pis, docker):
    """
    Run one demo smoke test; for LED demos judge the panel with the camera.

    A camera-judged LED demo holds PANEL_LOCK for its whole run, so no other
    Pi (thread or harness process) lights its panel in the shared view.
    """
    judged = bool(camera and demo["leds"] and pi.get("panel_crop"))
    with PANEL_LOCK if judged else contextlib.nullcontext():
        return _smoke_demo(pi, demo, seconds, camera if judged else None, outdir, all_pis, docker)


def _smoke_demo(pi, demo, seconds, camera, outdir, all_pis, docker):
    """smoke_demo's body (camera is None unless this demo is camera-judged)."""
    hint = DEMO_HINTS.get(demo["id"], {})
    seconds = max(seconds, hint.get("seconds", 0))
    env = "RIG_ALLOW_DOCKER=1 " if docker else ""
    if hint.get("keys"):
        env += f"RIG_KEYS={shlex.quote(hint['keys'])} "
    if hint.get("answers"):
        env += f"RIG_ANSWERS={shlex.quote(hint['answers'])} "
    if pi.get("web_check"):
        env += f"RIG_CDP_PORT={CDP_PORT} "
        if hint.get("web"):
            env += f"RIG_WEB={shlex.quote(json.dumps(hint['web']))} "
    if demo.get("icon"):
        env += f"RIG_ICON={shlex.quote(demo['icon'])} "
        if pi.get("icon_offset"):
            env += f"RIG_ICON_OFFSET={pi['icon_offset'][0]},{pi['icon_offset'][1]} "
    tag = demo_tag(demo)
    crop = pi.get("panel_crop")
    notes = ""
    if demo.get("leds"):
        # A Pi 5 LED stall offers "Lower to 0.2?" in the demo's terminal, and
        # scripted Enter keys answer it with the default: restore the shipped
        # brightness so later LED checks are judged at the same level
        _, level = ssh(pi["host"], "rq_led_brightness.sh --show 2>/dev/null | sed -n 's/.*level=//p'")
        if level.strip() and level.strip() != "normal":
            ssh(pi["host"], "sudo rq_led_brightness.sh --set normal >/dev/null 2>&1")
            notes += f" (brightness was {level.strip()}: reset to normal - a stall dialog answered?)"

    baseline = before = None
    holding = False
    try:
        # a fresh baseline right before the demo: every panel off, now
        if camera and not hint.get("service"):
            baseline, unclear = fresh_baseline(all_pis, camera, outdir / f"{pi['name']}-{tag}-baseline.png")
            if unclear:
                notes += f" (baseline: could not clear {','.join(unclear)})"
            if hint.get("dark"):
                # a program holds the panel lit, as when a person picks Clear
                # LEDs: the demo must stop it and leave the panel dark (and
                # the camera is shown to see this Pi's panel at all)
                holding = True
                before = start_holder(pi, camera, baseline, outdir / f"{pi['name']}-{tag}-before.png",
                                      seconds + INSTALL_ALLOWANCE)
        return _run_and_judge(pi, demo, hint, seconds, camera, outdir, env, baseline, before, notes)
    finally:
        if holding:
            stop_holder(pi)   # always: it must never outlive the check


def start_holder(pi, camera, baseline, dest, hold):
    """
    Light the Pi's panel with a helper that keeps holding it (led_fill.py
    --hold), and wait until the camera sees it lit.

    Returns:
        float: the lit score of the last frame (below the threshold: the
            panel never lit).
    """
    ssh(pi["host"], f"sudo rm -f {HOLDER_PID}; sudo setsid nohup {VENV_PY} {REMOTE_DIR}/led_fill.py "
                    f"--hold {int(hold)} --pidfile {HOLDER_PID} 0 60 0 >{REMOTE_DIR}/led_fill.log 2>&1 </dev/null &",
        timeout=60)
    score, end = 0.0, time.time() + 20
    while time.time() < end:
        score = lit_score(camera.grab(dest), baseline, pi["panel_crop"])
        if score >= pi.get("lit_threshold", 0.006):
            break
    return score


def holder_alive(pi):
    """True while the led_fill.py holder still runs on the Pi."""
    return ssh(pi["host"], f"p=$(cat {HOLDER_PID} 2>/dev/null) && grep -qa led_fill /proc/$p/cmdline 2>/dev/null",
               timeout=30)[0] == 0


def stop_holder(pi):
    """Kill the led_fill.py holder (by its pid file; never by pattern)."""
    ssh(pi["host"], f"p=$(cat {HOLDER_PID} 2>/dev/null); [ -n \"$p\" ] && grep -qa led_fill /proc/$p/cmdline 2>/dev/null "
                    f"&& sudo kill -9 $p; sudo rm -f {HOLDER_PID}; true", timeout=30)


def _run_and_judge(pi, demo, hint, seconds, camera, outdir, env, baseline, before, notes):
    """Run the demo (demo_smoke.sh), sample the camera, and judge."""
    host = pi["host"]
    result = {}
    tag = demo_tag(demo)
    crop = pi.get("panel_crop")
    threshold = pi.get("lit_threshold", 0.006)

    def worker():
        _, out = ssh(host, f"{env}bash {REMOTE_DIR}/demo_smoke.sh {shlex.quote(demo['id'])} {seconds} {REMOTE_DIR}",
                     timeout=seconds + INSTALL_ALLOWANCE + 180)
        parsed = parse_lines(out)
        name = f"icon:{demo['icon']}" if demo.get("icon") else f"demo:{demo['id']}"
        result.update(parsed[0] if parsed else {"verdict": "FAIL", "name": name, "detail": out.strip()[:200]})

    t = threading.Thread(target=worker)
    t.start()
    led = None
    service_state = None
    if hint.get("service"):
        end = time.time() + seconds - 5
        while time.time() < end and t.is_alive():
            _, service_state = ssh(host, f"systemctl is-active {hint['service']}")
            service_state = service_state.strip() or "unknown"
            if service_state == "active":
                break
            time.sleep(3)
        service_state = service_state or "not checked"
    elif baseline:
        # LED demos blink, animate and (on a Pi 4) take a while to import
        # Qiskit: sample every couple of seconds for the whole run, keep the best
        best, kept, last = -1.0, None, -1.0
        end = time.time() + seconds - 2 + (0 if hint.get("dark") else INSTALL_ALLOWANCE)
        time.sleep(4)
        i = 0
        while time.time() < end and t.is_alive():
            frame = camera.grab(outdir / f"{pi['name']}-{tag}-camera{i}.png")
            score = lit_score(frame, baseline, crop)
            last = score
            if score > best:
                if kept:
                    kept.unlink()
                best, kept = score, frame
            elif hint.get("dark"):   # keep the last frame: it is the one judged
                if kept:
                    kept.unlink()
                kept = frame
            else:
                frame.unlink()
            i += 1
        if kept:
            kept.rename(outdir / f"{pi['name']}-{tag}-camera.png")
        # a demo that switches the panel off is judged by where it ends up
        led = (last if hint.get("dark") else best) if best >= 0 else None
    t.join()
    holder = None
    if before is not None:
        holder = "still running" if holder_alive(pi) else "stopped"
    fetch(host, f"{REMOTE_DIR}/{tag}.png", outdir / f"{pi['name']}-{tag}-screen.png")
    if service_state is not None:
        result["detail"] = result.get("detail", "") + f" {hint['service']}={service_state}"
        if service_state != "active" and result.get("verdict") == "PASS":
            result["verdict"] = "FAIL"
    if led is not None:
        lit = led >= threshold
        detail = result.get("detail", "")
        if hint.get("dark"):
            result["detail"] = (detail + f" before={before:.3f} led={led:.3f}"
                                + (" (panel still lit)" if lit else " (panel off)")
                                + f" holder={holder}" + notes)
            if (lit or holder != "stopped") and result.get("verdict") == "PASS":
                result["verdict"] = "FAIL"
            elif before < threshold and result.get("verdict") == "PASS":
                # the panel never lit: nothing was shown to be switched off
                result["detail"] += " (could not light the panel first: check panel_crop)"
                result["verdict"] = "WARN"
            return result
        waits = "dialog=yes" in detail            # waiting for input: nothing to show
        ended = "alive=no" in detail and "exit=0" in detail   # finished by itself
        result["detail"] = detail + f" led={led:.3f}" + ("" if lit else " (panel dark)") + notes
        if not lit and hint.get("led_optional"):
            result["detail"] += " (expected without an IBM account)"
        elif not lit and result.get("verdict") == "PASS":
            result["verdict"] = "WARN" if (waits or ended) else "FAIL"
    return result


def run_demos(pi, demos, section, args, camera, outdir, cfg):
    """Smoke-test each demo (menu demos and icons) and add its report row."""
    for d in demos:
        label = f"icon:{d['icon']}" if d.get("icon") else f"demo:{d['id']}"
        print(f"   {label} ...", flush=True)
        if d["id"] == "?":
            section["rows"].append({"verdict": "FAIL", "name": label, "detail": "no demo found for this icon"})
            continue
        try:
            section["rows"].append(smoke_demo(pi, d, args.seconds, camera, outdir, cfg["pis"], args.docker))
        except Exception as exc:  # one broken demo must not end the run
            section["rows"].append({"verdict": "FAIL", "name": label, "detail": f"harness: {exc}"})


# ----------------------------------------------------------------------------
def main():
    # SIGTERM/SIGHUP (a killed or closed run) end through sys.exit, so the
    # atexit handlers run and the camera stream stops
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(HERE / "rig.json"))
    ap.add_argument("--pi", help="comma-separated Pi names from rig.json (default: all)")
    ap.add_argument("--demos", default="all", help="comma-separated demo ids, 'all' or 'none'")
    ap.add_argument("--seconds", type=int, default=30, help="how long each demo runs")
    ap.add_argument("--docker", action="store_true", help="also run docker demos")
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--checks-only", action="store_true")
    ap.add_argument("--update", metavar="TAG", help="first install this release into the other slot (A/B images)")
    ap.add_argument("--no-web-check", action="store_true",
                    help="don't check web/Jupyter pages in the desktop Chromium (and don't restart it)")
    ap.add_argument("--icons", nargs="?", const=DEFAULT_ICONS, metavar="FILES",
                    help="also start demos by double-clicking their desktop icons with a real (uinput) "
                         f"mouse; comma-separated .desktop names (default: {DEFAULT_ICONS})")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    pis = cfg["pis"]
    if args.pi:
        wanted = args.pi.split(",")
        pis = [p for p in pis if p["name"] in wanted]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = HERE / "results" / stamp
    outdir.mkdir(parents=True)

    camera = None
    if not args.no_camera and cfg.get("camera_url") and not args.checks_only:
        camera = Camera(cfg["camera_url"], outdir)
        if not camera.start():
            print("camera: no frame - LED checks skipped")
            camera = None

    report, failed = [], False
    try:
        for pi in pis:
            print(f"== {pi['name']} ({pi['host']})")
            section = {"pi": pi["name"], "rows": []}
            report.append(section)
            try:
                no_usage_counts(pi)
                if args.update:
                    update_slot(pi, args.update)
                    no_usage_counts(pi)     # the new slot (carried over since this release)
                section["rows"] += run_checks(pi)
                if not args.checks_only:
                    every = list_demos(pi)
                    demos = [] if args.demos == "none" else every
                    if args.demos not in ("all", "none"):
                        wanted = args.demos.split(",")
                        # a base id selects all its variants (id:variant)
                        demos = [d for d in demos if d["id"] in wanted or d["id"].split(":")[0] in wanted]
                    if args.icons:
                        demos += icon_demos(pi, args.icons.split(","), every)
                    # web checks: the desktop Chromium with remote debugging,
                    # restored when this Pi is done
                    pi["web_check"] = (not args.no_web_check and any(
                        d["type"] in ("jupyter", "browser", "web-static", "docker")
                        or DEMO_HINTS.get(d["id"], {}).get("web") for d in demos)
                        and browser_debug(pi, True))
                    try:
                        run_demos(pi, demos, section, args, camera, outdir, cfg)
                    finally:
                        if pi["web_check"]:
                            browser_debug(pi, False)
            except Exception as exc:  # keep going with the next Pi
                section["rows"].append({"verdict": "FAIL", "name": "run", "detail": str(exc)})
            for r in section["rows"]:
                print(f"   {r['verdict']:<4} {r['name']:<34} {r['detail']}")
                failed |= r["verdict"] == "FAIL"
    finally:
        if camera:
            camera.stop()

    lines = [f"# RasQberry rig test {stamp}", ""]
    for s in report:
        n = {v: sum(r["verdict"] == v for r in s["rows"]) for v in ("PASS", "FAIL", "WARN", "SKIP")}
        lines += [f"## {s['pi']}: {n['PASS']} pass, {n['FAIL']} fail, {n['WARN']} warn, {n['SKIP']} skipped", "",
                  "| | Check | Detail |", "|---|---|---|"]
        lines += [f"| {r['verdict']} | {r['name']} | {r['detail'].replace('|', '/')} |" for r in s["rows"]]
        lines.append("")
    (outdir / "report.md").write_text("\n".join(lines))
    print(f"\nReport: {outdir / 'report.md'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
