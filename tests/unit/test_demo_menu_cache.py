"""
Tests for the demo menu cache written by rq_demo_generate_menu.sh --cache
(R-120): raspi-config sources it, so it must always parse, and a demo's name
must stay text when the menu eval's the item list.
"""

import json
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_GEN = os.path.join(_ROOT, "RQB2-bin", "rq_demo_generate_menu.sh")
_SH = shutil.which("dash") or "/bin/sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _user_manifest(user_dir, file_id, demo_id, name):
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / f"rq_demo_{file_id}.json").write_text(json.dumps({
        "id": demo_id,
        "name": name,
        "category": "visualization",
        "description": "test",
        "entrypoint": {"type": "browser", "browser_url": "https://example.org/"},
        "menu": {"show": True, "order": 99},
    }))


def _generate(tmp_path):
    home = tmp_path / "home"
    user_dir = home / ".local" / "config" / "demo-manifests"
    _user_manifest(user_dir, "quoted", 'bad"id', "Bad id")
    _user_manifest(user_dir, "evil", "evil-name", 'Evil "$(touch PWNED)" `touch PWNED2` \\ it\'s')
    cache = tmp_path / "cache.sh"
    env = dict(os.environ, USER_HOME=str(home),
               RQ_CONFIG_FILE=str(tmp_path / "no-such-config.sh"))
    proc = subprocess.run(["bash", _GEN, "--cache", str(cache)], capture_output=True,
                          text=True, env=env, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    return cache, proc


def test_cache_parses_and_skips_bad_ids(tmp_path):
    cache, proc = _generate(tmp_path)
    assert subprocess.run([_SH, "-n", str(cache)]).returncode == 0
    text = cache.read_text()
    assert 'bad"id' not in text
    assert "Skipping" in proc.stderr
    assert '"evil-name")' in text


def test_demo_names_stay_text_in_the_menu_eval(tmp_path):
    cache, _ = _generate(tmp_path)
    # what do_quantum_demo_menu does with DEMO_MENU_ITEMS
    script = (f'. "{cache}"\n'
              'eval "set -- $(printf \'%s\' "${DEMO_MENU_ITEMS:-}" | tr \'\\n\' \' \')"\n'
              'while [ $# -gt 0 ]; do [ "$1" = evil-name ] && printf \'NAME=[%s]\\n\' "$2"; shift 2; done\n')
    proc = subprocess.run([_SH, "-c", script], capture_output=True, text=True, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / "PWNED").exists() and not (tmp_path / "PWNED2").exists()
    assert 'NAME=[Evil "$(touch PWNED)" `touch PWNED2` \\ it\'s]' in proc.stdout, proc.stdout
