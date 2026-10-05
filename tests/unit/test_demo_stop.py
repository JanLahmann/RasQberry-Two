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
    # only for the GTK emulator window, with the panel in use; -e (emulator
    # wanted) and -faux (the bundled no-window stand-in) stay as they were
    assert re.search(r"if UseEmulator and not UseFaux and UseNeo and IsRPi and '-e' not in sys.argv "
                     r"and _rq_led_panel\(\):\n.*\n    UseEmulator = False\n    NoHat = True", added)


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


# --- terminal lines that looked like faults (#27) --------------------------------

@needs_bash
def test_quiet_stderr_drops_only_the_harmless_qt_line():
    proc = subprocess.run(
        ["bash", "-c", f'. "{_COMMON}"; rq_quiet_stderr sh -c \''
         'echo "QStandardPaths: wrong permissions on runtime directory /run/user/1000, 0770 instead of 0700" >&2; '
         'echo "Real error: no display" >&2; echo out; exit 5\'; echo "RC=$?"'],
        capture_output=True, text=True, timeout=30)
    assert "QStandardPaths" not in proc.stderr
    assert "Real error: no display" in proc.stderr
    assert proc.stdout.split() == ["out", "RC=5"]


def test_painter_window_is_without_the_qt_runtime_line():
    painter = _read("RQB2-bin", "rq_led_painter.sh")
    assert 'rq_run_demo "$DEMO_NAME" rq_quiet_stderr ' in painter


def test_fractals_draw_without_qt_and_without_a_line_per_picture():
    sh = _read("RQB2-bin", "fractals.sh")
    assert "run_as_user env MPLBACKEND=Agg" in sh
    py = _read("RQB2-bin", "fractal_files", "fractals.py")
    loop = py[py.index("for i in range(number_of_frames):"):]
    # the numbers of every picture only with RQ_DEBUG=1
    assert loop.index("if DEBUG:") < loop.index('print(f"Loop i = ')
    assert 'print(f"\\rDrawing picture {i + 1} of {number_of_frames}...", end="", flush=True)' in loop
    # closing the window while it draws stops it, without a traceback
    assert "raise traceback.format_exc()" not in py
    assert 'print("\\nThe Quantum Fractals window was closed.")\n        sys.exit(0)' in loop
    # its pictures say how to stop it; the watch for a closed window is not busy
    assert py.count("add_stop_hint(") == 3 and 'STOP_HINT = "To stop: close this window"' in py
    assert loop.rstrip().endswith("time.sleep(1)")


def test_jupyter_launchers_stop_without_a_killed_line():
    for name, stop in (("rq_quantum_paradoxes.sh", 'rq_stop_pid "$JUPYTER_PID" 10'),
                       ("rq_my_programs.sh", 'rq_stop_pid "$5" 10\' \\\n')):
        text = _read("RQB2-bin", name)
        assert "kill -9" not in text, name
        assert stop in text, name


_FAKE_PI4_DRIVER = '''
import atexit, sys, types

class SwigHandle:
    """Like a SWIG pointer that owns memory SWIG has no destructor for."""
    def __init__(self):
        self.own = True
    def disown(self):
        self.own = False
    def __del__(self):
        if self.own:
            print("swig/python detected a memory leak of type 'ws2811_t *', no destructor found.")

backend = types.ModuleType("adafruit_blinka.microcontroller.bcm283x.neopixel")
backend._led_strip = None

def cleanup():                       # the library's own atexit cleanup
    backend._led_strip = None

def first_write():                   # neopixel_write() creates it and registers cleanup
    backend._led_strip = SwigHandle()
    atexit.register(cleanup)

neopixel_write = types.ModuleType("neopixel_write")
neopixel_write._neopixel = backend
sys.modules["neopixel_write"] = neopixel_write
sys.path.insert(0, sys.argv[1])
import rq_led_utils
first_write()
if sys.argv[2] == "quiet":
    rq_led_utils.quiet_pi4_driver_exit()
    rq_led_utils.quiet_pi4_driver_exit()      # once is enough
print("done")
'''


@pytest.mark.parametrize("mode,leak_line", [("quiet", False), ("plain", True)])
def test_pi4_driver_exit_has_no_swig_leak_line(tmp_path, mode, leak_line):
    script = tmp_path / "fake.py"
    script.write_text(_FAKE_PI4_DRIVER)
    out = subprocess.run([sys.executable, str(script), _BIN, mode],
                         capture_output=True, text=True, timeout=60, cwd=str(tmp_path)).stdout
    assert "done" in out
    assert ("swig/python detected a memory leak" in out) == leak_line


def test_real_strips_keep_the_pi4_exit_quiet():
    utils = _read("RQB2-bin", "rq_led_utils.py")
    # both places that open the physical strip, after their first frame
    assert utils.count("pixels.show()\n            quiet_pi4_driver_exit()") == 1
    assert utils.count("pixels.show()\n        quiet_pi4_driver_exit()") == 1


# --- browser demos: own maximised window, no dead tab (#9, #15) -------------------

def _tab_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rq_browser_tab_t", os.path.join(_BIN, "rq_browser_tab.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _browser_stubs(tmp_path):
    """chromium-browser that hands over at once, and a python3 that records
    what the demo-tab helper was asked (the real one for anything else)."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    _exe(stubs / "chromium-browser", f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp_path}/browser-args"\n')
    _exe(stubs / "python3", f'''#!/bin/sh
case "$1" in
    *rq_browser_tab.py)
        shift
        echo "$*" >> "{tmp_path}/tab-calls"
        [ "$1" = ids ] && echo "OLD1,OLD2"
        exit 0 ;;
esac
exec "{sys.executable}" "$@"
''')
    if shutil.which("setsid") is None:
        _exe(stubs / "setsid", f'''#!{sys.executable}
import os, sys
args = sys.argv[1:]
while args[0].startswith("-"):
    args.pop(0)
os.execvp(args[0], args)
''')
    return stubs


def _calls(tmp_path, n, timeout=10):
    path = tmp_path / "tab-calls"
    end = time.time() + timeout
    while time.time() < end:
        if path.exists() and len(path.read_text().splitlines()) >= n:
            break
        time.sleep(0.1)
    return path.read_text().splitlines() if path.exists() else []


@needs_bash
@pytest.mark.parametrize("flags,state", [("", "maximized"), ("--start-fullscreen", "fullscreen")])
def test_a_local_demo_opens_its_own_window_and_is_looked_after(tmp_path, flags, state):
    stubs = _browser_stubs(tmp_path)
    out = subprocess.run(
        ["bash", "-c", f'. "{_COMMON}"; rq_open_browser http://127.0.0.1:8888/lab {flags}; '
                       'echo "TABS=${_RQ_DEMO_TABS[*]}"; rq_close_demo_tabs; echo "LEFT=${#_RQ_DEMO_TABS[@]}"'],
        env=dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}"),
        capture_output=True, text=True, timeout=60).stdout
    args = (tmp_path / "browser-args").read_text().split()
    assert args[:2] == ["--password-store=basic", "--new-window"] and args[-1] == "http://127.0.0.1:8888/lab"
    calls = _calls(tmp_path, 3)
    assert calls[0] == "ids"
    # the watcher knows the tabs that were open before, and the window state
    assert f"watch --before OLD1,OLD2 --window-state {state} http://127.0.0.1:8888/lab" in calls
    assert "close http://127.0.0.1:8888/lab" in calls
    assert "TABS=http://127.0.0.1:8888/lab" in out and "LEFT=0" in out


@needs_bash
def test_a_website_opens_as_a_tab_as_before(tmp_path):
    stubs = _browser_stubs(tmp_path)
    subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_open_browser https://quantum.cloud.ibm.com/composer'],
                   env=dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}"),
                   capture_output=True, text=True, timeout=60, check=True)
    assert (tmp_path / "browser-args").read_text().split() == [
        "--password-store=basic", "https://quantum.cloud.ibm.com/composer"]
    time.sleep(0.5)
    assert not (tmp_path / "tab-calls").exists()


def test_stop_paths_close_the_demo_tab_before_the_server_goes():
    common = _read("RQB2-bin", "rq_common.sh")
    stop = common[common.index("_rq_window_container_stop() {"):]
    assert stop.index("rq_close_demo_tabs") < stop.index("rq_docker_stop_detached")
    run = _read("RQB2-bin", "rq_demo_run.sh")
    cleanup = run[run.index("cleanup() {"):]
    # only when the demo really stops: a container without a window keeps its tab
    assert 'if [ -n "$JUPYTER_PID$HTTP_SERVER_PID" ] || [ "$DOCKER_STOP_ON_EXIT" = "1" ]; then\n' \
           '        rq_close_demo_tabs' in cleanup
    assert cleanup.index("rq_close_demo_tabs") < cleanup.index('kill "$JUPYTER_PID"')
    for name, server in (("rq_fun_with_quantum.sh", 'kill "$JUPYTER_PID"'), ("rq_grok_bloch.sh", "kill $SERVER_PID"),
                         ("rq_fwq_portal.sh", 'kill "$SERVER_PID"'),
                         ("rq_quantum_paradoxes.sh", 'rq_stop_pid "$JUPYTER_PID"')):
        text = _read("RQB2-bin", name)
        body = text[text.index("cleanup() {"):]
        assert body.index("rq_close_demo_tabs") < body.index(server), name


def test_chromium_is_maximised_everywhere_with_a_local_devtools_port():
    dash = shutil.which("dash") or shutil.which("sh")
    out = subprocess.run([dash, "-ec", f'CHROMIUM_FLAGS=""; . "{os.path.join(_ROOT, "RQB2-system/etc/chromium.d/rasqberry")}"; '
                          'echo "$CHROMIUM_FLAGS"'],
                         capture_output=True, text=True, env=dict(os.environ, XDG_RUNTIME_DIR="/nonexistent")).stdout
    assert "--start-maximized" in out.split()                 # no small-screen flag needed
    assert "--remote-debugging-port=9222" in out.split()
    # 127.0.0.1 only, and no web page may use it
    assert "remote-allow-origins" not in out and "remote-debugging-address" not in out
    tab = _read("RQB2-bin", "rq_browser_tab.py")
    assert 'os.environ.get("RQ_BROWSER_CDP_PORT", "9222")' in tab


def test_session_switches_the_icon_rule_off_and_starts_chromium_unsized(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rq_desktop_session_t", os.path.join(_BIN, "rq_desktop_session.py"))
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    rules, started = [], []
    monkeypatch.setattr(ds, "reset_chromium_exit", lambda: None)
    monkeypatch.setattr(ds, "apply_touch_css", lambda touch: None)
    monkeypatch.setattr(ds, "touch_mode_on", lambda: False)
    monkeypatch.setattr(ds, "screen_size", lambda: (1920, 1080))     # a large screen
    monkeypatch.setattr(ds, "set_small_screen_flag", lambda small: None)
    monkeypatch.setattr(ds, "set_chromium_rule", lambda small: rules.append(small) or False)
    monkeypatch.setattr(ds, "layout_desktop", lambda size, touch: False)
    monkeypatch.setattr(ds, "online", lambda: True)
    monkeypatch.setattr(ds, "env_value", lambda key, default="": default)
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: started.append(cmd))
    monkeypatch.setenv("RQ_BROWSER_DELAY", "0")
    assert ds.main([]) == 0
    assert rules == [True]                                    # off on a large screen too
    assert started == [["/usr/bin/chromium", ds.HOMEPAGE]]   # no --window-size=1070,1005


def test_first_login_saves_a_maximised_placement():
    text = _read("RQB2-system", "usr", "local", "bin", "trust-rasqberry-desktop-files.sh")
    assert "'maximized': True," in text and "'maximized': False," not in text


# --- rq_browser_tab.py ---------------------------------------------------------------

def test_origin_treats_localhost_as_the_loopback_address():
    bt = _tab_module()
    assert bt.origin("http://localhost:8893/lab/tree/x.ipynb?token=t") == "http://127.0.0.1:8893"
    assert bt.origin("http://127.0.0.1:8893/") == "http://127.0.0.1:8893"
    assert bt.origin("https://quantum.cloud.ibm.com/composer") == "https://quantum.cloud.ibm.com:443"
    assert bt.origin("about:blank") == "" and bt.origin("chrome://newtab/") == ""


def test_watch_closes_the_tab_once_the_server_is_gone(monkeypatch):
    bt = _tab_module()
    monkeypatch.setattr(bt, "POLL", 0)
    monkeypatch.setattr(bt.time, "sleep", lambda s: None)
    tabs = [{"id": "OLD", "url": "http://127.0.0.1:8888/tree"},       # open before: not ours
            {"id": "NEW", "url": "http://localhost:8888/lab"}]
    up = iter([True, True, False, False])
    closed, states = [], []
    monkeypatch.setattr(bt, "pages", lambda timeout=2.0: list(tabs))
    monkeypatch.setattr(bt, "server_up", lambda org: next(up))
    monkeypatch.setattr(bt, "set_window_state", lambda tid, st: states.append((tid, st)))
    monkeypatch.setattr(bt, "close", lambda url: closed.append(url))
    assert bt.watch("http://127.0.0.1:8888/lab", ["OLD"], "fullscreen") == 0
    assert states == [("NEW", "fullscreen")]
    assert closed == ["http://127.0.0.1:8888/lab"]


def test_watch_leaves_a_tab_the_user_closed_and_gives_up_without_a_browser(monkeypatch):
    bt = _tab_module()
    monkeypatch.setattr(bt, "POLL", 0)
    monkeypatch.setattr(bt.time, "sleep", lambda s: None)
    seen = iter([[{"id": "NEW", "url": "http://127.0.0.1:8080/"}], []])
    monkeypatch.setattr(bt, "pages", lambda timeout=2.0: next(seen))
    monkeypatch.setattr(bt, "close", lambda url: pytest.fail("closed a tab"))
    assert bt.watch("http://127.0.0.1:8080/", [], "") == 0
    # no DevTools port at all: nothing to look after
    monkeypatch.setattr(bt, "pages", lambda timeout=2.0: None)
    monkeypatch.setattr(bt, "FIND_WAIT", 0)
    assert bt.watch("http://127.0.0.1:8080/", [], "maximized") == 0


def test_server_up_only_says_no_when_nothing_listens():
    import socket
    bt = _tab_module()
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert bt.server_up("http://127.0.0.1:%d" % port)
    finally:
        srv.close()
    assert not bt.server_up("http://127.0.0.1:%d" % port)


def _fake_devtools_server(replies):
    """A one-connection WebSocket server: checks the handshake (no Origin),
    reads one masked text frame, answers with REPLIES (an event first)."""
    import base64
    import hashlib
    import socket
    import struct
    import threading
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = {}

    def frame(text):
        data = text.encode()
        n = len(data)
        if n < 126:
            return struct.pack("!BB", 0x81, n) + data
        if n < 65536:
            return struct.pack("!BBH", 0x81, 126, n) + data
        return struct.pack("!BBQ", 0x81, 127, n) + data

    def serve():
        conn, _ = srv.accept()
        head = b""
        while b"\r\n\r\n" not in head:
            head += conn.recv(4096)
        got["head"] = head.decode()
        key = [l.split(": ", 1)[1] for l in got["head"].split("\r\n") if l.startswith("Sec-WebSocket-Key")][0]
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                     b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        b1, b2 = conn.recv(2)
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack("!H", conn.recv(2))[0]
        mask = conn.recv(4)
        data = b""
        while len(data) < n:
            data += conn.recv(n - len(data))
        got["masked"] = bool(b2 & 0x80)
        got["msg"] = json.loads(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        for r in replies(got["msg"]["id"]):
            conn.sendall(frame(r))
        conn.close()
        srv.close()

    threading.Thread(target=serve, daemon=True).start()
    return "ws://127.0.0.1:%d/devtools/browser/x" % srv.getsockname()[1], got


def test_devtools_client_speaks_websocket():
    bt = _tab_module()
    big = "x" * 70000          # an answer longer than 65535 bytes
    url, got = _fake_devtools_server(lambda i: [
        json.dumps({"method": "Target.targetCreated", "params": {}}),
        json.dumps({"id": i, "result": {"windowId": 7, "pad": big}})])
    dev = bt.DevTools(url, timeout=10)
    try:
        res = dev.call("Browser.getWindowForTarget", {"targetId": "T"})
    finally:
        dev.close()
    assert res["windowId"] == 7 and len(res["pad"]) == 70000
    assert got["masked"] and got["msg"]["method"] == "Browser.getWindowForTarget"
    assert got["msg"]["params"] == {"targetId": "T"}
    assert "Origin:" not in got["head"]          # Chromium refuses pages' origins


def test_devtools_client_reports_an_error_answer():
    bt = _tab_module()
    url, _ = _fake_devtools_server(lambda i: [json.dumps({"id": i, "error": {"message": "No target"}})])
    dev = bt.DevTools(url, timeout=10)
    try:
        with pytest.raises(RuntimeError, match="No target"):
            dev.call("Browser.getWindowForTarget", {"targetId": "T"})
    finally:
        dev.close()


def test_save_needs_the_devtools_port(monkeypatch):
    bt = _tab_module()
    monkeypatch.setattr(bt, "pages", lambda timeout=2.0: None)
    assert bt.save("http://127.0.0.1:8893/") == 2
    monkeypatch.setattr(bt, "pages", lambda timeout=2.0: [{"id": "A", "url": "http://127.0.0.1:9999/"}])
    assert bt.save("http://127.0.0.1:8893/") == 0      # nothing open there: nothing to lose


def _find_chrome():
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


@pytest.mark.skipif(_find_chrome() is None, reason="needs Chrome or Chromium")
def test_with_a_real_browser_the_tab_is_saved_and_closed_without_asking(tmp_path):
    # a page that would ask "Leave site?" and has a JupyterLab-like save command
    www = tmp_path / "www"
    www.mkdir()
    (www / "index.html").write_text("""<!doctype html><title>demo</title><script>
window.addEventListener('beforeunload', e => { e.preventDefault(); e.returnValue = ''; });
window.jupyterapp = {commands: {hasCommand: c => c === 'docmanager:save-all',
  execute: async c => { await new Promise(r => setTimeout(r, 200)); document.title = 'SAVED'; }}};
</script><p>demo</p>""")
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    web_port = s.getsockname()[1]
    s.close()
    web = subprocess.Popen([sys.executable, "-m", "http.server", str(web_port), "--bind", "127.0.0.1",
                            "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile = tmp_path / "profile"
    chrome = subprocess.Popen([_find_chrome(), "--headless=new", "--remote-debugging-port=0",
                               f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                               "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        port_file = profile / "DevToolsActivePort"
        end = time.time() + 30
        while time.time() < end and not (port_file.exists() and port_file.read_text().strip()):
            time.sleep(0.2)
        cdp_port = port_file.read_text().split()[0]
        env = dict(os.environ, RQ_BROWSER_CDP_PORT=cdp_port, RQ_BROWSER_POLL="0.3", RQ_BROWSER_FIND_WAIT="15")
        tool = [sys.executable, os.path.join(_BIN, "rq_browser_tab.py")]
        before = subprocess.run(tool + ["ids"], env=env, capture_output=True, text=True, timeout=30).stdout.strip()
        url = f"http://localhost:{web_port}/index.html"
        watcher = subprocess.Popen(tool + ["watch", "--before", before, "--window-state", "maximized", url], env=env)
        bt = _tab_module()
        bt.PORT = int(cdp_port)
        bt.cdp(f"/json/new?{url}", method="PUT")
        time.sleep(2)
        assert subprocess.run(tool + ["save", url], env=env, timeout=60).returncode == 0
        assert [t["title"] for t in bt.tabs_on(bt.origin(url), bt.pages())] == ["SAVED"]
        web.terminate()                       # the demo stops
        web.wait(10)
        assert watcher.wait(30) == 0
        assert bt.tabs_on(bt.origin(url), bt.pages()) == []     # closed, no "Leave site?"
        assert [t["url"] for t in bt.pages()] == ["about:blank"]
    finally:
        web.kill()
        chrome.kill()
        chrome.wait(10)


# --- My Quantum Programs saves before it stops (#12) -----------------------------

def _mqp_box(tmp_path):
    """rq_my_programs.sh with a stand-in JupyterLab (a plain web server) and a
    stand-in rq_browser_tab.py that records what it was asked."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "jupyter-lab", f'''#!/bin/sh
for a in "$@"; do case "$a" in --port=*) port="${{a#--port=}}" ;; esac; done
echo "$*" > "{tmp_path}/jupyter-args"
exec "{sys.executable}" -m http.server "$port" --bind 127.0.0.1
''')
    home = tmp_path / "home"
    (home / "RasQberry-Two/venv/RQB2/bin").mkdir(parents=True)
    (home / "RasQberry-Two/venv/RQB2/bin/activate").write_text("")
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in os.listdir(_BIN):
        if name not in ("rq_learner_setup.sh", "rq_browser_tab.py") and not name.startswith("__"):
            os.symlink(os.path.join(_BIN, name), bin_dir / name)
    _exe(bin_dir / "rq_learner_setup.sh", "#!/bin/sh\nexit 0\n")
    (bin_dir / "rq_browser_tab.py").write_text(f'''import os, sys
open("{tmp_path}/tab-calls", "a").write(sys.argv[1] + " " + sys.argv[2].split("?")[0] + "\\n")
sys.exit(int(os.environ.get("SAVE_RC", "0")) if sys.argv[1] == "save" else 0)
''')
    port = 39000 + os.getpid() % 500
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home), USER="rasqberry",
               RQ_CONFIG_FILE=str(env_config), RQ_ENV_FILE=str(env_file), RQ_DEMO_COUNTED="test",
               MY_PROGRAMS_JUPYTER_PORT=str(port))
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "SUDO_USER"):
        env.pop(k, None)
    return bin_dir, env, port


def _port_open(port):
    import socket
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
        return True
    except OSError:
        return False


@needs_bash
def test_my_programs_saves_the_open_notebooks_before_it_stops(tmp_path):
    bin_dir, env, port = _mqp_box(tmp_path)
    p = _Pty(f'exec bash "{bin_dir}/rq_my_programs.sh"', env=env)
    try:
        assert p.read_until(_STOP_LINE.format("JupyterLab"), 60), p.text()
        assert "--LabApp.expose_app_in_browser=True" in (tmp_path / "jupyter-args").read_text()
        assert "the open notebooks are saved when you stop JupyterLab here" in p.text()
        p.send("\r")
        assert p.wait(60) == 0, p.text()
        url = f"http://localhost:{port}/lab"   # (no Hello World in this empty folder)
        calls = _calls(tmp_path, 2)
        # saved first, then its tab closed, then the server stopped - once each
        assert calls[:2] == [f"save {url}", f"close {url}"] and len(calls) == 2, calls
        assert not _port_open(port)
        assert "could not be saved" not in p.text()
    finally:
        subprocess.run(["pkill", "-f", f"http.server {port}"], capture_output=True)


@needs_bash
def test_my_programs_asks_before_unsaved_edits_could_be_lost(tmp_path):
    bin_dir, env, port = _mqp_box(tmp_path)
    env["SAVE_RC"] = "2"                       # no DevTools port: nothing known
    p = _Pty(f'exec bash "{bin_dir}/rq_my_programs.sh"', env=env)
    try:
        assert p.read_until(_STOP_LINE.format("JupyterLab"), 60), p.text()
        p.send("\r")
        assert p.read_until("then press Enter to stop JupyterLab.", 30), p.text()
        time.sleep(0.5)
        assert _port_open(port)                # still running while it asks
        p.send("\r")
        assert p.wait(60) == 0, p.text()
        assert not _port_open(port)
    finally:
        subprocess.run(["pkill", "-f", f"http.server {port}"], capture_output=True)


@needs_bash
def test_my_programs_saves_on_ctrl_c_too(tmp_path):
    bin_dir, env, port = _mqp_box(tmp_path)
    p = _Pty(f'exec bash "{bin_dir}/rq_my_programs.sh"', env=env)
    try:
        assert p.read_until(_STOP_LINE.format("JupyterLab"), 60), p.text()
        p.send("\x03")
        p.wait(60)
        url = f"http://localhost:{port}/lab"   # (no Hello World in this empty folder)
        assert _calls(tmp_path, 2)[:2] == [f"save {url}", f"close {url}"]
        assert not _port_open(port)
    finally:
        subprocess.run(["pkill", "-f", f"http.server {port}"], capture_output=True)


# --- Hello World without an IBM Quantum account (#25) ---------------------------

def _starter_sync():
    import importlib.util
    spec = importlib.util.spec_from_file_location("rq_starter_sync_t", os.path.join(_BIN, "rq_starter_sync.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hello_world_real_hardware_cells_need_no_account_to_run():
    nb = json.load(open(os.path.join(_CFG, "my-quantum-programs", "Hello-World.ipynb")))
    cells = {c.get("id"): "".join(c["source"]) for c in nb["cells"]}
    run = cells["option3-code"]
    # guarded like the account cell (option3-save): a sentence, not a traceback
    assert "except AccountNotFoundError:" in run and "service = None" in run
    assert "RasQberry menu: IBM Quantum account > Save my API key" in run
    assert run.index("except AccountNotFoundError:") < run.index("service.least_busy(")
    assert "if service is not None:\n    display(plot_histogram(counts))" in cells["1o5retcxj0m"]
    # the other histograms are untouched
    assert cells["u3l93q05kx"].endswith("plot_histogram(counts)")
    assert cells["d9rjc7de28k"] == "plot_histogram(counts)"
    compile(run, "option3-code", "exec")


def test_starter_edits_can_name_a_cell_by_id():
    sync = _starter_sync()
    nb = {"cells": [{"id": "a", "source": ["x = 1"]}, {"id": "b", "source": ["plot(x)"]},
                    {"id": "c", "source": ["plot(x)"]}]}
    out = json.loads(sync.apply_edits(json.dumps(nb).encode(), [{"cell_id": "c", "source": "y = 2\nplot(y)"}]))
    assert [c["source"] for c in out["cells"]] == [["x = 1"], ["plot(x)"], ["y = 2\n", "plot(y)"]]
    with pytest.raises(ValueError, match="no cell has the id 'zz'"):
        sync.apply_edits(json.dumps(nb).encode(), [{"cell_id": "zz", "source": ""}])


def test_menu_lights_out_and_led_test_stop_like_their_icons():
    menu = _read("RQB2-config", "RQB2_menu.sh")
    qlo = menu[menu.index("run_qlo_demo() {"):]
    qlo = qlo[:qlo.index("\n}\n")]
    # the engine, as the icons: plain step lines and Enter stops it
    assert 'run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-lights-out console' in qlo
    assert 'run_engine_demo "$BIN_DIR/rq_demo_run.sh" quantum-lights-out\n' in qlo
    assert "lights_out.py" not in qlo
    test = menu[menu.index("            test )"):]
    test = test[:test.index(";;")]
    assert 'run_engine_demo "$BIN_DIR/rq_demo_run.sh" led-demos led-test' in test
    assert "_rq_pause" in test and "rq_led_test.sh" not in test
