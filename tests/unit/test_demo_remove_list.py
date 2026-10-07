"""
"Remove a demo" listed only the demos before the first Docker demo whose image
is not on the Pi (Quantum Lab; user tests 2026-10-06, N2): the size lookup
printed "0" twice and the list ended in an arithmetic error.
"""

import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _read(*parts):
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


@needs_bash
def test_a_missing_docker_image_counts_as_zero_once(tmp_path):
    src = _read("RQB2-bin", "rq_demo_remove.sh")
    funcs = "\n".join(re.search(r"^%s\(\) \{\n.*?^\}\n" % name, src, re.M | re.S).group(0)
                      for name in ("dir_mb", "image_mb", "demo_mb"))
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "docker").write_text("#!/bin/sh\necho 'Error: No such image' >&2\nexit 1\n")
    (stubs / "docker").chmod(0o755)
    script = (f"set -euo pipefail\nDOCKER_OK=yes\nDEMOS_ROOT={tmp_path}\n{funcs}\n"
              'echo "[$(image_mb ghcr.io/x@sha256:1)]"\necho "[$(demo_mb docker "" ghcr.io/x)]"\n'
              'echo "[$(demo_mb program "" "")]"\n')
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env=dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}"))
    assert p.returncode == 0, p.stderr
    assert p.stdout.split() == ["[0]", "[0]", "[0]"]


def test_one_demo_failing_does_not_end_the_remove_list():
    src = _read("RQB2-bin", "rq_demo_remove.sh")
    assert 'line=$(downloaded_entry "$mf") || continue' in src
    assert "|| echo 0)" not in src
