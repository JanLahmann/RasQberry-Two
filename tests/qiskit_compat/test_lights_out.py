"""
Quantum Lights Out under the installed Qiskit, without LED hardware.

Fetches Luka-D/Quantum-Lights-Out at the ref pinned in its manifest, applies
RQB2-config/demo-patches/quantum-lights-out.patch the way rq_demo_run.sh does,
and runs the demo's Grover solver on every built-in puzzle. Each answer is then
played through the demo's own console + LED visualisation (LEDs: the virtual
mmap writer) and the board must end up dark - so a Qiskit change that makes the
solver return wrong answers fails here, not only one that raises.

QLO_SRC=/path/to/checkout   use an existing checkout of the pinned ref
"""

import argparse
import importlib
import sys
import types

import pytest

import compat_helpers as h

h.require("qiskit", "qiskit_aer", "dotenv")


@pytest.fixture(scope="module")
def qlo_dir(tmp_path_factory):
    dest = str(tmp_path_factory.mktemp("qlo") / "Quantum-Lights-Out")
    install = h.fetch_pinned("rq_demo_quantum-lights-out.json", dest, src_env="QLO_SRC")
    h.apply_demo_patch(dest, install["patch_file"])
    return dest


@pytest.fixture
def lights_out(qlo_dir, led_env, monkeypatch):
    # The patched script imports board/neopixel at the top (unused once LEDs go
    # through rq_led_utils); on a non-Pi they cannot be imported at all.
    for name in ("board", "neopixel"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.syspath_prepend(qlo_dir)
    for name in ("lights_out", "turn_off_LEDs"):
        sys.modules.pop(name, None)
    module = importlib.import_module("lights_out")
    yield module
    for name in ("lights_out", "turn_off_LEDs"):
        sys.modules.pop(name, None)


def test_solver_solves_every_builtin_puzzle(lights_out, led_env, capsys):
    import rq_led_utils
    config = rq_led_utils.get_led_config()
    indices = lights_out.generate_led_indices()
    pixels = rq_led_utils.create_neopixel_strip(config["led_count"], config["pixel_order"],
                                                brightness=0.5)
    args = argparse.Namespace(console=True, delay=0.0, brightness=0.5)

    for number, puzzle in enumerate(lights_out.lights):
        grid = list(puzzle)
        solution = lights_out.compute_quantum_solution(grid)
        assert len(solution) == 9 and set(solution) <= {"0", "1"}, solution
        lights_out.visualize_solution(grid, solution, args, pixels, indices)
        assert grid == [0] * 9, f"puzzle {number} {puzzle}: solution {solution} leaves {grid}"

    assert "□" in capsys.readouterr().out  # the console view was drawn
    assert led_env.mmap.exists() and led_env.mmap.stat().st_size > 0
