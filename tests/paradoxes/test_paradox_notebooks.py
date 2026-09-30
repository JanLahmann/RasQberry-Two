#!/usr/bin/env python3
"""
Regression test for the Quantum Paradoxes notebooks (issue #181).

Fetches maria-violaris/quantum-paradoxes at the ref pinned in the demo
manifest, applies RQB2-bin/setup_quantum_paradoxes.py exactly as the installer
does, executes every notebook headless (scripted answers for the input()
prompts) and compares the EXACT outcome probabilities of every circuit sent to
a simulator with reference_probabilities.json.

The reference values were recorded from Maria Violaris' ORIGINAL notebooks
under the Qiskit of their era (0.39 for the 2022 notebooks, 0.45 for the
2023/24 ones) and match the patched notebooks under Qiskit 2.5.2 / Aer 0.17.2.

Run (needs qiskit, qiskit-aer, qiskit-ibm-runtime, nbclient, ipykernel,
matplotlib, pylatexenc, and network access or PARADOXES_SRC):

    python3 -m pytest -q tests/paradoxes

PARADOXES_SRC=/path/to/checkout   use an existing checkout of the pinned ref
PARADOX_UPDATE_REFERENCE=1        rewrite reference_probabilities.json

Skipped cleanly when the Qiskit/Jupyter stack or the sources are unavailable.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

for _mod in ("qiskit", "qiskit_aer", "qiskit_ibm_runtime", "nbclient", "nbformat",
             "ipykernel", "matplotlib"):
    if importlib.util.find_spec(_mod) is None:
        pytest.skip(f"{_mod} not installed - Quantum Paradoxes regression test skipped",
                    allow_module_level=True)

import nbformat  # noqa: E402
from nbclient import NotebookClient  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MANIFEST = os.path.join(_REPO_ROOT, "RQB2-config", "demo-manifests",
                         "rq_demo_quantum-paradoxes.json")
_REFERENCE = os.path.join(_HERE, "reference_probabilities.json")
_UPDATE = os.environ.get("PARADOX_UPDATE_REFERENCE") == "1"
_TOL = 1e-6

sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))
import setup_quantum_paradoxes  # noqa: E402

with open(_REFERENCE, encoding="utf-8") as _fh:
    _REF = json.load(_fh)
_CASES = sorted(k for k in _REF if not k.startswith("_"))


def _fetch_sources(dest):
    """Copy PARADOXES_SRC or fetch the pinned ref into dest; skip if impossible."""
    src = os.environ.get("PARADOXES_SRC")
    if src:
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
        return
    with open(_MANIFEST, encoding="utf-8") as fh:
        install = json.load(fh)["install"]
    if shutil.which("git") is None:
        pytest.skip("git not available and PARADOXES_SRC not set")
    try:
        os.makedirs(dest)
        for cmd in (["git", "init", "-q"],
                    ["git", "fetch", "-q", "--depth", "1", install["repo_url"], install["ref"]],
                    ["git", "checkout", "-q", "FETCH_HEAD"]):
            subprocess.run(cmd, cwd=dest, check=True, capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        pytest.skip(f"could not fetch quantum-paradoxes sources: {exc}")


@pytest.fixture(scope="module")
def patched_dir(tmp_path_factory):
    """quantum-paradoxes at the pinned ref, patched by the installer's setup script."""
    dest = str(tmp_path_factory.mktemp("paradoxes") / "quantum-paradoxes")
    _fetch_sources(dest)
    setup_quantum_paradoxes.setup_quantum_paradoxes(dest)
    return dest


def _execute(nb_dir, notebook, answers, out):
    """Execute one patched notebook with the recording harness; return records."""
    nb = nbformat.read(os.path.join(nb_dir, notebook), as_version=4)
    nb.cells.insert(0, nbformat.v4.new_code_cell(
        f"import sys; sys.path.insert(0, {_HERE!r})\n"
        f"import paradox_harness; paradox_harness.install({out!r}, {answers!r})"))
    os.environ["MPLBACKEND"] = "Agg"
    NotebookClient(nb, timeout=900, kernel_name="python3", allow_errors=True,
                   resources={"metadata": {"path": nb_dir}}).execute()
    errors = [f"{o['ename']}: {o['evalue'][:200]}" for c in nb.cells
              for o in c.get("outputs", []) if o.get("output_type") == "error"]
    if not os.path.exists(out):  # notebook never ran a circuit (e.g. EPR: drawings only)
        return [], errors
    with open(out, encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    return records, errors


def _same(a, b):
    return all(abs(a.get(k, 0.0) - b.get(k, 0.0)) < _TOL for k in set(a) | set(b))


@pytest.mark.parametrize("case", _CASES)
def test_notebook_matches_original(case, patched_dir, tmp_path):
    ref = _REF[case]
    records, errors = _execute(patched_dir, ref["notebook"], ref["answers"],
                               str(tmp_path / "record.jsonl"))
    assert not errors, f"{ref['notebook']} raised: {errors}"
    runs = [r for r in records if r["kind"] == "run"]

    if _UPDATE:
        old = ref.get("runs", [])
        ref["runs"] = []
        for i, run in enumerate(runs):
            entry = {"exact": run["exact"]}
            if i < len(old) and old[i].get("patched_only"):
                entry["patched_only"] = True  # fake-backend noise: not pinned
            elif run["noisy"]:
                entry["exact_noisy"] = run["exact_noisy"]
            ref["runs"].append(entry)
        with open(_REFERENCE, "w", encoding="utf-8") as fh:
            json.dump(_REF, fh, indent=1, sort_keys=True)
            fh.write("\n")
        return

    expected = ref["runs"]
    assert len(runs) == len(expected), (
        f"{case}: notebook sent {len(runs)} circuits to a simulator, expected {len(expected)}")
    for i, (got, want) in enumerate(zip(runs, expected)):
        assert _same(got["exact"], want["exact"]), (
            f"{case} run {i}: noiseless probabilities {got['exact']} != {want['exact']}")
        if "exact_noisy" in want:
            assert got["noisy"], f"{case} run {i}: expected a noisy simulator"
            assert _same(got["exact_noisy"], want["exact_noisy"]), (
                f"{case} run {i}: noisy probabilities {got['exact_noisy']} "
                f"!= {want['exact_noisy']}")
