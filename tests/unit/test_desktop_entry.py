"""
Tests for RQB2-bin/rq_demo_desktop_entry.sh (issue #287).

Skipped automatically if bash or jq are unavailable.
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_WRITER = os.path.join(_ROOT, "RQB2-bin", "rq_demo_desktop_entry.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required for these shell tests",
)


def _manifest(**overrides):
    base = {
        "id": "ext-demo",
        "name": "External Demo",
        "description": "Partner demo (MIT)",
        "category": "tool",
        "keywords": ["sap", "qaoa"],
        "entrypoint": {"type": "python", "script": "main.py", "working_dir": "ext-demo"},
        "icon": {"type": "system", "path": "applications-science"},
        "desktop": {"show": True, "terminal": False},
    }
    base.update(overrides)
    return base


def _run(manifest, tmp_path, demo_dir=None):
    mpath = tmp_path / "rqb-demo.json"
    mpath.write_text(json.dumps(manifest))
    out = tmp_path / "Desktop" / "rq-ext-ext-demo.desktop"
    cmd = ["bash", _WRITER, str(mpath), str(out)]
    if demo_dir:
        cmd.append(demo_dir)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc, out


def _fields(path):
    fields = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("["):
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def test_desktop_entry_dispatches_through_the_launcher(tmp_path):
    proc, out = _run(_manifest(), tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    fields = _fields(out)
    assert fields["Exec"] == "/usr/bin/rq_demo_run.sh ext-demo"
    assert fields["TryExec"] == "/usr/bin/rq_demo_run.sh"
    assert fields["Name"] == "External Demo"
    assert fields["Terminal"] == "false"
    assert fields["Icon"] == "applications-science"
    assert fields["Keywords"] == "sap;qaoa;"
    assert fields["Categories"] == "RasQberry;"
    assert os.access(out, os.X_OK)


def test_custom_icon_resolves_inside_the_demo_dir(tmp_path):
    m = _manifest(icon={"type": "custom", "path": "assets/logo.png"})
    proc, out = _run(m, tmp_path, demo_dir="/home/rasqberry/RasQberry-Two/demos/ext-demo")
    assert proc.returncode == 0, proc.stderr
    assert _fields(out)["Icon"] == "/home/rasqberry/RasQberry-Two/demos/ext-demo/assets/logo.png"


@pytest.mark.parametrize("bad", ["../../etc/passwd.png", "/etc/hostname", "assets/../../x.png"])
def test_unsafe_custom_icon_path_falls_back_to_system_icon(tmp_path, bad):
    m = _manifest(icon={"type": "custom", "path": bad})
    proc, out = _run(m, tmp_path, demo_dir="/home/rasqberry/RasQberry-Two/demos/ext-demo")
    assert proc.returncode == 0, proc.stderr
    assert _fields(out)["Icon"] == "applications-science"
    assert "must be relative" in proc.stdout + proc.stderr


def test_desktop_show_false_writes_nothing(tmp_path):
    proc, out = _run(_manifest(desktop={"show": False}), tmp_path)
    assert proc.returncode == 3
    assert not out.exists()


def test_terminal_defaults_to_true(tmp_path):
    proc, out = _run(_manifest(desktop={"show": True}), tmp_path)
    assert proc.returncode == 0
    assert _fields(out)["Terminal"] == "true"
