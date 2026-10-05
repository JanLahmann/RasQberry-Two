"""
Tests for the user test of 2026-10-04: how demos stop and what their windows show.

- #4, #8: Enter stops every demo, with the same stop line, through one runner
  (rq_run_demo); Ctrl+C and a closed window still stop it, and the LEDs are
  cleared after the demo is gone. Only a demo that asks questions in its
  window keeps the keyboard (Raspberry Tie on a real backend).
- #4: Raspberry Tie shows no Sense HAT emulator window when a panel is set up.
"""

import json
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

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_ENV_CONFIG = os.path.join(_CFG, "rasqberry_env-config.sh")
_ENV = os.path.join(_CFG, "rasqberry_environment.env")
_STOP_LINE = "To stop {}: press Enter or Ctrl+C, or close this window."

needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _read(*parts):
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class _Pty:
    """bash -c SCRIPT on a pseudo terminal, as in a demo's window."""

    def __init__(self, script, env=None):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # pragma: no cover - child
            os.execvpe("bash", ["bash", "-c", script], dict(os.environ, **(env or {})))
        self.out = b""

    def _pump(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if r:
            try:
                self.out += os.read(self.fd, 4096)
            except OSError:
                pass

    def read_until(self, text, timeout=15):
        end = time.time() + timeout
        while time.time() < end and text.encode() not in self.out:
            self._pump(0.2)
        return text.encode() in self.out

    def send(self, data):
        os.write(self.fd, data.encode())

    def wait(self, timeout=20):
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
            self._pump(0.2)
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        raise AssertionError("did not end: " + self.text())

    def text(self):
        return self.out.decode(errors="replace")


def _alive(pid):
    st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout
    return bool(st.strip()) and not st.strip().startswith("Z")


def _await_file(path, timeout=10):
    end = time.time() + timeout
    while time.time() < end and not (path.exists() and path.read_text().strip()):
        time.sleep(0.1)
    return path.read_text().strip() if path.exists() else ""


def _demo_program(tmp_path):
    """A Python demo that never reads its input, starts a helper process
    (like Fractals' browser) and would print a traceback on Ctrl+C."""
    prog = tmp_path / "demo.py"
    prog.write_text(f'''import os, subprocess, sys, time
helper = subprocess.Popen(["sleep", "300"])
open("{tmp_path}/pids", "w").write("%d %d\\n" % (os.getpid(), helper.pid))
print("DEMO RUNNING", flush=True)
while True:
    time.sleep(0.2)
''')
    return prog


# --- rq_run_demo: one stop rule (#4, #8) ----------------------------------------

@needs_bash
def test_enter_stops_a_demo_that_does_not_read_the_keyboard(tmp_path):
    prog = _demo_program(tmp_path)
    p = _Pty(f'. "{_COMMON}"; rq_run_demo "Lights Out" "{sys.executable}" "{prog}"; echo "RC=$?"')
    assert p.read_until(_STOP_LINE.format("Lights Out"))
    assert p.read_until("DEMO RUNNING")
    demo, helper = (int(v) for v in _await_file(tmp_path / "pids").split())
    p.send("\r")
    assert p.wait() == 0
    assert "RC=0" in p.text()
    # the demo and what it started are gone, and no shell job message
    assert not _alive(demo) and not _alive(helper)
    assert "Terminated" not in p.text() and "Killed" not in p.text()


@needs_bash
def test_ctrl_c_stops_the_demo_before_the_exit_trap_and_without_a_traceback(tmp_path):
    prog = _demo_program(tmp_path)
    marker = tmp_path / "trap"
    p = _Pty(f'. "{_COMMON}"; '
             f'trap \'kill -0 $(cut -d" " -f1 "{tmp_path}/pids") 2>/dev/null '
             f'&& echo demo-still-running > "{marker}" || echo demo-gone > "{marker}"\' EXIT; '
             f'rq_run_demo "Lights Out" "{sys.executable}" "{prog}"; echo NOT-REACHED')
    assert p.read_until("DEMO RUNNING")
    p.send("\x03")                                    # Ctrl+C in the window
    assert p.wait() == 130
    assert marker.read_text().strip() == "demo-gone"
    assert "Traceback" not in p.text() and "KeyboardInterrupt" not in p.text()
    assert "NOT-REACHED" not in p.text()


@needs_bash
def test_a_closed_window_stops_the_demo(tmp_path):
    prog = _demo_program(tmp_path)
    p = _Pty(f'. "{_COMMON}"; rq_run_demo Demo "{sys.executable}" "{prog}"')
    assert p.read_until("DEMO RUNNING")
    demo, helper = (int(v) for v in _await_file(tmp_path / "pids").split())
    os.kill(p.pid, signal.SIGHUP)
    assert p.wait() == 129
    time.sleep(0.3)
    assert not _alive(demo) and not _alive(helper)


@needs_bash
def test_a_demo_that_ends_by_itself_returns_its_status_and_restores_the_traps(tmp_path):
    p = _Pty(f'. "{_COMMON}"; trap "echo OWN-INT" INT; '
             'rq_run_demo Demo sh -c "echo DONE; exit 3"; echo "RC=$?"; trap -p INT')
    assert p.wait() == 0
    assert "DONE" in p.text() and "RC=3" in p.text()
    assert "OWN-INT" in p.text()                     # the caller's trap is back


def test_without_a_window_the_demo_simply_runs():
    out = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_run_demo Demo sh -c "echo RAN; exit 4"; echo "RC=$?"'],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30).stdout
    assert out.split() == ["RAN", "RC=4"]


@needs_bash
def test_a_program_run_by_a_shell_function_gets_time_to_clean_up(tmp_path):
    # Fractals runs through run_as_user (a function, so a subshell is the
    # child): its own SIGTERM cleanup closes its browser window and needs a
    # moment, which a quick SIGKILL would cut short
    prog = tmp_path / "graceful.py"
    prog.write_text(f'''import signal, sys, time
def bye(*_):
    time.sleep(1)
    open("{tmp_path}/cleaned", "w").write("yes")
    sys.exit(0)
signal.signal(signal.SIGTERM, bye)
print("UP", flush=True)
while True:
    time.sleep(0.2)
''')
    p = _Pty(f'. "{_COMMON}"; as_user() {{ "$@"; }}; '
             f'rq_run_demo Fractals as_user "{sys.executable}" "{prog}"; echo "RC=$?"')
    assert p.read_until("UP")
    p.send("\r")
    assert p.wait() == 0
    assert (tmp_path / "cleaned").read_text() == "yes"
    assert "RC=0" in p.text()


@needs_bash
def test_stop_pid_is_quiet_also_when_it_has_to_kill(tmp_path):
    prog = tmp_path / "stubborn.py"
    prog.write_text("import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                    "print('UP', flush=True)\ntime.sleep(300)\n")
    p = _Pty(f'. "{_COMMON}"; "{sys.executable}" "{prog}" & sleep 1; '
             'rq_stop_pid $! 1; echo "STOPPED"; sleep 0.5; echo END')
    assert p.wait(30) == 0
    assert "STOPPED" in p.text() and "END" in p.text()
    assert "Killed" not in p.text()


# --- every demo that did not stop with Enter now does ----------------------------

def test_launchers_without_their_own_enter_use_the_runner():
    for name in ("fractals.sh", "rq_led_test.sh", "rq_led_painter.sh"):
        text = _read("RQB2-bin", name)
        assert "rq_run_demo " in text, name
        assert "rq_stop_hint" not in text, name     # the runner prints the one line
    run = _read("RQB2-bin", "rq_demo_run.sh")
    body = run[run.index("run_python() {"):run.index("\n}\n", run.index("run_python() {"))]
    assert "rq_run_demo" in body
    # the Ctrl+C-only line is left for demos that need the keyboard
    assert body.count("rq_stop_hint") == 1 and 'if [ "$keyboard" = "true" ]' in body


def test_exit_traps_stop_the_demo_before_the_leds_are_cleared():
    common = _read("RQB2-bin", "rq_common.sh")
    led_exit = common[common.index("_rq_led_on_exit() {"):]
    assert led_exit.index("rq_stop_demo_child") < led_exit.index("led_clear_quietly")
    run = _read("RQB2-bin", "rq_demo_run.sh")
    cleanup = run[run.index("cleanup() {"):]
    assert cleanup.index("rq_stop_demo_child") < cleanup.index("led_clear_quietly")


def test_only_raspberry_tie_on_a_real_backend_keeps_the_keyboard():
    seen = {}
    mdir = os.path.join(_CFG, "demo-manifests")
    for name in os.listdir(mdir):
        if not name.startswith("rq_demo_") or name == "rq_demo_schema.json":
            continue
        mf = json.load(open(os.path.join(mdir, name)))
        if mf.get("entrypoint", {}).get("keyboard"):
            seen[mf["id"]] = None
        for v in mf.get("variants", []):
            if v.get("entrypoint", {}).get("keyboard"):
                seen.setdefault(mf["id"], []).append(v["id"])
    assert seen == {"quantum-raspberry-tie": ["real"]}
    schema = json.load(open(os.path.join(mdir, "rq_demo_schema.json")))
    assert schema["properties"]["entrypoint"]["properties"]["keyboard"]["type"] == "boolean"


@pytest.fixture
def box(tmp_path):
    """A fake home, env file and env-config, stub sudo/whiptail/curl."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "whiptail", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    venv = home / "RasQberry-Two/venv/RQB2/bin"
    venv.mkdir(parents=True)
    os.symlink(sys.executable, venv / "python3")
    (venv / "activate").write_text("")

    def env(extra=None):
        e = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home),
                 RQ_CONFIG_FILE=str(env_config), RQ_ENV_FILE=str(env_file), USER="rasqberry")
        e.update(extra or {})
        return e

    env.tmp = tmp_path
    env.home = home
    return env


def _catalogue_python_demo(box, keyboard=False):
    demo = box.home / "RasQberry-Two/demos/pydemo"
    demo.mkdir(parents=True)
    _demo_program(box.tmp)
    shutil.copy(box.tmp / "demo.py", demo / "demo.py")
    mdir = box.home / ".local/config/demo-manifests"
    mdir.mkdir(parents=True)
    entry = {"type": "python", "working_dir": "pydemo", "script": "demo.py"}
    if keyboard:
        entry["keyboard"] = True
    (mdir / "rq_demo_pydemo.json").write_text(json.dumps({
        "id": "pydemo", "name": "Py Demo", "entrypoint": entry,
        "install": {"marker_file": "demo.py"},
        "needs_hw": {"leds": False, "display": "none"}}))


@needs_bash
def test_a_catalogue_python_demo_stops_with_enter(box):
    _catalogue_python_demo(box)
    p = _Pty(f'exec bash "{_BIN}/rq_demo_run.sh" pydemo', env=box())
    assert p.read_until(_STOP_LINE.format("Py Demo"), 30), p.text()
    assert p.read_until("DEMO RUNNING")
    demo, _ = (int(v) for v in _await_file(box.tmp / "pids").split())
    p.send("\r")
    assert p.wait() == 0, p.text()
    assert not _alive(demo)


@needs_bash
def test_a_demo_that_asks_questions_keeps_the_keyboard(box):
    _catalogue_python_demo(box, keyboard=True)
    p = _Pty(f'exec bash "{_BIN}/rq_demo_run.sh" pydemo', env=box())
    assert p.read_until("To stop Py Demo: press Ctrl+C or close this window.", 30), p.text()
    assert p.read_until("DEMO RUNNING")
    p.send("\x03")
    assert p.wait() == 130


# --- Raspberry Tie: no Sense HAT emulator over the terminal (#4) -----------------

def test_raspberry_tie_skips_the_emulator_window_with_a_panel():
    patch = _read("RQB2-config", "demo-patches", "quantum-raspberry-tie.patch")
    added = "\n".join(l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))
    assert "def _rq_led_panel():" in added
    assert "get_led_config().get('led_physical', True)" in added
    assert re.search(r"if UseEmulator and not \('-e' in sys.argv\) and _rq_led_panel\(\):\n"
                     r".*\n    UseEmulator = False\n    NoHat = True", added)


# --- Quantum Lights Out: one plain line per step (#13) ---------------------------

def _added(patch_name):
    patch = _read("RQB2-config", "demo-patches", patch_name)
    return "\n".join(l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++"))


def test_lights_out_prints_one_plain_line_per_step():
    patch = _read("RQB2-config", "demo-patches", "quantum-lights-out.patch")
    added = _added("quantum-lights-out.patch")
    removed = "\n".join(l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---"))
    # no Python lists in the window any more
    assert 'print("Grid chosen:", lights_grid)' in removed
    assert removed.count("visualize_lights_out_grid_to_console(grid") == 3
    assert "visualize_lights_out_grid_to_console(" not in added
    # each press is one line: the tile by name and the grid after it
    assert 'print(f"  Press {name + \':\':<14} {grid_line(grid)}   {sum(grid)} on", flush=True)' in added
    assert '"top left", "top middle", "top right"' in added
    assert "Solved: all lights are off." in added
    # Ctrl+C without the demo window ends without a traceback
    assert "except KeyboardInterrupt:" in added


def test_lights_out_grid_line():
    added = _added("quantum-lights-out.patch")
    src = added[added.index("def grid_line(grid):"):]
    src = src[:src.index("\n\n")]
    ns = {}
    exec("import math\n" + src, ns)
    assert ns["grid_line"]([1, 1, 0, 0, 0, 0, 1, 0, 1]) == "■■□ □□□ ■□■"
