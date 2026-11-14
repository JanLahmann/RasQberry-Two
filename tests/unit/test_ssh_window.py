"""
SSH on a card that still has the published demo password (rq_ssh_window.sh,
rq_ssh_first_login.sh; Jan 2026-11-14, option d): a window after each start
with a forced password change, VNC off until the password is changed, keys
never affected, Imager-customised cards untouched.
"""

import os
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_WINDOW = os.path.join(_ROOT, "RQB2-bin", "rq_ssh_window.sh")
_FIRST = os.path.join(_ROOT, "RQB2-bin", "rq_ssh_first_login.sh")


def _run(tmp_path, code, demo="yes", boot_env="", stubs=""):
    env_file = tmp_path / "rasqberry_boot.env"
    env_file.write_text(boot_env)
    (tmp_path / "sshd_config.d").mkdir(exist_ok=True)
    env = dict(os.environ, RQ_SSHD_DIR=str(tmp_path), RQ_SSH_DROPIN=str(tmp_path / "05-first-login.conf"),
               RQ_BOOT_ENV_FILES=f"{tmp_path / 'none.env'}:{env_file}", RQ_DEMO_PW_STATE=demo,
               RQ_SSH_USER="rasqberry", RQ_SSH_RELOAD="true", RQ_NO_LED="1", RQ_SSH_POLL="0",
               RQ_SSH_BANNER=str(tmp_path / "banner.txt"), RQ_VNC_MARKER=str(tmp_path / "vnc-marker"))
    return subprocess.run(["bash", "-c", f'{stubs} . "{_WINDOW}"; {code}'],
                          capture_output=True, text=True, env=env)


def _dropin(tmp_path):
    f = tmp_path / "05-first-login.conf"
    return f.read_text() if f.exists() else None


def test_closed_before_sshd_starts_while_the_demo_password_is_set(tmp_path):
    assert _run(tmp_path, "cmd_close").returncode == 0
    d = _dropin(tmp_path)
    assert "ExposeAuthInfo yes" in d
    # everything else only for the desktop user, inside its Match block
    match = d[d.index("Match User rasqberry"):]
    for line in ("ForceCommand /usr/bin/rq_ssh_first_login.sh", "DisableForwarding yes",
                 "PasswordAuthentication no", "KbdInteractiveAuthentication no", "Banner "):
        assert "\n    " + line in match, line
    assert "PasswordAuthentication" not in d[:d.index("Match User")]
    assert "within 15 minutes" in (tmp_path / "banner.txt").read_text()


def test_unknown_counts_as_the_demo_password(tmp_path):
    _run(tmp_path, "cmd_close", demo="unknown")
    assert "PasswordAuthentication no" in _dropin(tmp_path)


def test_nothing_on_a_card_with_its_own_password(tmp_path):
    (tmp_path / "05-first-login.conf").write_text("old")
    _run(tmp_path, "cmd_close", demo="no")
    assert _dropin(tmp_path) is None
    assert _run(tmp_path, "main vnc-allowed", demo="no").returncode == 0


def test_window_opens_with_a_network_then_closes(tmp_path):
    # sleep stubbed: record the window; has_network true
    stubs = 'sleep() { echo "slept $1" >> "$RQ_SLEPT"; }; ip() { echo "default via 1.2.3.4"; }; hostname() { echo 10.0.0.5; }; '
    slept = tmp_path / "slept"
    r = _run(tmp_path, f'RQ_SLEPT="{slept}"; cmd_window', stubs=stubs)
    assert r.returncode == 0, r.stderr
    assert "slept 900" in slept.read_text()                  # 15 minutes by default
    assert "PasswordAuthentication no" in _dropin(tmp_path)  # closed again after it


def test_window_minutes_from_rasqberry_boot_env(tmp_path):
    assert _run(tmp_path, "window_minutes", boot_env="DEFAULT_PW_WINDOW_MIN=5\n").stdout == "5"
    assert _run(tmp_path, "window_minutes", boot_env='DEFAULT_PW_WINDOW_MIN="0"\n').stdout == "0"
    assert _run(tmp_path, "window_minutes", boot_env="DEFAULT_PW_WINDOW_MIN=soon\n").stdout == "15"
    assert _run(tmp_path, "window_minutes", boot_env="# DEFAULT_PW_WINDOW_MIN=1\n").stdout == "15"
    assert _run(tmp_path, "window_minutes", boot_env="DEFAULT_PW_WINDOW_MIN=08\n").stdout == "8"


def test_no_window_with_0(tmp_path):
    stubs = 'sleep() { echo "slept" >&2; exit 9; }; '
    r = _run(tmp_path, "cmd_close; cmd_window", boot_env="DEFAULT_PW_WINDOW_MIN=0\n", stubs=stubs)
    assert r.returncode == 0 and "slept" not in r.stderr
    assert "PasswordAuthentication no" in _dropin(tmp_path)


def test_a_changed_password_ends_it(tmp_path):
    _run(tmp_path, "cmd_close")
    _run(tmp_path, "cmd_check", demo="no")
    assert _dropin(tmp_path) is None


def test_vnc_waits_for_the_password_unless_opted_in(tmp_path):
    assert _run(tmp_path, "main vnc-allowed").returncode != 0
    assert _run(tmp_path, "main vnc-allowed", boot_env="DEFAULT_PW_WINDOW_VNC=yes\n").returncode == 0
    vnc = open(os.path.join(_ROOT, "RQB2-system", "usr", "local", "bin", "rasqberry-enable-vnc.sh")).read()
    assert vnc.index('"$WINDOW" vnc-allowed') < vnc.index("do_vnc 0")


def test_units_close_before_sshd_and_watch_password_changes():
    sysd = os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system")
    svc = open(os.path.join(sysd, "rasqberry-ssh-window.service")).read()
    assert "Before=ssh.service" in svc and "ExecStartPre=/usr/bin/rq_ssh_window.sh close" in svc
    path = open(os.path.join(sysd, "rasqberry-ssh-window-check.path")).read()
    assert "PathChanged=/etc/shadow" in path
    units = open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt")).read()
    assert "\nrasqberry-ssh-window.service\n" in units and "\nrasqberry-ssh-window-check.path\n" in units


def _first(tmp_path, auth, cmd="echo ran-original"):
    f = tmp_path / "auth"
    f.write_text(auth)
    env = dict(os.environ, SSH_USER_AUTH=str(f), SSH_ORIGINAL_COMMAND=cmd, SHELL="/bin/bash")
    return subprocess.run(["bash", _FIRST], capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)


def test_a_key_login_goes_straight_through(tmp_path):
    r = _first(tmp_path, "publickey ssh-ed25519 AAAA...\n")
    assert r.returncode == 0 and r.stdout.strip() == "ran-original"


def test_a_password_login_without_a_terminal_must_set_a_password_first(tmp_path):
    r = _first(tmp_path, "password\n")
    assert r.returncode == 1 and "ran-original" not in r.stdout
    assert "ssh -t" in r.stderr


def test_nothing_when_password_login_is_off_anyway(tmp_path):
    # Imager's "public-key only", carried over by an update
    (tmp_path / "sshd_config.d").mkdir(exist_ok=True)
    (tmp_path / "sshd_config.d" / "00-rasqberry-carried.conf").write_text("PasswordAuthentication no\n")
    (tmp_path / "05-first-login.conf").write_text("old")
    assert _run(tmp_path, "cmd_close").returncode == 0
    assert _dropin(tmp_path) is None


def test_the_carry_over_ignores_the_window_drop_in(tmp_path):
    # an A/B update must not turn the closed window into "keys only for good"
    src = tmp_path / "src" / "etc" / "ssh"
    (src / "sshd_config.d").mkdir(parents=True)
    (src / "sshd_config").write_text("# defaults\n")
    r = _run(tmp_path, f'RQ_SSHD_DIR="{src}"; RQ_SSH_DROPIN="{src}/sshd_config.d/05-rasqberry-first-login.conf"; '
                       f'SSHD_DIR="{src}"; DROPIN="$RQ_SSH_DROPIN"; write_dropin closed; '
                       f'rq_sshd_first_value "{src}" passwordauthentication; echo "[end]"')
    assert r.stdout.strip() == "[end]", r.stdout


def test_a_rejected_config_keeps_the_window_closed():
    sh = open(_WINDOW).read()
    reload = sh[sh.index("reload_sshd() {"):]
    reload = reload[:reload.index("\n}\n")]
    assert "write_dropin closed" in reload and "remove_dropin" not in reload


def _enable_vnc(tmp_path, updated):
    # updated: an A/B update from a system that had VNC on
    """Run rasqberry-enable-vnc.sh with the published password still set."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    state = tmp_path / "vnc-state"
    stubs = {
        "sudo": '[ "$1" = -n ] && shift; exec "$@"',
        "logger": "exit 0",
        "raspi-config": f'case "$2" in get_vnc) cat {state} 2>/dev/null || echo 1;; do_vnc) echo 0 > {state};; esac',
        "window": "exit 1",  # vnc-allowed: no
    }
    for name, body in stubs.items():
        f = bin_dir / name
        f.write_text("#!/bin/bash\n" + body + "\n")
        f.chmod(0o755)
    was_on = tmp_path / "vnc-was-on"
    if updated:
        was_on.write_text("2026-11-14\n")
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", RQ_VNC_MARKER=str(tmp_path / "marker"),
               RQ_SSH_WINDOW=str(bin_dir / "window"), RQ_VNC_WAS_ON=str(was_on), RQ_VNC_WAIT="0")
    script = os.path.join(_ROOT, "RQB2-system", "usr", "local", "bin", "rasqberry-enable-vnc.sh")
    subprocess.run(["bash", script], env=env, check=True)
    assert not (updated and was_on.exists())  # used once
    return state.exists()


def test_vnc_stays_off_on_a_new_card_but_stays_on_after_an_update(tmp_path):
    for name, updated in (("new", False), ("updated", True)):
        (tmp_path / name).mkdir()
        assert _enable_vnc(tmp_path / name, updated) == updated
