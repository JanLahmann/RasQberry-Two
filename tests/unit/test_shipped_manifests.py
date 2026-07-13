#!/usr/bin/env python3
"""
Unit tests for the shipped demo manifests.

These run rq_demo_validate.sh against the real manifests in
RQB2-config/demo-manifests to guard against schema regressions in CI (no
Raspberry Pi and no installed system required).

Run with:
    python3 -m pytest tests/unit/ -q

Skipped automatically if bash or jq are unavailable.
"""

import os
import shutil
import subprocess

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_REPO_ROOT, "RQB2-bin")
_VALIDATE = os.path.join(_BIN, "rq_demo_validate.sh")
_MANIFEST_DIR = os.path.join(_REPO_ROOT, "RQB2-config", "demo-manifests")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required for the manifest validation tests",
)


def test_all_shipped_manifests_validate():
    """rq_demo_validate.sh (no args) must pass for every shipped manifest."""
    proc = subprocess.run([_VALIDATE], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    # The validator exits non-zero if any manifest fails.
    assert proc.returncode == 0, f"validator failed:\n{output}"


def test_quantum_lab_manifest_validates():
    """The Quantum Lab (QuBins) manifest validates individually."""
    manifest = os.path.join(_MANIFEST_DIR, "rq_demo_quantum-lab.json")
    assert os.path.isfile(manifest), "quantum-lab manifest is missing"
    proc = subprocess.run([_VALIDATE, manifest], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"quantum-lab manifest failed to validate:\n{output}"


def test_doqumentation_manifest_validates():
    """The doQumentation (Workshop Server) manifest validates individually."""
    manifest = os.path.join(_MANIFEST_DIR, "rq_demo_doqumentation.json")
    assert os.path.isfile(manifest), "doqumentation manifest is missing"
    proc = subprocess.run([_VALIDATE, manifest], capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"doqumentation manifest failed to validate:\n{output}"
