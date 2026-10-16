"""
The reference pages generated from the code (docs/reference/): up to date,
complete, and small enough for the helpers' context.
"""

import glob
import json
import os
import re
import subprocess
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REF = os.path.join(_ROOT, "docs", "reference")
_GEN = os.path.join(_REF, "reference_docs.py")
_CONFIG = os.path.join(_ROOT, "RQB2-config")


def _page(name):
    with open(os.path.join(_REF, name), encoding="utf-8") as fh:
        return fh.read()


def test_reference_pages_are_up_to_date():
    r = subprocess.run([sys.executable, _GEN, "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + "\nRun: python3 docs/reference/reference_docs.py"


def test_every_page_says_it_is_generated():
    for path in glob.glob(os.path.join(_REF, "*.md")):
        with open(path, encoding="utf-8") as fh:
            assert fh.read().startswith("<!-- Generated from the code by docs/reference/reference_docs.py"), path


def test_main_menu_entries_are_all_there():
    menu = open(os.path.join(_CONFIG, "RQB2_menu.sh"), encoding="utf-8").read()
    main = menu[menu.index("do_rasqberry_menu() {"):]
    main = main[:main.index("FUN=$(show_menu")]
    labels = re.findall(r'[A-Z_]+ "([^"$]+)"', main)
    assert len(labels) >= 8
    page = _page("menu.md")
    for label in labels:
        assert label in page, label


def test_every_demo_and_group_is_described():
    demos, desktop = _page("demos.md"), _page("desktop.md")
    for path in glob.glob(os.path.join(_CONFIG, "demo-manifests", "rq_demo_*.json")):
        if path.endswith("schema.json"):
            continue
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
        assert f"id `{m['id']}`" in demos, m["id"]
    with open(os.path.join(_CONFIG, "known-demos.json"), encoding="utf-8") as fh:
        for d in json.load(fh)["demos"]:
            assert f"id `{d['id']}`" in demos, d["id"]
    with open(os.path.join(_CONFIG, "demo-manifests", "demo-groups.json"), encoding="utf-8") as fh:
        for g in json.load(fh)["groups"]:
            assert f"### {g['title']}" in desktop, g["id"]
            assert f"**{g['title']}**" in _page("menu.md"), g["id"]


def test_every_setting_is_listed():
    page = _page("settings.md")
    with open(os.path.join(_CONFIG, "rasqberry_environment.env"), encoding="utf-8") as fh:
        keys = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=", fh.read(), re.M)
    for key in keys:
        assert f"`{key}`" in page, key
    # the sound delay and the hotspot survive A/B updates
    assert "`RQ_AUDIO_DELAY_MS` = `0` **kept**" in page


def test_rq_help_commands_are_all_there():
    page = _page("commands.md")
    for name in ("rq_demo_run.sh", "rq_info.sh", "rq_python", "rq_update_check.sh"):
        assert f"### {name}" in page, name


def test_pages_fit_the_helpers_context():
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(_REF, "*.md")))
    assert total < 120_000, total


def test_folders_list_only_what_the_desktop_has():
    # rig mission 2026-10-16: LED Test was listed in the LED panel folder,
    # but the image puts only the ICON_ORDER launchers on the desktop
    desktop = _page("desktop.md")
    folders = desktop[desktop.index("## Group icons"):desktop.index("## Taskbar")]
    assert "**LED Test**" not in folders
    assert "Only there: **LED Test**." in desktop
