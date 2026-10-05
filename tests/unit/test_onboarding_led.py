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


def _display_ip():
    import importlib
    try:
        return importlib.import_module("rq_display_ip")
    except Exception as exc:  # pragma: no cover - LED libraries missing
        pytest.skip(f"rq_display_ip not importable: {exc}")


@pytest.mark.parametrize("verified", ["false", "skipped", None])
def test_unverified_ip_scroll_alternates_the_kit_layouts(verified):
    # A new card: single-24x8 until the checklist's LED step; on the quad kit
    # every second pass must read right (rig, 2026-10-04)
    ip = _display_ip()
    config = {"led_layout": "single-24x8"}
    if verified is not None:
        config["layout_verified"] = verified
    s, q = "single-24x8", "quad-4x12"
    assert ip.pass_layouts(1, config) == [s, q, s, q]
    assert ip.pass_layouts(3, config) == [s, q, s, q]
    assert ip.pass_layouts(4, config) == [s, q, s, q]
    assert ip.pass_layouts(5, config) == [s, q, s, q, s, q]
    # configured quad (unverified): it comes first
    assert ip.pass_layouts(2, dict(config, led_layout=q)) == [q, s, q, s]


def test_verified_ip_scroll_uses_only_the_configured_layout():
    ip = _display_ip()
    for layout in ("single-24x8", "quad-4x12", "single-8x32"):
        config = {"led_layout": layout, "layout_verified": "true"}
        assert ip.pass_layouts(3, config) == [layout] * 3
        assert ip.pass_layouts(0, config) == [layout]


@pytest.mark.parametrize("verified", [False, True])
def test_ip_scroll_switches_the_layout_per_pass_on_one_strip(env_file, monkeypatch, capsys, verified):
    ip = _display_ip()
    env_file("LED_LAYOUT=single-24x8\nLED_LAYOUT_VERIFIED=%s\n" % ("true" if verified else "false"))
    monkeypatch.setattr("time.sleep", lambda s: None)
    config = lu.get_led_config()
    assert config["layout_verified"] == ("true" if verified else "false")
    strip = _Strip(192)
    layouts = ip.scroll_text(strip, "10.0", config, wanted_seconds=60, speed=0)
    per_pass = len(lu.create_text_bitmap("10.0")) + 24 + 1     # steps + the clear
    assert len(strip.frames) == per_pass * len(layouts)
    firsts = [strip.frames[i * per_pass] for i in range(len(layouts))]
    if verified:
        assert layouts == ["single-24x8"]
        assert "alternating" not in capsys.readouterr().out
    else:
        assert layouts == ["single-24x8", "quad-4x12"] * 2
        assert "alternating single-24x8 and quad-4x12" in capsys.readouterr().out
    for frame, layout in zip(firsts, layouts):
        assert frame == _expected_frame("10.0", layout, (0, 100, 255))


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
# The setup checklist opens by itself until a person answered it (Q12, item 22)
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
    # item 22: opening a window is not "shown" - nobody may be looking (monitor
    # off, headless); the window's --now marks it once a person answers
    shown = home / ".state" / "rasqberry" / "setup-checklist-shown"
    assert not shown.exists()
    log.unlink()
    second = subprocess.run(["bash", script, "--desktop"], env=env, capture_output=True, text=True)
    assert second.returncode == 0 and "--now" in log.read_text()
    log.unlink()
    shown.parent.mkdir(parents=True, exist_ok=True)
    shown.write_text("answered\n")
    third = subprocess.run(["bash", script, "--desktop"], env=env, capture_output=True, text=True)
    assert third.returncode == 0 and not log.exists()


def test_checklist_is_marked_only_after_an_answer():
    # the mark comes from the dialog's exit code, not from opening it
    text = open(os.path.join(_BIN, "rq_firstlogin.sh")).read()
    desktop = text[text.index('if [ "$MODE" = "desktop" ]; then'):text.index("# Collect what is pending")]
    assert "mark_shown\n    term=" not in desktop
    assert "0|1|255) [ \"$MODE\" = \"all\" ] || mark_shown" in text


# ---------------------------------------------------------------------------
# #29: plain words after the LED check, brightness and Clear LEDs; the address
# scroll once in the saved layout
# ---------------------------------------------------------------------------

_COMMON = os.path.join(_BIN, "rq_common.sh")


@pytest.mark.parametrize("layout,words", [
    ("single-24x8", "one 24x8 panel"),
    ("quad-4x12", "four 4x12 panels"),
    ("quad-2x2-12x4", "four 4x12 panels, mounted upside down"),
    ("triple-8x8", "three 8x8 panels"),
    ("single-8x32", "one 32x8 panel"),
    ("single-24x8-flipy", "one 24x8 panel, mounted upside down"),
    ("quad-4x12-flipx", "four 4x12 panels, mounted mirrored"),
    ("custom-24x8", "your own layout (24x8)"),
])
def test_layout_ids_have_plain_names(layout, words):
    out = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_led_layout_name "$1"', "_", layout],
                         capture_output=True, text=True).stdout.strip()
    assert out == words


def test_every_shipped_layout_has_a_plain_name():
    import json
    with open(os.path.join(_ROOT, "RQB2-config", "led-layouts.json")) as fh:
        ids = [k for k in json.load(fh) if not k.startswith("_")]
    for layout in ids:
        out = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_led_layout_name "$1"', "_", layout],
                             capture_output=True, text=True).stdout.strip()
        assert out != layout and "panel" in out, layout


def _exec(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def wizard(tmp_path):
    """The LED wizard's functions (main not run) with stub python3/whiptail."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    wt = tmp_path / "wt.log"
    _exec(stubs / "id", 'if [ "$1" = -u ]; then echo 0; else exec /usr/bin/id "$@"; fi\n')
    _exec(stubs / "sudo", '[ "$1" = -n ] && shift\nexec "$@"\n')
    _exec(stubs / "whiptail", f'{{ for a in "$@"; do printf "%s\\n" "$a"; done; echo @@; }} >> "{wt}"\n'
                              'exit "${WT_RC:-0}"\n')
    # python3: the infer step names the layout; the address scroll runs until stopped
    _exec(stubs / "python3", f'''#!/bin/bash
case "$1" in
  *rq_led_wizard_infer.py) echo "PRESET ${{WIZ_LAYOUT:-quad-4x12}}" ;;
  *rq_display_ip.py) echo "scroll $* mode=${{LED_RENDER_MODE:-}}" >> "{log}"
                     trap 'echo scroll-stopped >> "{log}"; exit 0' TERM
                     sleep 30 & wait ;;
  *rq_led_wizard_probe.py) echo "probe $* mode=${{LED_RENDER_MODE:-}}" >> "{log}" ;;
  *) exec /usr/bin/env -i PATH=/usr/bin:/bin python3 "$@" ;;
esac
''')
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(os.path.join(_ROOT, "RQB2-config", "rasqberry_env-config.sh")).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file)))
    body = open(os.path.join(_BIN, "rq_led_setup_wizard.sh")).read().replace('\nmain "$@"', "\n")
    (tmp_path / "bin").mkdir()
    shutil.copy(_COMMON, tmp_path / "bin" / "rq_common.sh")
    (tmp_path / "bin" / "wizard.sh").write_text(body)
    for name in ("rq_display_ip.py", "rq_led_wizard_infer.py", "rq_led_wizard_probe.py"):
        (tmp_path / "bin" / name).write_text("# stub\n")

    def run(code, extra=None):
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_CONFIG_FILE=str(env_config),
                   RQ_ENV_FILE=str(env_file), RQ_WIZ_LOG=str(tmp_path / "wizard.log"),
                   HOME=str(tmp_path))
        env.update(extra or {})
        return subprocess.run(["bash", "-c", f'. "{tmp_path}/bin/wizard.sh"\n{code}'],
                              capture_output=True, text=True, env=env, timeout=60)

    run.log = log
    run.wt = wt
    run.env_file = env_file
    return run


def test_saved_says_the_kit_in_words_and_scrolls_the_address(wizard):
    proc = wizard("INFER_SRC_ARGS=(--standard quad-4x12); run_setup; echo RC=$?")
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    dialog = wizard.wt.read_text()
    assert "Saved: four 4x12 panels" in dialog
    assert "LED_LAYOUT" not in dialog
    assert "shows this Pi's address once" in dialog
    calls = wizard.log.read_text().splitlines()
    scroll = [i for i, c in enumerate(calls) if c.startswith("scroll")]
    assert scroll and "--once" in calls[scroll[0]]
    # stopped when the message is closed, and the panel cleared after that
    stopped = calls.index("scroll-stopped")
    assert any(c.startswith("probe") and "--pattern clear" in c for c in calls[stopped:])
    assert _env_value(wizard.env_file, "LED_LAYOUT") == "quad-4x12"
    assert _env_value(wizard.env_file, "LED_LAYOUT_VERIFIED") == "true"


def test_saved_scroll_and_clears_draw_through_the_render_hold(wizard):
    """Saving reloads the env file, whose LED_RENDER_MODE is "direct". The
    address scroll and the clears after it must still draw through the
    wizard's renderer: on their own they opened the panel next to it, which
    left the next LED demo dark on a Pi 4 (#1) and the scroll dark on a Pi 5
    (#7)."""
    assert _env_value(wizard.env_file, "LED_RENDER_MODE") == "direct"
    proc = wizard("export LED_RENDER_MODE=service; HOLD_MODE=service\n"
                  "INFER_SRC_ARGS=(--standard quad-4x12); run_setup; echo RC=$?")
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    drawing = [c for c in wizard.log.read_text().splitlines() if c.startswith(("scroll ", "probe "))]
    assert any(c.startswith("scroll") for c in drawing)
    assert all(c.endswith("mode=service") for c in drawing), drawing


def test_wiring_check_names_the_kits_in_words(wizard):
    code = ('python3() { echo \'{"name": "single-24x8", "count": 192}\'; }; '
            'LED_LAYOUT=quad-4x12; INFER_SRC_ARGS=(--standard single-24x8); run_diagnostic')
    wizard(code)
    dialog = wizard.wt.read_text()
    assert "From what you saw: one 24x8 panel (192 LEDs)" in dialog
    assert "Saved now: four 4x12 panels" in dialog and "LED_LAYOUT" not in dialog


def test_ip_scroll_once_is_one_pass_in_the_saved_layout(env_file, monkeypatch):
    ip = _display_ip()
    env_file("LED_LAYOUT=quad-4x12\nLED_LAYOUT_VERIFIED=true\n")
    passes = []
    monkeypatch.setattr(ip, "create_neopixel_strip", lambda *a, **k: _Strip(192))
    monkeypatch.setattr(ip, "display_scrolling_text",
                        lambda pixels, text, scroll_speed, passes=None, layout=None:
                        passes_seen.append((passes, layout)))
    passes_seen = passes
    monkeypatch.setattr(ip, "get_ip_addresses", lambda: ["eth0: 10.0.0.7"])
    monkeypatch.setattr(ip, "get_network_name", lambda: "rasq.local")
    monkeypatch.setattr(ip, "record_shown", lambda a: pytest.fail("--once must not record"))
    monkeypatch.setattr(sys, "argv", ["rq_display_ip.py", "--once"])
    import signal
    saved = signal.getsignal(signal.SIGTERM)
    try:
        ip.main()
    finally:
        signal.signal(signal.SIGTERM, saved)
    assert passes == [(1, "quad-4x12")]


def test_brightness_and_clear_say_saved(menu_env):
    # Brightness: one line after choosing (rq_led_brightness.sh)
    text = open(os.path.join(_BIN, "rq_led_brightness.sh")).read()
    assert 'Saved: ${label}. LED demos use it from their next start.' in text
    # Clear LEDs in the menu: one line when it worked, none when it failed
    proc = menu_env("_rq_led_holders() { :; }; do_led_off() { return 0; }; do_led_clear; echo RC=$?")
    assert "RC=0" in proc.stdout and "All LEDs are off." in _texts(menu_env)
    proc = menu_env("_rq_led_holders() { :; }; do_led_off() { return 1; }; do_led_clear; echo RC=$?")
    assert "RC=1" in proc.stdout
    # The desktop icon's window stays long enough to read it
    clear = open(os.path.join(_BIN, "rq_clear_leds.sh")).read()
    assert 'sleep "${RQ_CLEAR_LEDS_PAUSE:-2}"' in clear


# ---------------------------------------------------------------------------
# #31: the LED-busy dialog names the demo; lgpio's FIFO stays out of the
# person's folders
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmdline,name", [
    ("/home/u/RasQberry-Two/venv/RQB2/bin/python3 /usr/bin/rq_led_ibm_logo.py", "IBM LED Demo"),
    ("python3 RasQ-LED.py", "RasQ-LED Demo"),
    ("python3 rq_led_simpletest.py", "Simple LED Demo"),
    ("python3 rq_test_leds.py", "Quick LED Test"),
    ("python3 /usr/bin/demo_led_text_scroll_welcome.py", "Text & Logo Display"),
    ("python3 LED_painter.py", "LED-Painter"),
    ("python3 /usr/bin/rq_display_ip.py --duration 60", "the IP address scroll at start-up"),
    ("bash /usr/bin/fractals.sh", "Quantum Fractals"),         # from its manifest
    ("python3 /tmp/my_own_program.py", "my_own_program.py"),
])
def test_led_holder_is_named_like_the_menu(cmdline, name):
    out = subprocess.run(["bash", "-c", f'. "{_COMMON}"; _rq_led_holder_label "$1"', "_", cmdline],
                         capture_output=True, text=True).stdout.strip()
    assert out == name


def test_lgpio_fifo_is_not_left_in_the_current_folder(tmp_path):
    """A stand-in lgpio makes its FIFO in its working directory at import, as
    the real one does; the person's folder stays clean and current."""
    fake = tmp_path / "fake"
    fake.mkdir()
    (fake / "lgpio.py").write_text(
        "import os\nopen(os.path.join(os.getcwd(), '.lgd-nfy0'), 'w').close()\n"
        "WORK = os.getcwd()\n")
    home = tmp_path / "My-Quantum-Programs"
    home.mkdir()
    code = ("import os, sys, rq_led_utils as lu\n"
            "lu._lgpio_files_out_of_cwd()\n"
            "import lgpio\n"
            "print(os.getcwd(), lgpio.WORK, os.path.exists(lgpio.WORK), flush=True)\n"
            "lu._lgpio_files_out_of_cwd()\n"                # already imported: nothing
            "os.kill(os.getpid(), 15)\n")                   # a stop skips exit handlers
    proc = subprocess.run([sys.executable, "-c", code], cwd=home, capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH=f"{fake}:{_BIN}"), timeout=30)
    assert proc.returncode == -15, proc.stderr
    cwd, work, there = proc.stdout.split()
    assert os.path.realpath(cwd) == os.path.realpath(home)
    assert os.listdir(home) == []
    # gone right after the import, not only at a normal exit (#19)
    assert there == "False" and not os.path.exists(work)
