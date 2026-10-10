"""
The Demo Loop shows the demos the person chose (Jan, 2026-10-05).

- DEMO_LOOP_DEMOS: "all" (as shipped) or a comma-separated list of the four
  loop demos; anything unknown or empty means all.
- rq_demo_loop.sh --choose: a checklist pre-ticked with the saved choice;
  "All demos" or every demo ticked saves "all"; nothing ticked saves nothing.
  With "all" saved, "All demos" is ticked too and the demo ticks decide.
- The loop runs only the chosen demos, in loop order; the menu offers
  "Start" and "Choose the demos" and says what is chosen.
- R-123: shipped manifests with "loop_ok": true and a script or python
  entrypoint join the loop after the LED demos (Quantum Fractals); one that
  needs a screen is left out without one. --at-login asks nothing, and the
  menu switches "Start the Demo Loop at login" (DEMO_LOOP_AT_LOGIN).
"""

import os
import shutil
import stat
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_LOOP = os.path.join(_BIN, "rq_demo_loop.sh")

sys.path.insert(0, _HERE)
from test_raspi_config_menu import menu_env  # noqa: E402,F401

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required")

LED = ["ibm-logo", "quantum-lights-out", "quantum-raspberry-tie", "rasq-led"]
ALL = LED + ["quantum-fractals"]


def _exe(path, text):
    path.write_text("#!/bin/bash\n" + text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def loop(tmp_path):
    """rq_demo_loop.sh with its own env file, stub demos and stub tools."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    ran = tmp_path / "ran.log"
    wt = tmp_path / "wt.log"
    _exe(stubs / "id", 'if [ "$1" = -u ]; then echo 0; else exec /usr/bin/id "$@"; fi\n')
    _exe(stubs / "sudo", '[ "$1" = -n ] && shift\nexec "$@"\n')
    _exe(stubs / "timeout", 'shift\nexec "$@"\n')
    _exe(stubs / "pkill", "exit 0\n")
    _exe(stubs / "sleep", "exit 0\n")
    _exe(stubs / "whiptail", f'{{ for a in "$@"; do printf "%s\\n" "$a"; done; echo @@; }} >> "{wt}"\n'
                             'printf "%s" "${WT_REPLY:-}" >&2\nexit "${WT_RC:-0}"\n')
    for name in ("rq_led_ibm_demo.sh", "rq_rasq_led.sh"):
        _exe(bindir / name, f'echo "{name}" >> "{ran}"\n')
    _exe(bindir / "rq_demo_run.sh", f'case "$2" in --is-installed) exit 0 ;; esac\necho "$1" >> "{ran}"\n')
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(os.path.join(_CFG, "rasqberry_environment.env")).read())
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(open(os.path.join(_CFG, "rasqberry_env-config.sh")).read()
                          .replace("/usr/config/rasqberry_environment.env", str(env_file))
                          .replace('BIN_DIR="/usr/bin"', f'BIN_DIR="{bindir}"'))

    def run(*args, extra=None, saved=None):
        if saved is not None:
            with open(env_file, "a") as fh:
                fh.write(f"DEMO_LOOP_DEMOS={saved}\n")
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", RQ_CONFIG_FILE=str(env_config),
                   RQ_ENV_FILE=str(env_file), HOME=str(tmp_path), RQ_DEMO_LOOP_ROUNDS="1")
        env.pop("DISPLAY", None)        # no screen unless a test gives one
        env.update(extra or {})
        return subprocess.run(["bash", _LOOP, *args], env=env, capture_output=True, text=True,
                              stdin=subprocess.PIPE, timeout=60)

    def saved_value():
        value = None
        for line in env_file.read_text().splitlines():
            if line.startswith("DEMO_LOOP_DEMOS="):
                value = line.split("=", 1)[1]
        return value

    run.ran = ran
    run.wt = wt
    run.saved = saved_value
    run.bindir = bindir
    run.stubs = stubs
    run.tmp = tmp_path
    run.env_file = env_file
    return run


def _not_installed(loop, *missing):
    """rq_demo_run.sh stub: MISSING are not on this Pi; installs are logged."""
    _exe(loop.bindir / "rq_demo_run.sh",
         f'case "$2" in\n'
         f'  --is-installed) case " {" ".join(missing)} " in *" $1 "*) exit 1 ;; esac; exit 0 ;;\n'
         f'  --install-only) echo "install $1 auto=${{RQ_AUTO_INSTALL:-0}}" >> "{loop.ran}"; exit 0 ;;\n'
         f'esac\necho "$1 title=$RQ_WINDOW_TITLE" >> "{loop.ran}"\n')
    _exe(loop.stubs / "curl", "exit 0\n")
    tty = loop.tmp / "tty"
    tty.write_text("")
    return {"RQ_TEST_TTY": str(tty), "RQ_TEST_FREE_MB": "50000"}


def test_missing_loop_demos_are_one_question_with_the_reason(loop):
    # user test 2026-10-08, F2: one box for both, saying why
    extra = _not_installed(loop, "quantum-lights-out", "quantum-raspberry-tie")
    proc = loop(saved="all", extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    boxes = [b for b in loop.wt.read_text().split("@@") if "--yesno" in b]
    assert len(boxes) == 1
    assert "The Demo Loop shows Quantum Lights Out and Quantum Raspberry Tie, which are not on this Pi yet." in boxes[0]
    assert "about 25 MB" in boxes[0]
    ran = loop.ran.read_text().splitlines()
    # downloaded without asking again, before the loop starts
    assert ran[:2] == ["install quantum-lights-out auto=1", "install quantum-raspberry-tie auto=1"]
    assert "quantum-lights-out title=Demo Loop: Quantum Lights Out" in ran


def test_not_now_runs_the_loop_without_them(loop):
    extra = _not_installed(loop, "quantum-raspberry-tie")
    extra["WT_RC"] = "1"
    proc = loop(saved="all", extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Quantum Raspberry Tie, which is not on this Pi yet." in loop.wt.read_text()
    ran = loop.ran.read_text()
    assert "install" not in ran and "quantum-raspberry-tie" not in ran
    assert "[3/3] RasQ-LED" in proc.stdout
    plan = proc.stdout.split("Demo timings:", 1)[1].split("Controls:", 1)[0]
    assert "Raspberry Tie" not in plan


def test_nothing_left_ends_quietly(loop):
    extra = _not_installed(loop, "quantum-lights-out")
    extra["WT_RC"] = "1"
    proc = loop(saved="quantum-lights-out", extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "No demo left to show" in proc.stdout + proc.stderr


def test_the_window_keeps_the_loops_name():
    text = open(_LOOP).read()
    assert 'RQ_WINDOW_TITLE="Demo Loop${1:+: $1}"' in text
    assert "export RQ_WINDOW_TITLE" in text


def test_shipped_setting_is_all():
    env = open(os.path.join(_CFG, "rasqberry_environment.env")).read().splitlines()
    assert "DEMO_LOOP_DEMOS=all" in env


@pytest.mark.parametrize("saved,words", [
    ("all", "all demos"),
    ("", "all demos"),
    ("rasq-led,ibm-logo", "IBM Logo, RasQ-LED"),            # loop order, not saved order
    ("quantum-lights-out", "Quantum Lights Out"),
    ("quantum-fractals,ibm-logo", "IBM Logo, Quantum Fractals"),
    (",".join(LED), "IBM Logo, Quantum Lights Out, Quantum Raspberry Tie, RasQ-LED"),
    ("nonsense,also-not", "all demos"),
    (",".join(ALL), "all demos"),
])
def test_the_choice_in_words(loop, saved, words):
    proc = loop("--demos", saved=saved)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == words


def test_the_loop_runs_only_the_chosen_demos(loop):
    proc = loop(saved="rasq-led,quantum-lights-out")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert loop.ran.read_text().split() == ["quantum-lights-out", "rq_rasq_led.sh"]
    assert "[1/2] Quantum Lights Out" in proc.stdout and "[2/2] RasQ-LED" in proc.stdout
    plan = proc.stdout.split("Demo timings:", 1)[1].split("Controls:", 1)[0]
    assert "Quantum Lights Out" in plan and "RasQ-LED" in plan
    assert "IBM Logo" not in plan and "Raspberry Tie" not in plan


def test_all_runs_every_demo_in_order(loop):
    proc = loop(saved="all", extra={"DISPLAY": ":0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert loop.ran.read_text().split() == ["rq_led_ibm_demo.sh", "quantum-lights-out",
                                            "quantum-raspberry-tie", "rq_rasq_led.sh",
                                            "quantum-fractals"]
    assert "[5/5] Quantum Fractals (90s)" in proc.stdout


def test_a_demo_that_needs_a_screen_is_left_out_without_one(loop):
    proc = loop(saved="all")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Quantum Fractals needs a screen: the loop runs without it." in proc.stdout + proc.stderr
    assert "quantum-fractals" not in loop.ran.read_text()
    assert "[4/4]" in proc.stdout


def test_the_time_of_a_loop_ok_demo_can_be_set(loop):
    with open(loop.env_file, "a") as fh:
        fh.write("DEMO_LOOP_QUANTUM_FRACTALS_TIME=45\n")
    proc = loop(saved="quantum-fractals", extra={"DISPLAY": ":0"})
    assert "[1/1] Quantum Fractals (45s)" in proc.stdout


def test_only_shipped_script_demos_with_loop_ok_join():
    # Docker, browser and notebook demos could not be closed reliably
    import json
    mdir = os.path.join(_CFG, "demo-manifests")
    ok = []
    for f in sorted(os.listdir(mdir)):
        if f.startswith("rq_demo_") and f.endswith(".json"):
            m = json.load(open(os.path.join(mdir, f)))
            if m.get("loop_ok") is True:
                ok.append(m["id"])
                assert m["entrypoint"]["type"] in ("script", "python"), m["id"]
                assert int(m.get("timeout", 0)) > 0, m["id"]
    assert sorted(ok) == ["led-demos", "quantum-fractals", "quantum-lights-out",
                          "quantum-raspberry-tie", "rasq-led"]
    text = open(_LOOP).read()
    assert '.entrypoint.type == "script" or .entrypoint.type == "python"' in text
    # Fractals' own Chromium profile is stopped, not the user's browser
    assert 'cleanup_demo_processes "fractals.py" "fractals_chrome_"' in text


def test_at_login_asks_nothing_and_leaves_missing_demos_out(loop):
    extra = _not_installed(loop, "quantum-lights-out")
    proc = loop("--at-login", saved="all", extra=extra)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not loop.wt.exists() or "--yesno" not in loop.wt.read_text()
    out = proc.stdout + proc.stderr
    assert "Quantum Lights Out is not on this Pi: the loop runs without it." in out
    ran = loop.ran.read_text()
    assert "install" not in ran and "quantum-lights-out" not in ran
    assert "quantum-raspberry-tie" in ran


def test_shipped_login_setting_is_off_and_carried_over():
    env = open(os.path.join(_CFG, "rasqberry_environment.env")).read().splitlines()
    assert "DEMO_LOOP_AT_LOGIN=false" in env
    assert "DEMO_LOOP_QUANTUM_FRACTALS_TIME=90" in env
    carry = open(os.path.join(_BIN, "rq_carry_over.sh")).read()
    keys = carry.split('ENV_KEYS="', 1)[1].split('"', 1)[0].split()
    for key in [line.split("=", 1)[0] for line in env if line.startswith("DEMO_LOOP_")]:
        assert key in keys, key


def test_choose_is_pre_ticked_and_saves_the_ticks(loop):
    proc = loop("--choose", saved="ibm-logo,rasq-led",
                extra={"WT_REPLY": '"quantum-raspberry-tie" "rasq-led"'})
    assert proc.returncode == 0, proc.stderr
    assert loop.saved() == "quantum-raspberry-tie,rasq-led"
    checklist = loop.wt.read_text().split("@@")[0].splitlines()
    ticks = {checklist[i]: checklist[i + 2] for i, a in enumerate(checklist)
             if a in ALL + ["all"] and i + 2 < len(checklist)}
    assert ticks == {"ibm-logo": "ON", "quantum-lights-out": "OFF",
                     "quantum-raspberry-tie": "OFF", "rasq-led": "ON", "quantum-fractals": "OFF",
                     "all": "OFF"}
    assert "The loop shows: Quantum Raspberry Tie, RasQ-LED." in loop.wt.read_text()


@pytest.mark.parametrize("reply", ['"all"', '"ibm-logo" "all"',
                                   '"ibm-logo" "quantum-lights-out" "quantum-raspberry-tie" "rasq-led" '
                                   '"quantum-fractals"'])
def test_all_is_one_step_back(loop, reply):
    loop("--choose", saved="rasq-led", extra={"WT_REPLY": reply})
    assert loop.saved() == "all"


def test_all_saved_ticks_all_demos_and_all(loop):
    loop("--choose", saved="all", extra={"WT_REPLY": "", "WT_RC": "1"})
    checklist = loop.wt.read_text().split("@@")[0].splitlines()
    ticks = {checklist[i]: checklist[i + 2] for i, a in enumerate(checklist)
             if a in ALL + ["all"] and i + 2 < len(checklist)}
    assert set(ticks.values()) == {"ON"} and "all" in ticks


@pytest.mark.parametrize("reply, saved", [
    ('"ibm-logo" "rasq-led" "all"', "ibm-logo,rasq-led"),   # unticked demos count
    ('"all"', "all"),                                          # only "All demos" left
])
def test_with_all_saved_the_demo_ticks_decide(loop, reply, saved):
    loop("--choose", saved="all", extra={"WT_REPLY": reply})
    assert loop.saved() == saved


def test_nothing_ticked_or_cancel_changes_nothing(loop):
    loop("--choose", saved="rasq-led", extra={"WT_REPLY": ""})
    assert loop.saved() == "rasq-led"
    assert "choose at least one demo" in loop.wt.read_text()
    loop("--choose", extra={"WT_REPLY": '"ibm-logo"', "WT_RC": "1"})       # Cancel
    assert loop.saved() == "rasq-led"


def test_menu_offers_start_and_choose(menu_env):
    stubs = menu_env.tmp / "stubs"
    log = menu_env.tmp / "loop.log"
    fake_bin = menu_env.tmp / "fakebin"
    fake_bin.mkdir()
    _exe(fake_bin / "rq_demo_loop.sh",
         f'echo "loop $*" >> "{log}"\n[ "$1" = --demos ] && echo "IBM Logo, RasQ-LED"\nexit 0\n')
    proc = menu_env(f'BIN_DIR="{fake_bin}"; run_demo_loop; echo RC=$?',
                    extra_env={"WT_REPLY_menu": "START"})
    assert "RC=0" in proc.stdout, proc.stderr
    menu = menu_env.whiptail_calls()[-1]
    text = "\n".join(menu)
    assert "Now: IBM Logo, RasQ-LED" in text
    assert "Start the demo loop" in text and "Choose the demos" in text
    assert "Start the Demo Loop at login: off" in text
    assert log.read_text().splitlines() == ["loop --demos", "loop "]


def test_menu_switches_the_loop_at_login(menu_env):
    from test_raspi_config_menu import _env_value
    proc = menu_env('do_toggle_demo_loop_login; demo_loop_login_state; '
                    'do_toggle_demo_loop_login; demo_loop_login_state')
    assert proc.stdout.split()[-2:] == ["on", "off"], proc.stdout + proc.stderr
    assert _env_value(menu_env.env_file, "DEMO_LOOP_AT_LOGIN") == "false"
    boxes = "\n".join("\n".join(c) for c in menu_env.whiptail_calls())
    assert "starts at the next desktop login, instead of the browser" in boxes


def _session(monkeypatch, loop_on):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rq_desktop_session_loop",
                                                  os.path.join(_BIN, "rq_desktop_session.py"))
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    started = []
    for name, value in (("reset_chromium_exit", lambda: None), ("apply_touch_css", lambda touch: None),
                        ("touch_mode_on", lambda: False), ("screen_size", lambda: (1920, 1080)),
                        ("set_small_screen_flag", lambda small: None),
                        ("set_chromium_rule", lambda small: False),
                        ("layout_desktop", lambda size, touch: False), ("ensure_quick_exec", lambda: False),
                        ("online", lambda: True)):
        monkeypatch.setattr(ds, name, value)
    monkeypatch.setattr(ds, "env_value", lambda key, default="": (
        ("true" if loop_on else "false") if key == "DEMO_LOOP_AT_LOGIN" else default))
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: started.append(cmd))
    monkeypatch.setenv("RQ_BROWSER_DELAY", "0")
    monkeypatch.setenv("RQ_LOOP_DELAY", "0")
    assert ds.main([]) == 0
    return started


def test_login_starts_the_loop_instead_of_the_browser(monkeypatch):
    started = _session(monkeypatch, loop_on=True)
    assert started == [["x-terminal-emulator", "-e", "/usr/bin/rq_hold_on_error.sh", "-t", "Demo Loop",
                        "/usr/bin/rq_demo_loop.sh", "--at-login"]]


def test_login_opens_the_browser_when_the_loop_is_off(monkeypatch):
    started = _session(monkeypatch, loop_on=False)
    assert len(started) == 1 and started[0][0] == "/usr/bin/chromium"


def test_autologin_readme_promises_no_kiosk_mode():
    # R-126: the build README advertised a "Kiosk Mode" that does not exist
    text = open(os.path.join(_ROOT, "stage-RQB2", "03-desktop-autologin", "README.md")).read()
    assert "**Kiosk Mode**" not in text
    assert "Start the Demo Loop at login" in text
