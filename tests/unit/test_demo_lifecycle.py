"""
Tests for feedback batch C2 (2026-10-03): how demos stop, LEDs and Docker.

- one stop rule for every demo window: Enter or Ctrl+C, or closing the window
  (items 5, 33); Docker demos stop with their window, the Workshop & Qiskit Server
  keeps running by design;
- LED launchers clear the panel once, however they end (R-158);
- the Pi 5 LED driver stall is noticed, the driver reopened and the person
  offered a lower brightness - never lowered silently (item 31);
- the consent dialog of a Docker demo says that its image stays in the
  running slot and what fits on a 16 GB card (item 32);
- Fun with Quantum lists its notebooks from the manifest (item 10).
"""

import importlib.util
import os
import pty
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import time
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_ENV_CONFIG = os.path.join(_CFG, "rasqberry_env-config.sh")
_ENV = os.path.join(_CFG, "rasqberry_environment.env")

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _read(name):
    with open(os.path.join(_BIN, name), encoding="utf-8") as fh:
        return fh.read()


class _Pty:
    """bash -c SCRIPT on a pseudo terminal, as in a demo's window."""

    def __init__(self, script, env=None):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # pragma: no cover - child
            os.execvpe("bash", ["bash", "-c", script], dict(os.environ, **(env or {})))
        self.out = b""

    def read_until(self, text, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if text.encode() in self.out:
                return True
            r, _, _ = select.select([self.fd], [], [], 0.2)
            if r:
                try:
                    self.out += os.read(self.fd, 4096)
                except OSError:
                    break
        return text.encode() in self.out

    def send(self, data):
        os.write(self.fd, data.encode())

    def wait(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                try:
                    while select.select([self.fd], [], [], 0)[0]:
                        chunk = os.read(self.fd, 4096)
                        if not chunk:
                            break
                        self.out += chunk
                except OSError:
                    pass
                return os.waitstatus_to_exitcode(status)
            r, _, _ = select.select([self.fd], [], [], 0.2)
            if r:
                try:
                    self.out += os.read(self.fd, 4096)
                except OSError:
                    pass
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        raise AssertionError("did not end: " + self.out.decode(errors="replace"))


# --- one stop rule (items 5, 33) -------------------------------------------------

@needs_bash
def test_stop_hint_wording():
    out = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_stop_hint "Quantum Lab"; '
                                        'rq_stop_hint "Lights Out" keys'],
                         capture_output=True, text=True).stdout.splitlines()
    assert out == ["To stop Quantum Lab: press Enter or Ctrl+C, or close this window.",
                   "To stop Lights Out: press Ctrl+C or close this window."]


@needs_bash
def test_wait_for_stop_ends_on_enter():
    p = _Pty(f'. "{_COMMON}"; sleep 300 & rq_wait_for_stop Demo $!; echo WAITED; kill $!')
    assert p.read_until("To stop Demo: press Enter or Ctrl+C")
    p.send("\r")
    assert p.wait() == 0
    assert b"WAITED" in p.out


@needs_bash
def test_wait_for_stop_ends_when_the_demo_ends():
    p = _Pty(f'. "{_COMMON}"; sleep 1 & rq_wait_for_stop Demo $!; echo WAITED')
    assert p.wait() == 0
    assert b"WAITED" in p.out


@pytest.fixture
def fake_docker(tmp_path):
    """A docker stub: one running container until it is stopped."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    state = tmp_path / "running"
    state.write_text("true")
    log = tmp_path / "docker.log"
    _exe(stubs / "docker", f'''#!/bin/sh
echo "$*" >> "{log}"
case "$1 $2" in
    "container inspect") [ -f "{state}" ] || exit 1; cat "{state}" ;;
    "stop "*|"rm -f") rm -f "{state}" ;;
esac
exit 0
''')
    return stubs, log, state


@needs_bash
@pytest.mark.parametrize("how", ["enter", "ctrl-c", "hangup"])
def test_docker_demo_stops_with_its_window(fake_docker, how):
    stubs, log, state = fake_docker
    env = {"PATH": f"{stubs}:{os.environ['PATH']}"}
    p = _Pty(f'set -euo pipefail; . "{_COMMON}"; '
             'rq_docker_stop_with_window quantum-mixer Quantum-Mixer; echo AFTER', env)
    assert p.read_until("To stop Quantum-Mixer: press Enter or Ctrl+C, or close this window.")
    if how == "enter":
        p.send("\r")
    elif how == "ctrl-c":
        p.send("\x03")
    else:
        os.kill(p.pid, signal.SIGHUP)
    p.wait()
    assert "stop quantum-mixer" in log.read_text()
    assert not state.exists()
    if how == "enter":
        assert b"AFTER" in p.out


@needs_bash
def test_docker_demo_without_a_window_keeps_running(fake_docker):
    stubs, log, state = fake_docker
    out = subprocess.run(
        ["bash", "-c", f'. "{_COMMON}"; rq_docker_stop_with_window quantum-mixer Quantum-Mixer'],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env=dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}"))
    assert "keeps running in the background" in out.stdout
    assert state.exists()
    assert "stop" not in (log.read_text() if log.exists() else "")


def test_docker_launchers_stop_with_their_window():
    for name in ("quantum-mixer.sh", "qoffee-maker.sh", "rq_quantum_lab.sh"):
        text = _read(name)
        assert "rq_docker_stop_with_window" in text, name
        assert "To stop it later" not in text, name
    # the Workshop & Qiskit Server keeps running by design; only its
    # single-user mode (Qiskit Tutorials on this Pi) stops with its window
    doq = _read("rq_doqumentation.sh")
    assert doq.count("rq_docker_stop_with_window") == 1
    solo = doq[doq.index('if [ "$MODE" = "solo" ]; then\n    # Just you'):]
    assert "rq_docker_stop_with_window" in solo[:solo.index("\nfi\n")]


def test_demo_windows_share_one_stop_hint():
    # the old per-launcher wordings are gone from the windows people see
    old = re.compile(r'echo "Press (Ctrl\+C to stop|Enter to stop|Enter \(or Ctrl\+C\))')
    for name in ("rq_fun_with_quantum.sh", "rq_ibm_courses.sh", "rq_ibm_tutorials.sh",
                 "rq_quantum_paradoxes.sh", "rq_grok_bloch.sh", "rq_fwq_portal.sh",
                 "rq_my_programs.sh", "rq_demo_run.sh", "qoffee-maker.sh",
                 "quantum-mixer.sh", "rq_quantum_lab.sh"):
        text = _read(name)
        assert not old.search(text), name
        assert "rq_wait_for_stop" in text or "rq_docker_stop_with_window" in text, name
    assert "Press Enter to close this window" not in _read("rq_led_ibm_demo.sh")
    assert "Press Enter to close this window" not in _read("fractals.sh")


def test_menu_led_demos_stop_in_the_terminal_not_a_dialog():
    menu = open(os.path.join(_CFG, "RQB2_menu.sh"), encoding="utf-8").read()
    body = menu[menu.index("run_demo() {"):menu.index("_rq_demo_hangup() {")]
    assert "Keep running" not in body
    assert "press Enter or Ctrl+C, or close this window" in body
    assert "trap '_rq_demo_hangup' HUP" in body


# --- LED launchers clear the panel once (R-158) ----------------------------------

def test_led_launchers_clear_however_they_end():
    for name in ("rq_led_ibm_demo.sh", "rq_rasq_led.sh", "rq_led_test.sh",
                 "rq_led_display_text.sh", "rq_led_display_logo.sh"):
        text = _read(name)
        assert "rq_led_clear_on_exit" in text, name
        assert not re.search(r"^exec python3", text, re.M), name


@needs_bash
@pytest.mark.parametrize("sig,code", [(signal.SIGHUP, 129), (signal.SIGTERM, 143)])
def test_led_clear_on_exit_clears_once(tmp_path, sig, code):
    marks = tmp_path / "marks"
    script = (f'. "{_COMMON}"; led_clear_quietly() {{ echo clear >> "{marks}"; }}; '
              f'rq_led_stall_check() {{ echo check >> "{marks}"; }}; '
              f'rq_led_clear_on_exit; echo READY; sleep 30')
    p = _Pty(script)
    assert p.read_until("READY")
    time.sleep(0.3)
    os.killpg(p.pid, sig)        # as a closed window or a stop: the demo too
    assert p.wait() == code
    lines = marks.read_text().split()
    assert lines.count("clear") == 1
    # a closed window gets no question; a stop from the menu may
    assert ("check" in lines) == (code != 129)


# --- Pi 5 LED driver stall (item 31) ---------------------------------------------

def _load_led_utils(monkeypatch, tmp_path, write_seconds):
    """rq_led_utils with fake neopixel modules whose writes take write_seconds[i]."""
    calls = {"writes": [], "freed": 0}
    backend = types.ModuleType("adafruit_raspberry_pi5_neopixel_write")

    def free_pio():
        calls["freed"] += 1
    backend.free_pio = free_pio
    nw = types.ModuleType("neopixel_write")
    nw._neopixel = backend

    def write(pin, buf):
        i = len(calls["writes"])
        calls["writes"].append(len(buf))
        time.sleep(write_seconds[min(i, len(write_seconds) - 1)])
    nw.neopixel_write = write
    neo = types.ModuleType("neopixel")
    neo.neopixel_write = write
    monkeypatch.setitem(sys.modules, "neopixel", neo)
    monkeypatch.setitem(sys.modules, "neopixel_write", nw)
    monkeypatch.setitem(sys.modules, "adafruit_raspberry_pi5_neopixel_write", backend)
    spec = importlib.util.spec_from_file_location("rq_led_utils_c2", os.path.join(_BIN, "rq_led_utils.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LED_STALL_SECONDS = 0.05
    mod.LED_STALL_RETRY_SECONDS = 0.2
    mod.LED_STALL_FILE_PREFIX = str(tmp_path / "stall-")
    assert mod.guard_pi5_led_writes() is True
    assert mod.guard_pi5_led_writes() is True          # idempotent
    return mod, neo, calls


def _note(tmp_path):
    files = list(tmp_path.glob("stall-*"))
    assert len(files) == 1
    return dict(line.split("=", 1) for line in files[0].read_text().split())


def test_a_stalled_write_reopens_the_driver(monkeypatch, tmp_path, capsys):
    mod, neo, calls = _load_led_utils(monkeypatch, tmp_path, [0, 0.1, 0])
    buf = bytearray(576)
    neo.neopixel_write("pin", buf)               # fine
    neo.neopixel_write("pin", buf)               # stalls -> reopen + rewrite
    assert calls["freed"] == 1
    assert calls["writes"] == [576, 576, 580]    # 4 more bytes: set up again
    assert _note(tmp_path)["recovered"] == "yes"
    assert "stalled and was restarted" in capsys.readouterr().err
    neo.neopixel_write("pin", buf)
    assert calls["writes"][-1] == 576


def test_a_stuck_driver_skips_writes_and_retries(monkeypatch, tmp_path, capsys):
    mod, neo, calls = _load_led_utils(monkeypatch, tmp_path, [0.1, 0.1, 0])
    buf = bytearray(576)
    neo.neopixel_write("pin", buf)               # stall, reopen also stalls
    assert _note(tmp_path)["recovered"] == "no"
    assert "LED panel stopped" in capsys.readouterr().err
    n = len(calls["writes"])
    neo.neopixel_write("pin", buf)               # skipped while stuck
    assert len(calls["writes"]) == n
    time.sleep(0.25)
    neo.neopixel_write("pin", buf)               # retry: reopen works now
    assert calls["freed"] == 2
    assert "works again" in capsys.readouterr().err
    assert mod._stall_state["stuck_since"] is None


def test_no_guard_on_a_pi4(monkeypatch, tmp_path):
    nw = types.ModuleType("neopixel_write")
    nw._neopixel = types.ModuleType("adafruit_blinka.microcontroller.bcm283x.neopixel")
    neo = types.ModuleType("neopixel")
    neo.neopixel_write = lambda pin, buf: None
    monkeypatch.setitem(sys.modules, "neopixel", neo)
    monkeypatch.setitem(sys.modules, "neopixel_write", nw)
    spec = importlib.util.spec_from_file_location("rq_led_utils_c2b", os.path.join(_BIN, "rq_led_utils.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.guard_pi5_led_writes() is False
    assert not getattr(neo.neopixel_write, "_rq_stall_guard", False)


def test_brightness_limit(monkeypatch):
    spec = importlib.util.spec_from_file_location("rq_led_utils_c2c", os.path.join(_BIN, "rq_led_utils.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._brightness_limit("0.2") == 0.2
    for bad in ("", "x", "0", "1.5", None):
        assert mod._brightness_limit(bad) == 1.0
    assert mod.cap_brightness(0.6, {"led_max_brightness": 0.2}) == 0.2
    assert mod.cap_brightness(0.1, {"led_max_brightness": 0.2}) == 0.1
    assert mod.cap_brightness(0.6, {"led_max_brightness": 1.0}) == 0.6


@pytest.fixture
def box(tmp_path):
    """A fake home, env file and env-config, stub sudo/whiptail/curl."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    wt_log = tmp_path / "wt.log"
    _exe(stubs / "whiptail", f'''#!/bin/sh
{{ for a in "$@"; do printf '%s\\n' "$a"; done; echo "@@"; }} >> "{wt_log}"
exit "${{WT_RC:-0}}"
''')
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "curl", '#!/bin/sh\nexit 0\n')
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))

    def env(extra=None):
        e = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home),
                 RQ_CONFIG_FILE=str(env_config), RQ_ENV_FILE=str(env_file),
                 RQ_LED_STALL_PREFIX=str(tmp_path / "stall-"))
        e.update(extra or {})
        return e

    env.env_file = env_file
    env.wt_log = wt_log
    env.tmp = tmp_path
    return env


def _env_value(env_file, key):
    value = None
    for line in env_file.read_text().splitlines():
        if line.startswith(key + "="):
            value = line.split("=", 1)[1]
    return value


_BRIGHTNESS = os.path.join(_BIN, "rq_led_brightness.sh")


@needs_bash
def test_brightness_levels_set_default_and_limit(box):
    subprocess.run(["bash", _BRIGHTNESS, "--set", "low"], env=box(), check=True, capture_output=True)
    assert _env_value(box.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.2"
    assert _env_value(box.env_file, "LED_MAX_BRIGHTNESS") == "0.2"
    # and back up again: raising is offered too, no silent cap (Jan)
    subprocess.run(["bash", _BRIGHTNESS, "--set", "normal"], env=box(), check=True, capture_output=True)
    assert _env_value(box.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.4"
    assert _env_value(box.env_file, "LED_MAX_BRIGHTNESS") == "1.0"


@needs_bash
def test_after_stall_asks_before_lowering(box):
    (box.tmp / "stall-0").write_text(f"time={int(time.time())}\nrecovered=no\n")
    p = _Pty(f'bash "{_BRIGHTNESS}" --after-stall {int(time.time()) - 60}',
             env=box({"WT_RC": "1"}))           # "Keep 0.4"
    p.wait()
    dialog = box.wt_log.read_text()
    assert "LED panel stopped" in dialog and "power supply" in dialog and "27 W" in dialog
    assert "Lower to 0.2" in dialog
    assert _env_value(box.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.4"   # kept
    p = _Pty(f'bash "{_BRIGHTNESS}" --after-stall {int(time.time()) - 60}', env=box())
    p.wait()
    assert _env_value(box.env_file, "LED_MAX_BRIGHTNESS") == "0.2"


@needs_bash
def test_no_stall_no_question(box):
    (box.tmp / "stall-0").write_text("time=1000\nrecovered=yes\n")      # long ago
    p = _Pty(f'bash "{_BRIGHTNESS}" --after-stall {int(time.time()) - 60}', env=box())
    assert p.wait() == 0
    assert not box.wt_log.exists()


# --- Docker consent: per slot, 16 GB cards (item 32) -----------------------------

@needs_bash
@pytest.mark.parametrize("ab,gb,slot_note,small_note", [
    ("1", "26", True, False), ("0", "14", False, True), ("0", "58", False, False)])
def test_docker_consent_says_where_the_image_lives(box, ab, gb, slot_note, small_note):
    tty = box.tmp / "tty"
    tty.write_text("")
    subprocess.run(["bash", "-c", f'. "{_COMMON}"; load_rqb2_env; rq_confirm_demo_install quantum-mixer'],
                   env=box({"RQ_TEST_AB": ab, "RQ_TEST_ROOT_GB": gb, "RQ_TEST_TTY": str(tty),
                            "RQ_TEST_FREE_MB": "50000"}),
                   capture_output=True, text=True, timeout=60, start_new_session=True)
    text = box.wt_log.read_text()
    assert "quantum-mixer repository's CI" in text
    assert ("Docker images stay in this system's slot" in text) == slot_note
    assert ("A 16 GB card has room for one Docker demo" in text) == small_note


# --- Fun with Quantum window (item 10) -------------------------------------------

def test_fun_with_quantum_window():
    text = _read("rq_fun_with_quantum.sh")
    assert "Fun-with-Quantum" not in text
    assert "ws_ping_interval" in text                     # no websocket_ping_timeout warning
    assert '>"$SERVER_LOG" 2>&1 &' in text                # server log to a file
    assert "notebook_list" in text and ".variants[]" in text


@needs_bash
def test_fun_with_quantum_notebook_list_matches_the_manifest():
    mf = os.path.join(_CFG, "demo-manifests", "rq_demo_fun-with-quantum.json")
    out = subprocess.run(
        ["jq", "-r", '.variants[]? | select((.args // [])[0] // "" | endswith(".ipynb")) '
                     '| "    - \\(.name)  (\\(.args[0]))"', mf],
        capture_output=True, text=True, check=True).stdout
    assert "(Mermin-Peres-Game.ipynb)" in out and "(Readme.ipynb)" in out
    assert out.count("    - ") == 6


# --- doQumentation: a writable matplotlib config (item 20) -----------------------

def test_doqumentation_container_gets_a_writable_matplotlib_dir():
    assert "-e MPLCONFIGDIR=/tmp/matplotlib" in _read("rq_doqumentation.sh")


# --- a closed icon window stops the demo (items 5, 33) ---------------------------

# util-linux script(1) as far as it matters here: it blocks SIGHUP and passes
# SIGTERM on to the command
_SCRIPT_STUB = r'''#!/bin/bash
trap '' HUP
cmd=""; while [ $# -gt 1 ]; do case "$1" in -*c) cmd="$2"; shift 2 ;; -*) shift ;; *) break ;; esac; done
bash -c "$cmd" &
c=$!
trap 'kill -TERM $c' TERM
wait $c; rc=$?
while kill -0 $c 2>/dev/null; do wait $c; rc=$?; done
exit $rc
'''


@needs_bash
def test_closing_an_icon_window_stops_the_demo(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "script", _SCRIPT_STUB)
    marker = tmp_path / "cleaned"
    demo = tmp_path / "demo.sh"
    _exe(demo, f'#!/bin/bash\ntrap \'echo cleaned > "{marker}"; exit 143\' TERM\n'
               'echo READY\nwhile :; do sleep 0.2; done\n')
    p = _Pty(f'exec bash "{os.path.join(_BIN, "rq_hold_on_error.sh")}" "{demo}"',
             env={"PATH": f"{stubs}:{os.environ['PATH']}", "XDG_CACHE_HOME": str(tmp_path)})
    assert p.read_until("READY")
    os.kill(p.pid, signal.SIGHUP)            # the window is closed
    assert p.wait() == 143
    assert marker.read_text().strip() == "cleaned"


@needs_bash
def test_a_stuck_driver_is_restarted_without_a_reboot(box):
    drv = box.tmp / "rp1-pio"
    (drv / "1f00178000.pio").mkdir(parents=True)
    (box.tmp / "stall-0").write_text(f"time={int(time.time())}\nrecovered=no\n")
    p = _Pty(f'bash "{_BRIGHTNESS}" --after-stall {int(time.time()) - 60}',
             env=box({"WT_RC": "1", "RQ_PIO_DRIVER_DIR": str(drv)}))
    p.wait()
    assert (drv / "unbind").read_text().strip() == "1f00178000.pio"
    assert (drv / "bind").read_text().strip() == "1f00178000.pio"
    assert "has been restarted now" in box.wt_log.read_text()
