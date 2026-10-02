"""
Tests for who runs a demo when rq_demo_run.sh is started as root from the
RasQberry menu (Jan's decision Q26, R-025): demos that do not drive the LED
panel run as the desktop user; LED demos keep root.

Root is faked with an `id` stub, and `sudo` is a stub that records how it was
called, so nothing here needs a Raspberry Pi or root.
"""

import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_ENGINE = os.path.join(_ROOT, "RQB2-bin", "rq_demo_run.sh")
_ENV_CONFIG = os.path.join(_ROOT, "RQB2-config", "rasqberry_env-config.sh")
_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def engine(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "id", '#!/bin/sh\n[ "$1" = "-u" ] && { echo 0; exit 0; }\nexec /usr/bin/id "$@"\n')
    _exe(stubs / "whoami", "#!/bin/sh\necho root\n")
    _exe(stubs / "sudo", '#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > "$SUDO_LOG"\nexit 0\n')
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))

    def run(*args, display=None):
        err_file = tmp_path / "err.txt"
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": "/root",
            "SUDO_USER": "rasqberry",
            "USER": "root",
            "RQ_CONFIG_FILE": str(env_config),
            "RQ_ERROR_FILE": str(err_file),
            "SUDO_LOG": str(tmp_path / "sudo.log"),
        }
        if display:
            env["DISPLAY"] = display
        proc = subprocess.run(["bash", _ENGINE, *args], capture_output=True, text=True,
                              env=env, timeout=60)
        sudo = (tmp_path / "sudo.log").read_text().splitlines() if (tmp_path / "sudo.log").exists() else []
        err = err_file.read_text() if err_file.exists() else ""
        return proc, sudo, err

    return run


def test_non_led_demo_is_handed_to_the_desktop_user(engine):
    proc, sudo, _ = engine("fun-with-quantum", "readme", display=":0")
    assert sudo[:3] == ["-u", "rasqberry", "-H"], sudo
    assert "DISPLAY=:0" in sudo
    assert any(a.startswith("RQ_ERROR_FILE=") for a in sudo)
    i = sudo.index("--")
    assert sudo[i + 1].endswith("rq_demo_run.sh") and sudo[i + 2:] == ["fun-with-quantum", "readme"], sudo


def test_install_only_flag_survives_the_hand_over(engine):
    _, sudo, _ = engine("grok-bloch", "--install-only")
    assert "DISPLAY=:0" not in " ".join(sudo), "no display must stay no display (SSH)"
    i = sudo.index("--")
    assert sudo[i + 2:] == ["grok-bloch", "--install-only"], sudo


def test_led_demo_keeps_root_and_explains_a_missing_screen(engine):
    proc, sudo, err = engine("quantum-raspberry-tie", "simulator")
    assert sudo == [], "LED demos must not be handed to the user"
    assert proc.returncode != 0
    assert "needs a screen" in err and "VNC" in err, err
