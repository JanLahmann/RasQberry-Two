"""
rq_set_qiskit_ibm_token.py (menu: IBM Quantum account > Save an API key) under
the installed qiskit-ibm-runtime - offline, with a dummy key and a temporary
HOME. The network is blocked, so the script takes its "cannot be reached"
path: it saves only when told to save without checking.
"""

import json
import os
import subprocess

import compat_helpers as h

h.require("qiskit_ibm_runtime")

TOKEN = "dummy-token-for-ci-0123456789"

_WRAPPER = r'''
import builtins, getpass, runpy, socket, sys

def _no_network(*args, **kwargs):
    raise OSError("network disabled in this test")
socket.socket.connect = _no_network
socket.create_connection = _no_network

answers = iter(sys.argv[3:])
builtins.input = lambda prompt="": next(answers)
_key = sys.argv[2]
getpass.getpass = lambda prompt="", stream=None: _key

from qiskit_ibm_runtime import QiskitRuntimeService
_real_init = QiskitRuntimeService.__init__

def _init(self, *args, **kwargs):
    saved = QiskitRuntimeService.saved_accounts(default=True)
    if not saved:
        return _real_init(self, *args, **kwargs)
    self._offline_account = next(iter(saved.values()))
    print("OFFLINE-SERVICE", self._offline_account["channel"])

QiskitRuntimeService.__init__ = _init
QiskitRuntimeService.active_account = lambda self: self._offline_account
script = sys.argv[1]
sys.argv = [script]   # the script parses its own options
runpy.run_path(script, run_name="__main__")
'''


def _run(tmp_path, *answers):
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(_WRAPPER)
    proc = subprocess.run(
        [h.PYTHON, str(wrapper), os.path.join(h.BIN_DIR, "rq_set_qiskit_ibm_token.py"), TOKEN, *answers],
        capture_output=True, text=True, timeout=300,
        env=h.subprocess_env(HOME=str(tmp_path), QISKIT_IBM_TOKEN="", QISKIT_IBM_CHANNEL=""))
    h.record_subprocess_warnings("rq_set_qiskit_ibm_token.py", proc.stderr)
    return proc


def _saved(tmp_path):
    with open(tmp_path / ".qiskit" / "qiskit-ibm.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_offline_save_without_check(tmp_path):
    # answers: instance CRN (Enter = none), "save without checking?" -> y
    proc = _run(tmp_path, "", "y")
    assert proc.returncode == 0, f"token script failed:\n{proc.stdout}\n{proc.stderr[-4000:]}"
    accounts = _saved(tmp_path)
    default = [a for a in accounts.values() if a.get("is_default_account")]
    assert len(default) == 1 and default[0]["token"] == TOKEN, accounts
    assert default[0]["channel"] == "ibm_quantum_platform"
    # the saved account must be one the installed runtime accepts back
    from qiskit_ibm_runtime import QiskitRuntimeService
    listed = QiskitRuntimeService.saved_accounts(filename=str(tmp_path / ".qiskit" / "qiskit-ibm.json"))
    assert any(a["token"] == TOKEN for a in listed.values())


def test_offline_declined_saves_nothing(tmp_path):
    proc = _run(tmp_path, "", "n")
    assert proc.returncode == 2, proc.stdout
    assert not (tmp_path / ".qiskit" / "qiskit-ibm.json").exists()


def test_check_without_account(tmp_path):
    proc = subprocess.run(
        [h.PYTHON, os.path.join(h.BIN_DIR, "rq_set_qiskit_ibm_token.py"), "--check"],
        capture_output=True, text=True, timeout=300,
        env=h.subprocess_env(HOME=str(tmp_path), QISKIT_IBM_TOKEN="", QISKIT_IBM_CHANNEL=""))
    assert proc.returncode == 1 and "No IBM Quantum account" in proc.stdout, proc.stdout
