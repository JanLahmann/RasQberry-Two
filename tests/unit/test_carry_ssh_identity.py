"""
Tests for RQB2-bin/rq_carry_ssh_identity.sh (issue #275): an A/B slot update
keeps the device's SSH host keys and the user's authorized_keys.

Source and target roots are temp directories; runs unprivileged, so the
chown step is skipped.
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_carry_ssh_identity.sh")
HOME = "/home/rasqberry"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _root(base, keys=None, authorized=None):
    (base / "etc/ssh").mkdir(parents=True)
    (base / ("." + HOME)).mkdir(parents=True)
    for name, body in (keys or {}).items():
        (base / "etc/ssh" / name).write_text(body)
    if authorized is not None:
        (base / ("." + HOME) / ".ssh").mkdir()
        (base / ("." + HOME) / ".ssh/authorized_keys").write_text(authorized)
    return base


def _carry(src, target):
    env = dict(os.environ, RQ_SSH_SOURCE_ROOT=str(src), RQ_SSH_USER_HOME=HOME)
    return subprocess.run(["bash", _SCRIPT, str(target)], capture_output=True, text=True, env=env)


RUNNING_KEYS = {
    "ssh_host_ed25519_key": "running-ed25519",
    "ssh_host_ed25519_key.pub": "running-ed25519.pub",
    "ssh_host_rsa_key": "running-rsa",
    "ssh_host_rsa_key.pub": "running-rsa.pub",
}


def test_host_keys_replace_the_images_and_regen_is_masked(tmp_path):
    src = _root(tmp_path / "src", RUNNING_KEYS, "ssh-rsa AAAA user@mac\n")
    tgt = _root(tmp_path / "tgt", {"ssh_host_ecdsa_key": "image-ecdsa"})
    (tgt / "etc/systemd/system/multi-user.target.wants").mkdir(parents=True)
    wants = tgt / "etc/systemd/system/multi-user.target.wants/regenerate_ssh_host_keys.service"
    wants.write_text("")

    proc = _carry(src, tgt)
    assert proc.returncode == 0, proc.stderr
    assert sorted(os.listdir(tgt / "etc/ssh")) == sorted(RUNNING_KEYS)
    assert (tgt / "etc/ssh/ssh_host_ed25519_key").read_text() == "running-ed25519"
    assert oct((tgt / "etc/ssh/ssh_host_rsa_key").stat().st_mode & 0o777) == "0o600"
    mask = tgt / "etc/systemd/system/regenerate_ssh_host_keys.service"
    assert os.readlink(mask) == "/dev/null"
    assert not wants.exists()
    assert "host keys and authorized_keys" in proc.stdout


def test_authorized_keys_are_copied_with_private_modes(tmp_path):
    src = _root(tmp_path / "src", RUNNING_KEYS, "ssh-rsa AAAA user@mac\n")
    tgt = _root(tmp_path / "tgt")
    assert _carry(src, tgt).returncode == 0
    ak = tgt / ("." + HOME) / ".ssh/authorized_keys"
    assert ak.read_text() == "ssh-rsa AAAA user@mac\n"
    assert oct(ak.stat().st_mode & 0o777) == "0o600"
    assert oct(ak.parent.stat().st_mode & 0o777) == "0o700"


def test_nothing_to_carry_leaves_the_target_alone(tmp_path):
    src = _root(tmp_path / "src")
    tgt = _root(tmp_path / "tgt", {"ssh_host_ed25519_key": "image"})
    proc = _carry(src, tgt)
    assert proc.returncode == 0
    assert (tgt / "etc/ssh/ssh_host_ed25519_key").read_text() == "image"
    assert not (tgt / "etc/systemd/system/regenerate_ssh_host_keys.service").exists()
    assert "nothing" in proc.stdout


def test_missing_target_is_a_usage_error(tmp_path):
    assert _carry(tmp_path, tmp_path / "nope").returncode == 2
