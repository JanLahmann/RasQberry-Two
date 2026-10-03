"""
Running a credentials notebook unedited must never replace the IBM Quantum
account saved on the Pi.

The rig harness ran cell 1 of RQB2-config/00-Save-Credentials.ipynb as it
ships: it saved the placeholder "<your-api-key>" over the real API key in
~/.qiskit/qiskit-ibm.json (on /data, so both slots lost it). Any learner who
presses Run All does the same. These tests run the save cells with a fake
QiskitRuntimeService - no Qiskit, no network, no ~/.qiskit - and check that the
rig harness (tests/rig/pi/webcheck.py) never picks a credential cell to run.
"""

import importlib.util
import io
import json
import os
import re
import sys
import types
from contextlib import redirect_stdout

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_CFG = os.path.join(_ROOT, "RQB2-config")
_CREDENTIALS_NB = os.path.join(_CFG, "00-Save-Credentials.ipynb")
_WEBCHECK = os.path.join(_ROOT, "tests", "rig", "pi", "webcheck.py")

DUMMY_KEY = "dummy-key-for-tests-0123456789abcdefghijklmn"   # not a real key


def _cells(path):
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)
    return [("".join(c["source"]) if isinstance(c["source"], list) else c["source"], c["cell_type"])
            for c in nb["cells"]]


def _shipped_notebooks():
    out = []
    for folder, _, files in os.walk(_CFG):
        out += [os.path.join(folder, f) for f in files if f.endswith(".ipynb")]
    return sorted(out)


class FakeService:
    """Stands in for qiskit_ibm_runtime.QiskitRuntimeService (class methods only)."""

    accounts = {}
    saved = []

    @classmethod
    def saved_accounts(cls, **kwargs):
        return dict(cls.accounts)

    @classmethod
    def save_account(cls, **kwargs):
        cls.saved.append(kwargs)

    @classmethod
    def delete_account(cls, **kwargs):
        raise AssertionError("a save cell must never delete an account")


@pytest.fixture
def fake_runtime(monkeypatch):
    module = types.ModuleType("qiskit_ibm_runtime")
    module.QiskitRuntimeService = FakeService
    monkeypatch.setitem(sys.modules, "qiskit_ibm_runtime", module)
    FakeService.accounts, FakeService.saved = {}, []
    return FakeService


def _run(src, token=None):
    """Run a cell's source, with the token line set to `token` (None: unedited)."""
    if token is not None:
        src, n = re.subn(r'^token = .*$', f"token = {token!r}", src, flags=re.M)
        assert n == 1, "the cell has one token line"
    out = io.StringIO()
    with redirect_stdout(out):
        exec(compile(src, "save-cell", "exec"), {})
    return out.getvalue()


def _cell1():
    src, kind = _cells(_CREDENTIALS_NB)[1]
    assert kind == "code" and "save_account(" in src
    return src


@pytest.mark.parametrize("token", [None, "", "   ", "your-api-key", "<paste your key here>"])
def test_unedited_cell_changes_nothing(fake_runtime, token):
    out = _run(_cell1(), token)
    assert fake_runtime.saved == [], "the placeholder must never be saved"
    assert "NOT changed" in out and "token line" in out and "quantum.cloud.ibm.com" in out
    assert "already saved" not in out


def test_unedited_cell_tells_about_the_saved_account(fake_runtime):
    fake_runtime.accounts = {"default-ibm-quantum-platform": {"channel": "ibm_quantum_platform"}}
    out = _run(_cell1())
    assert fake_runtime.saved == []
    assert "NOT changed" in out and "already saved" in out and "replaces it" in out


@pytest.mark.parametrize("already", [False, True])
def test_real_key_is_saved_and_replaces(fake_runtime, already):
    if already:
        fake_runtime.accounts = {"default-ibm-quantum-platform": {"channel": "ibm_quantum_platform"}}
    out = _run(_cell1(), DUMMY_KEY)
    assert fake_runtime.saved == [{"channel": "ibm_quantum_platform", "token": DUMMY_KEY, "instance": None,
                                   "set_as_default": True, "overwrite": True}]
    assert out.startswith("Saved.")
    assert ("replaces the account saved before" in out) == already


def test_delete_cell_is_explained():
    cells = _cells(_CREDENTIALS_NB)
    i = next(i for i, (src, kind) in enumerate(cells) if kind == "code" and "delete_account(" in src)
    before, kind = cells[i - 1]
    assert kind == "markdown" and "removes your saved API key" in before


@pytest.mark.parametrize("path", _shipped_notebooks(), ids=os.path.basename)
def test_every_shipped_save_cell_refuses_the_placeholders(fake_runtime, path):
    # Hello-World.ipynb (doQumentation's, with our edit) and the credentials notebook
    saves = [src for src, kind in _cells(path) if kind == "code" and "save_account(" in src]
    for src in saves:
        _run(src)
        assert fake_runtime.saved == [], f"{os.path.basename(path)} saves its placeholders"


# --- the rig harness never runs credential code ---------------------------------

@pytest.fixture
def webcheck(monkeypatch):
    monkeypatch.setitem(sys.modules, "websocket", types.ModuleType("websocket"))
    spec = importlib.util.spec_from_file_location("rig_webcheck", _WEBCHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harness_skips_credential_notebooks(webcheck):
    for name in ("00-Save-Credentials.ipynb", "My-Account.ipynb", "set_token.ipynb", "API-Key.ipynb"):
        assert webcheck.CREDENTIAL_NOTEBOOK.search(name), name
    for name in ("Hello-World.ipynb", "Quantum-Coin-Game.ipynb", "WELCOME-tutorials.ipynb", "3sat.ipynb"):
        assert not webcheck.CREDENTIAL_NOTEBOOK.search(name), name


@pytest.mark.parametrize("src", [
    'QiskitRuntimeService.save_account(channel="ibm_quantum_platform", token="x")',
    'QiskitRuntimeService.delete_account(channel="ibm_quantum_platform")',
    "print(QiskitRuntimeService.saved_accounts())",
    'service = QiskitRuntimeService(channel="ibm_quantum_platform", token="x")',
    'my_token = "abc"',
    'os.environ["QISKIT_IBM_TOKEN"] = "x"',
    'api_key = "x"',
    'open(os.path.expanduser("~/.qiskit/qiskit-ibm.json"), "w")',
    'Path.home() / ".qiskit"',
])
def test_harness_skips_credential_cells(webcheck, src):
    nb = {"cells": [{"cell_type": "code", "source": src},
                    {"cell_type": "code", "source": "from qiskit import QuantumCircuit\nqc = QuantumCircuit(2)"}]}
    assert webcheck.first_code_cell(nb) == (1, nb["cells"][1]["source"], 1)


def test_harness_keeps_ordinary_cells(webcheck):
    for src in ("from qiskit import QuantumCircuit", "if token == expected:\n    pass",
                "max_tokens = 5", "import qiskit.circuit", "service = QiskitRuntimeService()"):
        nb = {"cells": [{"cell_type": "code", "source": src}]}
        assert webcheck.first_code_cell(nb)[0] == 0, src


@pytest.mark.parametrize("path", _shipped_notebooks(), ids=os.path.basename)
def test_harness_never_picks_a_shipped_credential_cell(webcheck, path):
    with open(path, encoding="utf-8") as fh:
        nb = json.load(fh)
    index, src, _ = webcheck.first_code_cell(nb)
    assert index is None or ("save_account" not in src and "delete_account" not in src)
    if os.path.basename(path) == "00-Save-Credentials.ipynb":
        assert webcheck.CREDENTIAL_NOTEBOOK.search(os.path.basename(path))
