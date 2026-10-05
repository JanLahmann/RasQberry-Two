"""
RasQ-LED keeps one LED driver open for the whole run (#5).

Every cycle used to start RasQ-LED-display.py as a program of its own, so the
Pi 5's LED driver was opened and closed every few seconds, and the final clear
was killed by a 3 s timeout in the middle of a frame. Qiskit is stubbed here
(the real circuits are tested in tests/qiskit_compat/test_rasq_led.py).
"""

import importlib.util
import os
import subprocess
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")


class _Strip:
    """A recording LED strip."""

    def __init__(self, n):
        self.pixels = [(0, 0, 0)] * n
        self.shows = 0

    def __len__(self):
        return len(self.pixels)

    def __setitem__(self, i, colour):
        self.pixels[i] = colour

    def fill(self, colour):
        self.pixels = [colour] * len(self.pixels)

    def show(self):
        self.shows += 1

    def deinit(self):
        self.released = True


def _qiskit_stubs(monkeypatch, bits):
    """Just enough of qiskit / qiskit_aer / dotenv for RasQ-LED.py to import."""
    class QuantumCircuit:
        def __init__(self, *_):
            pass

        def h(self, *_):
            pass

        def cx(self, *_):
            pass

        def measure(self, *_):
            pass

    class AerSimulator:
        def run(self, *_a, **_k):
            return types.SimpleNamespace(result=lambda: types.SimpleNamespace(
                get_counts=lambda: {bits: 1}))

    qiskit = types.ModuleType("qiskit")
    qiskit.QuantumCircuit = QuantumCircuit
    aer = types.ModuleType("qiskit_aer")
    aer.AerSimulator = AerSimulator
    providers = types.ModuleType("qiskit.providers")
    dotenv = types.ModuleType("dotenv")
    dotenv.dotenv_values = lambda *_: {"RASQ_LED_DISPLAY_TIMEOUT": "0"}
    for name, mod in (("qiskit", qiskit), ("qiskit_aer", aer), ("qiskit.providers", providers),
                      ("dotenv", dotenv)):
        monkeypatch.setitem(sys.modules, name, mod)


@pytest.fixture
def rasq(monkeypatch):
    monkeypatch.syspath_prepend(_BIN)
    import rq_led_utils
    monkeypatch.setattr(rq_led_utils, "ENV_FILE", _ENV)
    n = rq_led_utils.get_led_config()["n_qubit"]
    _qiskit_stubs(monkeypatch, "01" * (n // 2))
    opened = []

    def create(count, order, brightness=0.1, gpio_pin=None):
        opened.append(_Strip(count))
        return opened[-1]
    monkeypatch.setattr(rq_led_utils, "create_neopixel_strip", create)
    spec = importlib.util.spec_from_file_location("rasq_led_t", os.path.join(_BIN, "RasQ-LED.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.display_timeout = 0
    mod.opened = opened
    return mod


def test_one_driver_for_all_cycles(rasq, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("no display program per cycle"))
    for factor in (1, 2, rasq.n_qbit):
        assert rasq.run_circuit(factor)
    assert len(rasq.opened) == 1                       # opened once, not per cycle
    strip = rasq.opened[0]
    assert strip.shows > 3
    assert set(strip.pixels) == {(0, 0, 0)}            # each cycle ends cleared
    rasq.clear_leds()
    assert len(rasq.opened) == 1


def test_clear_without_a_panel_opens_nothing(rasq):
    rasq.clear_leds()
    assert rasq.opened == []


def test_a_panel_that_cannot_open_skips_the_cycle(rasq, monkeypatch, capsys):
    import rq_led_utils

    def broken(*_a, **_k):
        raise RuntimeError("GPIO busy")
    monkeypatch.setattr(rq_led_utils, "create_neopixel_strip", broken)
    assert rasq.call_display_on_strip("0101") is False
    assert "GPIO busy" in capsys.readouterr().out


def test_a_stop_signal_clears_the_panel():
    """SIGTERM (the menu, the demo loop) ends RasQ-LED like Ctrl+C: through
    its finally clause, which clears the panel."""
    text = open(os.path.join(_BIN, "RasQ-LED.py"), encoding="utf-8").read()
    assert "signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))" in text
    main = text[text.index("def main():"):]
    assert main.index("signal.SIGTERM") < main.index("demo_loop(")
    loop = text[text.index("def demo_loop("):text.index("def main():")]
    assert "finally:\n        release_leds()" in loop


def test_the_panel_is_released_before_the_program_ends(rasq):
    """Cleared and released by the demo itself, not by the strip's destructor
    at Python's shutdown, which printed a traceback at every end (#8)."""
    assert rasq.run_circuit(1)
    strip = rasq.opened[0]
    strip.fill((255, 0, 0))
    rasq.release_leds()
    assert set(strip.pixels) == {(0, 0, 0)} and strip.released
    assert rasq._pixels is None
    rasq.release_leds()                                # nothing left: no error


def test_demo_runs_until_stopped(rasq, monkeypatch, capsys):
    """For a stand, RasQ-LED goes on until it is stopped (#21): no more
    "Demo complete" after two cycles. Here Ctrl+C comes in the fifth cycle."""
    per_cycle = len(rasq.get_factors(rasq.n_qbit))
    runs = []

    def run(factor):
        runs.append(factor)
        if len(runs) > 4 * per_cycle:
            raise KeyboardInterrupt
        return True
    monkeypatch.setattr(rasq, "run_circuit", run)
    monkeypatch.setattr(rasq.time, "sleep", lambda *_: None)
    rasq.demo_loop()
    out = capsys.readouterr().out
    assert "--- Demo Cycle 5 ---" in out and "Demo complete" not in out
    assert "/2" not in out


def test_a_fixed_number_of_cycles_still_ends(rasq, monkeypatch, capsys):
    monkeypatch.setattr(rasq, "run_circuit", lambda factor: True)
    monkeypatch.setattr(rasq.time, "sleep", lambda *_: None)
    rasq.demo_loop(1)
    assert "Demo complete!" in capsys.readouterr().out


def test_main_runs_until_stopped():
    text = open(os.path.join(_BIN, "RasQ-LED.py"), encoding="utf-8").read()
    main = text[text.index("def main():"):]
    assert "demo_loop()" in main
