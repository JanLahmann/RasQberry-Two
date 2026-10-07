"""
User test 2026-10-07, round 3 (Pi 4 without Imager settings, Pi 5 after an
A/B update): the published demo password (F1), the Connect box (R1), the SSH
switch's default (F2), the checklist's network line (F3), the Docker note on
a single-system card (F4) and the IBM LED demo's Enter (F5).

Runs unprivileged with the stub tools of test_remote_access.py.
"""

import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_MOTD = os.path.join(_ROOT, "RQB2-system", "etc", "update-motd.d", "20-rasqberry")
_REMOTE = os.path.join(_BIN, "rq_remote_access.sh")

sys.path.insert(0, _HERE)
from test_raspi_config_menu import menu_env  # noqa: E402,F401
from test_remote_access import _checklist, _exe, _texts, stubs  # noqa: E402,F401

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
needs_perl = pytest.mark.skipif(shutil.which("perl") is None, reason="perl required")

DEMO = "Qiskit1!"
NOTE = "This Pi uses the published demo password: change it with passwd or in the"


def _crypt(password):
    return subprocess.run(["perl", "-e", f'print crypt("{password}", "ab")'],
                          capture_output=True, text=True).stdout


def _getent(stubs_dir, hash_):
    """getent: uid 1000 is rasqberry, its shadow line holds hash_."""
    _exe(stubs_dir / "getent",
         'case "$1" in\n'
         '  passwd) echo "rasqberry:x:1000:1000::/home/rasqberry:/bin/bash" ;;\n'
         f'  shadow) echo "rasqberry:{hash_}:19000:0:99999:7:::" ;;\n'
         'esac\n')


# ---------------------------------------------------------------------------
# F1: the published demo password (Jan: pre-tick the step, short reminders)
# ---------------------------------------------------------------------------

@needs_perl
@pytest.mark.parametrize("password,state", [(DEMO, "yes"), ("someone's own", "no")])
def test_demo_password_state(stubs, tmp_path, password, state):
    _getent(tmp_path / "stubs", _crypt(password))
    proc = subprocess.run(["bash", _REMOTE, "demo-password"], env=dict(os.environ, PATH=stubs.path),
                          capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip() == state, proc.stderr
    assert DEMO not in proc.stdout + proc.stderr


@pytest.mark.parametrize("hash_,state", [("!", "no"), ("*", "no"), ("", "unknown")])
def test_demo_password_locked_or_unreadable(stubs, tmp_path, hash_, state):
    _getent(tmp_path / "stubs", hash_)
    proc = subprocess.run(["bash", _REMOTE, "demo-password"], env=dict(os.environ, PATH=stubs.path),
                          capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip() == state


@pytest.mark.parametrize("answer,shown", [("yes", True), ("no", False), ("unknown", False)])
def test_login_message_names_the_demo_password(stubs, tmp_path, answer, shown):
    fake = tmp_path / "remote"
    _exe(fake, f'[ "$1" = demo-password ] && echo {answer}\nexit 0\n')
    proc = subprocess.run(["sh", _MOTD], env=dict(os.environ, PATH=stubs.path, RQ_REMOTE_ACCESS=str(fake)),
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert (NOTE in proc.stdout) == shown
    assert max(len(line) for line in proc.stdout.splitlines()) <= 80


def _checklist_args(tmp_path):
    return (tmp_path / "wt.log").read_text().split("@@")[0].splitlines()


@needs_perl
def test_password_step_is_ticked_with_the_demo_password(stubs, tmp_path):
    _getent(tmp_path / "stubs", _crypt(DEMO))
    proc = _checklist(stubs, tmp_path, WT_RC_checklist="1")
    assert proc.returncode == 0, proc.stderr
    args = _checklist_args(tmp_path)
    i = args.index("password")
    assert args[i + 1] == "Change the password, or keep the demo one (booth, class)"
    assert args[i + 2] == "ON"
    assert args[args.index("name") + 2] == "OFF"          # the other optional steps stay unticked


@needs_perl
def test_no_password_step_with_an_own_password(stubs, tmp_path):
    _getent(tmp_path / "stubs", _crypt("from Imager"))
    _checklist(stubs, tmp_path, WT_RC_checklist="1")
    assert "password" not in _checklist_args(tmp_path)


@needs_perl
def test_password_step_esc_changes_nothing(stubs, tmp_path):
    _getent(tmp_path / "stubs", _crypt(DEMO))
    _exe(tmp_path / "stubs" / "chpasswd", f'echo "chpasswd" >> "{stubs.calls}"\n')
    proc = _checklist(stubs, tmp_path, WT_REPLY_checklist="password", WT_RC_menu="255")
    assert proc.returncode == 0, proc.stderr
    assert "chpasswd" not in stubs.logged()
    assert not (tmp_path / "home" / ".state" / "rasqberry" / "demo-password-kept").exists()
    texts = (tmp_path / "wt.log").read_text()
    assert "uses the published demo password: anyone can look it up" in texts


@needs_perl
@pytest.mark.parametrize("password,shown", [(DEMO, True), ("from Imager", False)])
def test_done_screen_reminds_of_the_demo_password(stubs, tmp_path, password, shown):
    _getent(tmp_path / "stubs", _crypt(password))
    proc = _checklist(stubs, tmp_path, WT_REPLY_checklist="name", WT_RC_inputbox="1")
    assert proc.returncode == 0, proc.stderr
    calls = (tmp_path / "wt.log").read_text().split("@@")
    done = next(c for c in calls if "--msgbox" in c and "First 15 minutes" in c)
    assert (NOTE in done) == shown
    assert "still" not in done


def _remote_menu(menu_env, status, demo):
    code = ('_rq_remote() { case "$1" in '
            f'status) echo "{status}" ;; demo-password) echo {demo} ;; esac; return 0; }}; '
            'do_remote_access_menu')
    proc = menu_env(code, extra_env={"WT_RC_menu": "1"})
    assert proc.returncode == 0, proc.stderr
    return _texts(menu_env)


@pytest.mark.parametrize("status,words", [
    ("ssh=on vnc=on ssh_password=yes", "SSH and VNC accept the published demo password: anyone on the same network can log in."),
    ("ssh=off vnc=on ssh_password=yes", "VNC accepts the published demo password"),
    ("ssh=on vnc=off ssh_password=yes", "SSH accepts the published demo password"),
    ("ssh=on vnc=on ssh_password=no", "SSH accepts only computers whose key is saved on this Pi (no password). VNC accepts the published demo password"),
    ("ssh=off vnc=off ssh_password=yes", "SSH and VNC do not accept it now"),
])
def test_remote_access_says_when_the_demo_password_works(menu_env, status, words):
    texts = _remote_menu(menu_env, status + " name=rasqberry mdns=rasqberry.local", "yes")
    assert words in texts
    assert "Change the password (now: the published demo password)" in texts


def test_remote_access_with_an_own_password_is_as_before(menu_env):
    texts = _remote_menu(menu_env, "ssh=on vnc=on ssh_password=yes name=rasqberry mdns=rasqberry.local", "no")
    assert "Anyone on the same network who knows the password can log in over SSH and VNC." in texts
    assert "demo password" not in texts


# ---------------------------------------------------------------------------
# F2: "Switch SSH off?" defaults to Cancel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("what", ["ssh", "vnc"])
def test_switch_off_defaults_to_cancel(menu_env, what):
    log = menu_env.tmp / "remote.log"
    code = f'_rq_remote() {{ echo "$*" >> "{log}"; }}; do_toggle_remote {what} on yes'
    proc = menu_env(code, extra_env={"WT_RC_yesno": "1"})
    assert proc.returncode == 0, proc.stderr
    call = next(c for c in menu_env.whiptail_calls() if "--yesno" in c)
    assert "--defaultno" in call and "Switch off" in call
    assert not log.exists()                                  # Cancel: nothing switched


def test_switch_on_keeps_its_default(menu_env):
    code = '_rq_remote() { echo "SSH is on."; }; do_toggle_remote ssh off yes'
    menu_env(code)
    call = next(c for c in menu_env.whiptail_calls() if "--yesno" in c)
    assert "--defaultno" not in call
