"""
Tests for the fix batch after the fresh-card user test 2026-10-07 (system part):

  * the bootloader firmware check (rq_firmware.py, rasqberry-firmware-check
    .service): parsing rpi-eeprom-update, when the update is offered, the
    System Info line, the one-time desktop notice and the checklist step;
  * /etc/profile.d/00-rq-locale.sh: a locale sent over SSH that the Pi does
    not have (macOS: LC_CTYPE=UTF-8) becomes C.UTF-8;
  * P2: the checklist's password text is right also when the demo password
    was typed in Imager;
  * P4: Raspberry Pi Connect in Remote Access & Security and System Info;
  * P7: System Info from the slot badge says "close this window".
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import time
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_SYS = os.path.join(_ROOT, "RQB2-system")
_FW = os.path.join(_BIN, "rq_firmware.py")
_LOCALE = os.path.join(_SYS, "etc", "profile.d", "00-rq-locale.sh")

sys.path.insert(0, _HERE)
from test_raspi_config_menu import menu_env  # noqa: E402,F401
from test_remote_access import (_checklist, _exe, _password_step, _texts,  # noqa: E402,F401
                                stubs)

_spec = importlib.util.spec_from_file_location("rq_firmware", _FW)
fw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fw)

_ind_spec = importlib.util.spec_from_file_location("rq_slot_indicator",
                                                   os.path.join(_BIN, "rq_slot_indicator.py"))
ind = importlib.util.module_from_spec(_ind_spec)
_ind_spec.loader.exec_module(ind)

# rpi-eeprom-update on the rig's Pi 4, 2026-10-07 (exit 1)
PI4_OUTPUT = """*** UPDATE AVAILABLE ***

Run "sudo rpi-eeprom-update -a" to install this update without a prompt.

BOOTLOADER: update available
   CURRENT: Thu  8 May 15:21:35 UTC 2025 (1746717695)
    LATEST: Wed 23 Sep 12:02:14 UTC 2026 (1790164934)
   RELEASE: default (/usr/lib/firmware/raspberrypi/bootloader-2711/default)
            Use raspi-config to change the release.

  VL805_FW: Using bootloader EEPROM
     VL805: up to date
   CURRENT: 000138c0
    LATEST: 000138c0
"""
OLD = 1746717695            # 8 May 2025
NEW = 1790164934            # 23 Sep 2026
NOW = 1791331200            # 7 Oct 2026
DAY = 86400


# ---------------------------------------------------------------------------
# The firmware check: pure parts
# ---------------------------------------------------------------------------

def test_parse_takes_the_bootloader_lines_not_vl805():
    got = fw.parse_eeprom_update(PI4_OUTPUT, 1)
    assert got == {"current_ts": OLD, "latest_ts": NEW, "update": "yes"}


@pytest.mark.parametrize("rc,current,latest,update", [
    (0, NEW, NEW, "no"),
    (2, OLD, NEW, "yes"),      # failed, but the numbers say it
    (2, None, None, "unknown"),
])
def test_parse_exit_codes(rc, current, latest, update):
    text = ""
    if current:
        text = f"BOOTLOADER: x\n   CURRENT: a ({current})\n    LATEST: b ({latest})\n"
    assert fw.parse_eeprom_update(text, rc)["update"] == update


@pytest.mark.parametrize("compatible,model", [
    ("raspberrypi,5-model-b\0brcm,bcm2712\0", "pi5"),
    ("raspberrypi,4-model-b\0brcm,bcm2711\0", "pi4"),
    ("raspberrypi,3-model-b\0brcm,bcm2837\0", "other"),
])
def test_model(compatible, model):
    assert fw.model_of(compatible) == model


@pytest.mark.parametrize("current,update,crypto,due", [
    (OLD, "yes", "na", True),                  # old and an update: offer it
    (NOW - 30 * DAY, "yes", "ok", False),      # recent: no nagging
    (NOW - 30 * DAY, "yes", "fail", True),     # Pi 5 without the crypto service
    (OLD, "no", "na", False),                  # nothing newer to install
    (OLD, "unknown", "na", False),
])
def test_when_the_update_is_offered(current, update, crypto, due):
    status = {"model": "pi4", "current_ts": str(current), "update": update, "crypto": crypto}
    assert fw.assess(status, NOW)["due"] is due


def test_texts():
    pi4 = {"model": "pi4", "current_ts": str(OLD), "update": "yes", "crypto": "na"}
    assert fw.info_line(pi4, NOW) == "8 May 2025 (update available)"
    assert fw.info_line(dict(pi4, update="no"), NOW) == "8 May 2025 (up to date)"
    assert fw.info_line({}, NOW) == "unknown"
    # Connect from Imager is the Pi 5's problem (its firmware is in the EEPROM)
    assert fw.notice_text(pi4, NOW) == ("The Pi's firmware is from 8 May 2025. "
                                        "A newer version fixes problems.")
    assert fw.notice_text(dict(pi4, model="pi5"), NOW) == (
        "The Pi's firmware is from 8 May 2025. A newer version fixes problems, "
        "e.g. Raspberry Pi Connect from Imager.")


@pytest.mark.parametrize("source,first", [
    ("/dev/mmcblk0p1", True), ("/dev/sda1", True), ("/dev/nvme0n1p1", True),
    ("/dev/mmcblk0p2", False), ("/dev/mmcblk0p11", False), ("/dev/sda11", False), ("", False),
])
def test_first_partition(source, first):
    assert fw.is_first_partition(source) is first


DEFAULTS = 'FIRMWARE_RELEASE_STATUS="default"\n'


def test_with_bootfs_appends_once_and_keeps_the_rest():
    new = fw.with_bootfs(DEFAULTS, "/boot/config")
    assert new.startswith(DEFAULTS) and new.endswith("BOOTFS=/boot/config\n")
    assert fw.with_bootfs(new, "/boot/config") is None                 # idempotent
    assert fw.with_bootfs('FIRMWARE_RELEASE_STATUS="latest"', "/x").startswith(
        'FIRMWARE_RELEASE_STATUS="latest"\n#')                         # no newline at the end
    assert fw.with_bootfs(DEFAULTS + "BOOTFS=/mnt/boot\n", "/boot/config") is None   # someone's own
    assert fw.with_bootfs("", "/boot/config").endswith("BOOTFS=/boot/config\n")


def _bootfs(tmp_path, ab, source, text=DEFAULTS):
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    if ab:
        (config / "autoboot.txt").write_text("[all]\ntryboot_a_b=1\nboot_partition=2\n")
    defaults = tmp_path / "rpi-eeprom-update"
    defaults.write_text(text)
    env = dict(os.environ, RQ_BOOT_CONFIG_DIR=str(config), RQ_EEPROM_DEFAULTS=str(defaults),
               RQ_BOOT_CONFIG_SOURCE=source)
    proc = subprocess.run([sys.executable, _FW, "ab-bootfs"], env=env, capture_output=True,
                          text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return defaults.read_text(), str(config)


def test_ab_card_gets_bootfs_for_the_official_tools(tmp_path):
    text, config = _bootfs(tmp_path, True, "/dev/mmcblk0p1")
    assert text.startswith(DEFAULTS) and text.endswith(f"BOOTFS={config}\n")
    again, _ = _bootfs(tmp_path, True, "/dev/mmcblk0p1", text)
    assert again == text                                                  # idempotent


@pytest.mark.parametrize("ab,source", [(False, "/dev/mmcblk0p1"),     # standard card
                                       (True, "/dev/mmcblk0p2")])       # not the first partition
def test_no_bootfs_elsewhere(tmp_path, ab, source):
    text, _ = _bootfs(tmp_path, ab, source)
    assert text == DEFAULTS


# ---------------------------------------------------------------------------
# The firmware check: the command line, with stub tools
# ---------------------------------------------------------------------------

def _fw_env(tmp_path, model="pi5", eeprom_rc=1, crypto_rc=1):
    d = tmp_path / "fwstubs"
    d.mkdir(exist_ok=True)
    out = tmp_path / "eeprom.out"
    out.write_text(PI4_OUTPUT)
    _exe(d / "rpi-eeprom-update", f'cat "{out}"\nexit {eeprom_rc}\n')
    _exe(d / "rpi-fw-crypto", f'echo "Number of OTP keys: 1"\nexit {crypto_rc}\n')
    compat = tmp_path / "compatible"
    compat.write_text({"pi5": "brcm,bcm2712\0", "pi4": "brcm,bcm2711\0"}[model])
    return dict(os.environ, PATH=f"{d}:{os.environ['PATH']}",
                RQ_FIRMWARE_STATUS=str(tmp_path / "run" / "firmware-status"),
                RQ_DT_COMPATIBLE=str(compat), RQ_DT_BOOTLOADER_DIR=str(tmp_path / "none"),
                RQ_EEPROM_UPDATE=str(d / "rpi-eeprom-update"), RQ_FW_CRYPTO=str(d / "rpi-fw-crypto"))


def _fw(env, *args):
    return subprocess.run([sys.executable, _FW, *args], env=env, capture_output=True,
                          text=True, timeout=30)


def test_check_writes_the_status_and_due_says_why(tmp_path):
    env = _fw_env(tmp_path, model="pi5", crypto_rc=1)
    assert _fw(env, "due").returncode == 1                  # nothing checked yet
    assert _fw(env, "check", "--write").returncode == 0
    status = fw.read_status(env["RQ_FIRMWARE_STATUS"])
    assert status["model"] == "pi5" and status["current_ts"] == str(OLD)
    assert status["update"] == "yes" and status["crypto"] == "fail"
    due = _fw(env, "due")
    assert due.returncode == 0 and "Raspberry Pi Connect from Imager" in due.stdout
    assert _fw(env, "line").stdout.strip() == "8 May 2025 (update available, crypto service missing)"


def test_pi4_skips_the_crypto_check(tmp_path):
    env = _fw_env(tmp_path, model="pi4", eeprom_rc=0)
    _fw(env, "check", "--write")
    status = fw.read_status(env["RQ_FIRMWARE_STATUS"])
    assert status["crypto"] == "na" and status["update"] == "no"
    assert _fw(env, "due").returncode == 1


def test_the_unit_is_enabled_and_never_updates():
    unit = open(os.path.join(_SYS, "etc/systemd/system/rasqberry-firmware-check.service")).read()
    starts = [line for line in unit.splitlines() if line.startswith("ExecStart=")]
    assert starts == ["ExecStart=-/usr/bin/rq_firmware.py ab-bootfs",
                      "ExecStart=/usr/bin/rq_firmware.py check --write"]
    assert "Before=rpi-eeprom-update.service" in unit and "After=local-fs.target" in unit
    assert "network-online" not in unit
    assert "rasqberry-firmware-check.service" in open(os.path.join(_SYS, "enabled-units.txt")).read()
    assert os.access(_FW, os.X_OK)


# ---------------------------------------------------------------------------
# The notice in the taskbar indicator
# ---------------------------------------------------------------------------

def test_notice_once_per_firmware_version(tmp_path):
    due = {"due": True, "key": str(OLD)}
    book = ind.NoticeBook(str(tmp_path))
    assert book.firmware_to_announce(due) is True
    assert book.firmware_to_announce(due) is False
    book.save()
    again = ind.NoticeBook(str(tmp_path))                   # a new login
    assert again.firmware_to_announce(due) is False
    assert again.firmware_to_announce({"due": True, "key": str(NEW)}) is True
    assert again.firmware_to_announce({"due": False, "key": "1"}) is False


def test_notice_waits_for_the_checklist(tmp_path):
    assert ind.checklist_answered(str(tmp_path)) is False
    (tmp_path / "setup-checklist-shown").write_text("x")
    assert ind.checklist_answered(str(tmp_path)) is True


def test_rasqberry_never_updates_the_firmware():
    """Jan, 2026-10-07: notify only, point to Raspberry Pi's own tools."""
    for name in ("rq_firmware.py", "rq_slot_indicator.py", "rq_firstlogin.sh", "rq_info.sh"):
        code = open(os.path.join(_BIN, name)).read()
        # the command is only text to show (UPDATE_CMD, System Info), never run
        code = code.replace('UPDATE_CMD = "sudo rpi-eeprom-update -a"', "")
        code = code.replace('echo "                     sudo rpi-eeprom-update -a"', "")
        assert "rpi-eeprom-update -a\"" not in code and "[EEPROM_UPDATE, \"-a\"]" not in code, name
        assert "Update now" not in code and "Update the firmware" not in code, name
        assert "spawn([fw.UPDATE_CMD" not in code and "spawn(fw.UPDATE_CMD" not in code, name
    assert not hasattr(ind, "FIRMWARE_CMD") and not hasattr(fw, "update")
    assert fw.UPDATE_CMD == "sudo rpi-eeprom-update -a"
    # the command on a line of its own (copyable), then restart
    assert "\n    sudo rpi-eeprom-update -a\n" in fw.HOWTO
    assert "then restart" in fw.HOWTO_INTRO and fw.HOWTO_INTRO in fw.HOWTO
    assert "Advanced Options, Bootloader Version" in fw.HOWTO
    assert fw.DOC_URL.endswith("raspberry-pi.html#update-the-bootloader-configuration")


class _Widget:
    """A stand-in for a Gtk widget: remembers what was set and connected."""

    made = []

    def __init__(self, kind, **kw):
        self.kind, self.kw, self.calls, self.handlers, self.children = kind, kw, {}, {}, []
        _Widget.made.append(self)

    def __getattr__(self, name):
        def call(*args):
            self.calls.setdefault(name, []).append(args)
            if name in ("add", "pack_start", "pack_end"):
                self.children.append(args[0])
        return call

    def connect(self, signal, handler):
        self.handlers[signal] = handler


class _FakeGtk:
    """Gtk for show_firmware: widgets are _Widgets, the clipboard a list."""
    WindowPosition = Orientation = ButtonBoxStyle = types.SimpleNamespace(
        CENTER=0, VERTICAL=0, HORIZONTAL=1, END=2)
    clipboard = []

    def __getattr__(self, name):
        return lambda **kw: _Widget(name, **kw)

    class Clipboard:
        @staticmethod
        def get(selection):
            class _Clip:
                def set_text(self, text, length):
                    _FakeGtk.clipboard.append(("set_text", text, length))

                def store(self):
                    _FakeGtk.clipboard.append(("store",))
            return _Clip()


@pytest.fixture
def fake_gtk(monkeypatch):
    gtk = _FakeGtk()
    repo = types.ModuleType("gi.repository")
    repo.Gtk = gtk
    repo.Gdk = types.SimpleNamespace(SELECTION_CLIPBOARD="CLIPBOARD")
    gi = types.ModuleType("gi")
    gi.require_version = lambda *a: None
    gi.repository = repo
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repo)
    _Widget.made = []
    _FakeGtk.clipboard = []
    return gtk


def _notice_window(monkeypatch, tmp_path):
    item = ind.SlotIndicator.__new__(ind.SlotIndicator)
    item.fw_window = None
    item.spawned = []
    item.spawn = item.spawned.append
    item.open_url = lambda url: item.spawned.append(["open", url])
    monkeypatch.setattr(fw, "read_status", lambda: {})
    item.show_firmware()
    return item


def _label_texts():
    out = []
    for w in _Widget.made:
        if w.kind == "Label":
            for name in ("set_text", "set_markup"):
                out += [a[0] for a in w.calls.get(name, [])]
    return out


def test_firmware_notice_command_is_copyable(fake_gtk, monkeypatch, tmp_path):
    """User test 2026-10-07: over VNC the command could not be copied."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    item = _notice_window(monkeypatch, tmp_path)
    labels = [w for w in _Widget.made if w.kind == "Label"]
    # every text can be selected; the command is a line of its own, monospace
    assert labels and all(w.calls.get("set_selectable") == [(True,)] for w in labels)
    texts = _label_texts()
    assert "<tt><b>sudo rpi-eeprom-update -a</b></tt>" in texts
    assert fw.HOWTO_INTRO in texts and fw.HOWTO_OR in texts
    assert texts[0].startswith("The Pi's firmware is from")
    buttons = {w.kw.get("label"): w for w in _Widget.made if w.kind == "Button"}
    assert set(buttons) == {"Copy command", "How to update", "OK"}
    buttons["Copy command"].handlers["clicked"]()
    assert _FakeGtk.clipboard == [("set_text", "sudo rpi-eeprom-update -a", -1), ("store",)]
    assert buttons["Copy command"].calls["set_label"] == [("Copied",)]
    assert item.spawned == []                 # copying runs nothing
    buttons["How to update"].handlers["clicked"]()
    assert item.spawned == [["open", fw.DOC_URL]]


def test_firmware_copy_uses_wl_copy_on_wayland(fake_gtk, monkeypatch, tmp_path):
    # wl-copy, where installed, serves the text on its own as well
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(ind.shutil, "which", lambda name: "/usr/bin/" + name)
    item = _notice_window(monkeypatch, tmp_path)
    assert item.copy_text(fw.UPDATE_CMD) is True
    assert item.spawned == [["wl-copy", "sudo rpi-eeprom-update -a"]]


def test_howto_text(tmp_path):
    env = _fw_env(tmp_path, model="pi5")
    _fw(env, "check", "--write")
    out = _fw(env, "howto").stdout
    assert out.startswith("The Pi's firmware is from 8 May 2025.")
    assert "Raspberry Pi Connect from Imager" in out and fw.HOWTO in out and fw.DOC_URL in out


def test_notices_reach_the_trixie_panel_too():
    # wf-panel-pi's bus name on Trixie (busctl --user list, rig Pi 4)
    assert ind.PANELS["com.raspberrypi.wfpanelpi"] == ("/com/raspberrypi/wfpanelpi",
                                                       "com.raspberrypi.wfpanelpi")
    assert "org.wayfire.wfpanel" in ind.PANELS          # Bookworm


def test_system_info_from_the_badge_is_a_window():
    assert ind.SYSINFO_CMD[-1].endswith("do_show_system_info window")


@pytest.mark.parametrize("arg,text", [("window", "Press Enter to close this window."),
                                      ("", "Press Enter to return to the menu.")])
def test_system_info_enter_line(menu_env, arg, text):
    # 40 lines do not fit 80x24: printed with the "press Enter" line
    fake = menu_env.tmp / "rq_info.sh"
    fake.write_text("#!/bin/sh\n" + "".join(f'echo "line {i}"\n' for i in range(40)))
    fake.chmod(0o755)
    menu = os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")
    code = (f'sed "s|/usr/bin/rq_info.sh|{fake}|g" "{menu}" > "$TMPDIR/m.sh"; . "$TMPDIR/m.sh"; '
            f'do_show_system_info {arg} </dev/null')
    proc = menu_env(code)
    assert text in proc.stdout


# ---------------------------------------------------------------------------
# The checklist: the firmware step and the password wording (P2)
# ---------------------------------------------------------------------------

def _fake_firmware(tmp_path, due):
    path = tmp_path / "rq_firmware.py"
    _exe(path, 'echo "$1" >> "${FW_LOG:-/dev/null}"\ncase "$1" in\n'
               f'  due) {"echo notice; exit 0" if due else "exit 1"} ;;\n'
               '  line) echo "8 May 2025 (update available)" ;;\n'
               '  howto) echo "The Pi\'s firmware is from 8 May 2025. HOWTO" ;;\n'
               'esac\n')
    return path


def test_checklist_mentions_the_firmware_unticked(stubs, tmp_path):
    proc = _checklist(stubs, tmp_path, WT_RC_checklist="1",
                      RQ_FIRMWARE=str(_fake_firmware(tmp_path, True)))
    assert proc.returncode == 0, proc.stderr
    args = (tmp_path / "wt.log").read_text().split("@@")[0].splitlines()
    i = args.index("firmware")
    assert args[i + 1] == "About the Pi's firmware (from 8 May 2025; a newer one is available)"
    assert args[i + 2] == "OFF"


def test_checklist_firmware_step_only_explains(stubs, tmp_path):
    fake = _fake_firmware(tmp_path, True)
    log = tmp_path / "fw.log"
    proc = _checklist(stubs, tmp_path, WT_REPLY_checklist="firmware", RQ_FIRMWARE=str(fake),
                      FW_LOG=str(log))
    assert proc.returncode == 0, proc.stderr
    assert set(log.read_text().split()) <= {"due", "line", "howto"}   # it only explains
    calls = (tmp_path / "wt.log").read_text().split("@@")
    box = next(c for c in calls if "--msgbox" in c and "HOWTO" in c)
    assert "The Pi's firmware is from 8 May 2025." in box
    read = tmp_path / "home" / ".state" / "rasqberry" / "firmware-info-read"
    assert read.read_text().strip() == "8 May 2025 (update available)"
    # read: the next list says "Read again", not a pending step
    (tmp_path / "wt.log").unlink()
    _checklist(stubs, tmp_path, WT_RC_checklist="1", RQ_FIRMWARE=str(fake))
    args = (tmp_path / "wt.log").read_text().split("@@")[0].splitlines()
    assert args[args.index("firmware") + 1] == "Read again: about the Pi's firmware"


def test_checklist_without_an_outdated_firmware(stubs, tmp_path):
    _checklist(stubs, tmp_path, WT_RC_checklist="1", RQ_FIRMWARE=str(_fake_firmware(tmp_path, False)))
    args = (tmp_path / "wt.log").read_text().split("@@")[0].splitlines()
    assert "firmware" not in args


@pytest.mark.skipif(shutil.which("perl") is None, reason="perl required")
def test_password_step_does_not_say_still(stubs, tmp_path):
    _, texts, _ = _password_step(stubs, tmp_path, ["<cancel>"])
    assert "uses the published demo password" in texts
    assert "still has the demo password" not in texts


# ---------------------------------------------------------------------------
# Raspberry Pi Connect (P4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("output,state", [
    ("Signed in: yes\nSubscribed to events: yes\n", "signed-in"),
    ("Signed in: no\nTo sign in, run rpi-connect signin\n", "signed-out"),
    ("✗ Raspberry Pi Connect is not running, run rpi-connect on\n", "off"),
])
def test_connect_state(tmp_path, output, state):
    stub = tmp_path / "rpi-connect"
    _exe(stub, f"cat <<'EOF'\n{output}EOF\n")
    env = dict(os.environ, RQ_RPI_CONNECT=str(stub))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_remote_access.sh"), "connect"],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip() == state, proc.stderr


def test_connect_not_installed(tmp_path):
    env = dict(os.environ, RQ_RPI_CONNECT=str(tmp_path / "missing"))
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_remote_access.sh"), "connect"],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip() == "missing"


@pytest.mark.parametrize("state,line", [
    ("signed-out", "Raspberry Pi Connect: on, not signed in"),
    ("off", "Raspberry Pi Connect: off"),
    ("missing", None),
])
def test_remote_menu_shows_connect(menu_env, state, line):
    code = ('_rq_remote() { case "$1" in status) '
            'echo "ssh=on vnc=on name=rasqberry mdns=rasqberry.local ssh_password=yes" ;; '
            f'connect) echo {state} ;; esac; return 0; }}; '
            f'do_connect_info {state}; do_remote_access_menu')
    menu_env(code, extra_env={"WT_RC_menu": "1"})
    texts = _texts(menu_env)
    if line:
        assert line in texts
    else:
        assert "Raspberry Pi Connect:" not in texts
    assert "connect.raspberrypi.com" in texts          # the info box
    if state == "off":
        assert "Turn On Raspberry Pi Connect" in texts


def test_system_info_shows_firmware_and_connect(stubs, tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shutil.copy(os.path.join(_BIN, "rq_info.sh"), bindir / "rq_info.sh")
    _exe(bindir / "rq_firmware.py", 'echo "8 May 2025 (update available)"\n')
    _exe(bindir / "rq_remote_access.sh",
         'case "$1" in connect) echo signed-in ;; mdns) echo rasqberry.local ;; esac\n')
    env = dict(os.environ, PATH=stubs.path, RQ_BUILD_JSON=str(tmp_path / "none.json"))
    out = subprocess.run(["bash", str(bindir / "rq_info.sh")], env=env, capture_output=True,
                         text=True, timeout=30).stdout
    assert ("Firmware:          8 May 2025 (update available)\n"
            "                   To update, run this, then restart:\n"
            "                     sudo rpi-eeprom-update -a\n") in out
    assert "Pi Connect:        on, signed in\n" in out


# ---------------------------------------------------------------------------
# SSH locale (macOS sends LC_CTYPE=UTF-8)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("given,expected", [
    ({"LC_CTYPE": "UTF-8"}, {"LC_CTYPE": "C.UTF-8"}),
    ({"LANG": "en_GB.UTF-8", "LC_CTYPE": "UTF-8"}, {"LANG": "en_GB.UTF-8", "LC_CTYPE": "C.UTF-8"}),
    ({"LC_ALL": "de_DE.UTF-8"}, {"LC_ALL": "C.UTF-8"}),
    ({"LANG": "C.UTF-8"}, {"LANG": "C.UTF-8"}),
    ({}, {}),
])
def test_locale_profile(tmp_path, given, expected):
    d = tmp_path / "bin"
    d.mkdir()
    _exe(d / "locale", 'printf "C\\nC.utf8\\nPOSIX\\nen_GB.utf8\\n"\n')
    env = {"PATH": f"{d}:/usr/bin:/bin"}
    env.update(given)
    proc = subprocess.run(["sh", "-c", f'. "{_LOCALE}"; for v in LC_ALL LC_CTYPE LANG; do '
                           'eval "x=\\${$v-unset}"; echo "$v=$x"; done; set | grep -c "^_[avln]=" || true'],
                          env=env, capture_output=True, text=True, timeout=30)
    got = dict(line.split("=", 1) for line in proc.stdout.splitlines()[:3])
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        assert got[var] == expected.get(var, "unset"), proc.stdout
    assert proc.stdout.splitlines()[3] == "0"           # no helper variables left


def test_locale_profile_without_locale_tool_changes_nothing(tmp_path):
    env = {"PATH": str(tmp_path), "LANG": "en_GB.UTF-8"}
    proc = subprocess.run(["/bin/sh", "-c", f'. "{_LOCALE}"; echo "$LANG"'],
                          env=env, capture_output=True, text=True, timeout=30)
    assert proc.stdout.strip() == "en_GB.UTF-8"


def test_locale_profile_is_installed_first():
    names = sorted(os.listdir(os.path.join(_SYS, "etc", "profile.d")))
    assert names[0] == "00-rq-locale.sh"
    assert not os.access(_LOCALE, os.X_OK)               # sourced, like the others
