"""
Tests for the Trixie polish of 2026-10-07.

- The boot address scroll (rasqberry-ip-display.service) ended "failed" when
  the LED busy dialog's "Stop It" stopped it: a oneshot unit counts SIGTERM
  as a failure, and the script died of the signal, its last frame frozen.
- Quantum Raspberry Tie on the Pi 5: frames written back to back ran
  together (kernel 6.18 PIO): its patch had no Pi 5 frame pacing.
"""

import os
import signal
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
sys.path.insert(0, _BIN)


def _read(*parts):
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# --- the boot address scroll stops cleanly ------------------------------------------

def test_the_ip_display_unit_counts_a_stop_as_success():
    unit = _read("RQB2-system", "etc", "systemd", "system", "rasqberry-ip-display.service")
    assert "Type=oneshot" in unit
    assert "SuccessExitStatus=SIGTERM" in unit


class _Strip:
    def __init__(self):
        self.frames = []
        self.colour = None

    def fill(self, colour):
        self.colour = colour

    def show(self):
        self.frames.append(self.colour)


def _display_ip():
    import importlib
    try:
        return importlib.import_module("rq_display_ip")
    except Exception as exc:  # pragma: no cover - LED libraries missing
        pytest.skip(f"rq_display_ip not importable: {exc}")


def test_a_stopped_ip_display_exits_0_with_the_panel_dark(monkeypatch):
    ip = _display_ip()
    strip = _Strip()
    monkeypatch.setattr(ip, "get_led_config", lambda: {"led_count": 192, "pixel_order": "GRB",
                                                       "led_layout": "single-24x8"})
    monkeypatch.setattr(ip, "get_ip_addresses", lambda: ["10.0.0.2"])
    monkeypatch.setattr(ip, "record_shown", lambda addresses: None)
    monkeypatch.setattr(ip, "get_network_name", lambda: "rasq")
    monkeypatch.setattr(ip, "create_neopixel_strip", lambda *a, **k: strip)

    def stopped(*args, **kwargs):           # SIGTERM arrives during the scroll
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

    monkeypatch.setattr(ip, "scroll_text", stopped)
    monkeypatch.setattr(sys, "argv", ["rq_display_ip.py", "--duration", "60"])
    old = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit) as stop:
            ip.main()
    finally:
        signal.signal(signal.SIGTERM, old)
    assert stop.value.code == 0
    assert strip.frames == [(0, 0, 0)]


# --- Quantum Raspberry Tie paces its frames on the Pi 5 -----------------------------

def _qrt_added_lines():
    patch = _read("RQB2-config", "demo-patches", "quantum-raspberry-tie.patch")
    return "\n".join(line[1:] for line in patch.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def test_qrt_pi5_pacing():
    # Raspberry Tie opens the panel itself (neopixel.NeoPixel), not through
    # create_neopixel_strip, so it lacked the Pi 5 guard: on kernel 6.18 a
    # frame written right after another one was lost (rig: QRT-style frames
    # back to back left the panel dark; with the guard all of it lit)
    added = _qrt_added_lines()
    guard = added.index("guard_pi5_led_writes()")
    assert guard < added.index("neopixel_array = neopixel.NeoPixel(")
    # its Ctrl+C handler ends with os._exit, past the exit handlers: the black
    # frame must go out first
    stop = added[added.index("def _rq_stop"):added.index("_rq_signal.signal(")]
    assert stop.index("neopixel_array.show()") < stop.index("_wait_for_last_frame()") \
        < stop.index("os._exit(130)")


def test_the_qrt_guard_names_exist_in_rq_led_utils():
    utils = _read("RQB2-bin", "rq_led_utils.py")
    assert "\ndef guard_pi5_led_writes(" in utils
    assert "\ndef _wait_for_last_frame(" in utils
