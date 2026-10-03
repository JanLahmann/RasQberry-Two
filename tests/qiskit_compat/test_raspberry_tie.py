"""
Quantum Raspberry Tie under the installed Qiskit, on its local simulators.

Fetches KPRoche/quantum-raspberry-tie at the ref pinned in its manifest, applies
RQB2-config/demo-patches/quantum-raspberry-tie.patch the way rq_demo_run.sh does,
and runs QuantumRaspberryTie.v8_0.py headless until its first job result:

- the script disables the Sense HAT and NeoPixels itself when the machine is
  not aarch64; on an aarch64 runner LED_RENDER_MODE=service keeps it off GPIO
  as far as rq_led_utils is concerned, and -faux selects the bundled no-GUI
  Sense HAT stand-in (sense_faux) instead of the GTK emulator;
- only local backends are used (Aer, Aer MPS, FakeManilaV2 via SamplerV2) -
  the real-backend variant needs an IBM Quantum account and the network.

The demo loops forever, so each run is stopped once it printed a result. It
also silences DeprecationWarning right after its imports ("temporary because
the libraries are changing again"); a small wrapper keeps that filter from
being installed, so the deprecations of the calls it makes (transpile,
SamplerV2, ...) reach the report.

QRT_SRC=/path/to/checkout   use an existing checkout of the pinned ref
"""

import json
import os
import subprocess
import time

import pytest

import compat_helpers as h

h.require("qiskit", "qiskit_aer", "qiskit_ibm_runtime", "psutil", "requests", "PIL")

MANIFEST = "rq_demo_quantum-raspberry-tie.json"
RESULT = "Maximum pattern:"
TIMEOUT = 300

_WRAPPER = r'''
import os, runpy, sys, warnings
_filterwarnings = warnings.filterwarnings

def _keep_deprecations(action, *args, **kwargs):
    category = kwargs.get("category", args[1] if len(args) > 1 else Warning)
    if action == "ignore" and issubclass(DeprecationWarning, category):
        return None
    return _filterwarnings(action, *args, **kwargs)

warnings.filterwarnings = _keep_deprecations
sys.argv = sys.argv[1:]
sys.path[0] = os.path.dirname(os.path.abspath(sys.argv[0]))  # as if run directly
runpy.run_path(sys.argv[0], run_name="__main__")
'''


def _variant_args(variant_id):
    with open(os.path.join(h.MANIFEST_DIR, MANIFEST), encoding="utf-8") as fh:
        variants = {v["id"]: v for v in json.load(fh)["variants"]}
    return variants[variant_id].get("args", [])


@pytest.fixture(scope="module")
def qrt_dir(tmp_path_factory):
    dest = str(tmp_path_factory.mktemp("qrt") / "quantum-raspberry-tie")
    install = h.fetch_pinned(MANIFEST, dest, src_env="QRT_SRC")
    h.apply_demo_patch(dest, install["patch_file"])
    return dest


def _run_until_result(qrt_dir, tmp_path, args):
    script = json.load(open(os.path.join(h.MANIFEST_DIR, MANIFEST), encoding="utf-8"))["entrypoint"]["script"]
    out_path, err_path = tmp_path / "stdout.txt", tmp_path / "stderr.txt"
    wrapper = tmp_path / "keep_deprecations.py"
    wrapper.write_text(_WRAPPER)
    env = h.subprocess_env(HOME=str(tmp_path), RQB2_LED_MMAP_PATH=str(tmp_path / "leds.mmap"))
    with open(out_path, "w") as out, open(err_path, "w") as err:
        proc = subprocess.Popen([h.PYTHON, str(wrapper), script, *args], cwd=qrt_dir, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL, env=env)
        deadline = time.monotonic() + TIMEOUT
        try:
            while proc.poll() is None and time.monotonic() < deadline:
                if RESULT in out_path.read_text(errors="replace"):
                    break
                time.sleep(1)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    stdout, stderr = out_path.read_text(errors="replace"), err_path.read_text(errors="replace")
    h.record_subprocess_warnings(f"QuantumRaspberryTie {' '.join(args)}", stderr)
    return stdout, stderr


@pytest.mark.parametrize("label,args", [
    ("menu-simulator-variant", _variant_args("simulator") + ["-faux"]),
    ("noise-fake-manila", ["-faux", "-nois"]),
    ("16-qubit-aer-mps", ["-faux", "-16"]),
])
def test_local_simulator_run(qrt_dir, tmp_path, label, args):
    stdout, stderr = _run_until_result(qrt_dir, tmp_path, args)
    tail = f"--- stdout ---\n{stdout[-3000:]}\n--- stderr ---\n{stderr[-3000:]}"
    assert "problem transpiling circuit" not in stdout, tail
    assert "Traceback" not in stderr, tail
    assert RESULT in stdout, f"{label}: no job result within {TIMEOUT}s\n{tail}"
    assert "instantiating faux" in stdout or "SenseHat emu GUI found" in stdout, tail
