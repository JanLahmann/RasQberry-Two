#!/usr/bin/env python3
"""
Fixes from the fresh-card user tests of 2026-10-07 (demo side).

Run with:
    python3 -m pytest tests/unit/ -q
"""

import json
import os
import struct
import sys
import types

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_REPO_ROOT, "RQB2-bin")
sys.path.insert(0, _BIN)

import rq_led_utils as lu  # noqa: E402


def _read(name):
    with open(os.path.join(_BIN, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. The on-screen LED view during the LED panel check
# ---------------------------------------------------------------------------

def test_view_undoes_the_writer_brightness():
    """The check's white IBM at 15 % (38, 38, 38) was darker than the view's
    'off' grey (Pi 5 P3): the view shows it at full colour now."""
    assert lu.view_rgb(38, 38, 38, 38) == (255, 255, 255)
    assert lu.view_rgb(0, 0, 38, 38) == (0, 0, 255)
    assert lu.view_rgb(10, 20, 30, 0) == (10, 20, 30)       # not recorded: as is
    assert lu.view_rgb(10, 20, 30, 255) == (10, 20, 30)


def test_writer_records_its_brightness_in_the_header(tmp_path, monkeypatch):
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(tmp_path / "bus"))
    from rq_led_virtual import VirtualNeoPixel
    px = VirtualNeoPixel(None, 4, brightness=0.15, width=4, height=1)
    raw = (tmp_path / "bus").read_bytes()
    assert raw[:4] == b"RQL1"
    assert struct.unpack("<HHH", raw[4:10]) == (4, 1, 4)
    assert raw[10] == 38
    px.brightness = 0.4
    assert (tmp_path / "bus").read_bytes()[10] == 102
    px.deinit()


@pytest.fixture
def hint(tmp_path, monkeypatch):
    path = tmp_path / "view-layout.json"
    monkeypatch.setattr(lu, "VIEW_LAYOUT_HINT", str(path))
    monkeypatch.setattr(lu, "get_led_config", lambda: {"led_layout": "single-24x8"})
    return path


def test_view_follows_the_layout_the_check_draws_in(hint):
    assert lu.view_layout() == ("single-24x8", "single-24x8")
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    assert lu.view_layout() == ("quad-4x12", "quad-4x12")
    lu.clear_view_layout_hint()
    assert lu.view_layout() == ("single-24x8", "single-24x8")


def test_a_hint_from_a_check_that_died_does_not_count(hint):
    hint.write_text(json.dumps({"pid": 2 ** 22 + 12345, "layout": "quad-4x12",
                                "label": "quad-4x12"}))
    assert lu.view_layout() == ("single-24x8", "single-24x8")
    hint.write_text("not json")
    assert lu.view_layout() == ("single-24x8", "single-24x8")


def test_probe_names_its_layout_only_for_the_check(hint, monkeypatch):
    import rq_led_wizard_probe as probe
    monkeypatch.delenv("RQ_LED_VIEW_OWNER", raising=False)
    probe.tell_views("logo", "quad-4x12")
    assert not hint.exists()                         # demos never write it

    monkeypatch.setenv("RQ_LED_VIEW_OWNER", str(os.getpid()))
    probe.tell_views("logo", "quad-4x12")
    assert lu.view_layout() == ("quad-4x12", "quad-4x12")

    probe.tell_views("logo", "single-24x8", toggle_y=True)
    layout, label = lu.view_layout()
    assert label == "single-24x8, upside down"
    assert layout["y_flip"] != lu.get_layout("single-24x8").get("y_flip", False)

    probe.tell_views("clear", None)                  # raw chain order again
    assert not hint.exists()


def test_the_check_names_itself_for_the_probes():
    src = _read("rq_led_setup_wizard.sh")
    assert 'export RQ_LED_VIEW_OWNER="$$"' in src


def test_window_title_follows_the_layout(hint):
    pytest.importorskip("tkinter")
    import rq_led_virtual_gui as gui
    titles = []
    fake = types.SimpleNamespace(
        width=24, height=8, layout="single-24x8", label="single-24x8",
        _last_frame=(b"x", 38), root=types.SimpleNamespace(title=titles.append))
    fake._set_title = lambda: gui.VirtualLEDMatrix._set_title(fake)
    assert gui.VirtualLEDMatrix.follow_layout(fake) is False
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    assert gui.VirtualLEDMatrix.follow_layout(fake) is True
    assert titles[-1] == "RasQberry Virtual LED Matrix - 24x8 (quad-4x12)"
    assert fake._last_frame is None                  # redrawn in the new map


def test_web_view_shows_the_check_layout_and_undoes_brightness(tmp_path, monkeypatch, hint):
    import rq_led_web as web
    bus = tmp_path / "bus"
    count = 192
    pixels = bytearray(count * 3)
    idx = lu.map_xy_to_pixel(0, 0, layout="quad-4x12")
    pixels[idx * 3:idx * 3 + 3] = bytes((38, 38, 38))
    bus.write_bytes(b"RQL1" + struct.pack("<HHHB", 24, 8, count, 38) + b"\x00" * 5
                    + b"\x01" + bytes(pixels))
    monkeypatch.setenv("RQB2_LED_MMAP_PATH", str(bus))
    lu.set_view_layout_hint("quad-4x12", os.getpid())
    frame = web.read_frame()
    assert frame["layout"] == "quad-4x12"
    assert frame["rows"][0][0] == [255, 255, 255]


# ---------------------------------------------------------------------------
# 2. Quick LED Test (LEDs menu): the view closes with the test
# ---------------------------------------------------------------------------

def test_menu_led_demos_close_their_view():
    """run_led_demo blanked the panel but left the view open, also after
    raspi-config ended (Pi 4 F6); icon demos close it (--close-window)."""
    menu = open(os.path.join(_REPO_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    body = menu.split("run_led_demo() {", 1)[1].split("\n}\n", 1)[0]
    assert "do_led_off --close-window" in body
    assert 'python3 "$BIN_DIR/turn_off_LEDs.py" "$@"' in menu
    hangup = menu.split("_rq_demo_hangup() {", 1)[1].split("\n}\n", 1)[0]
    assert "do_led_off --close-window" in hangup


def test_stop_keys_close_an_idle_view(monkeypatch):
    pytest.importorskip("tkinter")
    import rq_led_virtual_gui as gui
    closed, status = [], []
    fake = types.SimpleNamespace(on_close=lambda: closed.append(1),
                                 status_var=types.SimpleNamespace(set=status.append))
    monkeypatch.setattr(gui, "stop_led_demo", lambda path: False)
    gui.VirtualLEDMatrix.on_stop_key(fake)
    assert closed == [1]
    monkeypatch.setattr(gui, "stop_led_demo", lambda path: True)
    gui.VirtualLEDMatrix.on_stop_key(fake)
    assert closed == [1] and status == ["Stopping the demo..."]


# ---------------------------------------------------------------------------
# 4. No "Notebook 7" banner over the classic notebook demos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("script", ["rq_fun_with_quantum.sh", "rq_demo_run.sh"])
def test_classic_notebook_without_the_migration_banner(script):
    assert "--NotebookApp.show_banner=False" in _read(script)


# ---------------------------------------------------------------------------
# 9. Ctrl+C in a demo started from a list is not an error
# ---------------------------------------------------------------------------

def test_chooser_takes_ctrl_c_as_a_stop():
    src = _read("rq_demo_choose.sh")
    loop = src.split('"$SCRIPT_DIR/rq_demo_run.sh" "$DEMO_ID" "$choice"', 1)[1]
    assert "|| rc=$?" in loop and "0|129|130|143) ;;" in loop


def test_learning_path_step_takes_ctrl_c_as_a_stop():
    src = _read("rq_learning_paths.sh")
    step = src.split("start_step() {", 1)[1].split("\n}\n", 1)[0]
    assert "case \"$rc\" in 0|129|130|143) return 0 ;; esac" in step


# ---------------------------------------------------------------------------
# 5. One question per download
# ---------------------------------------------------------------------------

from test_demo_consent import box, _ENGINE  # noqa: E402,F401  (fixture)


def test_courses_do_not_ask_for_what_tutorials_downloaded(box):
    d = box.home / "RasQberry-Two" / "demos" / "ibm-quantum-learning"
    d.mkdir(parents=True)
    proc = box([_ENGINE, "ibm-courses", "--install-only"], extra={"WT_RC": "1"})
    assert len(box.dialogs()) == 1                       # nothing there: asks
    (d / "WELCOME-tutorials.ipynb").write_text("{}")
    proc = box([_ENGINE, "ibm-courses", "--install-only"], extra={"WT_RC": "1"})
    assert len(box.dialogs()) == 1, proc.stdout          # no second question
    assert "uses what was downloaded for IBM Quantum Tutorials" in proc.stdout


def test_quantum_lab_asks_once_for_image_and_notebooks():
    src = _read("rq_quantum_lab.sh")
    block = src.split('info "IBM Quantum Learning content not found."', 1)[1].split("\nfi\n", 1)[0]
    assert '[ "${RQ_CONFIRMED_DEMO:-}" = "quantum-lab" ]' in block
    assert "RQ_AUTO_INSTALL=1 rq_require_demo_consent ibm-courses" in block
    lab = json.load(open(os.path.join(_REPO_ROOT, "RQB2-config", "demo-manifests",
                                      "rq_demo_quantum-lab.json")))
    assert "course notebooks" in lab["install"]["download"]["what"]


# ---------------------------------------------------------------------------
# 6. "Quantum Lights Out 0 MB" in Remove a demo
# ---------------------------------------------------------------------------

def test_a_small_checkout_is_at_least_1_mb(tmp_path):
    import re
    import subprocess
    src = _read("rq_demo_remove.sh")
    func = re.search(r"^dir_mb\(\) \{\n.*?^\}\n", src, re.M | re.S).group(0)
    (tmp_path / "qlo").mkdir()
    (tmp_path / "qlo" / "a.py").write_bytes(b"x" * 250_000)
    (tmp_path / "big").mkdir()
    (tmp_path / "big" / "b").write_bytes(b"x" * 3_500_000)
    script = (f"DEMOS_ROOT={tmp_path}\n{func}\n"
              'echo "$(dir_mb qlo) $(dir_mb big) $(dir_mb missing)"\n')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.split()
    assert out[0] == "1" and out[2] == "0"
    assert int(out[1]) in (4, 5)


# ---------------------------------------------------------------------------
# 7. Qoffee-Maker: Esc does not turn the kiosk into the raw notebook
# ---------------------------------------------------------------------------

_QOFFEE_JS = os.path.join(_REPO_ROOT, "RQB2-config", "demo-patches", "qoffee-appmode-custom.js")

_QOFFEE_HARNESS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const removed = [], listeners = {}, body = [];
const Jupyter = {notebook: {notebook_name: 'qoffee.ipynb', _fully_loaded: true,
                            kernel: {info_reply: {protocol_version: '5'}}},
  keyboard_manager: {command_shortcuts: {remove_shortcut: k => removed.push(k)}},
  actions: {exists: () => true, call: () => {}}};
global.document = {
  addEventListener: (ev, fn) => { listeners[ev] = fn; },
  getElementById: () => body[0] || null,
  createElement: () => ({style: {}}),
  body: {appendChild: el => body.push(el)}};
const timers = [];
console.log = console.warn = console.error = () => {};
new Function('require', 'setInterval', 'clearInterval', src)(
  (deps, cb) => cb(Jupyter, {on: () => {}}), fn => timers.push(fn), () => {});
timers.forEach(f => f());
listeners.keydown({key: 'Escape', keyCode: 27});
process.stdout.write(JSON.stringify({removed, hint: body.length ? body[0].textContent : ''}));
"""


def test_qoffee_kiosk_keeps_the_app_on_esc():
    import shutil
    import subprocess
    if shutil.which("node") is None:
        pytest.skip("node is required")
    proc = subprocess.run(["node", "-e", _QOFFEE_HARNESS, _QOFFEE_JS], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["removed"] == ["esc"]                 # no "Deactivate App Mode"
    assert "F11 leaves full screen" in out["hint"]


# ---------------------------------------------------------------------------
# 8. The Workshop server's first window goes with the server
# ---------------------------------------------------------------------------

def test_workshop_window_closes_when_the_server_is_stopped_elsewhere(tmp_path):
    import subprocess
    ver = subprocess.run(["bash", "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True,
                         text=True).stdout.strip()
    if int(ver or 0) < 4:
        pytest.skip("bash 4+ needed (read -t timeouts return > 128)")
    src = _read("rq_doqumentation.sh")
    start = src.index("    # Wait for Enter, but end with the server")
    block = src[start:src.index("    if command -v whiptail", start)]
    script = (
        'WORKSHOP_NAME="Workshop & Qiskit Server"; CONTAINER_NAME=doq\n'
        f'rq_docker_running() {{ n=$(cat {tmp_path}/n 2>/dev/null || echo 0); '
        f'echo $((n + 1)) > {tmp_path}/n; [ "$n" -lt 1 ]; }}\n'
        'rq_read_deferred() { read "$@"; }\ninfo() { echo "$*"; }\nsleep() { :; }\n'
        + block + 'echo "ASKED TO STOP"\n')
    r, w = os.pipe()                               # stdin stays open: no Enter
    proc = subprocess.Popen(["bash", "-c", script], stdin=r, stdout=subprocess.PIPE, text=True)
    os.close(r)
    out, _ = proc.communicate(timeout=20)
    os.close(w)
    assert proc.returncode == 0
    assert "was stopped" in out and "ASKED TO STOP" not in out


# ---------------------------------------------------------------------------
# 10. Small cards: no Docker demos on a 16 GB card, a note, not an error
#     (Jan, 2026-10-07: as rasqberry.org says, they need 32 GB or more)
# ---------------------------------------------------------------------------

_SMALL = {"RQ_TEST_FREE_MB": "50000", "RQ_TEST_ROOT_GB": "14"}


def _common_run(box, code, extra=None):
    from test_demo_consent import _COMMON
    return box(None, extra=extra, script=f'. "{_COMMON}"; load_rqb2_env; {code}')


def test_a_docker_download_on_a_small_card_is_a_note(box):
    # plenty of room does not matter: Docker demos need a 32 GB card
    proc = _common_run(box, 'rc=0; rq_confirm_download "Quantum Mixer" 1200 2300 --docker '
                       '--path "$USER_HOME" || rc=$?; echo "rc=$rc"; printf "%b\\n" "$RQ_CONSENT_MSG"',
                       extra=_SMALL)
    assert "rc=5" in proc.stdout, proc.stdout + proc.stderr
    assert ("Quantum Mixer is a Docker demo. Docker demos need an SD card of 32 GB or more; "
            "this card is 16 GB.") in proc.stdout
    assert "All other demos work on this card." in proc.stdout
    assert "Remove demos" not in proc.stdout and box.dialogs() == []


@pytest.mark.parametrize("args,gb,rc", [
    ("--docker", "28", "2"),       # a bigger card: removing demos can help
    ("", "14", "2")])              # a small demo on a full small card, likewise
def test_removing_demos_still_helps_elsewhere(box, args, gb, rc):
    proc = _common_run(box, f'rc=0; rq_confirm_download "Demo" 890 4000 {args} '
                       '--path "$USER_HOME" || rc=$?; echo "rc=$rc"; echo "$RQ_CONSENT_MSG"',
                       extra={"RQ_TEST_FREE_MB": "2000", "RQ_TEST_ROOT_GB": gb})
    assert f"rc={rc}" in proc.stdout and "Remove demos you do not use" in proc.stdout


def _docker_stub(box, have_image=False):
    from test_demo_consent import _exe
    log = box.tmp / "docker.log"
    _exe(box.stubs / "docker",
         f'#!/bin/sh\necho "$*" >> "{log}"\n'
         f'case "$1 $2" in "info "*) exit 0 ;; "image inspect") exit {0 if have_image else 1} ;; esac\nexit 1\n')
    return log


@pytest.mark.parametrize("demo,name", [("doqumentation", "Workshop & Qiskit Server"),
                                       ("qiskit-tutorials", "Qiskit Tutorials on this Pi"),
                                       ("quantum-lab", "Quantum Lab (QuBins)"),
                                       ("quantum-mixer", "Quantum Mixer"),
                                       ("qoffee-maker", "Qoffee-Maker")])
@pytest.mark.parametrize("install_only", [False, True])
def test_the_engine_stops_with_a_note_before_anything_else(box, demo, name, install_only):
    log = _docker_stub(box)
    args = [_ENGINE, demo] + (["--install-only"] if install_only else [])
    proc = box(args, extra=_SMALL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"{name} is a Docker demo. Docker demos need an SD card of 32 GB or more" in proc.stdout
    assert "please try it" not in proc.stdout.lower()          # no beta invitation first
    assert "ERROR" not in proc.stdout + proc.stderr and box.err() == ""
    # nothing pulled, nothing asked
    assert not any(line.startswith(("pull", "run")) for line in log.read_text().splitlines())
    assert [c for c in box.dialogs() if "--yesno" in c] == []


@pytest.mark.parametrize("gb,have_image", [("14", True), ("28", False)])
def test_the_engine_goes_on_with_the_image_here_or_on_a_bigger_card(box, gb, have_image):
    _docker_stub(box, have_image)
    proc = box([_ENGINE, "doqumentation", "--install-only"],
               extra={"RQ_TEST_FREE_MB": "50000", "RQ_TEST_ROOT_GB": gb})
    assert "is a Docker demo" not in proc.stdout


def test_consent_with_the_image_here_is_not_refused_on_a_small_card(box):
    _docker_stub(box, have_image=True)
    proc = _common_run(box, 'rc=0; rq_confirm_demo_install qoffee-maker || rc=$?; echo "rc=$rc"',
                       extra=_SMALL)
    assert "rc=5" not in proc.stdout, proc.stdout + proc.stderr


def test_docker_launchers_stop_before_their_first_download():
    # Quantum Lab fetched the course notebooks before its image question
    lab = _read("rq_quantum_lab.sh")
    assert lab.index("rq_stop_if_card_too_small") < lab.index("rq_require_demo_consent ibm-courses")
    # the others ask (rq_require_demo_consent: --docker, a note on a small card) first
    for f, demo in [("quantum-mixer.sh", "quantum-mixer"), ("qoffee-maker.sh", "qoffee-maker"),
                    ("rq_doqumentation.sh", "doqumentation")]:
        src = _read(f)
        assert src.index(f"rq_require_demo_consent {demo}") < src.index("docker pull" if "docker pull" in src
                                                                        else "rq_demo_docker_pull")
    assert "room for one Docker demo" not in _read("rq_common.sh")


def test_qiskit_tutorials_names_itself_in_the_download_question():
    assert 'RQ_CONSENT_NAME="$NAME" rq_require_demo_consent doqumentation' in _read("rq_doqumentation.sh")
    assert 'name="${RQ_CONSENT_NAME:-$name}"' in _read("rq_common.sh")


def test_catalogue_no_ends_quietly():
    src = _read("rq_demo_add_external.sh")
    assert "Installation cancelled by user" not in src
    no = src.split('Install it?"; then', 1)[1].split("fi", 1)[0]
    assert "return 0" in no


# ---------------------------------------------------------------------------
# 11. Polish: LED-Painter canvas, its GLib line
# ---------------------------------------------------------------------------

# The parts of upstream LED_painter.py (pinned commit 6a6a924) the fix edits
_PAINTER = '''import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout,
)
from PySide6.QtGui import QImage, QPixmap, QPen, QAction, QPainter, QColor
from PySide6.QtCore import Qt, QPoint

from display_to_LEDs_from_file import display_to_LEDs
from turn_off_LEDs import turn_off_LEDs


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 960, 320)
        self.image = QImage(24, 8, QImage.Format_RGB32)
        mainMenu = self.menuBar()
        imageLabel = QLabel()
        layout = QVBoxLayout()
        layout.addWidget(imageLabel)
        self.show()

    def paintEvent(self, event):
        canvasPainter = QPainter(self)
        canvasPainter.drawImage(self.rect(), self.image, self.image.rect())

    # Helper function to scale the mouse position from window size to canvas size (8x24)
    def scalePosition(self, pos):
        scaled_x = pos.x() / self.xScaleFactor
        scaled_y = pos.y() / self.yScaleFactor

        # Ensure the coordinates are within the bounds of the canvas
        return QPoint(min(scaled_x, 31), min(scaled_y, 7))

    def displayToLEDs(self):
        turn_off_LEDs()


def main():
    atexit.register(turn_off_LEDs)
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
'''


def test_painter_canvas_sits_below_the_menu_bar(tmp_path):
    import ast
    import importlib.util
    import types
    spec = importlib.util.spec_from_file_location(
        "lp_convert", os.path.join(_REPO_ROOT, "RQB2-config", "demo-patches",
                                   "led-painter-convert-to-pwm.py"))
    conv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conv)
    (tmp_path / "LED_painter.py").write_text(_PAINTER)
    assert conv.update_led_painter(str(tmp_path)) and conv.port_to_pyqt5(str(tmp_path))
    assert conv.fix_canvas(str(tmp_path))
    assert conv.fix_canvas(str(tmp_path))                  # again: no change
    assert conv.update_led_painter(str(tmp_path))          # no second import line
    src = (tmp_path / "LED_painter.py").read_text()
    ast.parse(src)
    assert src.count("from rq_led_utils import clear_all_leds") == 1
    assert "drawImage(self._rq_canvas_rect()" in src and "self.resize(960, 320 + mainMenu" in src
    # clicks map onto the canvas rect: a 960 x 320 canvas below a 30 px menu bar
    ns = {}
    body = src[src.index("    def scalePosition"):src.index("    def displayToLEDs")]

    class QPoint:
        def __init__(self, x, y):
            self.xy = (x, y)

    class QRect:
        def __init__(self, x, y, w, h):
            self.x, self.y, self.width, self.height = (lambda: x), (lambda: y), (lambda: w), (lambda: h)

    exec("class W:\n" + body, {"QPoint": QPoint}, ns)
    w = ns["W"]()
    w.image = types.SimpleNamespace(width=lambda: 24, height=lambda: 8)
    w._rq_canvas_rect = lambda: QRect(0, 30, 960, 320)
    pos = lambda x, y: types.SimpleNamespace(x=lambda: x, y=lambda: y)
    assert w.scalePosition(pos(0, 30)).xy == (0, 0)
    assert w.scalePosition(pos(959, 349)).xy == (23, 7)
    assert w.scalePosition(pos(5, 10)).xy == (0, 0)         # on the menu bar: clamped
    assert w.scalePosition(pos(500, 30 + 40 * 3 + 1)).xy == (12, 3)


def test_painter_is_converted_again_for_the_canvas_fix():
    src = _read("rq_led_painter.sh")
    assert src.count('grep -q "_rq_canvas_rect" "$DEMO_DIR/LED_painter.py"') == 2


def test_glib_line_at_the_painter_start_is_filtered(tmp_path):
    import subprocess
    from test_demo_consent import _COMMON
    line = ("(python3:29572): GLib-GObject-CRITICAL **: 11:06:47.155: g_object_unref: "
            "assertion 'G_IS_OBJECT (object)' failed")
    script = (f'. "{_COMMON}" >/dev/null 2>&1; rq_quiet_stderr sh -c '
              f'"echo \\"{line}\\" >&2; echo real error >&2"; sleep 0.3')
    err = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stderr
    assert "GLib-GObject-CRITICAL" not in err and "real error" in err
