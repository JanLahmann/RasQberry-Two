"""
Tests for RQB2-config/RQB2_menu.sh, the RasQberry menu that raspi-config SOURCES
into its own /bin/sh (dash) process (review 2026-10, batch B1).

What broke raspi-config itself:
  * R-001: reloading the env file set INTERACTIVE=true / ASK_TO_REBOOT=0 /
    CONFIG=... inside raspi-config, which then ran S4 Hostname non-interactively
    (empty hostname) and failed SSH/VNC.
  * R-017 / R-018: a file-scope IFS without a space broke raspi-config's
    "Network Proxy -> All" and the LED Output Targets checklist.
  * R-120: a cache dash cannot parse stopped all of raspi-config.
  * R-024: menu items starting with "-" made whiptail fail ("unknown option").

The menu runs here under dash with stub whiptail/sudo/script/setsid, an env
file in a temp dir (RQ_CONFIG_FILE) and no Raspberry Pi.

The optional test at the end runs the REAL raspi-config (bookworm, the version
the image ships) patched with raspi-config.diff, when RQ_TEST_RASPI_CONFIG
points to a copy of it (the code-quality workflow downloads it).
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_MENU = os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")
_ENV_CONFIG = os.path.join(_ROOT, "RQB2-config", "rasqberry_env-config.sh")
_ENV = os.path.join(_ROOT, "RQB2-config", "rasqberry_environment.env")
_DIFF = os.path.join(_ROOT, "RQB2-config", "raspi-config.diff")
_PATCHER = os.path.join(_ROOT, "RQB2-bin", "rq_patch_raspiconfig.sh")
_QRT_MANIFEST = os.path.join(_ROOT, "RQB2-config", "demo-manifests", "rq_demo_quantum-raspberry-tie.json")

_DASH = shutil.which("dash") or ("/bin/sh" if sys.platform.startswith("linux") else None)

pytestmark = pytest.mark.skipif(_DASH is None, reason="dash (raspi-config's /bin/sh) is required")

# Lines an env file on a device may still have (removed from the shipped one)
_OLD_GLOBALS = "INTERACTIVE=true\nASK_TO_REBOOT=0\nCONFIG=/leaked/config.txt\n"

# whiptail stub: logs its argv (one arg per line, records separated by "@@"),
# answers from WT_REPLY_<kind> (menu/checklist/yesno/inputbox) on stderr like
# whiptail, exits with WT_RC_<kind> (default 0), optionally sleeps first.
_WHIPTAIL = r'''#!/bin/sh
kind=other
for a in "$@"; do
  case "$a" in
    --menu) kind=menu ;; --checklist) kind=checklist ;; --yesno) kind=yesno ;;
    --inputbox) kind=inputbox ;; --msgbox) kind=msgbox ;;
  esac
done
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
eval "reply=\${WT_REPLY_$kind:-}"
eval "rc=\${WT_RC_$kind:-0}"
eval "pause=\${WT_SLEEP_$kind:-0}"
[ "$pause" != 0 ] && sleep "$pause"
[ -n "$reply" ] && printf '%s' "$reply" >&2
exit "$rc"
'''

# util-linux `script -qefc CMD LOG`: run CMD, log its output, return its status
_SCRIPT = r'''#!/bin/sh
while [ $# -gt 0 ]; do
  case "$1" in -*c) cmd="$2"; shift 2 ;; -*) shift ;; *) log="$1"; shift ;; esac
done
sh -c "$cmd" > "$log" 2>&1
'''

_PASSTHRU = '#!/bin/sh\nexec "$@"\n'
_NOOP = '#!/bin/sh\nexit 0\n'


def _write_exec(path, text):
    with open(path, "w") as fh:
        fh.write(text)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def menu_env(tmp_path):
    """A temp env file (shipped defaults + the old raspi-config lines), its
    env-config loader, stub tools on PATH, and a helper to run dash code with
    the menu sourced."""
    env_file = tmp_path / "rasqberry_environment.env"
    env_file.write_text(open(_ENV).read() + "\n" + _OLD_GLOBALS)
    env_config = tmp_path / "env-config.sh"
    env_config.write_text(
        open(_ENV_CONFIG).read().replace('/usr/config/rasqberry_environment.env', str(env_file)))
    home = tmp_path / "home"
    home.mkdir()

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _write_exec(stubs / "whiptail", _WHIPTAIL)
    _write_exec(stubs / "script", _SCRIPT)
    _write_exec(stubs / "setsid", _PASSTHRU)
    _write_exec(stubs / "sudo", _NOOP)      # rq_device_settings.sh save etc.
    _write_exec(stubs / "stty", _NOOP)      # no terminal in the test

    wt_log = tmp_path / "whiptail.log"

    def run(code, extra_env=None, stdin="\n\n\n", cache=None):
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "HOME": str(home),
            "RQ_CONFIG_FILE": str(env_config),
            "RQ_DEMO_MENU_CACHE": str(cache or (tmp_path / "no-cache.sh")),
            "RQ_DEMO_LOG": str(tmp_path / "demo.log"),
            "WT_LOG": str(wt_log),
            "TMPDIR": str(tmp_path),
        }
        env.update(extra_env or {})
        script = f'. "{_MENU}"\n{code}\n'
        return subprocess.run([_DASH, "-c", script], input=stdin, capture_output=True,
                              text=True, env=env, timeout=60)

    def whiptail_calls():
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

    run.env_file = env_file
    run.tmp = tmp_path
    run.whiptail_calls = whiptail_calls
    return run


def _env_value(env_file, key):
    value = None
    for line in env_file.read_text().splitlines():
        if line.startswith(key + "="):
            value = line.split("=", 1)[1]
    return value


# --- R-017 / R-018: no shell-wide IFS ---------------------------------------

def test_sourcing_the_menu_leaves_ifs_alone(menu_env):
    proc = menu_env("d=$(printf ' \\t\\nX'); d=${d%X}; "
                    '[ "$IFS" = "$d" ] && echo DEFAULT_IFS || echo CHANGED_IFS')
    assert "DEFAULT_IFS" in proc.stdout, proc.stdout + proc.stderr


def test_raspi_config_word_splitting_still_works(menu_env):
    # raspi-config's do_proxy: `for SCHEME in $SCHEMES` with "all"
    proc = menu_env('n=0; SCHEMES="http https ftp rsync"; for S in $SCHEMES; do n=$((n+1)); done; echo "N=$n"')
    assert "N=4" in proc.stdout, proc.stderr


def test_led_output_targets_two_ticks(menu_env):
    # R-018: confirming PHYSICAL + WEB used to collapse to one word and keep
    # only the strip; LED_VIRTUAL must follow the checklist too.
    proc = menu_env("do_led_output_menu; echo RC=$?",
                    extra_env={"WT_REPLY_checklist": '"PHYSICAL" "WEB"'})
    assert "RC=0" in proc.stdout, proc.stderr
    assert _env_value(menu_env.env_file, "LED_PHYSICAL") == "true"
    assert _env_value(menu_env.env_file, "LED_VIRTUAL") == "false"
    assert _env_value(menu_env.env_file, "LED_WEB") == "true"
    texts = "\n".join("\n".join(c) for c in menu_env.whiptail_calls())
    assert "At least one output target is required" not in texts


def test_led_output_targets_use_the_style_names(menu_env):
    # R-095: "LED panel" and "on-screen view", not "LED strip" or "matrix"
    menu_env("do_led_output_menu", extra_env={"WT_REPLY_checklist": '"PHYSICAL"'})
    texts = "\n".join("\n".join(c) for c in menu_env.whiptail_calls())
    assert "LED panel" in texts and "On-screen view" in texts
    assert "strip" not in texts.lower() and "matrix" not in texts.lower()


# --- R-001: raspi-config's globals survive every env reload ------------------

def test_initial_load_does_not_set_raspi_config_globals(menu_env):
    proc = menu_env('echo "I=${INTERACTIVE-unset} A=${ASK_TO_REBOOT-unset} C=${CONFIG-unset}"')
    assert "I=unset A=unset C=unset" in proc.stdout, proc.stdout + proc.stderr


def test_setting_change_keeps_raspi_config_interactive(menu_env):
    # what raspi-config has set by the time the RasQberry menu runs
    code = ('INTERACTIVE=True; ASK_TO_REBOOT=1; CONFIG=/boot/firmware/config.txt\n'
            'update_environment_file BROWSER_AUTOSTART false\n'
            'echo "after-update I=$INTERACTIVE A=$ASK_TO_REBOOT C=$CONFIG"\n'
            'LED_LAYOUT_VERIFIED=false; do_led_verify 2>/dev/null\n'
            'echo "after-verify I=$INTERACTIVE A=$ASK_TO_REBOOT C=$CONFIG"\n')
    proc = menu_env(code)
    assert "after-update I=True A=1 C=/boot/firmware/config.txt" in proc.stdout, proc.stdout + proc.stderr
    assert "after-verify I=True A=1 C=/boot/firmware/config.txt" in proc.stdout, proc.stdout + proc.stderr
    assert _env_value(menu_env.env_file, "BROWSER_AUTOSTART") == "false"


# --- R-093: the env writer ---------------------------------------------------

def test_env_writer_keeps_slash_and_ampersand_literal(menu_env):
    url = "https://example.org/fork/a&b.git"
    proc = menu_env(f'update_environment_file GIT_REPO_DEMO_QLO "{url}"; echo RC=$?')
    assert "RC=0" in proc.stdout, proc.stderr
    assert _env_value(menu_env.env_file, "GIT_REPO_DEMO_QLO") == url


def test_env_writer_adds_a_missing_key(menu_env):
    proc = menu_env('update_environment_file RQ_TEST_NEW_KEY yes; echo RC=$?')
    assert "RC=0" in proc.stdout, proc.stderr
    assert _env_value(menu_env.env_file, "RQ_TEST_NEW_KEY") == "yes"


def test_settings_editor_hides_raspi_config_globals_and_deprecated_keys(menu_env):
    proc = menu_env('echo "H=[$(_rq_hidden_env_keys)]"')
    hidden = proc.stdout.split("H=[", 1)[1].split("]", 1)[0].split()
    for key in ("INTERACTIVE", "ASK_TO_REBOOT", "CONFIG", "LED_VIRTUAL_MIRROR", "LED_FREQ_HZ",
                "LED_MATRIX_LAYOUT"):
        assert key in hidden, key
    for key in ("LED_PHYSICAL", "LED_VIRTUAL", "LED_LAYOUT", "LED_WEB"):
        assert key not in hidden, key


def test_settings_editor_refuses_a_value_with_a_space(menu_env):
    proc = menu_env("do_select_environment_variable; echo RC=$?",
                    extra_env={"WT_REPLY_menu": "LED_DEFAULT_BRIGHTNESS", "WT_REPLY_inputbox": "0.2 0.3"})
    assert "RC=0" in proc.stdout, proc.stderr
    assert _env_value(menu_env.env_file, "LED_DEFAULT_BRIGHTNESS") == "0.4"
    texts = "\n".join("\n".join(c) for c in menu_env.whiptail_calls())
    assert "was not saved" in texts


# --- R-024 / R-019: show_menu --------------------------------------------------

def test_menu_items_follow_double_dash(menu_env):
    # do_led_display_menu used to fail with "---1: unknown option"
    proc = menu_env("do_led_display_menu; echo RC=$?", extra_env={"WT_RC_menu": "1"})
    assert "RC=0" in proc.stdout, proc.stderr
    call = menu_env.whiptail_calls()[0]
    i = call.index("--menu")
    assert call[i + 5] == "--", call
    # separator rows have blank tags, never a tag starting with "-"
    items = call[i + 6:]
    tags = items[0::2]
    assert not [t for t in tags if t.startswith("-")], tags


def test_menu_box_leaves_room_for_the_prompt(menu_env):
    proc = menu_env('WT_WIDTH=80; WT_MENU_HEIGHT=11; show_menu "T" "line one\\nline two\\nline three" '
                    'a A b B; echo RC=$?', extra_env={"WT_RC_menu": "1"})
    assert "RC=1" in proc.stdout, proc.stderr
    call = menu_env.whiptail_calls()[0]
    i = call.index("--menu")
    height, menu_height = int(call[i + 2]), int(call[i + 4])
    # newt: prompt lines = (H-2)-4-1-L
    assert height - 7 - menu_height >= 3, call


def test_menu_error_is_not_mistaken_for_back(menu_env):
    proc = menu_env('show_menu "T" "P" a A; echo RC=$?',
                    extra_env={"WT_RC_menu": "1", "WT_REPLY_menu": "-x: unknown option"})
    assert "RC=2" in proc.stdout, proc.stdout + proc.stderr


# --- R-120: a broken demo cache ----------------------------------------------

def test_broken_cache_does_not_stop_raspi_config(menu_env):
    cache = menu_env.tmp / "cache.sh"
    cache.write_text("DEMO_MENU_ITEMS='\n\"a\" \"A\"\n'\ndispatch_demo_by_id() {\n    case \"$1\" in\n")
    proc = menu_env('echo "STATE=$_RQ_DEMO_CACHE_STATE"; type dispatch_demo_by_id >/dev/null && echo HAVE_DISPATCH',
                    cache=cache)
    assert "STATE=broken" in proc.stdout, proc.stdout + proc.stderr
    assert "HAVE_DISPATCH" in proc.stdout


def test_good_cache_is_loaded(menu_env):
    cache = menu_env.tmp / "cache.sh"
    cache.write_text("DEMO_MENU_ITEMS='\n\"a\" \"A\"\n'\ndispatch_demo_by_id() { echo \"run $1\"; }\nDEMO_COUNT=1\n")
    proc = menu_env('echo "STATE=$_RQ_DEMO_CACHE_STATE"; dispatch_demo_by_id a', cache=cache)
    assert "STATE=ok" in proc.stdout and "run a" in proc.stdout, proc.stdout + proc.stderr


# --- R-028 / R-156 / R-102: run_demo ------------------------------------------

def _demo_script(tmp_path, body):
    path = tmp_path / "demo.sh"
    path.write_text(body)
    return path


def test_console_demo_crash_is_reported(menu_env):
    _demo_script(menu_env.tmp, "echo 'starting'\necho 'RuntimeError: GPIO busy'\nexit 3\n")
    proc = menu_env(f'run_demo "T" "{menu_env.tmp}" sh demo.sh; echo "RC=$?"; echo "ERR=$RQ_LAST_DEMO_ERROR"')
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "GPIO busy" in proc.stdout
    # the stop dialog is gone for console demos (they own the terminal)
    assert not [c for c in menu_env.whiptail_calls() if "--yesno" in c]


def test_console_demo_stopped_with_ctrl_c_is_not_an_error(menu_env):
    _demo_script(menu_env.tmp, "exit 130\n")
    proc = menu_env(f'run_demo "T" "{menu_env.tmp}" sh demo.sh; echo "RC=$?"')
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr


def test_led_demo_failing_while_it_waits_is_reported(menu_env):
    # dies after the 2-second check, while the terminal waits for Enter
    _demo_script(menu_env.tmp, "sleep 3\necho 'late failure'\nexit 4\n")
    proc = menu_env(f'run_demo bg "T" "{menu_env.tmp}" sh demo.sh; echo "RC=$?"; echo "ERR=$RQ_LAST_DEMO_ERROR"',
                    stdin="")
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "late failure" in proc.stdout


def test_led_demo_stops_with_enter_like_every_demo(menu_env):
    # items 5, 33: no "Stop demo / Keep running" dialog, the same stop rule
    _demo_script(menu_env.tmp, "sleep 30\n")
    start = time.time()
    proc = menu_env(f'run_demo bg "T" "{menu_env.tmp}" sh demo.sh; echo "RC=$?"', stdin="\n")
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    assert "To stop T: press Enter or Ctrl+C, or close this window." in proc.stdout
    assert time.time() - start < 15
    assert not [c for c in menu_env.whiptail_calls() if "--yesno" in c]


def test_led_demo_wrappers_return_the_demo_status(menu_env):
    proc = menu_env('run_demo() { RQ_LAST_DEMO_ERROR=x; return 1; }; do_led_off() { return 0; }\n'
                    'do_led_demo_alert; echo "RC=$?"')
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr


# --- R-026: the engine's reason reaches the error box -------------------------

def test_engine_failure_reason_is_kept_and_explained(menu_env):
    engine = menu_env.tmp / "engine.sh"
    engine.write_text('#!/bin/sh\necho "This demo needs a screen: start it on the Pi\'s desktop or over VNC" >> "$RQ_ERROR_FILE"\nexit 1\n')
    os.chmod(engine, 0o755)
    proc = menu_env(f'run_engine_demo "{engine}"; echo "RC=$?"; echo "ERR=$RQ_LAST_DEMO_ERROR"')
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert "VNC" in proc.stdout and "SSH" in proc.stdout


def test_engine_stopped_with_ctrl_c_is_not_an_error(menu_env):
    engine = menu_env.tmp / "engine.sh"
    engine.write_text("#!/bin/sh\nexit 130\n")
    os.chmod(engine, 0o755)
    proc = menu_env(f'run_engine_demo "{engine}"; echo "RC=$?"')
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr


def test_offline_failure_is_explained(menu_env):
    proc = menu_env('_rq_explain_demo_error "Failed to fetch pinned commit abc for demo x" 1')
    assert "online" in proc.stdout


# --- R-023: Raspberry Tie runs the manifest's variants ------------------------

def test_raspberry_tie_menu_offers_the_manifest_variants():
    menu = open(_MENU).read()
    body = menu[menu.index("do_select_qrt_option() {"):]
    body = body[:body.index("\n}\n")]
    variants = [v["id"] for v in json.load(open(_QRT_MANIFEST))["variants"]]
    for variant in variants:
        assert f"\n           {variant} " in body or f" {variant} " in body, variant
    assert "rq_demo_run.sh\" quantum-raspberry-tie" in body
    assert "v7_1" not in body.replace("QuantumRaspberryTie.v7_1.py itself", "")


# --- Q26: IBM Quantum account --------------------------------------------------

@pytest.mark.skipif(shutil.which("jq") is None, reason="jq required")
def test_ibm_account_summary_never_shows_the_key(menu_env):
    f = menu_env.tmp / "qiskit-ibm.json"
    f.write_text(json.dumps({"default-ibm-quantum-platform": {
        "channel": "ibm_quantum_platform", "token": "SECRET-KEY", "is_default_account": True}}))
    proc = menu_env(f'_rq_ibm_account_summary "{f}"; echo " RC=$?"')
    assert "ibm_quantum_platform" in proc.stdout and "RC=0" in proc.stdout, proc.stderr
    assert "SECRET" not in proc.stdout
    f.write_text("{}")
    proc = menu_env(f'_rq_ibm_account_summary "{f}"; echo " RC=$?"')
    assert "RC=1" in proc.stdout


def test_forget_ibm_account_deletes_the_users_file(menu_env):
    qdir = menu_env.tmp / "home" / ".qiskit"
    qdir.mkdir()
    (qdir / "qiskit-ibm.json").write_text('{"x": {"token": "t"}}')
    proc = menu_env("do_ibm_account_forget; echo RC=$?",
                    extra_env={"USER_HOME": str(menu_env.tmp / "home")})
    # USER_HOME comes from the env loader (HOME) in the test
    assert "RC=0" in proc.stdout, proc.stdout + proc.stderr
    assert not (qdir / "qiskit-ibm.json").exists()


# --- the real raspi-config, patched (optional) ----------------------------------

_UPSTREAM = os.environ.get("RQ_TEST_RASPI_CONFIG")


def _function_names(path):
    import re
    return set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*) ?\(\)", open(path).read(), re.M))


@pytest.mark.skipif(not _UPSTREAM, reason="set RQ_TEST_RASPI_CONFIG to an upstream raspi-config")
def test_menu_functions_do_not_shadow_raspi_config():
    # raspi-config defines its functions AFTER sourcing the menu, so a shared
    # name silently runs raspi-config's function instead of ours (a RasQberry
    # "do_advanced_menu" opened raspi-config's Advanced Options).
    shared = _function_names(_MENU) & _function_names(_UPSTREAM)
    assert not shared, shared


@pytest.mark.skipif(not _UPSTREAM or not sys.platform.startswith("linux"),
                    reason="set RQ_TEST_RASPI_CONFIG to an upstream raspi-config (Linux only)")
def test_patched_raspi_config_nonint_smoke(menu_env, tmp_path):
    target = tmp_path / "raspi-config"
    shutil.copy(_UPSTREAM, target)
    env = dict(os.environ, RQ_RASPI_CONFIG=str(target), RQ_RASPI_CONFIG_DIFF=_DIFF)
    proc = subprocess.run(["bash", _PATCHER], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = target.read_text().replace("/usr/config/RQB2_menu.sh", _MENU)
    target.write_text(text)

    base = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "RQ_CONFIG_FILE": str(menu_env.tmp / "env-config.sh"),
        "RQ_DEMO_MENU_CACHE": str(tmp_path / "none.sh"),
    }
    # R-017: "Network Proxy -> All" (empty address: clears, writes nothing new)
    proc = subprocess.run([_DASH, str(target), "nonint", "do_proxy", "all", ""],
                          capture_output=True, text=True, env=base, timeout=60)
    assert "bad variable name" not in proc.stderr, proc.stderr
    assert proc.returncode == 0, proc.stderr

    # R-001: a RasQberry setting change inside raspi-config keeps its globals
    code = ('INTERACTIVE=True; ASK_TO_REBOOT=1; update_environment_file BROWSER_AUTOSTART false; '
            'echo "R:$INTERACTIVE:$ASK_TO_REBOOT:$CONFIG"')
    proc = subprocess.run([_DASH, str(target), "nonint", "eval", code],
                          capture_output=True, text=True, env=base, timeout=60)
    assert "R:True:1:" in proc.stdout, proc.stdout + proc.stderr
    assert "/leaked/" not in proc.stdout


# --- B3: installs go through the engine's consent; IBM content repairs -------

def _fake_bin(tmp, engine_body):
    b = tmp / "fakebin"
    b.mkdir(exist_ok=True)
    _write_exec(b / "rq_demo_run.sh", engine_body)
    return b


def test_install_via_engine_not_now_is_not_an_error(menu_env):
    # the engine asked and the user chose "Not now": exit 0, still not installed
    b = _fake_bin(menu_env.tmp, '#!/bin/sh\n[ "$2" = --is-installed ] && exit 1\nexit 0\n')
    proc = menu_env(f'BIN_DIR="{b}"; install_via_engine quantum-lights-out QLO; echo "RC=$?"')
    assert "RC=2" in proc.stdout, proc.stdout + proc.stderr


def test_install_via_engine_failure_keeps_the_reason(menu_env):
    b = _fake_bin(menu_env.tmp, '#!/bin/sh\n[ "$2" = --is-installed ] && exit 1\n'
                                'echo "Not enough free space for X" >> "$RQ_ERROR_FILE"\nexit 1\n')
    proc = menu_env(f'BIN_DIR="{b}"; install_via_engine x X; echo "RC=$?"; echo "ERR=$RQ_LAST_DEMO_ERROR"')
    assert "RC=1" in proc.stdout and "ERR=Not enough free space for X" in proc.stdout, proc.stdout


def test_broken_ibm_download_is_removed_not_reported_installed(menu_env):
    # R-056: a .git without a commit counted as "cloned" for good
    dest = menu_env.tmp / "home" / "RasQberry-Two" / "demos" / "ibm-quantum-learning"
    (dest / ".git").mkdir(parents=True)
    git = menu_env.tmp / "stubs" / "git"
    _write_exec(git, '#!/bin/sh\ncase " $* " in *" fetch "*|*" rev-parse "*) exit 1 ;; esac\n'
                     'case "$1" in init) mkdir -p .git ;; esac\nexit 0\n')
    proc = menu_env('do_ibm_tutorials_install; echo "RC=$?"', extra_env={"RQ_AUTO_INSTALL": "1"})
    assert "RC=1" in proc.stdout, proc.stdout + proc.stderr
    assert not dest.exists()
    assert _env_value(menu_env.env_file, "IBM_TUTORIALS_INSTALLED") == "false"


def test_quantum_demos_menu_offers_remove_and_download_all():
    menu = open(_MENU).read()
    assert 'REM  "Remove a demo (free space)"' in menu
    assert '"$BIN_DIR/rq_download_all.sh"' in menu
    # the Mixer installer no longer sets up Qoffee-Maker
    start = menu.index("do_quantum_mixer_install() {")
    assert "qoffee-setup.sh" not in menu[start:menu.index("\n}\n", start)]
