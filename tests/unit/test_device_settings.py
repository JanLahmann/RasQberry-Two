"""
Tests for RQB2-bin/rq_device_settings.sh (issue #290): LED settings survive
an A/B image update by way of the shared /data partition.

Every path is redirected into tmp_path through the script's environment
overrides; the /data mount check is skipped. Two env files stand in for the
two slots.
"""

import json
import os
import shutil
import subprocess
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_device_settings.sh")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")

SHIPPED = """# LED
LED_LAYOUT=single-24x8
LED_LAYOUT_VERIFIED=false
LED_GPIO_PIN=18
LED_PAINTER_INSTALLED=false
# other
QOFFEE_MAKER_INSTALLED=false
PI_MODEL=Pi5
"""


class Slot:
    """One A/B slot: its own env file, marker and user home; a shared store."""

    def __init__(self, tmp_path, name, store):
        self.root = tmp_path / name
        self.root.mkdir()
        self.env_file = self.root / "rasqberry_environment.env"
        self.env_file.write_text(SHIPPED)
        self.home = self.root / "home"
        self.home.mkdir()
        self.store = store

    def run(self, cmd):
        env = dict(
            os.environ,
            RQ_ENV_FILE=str(self.env_file),
            RQ_SETTINGS_DIR=str(self.store),
            RQ_SETTINGS_MARKER=str(self.root / "applied"),
            RQ_SETTINGS_USER_HOME=str(self.home),
            RQ_SETTINGS_SKIP_MOUNT_CHECK="1",
        )
        proc = subprocess.run(["bash", _SCRIPT, cmd], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, proc.stderr
        return proc

    def set(self, key, value):
        lines = [f"{key}={value}" if l.startswith(key + "=") else l
                 for l in self.env_file.read_text().splitlines()]
        self.env_file.write_text("\n".join(lines) + "\n")

    def value(self, key):
        found = [l.split("=", 1)[1] for l in self.env_file.read_text().splitlines()
                 if l.startswith(key + "=")]
        return found[-1] if found else None


@pytest.fixture
def slots(tmp_path):
    store = tmp_path / "data" / "rasqberry"
    return Slot(tmp_path, "a", store), Slot(tmp_path, "b", store)


def test_fresh_slot_gets_the_led_settings_back(slots):
    a, b = slots
    a.set("LED_LAYOUT", "quad-4x12")
    a.set("LED_LAYOUT_VERIFIED", "true")
    a.run("save")

    b.run("restore")  # fresh slot B: shipped defaults, no marker
    assert b.value("LED_LAYOUT") == "quad-4x12"
    assert b.value("LED_LAYOUT_VERIFIED") == "true"


def test_installed_flags_and_other_keys_stay_per_slot(slots):
    a, b = slots
    a.set("LED_PAINTER_INSTALLED", "true")
    a.set("QOFFEE_MAKER_INSTALLED", "true")
    a.set("PI_MODEL", "Pi4")
    a.run("save")
    saved = (a.store / "device-settings.env").read_text()
    assert "LED_PAINTER_INSTALLED" not in saved
    assert "QOFFEE_MAKER_INSTALLED" not in saved

    b.run("restore")
    assert b.value("LED_PAINTER_INSTALLED") == "false"
    assert b.value("QOFFEE_MAKER_INSTALLED") == "false"
    assert b.value("PI_MODEL") == "Pi5"


def test_restore_keeps_file_layout_and_comments(slots):
    a, b = slots
    a.set("LED_LAYOUT", "quad-4x12")
    a.run("save")
    b.run("restore")
    lines = b.env_file.read_text().splitlines()
    assert lines[0] == "# LED"
    assert lines[1] == "LED_LAYOUT=quad-4x12"


def test_a_change_on_this_slot_is_not_reverted_by_an_older_save(slots):
    a, b = slots
    a.set("LED_LAYOUT", "quad-4x12")
    a.run("save")
    b.run("restore")
    # later, on slot B, a writer that does not call save changes the layout
    b.set("LED_LAYOUT", "single-24x8")
    b.run("restore")  # next boot of B: the saved copy is older than B's apply
    assert b.value("LED_LAYOUT") == "single-24x8"


def test_a_newer_save_on_the_other_slot_is_applied(slots):
    a, b = slots
    a.set("LED_LAYOUT", "quad-4x12")
    a.run("save")
    b.run("restore")
    time.sleep(1.1)
    a.set("LED_LAYOUT", "single-24x8")
    a.run("save")
    b.run("restore")
    assert b.value("LED_LAYOUT") == "single-24x8"


def test_own_save_is_not_restored_over_itself(slots):
    a, _ = slots
    a.set("LED_LAYOUT", "quad-4x12")
    a.run("save")
    before = a.env_file.read_text()
    a.run("restore")
    assert a.env_file.read_text() == before


def test_new_keys_are_appended(slots):
    a, b = slots
    with open(a.env_file, "a") as fh:
        fh.write("LED_WEB=true\n")
    a.run("save")
    b.run("restore")
    assert b.value("LED_WEB") == "true"


def test_custom_layouts_follow_but_never_overwrite(slots):
    a, b = slots
    (a.home / ".local/config").mkdir(parents=True)
    (a.home / ".local/config/led-layouts.json").write_text(json.dumps({"mine": {}}))
    a.run("save")
    b.run("restore")
    assert json.loads((b.home / ".local/config/led-layouts.json").read_text()) == {"mine": {}}

    # a slot that already has its own custom layouts keeps them
    (b.home / ".local/config/led-layouts.json").write_text(json.dumps({"b-own": {}}))
    time.sleep(1.1)
    a.run("save")
    b.run("restore")
    assert json.loads((b.home / ".local/config/led-layouts.json").read_text()) == {"b-own": {}}


def test_nothing_saved_means_restore_does_nothing(slots):
    _, b = slots
    before = b.env_file.read_text()
    b.run("restore")
    assert b.env_file.read_text() == before


def test_without_shared_data_mount_both_commands_do_nothing(tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text("LED_LAYOUT=quad-4x12\n")
    store = tmp_path / "store"
    env = dict(os.environ, RQ_ENV_FILE=str(env_file), RQ_SETTINGS_DIR=str(store),
               RQ_SETTINGS_MARKER=str(tmp_path / "m"), RQ_SETTINGS_USER_HOME=str(tmp_path))
    # no skip flag: on a machine where /data is not a mount point this is the
    # standard-image path
    if subprocess.run(["sh", "-c", "mountpoint -q /data"], capture_output=True).returncode == 0:
        pytest.skip("/data is a mount point here")
    for cmd in ("save", "restore"):
        assert subprocess.run(["bash", _SCRIPT, cmd], env=env).returncode == 0
    assert not store.exists()
