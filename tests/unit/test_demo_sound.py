"""
Sound for LED demos (QEC demo review, Jan 2026-10-12): a Pi 4's headphone
jack shares the PWM hardware with the LED panel, so the launcher warns; and an
LED demo that plays sound runs as the desktop user (root cannot reach the
user's PipeWire), with the LED renderer doing the root part on a Pi 4.
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_RUN = os.path.join(_BIN, "rq_demo_run.sh")

# wpctl inspect @DEFAULT_AUDIO_SINK@ on the rig (excerpts)
PI4_JACK = '''id 57, type PipeWire:Interface:Node
    api.alsa.card.name = "bcm2835 Headphones"
  * node.description = "Built-in Audio Stereo"
  * node.name = "alsa_output.platform-fe00b840.mailbox.stereo-fallback"
'''
PI5_HDMI = '''id 61, type PipeWire:Interface:Node
    api.alsa.card.name = "vc4-hdmi-0"
  * node.description = "Built-in Audio Digital Stereo (HDMI)"
'''


def _sh(tmp_path, inspect, code):
    f = tmp_path / "inspect.txt"
    f.write_text(inspect)
    env = dict(os.environ, RQ_WPCTL_INSPECT=str(f))
    return subprocess.run(["bash", "-c", f'. "{_COMMON}"; {code}; echo "RC=$?"'],
                          capture_output=True, text=True, env=env)


@pytest.mark.parametrize("inspect, on_jack", [(PI4_JACK, True), (PI5_HDMI, False), ("", False)])
def test_jack_is_told_from_the_card_name(tmp_path, inspect, on_jack):
    proc = _sh(tmp_path, inspect, "rq_audio_on_jack")
    assert ("RC=0" in proc.stdout) is on_jack, proc.stdout + proc.stderr


@pytest.mark.parametrize("inspect, out, rc", [
    (PI5_HDMI, "Built-in Audio Digital Stereo (HDMI)", 0),
    (PI4_JACK, "Built-in Audio Stereo", 0),
    ("", "", 1),
])
def test_audio_output_names_the_default_sink(tmp_path, inspect, out, rc):
    proc = _sh(tmp_path, inspect, "rq_audio_output")
    lines = proc.stdout.splitlines()
    assert lines[-1] == f"RC={rc}", proc.stdout + proc.stderr
    assert (lines[0] if rc == 0 else "") == out


def test_launcher_warns_about_the_jack_with_leds():
    run = open(_RUN).read()
    block = run[run.index("check_requirements() {"):run.index("demo_docker_image()")]
    assert '[ "$needs_leds" = "true" ] && rq_audio_on_jack' in block
    assert "headphone jack, which uses the same hardware as the LED panel" in block
    # once per window, not again in the root pass
    assert '[ -z "$ROOT_PASS" ] || audio_req=none' in block


def test_led_demos_run_as_the_user_in_a_sandbox():
    run = open(_RUN).read()
    py = run[run.index("run_python() {"):run.index("# ROOT RUNS AND THE USER'S HOME")]
    # after the panel check, before the root fallback
    assert py.index("led_panel_ready") < py.index("rq_led_as_user") < py.index("(as root)")
    assert 'if [ "${RQ_LED_AS_ROOT:-}" != 1 ]; then' in py
    common = open(_COMMON).read()
    fn = common[common.index("rq_led_as_user() {"):common.index("rq_led_renderer_stop() {")]
    # a child of the launcher (stop signals reach it), not a systemd unit
    assert "systemd-run" not in fn
    assert "unshare --mount --propagation private" in fn
    for flag in ("--no-new-privs", "--bounding-set=-all", "--inh-caps=-all", "env -i"):
        assert flag in fn, flag
    # the whole home read-only, a few folders writable (test_led_sandbox.py)
    assert 'rq_led_sandbox_mounts "$home" "$PWD"' in fn
    assert "remount,bind,ro" in common and "remount,bind,rw" in common
    assert "XDG_RUNTIME_DIR" in fn and "LED_RENDER_MODE=" in fn
    # no sudo, adm or docker in the sandbox's groups
    groups = fn[fn.index("for g in"):fn.index("; do", fn.index("for g in"))]
    assert "sudo" not in groups and "docker" not in groups and "adm" not in groups


def test_a_manifest_cannot_ask_for_root():
    run = open(_RUN).read()
    assert "as_root" not in run.replace("RQ_LED_AS_ROOT", "")


@pytest.mark.parametrize("launcher", ["rq_led_ibm_demo.sh", "rq_rasq_led.sh",
                                      "rq_led_display_text.sh", "rq_led_display_logo.sh"])
def test_led_launchers_hand_the_program_to_the_sandbox(launcher):
    s = open(os.path.join(_BIN, launcher)).read()
    assert s.index("rq_led_user_prepare") < s.index("rq_led_as_user python3")


def test_root_pass_drops_the_users_python_paths():
    run = open(_RUN).read()
    assert "unset PYTHONPATH PYTHONHOME PYTHONSTARTUP" in run


def test_renderer_unit_is_confined():
    unit = open(os.path.join(_ROOT, "RQB2-system/etc/systemd/system/rasqberry-led-renderer.service")).read()
    assert "CapabilityBoundingSet=CAP_SYS_RAWIO CAP_DAC_READ_SEARCH CAP_FOWNER" in unit
    for line in ("NoNewPrivileges=yes", "ProtectSystem=strict", "PrivateNetwork=yes",
                 "DevicePolicy=closed", "DeviceAllow=/dev/mem rw"):
        assert line in unit, line


def test_cleanup_stops_the_sandbox_and_renderer_before_clearing():
    run = open(_RUN).read()
    clean = run[run.index("cleanup() {"):]
    assert "rq_led_release_panel" in clean
    common = open(_COMMON).read()
    on_exit = common[common.index("_rq_led_on_exit() {"):]
    assert "rq_led_release_panel" in on_exit
    release = common[common.index("rq_led_release_panel() {"):]
    assert release.index("rq_led_renderer_stop") < release.index("led_clear_quietly")


# The sound delay (RQ_AUDIO_DELAY_MS): how long LEDs wait for a Bluetooth
# speaker, one setting for every demo with sound (Jan, 2026-10-13)
_MENU = os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")


@pytest.mark.parametrize("value, ms", [
    ("", "0"), ("250", "250"), ("0", "0"), ("2000", "2000"), ("0150", "150"),
    ("2001", "0"), ("-5", "0"), ("abc", "0"), ("1.5", "0"), ("99999", "0"),
])
def test_audio_delay_is_checked(value, ms):
    env = dict(os.environ, RQ_AUDIO_DELAY_MS=value)
    proc = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_audio_delay_ms'],
                          capture_output=True, text=True, env=env)
    assert proc.stdout.strip().splitlines()[-1] == ms, proc.stderr
    # the menu (dash, without rq_common.sh) reads it the same way
    menu = open(_MENU).read()
    fns = menu[menu.index("_rq_audio_delay_ok() {"):menu.index("do_audio_delay() {")]
    proc = subprocess.run([shutil.which("dash") or "/bin/sh", "-c", fns + "\naudio_delay_ms"],
                          capture_output=True, text=True, env=env)
    assert proc.stdout.strip() == ms, proc.stderr


def test_audio_delay_reaches_the_demo_and_survives_updates():
    common = open(_COMMON).read()
    fn = common[common.index("rq_led_as_user() {"):common.index("rq_led_renderer_stop() {")]
    # through the sandbox's env -i
    assert 'RQ_AUDIO_DELAY_MS="$(rq_audio_delay_ms)"' in fn
    run = open(_RUN).read()
    block = run[run.index("check_requirements() {"):run.index("demo_docker_image()")]
    assert "export RQ_AUDIO_DELAY_MS" in block and "RQ_AUDIO_DELAY_MS=$(rq_audio_delay_ms)" in block
    env = open(os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")).read()
    assert "\nRQ_AUDIO_DELAY_MS=0\n" in env
    # kept on /data for both A/B slots, like the LED settings
    settings = open(os.path.join(_BIN, "rq_device_settings.sh")).read()
    assert "|RQ_AUDIO_DELAY_MS|" in settings
    assert "LED_*|RASQ_LED_*|RQ_AUDIO_DELAY_MS|" in common
    assert "LED_*|RASQ_LED_*|RQ_AUDIO_DELAY_MS|" in open(_MENU).read()


def test_audio_delay_is_in_desktop_settings():
    menu = open(_MENU).read()
    ds = menu[menu.index("do_desktop_settings_menu() {"):]
    ds = ds[:ds.index("\n}\n")]
    assert 'DELAY   "Sound delay (Bluetooth speaker): $(audio_delay_ms) ms"' in ds
    assert "DELAY)   do_audio_delay" in ds


def test_calibration_ticks_in_a_quickening_block():
    # 2.6 s in a loop: four ticks, each gap shorter (0.6, 0.45, 0.3 s), then
    # a pause, so only the right delay lines the rhythm up (Jan, 2026-10-13)
    code = (f"import sys; sys.path.insert(0, {_BIN!r}); import rq_audio_delay_calibrate as c; "
            "sys.stdout.buffer.write(c.tick())")
    proc = subprocess.run(["python3", "-c", code], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    import array
    data = array.array("h", proc.stdout)
    assert len(data) == int(48000 * 2.6)
    onsets = [int(48000 * t) for t in (0.0, 0.6, 1.05, 1.35)]
    gaps = [b - a for a, b in zip(onsets, onsets[1:])]
    assert gaps == sorted(gaps, reverse=True) and len(set(gaps)) == 3
    for start, end in zip(onsets, onsets[1:] + [len(data)]):
        assert max(abs(x) for x in data[start:start + 300]) > 10000
        assert max(abs(x) for x in data[start + 1500:end]) == 0


def test_calibration_runs_sandboxed_and_saves():
    sh = open(os.path.join(_BIN, "rq_audio_delay_calibrate.sh")).read()
    # the tick and flash run as the user in the LED sandbox, from the venv
    assert sh.index("activate_venv") < sh.index("rq_led_user_prepare") < sh.index("rq_led_as_user python3")
    assert "led_panel_ready || exit 0" in sh and "rq_led_clear_on_exit" in sh
    # root saves the checked value; an error leaves the setting as it was
    assert 'update_env_var RQ_AUDIO_DELAY_MS "$value"' in sh
    assert "value=$(rq_audio_delay_ms)" in sh
    assert "0|130) ;;" in sh
    menu = open(_MENU).read()
    fn = menu[menu.index("do_audio_delay() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert 'CAL "Calibrate: a tick and a flash' in fn
    assert '"$BIN_DIR/rq_audio_delay_calibrate.sh"' in fn


@pytest.mark.parametrize("rc, error", [(0, False), (130, False), (1, True)])
def test_calibration_stopped_with_ctrl_c_is_no_error_in_the_menu(tmp_path, rc, error):
    """Ctrl+C (exit 130) said "Cancelled", then the menu showed an error box (review C4)."""
    menu = open(_MENU).read()
    fn = menu[menu.index("do_audio_delay() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    (tmp_path / "rq_audio_delay_calibrate.sh").write_text(f"#!/bin/sh\nexit {rc}\n")
    (tmp_path / "rq_audio_delay_calibrate.sh").chmod(0o755)
    stubs = ('show_menu() { echo CAL; }\nclear() { :; }\n_rq_load_env() { :; }\n'
             'audio_delay_ms() { echo 0; }\nhandle_error() { echo "ERROR: $1"; }\n')
    proc = subprocess.run([shutil.which("dash") or "/bin/sh", "-c", stubs + fn + "do_audio_delay"],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          env=dict(os.environ, BIN_DIR=str(tmp_path)))
    assert proc.returncode == 0, proc.stderr
    assert ("ERROR: The sound delay could not be calibrated." in proc.stdout) == error


def test_calibration_removes_its_result_file_on_ctrl_c(tmp_path):
    """Ctrl+C ends the script through the INT trap, before its own clean-up."""
    import re
    sh = open(os.path.join(_BIN, "rq_audio_delay_calibrate.sh")).read()
    trap = re.search(r"^trap '.*' EXIT$", sh, re.M).group(0)
    marks = tmp_path / "marks"
    script = (f'. "{_COMMON}"\n'
              f'rq_led_release_panel() {{ echo release >> "{marks}"; }}\n'
              f'rq_led_stall_check() {{ echo check >> "{marks}"; }}\n'
              'rq_led_clear_on_exit\n'
              f'result=$(mktemp "{tmp_path}/rq-audio-delay.XXXXXX")\n'
              f'{trap}\n'
              'kill -INT $$\nsleep 5\n')
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 130, proc.stderr
    assert not list(tmp_path.glob("rq-audio-delay.*"))
    assert marks.read_text().split() == ["release", "check"]


def test_pi_is_not_a_bluetooth_speaker():
    # a speaker that can also send sound must connect as the speaker
    conf = open(os.path.join(os.path.dirname(_BIN), "RQB2-system", "etc", "wireplumber",
                             "wireplumber.conf.d", "51-rasqberry-bt-speaker.conf")).read()
    roles = conf[conf.index("bluez5.roles"):].split("]")[0]
    assert "a2dp_source" in roles and "a2dp_sink" not in roles
