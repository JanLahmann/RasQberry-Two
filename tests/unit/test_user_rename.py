"""
Tests for RQB2-bin/rq_user_rename.sh (#319): the desktop user gets the name
typed in Raspberry Pi Imager, with a new home /home/<name>.

The system is a fake root in a temp directory (RQ_RENAME_ROOT); usermod and
groupmod are stand-ins that edit its account files the way the real ones do
(-l, -d -m, -n). The same script ran with the real usermod/groupmod as root in
a Debian trixie container (see .local/custom-user/REPORT.md).

Also: rq_carry_over.sh takes the other system's user name over on the first
start of an A/B update, and rq_carry_ssh_identity.sh puts authorized_keys
into the new system's own home.
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_RENAME = os.path.join(_BIN, "rq_user_rename.sh")
_CARRY = os.path.join(_BIN, "rq_carry_over.sh")
_SSH = os.path.join(_BIN, "rq_carry_ssh_identity.sh")
_SYS = os.path.join(_ROOT, "RQB2-system")


def _gnu():
    """The script uses GNU sed -E -i, grep -Z and stat -c, as on the Pi."""
    try:
        return all(subprocess.run([t, "--version"], capture_output=True).returncode == 0
                   for t in ("sed", "grep", "stat"))
    except OSError:
        return False


pytestmark = [
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash required"),
    pytest.mark.skipif(not _gnu(), reason="GNU sed/grep/stat required (Linux)"),
]

VENV = "home/rasqberry/RasQberry-Two/venv/RQB2"

# usermod/groupmod stand-ins for the fake root: the account files and the
# home folder change the way the real tools change them
_USERMOD = r'''#!/bin/bash
set -e
R="$RQ_RENAME_ROOT"
if [ "$1" = -l ]; then
    new="$2"; old="$3"
    for f in passwd shadow; do
        awk -F: -v OFS=: -v o="$old" -v n="$new" '$1 == o { $1 = n } { print }' "$R/etc/$f" > "$R/etc/$f.tmp"
        cat "$R/etc/$f.tmp" > "$R/etc/$f"; rm "$R/etc/$f.tmp"
    done
    for f in group gshadow; do
        awk -F: -v OFS=: -v o="$old" -v n="$new" '{ k = split($NF, m, ","); s = "";
            for (i = 1; i <= k; i++) s = s (i > 1 ? "," : "") (m[i] == o ? n : m[i]); $NF = s; print }' \
            "$R/etc/$f" > "$R/etc/$f.tmp"
        cat "$R/etc/$f.tmp" > "$R/etc/$f"; rm "$R/etc/$f.tmp"
    done
elif [ "$1" = -d ] && [ "$3" = -m ]; then
    home="$2"; name="$4"
    old=$(awk -F: -v n="$name" '$1 == n { print $6 }' "$R/etc/passwd")
    awk -F: -v OFS=: -v n="$name" -v h="$home" '$1 == n { $6 = h } { print }' "$R/etc/passwd" > "$R/etc/passwd.tmp"
    cat "$R/etc/passwd.tmp" > "$R/etc/passwd"; rm "$R/etc/passwd.tmp"
    [ -d "$R$old" ] && mv "$R$old" "$R$home"
else
    echo "usermod stand-in: $*" >&2; exit 2
fi
'''
_GROUPMOD = r'''#!/bin/bash
set -e
R="$RQ_RENAME_ROOT"
[ "$1" = -n ] || exit 2
for f in group gshadow; do
    awk -F: -v OFS=: -v o="$3" -v n="$2" '$1 == o { $1 = n } { print }' "$R/etc/$f" > "$R/etc/$f.tmp"
    cat "$R/etc/$f.tmp" > "$R/etc/$f"; rm "$R/etc/$f.tmp"
done
'''


def _write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(mode)


def _system(root, user="rasqberry", data=None):
    """A RasQberry system as the image ships it, with uid 1000 = USER."""
    h = f"/home/{user}"
    _write(root / "etc/passwd", f"root:x:0:0:root:/root:/bin/bash\n{user}:x:1000:1000::{h}:/bin/bash\n"
                                "lightdm:x:107:115::/var/lib/lightdm:/bin/false\n")
    _write(root / "etc/shadow", f"root:*:20000:0:99999:7:::\n{user}:$y$IMAGE$hash:20000:0:99999:7:::\n")
    _write(root / "etc/group", f"root:x:0:\nsudo:x:27:{user}\nvideo:x:44:{user},vnc\n{user}:x:1000:\n"
                               f"gpio:x:986:{user}\ndocker:x:984:{user}\n")
    _write(root / "etc/gshadow", f"root:*::\nsudo:*::{user}\nvideo:*::{user},vnc\n{user}:!::\n"
                                 f"gpio:!::{user}\ndocker:!::{user}\n")
    _write(root / "etc/subuid", f"{user}:100000:65536\n")
    _write(root / "etc/subgid", f"{user}:100000:65536\n")
    v = root / h.lstrip("/") / "RasQberry-Two/venv/RQB2"
    _write(v / "bin/jupyter", f"#!{h}/RasQberry-Two/venv/RQB2/bin/python3\nimport sys\n", 0o755)
    _write(v / "bin/activate", f'VIRTUAL_ENV="{h}/RasQberry-Two/venv/RQB2"\nexport VIRTUAL_ENV\n')
    _write(v / "pyvenv.cfg", f"home = /usr/bin\ncommand = /usr/bin/python3 -m venv {h}/RasQberry-Two/venv/RQB2\n")
    (v / "lib").mkdir(parents=True, exist_ok=True)
    (v / "lib/mod.pyc").write_bytes(b"\x00\x01" + f"{h}/x.py".encode() + b"\x00")
    os.symlink("/usr/bin/python3", v / "bin/python3")
    home = root / h.lstrip("/")
    _write(home / ".config/Thonny/configuration.ini",
           f"[run]\nbackend.python = {h}/RasQberry-Two/venv/RQB2/bin/python3\nnot_mine = {h}2/other\n")
    _write(home / ".local/share/pki/nssdb/pkcs11.txt", f"parameters=configdir='sql:{h}/.local/share/pki/nssdb'\n")
    _write(home / ".cache/pip/entry", f"{h}/cached\n")
    os.symlink(f"{h}/RasQberry-Two", home / "rq-link")
    if data is not None:
        for d in ("Shared", ".qiskit"):
            (data / "home" / user / d).mkdir(parents=True, exist_ok=True)
            os.symlink(f"{data}/home/{user}/{d}", home / d)
        (data / "rasqberry").mkdir(parents=True, exist_ok=True)
    _write(root / "etc/lightdm/lightdm.conf", f"[Seat:*]\n#autologin-user=\nautologin-user={user}\n")
    _write(root / "etc/systemd/system/getty@tty1.service.d/autologin.conf",
           f"[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin {user} --noclear %I $TERM\n")
    _write(root / "etc/sudoers.d/010_rasqberry-nopasswd", f"{user} ALL=(ALL) NOPASSWD: ALL\n")
    _write(root / "etc/sudoers.d/README", "# rasqberry is not a rule here\n")
    for unit in ("rasqberry-led-renderer.service", "rasqberry-ip-display.service"):
        _write(root / "etc/systemd/system" / unit,
               f"[Service]\nExecStart={h}/RasQberry-Two/venv/RQB2/bin/python3 /usr/bin/x.py\n")
    _write(root / "etc/hostname", "rasqberry\n")
    _write(root / f"var/lib/systemd/linger/{user}", "")
    _write(root / f"var/spool/cron/crontabs/{user}", "@reboot true\n")
    (root / f"var/lib/lightdm/data/{user}").mkdir(parents=True)
    (root / "var/lib/rasqberry").mkdir(parents=True, exist_ok=True)
    return root


def _env(root, data, **extra):
    stubs = root.parent / "stubs"
    stubs.mkdir(exist_ok=True)
    _write(stubs / "usermod", _USERMOD, 0o755)
    _write(stubs / "groupmod", _GROUPMOD, 0o755)
    env = dict(os.environ, RQ_RENAME_ROOT=str(root), RQ_RENAME_DATA=str(data),
               RQ_USERMOD=str(stubs / "usermod"), RQ_GROUPMOD=str(stubs / "groupmod"))
    env.update(extra)
    return env


def _rename(root, data, *args, **extra):
    return subprocess.run(["bash", _RENAME, *args], env=_env(root, data, **extra),
                          capture_output=True, text=True, timeout=60)


def _snapshot(*dirs):
    """Every path below DIRS: file contents, link targets, modes."""
    out = {}
    for base in dirs:
        for dirpath, dirnames, filenames in os.walk(base):
            for name in dirnames + filenames:
                p = os.path.join(dirpath, name)
                if os.path.islink(p):
                    out[p] = ("link", os.readlink(p))
                elif os.path.isfile(p):
                    with open(p, "rb") as fh:
                        out[p] = ("file", fh.read(), os.stat(p).st_mode)
                else:
                    out[p] = ("dir", os.stat(p).st_mode)
    return out


@pytest.fixture
def card(tmp_path):
    data = tmp_path / "data"
    root = _system(tmp_path / "root", data=data)
    return root, data


def _passwd(root, name):
    for line in (root / "etc/passwd").read_text().splitlines():
        if line.split(":")[0] == name:
            return line
    return None


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def test_apply_renames_the_user_and_everything_that_names_it(card):
    root, data = card
    proc = _rename(root, data, "apply", "jan", "--why", "test")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    # the account and its home
    assert _passwd(root, "jan") == "jan:x:1000:1000::/home/jan:/bin/bash" and not _passwd(root, "rasqberry")
    assert "jan:x:1000:" in (root / "etc/group").read_text()
    assert "sudo:x:27:jan" in (root / "etc/group").read_text() and "video:x:44:jan,vnc" in (root / "etc/group").read_text()
    assert (root / "etc/shadow").read_text().splitlines()[1].startswith("jan:$y$IMAGE$hash:")
    assert (root / "etc/subuid").read_text() == "jan:100000:65536\n"
    assert not (root / "home/rasqberry").exists() and (root / "home/jan").is_dir()
    # the venv: shebangs, activate, pyvenv.cfg; binary files untouched
    v = root / "home/jan/RasQberry-Two/venv/RQB2"
    assert (v / "bin/jupyter").read_text().startswith("#!/home/jan/RasQberry-Two/venv/RQB2/bin/python3\n")
    assert os.access(v / "bin/jupyter", os.X_OK)
    assert '"/home/jan/RasQberry-Two/venv/RQB2"' in (v / "bin/activate").read_text()
    assert "venv /home/jan/RasQberry-Two/venv/RQB2" in (v / "pyvenv.cfg").read_text()
    assert b"/home/rasqberry/x.py" in (v / "lib/mod.pyc").read_bytes()
    assert os.readlink(v / "bin/python3") == "/usr/bin/python3"
    # configs in the home; another path that only starts like it stays
    thonny = (root / "home/jan/.config/Thonny/configuration.ini").read_text()
    assert "backend.python = /home/jan/RasQberry-Two/venv/RQB2/bin/python3" in thonny
    assert "not_mine = /home/rasqberry2/other" in thonny
    assert "sql:/home/jan/.local" in (root / "home/jan/.local/share/pki/nssdb/pkcs11.txt").read_text()
    # caches are not rewritten (they are rebuilt)
    assert (root / "home/jan/.cache/pip/entry").read_text() == "/home/rasqberry/cached\n"
    # symlinks into the home and to /data
    assert os.readlink(root / "home/jan/rq-link") == "/home/jan/RasQberry-Two"
    assert os.readlink(root / "home/jan/Shared") == f"{data}/home/jan/Shared"
    assert (data / "home/jan/.qiskit").is_dir() and not (data / "home/rasqberry").exists()
    assert (data / "rasqberry/desktop-user").read_text() == "jan\n"
    # units, autologin, sudo, linger, cron, lightdm
    for unit in ("rasqberry-led-renderer.service", "rasqberry-ip-display.service"):
        assert "ExecStart=/home/jan/RasQberry-Two/venv/RQB2/bin/python3" in \
            (root / "etc/systemd/system" / unit).read_text()
    assert "autologin-user=jan\n" in (root / "etc/lightdm/lightdm.conf").read_text()
    assert "--autologin jan --noclear" in \
        (root / "etc/systemd/system/getty@tty1.service.d/autologin.conf").read_text()
    assert (root / "etc/sudoers.d/010_rasqberry-nopasswd").read_text() == "jan ALL=(ALL) NOPASSWD: ALL\n"
    assert (root / "etc/sudoers.d/README").read_text() == "# rasqberry is not a rule here\n"
    assert (root / "var/lib/systemd/linger/jan").exists() and not (root / "var/lib/systemd/linger/rasqberry").exists()
    assert (root / "var/spool/cron/crontabs/jan").exists()
    assert (root / "var/lib/lightdm/data/jan").is_dir()
    # the hostname is not the user
    assert (root / "etc/hostname").read_text() == "rasqberry\n"
    # recorded; no journal, no backups left
    state = root / "var/lib/rasqberry"
    assert "from=rasqberry\nto=jan\n" in (state / "user-renamed").read_text()
    assert not (state / "user-rename.journal").exists() and not (state / "user-rename-backup").exists()
    assert not (state / "user-rename-failed").exists()
    assert "The desktop user is now 'jan'" in (root / "var/log/rasqberry-user-rename.log").read_text()


def test_dry_run_prints_the_changes_and_changes_nothing(card):
    root, data = card
    before = _snapshot(root, data)
    for args in (("plan", "jan"), ("apply", "jan", "--dry-run")):
        proc = _rename(root, data, *args)
        assert proc.returncode == 0, proc.stderr
        out = proc.stdout
        assert "would rename the user rasqberry -> jan (usermod -l)" in out
        assert "would move the home folder /home/rasqberry -> /home/jan" in out
        assert "would rewrite /home/rasqberry/RasQberry-Two/venv/RQB2/bin/jupyter" in out
        assert "would rewrite /etc/systemd/system/rasqberry-led-renderer.service" in out
        assert "would rewrite /etc/lightdm/lightdm.conf" in out
        assert f"would relink /home/rasqberry/Shared -> {data}/home/jan/Shared" in out
        assert "would move /var/lib/systemd/linger/rasqberry -> /var/lib/systemd/linger/jan" in out
        assert f"would move {data}/home/rasqberry -> {data}/home/jan" in out
        assert "dry run: nothing changed" in out
        assert "mod.pyc" not in out and ".cache" not in out
    assert _snapshot(root, data) == before


@pytest.mark.parametrize("step", ["account", "paths", "links", "names"])
def test_a_failed_step_undoes_everything(card, step):
    root, data = card
    before = _snapshot(root, data)
    proc = _rename(root, data, "apply", "jan", RQ_RENAME_FAIL_AT=step)
    assert proc.returncode == 1
    assert "NOT renamed to 'jan'" in proc.stdout and "Undoing" in proc.stdout
    after = _snapshot(root, data)
    # the same system as before, plus the note for the first login and the log
    failed = str(root / "var/lib/rasqberry/user-rename-failed")
    log = str(root / "var/log")
    extra = {p for p in after if p not in before}
    assert extra <= {failed, log, log + "/rasqberry-user-rename.log"}
    assert {p: v for p, v in after.items() if p not in extra} == before
    assert open(failed).read().startswith("jan\na step failed")


@pytest.mark.parametrize("name, why", [
    ("Jan", "not a valid Linux user name"), ("1abc", "not a valid"), ("jan doe", "not a valid"),
    ("a" * 33, "not a valid"), ("root", "system account"), ("docker", "system account"),
    ("video", "already exists"), ("gpio", "already exists"), ("lightdm", "system account"),
])
def test_names_that_cannot_be_used(card, name, why):
    root, data = card
    before = _snapshot(root, data)
    check = _rename(root, data, "check", name)
    assert check.returncode == 1 and why in check.stdout
    proc = _rename(root, data, "apply", name)
    assert proc.returncode == 1 and why in proc.stdout
    after = _snapshot(root, data)
    assert {p: v for p, v in after.items() if "user-rename" not in p and "/var/log" not in p} == before


def test_an_existing_home_folder_blocks_the_name(card):
    root, data = card
    (root / "home/jan").mkdir()
    proc = _rename(root, data, "apply", "jan")
    assert proc.returncode == 1 and "/home/jan already exists" in proc.stdout
    assert _passwd(root, "rasqberry")


def test_the_same_name_is_nothing_to_do(card):
    root, data = card
    before = _snapshot(root, data)
    assert _rename(root, data, "check", "rasqberry").returncode == 0
    proc = _rename(root, data, "apply", "rasqberry")
    assert proc.returncode == 0 and "nothing to do" in proc.stdout
    assert {p: v for p, v in _snapshot(root, data).items() if "/var/log" not in p} == before


def test_the_data_folder_of_the_other_system_wins(card):
    # A/B update: /data/home/jan is the other system's (and the one in use);
    # this system's /data/home/rasqberry is left alone, its links go to jan's
    root, data = card
    (data / "home/jan/Shared").mkdir(parents=True)
    (data / "home/jan/Shared/mine.txt").write_text("x")
    proc = _rename(root, data, "apply", "jan")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (data / "home/rasqberry/Shared").is_dir() and (data / "home/jan/Shared/mine.txt").exists()
    assert os.readlink(root / "home/jan/Shared") == f"{data}/home/jan/Shared"


def test_an_interrupted_rename_is_finished(card):
    # power cut after usermod -l: the journal tells the next run where it was
    root, data = card
    env = _env(root, data)
    subprocess.run([env["RQ_USERMOD"], "-l", "jan", "rasqberry"], env=env, check=True)
    (root / "var/lib/rasqberry/user-rename.journal").write_text(
        "from=rasqberry\nfrom_home=/home/rasqberry\nto=jan\n")
    proc = _rename(root, data, "apply", "jan")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Finishing an interrupted rename rasqberry -> jan" in proc.stdout
    assert _passwd(root, "jan") == "jan:x:1000:1000::/home/jan:/bin/bash"
    assert "autologin-user=jan" in (root / "etc/lightdm/lightdm.conf").read_text()
    assert (root / "home/jan/RasQberry-Two/venv/RQB2/bin/jupyter").read_text().startswith("#!/home/jan/")
    assert not (root / "var/lib/rasqberry/user-rename.journal").exists()


def test_a_second_rename_of_a_renamed_user(card):
    root, data = card
    assert _rename(root, data, "apply", "jan").returncode == 0
    proc = _rename(root, data, "apply", "maria")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _passwd(root, "maria") == "maria:x:1000:1000::/home/maria:/bin/bash"
    assert (root / "home/maria/RasQberry-Two/venv/RQB2/bin/jupyter").read_text().startswith("#!/home/maria/")
    assert "autologin-user=maria" in (root / "etc/lightdm/lightdm.conf").read_text()


# ---------------------------------------------------------------------------
# A/B update: the new system takes the name over (rq_carry_over.sh)
# ---------------------------------------------------------------------------

def _slot_extras(root, user, pw):
    """What the carry-over reads: shadow hash, hostname, state, Connect."""
    h = root / "home" / user
    lines = (root / "etc/shadow").read_text().splitlines()
    lines[1] = f"{user}:{pw}:20100:0:99999:7:::"
    (root / "etc/shadow").write_text("\n".join(lines) + "\n")
    (root / "boot/config").mkdir(parents=True, exist_ok=True)
    (root / "boot/config/autoboot.txt").write_text("[all]\n")
    _write(h / ".local/state/rasqberry/setup-checklist-shown", "answered\n")
    _write(h / ".config/com.raspberrypi.connect/auth.key", "token\n")
    _write(root / "usr/bin/rpi-connect", "#!/bin/sh\n", 0o755)


def _carry(new, old, data, **extra):
    env = _env(new, data, RQ_CARRY_ROOT=str(new), RQ_CARRY_DATA=str(data),
               RQ_CARRY_SKIP_MOUNT_CHECK="1", RQ_CARRY_NO_BIND="1", RQ_CARRY_NO_LIVE="1",
               RQ_CARRY_RENAME=_RENAME, **extra)
    return subprocess.run(["bash", _CARRY, "pull", str(old)], env=env, capture_output=True,
                          text=True, timeout=60)


@pytest.fixture
def update(tmp_path):
    data = tmp_path / "data"
    old = _system(tmp_path / "old", user="jan", data=data)
    _slot_extras(old, "jan", "$y$OWNER$secret")
    new = _system(tmp_path / "new")
    _slot_extras(new, "rasqberry", "$y$IMAGE$hash")
    (new / "home/rasqberry/.local/state/rasqberry/setup-checklist-shown").unlink()
    shutil.rmtree(new / "home/rasqberry/.config/com.raspberrypi.connect")
    return new, old, data


def test_an_update_takes_the_user_name_over(update):
    new, old, data = update
    proc = _carry(new, old, data)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "user name (jan)" in proc.stdout
    assert _passwd(new, "jan") == "jan:x:1000:1000::/home/jan:/bin/bash"
    # then the rest of the carry-over, for jan: password, state, Connect
    assert (new / "etc/shadow").read_text().splitlines()[1].startswith("jan:$y$OWNER$secret:")
    assert (new / "home/jan/.local/state/rasqberry/setup-checklist-shown").exists()
    assert (new / "home/jan/.config/com.raspberrypi.connect/auth.key").read_text() == "token\n"
    assert "autologin-user=jan" in (new / "etc/lightdm/lightdm.conf").read_text()
    assert "ExecStart=/home/jan/" in (new / "etc/systemd/system/rasqberry-led-renderer.service").read_text()
    # the other system's files on /data are untouched
    assert (data / "home/jan/Shared").is_dir()


def test_a_failed_rename_still_carries_the_rest_over(update):
    new, old, data = update
    proc = _carry(new, old, data, RQ_RENAME_FAIL_AT="names")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "could not rename the user 'rasqberry' to 'jan'" in proc.stderr
    assert _passwd(new, "rasqberry") and not _passwd(new, "jan")
    # read from the other system's user jan, written for rasqberry
    assert (new / "etc/shadow").read_text().splitlines()[1].startswith("rasqberry:$y$OWNER$secret:")
    assert (new / "home/rasqberry/.local/state/rasqberry/setup-checklist-shown").exists()
    assert (new / "home/rasqberry/.config/com.raspberrypi.connect/auth.key").exists()
    assert (new / "var/lib/rasqberry/user-rename-failed").read_text().startswith("jan\n")


def test_an_update_between_rasqberry_systems_renames_nothing(tmp_path):
    data = tmp_path / "data"
    old = _system(tmp_path / "old", data=data)
    _slot_extras(old, "rasqberry", "$y$OWNER$secret")
    new = _system(tmp_path / "new")
    _slot_extras(new, "rasqberry", "$y$IMAGE$hash")
    proc = _carry(new, old, data)
    assert proc.returncode == 0, proc.stderr
    assert "user name" not in proc.stdout and not (new / "var/log/rasqberry-user-rename.log").exists()
    assert (new / "etc/shadow").read_text().splitlines()[1].startswith("rasqberry:$y$OWNER$secret:")


def test_ssh_keys_go_to_the_new_systems_own_home(tmp_path):
    # the running system's user is jan; the new slot still has rasqberry
    src = tmp_path / "src"
    _write(src / "home/jan/.ssh/authorized_keys", "ssh-ed25519 AAAA jan@laptop\n")
    (src / "etc/ssh").mkdir(parents=True)
    tgt = _system(tmp_path / "tgt")
    (tgt / "etc/ssh").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, RQ_SSH_SOURCE_ROOT=str(src), RQ_SSH_USER_HOME="/home/jan")
    proc = subprocess.run(["bash", _SSH, str(tgt)], env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert (tgt / "home/rasqberry/.ssh/authorized_keys").read_text() == "ssh-ed25519 AAAA jan@laptop\n"
    assert not (tgt / "home/jan").exists()
