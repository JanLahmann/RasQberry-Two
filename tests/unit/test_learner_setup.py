"""
Learner tools (batch B10): rq_learner_setup.sh, rq_python and the venv .pth file.

- R-072: the venv's 00-rasqberry.pth puts /usr/bin (rq_led_utils) on sys.path,
  appended so it never shadows an installed package.
- R-059: the same file makes a root run of the venv python write no bytecode.
- R-074: Thonny and Geany are pointed at the venv once; a choice the user made
  in Thonny is kept.
- R-071: ~/My-Quantum-Programs is seeded once with the starter programs.
- R-127: the Jupyter notebook setting that turns the JupyterLab extension off.
- R-073: rq_python starts the LED renderer for an LED program only where the
  user cannot drive the strip (Pi 4), and stops it afterwards.

The scripts run against a temporary home and a fake environment config.
"""

import configparser
import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CONFIG = os.path.join(_ROOT, "RQB2-config")
_SETUP = os.path.join(_BIN, "rq_learner_setup.sh")
_RQ_PYTHON = os.path.join(_BIN, "rq_python")
_PTH = os.path.join(_CONFIG, "venv-extras", "00-rasqberry.pth")

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _fake_venv(path, packages=()):
    """A venv-shaped directory: bin/python3 and lib/python3.13/site-packages."""
    site = path / "lib" / "python3.13" / "site-packages"
    site.mkdir(parents=True)
    (path / "bin").mkdir()
    python = path / "bin" / "python3"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    (path / "bin" / "activate").write_text(f'VIRTUAL_ENV="{path}"\nexport VIRTUAL_ENV\n')
    (path / "bin" / "jupyter").write_text(f"#!{path}/bin/python3\nprint('jupyter')\n")
    (path / "pyvenv.cfg").write_text(f"home = /usr/bin\ncommand = /usr/bin/python3 -m venv {path}\n")
    for name in packages:
        (site / f"{name}-1.0.dist-info").mkdir()
    return path


@pytest.fixture
def home(tmp_path):
    """A user home with an RQB2 venv and an env config that points at it."""
    home = tmp_path / "home"
    home.mkdir()
    _fake_venv(home / "RasQberry-Two" / "venv" / "RQB2", packages=["qiskit"])
    env_config = tmp_path / "env-config.sh"
    # Like rasqberry_env-config.sh: the env file's values are exported (set -a).
    env_config.write_text(textwrap.dedent(f"""\
        USER_HOME="{home}"
        set -a
        REPO=RasQberry-Two
        STD_VENV=RQB2
        LED_PHYSICAL=true
        LED_RENDER_MODE=direct
        set +a
        """))
    return home, env_config


def _run(script, args, home_env, extra_env=None, check=True):
    home, env_config = home_env
    env = dict(os.environ, HOME=str(home), RQ_CONFIG_FILE=str(env_config))
    env.pop("SUDO_USER", None)
    env.pop("LED_RENDER_MODE", None)
    env.update(extra_env or {})
    proc = subprocess.run(["bash", script, *args], capture_output=True, text=True, env=env)
    if check:
        assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def _venv(home):
    return home / "RasQberry-Two" / "venv" / "RQB2"


# --------------------------------------------------------------------------
# The .pth file itself (R-072, R-059)
# --------------------------------------------------------------------------

def _pth_lines():
    return [l for l in open(_PTH).read().splitlines() if l and not l.startswith("#")]


def test_pth_appends_usr_bin_and_nothing_else():
    lines = _pth_lines()
    assert lines[0] == "/usr/bin"
    assert len(lines) == 2 and lines[1].startswith("import ")


@pytest.mark.parametrize("euid,expected", [(0, True), (1000, False)])
def test_pth_import_line_disables_bytecode_only_for_root(euid, expected):
    """site.py exec()s the import line; run it with a fake os.geteuid."""
    import types

    fake_os = types.SimpleNamespace(geteuid=lambda: euid)
    fake_sys = types.SimpleNamespace(dont_write_bytecode=False)
    line = _pth_lines()[1].replace("import os, sys; ", "")
    exec(line, {"os": fake_os, "sys": fake_sys})
    assert fake_sys.dont_write_bytecode is expected


def test_pth_in_a_real_venv(tmp_path):
    venv = tmp_path / "venv"
    if subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)]).returncode:
        pytest.skip("cannot create a venv here")
    _run(_SETUP, ["--venv-only", str(venv)], (tmp_path, tmp_path / "unused"))
    python = venv / "bin" / "python3"
    out = subprocess.run(
        [str(python), "-c", "import sys; print(sys.path[-1], sys.path.index('/usr/bin') > 1, sys.dont_write_bytecode)"],
        capture_output=True, text=True, check=True).stdout.split()
    assert out == ["/usr/bin", "True", str(os.geteuid() == 0)]


# --------------------------------------------------------------------------
# rq_learner_setup.sh
# --------------------------------------------------------------------------

def test_venv_only_installs_the_extras_idempotently(home):
    venv = _venv(home[0])
    _run(_SETUP, ["--venv-only", str(venv)], home)
    pth = venv / "lib" / "python3.13" / "site-packages" / "00-rasqberry.pth"
    nbconf = venv / "etc" / "jupyter" / "jupyter_notebook_config.d" / "zz-rasqberry.json"
    assert pth.read_text() == open(_PTH).read()
    assert json.loads(nbconf.read_text()) == {"NotebookApp": {"nbserver_extensions": {"jupyterlab": False}}}
    # jupyterlab.json is loaded first (sorted), so this override must sort after it
    assert sorted(["jupyterlab.json", nbconf.name])[-1] == nbconf.name
    second = _run(_SETUP, ["--venv-only", str(venv)], home)
    assert "Installed" not in second.stdout


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write anywhere")
def test_venv_only_reports_a_failed_install(home):
    venv = _venv(home[0])
    site = venv / "lib" / "python3.13" / "site-packages"
    site.chmod(0o555)
    try:
        proc = _run(_SETUP, ["--venv-only", str(venv)], home, check=False)
    finally:
        site.chmod(0o755)
    assert proc.returncode != 0
    assert "Could not install" in proc.stderr


def test_venv_only_fails_without_a_venv(home, tmp_path):
    proc = _run(_SETUP, ["--venv-only", str(tmp_path / "nope")], home, check=False)
    assert proc.returncode != 0


def test_full_setup_points_thonny_and_geany_at_the_venv(home):
    h, _ = home
    _run(_SETUP, [], home)
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(h / ".config" / "Thonny" / "configuration.ini")
    assert ini.get("run", "backend_name") == "LocalCPython"
    assert ini.get("LocalCPython", "executable") == str(_venv(h) / "bin" / "python3")
    geany = (h / ".config" / "geany" / "filedefs" / "filetypes.python").read_text()
    assert 'EX_00_CM=/usr/bin/rq_python "%f"' in geany


def test_thonny_default_interpreter_is_replaced_but_a_user_choice_kept(home):
    h, _ = home
    ini_path = h / ".config" / "Thonny" / "configuration.ini"
    ini_path.parent.mkdir(parents=True)
    ini_path.write_text("[general]\nui_mode = simple\n\n[LocalCPython]\nexecutable = /usr/bin/python3\n")
    _run(_SETUP, ["--quiet"], home)
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ini_path)
    assert ini.get("general", "ui_mode") == "simple"
    assert ini.get("LocalCPython", "executable") == str(_venv(h) / "bin" / "python3")

    # Once done, a later change by the user survives the next login.
    ini.set("LocalCPython", "executable", "/opt/other/python3")
    with open(ini_path, "w") as fh:
        ini.write(fh)
    _run(_SETUP, ["--quiet"], home)
    again = configparser.ConfigParser(interpolation=None)
    again.read(ini_path)
    assert again.get("LocalCPython", "executable") == "/opt/other/python3"


def test_thonny_interpreter_chosen_before_first_setup_is_kept(home):
    h, _ = home
    ini_path = h / ".config" / "Thonny" / "configuration.ini"
    ini_path.parent.mkdir(parents=True)
    ini_path.write_text("[run]\nbackend_name = RP2040\n\n[LocalCPython]\nexecutable = /opt/py/bin/python3\n")
    _run(_SETUP, ["--quiet"], home)
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(ini_path)
    assert ini.get("run", "backend_name") == "RP2040"
    assert ini.get("LocalCPython", "executable") == "/opt/py/bin/python3"


def test_existing_geany_settings_are_left_alone(home):
    h, _ = home
    ft = h / ".config" / "geany" / "filedefs" / "filetypes.python"
    ft.parent.mkdir(parents=True)
    ft.write_text("[build-menu]\nEX_00_CM=python3 \"%f\"\n")
    _run(_SETUP, [], home)
    assert ft.read_text() == "[build-menu]\nEX_00_CM=python3 \"%f\"\n"


def test_starter_programs_are_seeded_once(home):
    h, _ = home
    _run(_SETUP, [], home)
    programs = h / "My-Quantum-Programs"
    shipped = sorted(os.listdir(os.path.join(_CONFIG, "my-quantum-programs")))
    assert sorted(os.listdir(programs)) == shipped
    assert all(not os.access(programs / f, os.X_OK) for f in shipped)
    shutil.rmtree(programs)
    _run(_SETUP, [], home)
    assert not programs.exists(), "a folder the user removed must not come back"


def test_starter_programs_follow_a_link_to_data(home, tmp_path):
    # A/B card (Jan, Q33c): rq_carry_over.sh made ~/My-Quantum-Programs a link
    # to /data; the starter files land there, beside the learner's own files
    h, _ = home
    on_data = tmp_path / "data" / "home" / "rasqberry" / "My-Quantum-Programs"
    on_data.mkdir(parents=True)
    os.symlink(on_data, h / "My-Quantum-Programs")
    _run(_SETUP, [], home)
    shipped = sorted(os.listdir(os.path.join(_CONFIG, "my-quantum-programs")))
    assert sorted(os.listdir(on_data)) == shipped
    assert (h / "My-Quantum-Programs").is_symlink()


def test_starter_programs_never_overwrite_the_learners_files(home, tmp_path):
    h, _ = home
    on_data = tmp_path / "data" / "home" / "rasqberry" / "My-Quantum-Programs"
    on_data.mkdir(parents=True)
    (on_data / "01_bell_state.py").write_text("# my version\n")
    os.symlink(on_data, h / "My-Quantum-Programs")
    _run(_SETUP, [], home)
    assert (on_data / "01_bell_state.py").read_text() == "# my version\n"
    # only the starter that is new since earlier releases joins the learner's file
    assert sorted(os.listdir(on_data)) == ["01_bell_state.py", "Hello-World.ipynb"]


def test_a_new_starter_reaches_a_folder_seeded_earlier_once(home):
    # item 9: a folder seeded by an earlier release (stamp, no offered list)
    # gets the Hello World notebook once; the learner's files stay as they are
    h, _ = home
    programs = h / "My-Quantum-Programs"
    programs.mkdir()
    (programs / "README.md").write_text("my notes\n")
    (programs / "My-First-Circuit.ipynb").write_text("{}\n")
    stamps = h / ".local" / "state" / "rasqberry" / "learner-setup"
    stamps.mkdir(parents=True)
    (stamps / "programs").write_text("2026-07-01\n")
    _run(_SETUP, [], home)
    assert sorted(os.listdir(programs)) == ["Hello-World.ipynb", "My-First-Circuit.ipynb", "README.md"]
    assert (programs / "README.md").read_text() == "my notes\n"
    (programs / "Hello-World.ipynb").unlink()
    _run(_SETUP, [], home)
    assert not (programs / "Hello-World.ipynb").exists(), "a starter the learner deleted must not come back"


def test_hello_world_is_doqumentations_pinned_notebook():
    import hashlib
    pins = json.load(open(os.path.join(_CONFIG, "starter-notebooks.json")))["notebooks"]
    entry = [e for e in pins if e["file"] == "Hello-World.ipynb"][0]
    assert entry["repo_url"] == "https://github.com/JanLahmann/doQumentation"
    assert len(entry["ref"]) == 40 and int(entry["ref"], 16) >= 0
    data = open(os.path.join(_CONFIG, "my-quantum-programs", entry["file"]), "rb").read()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"], "run rq_starter_sync.py --update"
    nb = json.loads(data)
    assert any("QuantumCircuit(2)" in "".join(c["source"]) for c in nb["cells"])
    # our edit: Run All must not save the placeholders over the learner's account
    save = ["".join(c["source"]) for c in nb["cells"] if "save_account(" in "".join(c["source"])]
    assert save and all('if token.startswith("<")' in code for code in save)
    assert not any("Binder" in "".join(c["source"]) for c in nb["cells"])
    proc = subprocess.run([sys.executable, os.path.join(_BIN, "rq_starter_sync.py")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_my_programs_opens_the_hello_world_notebook():
    text = open(os.path.join(_BIN, "rq_my_programs.sh")).read()
    assert 'START_PAGE="lab/tree/Hello-World.ipynb"' in text


def test_starter_programs_wait_for_a_missing_data_partition(home, tmp_path):
    # the link points to /data, but /data is not mounted: nothing is created
    h, _ = home
    gone = tmp_path / "not-mounted" / "home" / "rasqberry" / "My-Quantum-Programs"
    os.symlink(gone, h / "My-Quantum-Programs")
    proc = _run(_SETUP, [], home)
    assert not gone.exists()
    assert "not available" in proc.stdout + proc.stderr


def test_starter_programs_compile():
    folder = os.path.join(_CONFIG, "my-quantum-programs")
    for name in os.listdir(folder):
        if name.endswith(".py"):
            compile(open(os.path.join(folder, name)).read(), name, "exec")
        if name.endswith(".ipynb"):
            nb = json.load(open(os.path.join(folder, name)))
            assert nb["nbformat"] == 4
            for cell in nb["cells"]:
                if cell["cell_type"] == "code":
                    compile("".join(cell["source"]), name, "exec")


# --------------------------------------------------------------------------
# rq_python
# --------------------------------------------------------------------------

@pytest.fixture
def stubs(tmp_path, home):
    """Stub python, sudo and systemctl; record what rq_python does."""
    h, _ = home
    log = tmp_path / "calls.log"
    state = tmp_path / "renderer.active"
    python = _venv(h) / "bin" / "python3"
    python.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo "python LED_RENDER_MODE=${{LED_RENDER_MODE:-}} args=$*" >> "{log}"
        """))
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir()
    (stub_bin / "sudo").write_text('#!/bin/sh\n[ "$1" = "-n" ] && shift\nexec "$@"\n')
    (stub_bin / "systemctl").write_text(textwrap.dedent(f"""\
        #!/bin/sh
        echo "systemctl $*" >> "{log}"
        case "$1" in
            is-active) [ -f "{state}" ] ;;
            start) touch "{state}" ;;
            stop) rm -f "{state}" ;;
        esac
        """))
    for stub in ("sudo", "systemctl"):
        (stub_bin / stub).chmod(0o755)
    env = {"PATH": f"{stub_bin}:{os.environ['PATH']}"}
    return log, state, env


def _script(tmp_path, text):
    path = tmp_path / "prog.py"
    path.write_text(text)
    return str(path)


@pytest.mark.skipif(os.path.exists("/dev/pio0"), reason="a Pi 5 needs no renderer")
def test_rq_python_runs_an_led_program_through_the_renderer(home, stubs, tmp_path):
    log, state, env = stubs
    prog = _script(tmp_path, "from rq_led_utils import get_pixels\n")
    _run(_RQ_PYTHON, [prog, "x"], home, extra_env=env)
    calls = log.read_text().splitlines()
    assert "systemctl start rasqberry-led-renderer.service" in calls
    assert f"python LED_RENDER_MODE=service args={prog} x" in calls
    assert calls[-1] == "systemctl stop rasqberry-led-renderer.service"
    assert not state.exists()


def test_rq_python_leaves_a_plain_program_alone(home, stubs, tmp_path):
    log, _, env = stubs
    prog = _script(tmp_path, "print('hello')\n")
    _run(_RQ_PYTHON, [prog], home, extra_env=env)
    calls = log.read_text().splitlines()
    assert not any(c.startswith("systemctl") for c in calls)
    assert calls == [f"python LED_RENDER_MODE=direct args={prog}"]


def test_rq_python_uses_a_running_renderer_without_stopping_it(home, stubs, tmp_path):
    log, state, env = stubs
    state.touch()
    prog = _script(tmp_path, "import neopixel\n")
    _run(_RQ_PYTHON, ["--leds", prog], home, extra_env=env)
    calls = log.read_text().splitlines()
    assert not any("start" in c or "stop" in c for c in calls)
    assert f"python LED_RENDER_MODE=service args={prog}" in calls


def test_rq_python_no_leds_and_exit_status(home, stubs, tmp_path):
    log, _, env = stubs
    python = _venv(home[0]) / "bin" / "python3"
    python.write_text(f'#!/bin/sh\necho "python $*" >> "{log}"\nexit 3\n')
    prog = _script(tmp_path, "import rq_led_utils\n")
    proc = _run(_RQ_PYTHON, ["--no-leds", prog], home, extra_env=env, check=False)
    assert proc.returncode == 3
    assert not any(c.startswith("systemctl") for c in log.read_text().splitlines())
