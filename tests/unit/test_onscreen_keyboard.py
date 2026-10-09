"""
On-screen keyboard (user feedback on the Trixie A/B release, Pi 5 with a
touchscreen): the wvkbd launcher that replaced squeekboard closed the Wi-Fi
password popup when tapped, and wvkbd never opened by itself in text fields.

- trixie: stage 09 leaves Raspberry Pi OS's squeekboard on and adds neither
  wvkbd nor its panel launcher; bookworm builds keep wvkbd.
- the launcher hides where wvkbd is not installed (TryExec).
- touch mode works without a user panel file (trixie images have none now).
- the touch mode and setup checklist texts fit squeekboard.
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_STAGE = os.path.join(_ROOT, "stage-RQB2", "09-touchscreen-support", "00-run-chroot.sh")
_TOUCH = os.path.join(_BIN, "rq_touch_mode.sh")

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

_SQUEEK = "[Desktop Entry]\nName=Squeekboard\nExec=/usr/bin/sbtest\n"
_SYS_PANEL = ("[panel]\nwidgets_right=tray netman clock squeek\n"
              "launchers=x-www-browser pcmanfm x-terminal-emulator\n")


def _run_stage(tmp_path, trixie):
    """Run stage 09 against a fake root (paths under /etc and /home moved there)."""
    root = tmp_path / "root"
    (root / "etc" / "xdg" / "autostart").mkdir(parents=True)
    (root / "etc" / "xdg" / "autostart" / "squeekboard.desktop").write_text(_SQUEEK)
    if trixie:
        (root / "etc" / "xdg" / "wf-panel-pi").mkdir(parents=True)
        (root / "etc" / "xdg" / "wf-panel-pi" / "wf-panel-pi.ini").write_text(_SYS_PANEL)
    script = open(_STAGE).read().replace("/etc/", f"{root}/etc/").replace("/home/", f"{root}/home/")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "apt.log"
    (stubs / "apt-get").write_text(f'#!/bin/sh\necho "apt-get $*" >> "{log}"\n')
    (stubs / "apt-get").chmod(0o755)
    env = {"PATH": f"{stubs}:{os.environ['PATH']}", "FIRST_USER_NAME": ""}
    p = subprocess.run(["bash", "-e"], input=script, capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return root, (log.read_text() if log.exists() else "")


def _panel_files(root):
    return [p for p in root.rglob("*wf-panel-pi*.ini") if "xdg" not in p.parts]


@needs_bash
def test_trixie_keeps_squeekboard_and_adds_no_wvkbd(tmp_path):
    root, apt = _run_stage(tmp_path, trixie=True)
    autostart = root / "etc" / "xdg" / "autostart"
    assert (autostart / "squeekboard.desktop").read_text() == _SQUEEK
    assert not (autostart / "squeekboard.desktop.disabled").exists()
    assert "wvkbd" not in apt
    # no user panel file: the panel reads the system one, squeek widget included
    assert not _panel_files(root)
    assert (root / "etc" / "xdg" / "wf-panel-pi" / "wf-panel-pi.ini").read_text() == _SYS_PANEL


@needs_bash
def test_bookworm_keeps_wvkbd_and_its_launcher(tmp_path):
    root, apt = _run_stage(tmp_path, trixie=False)
    autostart = root / "etc" / "xdg" / "autostart"
    assert "apt-get install -y wvkbd" in apt
    assert (autostart / "squeekboard.desktop.disabled").exists()
    assert not (autostart / "squeekboard.desktop").exists()
    assert "virtual-keyboard.desktop" in (root / "etc" / "skel" / ".config" / "wf-panel-pi.ini").read_text()


def test_wvkbd_launcher_hides_without_wvkbd():
    desktop = os.path.join(_ROOT, "RQB2-system", "usr", "share", "applications", "virtual-keyboard.desktop")
    text = open(desktop).read()
    assert "TryExec=wvkbd-mobintl\n" in text
    assert "wvkbd-mobintl" in open(os.path.join(_ROOT, "RQB2-system", "usr", "local", "bin",
                                                "toggle-keyboard.sh")).read()


@pytest.fixture
def trixie_touch(tmp_path):
    """A trixie home without a user panel file, and a runner for rq_touch_mode.sh."""
    home = tmp_path / "home"
    home.mkdir()
    sys_panel = tmp_path / "xdg-wf-panel-pi.ini"
    sys_panel.write_text(_SYS_PANEL)
    cfg = tmp_path / "env-config.sh"
    cfg.write_text(f'REPO=RasQberry-Two\nUSER_HOME="{home}"\n')
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "sudo").write_text('#!/bin/sh\n[ "$1" = -n ] && shift\nexec "$@"\n')
    (stubs / "systemctl").write_text("#!/bin/sh\nexit 3\n")
    (stubs / "pgrep").write_text("#!/bin/sh\nexit 1\n")
    for f in stubs.iterdir():
        f.chmod(0o755)

    def run(*args, system_panel=True):
        env = {"PATH": f"{stubs}:{os.environ['PATH']}", "HOME": str(home), "USER": "rasqberry",
               "RQ_CONFIG_FILE": str(cfg), "RQ_TOUCH_STATE_FILE": str(tmp_path / "touch.conf"),
               "RQ_SYS_PANEL_CONFIG": str(sys_panel) if system_panel else str(tmp_path / "none")}
        return subprocess.run(["bash", _TOUCH, *args], capture_output=True, text=True, env=env,
                              stdin=subprocess.DEVNULL)

    run.panel = home / ".config" / "wf-panel-pi" / "wf-panel-pi.ini"
    return run


@needs_bash
def test_touch_mode_starts_a_user_panel_file_on_trixie(trixie_touch):
    p = trixie_touch("enable")
    assert p.returncode == 0, p.stderr
    assert trixie_touch.panel.read_text() == "[panel]\nicon_size=48\n"
    p = trixie_touch("disable")
    assert p.returncode == 0, p.stderr
    # back to the system defaults: no icon size, no launchers of our own
    assert trixie_touch.panel.read_text() == "[panel]\n"
    assert not list(trixie_touch.panel.parent.glob("*.touch-backup"))


@needs_bash
def test_touch_mode_fills_the_empty_panel_file_the_panel_writes(trixie_touch):
    # wf-panel-pi writes an empty user file at every desktop start; Touch Mode
    # still has to get its icon size in (rig check 2026-10-09, F1)
    trixie_touch.panel.parent.mkdir(parents=True)
    trixie_touch.panel.write_text("")
    p = trixie_touch("enable")
    assert p.returncode == 0, p.stderr
    assert trixie_touch.panel.read_text() == "[panel]\nicon_size=48\n"
    p = trixie_touch("disable")
    assert p.returncode == 0, p.stderr
    assert "icon_size=48" not in trixie_touch.panel.read_text()


@needs_bash
def test_touch_mode_status_names_the_keyboard_of_the_system(trixie_touch):
    out = trixie_touch("status").stdout
    assert "opens in text fields" in out and "keyboard icon in the top bar" in out
    out = trixie_touch("status", system_panel=False).stdout
    assert "The keyboard icon in the top bar opens an on-screen keyboard." in out


def test_checklist_keyboard_hint_fits_squeekboard():
    text = open(os.path.join(_BIN, "rq_firstlogin.sh")).read()
    assert "No keyboard? The keyboard icon in the top bar shows one on the screen." in text
    for word in ("wvkbd", "toggle-keyboard"):
        assert word not in text
