"""
Raspberry Pi Imager's OS customisation (feedback Q13): Imager writes
firstrun.sh to the FIRST FAT partition and appends a systemd.run entry to its
cmdline.txt. Raspberry Pi OS needs its initramfs (imager_fixup) to run it;
RasQberry images have none, and on the A/B image the first FAT partition is
CONFIG, which the Pi does not boot from. rq_imager_firstrun.sh handles both,
and rq_imager_userconf.sh keeps the user "rasqberry".

On A/B it is for the first start of a newly written card only: a leftover
CONFIG/firstrun.sh found by the first start of an updated slot restarted the
trial into the other slot and applied old settings (rig, 2026-10-03).
"""

import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_SYS = os.path.join(_ROOT, "RQB2-system")
_FIRSTRUN = os.path.join(_BIN, "rq_imager_firstrun.sh")
_USERCONF = os.path.join(_BIN, "rq_imager_userconf.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

GNU_SED = shutil.which("gsed")

# What Imager 2.x generates (customization_generator.cpp), shortened
IMAGER_SCRIPT = """#!/bin/sh
set +e
FIRSTUSER=$(getent passwd 1000 | cut -d: -f1)
/usr/lib/raspberrypi-sys-mods/imager_custom set_hostname kit-07
/usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh -k 'ssh-ed25519 AAAA test'
if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf 'pi' '$5$hash'
else
   echo "$FIRSTUSER:"'$5$hash' | chpasswd -e
fi
/usr/lib/raspberrypi-sys-mods/imager_custom set_wlan 'Net' 'secret' 'DE'
/usr/lib/raspberrypi-sys-mods/imager_custom set_keymap 'de'
rm -f /boot/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt
exit 0
"""
RUN = " systemd.run=/boot/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target"
STD_CMDLINE = "console=tty1 root=PARTUUID=7635115e-02 rootfstype=ext4 fsck.repair=yes rootwait quiet init=/usr/lib/raspberrypi-sys-mods/firstboot cfg80211.ieee80211_regdom=GB splash"
AB_CMDLINE = "console=serial0,115200 console=tty1 root=/dev/mmcblk0p5 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=GB quiet splash plymouth.ignore-serial-consoles panic=10"


AUTOBOOT = "[all]\ntryboot_a_b=1\nboot_partition=2\nboot_partition_fallback=3\n\n[tryboot]\nboot_partition=3\nboot_partition_fallback=2\n"


def _card(tmp_path, ab=False, proc_cmdline="", history=None, tryboot=None):
    """
    A card as rq_imager_firstrun.sh sees it.

    history: CONFIG markers the A/B code leaves once the card has run
             ({name: content}); none on a newly written card
    tryboot: chosen/bootloader/tryboot (0/1), None = firmware does not say
    """
    fw, cfg, boot = tmp_path / "fw", tmp_path / "config", tmp_path / "boot"
    for d in (fw, boot):
        d.mkdir()
    if ab:
        cfg.mkdir()
        (cfg / "autoboot.txt").write_text(AUTOBOOT)
        for name, content in (history or {}).items():
            (cfg / name).write_text(content + "\n")
        (fw / "cmdline.txt").write_text(AB_CMDLINE + "\n")
        (cfg / "firstrun.sh").write_text(IMAGER_SCRIPT)
        # CONFIG has no cmdline.txt: Imager writes one with only its entries
        (cfg / "cmdline.txt").write_text(" cfg80211.ieee80211_regdom=DE" + RUN)
    else:
        (fw / "cmdline.txt").write_text(STD_CMDLINE.replace(" init=/usr/lib/raspberrypi-sys-mods/firstboot", "")
                                        + " cfg80211.ieee80211_regdom=DE" + RUN)
        (fw / "firstrun.sh").write_text(IMAGER_SCRIPT)
    (tmp_path / "proc_cmdline").write_text(proc_cmdline)
    dt = tmp_path / "dt"
    dt.mkdir()
    if tryboot is not None:
        (dt / "tryboot").write_bytes(tryboot.to_bytes(4, "big"))
    return fw, cfg, boot


def _boot(tmp_path, state=None):
    # The restart command records its argument: "" plain, "0 tryboot" trial
    reboot = tmp_path / "reboot"
    if not reboot.exists():
        reboot.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{tmp_path / "rebooted"}"\n')
        reboot.chmod(0o755)
    env = dict(os.environ, RQ_FW_DIR=str(tmp_path / "fw"), RQ_AB_CONFIG_DIR=str(tmp_path / "config"),
               RQ_BOOT_DIR=str(tmp_path / "boot"), RQ_PROC_CMDLINE=str(tmp_path / "proc_cmdline"),
               RQ_IMAGER_LOG=str(tmp_path / "imager.log"), RQ_DT_BOOTLOADER_DIR=str(tmp_path / "dt"),
               RQ_IMAGER_STATE=str(state or tmp_path / "state"), RQ_IMAGER_REBOOT=str(reboot))
    if GNU_SED:  # macOS: the script uses GNU sed (as on the Pi)
        d = tmp_path / "gnubin"
        d.mkdir(exist_ok=True)
        if not (d / "sed").exists():
            os.symlink(GNU_SED, d / "sed")
        env["PATH"] = f"{d}:{env['PATH']}"
    return subprocess.run(["bash", _FIRSTRUN, "boot"], env=env, capture_output=True, text=True, timeout=30)


needs_gnu_sed = pytest.mark.skipif(
    subprocess.run(["sed", "--version"], capture_output=True).returncode != 0 and GNU_SED is None,
    reason="GNU sed required (as on the Pi)")


@needs_gnu_sed
def test_standard_image_runs_firstrun_from_the_boot_partition(tmp_path):
    fw, _, boot = _card(tmp_path, proc_cmdline=STD_CMDLINE + RUN)
    proc = _boot(tmp_path)
    assert proc.returncode == 0, proc.stderr
    script = (fw / "firstrun.sh").read_text()
    # removes itself and its cmdline entries where they really are
    assert "rm -f /boot/firmware/firstrun.sh" in script
    assert "/boot/firmware/cmdline.txt" in script and " /boot/cmdline.txt" not in script
    # never renames the user
    assert "/usr/lib/userconf-pi/userconf" not in script and "/usr/bin/rq_imager_userconf.sh 'pi'" in script
    # this start runs /boot/firstrun.sh: a stand-in that runs the real one
    stand_in = (boot / "firstrun.sh").read_text()
    assert "exec /bin/bash /boot/firmware/firstrun.sh" in stand_in and os.access(boot / "firstrun.sh", os.X_OK)
    # later starts run it from the boot partition
    assert "systemd.run=/boot/firmware/firstrun.sh" in (fw / "cmdline.txt").read_text()
    # idempotent
    before = script
    assert _boot(tmp_path).returncode == 0
    assert (fw / "firstrun.sh").read_text() == before
    # firstrun.sh restarts the Pi itself; nothing set aside on this image
    assert not (tmp_path / "rebooted").exists() and not (tmp_path / "state" / "imager-ignored").exists()
    # the first start's usage count says the customisation was applied
    assert (tmp_path / "state" / "imager-customised").exists()


# A newly written A/B card: whatever the layout state (dual and single
# system cards start "pending"; no file on cards from images before B4)
@needs_gnu_sed
@pytest.mark.parametrize("layout", ["pending", "dual", "single", None])
def test_ab_image_moves_firstrun_from_config_and_restarts(tmp_path, layout):
    fw, cfg, _ = _card(tmp_path, ab=True, proc_cmdline=AB_CMDLINE, tryboot=0)
    if layout:
        (cfg / "ab-layout").write_text(layout + "\n")
    proc = _boot(tmp_path)
    assert proc.returncode == 0, proc.stderr
    # a plain restart: a new card is on no trial
    assert (tmp_path / "rebooted").read_text() == "\n"
    assert not (cfg / "firstrun.sh").exists() and not (cfg / "cmdline.txt").exists()
    cmdline = (fw / "cmdline.txt").read_text()
    assert cmdline.count("\n") == 1
    assert "root=/dev/mmcblk0p5" in cmdline and "panic=10" in cmdline
    assert "cfg80211.ieee80211_regdom=DE" in cmdline and "regdom=GB" not in cmdline
    # the one-time run comes last, so firstrun's " systemd.run.*" removal
    # leaves the slot's own entries alone
    assert cmdline.rstrip().endswith("systemd.run=/boot/firmware/firstrun.sh "
                                     "systemd.run_success_action=reboot systemd.unit=kernel-command-line.target")
    assert "rq_imager_userconf.sh" in (fw / "firstrun.sh").read_text()
    assert not (tmp_path / "state" / "imager-customised").exists()
    # the start after that runs it; nothing is moved or restarted again
    (tmp_path / "rebooted").unlink()
    (tmp_path / "proc_cmdline").write_text(cmdline)
    assert _boot(tmp_path).returncode == 0
    assert not (tmp_path / "rebooted").exists()
    assert (tmp_path / "state" / "imager-customised").exists()


def test_nothing_happens_without_customisation(tmp_path):
    fw, _, boot = _card(tmp_path)
    (fw / "firstrun.sh").unlink()
    before = (fw / "cmdline.txt").read_text()
    assert _boot(tmp_path).returncode == 0
    assert (fw / "cmdline.txt").read_text() == before and not (boot / "firstrun.sh").exists()
    assert not (tmp_path / "state" / "imager-customised").exists()


# An A/B card that has run before, as the A/B code leaves CONFIG
TRIAL_OF_B = {"target-slot": "B", "switch-retries": "0", "current-slot": "A"}   # update -> Slot B
CONFIRMED = {"slot-confirmed": "2026-09-10T10:00:00+02:00\nA", "current-slot": "A"}
ROLLED_BACK = {"current-slot": "B"}                                              # rollback to B


@needs_gnu_sed
@pytest.mark.parametrize("history,tryboot", [(TRIAL_OF_B, 1), (TRIAL_OF_B, None), (CONFIRMED, 0),
                                             (ROLLED_BACK, 0)],
                         ids=["updated-slot-trial", "trial-no-dt", "confirmed", "rolled-back"])
def test_a_card_that_has_run_ignores_a_stale_config_firstrun(tmp_path, history, tryboot):
    # rig 2026-10-03: the card was written with Imager customisation for an
    # image that never used it; the first start of an updated Slot B found it
    fw, cfg, boot = _card(tmp_path, ab=True, proc_cmdline=AB_CMDLINE.replace("p5", "p6"),
                          history=history, tryboot=tryboot)
    slot_cmdline = (fw / "cmdline.txt").read_text()
    proc = _boot(tmp_path)
    assert proc.returncode == 0, proc.stderr
    # no restart of any kind: the trial goes on
    assert not (tmp_path / "rebooted").exists()
    # not applied: the slot's own start stays as it is (the rig got regdom AE)
    assert (fw / "cmdline.txt").read_text() == slot_cmdline
    assert not (fw / "firstrun.sh").exists() and not (boot / "firstrun.sh").exists()
    # off CONFIG, kept root-only for reference (Wi-Fi key, password hash)
    assert not (cfg / "firstrun.sh").exists() and not (cfg / "cmdline.txt").exists()
    kept = list((tmp_path / "state" / "imager-ignored").iterdir())
    assert len(kept) == 1 and kept[0].name.startswith("firstrun.sh.config.")
    assert kept[0].read_text() == IMAGER_SCRIPT and (kept[0].stat().st_mode & 0o777) == 0o600
    assert "Not applied" in (tmp_path / "imager.log").read_text()
    # the A/B markers are not touched
    assert sorted(p.name for p in cfg.iterdir()) == sorted(["autoboot.txt", *history])
    # an updated slot does not count as customised
    assert not (tmp_path / "state" / "imager-customised").exists()
    # the next start finds nothing to do
    assert _boot(tmp_path).returncode == 0
    assert not (tmp_path / "rebooted").exists()


@needs_gnu_sed
def test_a_leftover_that_cannot_be_kept_is_removed(tmp_path):
    _, cfg, _ = _card(tmp_path, ab=True, proc_cmdline=AB_CMDLINE, history=CONFIRMED, tryboot=0)
    not_a_dir = tmp_path / "file"
    not_a_dir.write_text("")
    assert _boot(tmp_path, state=not_a_dir).returncode == 0
    assert not (cfg / "firstrun.sh").exists() and "-> removed" in (tmp_path / "imager.log").read_text()


# A firstrun.sh already armed in a slot's cmdline.txt (moved there by the
# first version of this script during the trial of an updated slot): this
# start would stop at kernel-command-line.target without it
@needs_gnu_sed
@pytest.mark.parametrize("history,tryboot,restart", [(TRIAL_OF_B, 1, "0 tryboot"),
                                                     (TRIAL_OF_B, None, "0 tryboot"),
                                                     (CONFIRMED, 0, "")],
                         ids=["trial", "trial-no-dt", "confirmed"])
def test_an_armed_leftover_restarts_into_the_same_slot(tmp_path, history, tryboot, restart):
    armed = AB_CMDLINE.replace("p5", "p6") + " cfg80211.ieee80211_regdom=AE" + RUN.replace("/boot/", "/boot/firmware/")
    fw, cfg, boot = _card(tmp_path, ab=True, proc_cmdline=armed, history=history, tryboot=tryboot)
    (cfg / "firstrun.sh").unlink()
    (cfg / "cmdline.txt").unlink()
    (fw / "firstrun.sh").write_text(IMAGER_SCRIPT)
    (fw / "cmdline.txt").write_text(armed + "\n")
    proc = _boot(tmp_path)
    assert proc.returncode == 0, proc.stderr
    # never a plain restart on a trial: "0 tryboot" starts this slot again
    assert (tmp_path / "rebooted").read_text() == restart + "\n"
    cmdline = (fw / "cmdline.txt").read_text()
    assert "systemd.run" not in cmdline and "root=/dev/mmcblk0p6" in cmdline and "panic=10" in cmdline
    assert not (fw / "firstrun.sh").exists() and not (boot / "firstrun.sh").exists()
    assert [p.name.startswith("firstrun.sh.boot.") for p in (tmp_path / "state" / "imager-ignored").iterdir()] == [True]


@needs_gnu_sed
def test_a_restart_never_ends_a_tryboot_trial(tmp_path):
    # the rule itself, on the one path that restarts for Imager: a start the
    # firmware made with the tryboot flag restarts with it
    _card(tmp_path, ab=True, proc_cmdline=AB_CMDLINE, tryboot=1)
    assert _boot(tmp_path).returncode == 0
    assert (tmp_path / "rebooted").read_text() == "0 tryboot\n"


def _userconf(tmp_path, *args, autologin=True):
    calls = tmp_path / "userconf.calls"
    real = tmp_path / "userconf"
    real.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\n')
    real.chmod(0o755)
    lightdm = tmp_path / "lightdm.conf"
    lightdm.write_text("[Seat:*]\n" + ("autologin-user=rasqberry\n" if autologin else "#autologin-user=\n"))
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    (stubs / "getent").write_text("#!/bin/sh\necho 'rasqberry:x:1000:1000::/home/rasqberry:/bin/bash'\n")
    (stubs / "getent").chmod(0o755)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_USERCONF=str(real),
               RQ_LIGHTDM_CONF=str(lightdm), RQ_USERCONF_STATE=str(tmp_path / "userconf-pi"),
               RQ_IMAGER_STATE=str(tmp_path / "state"), RQ_IMAGER_LOG=str(tmp_path / "imager.log"))
    proc = subprocess.run(["bash", _USERCONF, *args], env=env, capture_output=True, text=True, timeout=30)
    return proc, (calls.read_text() if calls.exists() else "")


def test_a_different_imager_user_name_keeps_rasqberry(tmp_path):
    proc, calls = _userconf(tmp_path, "pi", "$5$hash")
    assert proc.returncode == 0, proc.stderr
    assert calls.strip() == "rasqberry $5$hash"
    assert (tmp_path / "state" / "imager-user-requested").read_text().strip() == "pi"
    # the desktop keeps logging in by itself (cancel-rename reads this flag)
    assert (tmp_path / "userconf-pi" / "autologin").exists()


def test_the_rasqberry_name_is_just_a_password_change(tmp_path):
    proc, calls = _userconf(tmp_path, "rasqberry", "$5$hash", autologin=False)
    assert proc.returncode == 0, proc.stderr
    assert calls.strip() == "rasqberry $5$hash"
    assert not (tmp_path / "state").exists() and not (tmp_path / "userconf-pi" / "autologin").exists()


def test_unit_runs_early_and_is_enabled():
    unit = open(os.path.join(_SYS, "etc", "systemd", "system", "rasqberry-imager-firstrun.service")).read()
    assert "Before=sysinit.target kernel-command-line.service rasqberry-firstboot.service rasqberry-ab-layout.service" in unit
    assert "ConditionPathExists=|/boot/config/firstrun.sh" in unit
    assert "rasqberry-imager-firstrun.service" in open(os.path.join(_SYS, "enabled-units.txt")).read()


def test_first_boot_tasks_wait_for_the_customisation_start(tmp_path):
    # the root expansion restarts the Pi; not while firstrun.sh runs
    proc_cmdline = tmp_path / "cmdline"
    proc_cmdline.write_text(STD_CMDLINE + RUN)
    env = dict(os.environ, RQ_PROC_CMDLINE=str(proc_cmdline))
    proc = subprocess.run(["bash", os.path.join(_SYS, "usr", "local", "bin", "rasqberry-firstboot.sh")],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert "next start" in proc.stdout


# ---------------------------------------------------------------------------
# Raspberry Pi Connect: the token goes to rasqberry, not to the name typed in
# Imager. The samples are firstrun.sh files from Imager's own generator
# (customization_generator.cpp of 2.0.3, 2.0.11.1 and main, built against
# Qt 6.10 with settings: hostname, user "jan" or none (key only: "pi"),
# password hash, SSH key, Wi-Fi, keyboard, time zone, a Connect token).
# 1.8.5 (OptionsPopup.qml, transcribed) has no Connect part.
# ---------------------------------------------------------------------------

_SAMPLES = os.path.join(_HERE, "data", "imager-firstrun")
CONNECT_SAMPLES = ["imager-2.0.3-user.sh", "imager-2.0.3-keyonly.sh", "imager-2.0.11.1-user.sh",
                   "imager-2.0.11.1-keyonly.sh", "imager-main-user.sh", "imager-main-keyonly.sh"]
TOKEN = "rpuak_TESTTOKENaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
UID1000 = 'TARGET_USER=$(getent passwd 1000 | cut -d: -f1); [ -n "$TARGET_USER" ] || TARGET_USER=rasqberry'


def _gnu_env(tmp_path):
    env = dict(os.environ)
    if GNU_SED:
        d = tmp_path / "gnubin"
        d.mkdir(exist_ok=True)
        if not (d / "sed").exists():
            os.symlink(GNU_SED, d / "sed")
        env["PATH"] = f"{d}:{env['PATH']}"
    return env


def _patched(tmp_path, sample, times=1):
    f = tmp_path / sample
    shutil.copyfile(os.path.join(_SAMPLES, sample), f)
    for _ in range(times):
        proc = subprocess.run(["bash", _FIRSTRUN, "patch", str(f)], env=_gnu_env(tmp_path),
                              capture_output=True, text=True, timeout=30)
        assert proc.returncode == 0, proc.stderr
    return f.read_text()


def _connect_part(script):
    lines = script.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("TARGET_USER="))
    end = next(i for i, l in enumerate(lines) if "start rpi-connect.service" in l)
    return "\n".join(lines[start:end + 1]) + "\n"


def _run_connect(tmp_path, part):
    """Run a Connect part as the Pi would, with rasqberry as uid 1000.

    Returns (home, log): rasqberry's home and the commands that need root.
    """
    home = tmp_path / "home" / "rasqberry"
    home.mkdir(parents=True)
    stubs, log = tmp_path / "connect-stubs", tmp_path / "connect.log"
    stubs.mkdir()
    bodies = {
        # only rasqberry exists; "jan" or "pi" from Imager do not
        "getent": f'case "$2" in 1000|rasqberry) echo "rasqberry:x:1000:1000:,,,:{home}:/bin/bash" ;; *) exit 2 ;; esac\n',
        # install -o needs root: record it, make the directories under home
        "install": f'echo "install $*" >> "{log}"\n'
                   f'case " $* " in *" -d "*) for a in "$@"; do case "$a" in {tmp_path}/*) mkdir -p "$a" ;; esac; done ;; esac\n',
    }
    for name in ("chown", "loginctl", "systemctl", "sleep"):
        bodies[name] = f'echo "{name} $*" >> "{log}"\n'
    for name, body in bodies.items():
        (stubs / name).write_text("#!/bin/sh\n" + body)
        (stubs / name).chmod(0o755)
    script = tmp_path / "connect.sh"
    # the fallback home (/home/NAME) under tmp_path: /home is autofs on macOS
    script.write_text("#!/bin/sh\nset +e\n" + part.replace('="/home/', f'="{tmp_path}/home/'))
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
    subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, timeout=30)
    return home, log.read_text()


@needs_gnu_sed
@pytest.mark.parametrize("sample", CONNECT_SAMPLES)
def test_connect_goes_to_rasqberry(tmp_path, sample):
    original = open(os.path.join(_SAMPLES, sample)).read()
    typed = "jan" if "-user" in sample else "pi"
    assert f'TARGET_USER="{typed}"' in original and f'TARGET_HOME="/home/{typed}"' in original
    script = _patched(tmp_path, sample)
    part = _connect_part(script)
    assert part.splitlines()[0] == UID1000
    assert 'then TARGET_HOME="/home/$TARGET_USER"; fi' in part
    assert f'"{typed}"' not in part and f"/home/{typed}" not in part
    # the rest of the Connect part is Imager's, line for line
    orig_part = _connect_part(original).splitlines()
    new_part = part.splitlines()
    assert new_part[1] == orig_part[1] and new_part[3:] == orig_part[3:] and TOKEN in part
    # still a valid script (Imager 2.x: #!/bin/sh), and patching twice changes nothing
    assert subprocess.run(["sh", "-n", str(tmp_path / sample)]).returncode == 0
    again, run = tmp_path / "again", tmp_path / "run"
    again.mkdir()
    run.mkdir()
    assert _patched(again, sample, times=2) == script

    # run it: the token, the user units and linger are rasqberry's
    home, log = _run_connect(run, part)
    key = home / ".config" / "com.raspberrypi.connect" / "auth.key"
    assert key.read_text().strip() == TOKEN and (key.stat().st_mode & 0o777) == 0o600
    wants = home / ".config" / "systemd" / "user"
    assert os.path.islink(wants / "default.target.wants" / "rpi-connect.service")
    assert os.path.islink(wants / "paths.target.wants" / "rpi-connect-signin.path")
    assert os.path.islink(wants / "default.target.wants" / "rpi-connect-wayvnc.service")
    assert "install -o rasqberry -m 700 -d" in log and "chown rasqberry:rasqberry" in log
    assert "install -m 0644 /dev/null /var/lib/systemd/linger/rasqberry" in log
    assert "loginctl enable-linger rasqberry" in log
    assert "systemctl --quiet --user --machine rasqberry@.host start rpi-connect.service" in log
    assert not re.search(rf"(?<![\w.]){typed}(?![\w.])", log)


@pytest.mark.parametrize("sample", ["imager-2.0.11.1-user.sh"])
def test_unpatched_connect_misses_the_user(tmp_path, sample):
    # why the patch exists: Imager's own part puts the token under /home/jan,
    # for a user that is not there
    home, log = _run_connect(tmp_path, _connect_part(open(os.path.join(_SAMPLES, sample)).read()))
    assert not (home / ".config" / "com.raspberrypi.connect").exists()
    assert "install -o jan" in log and "linger/jan" in log and "--machine jan@.host" in log


@needs_gnu_sed
def test_imager_18_without_connect_is_patched_as_before(tmp_path):
    sample = "imager-1.8.5-user.sh"
    original = open(os.path.join(_SAMPLES, sample)).read()
    script = _patched(tmp_path, sample)
    assert "TARGET_USER" not in script
    assert "/usr/bin/rq_imager_userconf.sh 'jan'" in script and "rm -f /boot/firmware/firstrun.sh" in script
    # only the known substitutions and the mark
    expected = (original.replace("/boot/firstrun.sh", "/boot/firmware/firstrun.sh")
                .replace("/boot/cmdline.txt", "/boot/firmware/cmdline.txt")
                .replace("/usr/lib/userconf-pi/userconf", "/usr/bin/rq_imager_userconf.sh")
                .replace("#!/bin/bash\n", "#!/bin/bash\n# RasQberry: patched by rq_imager_firstrun.sh\n", 1))
    assert script == expected
    assert subprocess.run(["bash", "-n", str(tmp_path / sample)]).returncode == 0


@needs_gnu_sed
@pytest.mark.parametrize("sample", CONNECT_SAMPLES)
def test_connect_patch_changes_nothing_else(tmp_path, sample):
    original = open(os.path.join(_SAMPLES, sample)).read().splitlines()
    script = _patched(tmp_path, sample).splitlines()
    assert script[1] == "# RasQberry: patched by rq_imager_firstrun.sh"
    del script[1]
    changed = [(a, b) for a, b in zip(original, script) if a != b]
    assert len(original) == len(script)
    for a, b in changed:
        assert (a.startswith("TARGET_USER=") or "TARGET_HOME=\"/home/" in a or "/boot/" in a
                or "/usr/lib/userconf-pi/userconf" in a), (a, b)


# ---------------------------------------------------------------------------
# The note at the first login: another name was typed in Imager
# ---------------------------------------------------------------------------

NOTE = ("You chose the name jan in Imager. RasQberry always uses the name rasqberry; your password, "
        "SSH key, hostname and Wi-Fi from Imager are set.")

_WT = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
case " $* " in *" --msgbox "*) exit "${WT_RC_msgbox:-0}" ;; esac
exit 1
'''


def _firstlogin(tmp_path, mode="--now", requested="jan", **extra):
    stubs = tmp_path / "fl-stubs"
    stubs.mkdir(exist_ok=True)
    for name, body in (("whiptail", _WT[len("#!/bin/sh\n"):]), ("ps", "echo pts/0\n"),
                       ("sudo", "exit 1\n"), ("systemctl", "exit 1\n")):
        (stubs / name).write_text("#!/bin/sh\n" + body)
        (stubs / name).chmod(0o755)
    state = tmp_path / "var-lib-rasqberry"
    state.mkdir(exist_ok=True)
    if requested is not None:
        (state / "imager-user-requested").write_text(requested + "\n")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home),
               XDG_STATE_HOME=str(home / ".state"), RQ_IMAGER_STATE=str(state),
               RQ_ENV_FILE=str(tmp_path / "no-env"), RQ_KEYBOARD_FILE=str(tmp_path / "no-keyboard"),
               WT_LOG=str(tmp_path / "wt.log"), USER="rasqberry")
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "SSH_CONNECTION"):
        env.pop(k, None)
    env.update(extra)
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_firstlogin.sh"), mode], env=env,
                          capture_output=True, text=True, timeout=60)
    wt = tmp_path / "wt.log"
    dialogs = wt.read_text().split("@@\n")[:-1] if wt.exists() else []
    if wt.exists():
        wt.unlink()
    return proc, dialogs


@pytest.mark.parametrize("mode", ["--now", "login"])
def test_note_about_the_imager_user_name_once(tmp_path, mode):
    proc, dialogs = _firstlogin(tmp_path, mode="" if mode == "login" else mode)
    assert proc.returncode == 0, proc.stderr
    # first the note, then the checklist
    assert "--msgbox" in dialogs[0] and NOTE in dialogs[0]
    assert any("--checklist" in d for d in dialogs[1:])
    assert (tmp_path / "home" / ".state" / "rasqberry" / "imager-user-note-shown").exists()
    # once
    proc, dialogs = _firstlogin(tmp_path, mode="--now")
    assert not any(NOTE in d for d in dialogs)


@pytest.mark.parametrize("requested", [None, "rasqberry", ""])
def test_no_note_without_another_name(tmp_path, requested):
    proc, dialogs = _firstlogin(tmp_path, requested=requested)
    assert proc.returncode == 0, proc.stderr
    assert not any("Your user name" in d for d in dialogs)


def test_note_comes_again_when_the_window_was_closed(tmp_path):
    # a killed whiptail (window closed, session ended) is not "read"
    _firstlogin(tmp_path, WT_RC_msgbox="143")
    assert not (tmp_path / "home" / ".state" / "rasqberry" / "imager-user-note-shown").exists()
    _, dialogs = _firstlogin(tmp_path)
    assert NOTE in dialogs[0]


def test_note_at_an_ssh_login_after_the_checklist(tmp_path):
    shown = tmp_path / "home" / ".state" / "rasqberry" / "setup-checklist-shown"
    shown.parent.mkdir(parents=True)
    shown.write_text("answered\n")
    proc, dialogs = _firstlogin(tmp_path, mode="")
    assert proc.returncode == 0, proc.stderr
    # only the note: the checklist was answered before
    assert len(dialogs) == 1 and NOTE in dialogs[0]
    _, dialogs = _firstlogin(tmp_path, mode="")
    assert dialogs == []


def test_desktop_opens_a_window_for_the_note(tmp_path):
    # also when no checklist step is pending (decided in the text: the steps
    # depend on the machine the tests run on)
    text = open(os.path.join(_BIN, "rq_firstlogin.sh")).read()
    desktop = text[text.index('if [ "$MODE" = "desktop" ]; then'):text.index("# Collect what is pending")]
    assert 'if [ -z "$(pending_tasks)" ] && ! imager_note_pending; then' in desktop
    assert desktop.count("already_shown && ! imager_note_pending && exit 0") == 2
