"""
Tests for batch B7 (review 2026-10): remote access, security, device identity.

  * R-014 / Q17: VNC is switched on once, at the first desktop login, and
    stays off when the user switches it off - also across an A/B update.
  * R-013 / R-063: the menu's Remote Access & Security, rq_remote_access.sh,
    and the checklist's "Name this RasQberry".
  * R-005: the checklist's keyboard layout and time zone step.
  * R-016 / R-112: System Info (rq_info.sh) shows name, address and power; the
    NetworkManager hook scrolls a new address again.
  * R-090 / R-139: the login message, the update notice and rq_help fit 80
    columns.

Everything runs unprivileged with stub tools (raspi-config, sudo, systemctl,
ip, id) on PATH.
"""

import importlib
import json
import os
import shutil
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_SYS = os.path.join(_ROOT, "RQB2-system")
_VNC = os.path.join(_SYS, "usr", "local", "bin", "rasqberry-enable-vnc.sh")
_HOOK = os.path.join(_SYS, "etc", "NetworkManager", "dispatcher.d", "90-rasqberry-ip-display")
_MOTD = os.path.join(_SYS, "etc", "update-motd.d", "20-rasqberry")
_REMOTE = os.path.join(_BIN, "rq_remote_access.sh")

sys.path.insert(0, _HERE)
from test_carry_over import _run as _carry, _slot  # noqa: E402
from test_raspi_config_menu import menu_env  # noqa: E402,F401

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _exe(path, body):
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def stubs(tmp_path):
    """Stub tools on PATH; every call is logged to calls.log."""
    d = tmp_path / "stubs"
    d.mkdir()
    log = tmp_path / "calls.log"
    rec = f'echo "$(basename "$0") $*" >> "{log}"\n'
    # raspi-config: VNC state in a file, like get_vnc/do_vnc
    vnc = tmp_path / "vnc-state"
    _exe(d / "raspi-config", rec + f'''
case "$2" in
  get_vnc) cat "{vnc}" 2>/dev/null || echo 1 ;;
  do_vnc)  echo "$3" > "{vnc}" ;;
esac
exit 0
''')
    _exe(d / "sudo", '[ "$1" = -n ] && shift\nexec "$@"\n')
    _exe(d / "logger", "exit 0\n")
    _exe(d / "systemctl", rec + 'case "$1" in is-enabled) [ -e "$STUB_ENABLED" ] ;; *) exit 0 ;; esac\n')
    _exe(d / "id", 'if [ "$1" = -u ]; then echo 0; else exec /usr/bin/id "$@"; fi\n')
    _exe(d / "hostname", 'echo "${STUB_HOSTNAME:-rasqberry}"\n')

    class S:
        path = f"{d}:{os.environ['PATH']}"
        calls = log
        vnc_state = vnc

        @staticmethod
        def logged():
            return log.read_text() if log.exists() else ""
    return S


# ---------------------------------------------------------------------------
# R-014 / Q17: VNC on once
# ---------------------------------------------------------------------------

def _vnc(stubs, marker):
    env = dict(os.environ, PATH=stubs.path, RQ_VNC_MARKER=str(marker),
               RQ_VNC_WAIT="0", RQ_VNC_RETRY_WAIT="0")
    return subprocess.run(["bash", _VNC], env=env, capture_output=True, text=True, timeout=30)


def test_vnc_is_switched_on_once_and_then_left_alone(stubs, tmp_path):
    marker = tmp_path / "lib" / "vnc-auto-enabled"
    assert _vnc(stubs, marker).returncode == 0
    assert "do_vnc 0" in stubs.logged() and marker.exists()
    # The user switches VNC off; the next login must not switch it on again
    stubs.vnc_state.write_text("1\n")
    stubs.calls.unlink()
    assert _vnc(stubs, marker).returncode == 0
    assert stubs.logged() == "" and stubs.vnc_state.read_text().strip() == "1"


def test_vnc_already_on_only_writes_the_marker(stubs, tmp_path):
    stubs.vnc_state.write_text("0\n")
    marker = tmp_path / "vnc-auto-enabled"
    assert _vnc(stubs, marker).returncode == 0
    assert marker.exists() and "do_vnc" not in stubs.logged()


def test_autostart_no_longer_promises_vnc_at_every_login():
    readme = open(os.path.join(_ROOT, "stage-RQB2", "00-firstboot-setup", "README.md")).read()
    assert "even if disabled manually" not in readme and "vncserver-x11" not in readme
    assert "once" in open(os.path.join(_SYS, "etc", "xdg", "autostart",
                                       "rasqberry-enable-vnc.desktop")).read()


@pytest.mark.parametrize("old_vnc_enabled,old_marker,carried", [
    (False, True, True),     # switched off on the old system: stays off
    (True, True, False),     # on there: the new system switches it on once
    (False, False, False),   # a release that always switched it on
])
def test_ab_update_keeps_vnc_off(tmp_path, old_vnc_enabled, old_marker, carried):
    old = _slot(tmp_path / "old")
    new = _slot(tmp_path / "new")
    marker = "var/lib/rasqberry/vnc-auto-enabled"
    if old_marker:
        (old / marker).write_text("2026-10-01\n")
    if old_vnc_enabled:
        wants = old / "etc/systemd/system/graphical.target.wants"
        wants.mkdir(parents=True)
        os.symlink("/usr/lib/systemd/system/wayvnc.service", wants / "wayvnc.service")
    proc = _carry(new, tmp_path / "data", "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    assert (new / marker).exists() == carried
    assert ("VNC off" in proc.stdout) == carried


# ---------------------------------------------------------------------------
# rq_remote_access.sh
# ---------------------------------------------------------------------------

def _remote(stubs, *args, **env):
    e = dict(os.environ, PATH=stubs.path, RQ_VNC_MARKER=str(stubs.vnc_state) + ".marker")
    e.update(env)
    return subprocess.run(["bash", _REMOTE, *args], env=e, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("name,ok", [
    ("rasqberry-01", True), ("class7", True), ("a", True),
    ("Class-7", False), ("-x", False), ("x-", False), ("a_b", False), ("a.b", False),
    ("", False), ("a" * 64, False),
])
def test_names_follow_the_hostname_rules(stubs, name, ok):
    assert (_remote(stubs, "check-name", name).returncode == 0) == ok


def test_rename_goes_through_raspi_config_and_restarts_avahi(stubs):
    proc = _remote(stubs, "name", "rasqberry-07")
    assert proc.returncode == 0, proc.stderr
    log = stubs.logged()
    assert "raspi-config nonint do_hostname rasqberry-07" in log
    assert "systemctl try-restart avahi-daemon.service" in log
    assert "rasqberry-07" in proc.stdout


def test_bad_name_changes_nothing(stubs):
    assert _remote(stubs, "name", "Bad Name").returncode != 0
    assert "do_hostname" not in stubs.logged()


def test_vnc_off_marks_it_as_the_users_choice(stubs):
    proc = _remote(stubs, "vnc", "off")
    assert proc.returncode == 0, proc.stderr
    assert "raspi-config nonint do_vnc 1" in stubs.logged()
    assert os.path.exists(str(stubs.vnc_state) + ".marker")


def test_vnc_on_that_fails_says_so_and_leaves_the_retry(stubs):
    proc = _remote(stubs, "vnc", "on")       # the stub systemctl still says off
    assert proc.returncode != 0 and "VNC is still off." in proc.stdout
    assert not os.path.exists(str(stubs.vnc_state) + ".marker")


def test_status_reports_ssh_and_vnc(stubs, tmp_path):
    flag = tmp_path / "enabled"
    flag.write_text("")
    proc = _remote(stubs, "status", STUB_ENABLED=str(flag))
    assert "ssh=on vnc=on name=rasqberry" in proc.stdout
    assert "ssh=off vnc=off" in _remote(stubs, "status").stdout


# SSH key only (user test 2026-10-04, #31): Imager's "public-key only" turns
# password login off, and Remote Access must not promise a password then
_SSHD_CONFIG = ("Include /etc/ssh/sshd_config.d/*.conf\n#PasswordAuthentication yes\n"
                "KbdInteractiveAuthentication no\nUsePAM yes\n")


def _ssh_password(stubs, tmp_path, effective=None, dropin=None, main=_SSHD_CONFIG):
    d = tmp_path / "ssh"
    (d / "sshd_config.d").mkdir(parents=True, exist_ok=True)
    (d / "sshd_config").write_text(main)
    if dropin is not None:
        (d / "sshd_config.d" / "00-rasqberry-carried.conf").write_text(dropin)
    sshd = tmp_path / "sshd"
    # sshd -T as root prints the effective settings; as a user it fails
    _exe(sshd, f"printf '%s' '{effective}'\n" if effective else "exit 1\n")
    out = _remote(stubs, "status", RQ_SSHD=str(sshd), RQ_SSHD_DIR=str(d)).stdout
    return dict(f.split("=", 1) for f in out.split())["ssh_password"]


@pytest.mark.parametrize("effective,expected", [
    ("passwordauthentication no\nkbdinteractiveauthentication no\nusepam yes\n", "no"),
    ("passwordauthentication yes\nkbdinteractiveauthentication no\nusepam yes\n", "yes"),
    # keyboard-interactive with PAM asks for the password, too
    ("passwordauthentication no\nkbdinteractiveauthentication yes\nusepam yes\n", "yes"),
])
def test_ssh_password_from_the_effective_settings(stubs, tmp_path, effective, expected):
    assert _ssh_password(stubs, tmp_path, effective=effective) == expected


@pytest.mark.parametrize("dropin,main,expected", [
    (None, _SSHD_CONFIG, "yes"),                                    # the shipped default
    ("PasswordAuthentication no\n", _SSHD_CONFIG, "no"),            # carried over (A/B update)
    (None, _SSHD_CONFIG + "PasswordAuthentication no\n", "no"),     # Imager's sed
    ("PasswordAuthentication yes\n", _SSHD_CONFIG + "PasswordAuthentication no\n", "yes"),  # first wins
    (None, _SSHD_CONFIG + "Match User guest\n  PasswordAuthentication no\n", "yes"),       # conditional
])
def test_ssh_password_from_the_files_without_root(stubs, tmp_path, dropin, main, expected):
    assert _ssh_password(stubs, tmp_path, dropin=dropin, main=main) == expected


# ---------------------------------------------------------------------------
# The menu: Remote Access & Security
# ---------------------------------------------------------------------------

def _texts(menu_env):
    return "\n".join("\n".join(c) for c in menu_env.whiptail_calls())


def test_main_menu_has_remote_access(menu_env):
    menu_env("do_rasqberry_menu", extra_env={"WT_RC_menu": "1"})
    assert "Remote Access & Security" in _texts(menu_env)


def test_remote_menu_shows_the_state_and_switches_vnc_off(menu_env):
    log = menu_env.tmp / "remote.log"
    code = (f'_rq_remote() {{ echo "$*" >> "{log}"; '
            '[ "$1" = status ] && echo "ssh=on vnc=on name=rasqberry mdns=rasqberry-3.local"; '
            '[ "$1" = vnc ] && echo "VNC is off."; return 0; }; '
            'do_toggle_remote vnc on; '
            'do_remote_access_menu')
    proc = menu_env(code, extra_env={"WT_RC_menu": "1"})
    assert proc.returncode == 0, proc.stderr
    texts = _texts(menu_env)
    assert "Switch VNC off?" in texts and "stays off" in texts
    assert "VNC (the desktop on another computer): on" in texts
    assert "rasqberry-3.local" in texts
    assert "vnc off" in log.read_text()


def test_remote_menu_says_key_only_when_ssh_takes_no_password(menu_env):
    code = ('_rq_remote() { [ "$1" = status ] && '
            'echo "ssh=on vnc=on name=rasqberry mdns=rasqberry.local ssh_password=no"; return 0; }; '
            'do_toggle_remote ssh off no; do_remote_access_menu')
    proc = menu_env(code, extra_env={"WT_RC_menu": "1", "WT_RC_yesno": "1"})
    assert proc.returncode == 0, proc.stderr
    texts = _texts(menu_env)
    assert "SSH (log in from another computer): on, key only" in texts
    assert "SSH accepts only computers whose key is saved on this Pi (no password)." in texts
    assert "who knows the password can log in over VNC" in texts
    assert "can log in over SSH and VNC" not in texts
    assert "Only computers whose key is saved on this Pi can then log in (no password)." in texts


def test_remote_menu_with_password_ssh_keeps_the_old_words(menu_env):
    code = ('_rq_remote() { [ "$1" = status ] && '
            'echo "ssh=on vnc=on name=rasqberry mdns=rasqberry.local ssh_password=yes"; return 0; }; '
            'do_remote_access_menu')
    menu_env(code, extra_env={"WT_RC_menu": "1"})
    texts = _texts(menu_env)
    assert "Anyone on the same network who knows the password can log in over SSH and VNC." in texts
    assert "key only" not in texts


# "Change the password" (user test #19): password boxes with Cancel instead
# of a raw passwd prompt that Esc and Ctrl+C could not leave
_WT_PASSWORD = r'''#!/bin/sh
kind=other
for a in "$@"; do
  case "$a" in --passwordbox) kind=passwordbox ;; --msgbox) kind=msgbox ;; esac
done
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
if [ "$kind" = passwordbox ]; then
  reply=$(head -n 1 "$PW_REPLIES")
  sed -i.bak 1d "$PW_REPLIES"
  case "$reply" in
    ""|"<cancel>") exit 1 ;;
    "<empty>") exit 0 ;;
  esac
  printf '%s' "$reply" >&2
fi
exit 0
'''

SECRET = "s3cret pass:x"


def _change_password(menu_env, replies, sshpw="yes", chpasswd_rc=0):
    stubs = menu_env.tmp / "stubs"
    (stubs / "whiptail").write_text(_WT_PASSWORD)      # menu_env made it executable
    got = menu_env.tmp / "chpasswd.in"
    _exe(stubs / "chpasswd", f'echo "chpasswd $*" >> "{menu_env.tmp}/calls"\ncat > "{got}"\n'
                             f'[ {chpasswd_rc} -eq 0 ] || echo "chpasswd: (user rasqberry) pam_chauthtok() failed" >&2\n'
                             f'exit {chpasswd_rc}\n')
    _exe(stubs / "passwd", f'echo "passwd $*" >> "{menu_env.tmp}/calls"\n')
    answers = menu_env.tmp / "pw-replies"
    answers.write_text("".join(r + "\n" for r in replies))
    proc = menu_env(f"do_change_password {sshpw}",
                    extra_env={"PW_REPLIES": str(answers), "SUDO_USER": "rasqberry"})
    calls = (menu_env.tmp / "calls").read_text() if (menu_env.tmp / "calls").exists() else ""
    return proc, _texts(menu_env), calls, (got.read_text() if got.exists() else None)


def test_password_change_sets_it_through_chpasswd(menu_env):
    proc, texts, calls, got = _change_password(menu_env, [SECRET, SECRET])
    assert proc.returncode == 0, proc.stderr
    assert got == f"rasqberry:{SECRET}\n"
    assert calls == "chpasswd \n"               # no argument: the password came on stdin
    assert "--passwordbox" in texts and "Cancel keeps the current password." in texts
    assert "New password for rasqberry. It is used for SSH, VNC and the login screen." in texts
    assert "Password changed. Use the new one for SSH, VNC and the login screen." in texts
    assert SECRET not in texts and SECRET not in proc.stdout + proc.stderr


@pytest.mark.parametrize("replies", [["<cancel>"], [SECRET, "<cancel>"]])
def test_password_change_can_be_cancelled(menu_env, replies):
    proc, texts, calls, got = _change_password(menu_env, replies)
    assert proc.returncode == 0, proc.stderr
    assert calls == "" and got is None
    assert "Password changed" not in texts


def test_password_change_refuses_an_empty_password(menu_env):
    _, texts, calls, _ = _change_password(menu_env, ["<empty>", "<cancel>"])
    assert "The password cannot be empty." in texts
    assert calls == ""


def test_password_change_needs_the_same_password_twice(menu_env):
    _, texts, calls, got = _change_password(menu_env, [SECRET, "other", "<cancel>"])
    assert "The two passwords are not the same. Nothing was changed" in texts
    assert calls == "" and got is None
    # after a mismatch it asks again from the start
    _, texts, calls, got = _change_password(menu_env, [SECRET, "other", SECRET, SECRET])
    assert got == f"rasqberry:{SECRET}\n"


def test_password_change_with_key_only_ssh(menu_env):
    _, texts, _, _ = _change_password(menu_env, [SECRET, SECRET], sshpw="no")
    assert "Password changed. Use the new one for VNC and the login screen." in texts
    assert "for SSH" not in texts


def test_password_change_that_fails_says_so(menu_env):
    _, texts, _, _ = _change_password(menu_env, [SECRET, SECRET], chpasswd_rc=1)
    assert "The password was not changed." in texts and "pam_chauthtok" in texts
    assert "Password changed" not in texts and SECRET not in texts


def test_password_change_never_runs_passwd():
    menu = open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    body = menu.split("do_change_password() {", 1)[1].split("\n}\n", 1)[0]
    assert "passwd \"" not in body and "chpasswd" in body


def test_remote_menu_rename_validates_first(menu_env):
    log = menu_env.tmp / "remote.log"
    code = (f'_rq_remote() {{ echo "$*" >> "{log}"; [ "$1" != check-name ]; }}; '
            'do_name_this_rasqberry rasqberry')
    menu_env(code, extra_env={"WT_REPLY_inputbox": "Bad_Name"})
    assert "check-name bad_name" in log.read_text()
    assert "name bad_name" not in log.read_text().replace("check-name bad_name", "")
    assert "cannot be used" in _texts(menu_env)


# ---------------------------------------------------------------------------
# The checklist: keyboard and time zone first, then the name (R-005, R-063)
# ---------------------------------------------------------------------------

_WT_CHECKLIST = r'''#!/bin/sh
kind=other
for a in "$@"; do
  case "$a" in --menu) kind=menu ;; --checklist) kind=checklist ;; --yesno) kind=yesno ;;
    --inputbox) kind=inputbox ;; esac
done
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
eval "reply=\${WT_REPLY_$kind:-}"
eval "rc=\${WT_RC_$kind:-0}"
[ -n "$reply" ] && printf '%s' "$reply" >&2
exit "$rc"
'''


def _checklist(stubs, tmp_path, **extra):
    _exe(tmp_path / "stubs" / "whiptail", _WT_CHECKLIST[len("#!/bin/sh\n"):])
    _exe(tmp_path / "stubs" / "dpkg-reconfigure", f'echo "dpkg-reconfigure $*" >> "{stubs.calls}"\n')
    kb = tmp_path / "keyboard"
    kb.write_text('XKBMODEL="pc105"\nXKBLAYOUT="gb"\n')
    tz = tmp_path / "timezone"
    tz.write_text("Europe/London\n")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, PATH=stubs.path, HOME=str(home), XDG_STATE_HOME=str(home / ".state"),
               RQ_KEYBOARD_FILE=str(kb), RQ_TIMEZONE_FILE=str(tz),
               WT_LOG=str(tmp_path / "wt.log"), USER="rasqberry")
    env.update(extra)
    return subprocess.run(["bash", os.path.join(_BIN, "rq_firstlogin.sh"), "--all"],
                          env=env, capture_output=True, text=True, timeout=60)


def test_checklist_offers_keyboard_first_and_the_name(stubs, tmp_path):
    proc = _checklist(stubs, tmp_path, WT_RC_checklist="1")
    assert proc.returncode == 0, proc.stderr
    args = (tmp_path / "wt.log").read_text().split("@@")[0].splitlines()
    tags = [a for a in args if a in ("locale", "wifi", "password", "name", "led")]
    assert tags[0] == "locale" and "name" in tags
    locale = args.index("locale")
    assert args[locale + 1].startswith("Keyboard layout and time zone") and args[locale + 2] == "ON"
    assert args[args.index("name") + 2] == "OFF"


def test_keyboard_step_sets_the_layout_and_keeps_the_time_zone(stubs, tmp_path):
    proc = _checklist(stubs, tmp_path, WT_REPLY_checklist="locale", WT_REPLY_menu="de",
                      WT_RC_yesno="1")
    assert proc.returncode == 0, proc.stderr
    log = stubs.logged()
    assert "raspi-config nonint do_configure_keyboard de" in log
    assert "dpkg-reconfigure" not in log
    assert (tmp_path / "home" / ".state" / "rasqberry" / "keyboard-timezone-set").exists()


def test_name_step_keeps_the_name_on_cancel(stubs, tmp_path):
    proc = _checklist(stubs, tmp_path, WT_REPLY_checklist="name", WT_RC_inputbox="1")
    assert proc.returncode == 0, proc.stderr
    assert "do_hostname" not in stubs.logged()
    assert (tmp_path / "home" / ".state" / "rasqberry" / "name-kept").exists()


# ---------------------------------------------------------------------------
# System Info (R-016, R-112)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("throttled,text", [
    ("0x0", "Power:             OK"),
    ("0x50000", "under-voltage since start-up"),
    ("0x50005", "UNDER-VOLTAGE now"),
])
def test_system_info_decodes_the_power_state(stubs, tmp_path, throttled, text):
    _exe(tmp_path / "stubs" / "vcgencmd", f'echo "throttled={throttled}"\n')
    env = dict(os.environ, PATH=stubs.path, RQ_BUILD_JSON=str(tmp_path / "none.json"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_info.sh")], env=env,
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert text in proc.stdout
    assert proc.stdout.startswith("Name:              rasqberry")
    assert "Address:" in proc.stdout


# Heat (#21): the sticky "since start-up" bit alone is not "too hot now", and
# each heat line comes with one line of advice for this Pi.
@pytest.mark.parametrize("throttled,model,note,advice", [
    ("0x80000", "Raspberry Pi 5 Model B Rev 1.0", "was slowed down earlier because it got too hot",
     "Fit the Active Cooler and check that its fan runs."),
    ("0x80008", "Raspberry Pi 5 Model B Rev 1.0", "too hot now, slowed down",
     "Fit the Active Cooler and check that its fan runs."),
    ("0x60006", "Raspberry Pi 4 Model B Rev 1.5", "too hot now, slowed down",
     "Give it more air: a heatsink, or a case with vents."),
    ("0x50005", "Raspberry Pi 4 Model B Rev 1.5", None, None),   # under-voltage, not heat
    ("0x0", "Raspberry Pi 5 Model B Rev 1.0", None, None),
])
def test_system_info_temperature_now_or_earlier(stubs, tmp_path, throttled, model, note, advice):
    _exe(tmp_path / "stubs" / "vcgencmd", f'echo "throttled={throttled}"\n')
    (tmp_path / "model").write_text(model + "\0")
    (tmp_path / "temp").write_text("77000\n")
    env = dict(os.environ, PATH=stubs.path, RQ_BUILD_JSON=str(tmp_path / "none.json"),
               RQ_MODEL_FILE=str(tmp_path / "model"), RQ_THERMAL_FILE=str(tmp_path / "temp"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_info.sh")], env=env,
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("Temperature:"))
    if note is None:
        assert lines[i] == "Temperature:       77 °C"
        assert not lines[i + 1].startswith(" ")
    else:
        assert lines[i] == f"Temperature:       77 °C - {note}"
        assert lines[i + 1] == " " * 19 + advice


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
def test_system_info_json_has_the_runtime_fields(stubs, tmp_path):
    _exe(tmp_path / "stubs" / "vcgencmd", 'echo "throttled=0x50000"\n')
    env = dict(os.environ, PATH=stubs.path, RQ_BUILD_JSON=str(tmp_path / "none.json"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_info.sh"), "--json"], env=env,
                          capture_output=True, text=True, timeout=30)
    data = json.loads(proc.stdout)
    assert data["hostname"] == "rasqberry" and data["throttled"] == "0x50000"
    assert data["power"].startswith("under-voltage")


# ---------------------------------------------------------------------------
# The address scroll after a network change (R-016)
# ---------------------------------------------------------------------------

def _hook(stubs, tmp_path, shown, action="up", holders=""):
    _exe(tmp_path / "stubs" / "ip", 'echo "3: wlan0    inet 192.168.1.42/24 brd 192.168.1.255 scope global wlan0"\n'
         'echo "4: docker0    inet 172.17.0.1/16 scope global docker0"\n')
    leds = tmp_path / "clear_leds"
    _exe(leds, f'[ -n "{holders}" ] && echo "{holders}"\n')
    flag = tmp_path / "enabled"
    flag.write_text("")
    shown_file = tmp_path / "ip-shown"
    if shown is not None:
        shown_file.write_text(shown)
    env = dict(os.environ, PATH=stubs.path, RQ_IP_SHOWN=str(shown_file), RQ_CLEAR_LEDS=str(leds),
               STUB_ENABLED=str(flag))
    proc = subprocess.run(["bash", _HOOK, "wlan0", action], env=env, capture_output=True,
                          text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return "restart --no-block rasqberry-ip-display.service" in stubs.logged()


def test_new_address_is_scrolled_again(stubs, tmp_path):
    assert _hook(stubs, tmp_path, shown="")              # "NO IP" at boot, Wi-Fi later


@pytest.mark.parametrize("shown,action,holders", [
    (None, "up", ""),                                    # boot scroll not run yet
    ("192.168.1.42", "up", ""),                          # already shown
    ("", "down", ""),                                    # not a new address
    ("", "up", "123 Quantum Lights Out"),                # a demo has the panel
])
def test_address_scroll_is_not_repeated_needlessly(stubs, tmp_path, shown, action, holders):
    assert not _hook(stubs, tmp_path, shown, action, holders)


def test_ip_scroll_records_what_it_showed(tmp_path, monkeypatch):
    sys.path.insert(0, _BIN)
    try:
        mod = importlib.import_module("rq_display_ip")
    except Exception as exc:  # pragma: no cover - LED libraries missing
        pytest.skip(f"rq_display_ip not importable: {exc}")
    monkeypatch.setattr(mod, "SHOWN_FILE", str(tmp_path / "run" / "ip-shown"))
    mod.record_shown(["wlan0: 192.168.1.42", "eth0: 10.0.0.5"])
    assert (tmp_path / "run" / "ip-shown").read_text() == "10.0.0.5\n192.168.1.42"


# ---------------------------------------------------------------------------
# Login message, update notice, rq_help (R-090, R-139, R-091)
# ---------------------------------------------------------------------------

def test_login_message_points_to_the_menu_and_fits(stubs):
    proc = subprocess.run(["sh", _MOTD], env=dict(os.environ, PATH=stubs.path),
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "0 RasQberry" in proc.stdout and "rq_help" in proc.stdout
    assert max(len(line) for line in proc.stdout.splitlines()) <= 80


def test_ssh_login_shows_no_misleading_last_login(tmp_path):
    # User test #31: a fresh card said "Last login: <build time>" - the
    # console autologin of the first start, before the clock was set. The
    # build empties /var/log (pi-gen export-image), so a drop-in turns the
    # line off; it is installed with the other system files (#294).
    conf = os.path.join(_SYS, "etc", "ssh", "sshd_config.d", "10-rasqberry.conf")
    lines = [l.strip() for l in open(conf) if l.strip() and not l.startswith("#")]
    assert lines == ["PrintLastLog no"]
    # it says nothing about password login: rq_carry_ssh_identity.sh and
    # rq_remote_access.sh read the first PasswordAuthentication in the drop-ins
    assert "passwordauthentication" not in open(conf).read().lower()


def test_update_notice_fits_80_columns(tmp_path):
    from test_update_check import _run
    _run(tmp_path, "beta-2025-12-30-211449", "--refresh")
    notice = _run(tmp_path, "beta-2025-12-30-211449", "--notice").stdout
    assert "Software & Image Updates" in notice
    assert max(len(line) for line in notice.splitlines()) <= 80


def test_rq_help_lists_existing_commands_in_80_columns():
    env = dict(os.environ, RQ_MANIFEST_DIR=os.path.join(_ROOT, "RQB2-config", "demo-manifests"))
    out = subprocess.run(["bash", os.path.join(_BIN, "rq_help")], env=env,
                         capture_output=True, text=True, timeout=30).stdout
    assert max(len(line) for line in out.splitlines()) <= 80
    assert "quantum-lights-out" in out and "schema" not in out
    named = {w for line in out.splitlines() for w in line.split()
             if w.startswith("rq_") and w not in ("rq_help",)}
    assert named and all(os.path.exists(os.path.join(_BIN, w)) for w in named), named


def test_new_terminals_skip_pip_when_qiskit_is_there():
    text = open(os.path.join(_ROOT, "RQB2-config", "setup_qiskit_env.sh")).read()
    assert text.index("qiskit-*.dist-info") < text.index("pip show qiskit")
