"""
Tests for batch B3 of review 2026-10: every first install asks once (size,
time, free space; Jan's Q27), refuses on low space or no network, and a
failed download leaves nothing behind.

  * R-030 / R-166: rq_confirm_download / rq_confirm_demo_install in
    rq_common.sh, and the demo engine asking before a first install
  * R-058: update_env_var keeps the settings file when the write fails
  * R-057: a failed or unfinished install leaves no half checkout
  * R-087: a checkout counts as installed even when its flag says otherwise
  * R-029: rq_hold_on_error.sh keeps an icon's window open on failure
  * R-107: --help does not act

whiptail is a stub that logs its arguments; RQ_TEST_TTY points the dialogs
at a file instead of /dev/tty. No Raspberry Pi, network or root needed
(sudo is a stub that runs the command).
"""

import os
import shutil
import stat
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_COMMON = os.path.join(_BIN, "rq_common.sh")
_ENGINE = os.path.join(_BIN, "rq_demo_run.sh")
_ENV_CONFIG = os.path.join(_ROOT, "RQB2-config", "rasqberry_env-config.sh")
_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None or shutil.which("git") is None,
    reason="bash, jq and git are required")

_WHIPTAIL = r'''#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
exit "${WT_RC:-0}"
'''


def _exe(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def box(tmp_path):
    """A fake home, env file, env-config, stub tools and a runner."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _exe(stubs / "whiptail", _WHIPTAIL)
    _exe(stubs / "sudo", '#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    # reachability checks answer without the network
    _exe(stubs / "curl", '#!/bin/sh\nexit 0\n')
    home = tmp_path / "home"
    home.mkdir()
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(_ENV_CONFIG).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('USER_HOME="$(eval echo ~${SUDO_USER})"', f'USER_HOME="{home}"'))
    tty = tmp_path / "tty"
    tty.write_text("")
    wt_log = tmp_path / "wt.log"

    def run(args, extra=None, script=None, stdin=""):
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": str(home),
            "USER": "rasqberry",
            "RQ_CONFIG_FILE": str(env_config),
            "RQ_ENV_FILE": str(env_file),
            "RQ_TEST_TTY": str(tty),
            "RQ_TEST_FREE_MB": "50000",
            "RQ_ERROR_FILE": str(tmp_path / "err.txt"),
            "WT_LOG": str(wt_log),
        }
        env.update(extra or {})
        cmd = ["bash", "-c", script] if script else ["bash", *args]
        # start_new_session: no controlling terminal, as from a desktop icon
        # without one - the dialogs must use RQ_TEST_TTY, not /dev/tty
        return subprocess.run(cmd, capture_output=True, text=True, env=env, input=stdin,
                              timeout=120, start_new_session=True)

    def dialogs():
        if not wt_log.exists():
            return []
        calls, cur = [], []
        for line in wt_log.read_text().splitlines():
            if line == "@@":
                calls.append(cur)
                cur = []
            else:
                cur.append(line)
        return calls

    def err():
        f = tmp_path / "err.txt"
        return f.read_text() if f.exists() else ""

    run.home = home
    run.env_file = env_file
    run.stubs = stubs
    run.tmp = tmp_path
    run.dialogs = dialogs
    run.err = err
    return run


def _common(box, code, extra=None):
    return box(None, extra=extra, script=f'. "{_COMMON}"; load_rqb2_env; {code}')


def _env_value(env_file, key):
    value = None
    for line in env_file.read_text().splitlines():
        if line.startswith(key + "="):
            value = line.split("=", 1)[1]
    return value


# --- the consent dialog (R-030, Q27) -----------------------------------------

def test_dialog_names_what_size_time_and_free_space(box):
    proc = _common(box, 'rq_confirm_download "Demo X" 1200 2300 --what "Docker image" '
                        '--time "15 minutes" --peak 5600 --url ""; echo "RC=$?"')
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    (call,) = box.dialogs()
    text = call[call.index("--yesno") + 1]
    assert "Demo X is not on this Pi yet." in text
    assert "What:      Docker image" in text
    assert "about 1.2 GB (needs the internet)" in text
    assert "about 2.3 GB (7.9 GB while installing) on the SD card" in text
    assert "about 15 minutes" in text
    assert "50.0 GB now, 47.7 GB afterwards" in text
    assert call[call.index("--yes-button") + 1] == "Download"
    assert call[call.index("--no-button") + 1] == "Not now"


def test_not_now_returns_1(box):
    proc = _common(box, 'rq_confirm_download X 10 10 --url ""; echo "RC=$? $RQ_CONSENT_MSG"',
                   extra={"WT_RC": "1"})
    assert "RC=1 X was not downloaded." in proc.stdout, proc.stdout + proc.stderr


def test_low_space_is_refused_before_asking(box):
    proc = _common(box, 'rq_confirm_download X 900 3900 --url ""; echo "RC=$? $RQ_CONSENT_MSG"',
                   extra={"RQ_TEST_FREE_MB": "4000"})
    assert "RC=2 Not enough free space for X" in proc.stdout, proc.stdout + proc.stderr
    assert "about 3.9 GB plus 1.0 GB to spare, and 4.0 GB is free" in proc.stdout
    assert "Remove a demo" in proc.stdout
    assert box.dialogs() == []


def test_offline_is_refused_before_asking(box):
    proc = _common(box, 'rq_confirm_download X 10 10 --url https://ghcr.io/v2/; echo "RC=$? $RQ_CONSENT_MSG"',
                   extra={"RQ_TEST_OFFLINE": "1"})
    assert "RC=3" in proc.stdout and "ghcr.io cannot be reached" in proc.stdout, proc.stdout
    assert box.dialogs() == []


def test_auto_install_skips_the_question_but_not_the_space_check(box):
    proc = _common(box, 'rq_confirm_download X 10 10 --url ""; echo "RC=$?"',
                   extra={"RQ_AUTO_INSTALL": "1"})
    assert "RC=0" in proc.stdout and box.dialogs() == []
    proc = _common(box, 'rq_confirm_download X 10 3000 --url ""; echo "RC=$?"',
                   extra={"RQ_AUTO_INSTALL": "1", "RQ_TEST_FREE_MB": "3500"})
    assert "RC=2" in proc.stdout


def test_without_a_terminal_it_does_not_download(box):
    proc = _common(box, 'rq_confirm_download X 10 10 --url ""; echo "RC=$? $RQ_CONSENT_MSG"',
                   extra={"RQ_TEST_TTY": str(box.tmp / "no" / "tty")})
    assert "RC=4" in proc.stdout and "desktop icon or the RasQberry menu" in proc.stdout


def test_demo_consent_uses_the_manifest_and_asks_once(box):
    proc = _common(box, 'rq_confirm_demo_install doqumentation; echo "RC=$? [$RQ_CONFIRMED_DEMO]"; '
                        'rq_confirm_demo_install doqumentation; echo "RC2=$?"')
    assert "RC=0 [doqumentation]" in proc.stdout, proc.stdout + proc.stderr
    assert "RC2=0" in proc.stdout
    (call,) = box.dialogs()
    text = call[call.index("--yesno") + 1]
    assert "Workshop & Qiskit Server is not on this Pi yet." in text
    assert "about 1.3 GB" in text and "5.4 GB on the SD card" in text


def test_registry_url_of_an_image():
    script = f'. "{_COMMON}"; rq_image_registry_url ghcr.io/a/b:c; rq_image_registry_url python:3.11; ' \
             f'rq_image_registry_url localhost:5000/x'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout.split()
    assert out == ["https://ghcr.io/v2/", "https://registry-1.docker.io/v2/", "https://localhost:5000/v2/"]


# --- the engine asks before a first install ----------------------------------

def test_engine_asks_and_not_now_downloads_nothing(box):
    proc = box([_ENGINE, "quantum-paradoxes", "--install-only"], extra={"WT_RC": "1"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "was not downloaded" in proc.stdout
    assert not (box.home / "RasQberry-Two" / "demos" / "quantum-paradoxes").exists()
    (call,) = box.dialogs()
    assert "Quantum Paradoxes is not on this Pi yet." in call[call.index("--yesno") + 1]


def test_engine_refuses_on_low_space_with_the_reason(box):
    proc = box([_ENGINE, "quantum-mixer", "--install-only"], extra={"RQ_TEST_FREE_MB": "3000"})
    assert proc.returncode == 1
    assert "Not enough free space for Quantum Mixer" in box.err()
    assert box.dialogs() == []


def test_engine_offline_fails_fast_with_the_reason(box):
    proc = box([_ENGINE, "grok-bloch", "--install-only"], extra={"RQ_TEST_OFFLINE": "1"})
    assert proc.returncode == 1
    assert "cannot be reached" in box.err() and "internet" in box.err()


def _local_repo(tmp_path, files):
    repo = tmp_path / "upstream"
    repo.mkdir()
    for name, text in files.items():
        (repo / name).write_text(text)
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "x"], check=True)
    return repo


def _user_manifest(box, manifest):
    d = box.home / ".local" / "config" / "demo-manifests"
    d.mkdir(parents=True, exist_ok=True)
    import json
    (d / f"rq_demo_{manifest['id']}.json").write_text(json.dumps(manifest))


def test_failure_after_the_download_leaves_no_checkout(box):
    # R-057: a tree with its marker file made a half-installed demo look
    # installed; it then ran unpatched or half set up
    repo = _local_repo(box.tmp, {"marker.txt": "x"})
    _user_manifest(box, {
        "id": "b3-test", "name": "B3 Test", "category": "tool", "description": "t",
        "entrypoint": {"type": "python", "script": "x.py", "working_dir": "b3-test"},
        "install": {"repo_url": f"file://{repo}", "marker_file": "marker.txt",
                    "post_install": "no-such-setup-step.sh",
                    "download": {"download_mb": 1, "url": f"file://{repo}"}}})
    proc = box([_ENGINE, "b3-test", "--install-only"])
    assert proc.returncode != 0
    assert not (box.home / "RasQberry-Two" / "demos" / "b3-test").exists(), proc.stdout + proc.stderr
    # and the next start asks again instead of running a broken demo
    proc = box([_ENGINE, "b3-test", "--is-installed"])
    assert proc.returncode == 1


def test_successful_install_sets_the_flag(box):
    repo = _local_repo(box.tmp, {"marker.txt": "x"})
    _user_manifest(box, {
        "id": "b3-ok", "name": "B3 OK", "category": "tool", "description": "t",
        "entrypoint": {"type": "python", "script": "x.py", "working_dir": "b3-ok"},
        "install": {"repo_url": f"file://{repo}", "marker_file": "marker.txt",
                    "installed_flag": "GROK_BLOCH_INSTALLED",
                    "download": {"download_mb": 1, "url": f"file://{repo}"}}})
    proc = box([_ENGINE, "b3-ok", "--install-only"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (box.home / "RasQberry-Two" / "demos" / "b3-ok" / "marker.txt").exists()
    assert _env_value(box.env_file, "GROK_BLOCH_INSTALLED") == "true"


def test_checkout_counts_as_installed_and_the_flag_follows(box):
    # R-087: Lights Out had no flag; an older engine did not set it
    d = box.home / "RasQberry-Two" / "demos" / "Quantum-Lights-Out"
    d.mkdir(parents=True)
    (d / "lights_out.py").write_text("")
    assert box([_ENGINE, "quantum-lights-out", "--is-installed"]).returncode == 0
    assert _env_value(box.env_file, "QUANTUM_LIGHTS_OUT_INSTALLED") == "false"   # a query writes nothing
    proc = box([_ENGINE, "quantum-lights-out", "--install-only"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _env_value(box.env_file, "QUANTUM_LIGHTS_OUT_INSTALLED") == "true"
    assert box.dialogs() == []


def test_docker_demo_is_installed_when_its_image_is(box):
    _exe(box.stubs / "docker",
         '#!/bin/sh\ncase "$1 $2" in "info "*) exit 0 ;; "image inspect") [ -n "$HAVE_IMAGE" ] ;; *) exit 1 ;; esac\n')
    assert box([_ENGINE, "doqumentation", "--is-installed"]).returncode == 1
    assert box([_ENGINE, "doqumentation", "--is-installed"], extra={"HAVE_IMAGE": "1"}).returncode == 0
    # a removed image is missing although the flag still says "installed"
    with open(box.env_file, "a") as fh:
        fh.write("QUANTUM_MIXER_INSTALLED=true\n")
    assert box([_ENGINE, "quantum-mixer", "--is-installed"]).returncode == 1


# --- shared helpers ---------------------------------------------------------

def test_env_write_failure_keeps_the_settings(box):
    # R-058: a write that fails (full disk) emptied the whole file
    before = box.env_file.read_text()
    _exe(box.stubs / "tee", "#!/bin/sh\ncat >/dev/null\nexit 1\n")
    proc = _common(box, 'update_env_var LED_LAYOUT quad-4x12; echo "RC=$?"')
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "settings were left as they were" in proc.stderr
    assert box.env_file.read_text() == before
    assert not [p for p in os.listdir(box.tmp) if p.startswith(".rasqberry_environment")]


def test_env_write_keeps_special_characters_and_appends(box):
    proc = _common(box, 'update_env_var GIT_REF_X "a/b|c\\d"; update_env_var LED_LAYOUT quad-4x12; echo "RC=$?"')
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    assert _env_value(box.env_file, "GIT_REF_X") == "a/b|c\\d"
    assert _env_value(box.env_file, "LED_LAYOUT") == "quad-4x12"


def test_failed_fetch_removes_the_destination(box, tmp_path):
    real_git = shutil.which("git")
    _exe(box.stubs / "git", f'#!/bin/sh\ncase " $* " in *" fetch "*) exit 128 ;; esac\nexec "{real_git}" "$@"\n')
    dest = tmp_path / "demo"
    proc = _common(box, f'fetch_pinned_repo https://example.invalid/x.git {"a" * 40} "{dest}"; echo "RC=$?"')
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert not dest.exists()


def test_help_guard_prints_the_header_and_does_nothing_else(box):
    proc = box([os.path.join(_BIN, "rq_led_painter.sh"), "--help"],
               extra={"RQ_CONFIG_FILE": "/nonexistent"})
    assert proc.returncode == 0, proc.stderr
    assert "rq_led_painter.sh --path DIR" in proc.stdout
    assert not (box.home / "RasQberry-Two").exists()


# --- R-029: the icon window stays open on failure ----------------------------

_HOLD = os.path.join(_BIN, "rq_hold_on_error.sh")


def test_hold_waits_and_names_the_report_on_failure(box):
    proc = box([_HOLD, "sh", "-c", "echo boom; exit 4"], stdin="\n")
    assert proc.returncode == 4
    assert "boom" in proc.stdout
    assert "stopped with an error (status 4)" in proc.stdout
    assert "rq_info.sh --report" in proc.stdout
    assert "Press Enter to close this window." in proc.stdout


@pytest.mark.parametrize("rc", [0, 130])
def test_hold_closes_quietly_on_success_or_ctrl_c(box, rc):
    proc = box([_HOLD, "sh", "-c", f"exit {rc}"])
    assert proc.returncode == rc
    assert "Press Enter" not in proc.stdout


# --- the catalogue says who provides a demo (R-163) ------------------------------

_ADD = os.path.join(_BIN, "rq_demo_add_external.sh")


@pytest.mark.parametrize("demo_id,provider", [
    ("traqmania", "Provided by Jan-R. Lahmann, who also makes RasQberry Two, as part of the Fun with Quantum family."),
    ("sap-quantum-learning", "Provided by SAP."),
    ("sap-quantum-led", "Provided by SAP."),
])
def test_catalogue_question_names_the_provider_from_the_registry(box, demo_id, provider):
    proc = box([_ADD, demo_id], extra={"WT_RC": "1"})       # "No": nothing installed
    assert proc.returncode != 0
    text = "\n".join(box.dialogs()[0])
    assert provider in text
    assert "external contributor" not in text and "NOT part of" not in text
    assert "Its makers maintain the demo" in text
    assert not (box.home / "RasQberry-Two/demos").exists()


def test_every_catalogue_entry_names_its_provider():
    import json
    registry = json.load(open(os.path.join(_ROOT, "RQB2-config", "known-demos.json")))["demos"]
    assert all(d.get("provider") for d in registry), [d["id"] for d in registry if not d.get("provider")]


def test_a_failed_pip_install_is_said_in_plain_words():
    add = open(_ADD).read()
    assert "pip failed" not in add
    assert "could not be installed, so the demo was not installed" in add
