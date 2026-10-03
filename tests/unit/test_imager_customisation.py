"""
Raspberry Pi Imager's OS customisation (feedback Q13): Imager writes
firstrun.sh to the FIRST FAT partition and appends a systemd.run entry to its
cmdline.txt. Raspberry Pi OS needs its initramfs (imager_fixup) to run it;
RasQberry images have none, and on the A/B image the first FAT partition is
CONFIG, which the Pi does not boot from. rq_imager_firstrun.sh handles both,
and rq_imager_userconf.sh keeps the user "rasqberry".
"""

import os
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


def _card(tmp_path, ab=False, proc_cmdline=""):
    fw, cfg, boot = tmp_path / "fw", tmp_path / "config", tmp_path / "boot"
    for d in (fw, boot):
        d.mkdir()
    if ab:
        cfg.mkdir()
        (fw / "cmdline.txt").write_text(AB_CMDLINE + "\n")
        (cfg / "firstrun.sh").write_text(IMAGER_SCRIPT)
        # CONFIG has no cmdline.txt: Imager writes one with only its entries
        (cfg / "cmdline.txt").write_text(" cfg80211.ieee80211_regdom=DE" + RUN)
    else:
        (fw / "cmdline.txt").write_text(STD_CMDLINE.replace(" init=/usr/lib/raspberrypi-sys-mods/firstboot", "")
                                        + " cfg80211.ieee80211_regdom=DE" + RUN)
        (fw / "firstrun.sh").write_text(IMAGER_SCRIPT)
    (tmp_path / "proc_cmdline").write_text(proc_cmdline)
    return fw, cfg, boot


def _boot(tmp_path):
    env = dict(os.environ, RQ_FW_DIR=str(tmp_path / "fw"), RQ_AB_CONFIG_DIR=str(tmp_path / "config"),
               RQ_BOOT_DIR=str(tmp_path / "boot"), RQ_PROC_CMDLINE=str(tmp_path / "proc_cmdline"),
               RQ_IMAGER_LOG=str(tmp_path / "imager.log"),
               RQ_IMAGER_REBOOT=f"touch {tmp_path / 'rebooted'}")
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


@needs_gnu_sed
def test_ab_image_moves_firstrun_from_config_and_restarts(tmp_path):
    fw, cfg, _ = _card(tmp_path, ab=True, proc_cmdline=AB_CMDLINE)
    proc = _boot(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "rebooted").exists()
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
    # the start after that runs it; nothing is moved or restarted again
    (tmp_path / "rebooted").unlink()
    (tmp_path / "proc_cmdline").write_text(cmdline)
    assert _boot(tmp_path).returncode == 0
    assert not (tmp_path / "rebooted").exists()


def test_nothing_happens_without_customisation(tmp_path):
    fw, _, boot = _card(tmp_path)
    (fw / "firstrun.sh").unlink()
    before = (fw / "cmdline.txt").read_text()
    assert _boot(tmp_path).returncode == 0
    assert (fw / "cmdline.txt").read_text() == before and not (boot / "firstrun.sh").exists()


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
