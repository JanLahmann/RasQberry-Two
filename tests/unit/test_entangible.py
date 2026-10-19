"""
Entangible as an internal demo (Big projects, beta): its manifest, desktop
entry and icon, and rq_entangible.sh against a stub of Entangible's own
command (deploy/rasqberry/entangible, contract: docs/rasqberry-integration.md
in github.com/JanLahmann/entangible).

The stub keeps its state in files (installed, running, bundle, ready) and logs
every call; its exit codes come from files too (install_rc, start_rc), so the
launcher's handling of 0 / 130 / failure can be checked. No Raspberry Pi,
systemd, camera or network needed.
"""

import json
import os
import pty
import select
import shutil
import signal
import stat
import subprocess
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_LAUNCHER = os.path.join(_BIN, "rq_entangible.sh")
_ENGINE = os.path.join(_BIN, "rq_demo_run.sh")
_REMOVE = os.path.join(_BIN, "rq_demo_remove.sh")
_DL = os.path.join(_BIN, "rq_download_all.sh")
_ENV_CONFIG = os.path.join(_CFG, "rasqberry_env-config.sh")
_ENV = os.path.join(_CFG, "rasqberry_environment.env")
_PIN = "e7105e9c92a284a42489b6d56779e84be51b9dcb"
_STOP_LINE = "To stop Entangible: press Enter or Ctrl+C, or close this window."

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="bash and jq are required")

# Entangible's command: state in $ENT_STATE, calls in $ENT_STATE/calls
_STUB = r'''#!/bin/bash
S="$ENT_STATE"
echo "$*" >> "$S/calls"
get() { cat "$S/$1" 2>/dev/null || echo "$2"; }
case "$1" in
  status)
    if [ -f "$S/status_raw" ]; then cat "$S/status_raw"; exit 0; fi
    inst=$(get installed false); run=$(get running false); b=$(get bundle null)
    [ "$b" = null ] || b="\"$b\""
    health=unknown; ready=null
    if [ "$run" = true ]; then health=$(get health ok); [ "$health" = ok ] && ready=$(get ready false); fi
    if [ "$health" = ok ] && [ -s "$S/ready_seq" ]; then
      ready=$(head -1 "$S/ready_seq")
      [ "$(wc -l < "$S/ready_seq")" -gt 1 ] && sed -i.bak 1d "$S/ready_seq"
    fi
    [ "$inst" = true ] && [ "$health" = unknown ] && health=down
    printf '{"installed":%s,"running":%s,"version":"094616c","bundle":%s,"urls":{"kiosk":"https://localhost:8443/?kiosk&connect=1","visitor":"%s"},"source":"%s","ready":%s,"health":"%s","enabled":false}\n' \
      "$inst" "$run" "$b" "$(get visitor https://192.168.1.23:8443/?connect=1)" "$(get source cv2:0)" "$ready" "$health"
    ;;
  install)
    # --no-enable: installed, not started (and not at boot)
    [ "$2" = "--no-enable" ] || { echo "install without --no-enable" >&2; exit 2; }
    rc=$(get install_rc 0)
    if [ "$rc" = 0 ]; then echo true > "$S/installed"; echo booth-v2 > "$S/bundle"; fi
    exit "$rc" ;;
  doctor)
    echo "note: the service is running, so the 'port' row is expected to be x"
    [ -f "$S/hint" ] && echo "hint: $(cat "$S/hint")"
    echo "camera  x"
    exit 1 ;;
  start)
    rc=$(get start_rc 0)
    [ "$rc" = 0 ] && echo true > "$S/running"
    exit "$rc" ;;
  stop) echo false > "$S/running" ;;
  uninstall)
    echo "Uninstalling Entangible (checkout $PWD is kept)"
    echo "    kept: the checkout, apt packages (shared), uv, ~/.qamposer-physical/*.toml, the log"
    echo "    kept (shared tool) uv; if nothing else uses it: rm -f $HOME/.local/bin/uv $HOME/.local/bin/uvx"
    echo "    kept (shared) uv cache; if nothing else uses it: rm -rf $HOME/.cache/uv"
    echo "    kept uv cache /data/rasqberry/cache/entangible/uv (part of the /data cache: --purge-cache removes it)"
    echo "removed: /etc/default/entangible"
    echo false > "$S/installed"; echo false > "$S/running"; rm -f "$S/bundle" ;;
  *) exit 2 ;;
esac
'''

_WHIPTAIL = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
case " $* " in *" --yesno "*) exit "${WT_RC:-0}" ;; esac
exit 0
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _manifest():
    with open(os.path.join(_MANIFESTS, "rq_demo_entangible.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def ent(tmp_path):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "curl", "#!/bin/sh\nexit 0\n")
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    _exe(stubs / "whiptail", _WHIPTAIL)
    _exe(stubs / "qrencode", '#!/bin/sh\necho "QR:$*"\n')
    _exe(stubs / "chromium", '#!/bin/sh\necho "$*" >> "$ENT_STATE/browser"\n')
    _exe(stubs / "wlr-randr", '#!/bin/sh\nprintf "HDMI-A-1 \\"x\\"\\n  Enabled: yes\\n  Modes:\\n'
         '    1920x1080 px, 60.000000 Hz (preferred, current)\\n"\n')
    home = tmp_path / "home"
    checkout = home / "RasQberry-Two" / "demos" / "entangible"
    (checkout / "deploy" / "rasqberry").mkdir(parents=True)
    _exe(checkout / "deploy" / "rasqberry" / "entangible", _STUB)
    (checkout / "deploy" / "rasqberry" / "BUNDLE_TAG").write_text("booth-v2\n")
    state = tmp_path / "state"
    state.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    tty = tmp_path / "tty"
    tty.write_text("")

    def env(extra=None):
        e = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": str(home), "USER": "jan",
            "RQ_CONFIG_FILE": str(env_config), "RQ_ENV_FILE": str(env_file),
            "RQ_TEST_TTY": str(tty), "RQ_TEST_FREE_MB": "50000",
            "ENT_STATE": str(state), "WT_LOG": str(tmp_path / "wt.log"),
            "ENTANGIBLE_START_WAIT": "3", "ENTANGIBLE_READY_SETTLE": "1",
            "RQ_DATA_DIR": str(tmp_path / "data"), "RQ_UMAMI": "0",
        }
        e.pop("DISPLAY", None)
        e.update(extra or {})
        return e

    def run(args=(), extra=None, script=_LAUNCHER):
        return subprocess.run(["bash", script, *args], capture_output=True, text=True,
                              env=env(extra), stdin=subprocess.DEVNULL, timeout=120,
                              start_new_session=True)

    def calls(all_=False):
        """The calls that change something (status and doctor only read)."""
        f = state / "calls"
        lines = f.read_text().splitlines() if f.exists() else []
        return lines if all_ else [c for c in lines if c not in ("status", "doctor")]

    def setup_done():
        """A finished install: service set up, bundle and stamp match."""
        (state / "installed").write_text("true")
        (state / "bundle").write_text("booth-v2")
        stamp = home / ".cache" / "rasqberry" / "entangible.rasqberry"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text("unknown booth-v2\n")   # the test checkout is no git repo

    run.env = env
    run.home = home
    run.checkout = checkout
    run.state = state
    run.calls = calls
    run.setup_done = setup_done
    run.wt_log = tmp_path / "wt.log"
    run.data = tmp_path / "data"
    return run


class _Pty:
    """The launcher on a pseudo terminal, as in a demo's window."""

    def __init__(self, env):
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # pragma: no cover - child
            os.execvpe("bash", ["bash", _LAUNCHER], env)
        self.out = b""

    def expect(self, text, timeout=30):
        end = time.time() + timeout
        while text.encode() not in self.out:
            if time.time() > end:
                raise AssertionError("no %r in:\n%s" % (text, self.out.decode(errors="replace")))
            r, _, _ = select.select([self.fd], [], [], 0.2)
            if r:
                try:
                    self.out += os.read(self.fd, 4096)
                except OSError:
                    break

    def send(self, data):
        os.write(self.fd, data)

    def wait(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                try:
                    while True:
                        r, _, _ = select.select([self.fd], [], [], 0.1)
                        if not r:
                            break
                        chunk = os.read(self.fd, 4096)
                        if not chunk:
                            break
                        self.out += chunk
                except OSError:
                    pass
                return os.waitstatus_to_exitcode(status)
            r, _, _ = select.select([self.fd], [], [], 0.2)
            if r:
                try:
                    self.out += os.read(self.fd, 4096)
                except OSError:
                    pass
        os.kill(self.pid, signal.SIGKILL)
        raise AssertionError("launcher did not end:\n" + self.out.decode(errors="replace"))


# --- the data ----------------------------------------------------------------------

def test_manifest_is_an_internal_big_project_pinned_on_booth_v2():
    m = _manifest()
    assert m["id"] == "entangible" and m["name"] == "Entangible"
    assert m["group"] == "projects" and m["maturity"] == "beta"
    assert m["entrypoint"] == {"working_dir": "entangible", "launcher": "rq_entangible.sh"}
    inst = m["install"]
    assert inst["repo_url"] == "https://github.com/JanLahmann/entangible.git"
    assert inst["ref"] == _PIN
    assert inst["marker_file"] == "deploy/rasqberry/entangible"
    assert inst["post_install"] == inst["pre_remove"] == "rq_entangible.sh"
    assert inst["download_all"] is False
    assert inst["download"]["download_mb"] > 0 and inst["download"]["time"]
    # the camera is named where people choose the demo
    assert "camera" in m["description"].lower() and len(m["description"]) <= 200
    assert m["needs_hw"]["leds"] is False and m["loop_ok"] is False
    # an internal demo, not a catalogue entry
    with open(os.path.join(_CFG, "known-demos.json"), encoding="utf-8") as fh:
        assert "entangible" not in {d["id"] for d in json.load(fh)["demos"]}


def test_manifest_validates():
    proc = subprocess.run([os.path.join(_BIN, "rq_demo_validate.sh"),
                           os.path.join(_MANIFESTS, "rq_demo_entangible.json")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_schema_knows_the_new_install_fields():
    with open(os.path.join(_MANIFESTS, "rq_demo_schema.json"), encoding="utf-8") as fh:
        props = json.load(fh)["properties"]["install"]["properties"]
    assert props["pre_remove"]["type"] == "string"
    assert props["download_all"]["type"] == "boolean"


def test_desktop_entry_icon_and_build_list():
    entry = open(os.path.join(_CFG, "desktop-bookmarks", "entangible.desktop")).read()
    assert "Exec=/usr/bin/rq_hold_on_error.sh /usr/bin/rq_demo_run.sh entangible\n" in entry
    assert "Name=Entangible\n" in entry and "Comment=(beta) " in entry
    assert "Icon=/usr/share/icons/rasqberry/entangible.svg\n" in entry
    assert os.path.isfile(os.path.join(_ROOT, "desktop-icons", "entangible.svg"))
    stage = open(os.path.join(_ROOT, "stage-RQB2", "06-desktop-integration", "00-run-chroot.sh")).read()
    assert stage.count("|entangible|") == 2
    groups = json.load(open(os.path.join(_MANIFESTS, "demo-groups.json")))
    projects = [g for g in groups["groups"] if g["id"] == "projects"][0]
    assert "Entangible" in projects["menu"]


# --- install (post_install) and exit codes -------------------------------------------

def test_path_mode_installs_and_records_the_setup(ent):
    proc = ent(["--path", str(ent.checkout)])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls() == ["install --no-enable"]
    stamp = ent.home / ".cache" / "rasqberry" / "entangible.rasqberry"
    assert stamp.read_text().split()[1] == "booth-v2"


@pytest.mark.parametrize("rc, text", [
    (130, "was stopped"),
    (4, "could not download"),
    (5, "needs Raspberry Pi OS Trixie"),
    (1, "failed (exit 1)"),
])
def test_path_mode_passes_the_exit_code_on(ent, rc, text):
    (ent.state / "install_rc").write_text(str(rc))
    proc = ent(["--path", str(ent.checkout)])
    assert proc.returncode == rc
    assert text in proc.stdout + proc.stderr
    assert not (ent.home / ".cache" / "rasqberry" / "entangible.rasqberry").exists()


def test_start_ctrl_c_during_install_ends_with_130_and_starts_nothing(ent):
    (ent.state / "install_rc").write_text("130")
    proc = ent(extra={"RQ_CONFIRMED_DEMO": "entangible"})
    assert proc.returncode == 130, proc.stdout + proc.stderr
    assert ent.calls() == ["install --no-enable"]


def test_start_failed_install_is_an_error_with_the_reason(ent):
    (ent.state / "install_rc").write_text("4")
    proc = ent(extra={"RQ_CONFIRMED_DEMO": "entangible", "RQ_ERROR_FILE": str(ent.state / "err")})
    assert proc.returncode == 1
    assert "could not download" in (ent.state / "err").read_text()
    assert "start" not in ent.calls()


def test_first_start_asks_before_installing(ent):
    proc = ent(extra={"WT_RC": "1"})          # "Not now"
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls() == []
    dialog = ent.wt_log.read_text()
    assert "Download Entangible?" in dialog and "100 MB" in dialog
    assert "1-3 minutes" in dialog and "cache" not in dialog


def test_with_a_warm_cache_on_data_the_question_says_less(ent):
    # rig recheck 2026-10-11: after a Remove the bundle, uv and the wheels
    # come from /data; only the checkout is downloaded
    cached = _manifest()["install"]["download"]["cached"]
    bundle = ent.data / cached["path"]
    bundle.parent.mkdir(parents=True)
    bundle.write_text("tar")
    proc = ent(extra={"WT_RC": "1"})          # "Not now"
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dialog = ent.wt_log.read_text()
    assert "about 5 MB" in dialog and "100 MB" not in dialog
    assert "half a minute (most of it from the cache on this card)" in dialog


def test_the_cache_check_names_one_bundle_tag():
    # web/<tag>/entangible-web-<tag>.tar.gz (Entangible's cache layout); the
    # tag is the pin's deploy/rasqberry/BUNDLE_TAG: change both together
    cached = _manifest()["install"]["download"]["cached"]
    parts = cached["path"].split("/")
    assert parts[:4] == ["rasqberry", "cache", "entangible", "web"]
    assert parts[5] == "entangible-web-%s.tar.gz" % parts[4]
    assert 0 < cached["download_mb"] < _manifest()["install"]["download"]["download_mb"]


@pytest.mark.parametrize("why", ["bundle", "stamp", "uninstalled"])
def test_start_installs_again_when_the_setup_does_not_match(ent, why):
    ent.setup_done()
    if why == "bundle":
        (ent.state / "bundle").write_text("booth-v1")       # an older web app
    elif why == "stamp":
        (ent.home / ".cache" / "rasqberry" / "entangible.rasqberry").write_text("abc booth-v2\n")
    else:
        (ent.state / "installed").write_text("false")       # e.g. after an A/B update
    proc = ent(extra={"RQ_CONFIRMED_DEMO": "entangible"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls()[0] == "install --no-enable"


def test_a_matching_setup_is_not_installed_again(ent):
    ent.setup_done()
    proc = ent()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls() == ["start"]
    assert not ent.wt_log.exists()           # no download question


def test_a_failed_start_is_an_error_and_130_stays_130(ent):
    ent.setup_done()
    (ent.state / "start_rc").write_text("1")
    assert ent().returncode == 1
    (ent.state / "start_rc").write_text("130")
    assert ent().returncode == 130


# --- what the window shows (status JSON) ---------------------------------------------

def test_without_a_terminal_it_shows_the_addresses_and_keeps_running(ent):
    ent.setup_done()
    (ent.state / "ready").write_text("true")
    proc = ent()
    out = proc.stdout
    assert proc.returncode == 0, out + proc.stderr
    assert "https://192.168.1.23:8443/?connect=1" in out
    assert "https://localhost:8443/?kiosk&connect=1" in out
    assert "QR:-t ANSIUTF8 -m 2 https://192.168.1.23:8443/?connect=1" in out
    assert "Camera: connected (cv2:0)." in out
    assert "keeps running" in out and "stop" not in ent.calls()


# --- the hotspot's address for phones (review C1) ----------------------------------
_HS_MARK = "# rq_hotspot.sh: phones on the hotspot use its address (removed when it stops)"


def _hotspot(tmp_path, ent, on, text):
    """nmcli lists the hotspot as active (or not); Entangible's settings file."""
    stubs = tmp_path / "stubs"
    _exe(stubs / "nmcli", "#!/bin/sh\n" + ("echo rasqberry-hotspot\n" if on else "")
         + 'echo "Wired connection 1"\n')
    _exe(stubs / "systemctl", f'#!/bin/sh\necho "systemctl $*" >> "{tmp_path / "systemctl.log"}"\n')
    env_file = tmp_path / "entangible.default"
    env_file.write_text(text)
    return {"RQ_HOTSPOT_ENTANGIBLE_ENV": str(env_file)}, env_file


def test_a_hotspot_that_ended_without_its_stop_no_longer_sends_phones_to_it(ent, tmp_path):
    """Pi switched off with the hotspot on, next day on the school Wi-Fi."""
    ent.setup_done()
    extra, env_file = _hotspot(tmp_path, ent, False,
                               f"QAMPOSER_PORT=8443\n{_HS_MARK}\nQAMPOSER_ADVERTISE_HOST=10.42.0.1\n")
    proc = ent(extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert env_file.read_text() == "QAMPOSER_PORT=8443\n"
    assert "start" in ent.calls()


def test_a_hotspot_started_before_entangible_was_set_up_gets_its_address(ent, tmp_path):
    ent.setup_done()
    extra, env_file = _hotspot(tmp_path, ent, True, "QAMPOSER_PORT=8443\n")
    proc = ent(extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert env_file.read_text() == f"QAMPOSER_PORT=8443\n{_HS_MARK}\nQAMPOSER_ADVERTISE_HOST=10.42.0.1\n"


def test_an_address_set_by_hand_stays(ent, tmp_path):
    ent.setup_done()
    for on in (True, False):
        extra, env_file = _hotspot(tmp_path, ent, on, "QAMPOSER_ADVERTISE_HOST=booth.local\n")
        assert ent(extra=extra).returncode == 0
        assert env_file.read_text() == "QAMPOSER_ADVERTISE_HOST=booth.local\n"


def test_a_camera_that_is_only_briefly_connected_counts_as_none(ent):
    # rig test 2026-10-11, F1: ready is true for ~2 s after the start, also
    # without a camera
    ent.setup_done()
    (ent.state / "ready_seq").write_text("true\ntrue\nfalse\n")
    proc = ent(extra={"ENTANGIBLE_READY_SETTLE": "5"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Camera: none found (cv2:0)" in proc.stdout
    assert "Camera: connected" not in proc.stdout


def test_a_camera_that_stays_connected_is_connected(ent):
    ent.setup_done()
    (ent.state / "ready_seq").write_text("true\n")
    proc = ent(extra={"ENTANGIBLE_READY_SETTLE": "2"})
    assert proc.returncode == 0
    assert "Camera: connected (cv2:0)." in proc.stdout


def test_without_a_camera_it_starts_and_says_so(ent):
    ent.setup_done()
    (ent.state / "ready").write_text("false")
    proc = ent()
    assert proc.returncode == 0
    assert "Camera: none found (cv2:0)" in proc.stdout
    assert "Connect a USB webcam or the Pi camera" in proc.stdout
    assert "QAMPOSER_SOURCE" not in proc.stdout


def test_a_camera_source_that_does_not_fit_shows_doctors_hint(ent):
    ent.setup_done()
    (ent.state / "ready").write_text("false")
    hint = ("QAMPOSER_SOURCE=cv2:0, but this Pi has a Pi Camera Module - set "
            "QAMPOSER_SOURCE=picamera2 in /etc/default/entangible, then: entangible restart")
    (ent.state / "hint").write_text(hint)
    proc = ent()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "  " + hint in proc.stdout and "hint:" not in proc.stdout
    assert "Connect a USB webcam" not in proc.stdout
    assert "doctor" in ent.calls(all_=True)


def test_install_is_on_demand_and_the_launcher_starts_the_service(ent):
    # install --no-enable leaves the service stopped (and off at boot);
    # status carries "enabled" as its last field
    proc = ent(extra={"RQ_CONFIRMED_DEMO": "entangible"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls() == ["install --no-enable", "start"]
    assert "Entangible is running." in proc.stdout
    src = open(_LAUNCHER).read()
    assert "systemctl" not in src          # no disable workaround: --no-enable does it


def test_without_a_network_no_qr_code(ent):
    ent.setup_done()
    (ent.state / "visitor").write_text("https://localhost:8443/?connect=1")
    proc = ent()
    assert proc.returncode == 0
    assert "not on a network" in proc.stdout and "QR:" not in proc.stdout


def test_a_status_that_is_no_json_counts_as_not_set_up(ent):
    ent.setup_done()
    (ent.state / "status_raw").write_text("entangible: oops\n")
    proc = ent(extra={"RQ_CONFIRMED_DEMO": "entangible"})
    # installs, then the service never reports running: an error, and it is stopped
    assert proc.returncode == 1
    assert ent.calls()[0] == "install --no-enable" and ent.calls()[-1] == "stop"
    assert "stopped while starting" in proc.stderr


def test_a_service_that_never_answers_is_stopped_again(ent):
    ent.setup_done()
    (ent.state / "health").write_text("down")
    proc = ent()
    assert proc.returncode == 1
    assert ent.calls() == ["start", "stop"]
    assert "journalctl -u entangible-host" in proc.stderr


def test_the_booth_screen_opens_in_a_browser_of_its_own(ent):
    ent.setup_done()
    proc = ent(extra={"DISPLAY": ":0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    deadline = time.time() + 5
    browser = ent.state / "browser"
    while not browser.exists() and time.time() < deadline:
        time.sleep(0.1)
    args = browser.read_text()
    assert "--user-data-dir=" in args and "--ignore-certificate-errors" in args
    assert args.strip().endswith("https://localhost:8443/?kiosk&connect=1")
    # the whole screen (rig recheck 2026-10-11: half of it, or 480 px off):
    # a class no labwc rule matches, at 0,0 at the screen's size; F11 still
    # leaves full screen (no --kiosk)
    assert "--class=entangible-booth" in args and "--start-fullscreen" in args
    assert "--window-position=0,0 --window-size=1920,1080" in args
    assert "--kiosk" not in args


def test_without_a_screen_size_the_booth_screen_still_opens_full_screen(ent):
    ent.setup_done()
    os.remove(os.path.join(ent.env()["PATH"].split(":")[0], "wlr-randr"))
    proc = ent(extra={"DISPLAY": ":0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    deadline = time.time() + 5
    browser = ent.state / "browser"
    while not browser.exists() and time.time() < deadline:
        time.sleep(0.1)
    args = browser.read_text()
    assert "--start-fullscreen" in args and "--window-size" not in args


# --- stopping (Enter, Ctrl+C) --------------------------------------------------------

def test_enter_stops_the_service(ent):
    ent.setup_done()
    p = _Pty(ent.env())
    p.expect(_STOP_LINE)
    p.send(b"\n")
    assert p.wait() == 0
    assert ent.calls() == ["start", "stop"]
    assert (ent.state / "running").read_text().strip() == "false"


def test_ctrl_c_stops_the_service_with_130(ent):
    ent.setup_done()
    p = _Pty(ent.env())
    p.expect(_STOP_LINE)
    p.send(b"\x03")
    assert p.wait() == 130
    assert ent.calls()[-1] == "stop"


def test_a_service_already_running_is_stopped_with_the_window(ent):
    ent.setup_done()
    (ent.state / "running").write_text("true")   # it starts with the Pi
    p = _Pty(ent.env())
    p.expect(_STOP_LINE)
    p.send(b"\n")
    assert p.wait() == 0
    assert ent.calls() == ["stop"]


def test_stopped_elsewhere_the_window_ends_without_stopping_again(ent):
    ver = subprocess.run(["bash", "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True,
                         text=True).stdout.strip()
    if int(ver or 0) < 4:
        pytest.skip("bash 4+ needed (read -t timeouts return > 128)")
    ent.setup_done()
    p = _Pty(ent.env())
    p.expect(_STOP_LINE)
    (ent.state / "running").write_text("false")
    p.expect("Entangible was stopped.", timeout=15)
    assert p.wait() == 0
    assert ent.calls() == ["start"]


# --- the engine, Remove a demo and Download all ---------------------------------------

def test_engine_sees_the_checkout_as_installed(ent):
    proc = ent(["entangible", "--is-installed"], script=_ENGINE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    shutil.rmtree(ent.checkout)
    assert ent(["entangible", "--is-installed"], script=_ENGINE).returncode == 1


def test_remove_takes_the_service_away_before_the_checkout(ent):
    ent.setup_done()
    proc = ent(["entangible", "--yes"], script=_REMOVE)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ent.calls() == ["uninstall --purge"]
    assert not ent.checkout.exists()
    assert not (ent.home / ".cache" / "rasqberry" / "entangible.rasqberry").exists()
    # N4: no "checkout is kept" right before the checkout is removed
    assert "is kept" not in proc.stdout and "kept: the checkout" not in proc.stdout
    assert "removed: /etc/default/entangible" in proc.stdout
    # uv is not Entangible's here: its "kept" lines stay
    assert "kept (shared tool) uv" in proc.stdout and "kept (shared) uv cache" in proc.stdout


def test_remove_takes_uv_only_when_entangible_brought_it(ent):
    uv = ent.home / ".local" / "bin" / "uv"
    cache = ent.home / ".cache" / "uv"
    for marked in (True, False):
        ent.setup_done()
        uv.parent.mkdir(parents=True, exist_ok=True)
        uv.write_text("")
        cache.mkdir(parents=True, exist_ok=True)
        mark = ent.home / ".cache" / "rasqberry" / "entangible.uv"
        if marked:
            mark.write_text("")
        proc = ent(["--remove", "--path", str(ent.checkout)])
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert uv.exists() != marked and cache.exists() != marked and not mark.exists()
        # no "uv is kept, remove it yourself" right before it is removed
        out = proc.stdout
        assert ("kept (shared tool) uv" in out) != marked
        assert ("kept (shared) uv cache" in out) != marked
        assert ("removed  uv (installed for Entangible)" in out) == marked
        # the /data cache stays, and says so
        assert "kept uv cache /data/rasqberry/cache/entangible/uv" in out


def test_install_marks_uv_it_brought(ent, tmp_path):
    # the stub install "installs" uv like Entangible's installer does
    stub = ent.checkout / "deploy" / "rasqberry" / "entangible"
    stub.write_text(stub.read_text().replace(
        'echo booth-v2 > "$S/bundle"; fi',
        'echo booth-v2 > "$S/bundle"; mkdir -p "$HOME/.local/bin"; : > "$HOME/.local/bin/uv"; '
        'chmod +x "$HOME/.local/bin/uv"; fi'))
    # a PATH without a uv of this machine (that one would not be Entangible's)
    stubs = ent.env()["PATH"].split(":")[0]
    path = ":".join([stubs, "/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    if shutil.which("jq", path=path) is None or shutil.which("uv", path=path):
        pytest.skip("needs jq, and no uv, in the system directories")
    assert ent(["--path", str(ent.checkout)], extra={"PATH": path}).returncode == 0
    assert (ent.home / ".cache" / "rasqberry" / "entangible.uv").exists()


def test_cache_on_data_is_made_for_the_user_before_install(ent):
    import getpass
    (ent.data / "rasqberry").mkdir(parents=True)
    proc = ent(["--path", str(ent.checkout)], extra={"USER": getpass.getuser()})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cache = ent.data / "rasqberry" / "cache" / "entangible"
    assert cache.is_dir() and os.access(cache, os.W_OK)
    assert cache.stat().st_uid == os.getuid()
    assert "No download cache" not in proc.stderr


def test_without_a_data_partition_no_cache_and_no_warning(ent):
    proc = ent(["--path", str(ent.checkout)])
    assert proc.returncode == 0
    assert not ent.data.exists() and "No download cache" not in proc.stderr


def test_window_transcript_does_not_overwrite_entangibles_log():
    src = open(os.path.join(_BIN, "rq_hold_on_error.sh")).read()
    assert 'entangible) name="$name-window"' in src


def test_download_all_leaves_it_out(ent):
    shutil.rmtree(ent.checkout)              # not downloaded
    proc = ent(["--list"], extra={"RQ_DEMO_ENGINE": "/bin/false"}, script=_DL)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    ids = {line.split("\t")[0] for line in proc.stdout.splitlines()}
    assert "entangible" not in ids and "grok-bloch" in ids


def test_back_to_the_window_hint_works_in_full_screen():
    # N2: the full-screen booth hides the taskbar: F11 first
    src = open(_LAUNCHER).read()
    assert "press F11 to leave full screen, then click this window in the taskbar" in src
