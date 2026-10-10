"""
Quantum Mixer without a Home Connect account (F1 of the 2026-10-08 Pi 4 test,
item 18 of feedback-2026-10-03): its QoffeeMaker login answered a bare
"Internal Server Error" and the hint named Qoffee-Maker's settings file, which
is not there unless Qoffee-Maker was downloaded. The fix is in the Mixer image
since quantum-mixer 8a9cf32 (its PR #3); the copy RasQberry mounted over the
older image in the meantime is gone.

quantum-mixer.sh runs against a stub docker that logs its arguments; no
Raspberry Pi, network or Docker needed.
"""

import json
import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MIXER = os.path.join(_BIN, "quantum-mixer.sh")
_FIXLESS_REF = "fc0cb984508ce80b3d0c650669bc7f2b8bde72c3"   # the image that answered a 500

pytestmark = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                                reason="bash and jq are required")

_DOCKER = r'''#!/bin/sh
printf '%s\n' "$*" >> "$DOCKER_LOG"
case "$1 $2" in
  "image inspect") exit 0 ;;
  "container inspect")
     case "$*" in *State.Running*) echo true; exit 0 ;; esac
     exit 1 ;;
  "run -d") echo abc123; for a in "$@"; do printf 'ARG %s\n' "$a"; done >> "$DOCKER_LOG"; exit 0 ;;
esac
exit 0
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def mixer(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "docker", _DOCKER)
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    real_id = shutil.which("id")
    _exe(stubs / "id", f'#!/bin/sh\n[ "$1" = "-nG" ] && {{ echo "users docker"; exit 0; }}\nexec {real_id} "$@"\n')
    home = tmp_path / "home"
    home.mkdir()
    cfg = tmp_path / "config"
    shutil.copytree(_CFG, cfg)
    env_file = cfg / "rasqberry_environment.env"
    env_config = cfg / "rasqberry_env-config.sh"
    env_config.write_text(env_config.read_text()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    log = tmp_path / "docker.log"

    def run():
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": str(home), "USER": "jan",
            "RQ_CONFIG_FILE": str(env_config), "RQ_ENV_FILE": str(env_file),
            "DOCKER_LOG": str(log), "QUANTUM_MIXER_PORT": "8085",
        }
        p = subprocess.run(["bash", _MIXER], capture_output=True, text=True, env=env,
                           stdin=subprocess.DEVNULL, timeout=60, start_new_session=True)
        args = [l[4:] for l in log.read_text().splitlines() if l.startswith("ARG ")] \
            if log.exists() else []
        return p, args

    run.home = home
    run.cfg = cfg
    return run


def test_without_an_account_the_hint_names_a_real_file_and_nothing_is_mounted(mixer):
    p, args = mixer()
    assert p.returncode == 0, p.stdout + p.stderr
    hc = mixer.home / ".config" / "rasqberry" / "home-connect.env"
    # the settings file the hint names exists, with empty values to fill in
    assert hc.exists()
    assert "HOMECONNECT_CLIENT_ID=\n" in hc.read_text()
    assert oct(hc.stat().st_mode & 0o777) == "0o600"
    assert str(hc) in p.stdout
    assert "Qoffee-Maker/.env" not in p.stdout
    assert "/home/rasqberry" not in p.stdout
    assert "shows an error" not in p.stdout
    # the page in the browser says the same
    hint = [a for a in args if a.startswith("HOMECONNECT_SETUP_HINT=")]
    assert hint and str(hc) in hint[0]
    assert not any(a.startswith("HOMECONNECT_CLIENT_ID=") for a in args)
    # the image has the Qoffee page itself: nothing is mounted over it
    assert "-v" not in args and not any(a.endswith(":ro") for a in args)


def test_an_account_in_the_mixer_settings_file_is_used(mixer):
    hc = mixer.home / ".config" / "rasqberry" / "home-connect.env"
    hc.parent.mkdir(parents=True)
    hc.write_text("HOMECONNECT_CLIENT_ID=abc\nHOMECONNECT_CLIENT_SECRET=s3\n")
    p, args = mixer()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "HOMECONNECT_CLIENT_ID=abc" in args
    assert "HOMECONNECT_BASE_URL=https://simulator.home-connect.com" in args
    assert "HOST_ADDRESS=http://127.0.0.1:8085" in args
    assert "auth/callback" in p.stdout


def test_qoffee_makers_settings_still_count(mixer):
    q = mixer.home / "RasQberry-Two" / "demos" / "Qoffee-Maker"
    q.mkdir(parents=True)
    (q / ".env").write_text("HOMECONNECT_CLIENT_ID=qm\nHOMECONNECT_CLIENT_SECRET=x\n"
                            "HOMECONNECT_API_URL=https://api.home-connect.com/\n")
    p, args = mixer()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "HOMECONNECT_CLIENT_ID=qm" in args
    assert "HOMECONNECT_BASE_URL=https://api.home-connect.com" in args


def test_the_pin_is_a_mixer_build_with_the_qoffee_page():
    with open(os.path.join(_CFG, "demo-manifests", "rq_demo_quantum-mixer.json")) as f:
        m = json.load(f)
    ref = m["install"]["source"]["ref"]
    assert ref != _FIXLESS_REF
    ep = m["entrypoint"]
    assert ep["docker_image"].startswith("ghcr.io/janlahmann/quantum-mixer@sha256:")
    assert ep["docker_image_fallback"] == "ghcr.io/janlahmann/quantum-mixer:" + ref
    # the temporary copy of the fixed use case and its mount are gone
    assert not os.path.exists(os.path.join(_CFG, "quantum-mixer"))
    text = open(_MIXER).read()
    assert "QOFFEE_FIX" not in text and "usecase.py" not in text
    assert "HOMECONNECT_SETUP_HINT=" in text
