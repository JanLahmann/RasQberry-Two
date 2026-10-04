"""
Feedback 2026-10-03, batch C1 (menus, system texts): the main menu, System
Info, the raspi-config About box, and the A/B texts that are not covered in
test_menu_ab.py / test_update_slot.py.
"""

import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
sys.path.insert(0, _HERE)

from test_raspi_config_menu import menu_env  # noqa: E402,F401
from test_remote_access import stubs, _exe  # noqa: E402,F401


def _texts(menu_env):
    return "\n".join("\n".join(c) for c in menu_env.whiptail_calls())


# --- item 4: the main menu ---------------------------------------------------

def test_main_menu_has_desktop_settings_and_a_real_prompt(menu_env):
    menu_env("do_rasqberry_menu", extra_env={"WT_RC_menu": "1"})
    (call,) = menu_env.whiptail_calls()
    assert "Desktop Settings (touch mode, browser at login)" in call
    assert not any(a.startswith("Browser at login") for a in call)
    assert "System Options" not in call
    assert "Quantum demos, setup and settings for this RasQberry Two" in call


def test_desktop_settings_hold_touch_mode_and_the_browser(menu_env):
    menu_env("do_desktop_settings_menu", extra_env={"WT_RC_menu": "1"})
    texts = _texts(menu_env)
    assert "Touch mode (bigger icons and buttons): off" in texts
    assert "Browser at login (rasqberry.org): on" in texts


# --- item 1: raspi-config's About --------------------------------------------

def test_about_names_the_rasqberry_extension(menu_env):
    proc = menu_env("do_rasqberry_about; echo RC=$?")
    assert "RC=0" in proc.stdout
    texts = _texts(menu_env)
    assert "straightforward way of doing initial configuration" in texts
    assert '"0 RasQberry" is not part of raspi-config' in texts


# --- H-34: System Info --------------------------------------------------------

def _info_stub(menu_env, lines):
    fake = menu_env.tmp / "rq_info.sh"
    fake.write_text("#!/bin/sh\n" + "".join(f'echo "line {i}"\n' for i in range(lines)))
    fake.chmod(0o755)
    return fake


@pytest.mark.parametrize("rc", ["0", "255"])
def test_system_info_fits_and_esc_is_not_an_error(menu_env, rc):
    # 15 lines + the bug-report hint fit 80x24 without scrolling; Esc (255)
    # used to show "Failed to show system info"
    fake = _info_stub(menu_env, 15)
    code = (f'sed "s|/usr/bin/rq_info.sh|{fake}|g" "$RQ_MENU" > "$TMPDIR/m.sh"; . "$TMPDIR/m.sh"; '
            'do_show_system_info; echo RC=$?')
    proc = menu_env(code, extra_env={"WT_RC_msgbox": rc, "RQ_MENU": os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")})
    assert "RC=0" in proc.stdout, proc.stderr
    (call,) = menu_env.whiptail_calls()
    assert "--scrolltext" not in call
    width = int(call[-1])
    assert width <= 76
    assert "Failed to show" not in _texts(menu_env)


# --- item 2 and 24: rq_info.sh --------------------------------------------------

def _rq_info(stubs, tmp_path, summary=None):
    if summary is not None:
        _exe(tmp_path / "stubs" / "rq_slot_manager.sh", f"cat <<'EOF'\n{summary}\nEOF\n")
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    shutil.copy(os.path.join(_BIN, "rq_info.sh"), bindir / "rq_info.sh")
    if summary is not None:
        shutil.copy(tmp_path / "stubs" / "rq_slot_manager.sh", bindir / "rq_slot_manager.sh")
    env = dict(os.environ, PATH=stubs.path, RQ_BUILD_JSON=str(tmp_path / "none.json"))
    return subprocess.run(["bash", str(bindir / "rq_info.sh")], env=env,
                          capture_output=True, text=True, timeout=30)


def test_system_info_names_the_hardware(stubs, tmp_path):
    proc = _rq_info(stubs, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Hardware:" in proc.stdout.splitlines()[2]
    assert "No such file" not in proc.stderr


def test_single_system_card_says_one_system(stubs, tmp_path):
    summary = "\n".join(["layout=ab", "current=A", "confirmed=yes", "default=A", "pending=",
                         "slot_a=beta-2026-09-30-221656", "slot_b=EMPTY", "expanded=no",
                         "card_mode=single"])
    out = _rq_info(stubs, tmp_path, summary).stdout
    assert "one system on this card" in out
    assert "Slot B" not in out


def test_two_system_card_marks_the_default_slot(stubs, tmp_path):
    summary = "\n".join(["layout=ab", "current=B", "confirmed=yes", "default=B", "pending=",
                         "slot_a=beta-2026-09-30-221656", "slot_b=beta-2026-10-15-101010",
                         "expanded=yes", "card_mode=dual"])
    out = _rq_info(stubs, tmp_path, summary).stdout
    assert "Image type:        A/B, two systems (running Slot B)" in out
    assert "Slot A:            beta-2026-09-30-221656 (beta)\n" in out
    assert "Slot B:            beta-2026-10-15-101010 (beta) - running, start slot" in out
    assert "stable" not in out and "testing" not in out


# --- item 40: the name avahi really uses ---------------------------------------

def test_rename_reports_the_name_avahi_picked(stubs, tmp_path):
    _exe(tmp_path / "stubs" / "busctl", 'echo "s \\"rasqberry-07-2.local\\""\n')
    _exe(tmp_path / "stubs" / "timeout", 'shift\nexec "$@"\n')
    env = dict(os.environ, PATH=stubs.path, RQ_MDNS_WAIT="2")
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_remote_access.sh"), "name", "rasqberry-07"],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "rasqberry-07.local is taken" in proc.stdout and "rasqberry-07-2.local" in proc.stdout
