"""
Test for the HOME fallback in RQB2-config/rasqberry_env-config.sh (issue #286).
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_CONFIG = os.path.abspath(os.path.join(_HERE, "..", "..", "RQB2-config", "rasqberry_env-config.sh"))

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")

def test_env_config_survives_unset_home_under_set_u():
    """
    #286: systemd units have no HOME. Sourcing under `set -u` used to die with
    "HOME: unbound variable" before reaching the config-file check.
    """
    proc = subprocess.run(
        ["bash", "-u", "-c", f". {_ENV_CONFIG}; echo USER_HOME=$USER_HOME"],
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
    )
    assert "unbound variable" not in proc.stderr
    # Either the installed config exists (then USER_HOME is printed) or the
    # loader stops at the missing-config check; both are past the HOME bug.
    assert "USER_HOME=" in proc.stdout or "Missing config file" in proc.stderr
