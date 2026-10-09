"""
Tests for the demo group window and the Touch Mode icon (Jan, 2026-10-08).

- rq_group_window.py: a group's icon opens a small window with the group's
  demos as icons instead of the raw folder in the file manager. Tested here
  without GTK: reading the launchers (Desktop Entry parsing, which ones show,
  their order), the command a click runs (as the desktop's double-click:
  "x-terminal-emulator -e <Exec>" for Terminal=true), the grid size, and the
  fallback to the file manager without GTK.
- rq_desktop_session.py: the group icon's command starts that window; the
  Touch Mode icon is on the desktop only with a touchscreen (udev
  ID_INPUT_TOUCHSCREEN=1, fake udev data here); the layout copes with an
  icon fewer (Touch Mode gone, or Setup and Configuration merged later).
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_BOOKMARKS = os.path.join(_CFG, "desktop-bookmarks")
sys.path.insert(0, _BIN)
import rq_desktop_session as ds  # noqa: E402
import rq_group_window as gw  # noqa: E402


def _which(prog):
    """Every program exists (the launchers name /usr/bin/rq_demo_run.sh)."""
    return "/usr/bin/" + os.path.basename(prog)


def _folder(tmp_path, names, extra=None):
    folder = tmp_path / "group"
    folder.mkdir()
    for n in names:
        shutil.copy(os.path.join(_BOOKMARKS, n + ".desktop"), folder)
    for name, text in (extra or {}).items():
        (folder / name).write_text(text)
    return folder


# --- reading the launchers --------------------------------------------------------

def test_parse_desktop_file(tmp_path):
    f = tmp_path / "a.desktop"
    f.write_text("# comment\n[Desktop Entry]\nName=Demo\nName[de]=Vorführung\n"
                 "Comment=One\\sline\\ntwo\nExec=run \"a b\"\nTerminal=true\n"
                 "[Desktop Action other]\nName=Other\nExec=other\n")
    entry = gw.parse_desktop_file(str(f))
    assert entry == {"Name": "Demo", "Comment": "One line\ntwo", "Exec": 'run "a b"', "Terminal": "true"}
    (tmp_path / "b.desktop").write_text("[Something]\nName=x\n")
    assert gw.parse_desktop_file(str(tmp_path / "b.desktop")) is None
    assert gw.parse_desktop_file(str(tmp_path / "missing.desktop")) is None


@pytest.mark.parametrize("text,shown", [
    ("Name=A\nExec=a\n", True),
    ("Type=Application\nName=A\nExec=a\nNoDisplay=false\n", True),
    ("Name=A\nExec=a\nNoDisplay=true\n", False),
    ("Name=A\nExec=a\nHidden=true\n", False),
    ("Type=Link\nName=A\nURL=https://rasqberry.org\n", False),
    ("Name=A\n", False),
    ("Exec=a\n", False),
    ("Name=A\nExec=a\nTryExec=/usr/bin/gone\n", False),
    ("Name=A\nExec=a\nTryExec=/usr/bin/there\n", True),
])
def test_which_launchers_show(tmp_path, text, shown):
    f = tmp_path / "a.desktop"
    f.write_text("[Desktop Entry]\n" + text)
    entry = gw.parse_desktop_file(str(f))
    assert gw.entry_shown(entry, which=lambda p: p if "there" in p or "/" not in p else None) is shown


def test_exec_line_as_the_desktop_parses_it():
    entry = {"Name": "IBM LED Demo", "Icon": "ibm",
             "Exec": '/usr/bin/rq_hold_on_error.sh -t "IBM LED Demo" /usr/bin/rq_demo_run.sh led-demos ibm-logo'}
    assert gw.exec_argv(entry) == ["/usr/bin/rq_hold_on_error.sh", "-t", "IBM LED Demo",
                                   "/usr/bin/rq_demo_run.sh", "led-demos", "ibm-logo"]
    # RasQberry Setup: a whole shell line inside double quotes
    setup = gw.parse_desktop_file(os.path.join(_BOOKMARKS, "rasqberry-setup.desktop"))
    argv = gw.exec_argv(setup)
    assert argv[:4] == ["lxterminal", "-t", "RasQberry Setup", "-e"] and argv[4].startswith("bash -c '")
    # field codes: no files, so %U and friends go; %c, %k, %i, %% expand
    entry = {"Name": "N", "Icon": "i", "Exec": "prog %U --name=%c --file %k %i 100%%"}
    assert gw.exec_argv(entry, "/x.desktop") == ["prog", "--name=N", "--file", "/x.desktop",
                                                 "--icon", "i", "100%"]
    assert gw.exec_argv({"Exec": 'broken "quote'}) == []


def test_led_panel_window_lists_its_demos_in_menu_order(tmp_path):
    sap = ("[Desktop Entry]\nName=SAP Quantum LED\nExec=/usr/bin/rq_hold_on_error.sh "
           "/usr/bin/rq_demo_run.sh sap-quantum-led\nTerminal=true\nIcon=x\n")
    folder = _folder(tmp_path, ["clear-leds", "led-painter", "quantum-raspberry-tie", "rasq-led",
                                "quantum-lights-out", "led-ibm-demo"],
                     {"rq-ext-sap-quantum-led.desktop": sap, "notes.txt": "mine",
                      ".rq-ext-x.desktop.tmp": "half written", ".hidden.desktop": sap,
                      "gone.desktop": "[Desktop Entry]\nName=Gone\nExec=x\nNoDisplay=true\n"})
    user = tmp_path / "user-manifests"
    user.mkdir()
    (user / "rq_demo_sap-quantum-led.json").write_text(json.dumps({"id": "sap-quantum-led",
                                                                   "menu": {"order": 45}}))
    launchers = gw.list_launchers(str(folder), dirs=[_MANIFESTS, str(user)], which=_which)
    assert [launcher["id"] for launcher in launchers] == [
        "led-ibm-demo", "rasq-led", "quantum-lights-out", "quantum-raspberry-tie",
        "rq-ext-sap-quantum-led", "led-painter", "clear-leds"]
    first = launchers[0]
    assert first["name"] == "IBM LED Demo" and first["terminal"] is True
    assert first["icon"] == "/usr/share/icons/rasqberry/led-ibm-demo.svg"
    assert first["comment"] == "The IBM logo in colour on the LED panel"


def test_learn_window_order_matches_the_menu(tmp_path):
    folder = _folder(tmp_path, ["composer", "grok-bloch", "ibm-quantum-courses", "ibm-quantum-tutorials",
                                "my-quantum-programs", "qiskit-tutorials", "quantum-lab"])
    names = [launcher["id"] for launcher in gw.list_launchers(str(folder), dirs=[_MANIFESTS], which=_which)]
    # My Quantum Programs first (as in the menu), Composer by its manifest (60)
    assert names == ["my-quantum-programs", "grok-bloch", "qiskit-tutorials", "quantum-lab",
                     "ibm-quantum-tutorials", "ibm-quantum-courses", "composer"]


def test_workshops_window_has_the_demo_loop_last(tmp_path):
    folder = _folder(tmp_path, ["demo-loop", "doqumentation"])
    names = [launcher["id"] for launcher in gw.list_launchers(str(folder), dirs=[_MANIFESTS], which=_which)]
    assert names == ["doqumentation", "demo-loop"]


def test_an_empty_or_missing_folder_shows_nothing(tmp_path):
    assert gw.list_launchers(str(tmp_path)) == []
    assert gw.list_launchers(str(tmp_path / "missing")) == []


# --- starting a demo ----------------------------------------------------------------

def test_terminal_from_libfm(tmp_path):
    user, system = tmp_path / "user.conf", tmp_path / "system.conf"
    system.write_text("[config]\nterminal=x-terminal-emulator %s\n")
    assert gw.terminal_command([str(user), str(system)]) == ["x-terminal-emulator", "-e"]
    user.write_text("[config]\nterminal=lxterminal -e %s\n")
    assert gw.terminal_command([str(user), str(system)]) == ["lxterminal", "-e"]
    assert gw.terminal_command([str(tmp_path / "none")]) == ["x-terminal-emulator", "-e"]
    # the person's file is found under the home
    (tmp_path / ".config/libfm").mkdir(parents=True)
    (tmp_path / ".config/libfm/libfm.conf").write_text("terminal=xterm\n")
    assert gw.terminal_command(["~/.config/libfm/libfm.conf"], home=str(tmp_path)) == ["xterm", "-e"]


def test_a_click_runs_what_the_desktop_double_click_runs(tmp_path):
    # measured on the Pi (trixie, 2026-10-08): pcmanfm runs a Terminal=true
    # launcher as "x-terminal-emulator -e <Exec words>", in the home folder,
    # with its own environment; Terminal=false ones as their Exec
    folder = _folder(tmp_path, ["led-ibm-demo", "composer"])
    launchers = {launcher["id"]: launcher
                 for launcher in gw.list_launchers(str(folder), dirs=[_MANIFESTS], which=_which)}
    calls = []

    def popen(argv, **kw):
        calls.append((argv, kw))

    home = str(tmp_path)
    assert gw.launch(launchers["led-ibm-demo"], ["x-terminal-emulator", "-e"], home=home, popen=popen)
    assert gw.launch(launchers["composer"], ["x-terminal-emulator", "-e"], home=home, popen=popen)
    assert calls[0][0] == ["x-terminal-emulator", "-e", "/usr/bin/rq_hold_on_error.sh", "-t", "IBM LED Demo",
                           "/usr/bin/rq_demo_run.sh", "led-demos", "ibm-logo"]
    assert calls[1][0] == ["chromium", "--password-store=basic", "https://quantum.ibm.com/composer/"]
    for _, kw in calls:
        # the window's environment (the desktop's), the home folder, and a
        # session of its own: it outlives the window, which closes next
        assert kw["cwd"] == home and kw["start_new_session"] is True and "env" not in kw


def test_a_launcher_path_and_a_failed_start(tmp_path):
    launcher = {"argv": ["prog"], "terminal": False, "cwd": str(tmp_path), "path": "x.desktop"}
    seen = []
    assert gw.launch(launcher, home="/elsewhere", popen=lambda argv, **kw: seen.append(kw["cwd"]))
    assert seen == [str(tmp_path)]

    def fails(argv, **kw):
        raise OSError("no such program")

    assert not gw.launch(launcher, popen=fails)


# --- window size -------------------------------------------------------------------

@pytest.mark.parametrize("count,cols", [(0, 1), (1, 1), (2, 2), (4, 4), (5, 3), (6, 3), (7, 4), (9, 4)])
def test_grid_columns(count, cols):
    assert gw.columns(count) == cols


def test_grid_fits_two_thirds_of_a_small_screen():
    # 800x480 touch display in touch mode: 2/3 of 800 px holds 2 columns
    assert gw.columns(7, 800, touch=True) == 2
    assert gw.columns(7, 1920, touch=True) == 4
    cols = gw.columns(7, 800, touch=False)
    assert cols * (gw.cell_width(False) + 8) + 40 <= 800 * 2 // 3


def test_touch_mode_has_bigger_icons():
    assert gw.icon_size(True) > gw.icon_size(False) >= 48
    assert gw.cell_width(True) > gw.cell_width(False)


def test_one_window_per_group():
    ids = {gw.app_id(g["id"]) for g in ds.load_groups()["groups"]}
    assert len(ids) == 6
    for app in ids:
        # a valid GApplication id: dot-separated elements of [A-Za-z0-9_]
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+", app)


# --- the command ----------------------------------------------------------------------

def test_without_gtk_the_folder_opens_in_the_file_manager(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "HOME", str(tmp_path))
    monkeypatch.setattr(ds, "group_dir", lambda home=None: str(tmp_path / "groups"))
    monkeypatch.setattr(gw, "load_gtk", lambda: None)
    calls = []
    monkeypatch.setattr(os, "execvp", lambda prog, args: calls.append(args))
    assert gw.main(["play"]) == 0
    assert calls == [["pcmanfm", str(tmp_path / "groups" / "Play")]]
    assert gw.main(["nope"]) == 1
    assert gw.main([]) == 2


def test_list_prints_names_and_commands(tmp_path):
    home = tmp_path / "home"
    folder = home / ".local/share/rasqberry/desktop-groups/Workshops & events"
    folder.mkdir(parents=True)
    shutil.copy(os.path.join(_BOOKMARKS, "demo-loop.desktop"), folder)
    stub = tmp_path / "bin"
    stub.mkdir()
    loop = stub / "rq_demo_loop.sh"
    loop.write_text("#!/bin/sh\n")
    loop.chmod(0o755)
    # TryExec=/usr/bin/rq_demo_loop.sh: only on a Pi, so point the launcher here
    text = (folder / "demo-loop.desktop").read_text().replace("/usr/bin/rq_demo_loop.sh", str(loop))
    (folder / "demo-loop.desktop").write_text(text)
    out = subprocess.run([sys.executable, os.path.join(_BIN, "rq_group_window.py"), "--list", "workshops"],
                         capture_output=True, text=True, env=dict(os.environ, HOME=str(home)))
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("Demo Loop\tx-terminal-emulator -e /usr/bin/rq_hold_on_error.sh -t 'Demo Loop' ")


class _Exec(Exception):
    """os.exec* does not return: neither does the stub."""


def test_the_group_icon_opens_the_window(monkeypatch, tmp_path):
    calls = []

    def stub(kind):
        def run(prog, args):
            calls.append((kind, args))
            raise _Exec
        return run

    monkeypatch.setattr(os, "execv", stub("execv"))
    monkeypatch.setattr(os, "execvp", stub("execvp"))
    with pytest.raises(_Exec):
        ds.open_group("led-panel", root=str(tmp_path))
    window = os.path.join(_BIN, "rq_group_window.py")
    assert calls == [("execv", [sys.executable, window, "led-panel"])]
    assert (tmp_path / "LED panel").is_dir()
    # without the window script: the folder in the file manager, as before
    calls.clear()
    with pytest.raises(_Exec):
        ds.open_group("led-panel", root=str(tmp_path), window="")
    assert calls == [("execvp", ["pcmanfm", str(tmp_path / "LED panel")])]
    assert ds.open_group("nope", root=str(tmp_path)) == 1


def test_the_rig_harness_no_longer_closes_the_window_with_alt_f4():
    # the window closes itself after Enter; Alt+F4 then hit the demo's window
    text = open(os.path.join(_ROOT, "tests/rig/pi/demo_smoke.sh"), encoding="utf-8").read()
    assert "56+62" not in text and "group's window" in text


# --- the Touch Mode icon: only with a touchscreen ------------------------------------------

def _udev(tmp_path, files):
    d = tmp_path / "udev"
    d.mkdir(parents=True)
    for name, text in files.items():
        (d / name).write_text(text)
    return str(d)


def test_touchscreen_detection_with_fake_udev_data(tmp_path):
    # a Pi 4 with HDMI only (from the rig): pointing sticks and switches
    pi4 = {"c13:63": "", "c13:64": "E:ID_INPUT=1\nE:ID_INPUT_POINTINGSTICK=1\nE:ID_INPUT_KEY=1\n",
           "c13:65": "E:ID_INPUT=1\nE:ID_INPUT_SWITCH=1\n", "+input:input0": "E:ID_INPUT=1\n",
           "b179:0": "E:ID_INPUT_TOUCHSCREEN=1\n"}   # not an input device: ignored
    assert not ds.has_touchscreen(_udev(tmp_path / "a", pi4))
    # a mouse or touchpad is no touchscreen
    pad = {"c13:70": "E:ID_INPUT=1\nE:ID_INPUT_TOUCHPAD=1\nE:ID_INPUT_MOUSE=1\n"}
    assert not ds.has_touchscreen(_udev(tmp_path / "b", pad))
    # the official 7-inch display (event node) or a USB one (device entry)
    dsi = {"c13:66": "I:1234\nE:ID_INPUT=1\nE:ID_INPUT_TOUCHSCREEN=1\nG:seat\n"}
    assert ds.has_touchscreen(_udev(tmp_path / "c", dsi))
    usb = {"+input:input7": "E:ID_INPUT=1\nE:ID_INPUT_TOUCHSCREEN=1\n"}
    assert ds.has_touchscreen(_udev(tmp_path / "d", usb))
    assert not ds.has_touchscreen(str(tmp_path / "no-udev"))


def test_touchscreen_command(monkeypatch):
    monkeypatch.setattr(ds, "has_touchscreen", lambda udev_data=None: True)
    assert ds.main(["--touchscreen"]) == 0
    monkeypatch.setattr(ds, "has_touchscreen", lambda udev_data=None: False)
    assert ds.main(["--touchscreen"]) == 1


def _desktop(tmp_path):
    home = tmp_path / "home"
    desk = home / "Desktop"
    desk.mkdir(parents=True)
    for n in ds.ICON_ORDER:
        shutil.copy(os.path.join(_BOOKMARKS, n + ".desktop"), desk)
    conf = home / "d.conf"
    conf.write_text("[*]\ndesktop_font=Nunito Sans Light 12\n")
    return home, desk, conf


def _layout(home, desk, conf, monkeypatch, touchscreen, size=(1920, 1080), setup=None):
    monkeypatch.setattr(ds, "libfm_icon_size", lambda path=None, libfm=None: 48)
    monkeypatch.setattr(ds, "pcmanfm_profile", lambda autostart=None: "default")
    return ds.layout_desktop(size, False, desktop=str(desk), conf=str(conf), record=str(home / "rec"),
                             dirs=[_MANIFESTS], known=os.path.join(_CFG, "known-demos.json"),
                             exe="/usr/bin/rq_desktop_session.py",
                             icon_dir=os.path.join(_ROOT, "desktop-icons"), touchscreen=touchscreen,
                             setup=setup)


def _placed(conf):
    return re.findall(r"^\[(.+)\.desktop\]\nx=(\d+)\ny=(\d+)", conf.read_text(), re.M)


def test_touch_mode_icon_only_with_a_touchscreen(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    hidden = home / ds.HIDDEN_DIR
    # no touchscreen (the rig's Pi 4): one icon fewer, no gap
    assert _layout(home, desk, conf, monkeypatch, touchscreen=False)
    assert not (desk / "touch-mode.desktop").exists()
    assert (hidden / "touch-mode.desktop").exists()
    placed = _placed(conf)
    assert len(placed) == 13 and "touch-mode" not in [n for n, _, _ in placed]
    assert [n for n, _, _ in placed][:2] == ["rasqberry-menu", "learning-paths"]
    # not in a group folder either: it is no demo
    root = home / ".local/share/rasqberry/desktop-groups"
    assert not list(root.glob("*/touch-mode.desktop"))
    # nothing changed: no new layout
    assert not _layout(home, desk, conf, monkeypatch, touchscreen=False)
    # a touchscreen connected: it comes back, after RasQberry Configuration
    assert _layout(home, desk, conf, monkeypatch, touchscreen=True)
    assert (desk / "touch-mode.desktop").exists() and not (hidden / "touch-mode.desktop").exists()
    placed = _placed(conf)
    assert len(placed) == 14 and placed[1][0] == "touch-mode"
    assert json.loads((home / "rec").read_text())["icons"][1] == "touch-mode"


def test_a_deleted_touch_mode_icon_stays_deleted(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    (desk / "touch-mode.desktop").unlink()
    _layout(home, desk, conf, monkeypatch, touchscreen=True)
    assert not (desk / "touch-mode.desktop").exists()


def test_touch_mode_icon_in_an_old_more_folder_is_put_away_too(tmp_path):
    home, desk, _ = _desktop(tmp_path)
    (desk / "More").mkdir()
    shutil.move(str(desk / "touch-mode.desktop"), str(desk / "More"))
    assert ds.place_touchscreen_launchers(str(desk), False)
    assert not (desk / "More" / "touch-mode.desktop").exists()
    assert (home / ds.HIDDEN_DIR / "touch-mode.desktop").exists()


def test_touch_mode_is_in_the_desktop_settings_menu():
    menu = open(os.path.join(_CFG, "RQB2_menu.sh"), encoding="utf-8").read()
    settings = menu[menu.index("do_desktop_settings_menu() {"):]
    settings = settings[:settings.index("\n}\n")]
    assert 'TOUCH   "Touch mode (bigger icons and buttons)' in settings and "do_touch_mode_menu" in settings
    assert 'DESKTOP "Desktop Settings (touch mode, browser at login)"' in menu


@pytest.mark.parametrize("gone", [("touch-mode",), ("touch-mode", "rasqberry-setup"),
                                  ("touch-mode", "rasqberry-menu"), ("rasqberry-setup",)])
@pytest.mark.parametrize("w,h,touch,icon", [(1920, 1080, False, 48), (1920, 1080, True, 72),
                                            (800, 480, False, 48), (800, 480, True, 72)])
def test_the_layout_copes_with_fewer_system_icons(gone, w, h, touch, icon):
    # Touch Mode without a touchscreen, RasQberry Setup after the checklist,
    # or Setup and Configuration as one icon (Jan deciding): the icons close
    # up, nothing overflows
    groups = ds.load_groups()
    system = [n for n in groups["system"] if n not in gone]
    top = ds.desktop_order(system + groups["starters"], {}, groups)
    assert len(top) == 14 - len(gone)
    label, offset = ds.LABEL_HEIGHT_NUNITO, ds.layout_top(touch, "default")
    pos, overflow = ds.plan_layout(top, w, h, touch=touch, icon=icon, label=label, top=offset)
    assert not overflow and len(pos) == len(top)
    assert pos[top[0]] == (ds.MARGIN, ds.MARGIN + offset)
    assert len(set(pos.values())) == len(top)
    for x, y in pos.values():
        assert x + icon <= w and y + icon + label <= h


# --- Contributed demos (Jan, 2026-10-08) -------------------------------------------------

def test_contributed_demos_window_offers_the_catalogue(tmp_path):
    groups = ds.load_groups()
    contributed = gw.find_group("contributed", groups)
    assert contributed["title"] == "Contributed demos" and contributed["catalogue"] is True
    assert not any(g.get("catalogue") for g in groups["groups"] if g["id"] != "contributed")
    # empty at first: no launchers, the window shows a hint and the button
    assert gw.list_launchers(str(tmp_path / "none")) == []
    add = gw.add_demo_launcher(["x-terminal-emulator", "-e"])
    argv = gw.launch_argv(add, ["x-terminal-emulator", "-e"])
    assert argv[:4] == ["x-terminal-emulator", "-e", "bash", "-c"]
    # the catalogue picker as root, like Manage demos > Add demo from catalogue
    assert re.search(r"; sudo \S*rq_demo_add_external\.sh; echo; read ", argv[4])
    assert argv[4].startswith("printf '\\033]0;Add demo from catalogue\\007'")
    src = open(os.path.join(_BIN, "rq_group_window.py"), encoding="utf-8").read()
    assert 'if self.group.get("catalogue"):' in src and "No demos from the catalogue yet." in src


def test_contributed_demos_menu_offers_the_catalogue_also_when_empty():
    menu = open(os.path.join(_CFG, "RQB2_menu.sh"), encoding="utf-8").read()
    body = menu[menu.index("do_demo_group_menu() {"):]
    body = body[:body.index("\n}\n")]
    assert 'set -- "$@" ADDX "Add demo from catalogue"' in body
    assert "No demos from the catalogue yet. Add one:" in body
    assert "ADDX)  do_add_external_demo" in body


# --- RasQberry Setup: last, and only until the checklist is done ------------------------------

def test_setup_icon_is_last_and_leaves_when_the_checklist_is_done(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    assert _layout(home, desk, conf, monkeypatch, touchscreen=False)
    placed = [n for n, _, _ in _placed(conf)]
    assert placed[-1] == "rasqberry-setup" and len(placed) == 13
    # the checklist's mark: the icon goes, nothing is left in its place
    mark = home / ds.SETUP_DONE
    mark.parent.mkdir(parents=True)
    mark.write_text("2026-10-08\n")
    assert _layout(home, desk, conf, monkeypatch, touchscreen=False)
    placed = [n for n, _, _ in _placed(conf)]
    assert "rasqberry-setup" not in placed and len(placed) == 12
    assert not (desk / "rasqberry-setup.desktop").exists()
    assert (home / ds.HIDDEN_DIR / "rasqberry-setup.desktop").exists()
    assert not _layout(home, desk, conf, monkeypatch, touchscreen=False)
    # the menu keeps the checklist; Configuration stays first
    assert placed[0] == "rasqberry-menu"


def test_setup_done_reads_the_checklists_mark(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "HOME", str(tmp_path))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert not ds.setup_done()
    (tmp_path / ".local/state/rasqberry").mkdir(parents=True)
    (tmp_path / ".local/state/rasqberry/setup-done").write_text("x")
    assert ds.setup_done() and ds.setup_done(str(tmp_path))
    # the checklist honours XDG_STATE_HOME: so does the desktop
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert not ds.setup_done()
    # and both name the same file
    text = open(os.path.join(_BIN, "rq_firstlogin.sh"), encoding="utf-8").read()
    assert 'SETUP_DONE_FILE="$STATE_DIR/setup-done"' in text
    assert ds.SETUP_DONE == ".local/state/rasqberry/setup-done"


_WT = r"""#!/bin/sh
{ for a in "$@"; do printf '%s\n' "$a"; done; echo "@@"; } >> "$WT_LOG"
case " $* " in
  *" --checklist "*) printf '%s' "$WT_CHOICE" >&2; exit "${WT_RC:-0}" ;;
esac
exit 0
"""


def _checklist(tmp_path, choice, rc="0", mode="--all"):
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    for name, body in (("whiptail", _WT), ("ps", "#!/bin/sh\necho pts/0\n"),
                       ("sudo", "#!/bin/sh\nexit 1\n"), ("systemctl", "#!/bin/sh\nexit 1\n")):
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True, exist_ok=True)
    shutil.copy(os.path.join(_BOOKMARKS, "rasqberry-setup.desktop"), home / "Desktop")
    log = tmp_path / "wt.log"
    env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}", HOME=str(home),
               XDG_STATE_HOME=str(home / ".state"), XDG_RUNTIME_DIR=str(tmp_path / "run"),
               RQ_IMAGER_STATE=str(tmp_path / "none"), RQ_ENV_FILE=str(tmp_path / "no-env"),
               RQ_KEYBOARD_FILE=str(tmp_path / "no-keyboard"), WT_LOG=str(log),
               WT_CHOICE=choice, WT_RC=rc, USER="rasqberry")
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "SSH_CONNECTION"):
        env.pop(k, None)
    proc = subprocess.run(["bash", os.path.join(_BIN, "rq_firstlogin.sh"), mode], env=env,
                          capture_output=True, text=True, timeout=120)
    dialogs = log.read_text().split("@@\n")[:-1] if log.exists() else []
    if log.exists():
        log.unlink()
    return proc, dialogs, home / ".state/rasqberry/setup-done"


_needs_pending = pytest.mark.skipif(os.geteuid() == 0, reason="the option is not offered to root")


@_needs_pending
def test_checklist_offers_dont_show_again_and_removes_the_icon(tmp_path):
    proc, dialogs, done = _checklist(tmp_path, "noicon")
    assert proc.returncode == 0, proc.stderr
    checklist = next(d for d in dialogs if "--checklist" in d)
    if done.exists() and "noicon" not in checklist:
        pytest.skip("no step pending on this machine: the checklist was done at once")
    # the last entry of the list
    # (each line ends in a space: a margin in the list, user test 2026-10-08)
    assert [line.rstrip(" ") for line in checklist.rstrip("\n").split("\n")[-3:]] == [
        "noicon", "Don't show again and remove the RasQberry Setup icon", "OFF"]
    assert done.exists()
    assert any("The RasQberry Setup icon is removed" in d and "Setup Checklist" in d for d in dialogs)
    # next time: no such entry any more, and the list names the menu
    (tmp_path / "home/Desktop/rasqberry-setup.desktop").unlink()
    _, dialogs, _ = _checklist(tmp_path, "", rc="1")
    checklist = next(d for d in dialogs if "--checklist" in d)
    assert "noicon" not in checklist


@_needs_pending
@pytest.mark.parametrize("rc", ["1", "255"])
def test_only_closing_the_checklist_keeps_the_icon(tmp_path, rc):
    proc, dialogs, done = _checklist(tmp_path, "", rc=rc, mode="--now")
    assert proc.returncode == 0, proc.stderr
    if not any("--checklist" in d for d in dialogs):
        pytest.skip("no step pending on this machine")
    assert not done.exists()
