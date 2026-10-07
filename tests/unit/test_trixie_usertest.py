"""
Tests for the Trixie user test of 2026-10-06 (Pi 5, dev-trixie-2026-10-06-190843).

- T1: every desktop icon asked "Execute File": trixie's pcmanfm-pi reads
  quick_exec from the profile's pcmanfm.conf, not from libfm.conf.
- T2: the Pi 5 kernel (6.18) no longer waits for a frame in the PIO write, so a
  frame written right after another one was lost (RasQ-LED, SAP LED dark).
- T3: the on-screen LED view takes no keyboard focus.
- T4: Ctrl+C while a demo window waits ("read -t") ended in a bash abort.
- T5: icon rows overlapped (pcmanfm-pi counts y from the top of the screen,
  taller labels), touch-mode labels ran under the browser, catalogue icons
  landed apart.
- N2: see test_demo_remove_list.py.
- N3: Quantum Fractals: closing its first window did not stop it.
"""

import importlib.util
import json
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_COMMON = os.path.join(_BIN, "rq_common.sh")
sys.path.insert(0, _BIN)
import rq_desktop_session as ds  # noqa: E402

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _read(*parts):
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


# --- T1: quick_exec in the profile's pcmanfm.conf --------------------------------

def test_quick_exec_goes_into_a_copy_of_the_system_pcmanfm_conf(tmp_path):
    system = tmp_path / "xdg"
    (system / "default").mkdir(parents=True)
    (system / "default" / "pcmanfm.conf").write_text(
        "[config]\nsingle_click=0\nuse_trash=1\n\n[ui]\nbig_icon_size=48\n")
    conf = tmp_path / "home" / ".config" / "pcmanfm" / "default" / "pcmanfm.conf"
    assert ds.ensure_quick_exec("default", str(conf), str(system)) is True
    text = conf.read_text()
    assert text.startswith("[config]\nquick_exec=1\nsingle_click=0\n")
    assert "[ui]\nbig_icon_size=48" in text
    # already there: nothing to write, pcmanfm needs no reload
    assert ds.ensure_quick_exec("default", str(conf), str(system)) is False


def test_quick_exec_is_switched_on_in_an_existing_pcmanfm_conf(tmp_path):
    conf = tmp_path / "pcmanfm.conf"
    conf.write_text("[ui]\nbig_icon_size=72\n[config]\nquick_exec=0\nuse_trash=1\n")
    assert ds.ensure_quick_exec("default", str(conf), str(tmp_path / "none")) is True
    assert conf.read_text() == "[ui]\nbig_icon_size=72\n[config]\nquick_exec=1\nuse_trash=1\n"
    bare = tmp_path / "bare.conf"
    bare.write_text("[ui]\nbig_icon_size=48\n")
    assert ds.ensure_quick_exec("default", str(bare), str(tmp_path / "none")) is True
    assert bare.read_text() == "[ui]\nbig_icon_size=48\n\n[config]\nquick_exec=1\n"


def test_icon_size_comes_from_pcmanfm_conf_before_libfm_conf(tmp_path):
    pcm, libfm = tmp_path / "pcmanfm.conf", tmp_path / "libfm.conf"
    libfm.write_text("[ui]\nbig_icon_size=48\n")
    assert ds.libfm_icon_size(str(pcm), str(libfm)) == 48          # bookworm: no pcmanfm.conf
    pcm.write_text("[config]\nquick_exec=1\n[ui]\nbig_icon_size=72\n")
    assert ds.libfm_icon_size(str(pcm), str(libfm)) == 72
    assert ds.libfm_icon_size(str(tmp_path / "x"), str(tmp_path / "y")) == 48


def test_the_image_and_the_first_login_set_quick_exec_for_the_profile():
    stage = _read("stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")
    assert 'rq_desktop_session.py" --quick-exec "$USER_CONFIG_DIR/pcmanfm.conf"' in stage
    assert 'cp "$USER_CONFIG_DIR/pcmanfm.conf" "$SKEL_CONFIG_DIR/pcmanfm.conf"' in stage
    trust = _read("RQB2-system", "usr", "local", "bin", "trust-rasqberry-desktop-files.sh")
    assert "rq_desktop_session.py --quick-exec" in trust


def test_login_reloads_pcmanfm_when_quick_exec_was_added(monkeypatch):
    calls = []
    monkeypatch.setattr(ds, "reset_chromium_exit", lambda: None)
    monkeypatch.setattr(ds, "apply_touch_css", lambda touch: None)
    monkeypatch.setattr(ds, "touch_mode_on", lambda: False)
    monkeypatch.setattr(ds, "screen_size", lambda: (1920, 1080))
    monkeypatch.setattr(ds, "set_small_screen_flag", lambda small: None)
    monkeypatch.setattr(ds, "set_chromium_rule", lambda small: False)
    monkeypatch.setattr(ds, "layout_desktop", lambda size, touch: False)
    monkeypatch.setattr(ds, "ensure_quick_exec", lambda: True)
    monkeypatch.setattr(ds, "run_quietly", calls.append)
    assert ds.main(["--no-browser"]) == 0
    assert calls == [["pcmanfm", "--reconfigure"]]


# --- T5: icon layout on trixie -----------------------------------------------------

def test_label_height_follows_the_desktop_font(tmp_path):
    conf = tmp_path / "desktop-items-0.conf"
    conf.write_text("[*]\ndesktop_font=PibotoLt 12\n")
    assert ds.label_height(str(conf)) == ds.LABEL_HEIGHT
    conf.write_text("[*]\ndesktop_font=Nunito Sans Light 12\n")
    assert ds.label_height(str(conf)) == ds.LABEL_HEIGHT_NUNITO
    assert ds.label_height(str(tmp_path / "missing")) == ds.LABEL_HEIGHT_NUNITO


@pytest.mark.parametrize("touch,icon", [(False, 48), (True, 72)])
def test_trixie_rows_start_below_the_panel_and_do_not_overlap(touch, icon):
    panel = 64 if touch else 36
    top = ds.layout_top(touch, "default")
    assert top == panel and ds.layout_top(touch, "LXDE-pi") == 0
    label = ds.LABEL_HEIGHT_NUNITO
    pos, overflow = ds.plan_layout(ds.ICON_ORDER, 1920, 1080, touch=touch, icon=icon,
                                   label=label, top=top)
    assert not overflow
    # pcmanfm-pi counts from the top of the screen: the first row clears the panel
    assert pos["rasqberry-setup"] == (10, panel + 10)
    ys = sorted({y for _, y in pos.values()})
    assert all(b - a >= icon + label for a, b in zip(ys, ys[1:]))
    assert max(ys) + icon + label <= 1080
    # the last column's labels end left of the browser (touch mode: they ran under it)
    assert max(x for x, _ in pos.values()) + ds.ITEM_WIDTH <= ds.CHROMIUM_X


def test_build_layout_uses_the_desktop_profile_and_font(tmp_path, monkeypatch):
    conf = tmp_path / "c.conf"
    conf.write_text("[*]\ndesktop_font=Nunito Sans Light 12\n")
    monkeypatch.setattr(ds, "pcmanfm_profile", lambda autostart=None: "default")
    assert ds.main(["--layout", "1920x1080", str(conf)]) == 0
    text = conf.read_text()
    assert "[rasqberry-setup.desktop]\nx=10\ny=46\ntrusted=true\n" in text
    rows = sorted({int(y) for y in re.findall(r"^y=(\d+)", text, re.M)})
    assert rows[1] - rows[0] >= 48 + ds.LABEL_HEIGHT_NUNITO


def test_catalogue_launchers_join_the_grid(tmp_path, monkeypatch):
    desk, conf, rec = tmp_path / "Desktop", tmp_path / "d.conf", tmp_path / "rec"
    desk.mkdir()
    for n in ds.ICON_ORDER:
        (desk / f"{n}.desktop").write_text(n)
    (desk / "rq-ext-sap-quantum-led.desktop").write_text("x")
    (desk / "notes.desktop").write_text("someone else's")
    conf.write_text("[*]\ndesktop_font=Nunito Sans Light 12\n")
    monkeypatch.setattr(ds, "libfm_icon_size", lambda path=None, libfm=None: 48)
    monkeypatch.setattr(ds, "pcmanfm_profile", lambda autostart=None: "default")
    names = ds.present_launchers(str(desk))
    assert names == ds.ICON_ORDER + ["rq-ext-sap-quantum-led"]
    assert ds.layout_desktop((1920, 1080), False, desktop=str(desk), conf=str(conf), record=str(rec))
    m = re.search(r"\[rq-ext-sap-quantum-led\.desktop\]\nx=(\d+)\ny=(\d+)", conf.read_text())
    assert m and int(m.group(1)) + ds.ITEM_WIDTH <= ds.CHROMIUM_X
    assert "[notes.desktop]" not in conf.read_text()
    assert json.loads(rec.read_text())["icons"][-1] == "rq-ext-sap-quantum-led"


def test_adding_a_catalogue_demo_lays_the_desktop_out_again():
    text = _read("RQB2-bin", "rq_demo_add_external.sh")
    assert 'mv -f "$tmp" "$out"; relayout_desktop' in text
    assert re.search(r'rm -f "\$manifest" .*\n\s*relayout_desktop', text)
    assert "--relayout" in text


@needs_bash
def test_touch_mode_sets_the_icon_size_in_pcmanfm_conf_too(tmp_path):
    home = tmp_path / "home"
    (home / ".config" / "libfm").mkdir(parents=True)
    (home / ".config" / "libfm" / "libfm.conf").write_text("[ui]\nbig_icon_size=48\n")
    pcm = home / ".config" / "pcmanfm" / "default" / "pcmanfm.conf"
    pcm.parent.mkdir(parents=True)
    pcm.write_text("[config]\nquick_exec=1\n[ui]\nbig_icon_size=48\n")
    cfg = tmp_path / "env-config.sh"
    cfg.write_text(f'REPO=RasQberry-Two\nUSER_HOME="{home}"\n')
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "sudo").write_text('#!/bin/sh\n[ "$1" = -n ] && shift\nexec "$@"\n')
    (stubs / "systemctl").write_text("#!/bin/sh\nexit 3\n")
    (stubs / "pgrep").write_text("#!/bin/sh\nexit 1\n")
    for f in stubs.iterdir():
        f.chmod(0o755)
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
           "RQ_CONFIG_FILE": str(cfg), "RQ_TOUCH_STATE_FILE": str(tmp_path / "touch.conf")}

    def run(*args):
        return subprocess.run(["bash", os.path.join(_BIN, "rq_touch_mode.sh"), *args],
                              capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)

    p = run("enable")
    assert p.returncode == 0, p.stderr
    assert "big_icon_size=72" in pcm.read_text() and "quick_exec=1" in pcm.read_text()
    assert "Desktop icons:  72 px" in run("status").stdout
    p = run("disable")
    assert p.returncode == 0, p.stderr
    assert pcm.read_text() == "[config]\nquick_exec=1\n[ui]\nbig_icon_size=48\n"


# --- T2: Pi 5 frame pacing -----------------------------------------------------------

def _led_utils():
    spec = importlib.util.spec_from_file_location("rq_led_utils_t2", os.path.join(_BIN, "rq_led_utils.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_frame_is_not_written_before_the_previous_one_is_out():
    """Kernel 6.18 returns from the write when the frame starts: the next
    frame must wait for it plus the pause that ends a frame, or the LEDs pass
    it on down the chain and it is lost (RasQ-LED, SAP LED: panel dark)."""
    led = _led_utils()
    starts = []

    def async_write(pin, buf):           # 6.18: returns at once
        starts.append(time.monotonic())

    guarded = led._guarded_pi5_write(async_write, lambda: None)
    buf = bytes(576)                     # 192 LEDs: 5.76 ms on the wire
    for _ in range(4):
        guarded("pin", buf)
    frame = len(buf) * led.LED_BYTE_SECONDS
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    assert all(g >= frame + led.LED_LATCH_SECONDS - 0.0005 for g in gaps), gaps
    # the last frame is let out before the program ends
    t = time.monotonic()
    led._wait_for_last_frame()
    assert time.monotonic() - t >= frame * 0.5


def test_a_driver_that_waits_for_the_frame_only_adds_the_pause():
    """Kernel 6.12 (bookworm) blocked until the frame was out: no extra
    frame time on top, so animations keep their speed there."""
    led = _led_utils()
    frame = 576 * led.LED_BYTE_SECONDS
    start = 100.0
    assert led._frame_out_at(start, start + frame * 0.9, 576) == pytest.approx(
        start + frame * 0.9 + led.LED_LATCH_SECONDS)
    assert led._frame_out_at(start, start + 0.0001, 576) == pytest.approx(
        start + 0.0001 + frame + led.LED_LATCH_SECONDS)


# --- T3: the on-screen LED view takes no keyboard focus -------------------------------

def test_the_led_view_never_takes_the_keyboard_focus():
    text = _read("RQB2-bin", "rq_led_virtual_gui.py")
    # set right after the window is made, before mainloop maps it
    made = text.index("self.root = tk.Tk()")
    focus = text.index('self.root.wm_focusmodel("active")')
    assert made < focus < text.index("self.root.mainloop()")


# --- T4: Ctrl+C while a demo window waits ----------------------------------------------

class _Pty:
    def __init__(self, script):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # pragma: no cover - child
            os.execvp("bash", ["bash", "-c", script])
        self.out = b""

    def read_until(self, text, timeout=15):
        end = time.time() + timeout
        while time.time() < end and text.encode() not in self.out:
            if select.select([self.fd], [], [], 0.2)[0]:
                try:
                    self.out += os.read(self.fd, 4096)
                except OSError:
                    break
        return text.encode() in self.out

    def wait(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                return os.waitstatus_to_exitcode(status)
            self.read_until("\0", 0.2)
        os.kill(self.pid, signal.SIGKILL)
        raise AssertionError("did not end: " + self.out.decode(errors="replace"))


@needs_bash
def test_ctrl_c_runs_the_stop_trap_after_the_read_not_inside_it(tmp_path):
    """Bash 5.2 aborted ("stack smashing detected", "longjmp causes
    uninitialized stack frame", 134) when the 2 s read alarm fired inside
    a long INT trap - every time on the Pi 5 with a demo that takes 1.5 s
    to stop. The trap now runs after read has returned, with the caller's
    own trap, and the demo is stopped."""
    marker = tmp_path / "stopped"
    p = _Pty(f'. "{_COMMON}"; rq_run_demo T4 bash -c '
             f'"trap \\"sleep 1.5; echo yes > {marker}; exit 0\\" TERM; echo READY; sleep 100 & wait"; '
             f'echo NOT-REACHED')
    assert p.read_until("READY")
    time.sleep(1.3)
    os.write(p.fd, b"\x03")
    assert p.wait() == 130
    out = p.out.decode(errors="replace")
    assert "longjmp" not in out and "smashing" not in out and "NOT-REACHED" not in out
    assert marker.read_text().strip() == "yes"


@needs_bash
def test_deferred_read_keeps_the_callers_traps_and_status():
    script = (f'. "{_COMMON}"; trap "echo INT-TRAP" INT; '
              'rq_read_deferred -r -t 1 x < /dev/null; echo "rc=$?"; '
              'echo hello | { rq_read_deferred -r -t 1 x; echo "rc=$? x=$x"; }; '
              'trap -p INT; trap -p TERM | wc -c')
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    assert "rc=1" in out and "rc=0 x=hello" in out
    assert "trap -- 'echo INT-TRAP' SIGINT" in out
    assert out.strip().endswith("0")          # no TERM trap left behind


def test_every_wait_loop_reads_through_the_deferred_read():
    common = _read("RQB2-bin", "rq_common.sh")
    assert "read -r -t 2 _" not in common.replace("rq_read_deferred -r -t 2 _", "")
    assert "rq_read_deferred -t 1 -n 1 key" in _read("RQB2-bin", "rq_demo_loop.sh")


# --- N3: Quantum Fractals ----------------------------------------------------------------

def test_fractals_keeps_one_window_until_it_is_closed():
    text = _read("RQB2-bin", "fractal_files", "fractals.py")
    # one browser window for the pictures and the animation: no second driver
    assert text.count("WebClient(") == 1
    tail = text[text.index("Putting the pictures together"):]
    assert tail.index("find_element") < tail.index("driver.get(gif_url)")
    assert "driver.quit()\n\nprint(\"Putting" not in text


# --- Pi 4: views of root-run demos used the wrong layout ----------------------------

def test_env_file_is_read_without_python_dotenv(tmp_path, monkeypatch):
    """The system Python on trixie has no dotenv: the on-screen and browser
    views of a demo run as root fell back to single-24x8 on a quad-4x12 kit."""
    led = _led_utils()
    env = tmp_path / "env"
    env.write_text('# c\nLED_LAYOUT=quad-4x12\nLED_COUNT="192"\nexport LED_WEB=false\n'
                   "LED_PIXEL_ORDER='GRB'\nX=a # note\n")
    monkeypatch.setattr(led, "ENV_FILE", str(env))
    monkeypatch.setattr(led, "dotenv_values", None)
    assert led.get_led_config()["led_layout"] == "quad-4x12"
    raw = led._plain_env_values(str(env))
    assert raw["LED_COUNT"] == "192" and raw["LED_WEB"] == "false"
    assert raw["LED_PIXEL_ORDER"] == "GRB" and raw["X"] == "a"


def test_the_views_start_with_the_demos_own_python():
    text = _read("RQB2-bin", "rq_led_utils.py")
    assert "[sys.executable or 'python3', script]" in text
    assert "['python3', script]" not in text


def test_a_removed_catalogue_launcher_leaves_no_position(tmp_path):
    conf = tmp_path / "d.conf"
    conf.write_text("[*]\nx=1\n[rq-ext-old.desktop]\nx=120\ny=706\ntrusted=true\n[mine.desktop]\nx=1\ny=2\n")
    ds.write_positions(str(conf), {"composer": (10, 46)})
    text = conf.read_text()
    assert "rq-ext-old" not in text and "[mine.desktop]" in text and "[composer.desktop]" in text
