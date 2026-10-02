"""
Tests for batch B5 (review 2026-10): first-boot onboarding and LED setup.

- One LED layout setting (Q22, R-022, R-155): text, logos and the boot IP
  scroll follow LED_LAYOUT; the retired LED_MATRIX_* keys are dropped from env
  files, device-settings stores and boot files, a legacy "quad" becomes
  quad-4x12.
- The LED panel check (R-009, R-010, R-011, R-150): colour-free cue (blinking),
  a layout file for an unsaved custom layout.
- Honest clearing (R-148), the panel holder check in the menu (R-162), the
  shutdown clear (R-043), the dark cube logo (R-159).
- The setup checklist opens by itself once (Q12, R-008).

No hardware: strips are lists, whiptail and terminals are stubs.
"""

import os
import shutil
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
sys.path.insert(0, _BIN)
sys.path.insert(0, _HERE)

import rq_env_merge  # noqa: E402
import rq_led_utils as lu  # noqa: E402
import rq_led_wizard_probe as pw  # noqa: E402
from test_raspi_config_menu import _DASH, _env_value, menu_env  # noqa: E402,F401

_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")


# ---------------------------------------------------------------------------
# One layout setting
# ---------------------------------------------------------------------------

@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Point rq_led_utils at a private env file; returns a writer."""
    path = tmp_path / "rasqberry_environment.env"

    def write(text):
        path.write_text(text)
        monkeypatch.setattr(lu, "_env_cache", None)
        monkeypatch.setattr(lu, "_env_cache_key", None)

    def parse(p):
        values = {}
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k] = v
        return values

    monkeypatch.setattr(lu, "ENV_FILE", str(path))
    monkeypatch.setattr(lu, "dotenv_values", parse)
    monkeypatch.delenv("LED_RENDER_MODE", raising=False)
    return write


def test_text_geometry_follows_led_layout_not_the_retired_keys(env_file):
    # the Pi 4 rig: the wizard set quad-4x12, LED_MATRIX_LAYOUT stayed "single"
    env_file("LED_LAYOUT=quad-4x12\nLED_MATRIX_LAYOUT=single\nLED_MATRIX_WIDTH=99\n")
    config = lu.get_led_config()
    assert config["layout"] == config["led_layout"] == "quad-4x12"
    assert (config["matrix_width"], config["matrix_height"]) == (24, 8)

    env_file("LED_LAYOUT=single-8x32\n")
    config = lu.get_led_config()
    assert (config["layout"], config["matrix_width"], config["led_count"]) == ("single-8x32", 32, 256)


def test_env_without_led_layout_maps_legacy_quad_to_the_kit(env_file):
    env_file("LED_MATRIX_LAYOUT=quad\n")
    assert lu.get_led_config()["led_layout"] == "quad-4x12"
    env_file("LED_MATRIX_LAYOUT=single\n")
    assert lu.get_led_config()["led_layout"] == "single-24x8"


class _Strip(list):
    """A strip that records every frame shown."""

    def __init__(self, n):
        super().__init__([(0, 0, 0)] * n)
        self.frames = []

    def fill(self, colour):
        for i in range(len(self)):
            self[i] = colour

    def show(self):
        self.frames.append(list(self))


def _expected_frame(text, layout, colour, n=192):
    """The first frame of the scroll, drawn by hand through `layout`."""
    frame = [(0, 0, 0)] * n
    columns = lu.create_text_bitmap(text)
    for x in range(24):
        if x < len(columns):
            for y in range(7):
                if columns[x] & (1 << y):
                    frame[lu.map_xy_to_pixel(x, y, layout=layout)] = colour
    return frame


@pytest.mark.parametrize("layout", ["quad-4x12", "single-24x8"])
def test_ip_scroll_is_upright_on_the_configured_panel(env_file, monkeypatch, layout):
    # R-155: rq_display_ip.py scrolls through display_scrolling_text
    env_file(f"LED_LAYOUT={layout}\nLED_MATRIX_LAYOUT=single\n")
    monkeypatch.setattr("time.sleep", lambda s: None)
    clock = iter(range(0, 1000))
    monkeypatch.setattr("time.time", lambda: next(clock))
    strip = _Strip(192)
    lu.display_scrolling_text(strip, "10.0", duration_seconds=2, scroll_speed=0, color=(1, 2, 3))
    assert strip.frames[0] == _expected_frame("10.0", layout, (1, 2, 3))
    if layout == "quad-4x12":
        assert strip.frames[0] != _expected_frame("10.0", "single-24x8", (1, 2, 3))


def test_logo_display_follows_led_layout(env_file, monkeypatch):
    pytest.importorskip("PIL")
    import rq_led_logo
    env_file("LED_LAYOUT=quad-4x12\nLED_MATRIX_LAYOUT=single\n")
    monkeypatch.setattr(rq_led_logo.time, "sleep", lambda s: None)
    image = [[(9, 9, 9) if (x, y) == (0, 0) else (0, 0, 0) for y in range(8)] for x in range(24)]
    strip = _Strip(192)
    rq_led_logo.display_static_image(strip, image, duration=0, brightness=1.0)
    lit = [i for i, p in enumerate(strip.frames[0]) if p != (0, 0, 0)]
    assert lit == [lu.map_xy_to_pixel(0, 0, layout="quad-4x12")]


def test_shipped_env_has_no_retired_matrix_keys():
    keys = [line.split("=", 1)[0] for line in open(_ENV) if "=" in line and not line.startswith("#")]
    assert not [k for k in keys if k.startswith("LED_MATRIX_")]
    assert "LED_LAYOUT" in keys and "LED_LAYOUT_VERIFIED" in keys


def test_env_merge_drops_retired_keys_and_keeps_the_panel():
    new = open(_ENV).read().splitlines()
    old = ["LED_LAYOUT=quad-4x12", "LED_LAYOUT_VERIFIED=true", "LED_MATRIX_LAYOUT=single",
           "LED_MATRIX_Y_FLIP=false", "LED_MATRIX_PANEL_WIDTH=12"]
    merged, *_ = rq_env_merge.merge(new, old)
    text = "\n".join(merged)
    assert "LED_MATRIX_" not in "\n".join(l for l in merged if not l.startswith("#"))
    assert "LED_LAYOUT=quad-4x12" in text and "LED_LAYOUT_VERIFIED=true" in text


def test_env_merge_turns_a_legacy_quad_into_quad_4x12():
    new = open(_ENV).read().splitlines()
    merged, *_ = rq_env_merge.merge(new, ["LED_MATRIX_LAYOUT=quad", "LED_COUNT=192"])
    assert "LED_LAYOUT=quad-4x12" in merged


def test_device_settings_store_skips_retired_keys(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash required")
    env = tmp_path / "env"
    env.write_text("LED_LAYOUT=quad-4x12\nLED_LAYOUT_VERIFIED=true\nLED_MATRIX_LAYOUT=single\n")
    store = tmp_path / "store"
    run_env = dict(os.environ, RQ_ENV_FILE=str(env), RQ_SETTINGS_DIR=str(store),
                   RQ_SETTINGS_MARKER=str(tmp_path / "applied"),
                   RQ_SETTINGS_USER_HOME=str(tmp_path), RQ_SETTINGS_SKIP_MOUNT_CHECK="1")
    script = os.path.join(_BIN, "rq_device_settings.sh")
    assert subprocess.run(["bash", script, "save"], env=run_env, capture_output=True).returncode == 0
    saved = (store / "device-settings.env").read_text()
    assert "LED_LAYOUT_VERIFIED=true" in saved and "LED_MATRIX" not in saved

    # an older store must not put them back into a new slot
    (store / "device-settings.env").write_text("LED_LAYOUT=quad-4x12\nLED_MATRIX_LAYOUT=quad\n")
    env.write_text("LED_LAYOUT=single-24x8\n")
    os.remove(tmp_path / "applied")
    assert subprocess.run(["bash", script, "restore"], env=run_env, capture_output=True).returncode == 0
    assert env.read_text().splitlines() == ["LED_LAYOUT=quad-4x12"]


def _bash4():
    bash = shutil.which("bash")
    if not bash:
        return None
    out = subprocess.run([bash, "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True, text=True)
    return bash if out.stdout.strip().isdigit() and int(out.stdout) >= 4 else None


@pytest.mark.skipif(_bash4() is None, reason="bash 4+ required (declare -A)")
def test_boot_file_legacy_matrix_layout_becomes_led_layout(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "systemd-cat").write_text("#!/bin/sh\ncat >/dev/null\n")
    os.chmod(stubs / "systemd-cat", 0o755)
    env = tmp_path / "env"
    env.write_text("LED_LAYOUT=single-24x8\nLED_GPIO_PIN=18\n")
    boot = tmp_path / "boot.env"
    boot.write_text("LED_MATRIX_LAYOUT=quad\nLED_MATRIX_WIDTH=32\nLED_LAYOUT_VERIFIED=true\n")
    run_env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_BOOT_CONFIG=str(boot),
                   RQ_ENV_FILE=str(env), RQ_BOOT_TEMP_ENV=str(tmp_path / "tmp.env"))
    script = os.path.join(_ROOT, "RQB2-system", "usr", "local", "bin", "rasqberry-load-boot-config.sh")
    proc = subprocess.run([_bash4(), script], env=run_env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    lines = env.read_text().splitlines()
    assert "LED_LAYOUT=quad-4x12" in lines
    assert "LED_LAYOUT_VERIFIED=true" in lines       # appended, it was missing
    assert not [l for l in lines if l.startswith("LED_MATRIX_")]


def test_boot_template_uses_led_layout():
    text = open(os.path.join(_ROOT, "stage-RQB2", "10-boot-config", "files", "rasqberry_boot.env")).read()
    assert "#LED_LAYOUT=" in text and "LED_LAYOUT_VERIFIED" in text
    assert not [l for l in text.splitlines() if l.startswith("#LED_MATRIX_")]


# ---------------------------------------------------------------------------
# The LED panel check: probe
# ---------------------------------------------------------------------------

def test_blinking_logo_is_a_colour_free_cue(monkeypatch):
    strip = _Strip(192)
    monkeypatch.setattr(pw, "_make_strip", lambda count, brightness: strip)
    monkeypatch.setattr(pw.time, "sleep", lambda s: None)
    pw.render_logo(192, "quad-4x12", color=(255, 255, 0), blink=3)
    lit = [any(p != (0, 0, 0) for p in f) for f in strip.frames]
    assert lit == [True, False, True, False, True, False, True]   # ends lit
    strip.frames.clear()
    pw.render_logo(192, "single-24x8", color=(0, 0, 255))
    assert len(strip.frames) == 1                                     # steady


def test_probe_renders_an_unsaved_custom_layout_from_a_file(tmp_path, monkeypatch):
    import json
    layout = dict(lu.get_layout("quad-4x12"))
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(layout))
    seen = {}
    monkeypatch.setattr(pw, "render_logo", lambda count, lay, **kw: seen.update(layout=lay, **kw))
    assert pw.main(["--pattern", "logo", "--layout-file", str(path), "--count", "192",
                    "--color", "white"]) == 0
    assert seen["layout"]["panels"] == layout["panels"]


def test_probe_colours_avoid_red_green(monkeypatch):
    # R-011: the run and wiring probes are blue/yellow with white start LEDs
    strip = _Strip(192)
    monkeypatch.setattr(pw, "_make_strip", lambda count, brightness: strip)
    pw.render_pattern("row2", 192, run=8)
    colours = {p for p in strip.frames[-1] if p != (0, 0, 0)}
    assert colours == {(0, 0, 255), (255, 255, 0), (255, 255, 255)}


def test_cube_logo_is_dark_and_not_white():
    pil = pytest.importorskip("PIL.Image")
    image = pil.open(os.path.join(_ROOT, "RQB2-config", "LED-Logos", "rasqberry-cube-24x8.png")).convert("RGB")
    pixels = [image.getpixel((x, y)) for x in range(24) for y in range(8)]
    lit = [p for p in pixels if p != (0, 0, 0)]
    assert len(lit) <= 192 // 3
    assert (255, 255, 255) not in lit


def test_turn_off_leds_reports_failure(monkeypatch):
    import turn_off_LEDs
    monkeypatch.setattr(turn_off_LEDs, "clear_all_leds", lambda: False)
    monkeypatch.setattr(sys, "argv", ["turn_off_LEDs.py"])
    assert turn_off_LEDs.main() == 1
    monkeypatch.setattr(turn_off_LEDs, "clear_all_leds", lambda: True)
    assert turn_off_LEDs.main() == 0


# ---------------------------------------------------------------------------
# The menu (raspi-config context, dash)
# ---------------------------------------------------------------------------

def _texts(menu_env):
    return "\n".join("\n".join(c) for c in menu_env.whiptail_calls())


def test_led_menu_has_one_layout_setting(menu_env):
    proc = menu_env("_RQ_LED_VERIFY_DONE=1; do_select_led_option; echo RC=$?",
                    extra_env={"WT_RC_menu": "1"})
    assert "RC=0" in proc.stdout, proc.stderr
    texts = _texts(menu_env)
    assert "Configure Matrix Layout" not in texts and "Check the LED Panel" in texts
    assert "do_select_led_layout" not in open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()


def test_led_check_is_not_offered_again_after_no_panel(menu_env):
    proc = menu_env('LED_LAYOUT_VERIFIED=skipped; bash() { echo "WIZARD $*"; }; do_led_verify; '
                    'echo ---; do_led_verify --again')
    first, second = proc.stdout.split("---")
    assert "WIZARD" not in first
    assert "--verify" in second


def test_led_demo_names_the_holder_and_can_be_cancelled(menu_env):
    code = ('_rq_led_holders() { echo "123 the IP address scroll at start-up"; }; '
            'run_demo() { echo DEMO_STARTED; }; '
            'run_led_demo bg "IBM LED Demo" /tmp python3 x.py; echo RC=$?')
    proc = menu_env(code, extra_env={"WT_RC_yesno": "1"})
    assert "DEMO_STARTED" not in proc.stdout and "RC=0" in proc.stdout, proc.stderr
    assert "the IP address scroll at start-up" in _texts(menu_env)


def test_stop_says_when_nothing_runs(menu_env):
    proc = menu_env("_rq_led_holders() { :; }; LAST_DEMO_PGID=; stop_last_demo; echo RC=$?")
    assert "RC=0" in proc.stdout
    texts = _texts(menu_env)
    assert "No demo is running." in texts and "cleared the LEDs" not in texts


def test_brightness_is_validated_but_not_capped(menu_env):
    env = {"WT_REPLY_menu": "LED_DEFAULT_BRIGHTNESS", "WT_REPLY_inputbox": "1.5"}
    menu_env("do_select_environment_variable", extra_env=env)
    assert _env_value(menu_env.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.4"
    env["WT_REPLY_inputbox"] = "0.8"
    menu_env("do_select_environment_variable", extra_env=env)
    assert "Brighter LED Panel" in _texts(menu_env)
    assert _env_value(menu_env.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.8"


def test_main_menu_offers_the_checklist_and_safe_shutdown(menu_env):
    menu_env("do_rasqberry_menu", extra_env={"WT_RC_menu": "1"})
    texts = _texts(menu_env)
    assert "Setup Checklist" in texts and "Shut Down Safely" in texts


# ---------------------------------------------------------------------------
# System files
# ---------------------------------------------------------------------------

def test_shutdown_clear_unit_is_enabled_and_physical_only():
    unit = open(os.path.join(_ROOT, "RQB2-system", "etc", "systemd", "system",
                             "rasqberry-led-clear.service")).read()
    assert "turn_off_LEDs.py --physical" in unit and "ExecStop=" in unit
    assert "rasqberry-led-clear.service" in open(os.path.join(_ROOT, "RQB2-system", "enabled-units.txt")).read()


# ---------------------------------------------------------------------------
# The setup checklist opens by itself once (Q12)
# ---------------------------------------------------------------------------

def test_desktop_opens_the_checklist_once(tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash required")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "terminal.log"
    for name, body in (("lxterminal", f'printf "%s\\n" "$@" >> "{log}"\n'),
                       ("systemctl", "exit 1\n"), ("sudo", "exit 1\n")):
        path = stubs / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), PATH=f"{stubs}:{os.environ['PATH']}",
               RQ_FIRSTLOGIN_MIN_WAIT="0", XDG_STATE_HOME=str(home / ".state"))
    script = os.path.join(_BIN, "rq_firstlogin.sh")
    # The LED check is pending (no env file here: LED_LAYOUT_VERIFIED unset)
    first = subprocess.run(["bash", script, "--desktop"], env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "--now" in log.read_text()
    assert (home / ".state" / "rasqberry" / "setup-checklist-shown").exists()
    log.unlink()
    second = subprocess.run(["bash", script, "--desktop"], env=env, capture_output=True, text=True)
    assert second.returncode == 0 and not log.exists()
