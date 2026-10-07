"""
Tests for the Trixie polish of 2026-10-07.

- The boot address scroll (rasqberry-ip-display.service) ended "failed" when
  the LED busy dialog's "Stop It" stopped it: a oneshot unit counts SIGTERM
  as a failure, and the script died of the signal, its last frame frozen.
- Quantum Raspberry Tie on the Pi 5: frames written back to back ran
  together (kernel 6.18 PIO), see test_qrt_pi5_pacing below.
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
