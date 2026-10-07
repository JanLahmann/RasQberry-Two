"""
Tests for the Qoffee-Maker app-mode script (RQB2-config/demo-patches/
qoffee-appmode-custom.js), run under node with a stand-in for the classic
notebook (#3 of the 2026-10-05 user test):

- the app mode starts only once the kernel is ready: its restart interrupted
  the kernel the page had just started, and the widget manager lost the app's
  widgets (raw "AppBox(...)" text instead of the app).
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_JS = os.path.abspath(os.path.join(_HERE, "..", "..", "RQB2-config", "demo-patches",
                                   "qoffee-appmode-custom.js"))

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is required")

_HARNESS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const name = process.argv[2];
const handlers = {};
const events = {on: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); }};
const calls = [];
const Jupyter = {notebook: {notebook_name: name, _fully_loaded: true, kernel: {info_reply: {}}}};
// the app's action restarts the kernel and runs all cells, as qoffeefrontend/app.js does
Jupyter.actions = Object.preventExtensions({        // as in the notebook: not extensible
  exists: n => n === 'simple-app:app-activate',
  call: function (n) {
    calls.push(n);
    if (n === 'simple-app:app-activate') {
      Jupyter.actions.call('jupyter-notebook:restart-kernel-and-run-all-cells');
    }
  },
});
const timers = [];
const fakeRequire = (deps, cb) => cb(Jupyter, events);
const tick = n => { for (let i = 0; i < n; i++) timers.forEach(f => f && f()); };
console.log = console.warn = console.error = () => {};
new Function('require', 'setInterval', 'clearInterval', src)(
  fakeRequire, fn => timers.push(fn), id => { timers[id - 1] = null; });
tick(10);
const before = calls.slice();
(handlers['kernel_ready.Kernel'] || []).forEach(f => f());
tick(13);
process.stdout.write(JSON.stringify({before, activated: calls.slice(before.length)}));
"""


def _run(notebook="qoffee.ipynb"):
    proc = subprocess.run(["node", "-e", _HARNESS, _JS, notebook], capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_app_mode_waits_for_the_kernel():
    out = _run()
    assert out["before"] == []                       # kernel still starting: nothing yet
    assert out["activated"] == ["simple-app:app-activate",
                                "jupyter-notebook:restart-kernel-and-run-all-cells"]   # once


def test_other_notebooks_keep_the_normal_interface():
    out = _run("Untitled.ipynb")
    assert out["before"] == [] and out["activated"] == []
