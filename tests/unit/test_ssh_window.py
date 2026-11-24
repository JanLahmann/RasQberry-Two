"""
SSH on a card that still has the published demo password (rq_ssh_window.sh,
rq_ssh_first_login.sh; Jan 2026-11-14, option d): a window after each start
with a forced password change, VNC off until the password is changed, keys
never affected, Imager-customized cards left alone (only their VNC waits).
"""

import os
import subprocess

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_WINDOW = os.path.join(_ROOT, "RQB2-bin", "rq_ssh_window.sh")
_FIRST = os.path.join(_ROOT, "RQB2-bin", "rq_ssh_first_login.sh")


def _run(tmp_path, code, demo="yes", boot_env="", stubs="", locked="P"):
    env_file = tmp_path / "rasqberry_boot.env"
    env_file.write_text(boot_env)
    (tmp_path / "sshd_config.d").mkdir(exist_ok=True)
    env = dict(os.environ, RQ_SSHD_DIR=str(tmp_path), RQ_SSH_DROPIN=str(tmp_path / "05-first-login.conf"),
               RQ_BOOT_ENV_FILES=f"{tmp_path / 'none.env'}:{env_file}", RQ_DEMO_PW_STATE=demo,
               RQ_SSH_USER="rasqberry", RQ_SSH_RELOAD="true", RQ_NO_LED="1", RQ_SSH_POLL="0",
               RQ_SSH_BANNER=str(tmp_path / "banner.txt"), RQ_ACCOUNT_LOCKED=locked,
               RQ_ENABLE_VNC=str(tmp_path / "enable-vnc"), RQ_VNC_CALLS=str(tmp_path / "calls"))
    # never the real VNC switch (a dev Pi would turn VNC on): a fake
    # rasqberry-enable-vnc.sh that logs each run
    fake_vnc = tmp_path / "enable-vnc"
    fake_vnc.write_text('#!/bin/sh\necho run >> "$RQ_VNC_CALLS"\n')
    fake_vnc.chmod(0o755)
    # main checks for root: after sourcing (rq_common.sh defines it), not as root here
    code = code.replace("main ", "ensure_root() { :; }; main ")
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


def test_status_reports_the_window_state(tmp_path):
    # the drop-in indents PasswordAuthentication inside its Match block (#421)
    _run(tmp_path, "cmd_close")
    assert "dropin=closed" in _run(tmp_path, "cmd_status").stdout
    _run(tmp_path, "write_dropin open")
    assert "dropin=open" in _run(tmp_path, "cmd_status").stdout


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


def _calls(tmp_path):
    """Runs of the fake rasqberry-enable-vnc.sh."""
    f = tmp_path / "calls"
    return f.read_text().splitlines() if f.exists() else []


def test_a_changed_password_switches_vnc_on_without_a_drop_in(tmp_path):
    """Fresh-card test 2026-11-15: an Imager card with keys only kept the
    published password, so it has no drop-in; after passwd VNC stayed off."""
    assert _run(tmp_path, "main check", demo="no").returncode == 0
    assert _calls(tmp_path) == ["run"]


def test_vnc_not_from_the_boot_time_check_without_a_drop_in(tmp_path):
    """cmd_window runs cmd_check at every boot of a card with its own password:
    VNC stays the desktop login's job there."""
    _run(tmp_path, "cmd_check", demo="no")
    assert _calls(tmp_path) == []


def test_vnc_with_the_drop_in_removed_at_boot(tmp_path):
    """The password came in since "close" (carry-over, Imager): the drop-in goes
    and VNC comes on, as before."""
    _run(tmp_path, "cmd_close")
    _run(tmp_path, "cmd_check", demo="no")
    assert _dropin(tmp_path) is None and _calls(tmp_path) == ["run"]


def test_no_vnc_while_the_published_password_is_set(tmp_path):
    """The published or an unknown password: nothing."""
    _run(tmp_path, "main check", demo="yes")
    _run(tmp_path, "main check", demo="unknown")
    assert _calls(tmp_path) == []


def test_a_locked_account_keeps_vnc_waiting(tmp_path):
    """usermod -L makes the hash read as "not the published one", but an unlock
    brings it back: VNC, which stays on once on, waits for a real change."""
    assert _run(tmp_path, "main vnc-allowed", demo="no", locked="L").returncode != 0
    assert _run(tmp_path, "main vnc-allowed", demo="no", locked="P").returncode == 0


def _login_vnc(tmp_path, labwc=True, marker_meanwhile=False, was_on_before=True, session_ends=False):
    """Run rasqberry-enable-vnc.sh with stubs; returns (result, raspi-config calls, marker, was_on)."""
    stubs = tmp_path / "bin"
    stubs.mkdir()
    marker, log, was_on = tmp_path / "marker", tmp_path / "raspi.log", tmp_path / "vnc-was-on"
    if was_on_before:
        was_on.write_text("")
    for name, body in {
        "sudo": 'while [ "${1#-}" != "$1" ]; do shift; done\nexec "$@"\n',
        "raspi-config": f'echo "$*" >> "{log}"\n[ "$2" = get_vnc ] && {{ [ -e "{tmp_path}/on" ] && echo 0 || echo 1; }}\n'
                        f'[ "$2" = do_vnc ] && : > "{tmp_path}/on"\nexit 0\n',
        "sleep": (f': > "{marker}"\n' if marker_meanwhile
                  else f': > "{tmp_path}/ended"\n' if session_ends else "exit 0\n"),
        "pgrep": (f'[ -e "{tmp_path}/ended" ] && exit 1\n[ "$*" = labwc ] && exit 0\nexit 1\n'
                  if labwc else "exit 1\n"),
        "logger": "exit 0\n",
        "tee": 'cat > "$1"\n',
        "window": "exit 0\n",                            # vnc-allowed: yes
    }.items():
        (stubs / name).write_text("#!/bin/sh\n" + body)
        (stubs / name).chmod(0o755)
    vnc = os.path.join(_ROOT, "RQB2-system", "usr", "local", "bin", "rasqberry-enable-vnc.sh")
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_VNC_MARKER=str(marker),
               RQ_SSH_WINDOW=str(stubs / "window"), RQ_VNC_WAS_ON=str(was_on), RQ_VNC_WAIT="0")
    r = subprocess.run(["bash", vnc], capture_output=True, text=True, env=env)
    return r, (log.read_text() if log.exists() else ""), marker.exists(), was_on.exists()


def test_the_login_routine_stops_if_another_run_switched_vnc_on(tmp_path):
    """The login and a password change can both run it: the marker, written by
    the other run meanwhile, ends the loop before do_vnc."""
    r, calls, _, _ = _login_vnc(tmp_path, marker_meanwhile=True, was_on_before=False)
    assert r.returncode == 0, r.stderr
    assert "do_vnc" not in calls


def test_vnc_only_inside_the_desktop_session(tmp_path):
    """A/B update 2026-11-15: before labwc runs, raspi-config switches on the X11
    VNC server instead of wayvnc. Without labwc: nothing, no marker, and
    vnc-was-on stays for the login."""
    r, calls, marker, was_on = _login_vnc(tmp_path, labwc=False)
    assert r.returncode == 0, r.stderr
    assert "do_vnc" not in calls and not marker and was_on


def test_vnc_waits_if_the_session_ends_meanwhile(tmp_path):
    """labwc gone during the wait: no do_vnc (it would pick the X11 server)."""
    r, calls, marker, was_on = _login_vnc(tmp_path, labwc=True, session_ends=True)
    assert r.returncode == 0, r.stderr
    assert "do_vnc" not in calls and not marker and was_on


def test_vnc_on_in_the_desktop_session(tmp_path):
    """With labwc: VNC on, marker written, vnc-was-on gone."""
    r, calls, marker, was_on = _login_vnc(tmp_path, labwc=True)
    assert r.returncode == 0, r.stderr
    assert "nonint do_vnc 0" in calls and marker and not was_on


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
    # an updated slot: not before the carry-over has copied the VNC choice
    check = open(os.path.join(sysd, "rasqberry-ssh-window-check.service")).read()
    assert "After=rasqberry-carry-over.service" in check
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
        "pgrep": '[ "$*" = labwc ]',   # inside the desktop session (labwc runs)
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
