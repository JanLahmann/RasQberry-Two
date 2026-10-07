"""
Tests for RQB2-bin/rq_led_painter.sh before it starts (user test #6: the
painter stayed dark on the Pi 4 four-panel kit, and nothing said why).

  * Another program on the LED panel: the painter names it and offers to stop
    it, with the dialog of the other LED demos (led_panel_ready), although the
    painter itself runs as the desktop user (the check runs through sudo).
  * A renderer that does not keep running: one plain line says that the panel
    stays dark.

Stub tools on PATH (sudo, systemctl, whiptail) and a fake home with an
installed checkout and venv; no Raspberry Pi, GPIO or root needed.
"""

import os
import pty
import select
import shutil
import stat
import subprocess
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_PAINTER = os.path.join(_BIN, "rq_led_painter.sh")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_ENV_CONFIG = os.path.join(_ROOT, "RQB2-config", "rasqberry_env-config.sh")
_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                                reason="bash and jq are required")


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def painter(tmp_path):
    """An installed LED-Painter in a fake home; returns (env, log file)."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    home = tmp_path / "home"
    demo = home / "RasQberry-Two" / "demos" / "RasQberry-Two-LED-Painter"
    demo.mkdir(parents=True)
    (demo / "LED_painter.py").write_text("from PyQt5 import QtWidgets\n# _rq_canvas_rect\n")
    venv = home / "RasQberry-Two" / "venv" / "RQB2" / "bin"
    venv.mkdir(parents=True)
    (venv / "activate").write_text("")
    _exe(venv / "python3", f'#!/bin/sh\n[ "$1" = -c ] && exit 0\necho "painter $*" >> "{log}"\n')
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    # The panel check runs as root through sudo: the stub runs it with a
    # rq_common.sh whose led_holders reports FAKE_HOLDER
    fake_common = tmp_path / "rq_common_fake.sh"
    fake_common.write_text(f'. "{_COMMON}"\n'
                           'led_holders() { [ -z "${FAKE_HOLDER:-}" ] || echo "4242 $FAKE_HOLDER"; }\n'
                           f'stop_led_holders() {{ echo "stopped $1" >> "{log}"; }}\n')
    _exe(stubs / "sudo", '#!/bin/bash\n[ "$1" = -n ] && shift\nargs=()\n'
                         'for a in "$@"; do case "$a" in */rq_common.sh) a="$FAKE_COMMON" ;; esac; args+=("$a"); done\n'
                         'exec "${args[@]}"\n')
    _exe(stubs / "systemctl", f'#!/bin/sh\necho "systemctl $*" >> "{log}"\n'
                              'case "$1" in is-active) exit "${STUB_ACTIVE:-0}" ;; esac\nexit 0\n')
    _exe(stubs / "whiptail", f'#!/bin/sh\necho "whiptail $*" >> "{log}"\nexit "${{WT_RC:-0}}"\n')
    env = {
        "PATH": f"{stubs}:{os.environ['PATH']}",
        "HOME": str(home),
        "USER": "rasqberry",
        "RQ_CONFIG_FILE": str(env_config),
        "RQ_ENV_FILE": str(env_file),
        "FAKE_COMMON": str(fake_common),
        "WAYLAND_DISPLAY": "wayland-0",
        "TERM": "xterm",
    }
    return env, log


def _run(env, extra=None):
    proc = subprocess.run(["bash", _PAINTER], env=dict(env, **(extra or {})), capture_output=True,
                          text=True, timeout=60, start_new_session=True, stdin=subprocess.DEVNULL)
    return proc, proc.stdout + proc.stderr


def _run_in_a_window(env, extra=None, timeout=30):
    pid, fd = pty.fork()
    if pid == 0:  # pragma: no cover - child
        os.execvpe("bash", ["bash", _PAINTER], dict(env, **(extra or {})))
    out, end = b"", time.time() + timeout
    while time.time() < end:
        if select.select([fd], [], [], 0.2)[0]:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                break
            out += chunk
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def test_free_panel_and_a_running_renderer_start_quietly(painter):
    env, log = painter
    proc, out = _run(env)
    assert proc.returncode == 0, out
    calls = log.read_text()
    assert "systemctl start rasqberry-led-renderer" in calls
    assert "systemctl is-active --quiet rasqberry-led-renderer" in calls
    assert calls.index("systemctl start") < calls.index("painter LED_painter.py")
    assert "stays dark" not in out and "in use" not in out and "whiptail" not in calls


def test_a_renderer_that_did_not_start_is_said_in_one_line(painter):
    env, log = painter
    proc, out = _run(env, {"STUB_ACTIVE": "3"})
    assert proc.returncode == 0, out
    assert "The LED panel stays dark: the LED renderer did not start" in out
    assert "painter LED_painter.py" in log.read_text()      # the window still opens


def test_without_a_window_another_program_on_the_panel_is_named(painter):
    env, log = painter
    proc, out = _run(env, {"FAKE_HOLDER": "the IP address scroll at start-up"})
    assert proc.returncode == 0, out
    assert "The LED panel is in use by: the IP address scroll at start-up" in out


def test_in_a_window_the_busy_dialog_can_stop_the_other_program(painter):
    env, log = painter
    rc, out = _run_in_a_window(env, {"FAKE_HOLDER": "RasQ-LED Demo"})
    assert rc == 0, out
    calls = log.read_text()
    assert "whiptail --title LED Panel in Use --yes-button Stop It" in calls
    assert "stopped 4242 RasQ-LED Demo" in calls
    assert calls.index("stopped") < calls.index("systemctl start rasqberry-led-renderer")


def test_in_a_window_cancel_leaves_the_other_program_and_does_not_start(painter):
    env, log = painter
    rc, out = _run_in_a_window(env, {"FAKE_HOLDER": "RasQ-LED Demo", "WT_RC": "1"})
    assert rc == 0, out
    calls = log.read_text()
    assert "LED Panel in Use" in calls
    assert "stopped" not in calls and "systemctl start" not in calls and "painter" not in calls
