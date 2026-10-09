"""
Tests for the demo groups (Jan, 2026-10-07): one desktop folder and one
Quantum Demos submenu per group, from demo-groups.json and each manifest's
"group" (known-demos.json for catalogue demos, else a guess).

- the data: demo-groups.json, the manifests, the schema, the validator and the
  registry agree, and every launcher lands where Jan's table puts it;
- the desktop (rq_desktop_session.py): launchers sorted into their folders,
  starters on the desktop and in their folders, a group icon per folder, the
  old More folder emptied, small screens and touch mode still fit;
- the menu cache (rq_demo_generate_menu.sh) and the menu (RQB2_menu.sh under
  dash): the groups, each group's demos with their needs, Manage demos.
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from test_raspi_config_menu import menu_env  # noqa: F401 (fixture)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")
_MANIFESTS = os.path.join(_CFG, "demo-manifests")
_BOOKMARKS = os.path.join(_CFG, "desktop-bookmarks")
_GEN = os.path.join(_BIN, "rq_demo_generate_menu.sh")
_MENU = os.path.join(_CFG, "RQB2_menu.sh")
_SH = shutil.which("dash") or "/bin/sh"
sys.path.insert(0, _BIN)
import rq_desktop_session as ds  # noqa: E402

needs_jq = pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                              reason="bash and jq are required")

# Jan's groups (2026-10-07; Contributed demos 2026-10-08): desktop launcher -> folder
_TABLE = {
    "led-panel": {"led-ibm-demo", "rasq-led", "quantum-lights-out", "quantum-raspberry-tie",
                  "led-painter", "clear-leds"},
    "play": {"fun-with-quantum", "quantum-coin-game", "quantum-paradoxes", "quantum-fractals"},
    "projects": {"qoffee-maker", "quantum-mixer", "rq-ext-racetraq"},
    "learn": {"my-quantum-programs", "grok-bloch", "qiskit-tutorials", "quantum-lab",
              "ibm-quantum-tutorials", "ibm-quantum-courses", "composer"},
    "workshops": {"doqumentation", "demo-loop"},
    "contributed": {"rq-ext-sap-quantum-led", "rq-ext-sap-quantum-learning"},
}
_STARTERS = ["learning-paths", "led-ibm-demo", "grok-bloch", "quantum-coin-game", "my-quantum-programs"]
_SYSTEM = ["rasqberry-setup", "rasqberry-menu", "touch-mode"]
# the desktop's order: RasQberry Setup last (temporary, Jan 2026-10-08)
_DESK_ORDER = (["rasqberry-menu", "touch-mode"] + _STARTERS
               + ["rq-group-%s" % g for g in _TABLE] + ["rasqberry-setup"])


def _groups_json():
    return json.load(open(os.path.join(_MANIFESTS, "demo-groups.json"), encoding="utf-8"))


def _manifests():
    out = {}
    for name in os.listdir(_MANIFESTS):
        if name.startswith("rq_demo_") and name.endswith(".json") and "schema" not in name:
            m = json.load(open(os.path.join(_MANIFESTS, name), encoding="utf-8"))
            out[m["id"]] = m
    return out


# --- the data ------------------------------------------------------------------

def test_groups_file_matches_schema_validator_and_menu_fallback():
    data = _groups_json()
    ids = [g["id"] for g in data["groups"]]
    assert ids == ["led-panel", "play", "projects", "learn", "workshops", "contributed"]
    # the catalogue demos' group, offered also while empty
    assert [g["id"] for g in data["groups"] if g.get("catalogue")] == ["contributed"]
    schema = json.load(open(os.path.join(_MANIFESTS, "rq_demo_schema.json")))
    assert schema["properties"]["group"]["enum"] == ids
    validator = open(os.path.join(_BIN, "rq_demo_validate.sh")).read()
    assert "VALID_GROUPS='%s'" % json.dumps(ids) in validator
    menu = open(_MENU, encoding="utf-8").read()
    fallback = menu[menu.index("_rq_demo_groups_fallback() {"):]
    for g in data["groups"]:
        assert '"%s" "%s"' % (g["id"], g["title"]) in fallback
        assert "%s) echo \"%s\"" % (g["id"], g["title"]) in re.sub(r"\)\s+echo", ") echo", fallback)
        # icon shipped; the title fits two label lines and a folder name
        assert os.path.isfile(os.path.join(_ROOT, "desktop-icons", g["icon"])), g["icon"]
        assert len(g["title"]) <= 20 and "/" not in g["title"]
        assert len(g["title"]) + 2 + len(g["menu"]) <= 70, g["id"]
    assert data["starters"] == _STARTERS and data["system"] == _SYSTEM
    assert data["last"] == ["rasqberry-setup"]


def test_every_shipped_manifest_and_catalogue_entry_has_a_valid_group():
    ids = {g["id"] for g in _groups_json()["groups"]}
    for demo_id, m in _manifests().items():
        assert m.get("group") in ids, demo_id
    registry = json.load(open(os.path.join(_CFG, "known-demos.json")))
    # racetraQ (formerly traQmania) is from the Fun with Quantum family: Big
    # projects; the SAP demos come from a partner: Contributed demos (Jan, 2026-10-08)
    assert {d["id"]: d["group"] for d in registry["demos"]} == {
        "racetraq": "projects", "sap-quantum-learning": "contributed", "sap-quantum-led": "contributed"}


def test_every_desktop_launcher_lands_where_jans_table_puts_it(tmp_path):
    groups = ds.load_groups()
    seen = {g: set() for g in _TABLE}
    loose = set()
    for name in ds.ICON_ORDER + ["rq-ext-racetraq", "rq-ext-sap-quantum-learning",
                                 "rq-ext-sap-quantum-led"]:
        path = os.path.join(_BOOKMARKS, name + ".desktop")
        group = ds.launcher_group(name, path, groups, dirs=[_MANIFESTS],
                                  known=os.path.join(_CFG, "known-demos.json"))
        (seen[group] if group else loose).add(name)
    assert seen == _TABLE
    assert loose == set(_SYSTEM) | {"learning-paths"}


@needs_jq
@pytest.mark.parametrize("demo_id", ["rasq-led", "composer", "doqumentation", "led-demos",
                                     "fun-with-quantum", "racetraq", "traqmania", "sap-quantum-led",
                                     "sap-quantum-learning"])
def test_shell_and_python_decide_the_same_group(demo_id):
    sh = subprocess.run(["bash", "-c", '. "$1"; rq_demo_group "$2"', "_",
                         os.path.join(_BIN, "rq_common.sh"), demo_id],
                        capture_output=True, text=True).stdout.strip()
    py = ds.demo_group(demo_id, ds.load_groups(), dirs=[_MANIFESTS],
                       known=os.path.join(_CFG, "known-demos.json"))
    assert sh == py and sh in _TABLE, (sh, py)


@needs_jq
@pytest.mark.parametrize("manifest,group", [
    ({"group": "bogus", "needs_hw": {"leds": True}}, "contributed"),
    ({"category": "game"}, "contributed"),
    ({"category": "jupyter"}, "contributed"),
    # its own manifest does not choose: only the curated catalogue entry does
    ({"group": "workshops", "category": "game"}, "contributed"),
])
def test_a_catalogue_demo_goes_to_contributed_demos(tmp_path, manifest, group):
    m = dict({"id": "x-demo", "name": "X", "category": "tool", "description": "t"}, **manifest)
    (tmp_path / "rq_demo_x-demo.json").write_text(json.dumps(m))
    sh = subprocess.run(["bash", "-c", '. "$1"; rq_demo_group x-demo "$2"', "_",
                         os.path.join(_BIN, "rq_common.sh"), str(tmp_path / "rq_demo_x-demo.json")],
                        capture_output=True, text=True).stdout.strip()
    # (the user's manifest directory after the shipped one)
    py = ds.demo_group("x-demo", ds.load_groups(), dirs=[_MANIFESTS, str(tmp_path)],
                       known=os.path.join(_CFG, "known-demos.json"))
    assert sh == py == group


# --- the desktop ---------------------------------------------------------------

def _desktop(tmp_path, more=()):
    home = tmp_path / "home"
    desk = home / "Desktop"
    (desk / "More").mkdir(parents=True)
    for n in ds.ICON_ORDER:
        shutil.copy(os.path.join(_BOOKMARKS, n + ".desktop"), desk / "More" if n in more else desk)
    conf = home / "d.conf"
    conf.write_text("[*]\ndesktop_font=Nunito Sans Light 12\n[composer.desktop]\nx=1\ny=1\n"
                    "trusted=true\n[More]\nx=5\ny=5\ntrusted=true\n")
    return home, desk, conf


def _layout(home, desk, conf, size=(1920, 1080), touch=False, monkeypatch=None, icon=48):
    monkeypatch.setattr(ds, "libfm_icon_size", lambda path=None, libfm=None: icon)
    monkeypatch.setattr(ds, "pcmanfm_profile", lambda autostart=None: "default")
    return ds.layout_desktop(size, touch, desktop=str(desk), conf=str(conf),
                             record=str(home / "rec"), dirs=[_MANIFESTS],
                             known=os.path.join(_CFG, "known-demos.json"),
                             exe="/usr/bin/rq_desktop_session.py",
                             icon_dir=os.path.join(_ROOT, "desktop-icons"),
                             # with a touchscreen and the setup not done: Touch Mode
                             # and RasQberry Setup stay (test_group_window.py)
                             touchscreen=True, setup=False)


def _folders(home):
    root = home / ".local/share/rasqberry/desktop-groups"
    return {d: sorted(f[:-8] for f in os.listdir(root / d)) for d in os.listdir(root)}


def test_launchers_go_into_their_folders_and_starters_stay(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path, more=("demo-loop", "clear-leds"))
    (desk / "rq-ext-sap-quantum-led.desktop").write_text("[Desktop Entry]\nName=SAP\n")
    (desk / "notes.txt").write_text("mine")
    assert _layout(home, desk, conf, monkeypatch=monkeypatch)
    titles = {g["id"]: g["title"] for g in ds.load_groups()["groups"]}
    assert _folders(home) == {titles[g]: sorted(n for n in names if n != "rq-ext-racetraq"
                                                  and n != "rq-ext-sap-quantum-learning")
                              for g, names in _TABLE.items()}
    on_desk = sorted(os.listdir(desk))
    assert on_desk == sorted([n + ".desktop" for n in _SYSTEM + _STARTERS]
                             + ["rq-group-%s.desktop" % g for g in _TABLE] + ["notes.txt"])
    # the old More folder is gone, and so are its positions and composer's
    text = conf.read_text()
    assert "[More]" not in text and "[composer.desktop]" not in text
    order = re.findall(r"^\[(.+)\.desktop\]", text, re.M)
    assert order == _DESK_ORDER
    # nothing changed: no new layout
    assert not _layout(home, desk, conf, monkeypatch=monkeypatch)


def test_group_launcher_opens_its_folder_with_its_own_icon(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    _layout(home, desk, conf, monkeypatch=monkeypatch)
    text = (desk / "rq-group-workshops.desktop").read_text()
    assert "Name=Workshops & events\n" in text
    assert "Exec=/usr/bin/rq_desktop_session.py --open-group workshops\n" in text
    assert re.search(r"^Icon=.*/group-workshops\.svg$", text, re.M)
    assert "Terminal=false" in text and "NoDisplay" not in text
    assert os.access(desk / "rq-group-workshops.desktop", os.X_OK)
    # a group that is gone takes its icon along
    groups = ds.load_groups()
    groups["groups"] = [g for g in groups["groups"] if g["id"] != "workshops"]
    assert ds.ensure_group_launchers(str(desk), groups)
    assert not (desk / "rq-group-workshops.desktop").exists()
    assert (desk / "rq-group-contributed.desktop").exists()


def test_a_fresh_copy_on_the_desktop_wins_and_a_moved_demo_changes_folder(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    _layout(home, desk, conf, monkeypatch=monkeypatch)
    root = home / ".local/share/rasqberry/desktop-groups"
    # reinstalled on the desktop: the new copy goes into the folder
    (desk / "rasq-led.desktop").write_text("[Desktop Entry]\nName=new\nExec=rq_demo_run.sh rasq-led\n")
    # left in the wrong folder (an older grouping)
    shutil.move(str(root / "Play" / "quantum-fractals.desktop"), str(root / "LED panel"))
    assert _layout(home, desk, conf, monkeypatch=monkeypatch, size=(1920, 1200))
    assert "Name=new" in (root / "LED panel" / "rasq-led.desktop").read_text()
    assert not (desk / "rasq-led.desktop").exists()
    assert (root / "Play" / "quantum-fractals.desktop").exists()
    assert not (root / "LED panel" / "quantum-fractals.desktop").exists()


def test_open_group(monkeypatch, tmp_path):
    # the group's window (rq_group_window.py); without it the folder in
    # pcmanfm (more in test_group_window.py)
    calls = []
    monkeypatch.setattr(os, "execvp", lambda prog, args: calls.append(args))
    assert ds.open_group("nope", root=str(tmp_path)) == 1
    ds.open_group("learn", root=str(tmp_path), window="")
    assert calls == [["pcmanfm", str(tmp_path / "Learn & code")]]
    assert (tmp_path / "Learn & code").is_dir()


def test_without_the_groups_file_the_desktop_stays_flat(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    monkeypatch.setattr(ds, "GROUPS_FILE", str(tmp_path / "missing.json"))
    assert _layout(home, desk, conf, monkeypatch=monkeypatch)
    assert sorted(f[:-8] for f in os.listdir(desk) if f.endswith(".desktop")) == sorted(ds.ICON_ORDER)
    assert not (home / ".local/share/rasqberry/desktop-groups").exists()


@pytest.mark.parametrize("w,h,touch,icon", [(1920, 1080, False, 48), (1920, 1080, True, 72),
                                            (1280, 720, False, 48), (1280, 720, True, 72),
                                            (800, 480, False, 48), (800, 480, True, 72),
                                            (720, 1280, True, 72)])
def test_the_grouped_desktop_fits(w, h, touch, icon):
    # T5: Nunito labels, rows below the panel (trixie), left of Chromium on
    # large screens - and no More folder any more
    groups = ds.load_groups()
    top = ds.desktop_order(_SYSTEM + _STARTERS, {}, groups)
    assert len(top) == 14 and top == _DESK_ORDER
    label, offset = ds.LABEL_HEIGHT_NUNITO, ds.layout_top(touch, "default")
    pos, overflow = ds.plan_layout(top, w, h, touch=touch, icon=icon, label=label, top=offset)
    assert not overflow and len(pos) == 14
    for x, y in pos.values():
        assert x + icon <= w and y + icon + label <= h
    if not ds.is_small((w, h)):
        assert max(x for x, _ in pos.values()) + ds.ITEM_WIDTH <= ds.CHROMIUM_X


def test_a_tiny_screen_drops_the_starters_first(tmp_path, monkeypatch):
    home, desk, conf = _desktop(tmp_path)
    # 640x360 in touch mode (a 720x1280 panel at scale 2, sideways): 8 places
    monkeypatch.setattr(ds, "env_value", lambda key, default="", path=None: default)
    assert _layout(home, desk, conf, size=(640, 360), touch=True, icon=72, monkeypatch=monkeypatch)
    on_desk = sorted(f[:-8] for f in os.listdir(desk))
    # (the grid gets tighter first: 12 places; Learning paths has no folder)
    assert "rasqberry-setup" in on_desk and "learning-paths" in on_desk
    assert "rq-group-workshops" in on_desk and "my-quantum-programs" not in on_desk
    assert "More" not in on_desk
    root = home / ".local/share/rasqberry/desktop-groups"
    assert (root / "Learn & code" / "my-quantum-programs.desktop").exists()
    # a bigger screen again: the starters come back
    assert _layout(home, desk, conf, monkeypatch=monkeypatch)
    assert (desk / "my-quantum-programs.desktop").exists()


# --- the menu cache --------------------------------------------------------------

def _cache(tmp_path, user_manifests=()):
    home = tmp_path / "home"
    user_dir = home / ".local/config/demo-manifests"
    user_dir.mkdir(parents=True)
    for m in user_manifests:
        (user_dir / ("rq_demo_%s.json" % m["id"])).write_text(json.dumps(m))
    cache = tmp_path / "cache.sh"
    env = dict(os.environ, USER_HOME=str(home), RQ_CONFIG_FILE=str(tmp_path / "none"))
    proc = subprocess.run(["bash", _GEN, "--cache", str(cache)], capture_output=True,
                          text=True, env=env, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert subprocess.run([_SH, "-n", str(cache)]).returncode == 0
    return cache


def _pairs(cache, call):
    out = subprocess.run([_SH, "-c", '. "$1"; eval "set -- $(%s | tr \'\\n\' \' \')"; '
                          'printf "%%s\\n" "$@"' % call, "sh", str(cache)],
                         capture_output=True, text=True).stdout.splitlines()
    return list(zip(out[0::2], out[1::2]))


@needs_jq
def test_cache_lists_the_groups_and_their_demos_with_needs(tmp_path):
    sap = {"id": "sap-quantum-led", "name": "SAP Quantum LED", "category": "led-demo",
           "description": "t", "entrypoint": {"type": "python", "script": "x.py"},
           "needs_hw": {"leds": True}, "menu": {"order": 72}}
    cache = _cache(tmp_path, [sap])
    groups = _pairs(cache, "demo_group_list")
    assert [g for g, _ in groups] == ["led-panel", "play", "projects", "learn", "workshops", "contributed"]
    assert groups[0][1].startswith("LED panel: ")
    items = {g: _pairs(cache, "demo_group_items %s" % g) for g, _ in groups}
    assert [i for i, _ in items["led-panel"]] == ["rasq-led", "quantum-lights-out",
                                                  "quantum-raspberry-tie", "led-painter"]
    assert [i for i, _ in items["contributed"]] == ["sap-quantum-led"]
    assert [i for i, _ in items["play"]] == ["fun-with-quantum", "quantum-paradoxes", "quantum-fractals"]
    assert [i for i, _ in items["projects"]] == ["qoffee-maker", "quantum-mixer"]
    assert [i for i, _ in items["learn"]] == ["grok-bloch", "qiskit-tutorials", "quantum-lab",
                                              "ibm-tutorials", "ibm-courses", "composer"]
    assert [i for i, _ in items["workshops"]] == ["doqumentation"]
    names = dict(sum(items.values(), []))
    assert names["qoffee-maker"] == "Qoffee-Maker [internet, 32 GB]"
    assert names["composer"] == "IBM Quantum Composer [internet]"   # works without an account (#31)
    assert names["doqumentation"] == "Workshop & Qiskit Server (beta) [internet, 32 GB]"
    assert names["rasq-led"] == "RasQ-LED Demo"      # no [LED panel] inside its own group
    subprocess.run([_SH, "-c", '. "$1"; demo_group_title learn', "sh", str(cache)])
    title = subprocess.run([_SH, "-c", '. "$1"; demo_group_title learn', "sh", str(cache)],
                           capture_output=True, text=True).stdout
    assert title == "Learn & code\n"


# --- the menu ----------------------------------------------------------------------

def _menu_items(call):
    """The tags and texts of the menu a whiptail call shows."""
    args = call[call.index("--") + 1:]
    return list(zip(args[0::2], args[1::2]))


@needs_jq
def test_quantum_demos_shows_paths_groups_stop_and_manage(menu_env, tmp_path):  # noqa: F811
    cache = _cache(tmp_path)
    menu_env("do_quantum_demo_menu", extra_env={"WT_RC_menu": "1"}, cache=cache)
    call = menu_env.whiptail_calls()[-1]
    assert call[call.index("--title") + 1] == "RasQberry: Quantum Demos"
    items = _menu_items(call)
    assert [t for t, _ in items] == ["PATHS", "led-panel", "play", "projects", "learn",
                                     "workshops", "contributed", "STOP", "MANAGE"]
    assert len(items) <= 11   # no scrolling (11 visible lines)


@needs_jq
@pytest.mark.parametrize("group,first,last", [
    ("led-panel", ["IBM", "rasq-led"], ["led-painter", "DISP", "CLEAR", "LEDS"]),
    ("contributed", ["sap-quantum-led"], ["ADDX"]),
    ("learn", ["MYQ", "grok-bloch"], ["composer"]),
    ("workshops", ["doqumentation"], ["LOOP"]),
    # the Coin Game, an icon of its own in the Play window, is here too (F3)
    ("play", ["fun-with-quantum", "COIN", "quantum-paradoxes"], ["quantum-fractals"]),
])
def test_a_group_submenu_has_its_fixed_entries(menu_env, tmp_path, group, first, last):  # noqa: F811
    sap = {"id": "sap-quantum-led", "name": "SAP Quantum LED", "category": "led-demo",
           "description": "t", "entrypoint": {"type": "python", "script": "x.py"},
           "needs_hw": {"leds": True}, "menu": {"order": 72}}
    cache = _cache(tmp_path, [sap])
    menu_env("do_demo_group_menu %s" % group, extra_env={"WT_RC_menu": "1"}, cache=cache)
    call = menu_env.whiptail_calls()[-1]
    tags = [t for t, _ in _menu_items(call)]
    assert tags[:len(first)] == first and tags[-len(last):] == last, tags
    assert len(tags) <= 11


@needs_jq
def test_group_lines_name_only_demos_that_are_there(tmp_path):
    # user test 2026-10-08, F3: "Big projects: ... traQmania" while traQmania
    # was not in the submenu; the Contributed line named SAP demos not added
    lines = dict(_pairs(_cache(tmp_path), "demo_group_list"))
    assert lines["projects"] == "Big projects: Qoffee-Maker, Quantum Mixer"
    assert lines["contributed"] == "Contributed demos: add demos from the catalogue"
    for line in lines.values():
        assert "racetraQ" not in line and "SAP" not in line
    trq = {"id": "racetraq", "name": "racetraQ", "category": "game",
           "description": "t", "entrypoint": {"type": "python", "script": "x.py"},
           "menu": {"order": 80}}
    sap = {"id": "sap-quantum-led", "name": "SAP Quantum LED", "category": "led-demo",
           "description": "t", "entrypoint": {"type": "python", "script": "x.py"},
           "needs_hw": {"leds": True}, "menu": {"order": 72}}
    lines = dict(_pairs(_cache(tmp_path / "added", [trq, sap]), "demo_group_list"))
    assert lines["projects"] == "Big projects: Qoffee-Maker, Quantum Mixer, racetraQ"
    assert lines["contributed"] == "Contributed demos: SAP Quantum LED, more from the catalogue"


@needs_jq
def test_an_install_under_the_old_name_stays_in_big_projects(tmp_path):
    # traQmania was renamed racetraQ (2026-10-08): a Pi that still has it
    # installed as traqmania keeps it in Big projects (the racetraq entry
    # "replaces" it), in the menu and on the desktop, until it is moved over
    old = {"id": "traqmania", "name": "traQmania", "category": "game",
           "description": "t", "entrypoint": {"type": "docker", "docker_image": "ghcr.io/janlahmann/traqmania",
                                               "working_dir": "traQmania"},
           "menu": {"order": 75}}
    lines = dict(_pairs(_cache(tmp_path, [old]), "demo_group_list"))
    assert lines["projects"] == "Big projects: Qoffee-Maker, Quantum Mixer, traQmania"
    assert "traQmania" not in lines["contributed"]
    path = tmp_path / "rq-ext-traqmania.desktop"
    path.write_text("[Desktop Entry]\nName=traQmania\n")
    assert ds.launcher_group("rq-ext-traqmania", str(path), ds.load_groups(),
                             dirs=[_MANIFESTS, str(tmp_path / "home/.local/config/demo-manifests")],
                             known=os.path.join(_CFG, "known-demos.json")) == "projects"


def test_the_coin_game_entry_starts_its_notebook():
    menu = open(os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")).read()
    body = menu[menu.index("do_demo_group_menu() {"):]
    assert 'COIN)  run_engine_demo "$BIN_DIR/rq_demo_run.sh" fun-with-quantum coin-game' in body
    desk = open(os.path.join(_ROOT, "RQB2-config", "desktop-bookmarks", "quantum-coin-game.desktop")).read()
    assert "rq_demo_run.sh fun-with-quantum coin-game" in desk


def test_without_a_cache_the_groups_still_show(menu_env):  # noqa: F811
    menu_env("_RQ_DEMO_CACHE_WARNED=1; do_quantum_demo_menu; do_demo_group_menu led-panel",
             extra_env={"WT_RC_menu": "1"})
    calls = menu_env.whiptail_calls()
    top = [t for t, _ in _menu_items(calls[0])]
    assert top == ["PATHS", "led-panel", "play", "projects", "learn", "workshops", "contributed",
                   "STOP", "MANAGE"]
    assert [t for t, _ in _menu_items(calls[1])] == ["IBM", "DISP", "CLEAR", "LEDS"]


def test_manage_demos_menu(menu_env):  # noqa: F811
    menu_env("do_manage_demos_menu", extra_env={"WT_RC_menu": "1"})
    call = menu_env.whiptail_calls()[-1]
    assert [t for t, _ in _menu_items(call)] == ["DALL", "ADDX", "UPD", "REM", "DSTP"]


def test_ibm_led_demo_is_the_same_in_both_menus():
    menu = open(_MENU, encoding="utf-8").read()
    assert "do_led_ibm_demo() {" in menu
    assert menu.count("do_led_ibm_demo ") == 2   # the group menu and LED options
    assert menu.count('run_led_demo bg "IBM LED Demo" "$BIN_DIR" python3 rq_led_ibm_logo.py') == 1


# --- texts ---------------------------------------------------------------------------

def test_no_text_names_an_old_menu_path():
    old = [r"Quantum Demos (>|->|&rarr;|→) (Remove a demo|Stop Docker demos|Update demos|"
           r"Continuous Demo Loop|LEDs\b|Add demo)",
           r"RasQberry menu > LEDs", r"\(LEDs > ", r"\*\*LEDs\*\* →"]
    hits = []
    for folder in ("RQB2-bin", "RQB2-config", "docs", "RQB2-system"):
        for dirpath, _, files in os.walk(os.path.join(_ROOT, folder)):
            for f in files:
                try:
                    text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                for pat in old:
                    hits += ["%s: %s" % (f, m.group(0)) for m in re.finditer(pat, text)]
    assert not hits, hits


def test_removing_a_catalogue_demo_also_clears_its_group_folder():
    text = open(os.path.join(_BIN, "rq_demo_add_external.sh")).read()
    assert '"$USER_HOME"/.local/share/rasqberry/desktop-groups/*/"rq-ext-${id}.desktop"' in text
    assert ds.group_dir("/home/x") == "/home/x/.local/share/rasqberry/desktop-groups"


def test_demos_in_one_group_window_have_their_own_icons():
    # user test 2026-10-08, F4: shared cups and globes, faint generic icons
    bm = os.path.join(_ROOT, "RQB2-config", "desktop-bookmarks")
    icons = {}
    for f in os.listdir(bm):
        for line in open(os.path.join(bm, f)):
            if line.startswith("Icon="):
                icons[f[:-len(".desktop")]] = line.strip()[5:]
    pairs = [("qoffee-maker", "quantum-mixer"), ("quantum-lab", "ibm-quantum-tutorials"),
             ("ibm-quantum-tutorials", "ibm-quantum-courses"), ("quantum-lab", "ibm-quantum-courses"),
             # fresh-card test 2026-10-08, F4: Grokking's atom, the circuit tile
             ("quantum-paradoxes", "grok-bloch"), ("doqumentation", "qiskit-tutorials")]
    for a, b in pairs:
        assert icons[a] != icons[b], (a, b)
    for name in ("quantum-mixer", "quantum-lab", "ibm-quantum-tutorials", "ibm-quantum-courses", "demo-loop",
                 "quantum-paradoxes", "doqumentation"):
        path = icons[name]
        assert path.startswith("/usr/share/icons/rasqberry/"), name
        assert os.path.exists(os.path.join(_ROOT, "desktop-icons", os.path.basename(path))), name
    reg = json.load(open(os.path.join(_ROOT, "RQB2-config", "known-demos.json")))
    for d in reg["demos"]:
        if d.get("icon"):
            assert os.path.exists(os.path.join(_ROOT, "desktop-icons", d["icon"])), d["id"]


def test_a_demos_icon_is_the_same_in_its_manifest_and_on_the_desktop():
    # the group window and the menu read the bookmark, a regenerated entry the
    # manifest: a new icon in one only came back in the other
    bm = os.path.join(_ROOT, "RQB2-config", "desktop-bookmarks")
    for demo_id in ("quantum-paradoxes", "doqumentation", "qiskit-tutorials", "grok-bloch"):
        m = json.load(open(os.path.join(_ROOT, "RQB2-config", "demo-manifests", f"rq_demo_{demo_id}.json")))
        icon = [line.strip()[5:] for line in open(os.path.join(bm, f"{demo_id}.desktop")) if line.startswith("Icon=")]
        assert icon == [m["icon"]["path"]], demo_id
