"""
Tests for rq_demo_add_external.sh --remove (uninstalling a catalog demo).

The script loads its environment through RQ_CONFIG_FILE, pointed here at a
stub that sets USER_HOME to a temp directory. Skipped without bash or jq.
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "..", "RQB2-bin", "rq_demo_add_external.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required for these shell tests",
)


def _home(tmp_path, manifest):
    home = tmp_path / "home"
    (home / ".local/config/demo-manifests").mkdir(parents=True)
    (home / "Desktop").mkdir()
    (home / f".local/config/demo-manifests/rq_demo_{manifest['id']}.json").write_text(json.dumps(manifest))
    (home / f"Desktop/rq-ext-{manifest['id']}.desktop").write_text("[Desktop Entry]\n")
    stub = tmp_path / "env-config.sh"
    stub.write_text(f'USER_HOME="{home}"\nREPO=RasQberry-Two\nSTD_VENV=RQB2\n')
    return home, stub


def _remove(stub, demo_id):
    env = dict(os.environ, RQ_CONFIG_FILE=str(stub))
    return subprocess.run(["bash", _SCRIPT, "--remove", demo_id], capture_output=True, text=True, env=env)


def test_remove_deletes_checkout_manifest_and_icon(tmp_path):
    m = {"id": "gone-demo", "entrypoint": {"working_dir": "Gone-Repo"},
         "install": {"repo_url": "https://github.com/a/Gone-Repo.git"}}
    home, stub = _home(tmp_path, m)
    checkout = home / "RasQberry-Two/demos/Gone-Repo"
    checkout.mkdir(parents=True)
    keep = home / "RasQberry-Two/demos/Other-Demo"
    keep.mkdir()

    proc = _remove(stub, "gone-demo")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not checkout.exists()
    assert keep.exists()
    assert not (home / ".local/config/demo-manifests/rq_demo_gone-demo.json").exists()
    assert not (home / "Desktop/rq-ext-gone-demo.desktop").exists()


def test_remove_falls_back_to_repo_name(tmp_path):
    m = {"id": "no-wd", "install": {"repo_url": "https://github.com/a/No-Wd-Repo.git"}}
    home, stub = _home(tmp_path, m)
    checkout = home / "RasQberry-Two/demos/No-Wd-Repo"
    checkout.mkdir(parents=True)
    assert _remove(stub, "no-wd").returncode == 0
    assert not checkout.exists()


@pytest.mark.parametrize("bad", ["..", "../../etc", "a/b"])
def test_remove_refuses_paths_outside_demos(tmp_path, bad):
    m = {"id": "evil", "entrypoint": {"working_dir": bad}}
    home, stub = _home(tmp_path, m)
    proc = _remove(stub, "evil")
    assert proc.returncode != 0
    assert (home / ".local/config/demo-manifests/rq_demo_evil.json").exists()


def test_remove_unknown_demo_fails(tmp_path):
    _, stub = _home(tmp_path, {"id": "present"})
    proc = _remove(stub, "absent")
    assert proc.returncode != 0
    assert "not installed" in proc.stdout + proc.stderr


def test_remove_offers_to_delete_the_docker_image(tmp_path):
    # R-160: traQmania's (now racetraQ) 3.2 GB image stayed behind
    m = {"id": "dock-demo", "entrypoint": {"type": "docker", "docker_image": "ghcr.io/x/dock:latest",
                                            "working_dir": "dock-demo"},
         "install": {"repo_url": "https://github.com/x/dock-demo.git"}}
    home, stub = _home(tmp_path, m)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    (bin_dir / "docker").write_text(f'#!/bin/sh\necho "$*" >> "{log}"\n'
                                    'case "$1 $2" in "image inspect") echo 3240000000; exit 0 ;; esac\nexit 0\n')
    (bin_dir / "docker").chmod(0o755)
    env = dict(os.environ, RQ_CONFIG_FILE=str(stub), RQ_ASSUME_YES="yes",
               PATH=f"{bin_dir}:{os.environ['PATH']}")
    proc = subprocess.run(["bash", _SCRIPT, "--remove", "dock-demo"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "rmi ghcr.io/x/dock:latest" in log.read_text()
