"""
The LED sandbox's view of the home (rq_common.sh rq_led_sandbox_mounts,
rq_led_as_user), pre-beta review 2026-10-16 (B4, D2).

A list of protected files guarded only those that existed: a catalogue LED
demo could create ~/.bash_profile, ~/.ssh/authorized_keys, ~/.local/bin/sudo,
an autostart entry or a systemd user unit, and change the desktop launchers,
labwc's settings and other demos' code - all run later by the user, who may
sudo. Now the whole home is read-only, and only what LED demos use is
writable again.

The mount list is checked here; test_the_sandbox_on_linux runs the real
mounts (as root on Linux, e.g. in a privileged container).
"""

import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_COMMON = os.path.join(_ROOT, "RQB2-bin", "rq_common.sh")

HOME = "/home/ada"
DEMOS = HOME + "/RasQberry-Two/demos"
WRITABLE = [HOME + "/.cache/rasqberry-led-sandbox", HOME + "/.qiskit", HOME + "/.config/sense_hat",
            HOME + "/.sensehat"]


def _mounts(cwd, home=HOME):
    proc = subprocess.run(["bash", "-c", f'. "{_COMMON}"; rq_led_sandbox_mounts "$1" "$2"', "_", home, cwd],
                          capture_output=True, text=True, env=dict(os.environ, REPO="RasQberry-Two"))
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.splitlines()


@pytest.mark.parametrize("cwd, own", [
    (DEMOS + "/Quantum-Lights-Out", DEMOS + "/Quantum-Lights-Out"),
    (DEMOS + "/quantum-raspberry-tie/svg", DEMOS + "/quantum-raspberry-tie"),
    (DEMOS + "/sap-quantum-led/", DEMOS + "/sap-quantum-led"),
    (DEMOS, None),                                  # all demos: no
    (DEMOS + "/.rq-new-x", None),                   # a download in progress
    (DEMOS + "/.demo-versions", None),
    (HOME, None),
    (HOME + "/RasQberry-Two", None),
    ("/usr/bin", None),
    ("/tmp" + DEMOS + "/x", None),
])
def test_the_home_is_read_only_and_only_these_are_writable(cwd, own):
    lines = _mounts(cwd)
    # first the whole home read-only, then the writable folders under it
    assert lines[0] == "ro " + HOME
    assert [ln for ln in lines if ln.startswith("ro ")] == ["ro " + HOME]
    rw = [ln[3:] for ln in lines[1:]]
    assert all(ln.startswith("rw ") for ln in lines[1:])
    assert rw == WRITABLE + ([own] if own else [])


def test_what_a_later_login_or_root_runs_is_not_writable():
    rw = [ln[3:] for ln in _mounts(DEMOS + "/Quantum-Lights-Out") if ln.startswith("rw ")]
    for path in (".bashrc", ".profile", ".bash_profile", ".bash_login", ".bash_aliases", ".ssh",
                 ".local/bin", ".local/lib", ".local/config", ".local/share/applications",
                 ".config/autostart", ".config/systemd", ".config/labwc", "Desktop",
                 "RasQberry-Two/venv", "RasQberry-Two/demos/.demo-versions",
                 "RasQberry-Two/demos/grok-bloch", ".cache/pip"):
        p = HOME + "/" + path
        assert not any(p == w or p.startswith(w + "/") for w in rw), path


def test_the_sandbox_gets_its_own_cache():
    common = open(_COMMON).read()
    fn = common[common.index("rq_led_as_user() {"):common.index("rq_led_renderer_stop() {")]
    assert 'XDG_CACHE_HOME="$cache" MPLCONFIGDIR="$cache/matplotlib"' in fn
    # made by the user before the home turns read-only, not by root
    assert 'setpriv --reuid="$uid" --regid="$gid" --clear-groups -- mkdir -p "$home/$p"' in fn


_E2E = r'''
set -u
id ada >/dev/null 2>&1 || useradd -m ada
H=/home/ada
su ada -c "mkdir -p $H/RasQberry-Two/demos/qlo $H/RasQberry-Two/demos/other $H/RasQberry-Two/venv; touch $H/.bashrc $H/.profile"
. "$1"
get_user_name() { echo ada; }
rq_audio_runtime_dir() { return 1; }
cd $H/RasQberry-Two/demos/qlo
rq_led_as_user bash -c '
for f in .bash_profile .bash_aliases .bashrc .ssh/authorized_keys .local/bin/sudo .config/autostart/x.desktop \
         .config/systemd/user/x.service .config/labwc/autostart Desktop/x.desktop RasQberry-Two/venv/x \
         RasQberry-Two/demos/other/x RasQberry-Two/demos/.demo-versions .cache/pip/x \
         RasQberry-Two/demos/qlo/svg/x .qiskit/qiskit-ibm.json .config/sense_hat/RTIMULib.ini .sensehat/fb \
         .cache/rasqberry-led-sandbox/fontconfig/x; do
    mkdir -p "$(dirname "$HOME/$f")" 2>/dev/null
    if echo x > "$HOME/$f" 2>/dev/null; then echo "W $f"; else echo "- $f"; fi
done
echo "cache=$XDG_CACHE_HOME"'
'''


@pytest.mark.skipif(os.geteuid() != 0 or not shutil.which("unshare") or not shutil.which("setpriv")
                    or not shutil.which("useradd"), reason="needs root on Linux (unshare, setpriv)")
def test_the_sandbox_on_linux(tmp_path):
    script = tmp_path / "e2e.sh"
    script.write_text(_E2E)
    out = subprocess.run(["bash", str(script), _COMMON], capture_output=True, text=True).stdout
    written = {ln[2:] for ln in out.splitlines() if ln.startswith("W ")}
    assert written == {"RasQberry-Two/demos/qlo/svg/x", ".qiskit/qiskit-ibm.json",
                       ".config/sense_hat/RTIMULib.ini", ".sensehat/fb",
                       ".cache/rasqberry-led-sandbox/fontconfig/x"}, out
    assert "cache=/home/ada/.cache/rasqberry-led-sandbox" in out
