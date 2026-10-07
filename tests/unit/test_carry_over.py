"""
Tests for RQB2-bin/rq_carry_over.sh (B4, R-053): what survives an A/B update.

Slot roots and the data partition are temp directories; runs unprivileged
(no chown, no bind mount: RQ_CARRY_NO_BIND=1). The same commands ran as root
against the real beta-2026-09-30 slot roots on loop devices (see the B4 report).
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_carry_over.sh")
USER = "rasqberry"
HOME = "/home/rasqberry"
ENV = "/usr/config/rasqberry_environment.env"
NM = "/etc/NetworkManager/system-connections"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _slot(base, hostname="rasqberry", pw="$y$image$hash", tz="Europe/London",
          lang="en_GB.UTF-8", kb="gb", env_lines=("LED_LAYOUT=single",)):
    """A minimal slot root with the files the carry-over touches."""
    for d in ("etc/default", "etc/NetworkManager/system-connections", "usr/config",
              "boot/config", "var/lib/rasqberry", "usr/share/zoneinfo/Europe", "." + HOME):
        (base / d).mkdir(parents=True, exist_ok=True)
    (base / "etc/hostname").write_text(hostname + "\n")
    (base / "etc/hosts").write_text(f"127.0.0.1\tlocalhost\n127.0.1.1\t\t{hostname}\n")
    (base / "etc/shadow").write_text(
        f"root:*:19000:0:99999:7:::\n{USER}:{pw}:19500:0:99999:7:::\nsshd:!:19000::::::\n")
    os.chmod(base / "etc/shadow", 0o640)
    (base / "etc/timezone").write_text(tz + "\n")
    for zone in ("London", "Berlin"):
        (base / f"usr/share/zoneinfo/Europe/{zone}").write_text("TZif")
    os.symlink(f"/usr/share/zoneinfo/{tz}", base / "etc/localtime")
    (base / "etc/default/locale").write_text(f"LANG={lang}\n")
    (base / "etc/locale.gen").write_text(f"{lang} UTF-8\n")
    (base / "etc/default/keyboard").write_text(f'XKBMODEL="pc105"\nXKBLAYOUT="{kb}"\n')
    (base / ENV.lstrip("/")).write_text("\n".join(env_lines) + "\n")
    (base / "boot/config/autoboot.txt").write_text("[all]\nboot_partition=2\n")
    return base


def _run(target, data, *args, **extra):
    env = dict(os.environ, RQ_CARRY_ROOT=str(target), RQ_CARRY_DATA=str(data),
               RQ_CARRY_USER=USER, RQ_CARRY_HOME=HOME, RQ_CARRY_SKIP_MOUNT_CHECK="1",
               RQ_CARRY_NO_BIND="1", RQ_CARRY_NO_LIVE="1")
    env.update(extra)
    return subprocess.run(["bash", _SCRIPT, *args], capture_output=True, text=True, env=env)


@pytest.fixture
def slots(tmp_path):
    old = _slot(tmp_path / "old", hostname="classroom-7", pw="$y$j9T$OWNER$secret",
                tz="Europe/Berlin", lang="de_DE.UTF-8", kb="de",
                env_lines=("LED_LAYOUT=quad", "BROWSER_AUTOSTART=false", "RQ_FIRSTLOGIN_DONE=true"))
    new = _slot(tmp_path / "new", env_lines=("LED_LAYOUT=single", "BROWSER_AUTOSTART=true"))
    data = tmp_path / "data"
    data.mkdir()
    return old, new, data


def _shadow_field(root, user, field):
    for line in (root / "etc/shadow").read_text().splitlines():
        parts = line.split(":")
        if parts[0] == user:
            return parts[field]
    return None


# ---------------------------------------------------------------------------
# pull: a fresh slot takes over the old slot's identity
# ---------------------------------------------------------------------------

def test_pull_takes_over_identity(slots):
    old, new, data = slots
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    assert (new / "etc/hostname").read_text().strip() == "classroom-7"
    assert "classroom-7" in (new / "etc/hosts").read_text()
    assert (new / "etc/timezone").read_text().strip() == "Europe/Berlin"
    assert os.readlink(new / "etc/localtime") == "/usr/share/zoneinfo/Europe/Berlin"
    assert "LANG=de_DE.UTF-8" in (new / "etc/default/locale").read_text()
    assert 'XKBLAYOUT="de"' in (new / "etc/default/keyboard").read_text()
    for item in ("hostname (classroom-7)", "password", "time zone", "locale", "keyboard layout"):
        assert item in proc.stdout
    done = (new / "var/lib/rasqberry/carry-over.done").read_text()
    assert "carried=hostname (classroom-7), password" in done


def test_pull_carries_only_the_users_password_hash(slots):
    old, new, data = slots
    _run(new, data, "pull", str(old))
    assert _shadow_field(new, USER, 1) == "$y$j9T$OWNER$secret"
    assert _shadow_field(new, USER, 2) == "19500"
    # system accounts come from the new image
    assert _shadow_field(new, "root", 1) == "*"
    assert _shadow_field(new, "sshd", 1) == "!"
    assert oct((new / "etc/shadow").stat().st_mode & 0o777) == "0o640"


def test_pull_env_preferences_but_not_other_keys(slots):
    old, new, data = slots
    _run(new, data, "pull", str(old))
    env = (new / ENV.lstrip("/")).read_text().splitlines()
    assert "BROWSER_AUTOSTART=false" in env and "BROWSER_AUTOSTART=true" not in env
    assert "RQ_FIRSTLOGIN_DONE=true" in env
    assert "LED_LAYOUT=single" in env          # LED keys: rq_device_settings.sh's job


def test_pull_keeps_usage_counts_off(tmp_path):
    # A rig or development Pi (RQ_UMAMI=0) stays uncounted in the updated
    # slot: the carry-over runs before its health check counts the update
    old = _slot(tmp_path / "old", env_lines=("LED_LAYOUT=quad", "RQ_UMAMI=0"))
    new = _slot(tmp_path / "new")
    data = tmp_path / "data"
    data.mkdir()
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert "RQ_UMAMI=0" in (new / ENV.lstrip("/")).read_text().splitlines()


def test_pull_keeps_the_demo_loop_choice(tmp_path):
    # The demos picked for the Demo Loop and its timings survive an update;
    # a key the old slot lacks keeps the new image's value
    old = _slot(tmp_path / "old", env_lines=("DEMO_LOOP_DEMOS=ibm-logo,rasq-led",
                                             "DEMO_LOOP_PAUSE=5"))
    new = _slot(tmp_path / "new", env_lines=("DEMO_LOOP_DEMOS=all", "DEMO_LOOP_PAUSE=2",
                                             "DEMO_LOOP_RASQ_LED_TIME=60"))
    data = tmp_path / "data"
    data.mkdir()
    assert _run(new, data, "pull", str(old)).returncode == 0
    env = (new / ENV.lstrip("/")).read_text().splitlines()
    assert "DEMO_LOOP_DEMOS=ibm-logo,rasq-led" in env and "DEMO_LOOP_DEMOS=all" not in env
    assert "DEMO_LOOP_PAUSE=5" in env
    assert "DEMO_LOOP_RASQ_LED_TIME=60" in env


def test_pull_of_identical_slot_carries_nothing(tmp_path):
    a = _slot(tmp_path / "a")
    b = _slot(tmp_path / "b")
    proc = _run(b, tmp_path, "pull", str(a))
    assert proc.returncode == 0
    assert "nothing (already the same)" in proc.stdout


def test_pull_migrates_qiskit_and_wifi_from_a_slot_without_data(slots):
    old, new, data = slots
    (old / ("." + HOME) / ".qiskit").mkdir()
    (old / ("." + HOME) / ".qiskit/qiskit-ibm.json").write_text('{"token": "T"}')
    (old / NM.lstrip("/") / "School.nmconnection").write_text("[wifi]\nssid=School\n")
    proc = _run(new, data, "pull", str(old))
    assert "IBM Quantum account (~/.qiskit)" in proc.stdout
    assert "Wi-Fi/network profiles" in proc.stdout
    assert (data / f"home/{USER}/.qiskit/qiskit-ibm.json").read_text() == '{"token": "T"}'
    assert (data / "rasqberry/system-connections/School.nmconnection").exists()


def test_pull_does_not_overwrite_what_data_already_has(slots):
    old, new, data = slots
    (old / ("." + HOME) / ".qiskit").mkdir()
    (old / ("." + HOME) / ".qiskit/qiskit-ibm.json").write_text("old")
    (data / f"home/{USER}/.qiskit").mkdir(parents=True)
    (data / f"home/{USER}/.qiskit/qiskit-ibm.json").write_text("newer, on /data")
    _run(new, data, "pull", str(old))
    assert (data / f"home/{USER}/.qiskit/qiskit-ibm.json").read_text() == "newer, on /data"


# ---------------------------------------------------------------------------
# link: user data lives on /data
# ---------------------------------------------------------------------------

def test_link_puts_shared_and_qiskit_on_data(slots):
    _, new, data = slots
    proc = _run(new, data, "link")
    assert proc.returncode == 0, proc.stderr
    home = new / ("." + HOME)
    assert os.readlink(home / "Shared") == str(data / f"home/{USER}/Shared")
    assert os.readlink(home / ".qiskit") == str(data / f"home/{USER}/.qiskit")
    assert (data / f"home/{USER}/Shared").is_dir()
    assert oct((data / f"home/{USER}/.qiskit").stat().st_mode & 0o777) == "0o700"
    assert "bind" in proc.stdout and "system-connections" in proc.stdout


def test_link_moves_an_existing_qiskit_dir(slots):
    _, new, data = slots
    q = new / ("." + HOME) / ".qiskit"
    q.mkdir()
    (q / "qiskit-ibm.json").write_text("token")
    _run(new, data, "link")
    assert q.is_symlink()
    assert (data / f"home/{USER}/.qiskit/qiskit-ibm.json").read_text() == "token"


def test_link_leaves_a_users_own_shared_folder_alone(slots):
    _, new, data = slots
    own = new / ("." + HOME) / "Shared"
    own.mkdir()
    (own / "notes.txt").write_text("mine")
    proc = _run(new, data, "link")
    assert not own.is_symlink() and (own / "notes.txt").read_text() == "mine"
    assert "left alone" in proc.stdout


def test_link_is_idempotent(slots):
    _, new, data = slots
    _run(new, data, "link")
    proc = _run(new, data, "link")
    assert proc.returncode == 0
    assert "~/Shared ->" not in proc.stdout     # nothing new to link


def test_network_profiles_migrate_once(slots):
    _, new, data = slots
    nm = new / NM.lstrip("/")
    (nm / "Home.nmconnection").write_text("[wifi]\nssid=Home\n")
    _run(new, data, "link")
    on_data = data / "rasqberry/system-connections"
    assert (on_data / "Home.nmconnection").exists()
    assert oct((on_data / "Home.nmconnection").stat().st_mode & 0o777) == "0o600"
    assert oct(on_data.stat().st_mode & 0o777) == "0o700"
    # the user deletes it (on /data); the slot's old copy must not bring it back
    (on_data / "Home.nmconnection").unlink()
    _run(new, data, "link")
    assert not (on_data / "Home.nmconnection").exists()


def test_no_prepared_data_partition_no_links(slots):
    _, new, data = slots
    env = {"RQ_CARRY_SKIP_MOUNT_CHECK": "0"}     # temp dir is not a mount point
    proc = _run(new, data, "link", **env)
    assert proc.returncode == 0
    assert "user data stays on this system" in proc.stdout
    assert not (new / ("." + HOME) / "Shared").exists()


def test_standard_image_is_left_alone(slots):
    _, new, data = slots
    (new / "boot/config/autoboot.txt").unlink()
    proc = _run(new, data, "boot")
    assert proc.returncode == 0
    assert not (new / ("." + HOME) / "Shared").exists()


def test_list_names_what_is_kept_and_lost(tmp_path):
    out = _run(tmp_path, tmp_path, "list").stdout
    for item in ("Shared", "~/.qiskit", "~/My-Quantum-Programs", "Wi-Fi", "LED",
                 "password", "hostname", "SSH host keys", "installed demos",
                 "Raspberry Pi Connect"):
        assert item in out


# ---------------------------------------------------------------------------
# ~/My-Quantum-Programs on /data (Jan, Q33c)
# ---------------------------------------------------------------------------

STARTERS = {"01_bell_state.py": "# Bell\n", "README.md": "# My Quantum Programs\n"}


def _ship_programs(root, extra=None):
    """The image's starter files, and the copy rq_learner_setup.sh made at build."""
    shipped = root / "usr/config/my-quantum-programs"
    folder = root / ("." + HOME) / "My-Quantum-Programs"
    for d in (shipped, folder):
        d.mkdir(parents=True, exist_ok=True)
        for name, text in {**STARTERS, **(extra or {})}.items():
            (d / name).write_text(text)
    return folder


def test_link_moves_my_programs_to_data(slots):
    _, new, data = slots
    folder = _ship_programs(new)
    (folder / "mine.py").write_text("print('mine')\n")
    proc = _run(new, data, "link")
    assert proc.returncode == 0, proc.stderr
    on_data = data / f"home/{USER}/My-Quantum-Programs"
    assert os.readlink(folder) == str(on_data)
    assert sorted(os.listdir(on_data)) == ["01_bell_state.py", "README.md", "mine.py"]


def test_an_update_keeps_the_learners_programs(slots):
    # /data holds the learner's folder from the old slot; the new slot ships
    # the starter files again (and one new starter)
    _, new, data = slots
    on_data = data / f"home/{USER}/My-Quantum-Programs"
    on_data.mkdir(parents=True)
    (on_data / "01_bell_state.py").write_text("# Bell, my changes\n")   # edited starter
    (on_data / "mine.py").write_text("print('mine')\n")                  # own file
    # README.md: a starter the learner deleted
    folder = _ship_programs(new, extra={"05_new_starter.py": "# new\n"})
    (folder / "made-in-slot.py").write_text("x = 1\n")    # made before the link existed
    _run(new, data, "link")
    assert folder.is_symlink()
    assert (on_data / "01_bell_state.py").read_text() == "# Bell, my changes\n"
    assert (on_data / "mine.py").exists() and (on_data / "made-in-slot.py").exists()
    assert not (on_data / "README.md").exists(), "a deleted starter must not come back"
    assert not (on_data / "05_new_starter.py").exists()   # shipped, unchanged: stays in /usr/config


def _learner_setup_ran(root):
    stamp = root / ("." + HOME) / ".local/state/rasqberry/learner-setup/programs"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("2026-10-03T08:53:09+0100\n")


def test_no_my_programs_link_without_the_folder(slots):
    # a learner who deleted the folder does not get an empty one back
    _, new, data = slots
    _learner_setup_ran(new)
    _run(new, data, "link")
    assert not os.path.lexists(new / ("." + HOME) / "My-Quantum-Programs")


def test_first_start_links_my_programs_before_the_learner_setup(slots):
    # Item 27: on the first start the carry-over runs before the desktop
    # login where the learner setup creates the folder; it is linked now,
    # and the setup fills the folder on /data
    _, new, data = slots
    proc = _run(new, data, "link")
    assert proc.returncode == 0, proc.stderr
    link = new / ("." + HOME) / "My-Quantum-Programs"
    assert os.readlink(link) == str(data / f"home/{USER}/My-Quantum-Programs")
    assert (data / f"home/{USER}/My-Quantum-Programs").is_dir()


def test_pull_brings_my_programs_from_a_slot_without_data(slots):
    old, new, data = slots
    folder = _ship_programs(old)
    (folder / "mine.py").write_text("print('mine')\n")
    proc = _run(new, data, "pull", str(old))
    assert "own programs (~/My-Quantum-Programs)" in proc.stdout
    assert (data / f"home/{USER}/My-Quantum-Programs/mine.py").exists()


# ---------------------------------------------------------------------------
# The marks of what the user was already asked or told (user test 2026-10-07)
# ---------------------------------------------------------------------------

STATE = HOME + "/.local/state/rasqberry"
MARKS = ("setup-checklist-shown", "firstlogin-offered", "imager-user-note-shown",
         "abinfo-read", "demo-password-kept", "keyboard-timezone-set", "name-kept",
         "firmware-info-read", "slot-indicator.json")


def _state(root):
    return root / ("." + STATE)


def test_pull_carries_the_setup_checklist_marks(slots):
    # An update into the other slot reopened the first-start checklist: the
    # marks of the old slot come along
    old, new, data = slots
    st = _state(old)
    st.mkdir(parents=True)
    for name in MARKS:
        (st / name).write_text(f"{name} 2026-10-01\n")
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    for name in MARKS:
        assert (_state(new) / name).read_text() == f"{name} 2026-10-01\n"
    assert "setup checklist and notices already seen" in proc.stdout


def test_pull_user_state_keeps_per_slot_folders_and_logs(slots):
    # learner-setup/ records this slot's own Thonny/Geany settings (made at
    # build time); the indicator's log is no mark
    old, new, data = slots
    st = _state(old)
    (st / "learner-setup").mkdir(parents=True)
    (st / "learner-setup/programs").write_text("old\n")
    (st / "slot-indicator.log").write_text("old log\n")
    (st / "setup-checklist-shown").write_text("x\n")
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert (_state(new) / "setup-checklist-shown").exists()
    assert not (_state(new) / "learner-setup").exists()
    assert not (_state(new) / "slot-indicator.log").exists()


def test_pull_user_state_never_overwrites(slots):
    old, new, data = slots
    _state(old).mkdir(parents=True)
    (_state(old) / "slot-indicator.json").write_text('{"old": 1}\n')
    (_state(old) / "name-kept").write_text("old\n")
    _state(new).mkdir(parents=True)
    (_state(new) / "slot-indicator.json").write_text('{"new": 1}\n')
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert (_state(new) / "slot-indicator.json").read_text() == '{"new": 1}\n'
    assert (_state(new) / "name-kept").read_text() == "old\n"


def test_pull_without_user_state_carries_none(slots):
    old, new, data = slots
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    assert "setup checklist" not in proc.stdout
    assert not _state(new).exists()


def test_pull_user_state_also_without_a_data_partition(slots):
    # The marks go into the slot's own home, not onto /data: a card on the
    # placeholder DATA partition keeps them too
    old, new, data = slots
    _state(old).mkdir(parents=True)
    (_state(old) / "setup-checklist-shown").write_text("x\n")
    proc = _run(new, data, "pull", str(old), RQ_CARRY_SKIP_MOUNT_CHECK="0")
    assert proc.returncode == 0, proc.stderr
    assert (_state(new) / "setup-checklist-shown").exists()


def test_the_carried_marks_are_where_the_checklist_looks(slots):
    # The path the carry-over copies is the one rq_firstlogin.sh and the slot
    # indicator read: after the pull, the checklist counts as answered
    import sys
    sys.path.insert(0, os.path.join(_HERE, "..", "..", "RQB2-bin"))
    import rq_slot_indicator as si
    firstlogin = open(os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_firstlogin.sh")).read()
    assert 'STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/rasqberry"' in firstlogin
    assert 'SHOWN_FILE="$STATE_DIR/setup-checklist-shown"' in firstlogin
    assert "USER_STATE=.local/state/rasqberry\n" in open(_SCRIPT).read()
    old, new, data = slots
    _state(old).mkdir(parents=True)
    (_state(old) / "setup-checklist-shown").write_text("x\n")
    assert not si.checklist_answered(str(_state(new)))
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert si.checklist_answered(str(_state(new)))


# ---------------------------------------------------------------------------
# Raspberry Pi Connect (user test 2026-10-07, R4; Jan: carry it over)
# ---------------------------------------------------------------------------

CONNECT_CFG = HOME.lstrip("/") + "/.config/com.raspberrypi.connect"
UNITS = HOME.lstrip("/") + "/.config/systemd/user"
# How Imager 2.x enables Connect (tests/unit/data/imager-firstrun) and how the
# package's postinst / `rpi-connect on` does it
IMAGER_LINKS = {"default.target.wants/rpi-connect.service": "rpi-connect.service",
                "paths.target.wants/rpi-connect-signin.path": "rpi-connect-signin.path",
                "default.target.wants/rpi-connect-wayvnc.service": "rpi-connect-wayvnc.service"}
POSTINST_LINKS = {"default.target.wants/rpi-connect.service": "rpi-connect.service",
                  "rpi-connect.service.wants/rpi-connect-wayvnc.service": "rpi-connect-wayvnc.service",
                  "rpi-connect.service.wants/rpi-connect-signin.path": "rpi-connect-signin.path"}


def _connect_installed(root):
    (root / "usr/bin").mkdir(parents=True, exist_ok=True)
    (root / "usr/bin/rpi-connect").write_text("#!/bin/sh\n")
    (root / "usr/bin/rpi-connect").chmod(0o755)
    units = root / "usr/lib/systemd/user"
    units.mkdir(parents=True, exist_ok=True)
    for name in ("rpi-connect.service", "rpi-connect-wayvnc.service", "rpi-connect-signin.path",
                 "rpi-connect-signin.service"):
        (units / name).write_text("[Unit]\n")


def _connect_on(root, links=IMAGER_LINKS, signed_in=True, linger=True):
    _connect_installed(root)
    if signed_in:
        cfg = root / CONNECT_CFG
        cfg.mkdir(parents=True)
        cfg.chmod(0o700)
        (cfg / "state.json").write_text('{"signed_in": true}\n')
        (cfg / "state.json").chmod(0o600)
    for rel, unit in links.items():
        link = root / UNITS / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(f"/usr/lib/systemd/user/{unit}", link)
    if linger:
        (root / "var/lib/systemd/linger").mkdir(parents=True)
        (root / "var/lib/systemd/linger" / USER).write_text("")


@pytest.mark.parametrize("links", [IMAGER_LINKS, POSTINST_LINKS])
def test_pull_carries_connect_signed_in_and_on(slots, links):
    old, new, data = slots
    _connect_on(old, links)
    _connect_installed(new)
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    cfg = new / CONNECT_CFG
    assert (cfg / "state.json").read_text() == '{"signed_in": true}\n'
    assert oct(cfg.stat().st_mode & 0o777) == "0o700"              # permissions kept
    assert oct((cfg / "state.json").stat().st_mode & 0o777) == "0o600"
    for rel, unit in links.items():                                  # the same units, enabled
        assert os.readlink(new / UNITS / rel) == f"/usr/lib/systemd/user/{unit}"
    assert (new / "var/lib/systemd/linger" / USER).exists()
    assert "Raspberry Pi Connect (sign-in, switched on)" in proc.stdout
    done = (new / "var/lib/rasqberry/carry-over.done").read_text()
    assert "Raspberry Pi Connect" in done


def test_pull_connect_off_carries_only_the_sign_in(slots):
    # Signed in once, then switched off: it stays off on the new system
    old, new, data = slots
    _connect_on(old, links={}, linger=False)
    _connect_installed(new)
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    assert (new / CONNECT_CFG / "state.json").exists()
    assert not (new / UNITS).exists()
    assert not (new / "var/lib/systemd/linger").exists()
    assert "Raspberry Pi Connect (sign-in)" in proc.stdout


def test_pull_connect_only_where_the_new_system_has_it(slots):
    old, new, data = slots
    _connect_on(old)
    proc = _run(new, data, "pull", str(old))          # new: rpi-connect not installed
    assert proc.returncode == 0, proc.stderr
    assert not (new / CONNECT_CFG).exists() and not (new / UNITS).exists()
    assert not (new / "var/lib/systemd/linger").exists()
    assert "Raspberry Pi Connect" not in proc.stdout


def test_pull_connect_skips_units_the_new_system_lacks(slots):
    old, new, data = slots
    _connect_on(old, POSTINST_LINKS)
    _connect_installed(new)
    (new / "usr/lib/systemd/user/rpi-connect-wayvnc.service").unlink()
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert (new / UNITS / "default.target.wants/rpi-connect.service").is_symlink()
    assert not os.path.lexists(new / UNITS / "rpi-connect.service.wants/rpi-connect-wayvnc.service")


def test_pull_connect_never_overwrites(slots):
    old, new, data = slots
    _connect_on(old)
    _connect_installed(new)
    (new / CONNECT_CFG).mkdir(parents=True)
    (new / CONNECT_CFG / "state.json").write_text("new\n")
    assert _run(new, data, "pull", str(old)).returncode == 0
    assert (new / CONNECT_CFG / "state.json").read_text() == "new\n"


def test_pull_without_connect_says_nothing(slots):
    old, new, data = slots
    _connect_installed(old)
    _connect_installed(new)
    proc = _run(new, data, "pull", str(old))
    assert proc.returncode == 0, proc.stderr
    assert "Raspberry Pi Connect" not in proc.stdout
    assert not (new / HOME.lstrip("/") / ".config").exists()
