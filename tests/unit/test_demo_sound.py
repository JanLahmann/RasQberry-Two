"""
Sound for LED demos (QEC demo review, Jan 2026-10-12): a Pi 4's headphone
jack shares the PWM hardware with the LED panel, so the launcher warns; and an
LED demo that plays sound runs as the desktop user (root cannot reach the
user's PipeWire), with the LED renderer doing the root part on a Pi 4.
"""

import os
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
    for prop in ("NoNewPrivileges=yes", "ProtectSystem=strict", "CapabilityBoundingSet=",
                 "/run/docker.sock", "RestrictSUIDSGID=yes", "/venv", ".local/config", ".bashrc"):
        assert prop in fn, prop
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
    assert clean.index("rq_led_renderer_stop") < clean.index("led_clear_quietly")
    common = open(_COMMON).read()
    on_exit = common[common.index("_rq_led_on_exit() {"):]
    assert on_exit.index("rq_led_renderer_stop") < on_exit.index("led_clear_quietly")
