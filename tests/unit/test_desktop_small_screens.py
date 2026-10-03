"""
Tests for B8 "desktop, small screens, touch": rq_desktop_session.py (screen
size, icon layout, More folder, Chromium rule and crash state) and
rq_touch_mode.sh (asks before a restart, restarts lightdm instead of ending the
session, no colour codes, files restored).
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
sys.path.insert(0, _BIN)
import rq_desktop_session as ds  # noqa: E402

_TOUCH = os.path.join(_BIN, "rq_touch_mode.sh")
_BOOKMARKS = os.path.join(_ROOT, "RQB2-config", "desktop-bookmarks")


# --- screen size ---------------------------------------------------------------

def test_wlr_randr_hdmi_and_headless():
    hdmi = ('HDMI-A-1 "Dell Inc. U2415"\n  Enabled: yes\n  Modes:\n'
            '    1280x720 px, 60.000000 Hz\n    1920x1200 px, 59.950001 Hz (preferred, current)\n'
            '  Position: 0,0\n  Transform: normal\n  Scale: 1.000000\n')
    assert ds.parse_wlr_randr(hdmi) == (1920, 1200)
    headless = 'NOOP-1 "Headless output 2"\n  Enabled: yes\n  Modes:\n    800x480 px (current)\n'
    assert ds.parse_wlr_randr(headless) == (800, 480)


def test_wlr_randr_skips_disabled_and_honours_rotation_and_scale():
    text = ('HDMI-A-1 "off"\n  Enabled: no\n  Modes:\n    1920x1080 px, 60 Hz (current)\n'
            'DSI-2 "Touch Display 2"\n  Enabled: yes\n  Modes:\n    720x1280 px, 60 Hz (preferred, current)\n'
            '  Transform: 90\n  Scale: 2.000000\n')
    assert ds.parse_wlr_randr(text) == (640, 360)
    assert ds.parse_wlr_randr("") is None


@pytest.mark.parametrize("size,small", [((1920, 1080), False), ((1600, 900), False),
                                        ((1280, 720), True), ((800, 480), True),
                                        ((720, 1280), True)])
def test_small_screens(size, small):
    assert ds.is_small(size) is small


# --- icon layout ---------------------------------------------------------------


@pytest.mark.parametrize("w,h,touch,icon", [(1920, 1080, False, 48), (800, 480, False, 48),
                                            (800, 480, True, 72), (1920, 1080, True, 72),
                                            (1280, 720, True, 72), (720, 1280, True, 72)])
def test_every_icon_is_on_screen_or_in_more(w, h, touch, icon):
    pos, overflow = ds.plan_layout(ds.ICON_ORDER, w, h, touch=touch, icon=icon)
    panel = 64 if touch else 36
    placed = [n for n in pos if n != ds.MORE_DIR]
    assert sorted(placed + overflow) == sorted(ds.ICON_ORDER)
    for x, y in pos.values():
        assert x + icon <= w and y + icon + ds.LABEL_HEIGHT <= h - panel, (x, y)
    # rows far enough apart that a label does not run into the next icon
    ys = sorted({y for _, y in pos.values()})
    assert all(b - a >= icon + ds.LABEL_HEIGHT for a, b in zip(ys, ys[1:]))
    assert (ds.MORE_DIR in pos) == bool(overflow)


def test_large_screen_keeps_setup_first_and_icons_left_of_chromium():
    # R-008: the Setup icon sat at x=450, under Chromium (x=480)
    for touch, icon in ((False, 48), (True, 72)):
        pos, overflow = ds.plan_layout(ds.ICON_ORDER, 1920, 1080, touch=touch, icon=icon)
        assert pos["rasqberry-setup"] == (10, 10) and not overflow
        grid = sorted({x for x, _ in pos.values()})
        cell = grid[1] - grid[0] - 10
        assert max(x for x, _ in pos.values()) + cell <= ds.CHROMIUM_X


def test_seven_inch_screen_fits_all_icons_without_touch_mode():
    # R-035: row 5 used to be off-screen at 800x480
    pos, overflow = ds.plan_layout(ds.ICON_ORDER, 800, 480)
    assert not overflow and len(pos) == len(ds.ICON_ORDER)


def test_seven_inch_touch_mode_uses_the_more_folder_for_the_last_icons():
    pos, overflow = ds.plan_layout(ds.ICON_ORDER, 800, 480, touch=True, icon=72)
    assert overflow == ds.ICON_ORDER[-len(overflow):]
    assert "touch-mode" in pos and "rasqberry-setup" in pos


def test_write_positions_keeps_settings_and_foreign_icons(tmp_path):
    conf = tmp_path / "desktop-items-0.conf"
    conf.write_text("[*]\nwallpaper_mode=fit\n[composer.desktop]\nx=560\ny=10\ntrusted=true\n"
                    "[my-own.desktop]\nx=700\ny=700\n")
    ds.write_positions(str(conf), {"composer": (10, 120), ds.MORE_DIR: (10, 230)})
    text = conf.read_text()
    assert text.startswith("[*]\nwallpaper_mode=fit\n")
    assert "[my-own.desktop]\nx=700\ny=700\n" in text
    assert "[composer.desktop]\nx=10\ny=120\ntrusted=true\n" in text
    assert "x=560" not in text and "[More]\nx=10\ny=230\n" in text


def test_more_folder_round_trip(tmp_path):
    desk = tmp_path / "Desktop"
    desk.mkdir()
    for n in ("demo-loop", "clear-leds", "composer"):
        (desk / f"{n}.desktop").write_text(n)
    (desk / "notes.txt").write_text("mine")
    ds.sort_into_more(str(desk), ["demo-loop", "clear-leds"])
    assert sorted(os.listdir(desk / "More")) == ["clear-leds.desktop", "demo-loop.desktop"]
    # a fresh copy on the desktop (e.g. reinstalled) wins over the folder's
    (desk / "demo-loop.desktop").write_text("new")
    ds.sort_into_more(str(desk), [])
    assert not (desk / "More").exists()
    assert (desk / "demo-loop.desktop").read_text() == "new"
    assert sorted(os.listdir(desk)) == ["clear-leds.desktop", "composer.desktop",
                                        "demo-loop.desktop", "notes.txt"]


def test_layout_only_when_something_changed(tmp_path, monkeypatch):
    # icons the user moved stay where they are until screen/touch/icons change
    desk, conf, rec = tmp_path / "Desktop", tmp_path / "d.conf", tmp_path / "rec"
    desk.mkdir()
    for n in ds.ICON_ORDER:
        (desk / f"{n}.desktop").write_text(n)
    conf.write_text("[*]\n")
    monkeypatch.setattr(ds, "libfm_icon_size", lambda path=None: 48)
    args = dict(desktop=str(desk), conf=str(conf), record=str(rec))
    assert ds.layout_desktop((1920, 1080), False, **args)
    conf.write_text(re.sub(r"(\[composer\.desktop\]\nx=)\d+", r"\g<1>900", conf.read_text()))
    assert not ds.layout_desktop((1920, 1080), False, **args)
    assert "x=900" in conf.read_text()
    assert ds.layout_desktop((800, 480), False, **args)
    assert "x=900" not in conf.read_text()
    assert json.loads(rec.read_text())["screen"] == [800, 480]


def test_build_layout_command(tmp_path):
    conf = tmp_path / "c.conf"
    conf.write_text("[*]\nshow_mounts=0\n")
    subprocess.run([sys.executable, os.path.join(_BIN, "rq_desktop_session.py"),
                    "--layout", "1920x1080", str(conf)], check=True)
    text = conf.read_text()
    assert text.startswith("[*]\nshow_mounts=0\n[rasqberry-setup.desktop]\nx=10\ny=10\ntrusted=true\n")
    assert text.count("trusted=true") == len(ds.ICON_ORDER)


# --- Chromium -------------------------------------------------------------------

_RC = '''<openbox_config>
  <windowRules>
    <windowRule identifier="chromium">
      <action name="MoveTo" x="480" y="45"/>
    </windowRule>
    <windowRule identifier="Kodi" serverDecoration="yes" />
  </windowRules>
</openbox_config>
'''


def test_chromium_rule_off_on_small_screens_and_back(tmp_path):
    rc = tmp_path / "rc.xml"
    rc.write_text(_RC)
    assert ds.set_chromium_rule(True, str(rc))
    assert 'identifier="rasqberry-small-screen-chromium"' in rc.read_text()
    assert not ds.set_chromium_rule(True, str(rc))
    assert ds.set_chromium_rule(False, str(rc))
    assert rc.read_text() == _RC
    assert not ds.set_chromium_rule(True, str(tmp_path / "missing.xml"))


def test_chromium_crash_state_reset(tmp_path):
    prefs = tmp_path / "Preferences"
    prefs.write_text('{"profile":{"exit_type":"Crashed","exited_cleanly":false,"name":"x"}}')
    assert ds.reset_chromium_exit(str(prefs))
    assert json.loads(prefs.read_text())["profile"] == {"exit_type": "Normal",
                                                       "exited_cleanly": True, "name": "x"}
    assert not ds.reset_chromium_exit(str(prefs))


def test_chromium_flags_file_is_plain_sh_and_ends_true(tmp_path):
    flags = os.path.join(_ROOT, "RQB2-system", "etc", "chromium.d", "rasqberry")
    text = open(flags).read()
    for flag in ("--password-store=basic", "--hide-crash-restore-bubble", "--start-maximized",
                 "--touch-events=enabled"):
        assert flag in text
    dash = shutil.which("dash") or shutil.which("sh")
    run = tmp_path / "run"
    run.mkdir()
    (run / "rasqberry-small-screen").write_text("")
    out = subprocess.run([dash, "-ec", f'CHROMIUM_FLAGS="-x"; . "{flags}"; echo "$CHROMIUM_FLAGS"'],
                         capture_output=True, text=True, env={**os.environ, "XDG_RUNTIME_DIR": str(run)})
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[0] == "-x" and "--start-maximized" in out.stdout


def test_autostart_runs_the_session_helper():
    path = os.path.join(_ROOT, "RQB2-system", "etc", "xdg", "autostart", "rasqberry-browser.desktop")
    assert "Exec=/usr/bin/rq_desktop_session.py\n" in open(path).read()
    assert os.access(os.path.join(_BIN, "rq_desktop_session.py"), os.X_OK)
    page = os.path.join(_ROOT, "RQB2-system", "usr", "share", "rasqberry", "offline.html")
    assert ds.OFFLINE_PAGE == "file:///usr/share/rasqberry/offline.html" and os.path.exists(page)


# --- launchers -------------------------------------------------------------------

def test_no_launcher_claims_file_types():
    # R-136: demo launchers were registered as .html/.py handlers
    for name in os.listdir(_BOOKMARKS):
        assert "\nMimeType=" not in open(os.path.join(_BOOKMARKS, name)).read(), name


def test_every_desktop_launcher_has_a_place_in_the_layout():
    script = open(os.path.join(_ROOT, "stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")).read()
    listed = set(re.search(r"\^\(([^)]*)\)\\\.desktop\$", script).group(1).split("|"))
    assert listed == set(ds.ICON_ORDER)


def test_touch_icon_asks_instead_of_logging_out():
    text = open(os.path.join(_BOOKMARKS, "touch-mode.desktop")).read()
    assert "Exec=/usr/bin/rq_touch_mode.sh toggle --ask\n" in text


# --- rq_touch_mode.sh --------------------------------------------------------------

def _gnu_tools():
    return shutil.which("bash") is not None


@pytest.fixture
def touch(tmp_path):
    """A home with the desktop's config files, stub sudo/systemctl/pgrep, and a runner."""
    home = tmp_path / "home"
    (home / ".config" / "libfm").mkdir(parents=True)
    (home / ".config" / "lxterminal").mkdir()
    (home / ".config" / "libfm" / "libfm.conf").write_text("[config]\nquick_exec=1\n[ui]\nbig_icon_size=48\n")
    (home / ".config" / "lxterminal" / "lxterminal.conf").write_text("[general]\nfontname=Monospace 10\n")
    (home / ".config" / "wf-panel-pi.ini").write_text("[panel]\nlauncher_000001=a.desktop\n")
    cfg = tmp_path / "env-config.sh"
    cfg.write_text(f'REPO=RasQberry-Two\nUSER_HOME="{home}"\nTOUCH_TERMINAL_FONT_SIZE=16\n')
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    (stubs / "sudo").write_text('#!/bin/sh\n[ "$1" = -n ] && shift\nexec "$@"\n')
    (stubs / "systemctl").write_text(
        f'#!/bin/sh\necho "systemctl $*" >> "{log}"\n'
        '[ "$1" = is-active ] && { [ "${FAKE_DESKTOP:-0}" = 1 ]; exit $?; }\nexit 0\n')
    (stubs / "pgrep").write_text('#!/bin/sh\n[ "${FAKE_DESKTOP:-0}" = 1 ]\n')
    for name in ("loginctl", "pkill"):
        (stubs / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
    for f in stubs.iterdir():
        f.chmod(0o755)

    def run(*args, desktop=False):
        env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
               "RQ_CONFIG_FILE": str(cfg), "RQ_TOUCH_STATE_FILE": str(tmp_path / "touch-mode.conf"),
               "FAKE_DESKTOP": "1" if desktop else "0"}
        return subprocess.run(["bash", _TOUCH, *args], capture_output=True, text=True, env=env,
                              stdin=subprocess.DEVNULL)

    run.home, run.log, run.state = home, log, tmp_path / "touch-mode.conf"
    return run


pytestmark_touch = pytest.mark.skipif(not _gnu_tools(), reason="bash required")


@pytestmark_touch
def test_enable_and_disable_without_restart(touch):
    p = touch("enable")
    assert p.returncode == 0, p.stderr
    cfg = touch.home / ".config"
    assert "big_icon_size=72" in (cfg / "libfm" / "libfm.conf").read_text()
    assert "[panel]\nicon_size=48\n" in (cfg / "wf-panel-pi.ini").read_text()
    # R-033: 16 pt from the env file is capped at 12
    assert "fontname=Monospace 12" in (cfg / "lxterminal" / "lxterminal.conf").read_text()
    assert "TOUCH_MODE=enabled" in touch.state.read_text()
    assert "restart" not in (touch.log.read_text() if touch.log.exists() else "")
    p = touch("disable")
    assert p.returncode == 0, p.stderr
    assert (cfg / "libfm" / "libfm.conf").read_text().endswith("big_icon_size=48\n")
    assert "icon_size" not in (cfg / "wf-panel-pi.ini").read_text()
    assert "fontname=Monospace 10" in (cfg / "lxterminal" / "lxterminal.conf").read_text()
    assert not list(cfg.rglob("*.touch-backup"))


@pytestmark_touch
def test_restart_restarts_lightdm_and_never_ends_the_session(touch):
    # R-149: ending the session left the password screen; R-032: SSH survived?
    p = touch("toggle", "--restart", desktop=True)
    assert p.returncode == 0, p.stderr
    calls = touch.log.read_text()
    assert "systemctl --no-block restart lightdm" in calls
    assert "loginctl" not in calls and "pkill" not in calls


@pytestmark_touch
def test_ask_without_an_answer_changes_nothing(touch):
    # the icon asks first; no display and no terminal here means "no"
    p = touch("toggle", "--ask", desktop=True)
    assert p.returncode == 0, p.stderr
    assert "Nothing changed" in p.stdout
    assert not touch.state.exists()
    assert "restart lightdm" not in touch.log.read_text()


@pytestmark_touch
def test_ask_without_a_desktop_just_applies(touch):
    p = touch("toggle", "--ask")
    assert p.returncode == 0, p.stderr
    assert "TOUCH_MODE=enabled" in touch.state.read_text()
    assert "next desktop login" in p.stdout


@pytestmark_touch
def test_status_is_plain_text_even_without_config_files(touch):
    # R-098: the menu showed raw ^[[0;32m codes
    shutil.rmtree(touch.home / ".config")
    p = touch("status")
    assert p.returncode == 0, p.stderr
    assert "\x1b[" not in p.stdout and p.stdout.startswith("Touch Mode: OFF")
    assert touch("status", "--quiet").stdout == "disabled\n"
    assert touch("bogus").returncode == 1
