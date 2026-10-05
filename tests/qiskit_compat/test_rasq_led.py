"""
RasQ-LED (RQB2-bin/RasQ-LED.py) under the installed Qiskit, without LEDs.

Builds and runs every entanglement pattern the demo loop shows and checks the
physics (inside each entangled block all qubits agree), then runs one full
cycle through the display functions of RasQ-LED-display.py (in-process, on
one strip for the whole run) with frames going to a temp mmap file.
"""

import importlib.util
import os

import pytest

import compat_helpers as h

h.require("qiskit", "qiskit_aer", "dotenv")


@pytest.fixture
def rasq_led(led_env):
    spec = importlib.util.spec_from_file_location("rasq_led", os.path.join(h.BIN_DIR, "RasQ-LED.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_entanglement_pattern(rasq_led):
    n = rasq_led.n_qbit
    assert n == rasq_led.led_config["n_qubit"] > 0
    factors = rasq_led.get_factors(n)
    assert factors[0] == 1 and factors[-1] == n
    for factor in factors:
        rasq_led.set_up_circuit(factor)
        assert rasq_led.circ_execute(), f"circuit with block size {factor} failed"
        bits = rasq_led.measurement[::-1]  # qubit 0 first
        assert len(bits) == n and set(bits) <= {"0", "1"}
        for start in range(0, n, factor):
            block = bits[start:start + factor]
            assert len(set(block)) == 1, f"block size {factor}: entangled block {block} disagrees"


def test_display_cycle_through_virtual_leds(rasq_led, led_env):
    """run_circuit() end to end: simulate, then the display functions write the frame."""
    rasq_led.display_timeout = 1
    assert rasq_led.run_circuit(rasq_led.n_qbit)
    assert led_env.mmap.exists() and led_env.mmap.stat().st_size > 0
