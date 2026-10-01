"""
Quantum Fractals (RQB2-bin/fractal_files) under the installed Qiskit, headless.

The circuit/statevector part and the Bloch-sphere plot are checked in-process;
then fractals.py itself runs end to end for a few frames with matplotlib's Agg
backend and a stand-in for its Chrome window (fractal_webclient), which is the
only part that needs a display.
"""

import os
import re
import shutil
import subprocess

import numpy as np
import pytest

import compat_helpers as h

h.require("qiskit", "matplotlib", "selenium", "celluloid", "PIL")

FRACTAL_DIR = os.path.join(h.BIN_DIR, "fractal_files")
FRAMES = 3

# Replaces fractal_webclient.py: a driver that loads nothing and reports its
# window closed when the demo starts polling it, so fractals.py exits.
_FAKE_WEBCLIENT = '''
from selenium.common.exceptions import NoSuchWindowException

class _Driver:
    def get(self, url):
        pass
    def quit(self):
        pass
    def find_element(self, *args):
        raise NoSuchWindowException("headless test: no browser window")

class WebClient:
    def __init__(self, default_image_url):
        pass
    def get_driver(self):
        return _Driver()
'''


@pytest.fixture
def fractal_modules(monkeypatch):
    monkeypatch.syspath_prepend(FRACTAL_DIR)
    import fractal_quantum_circuit
    import fractal_julia_calculations
    return fractal_quantum_circuit, fractal_julia_calculations


def test_statevector_per_frame(fractal_modules):
    circuit_mod, _ = fractal_modules
    qfc = circuit_mod.QuantumFractalCircuit(number_of_qubits=1, number_of_frames=4)
    # H then Rz(phi): amplitudes e^{-i phi/2}/sqrt2, e^{i phi/2}/sqrt2 -> ratio e^{-i phi}
    for frame in range(4):
        ratio, circ, sv = qfc.get_quantum_circuit(frame_iteration=frame)
        phi = frame * 2 * np.pi / 4
        assert circ.num_qubits == 1
        assert np.allclose(np.abs(sv) ** 2, [0.5, 0.5], atol=1e-6)
        assert abs(complex(ratio) - complex(round(np.cos(phi), 2), round(-np.sin(phi), 2))) < 1e-6


def test_julia_and_bloch_plot(fractal_modules):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from qiskit.visualization import plot_bloch_multivector
    circuit_mod, julia_mod = fractal_modules
    ratio, circ, sv = circuit_mod.QuantumFractalCircuit(1, 60).get_quantum_circuit(7)
    z = (np.linspace(-1.5, 1.5, 40).reshape(1, 40)
         + 1j * np.linspace(-1.5, 1.5, 40).reshape(40, 1)).astype(np.complex64)
    julia = julia_mod.JuliaSet(sv_custom=ratio, sv_list=sv, z=z,
                               con=np.full(z.shape, True), div=np.zeros(z.shape, dtype=np.uint8))
    julia.set_1cn()
    julia.set_2cn1()
    julia.set_2cn2()
    assert julia.res_1cn.shape == julia.res_2cn1.shape == julia.res_2cn2.shape == z.shape
    fig = plot_bloch_multivector(circ)
    assert fig.axes
    plt.close("all")


def test_fractals_demo_runs_headless(tmp_path):
    """fractals.py end to end for a few frames: images, Bloch plots and the GIF."""
    work = tmp_path / "fractal_files"
    shutil.copytree(FRACTAL_DIR, work)
    (work / "fractal_webclient.py").write_text(_FAKE_WEBCLIENT)
    script = work / "fractals.py"
    source, count = re.subn(r"^number_of_frames: int = \d+", f"number_of_frames: int = {FRAMES}",
                            script.read_text(), flags=re.M)
    assert count == 1, "fractals.py no longer defines 'number_of_frames: int = N' - update this test"
    script.write_text(source)

    tmp = tmp_path / "tmp"
    tmp.mkdir()
    proc = subprocess.run([h.PYTHON, "fractals.py"], cwd=work, capture_output=True, text=True,
                          timeout=600, env=h.subprocess_env(TMPDIR=str(tmp)))
    h.record_subprocess_warnings("fractals.py", proc.stderr)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"fractals.py failed:\n{out[-4000:]}"
    assert f"Loop i = {FRAMES - 1:>2}" in proc.stdout, out[-4000:]
    images = tmp / "rasqberry-fractals-img"
    assert (images / "2cn2.png").stat().st_size > 0
    assert (images / f"1qubit_simulator_4animations_H_{FRAMES}.gif").stat().st_size > 0
