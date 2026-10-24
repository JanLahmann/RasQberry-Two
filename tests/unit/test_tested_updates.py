"""
Tested updates of the demos the image ships (Jan, 2026-10-24): the online
catalogue's "tested_updates" moves a downloaded demo to a newer pin we
tested, with a notice in the taskbar and one click (rq_demo_update.sh
--tested), and only from the source the release already uses.
"""

import importlib.util
import json
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_CFG = os.path.join(_ROOT, "RQB2-config")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BIN, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cat = _load("rq_catalogue")
ind = _load("rq_slot_indicator")

REPO = "ghcr.io/example/lab"
IMG_REL = REPO + "@sha256:" + "1" * 64
IMG_NEW = REPO + "@sha256:" + "2" * 64
IMG_OLDER_TESTED = REPO + "@sha256:" + "3" * 64
REF_REL = "a" * 40
REF_NEW = "b" * 40


@pytest.fixture
def pi(tmp_path):
    """A shipped image demo (lab) and a shipped notebook demo (games), downloaded."""
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    (mdir / "rq_demo_lab.json").write_text(json.dumps({
        "id": "lab", "name": "Qiskit Live",
        "entrypoint": {"type": "docker", "docker_image": IMG_REL}}))
    (mdir / "rq_demo_games.json").write_text(json.dumps({
        "id": "games", "name": "Games",
        "entrypoint": {"type": "jupyter", "working_dir": "games"},
        "install": {"repo_url": "https://github.com/x/games.git", "ref": REF_REL}}))
    home = tmp_path / "home"
    (home / "RasQberry-Two" / "demos" / "games" / ".git").mkdir(parents=True)
    return {"manifests": str(mdir), "home": str(home), "repo": "RasQberry-Two"}


def _image(**kw):
    t = {"id": "lab", "kind": "image", "pin": IMG_NEW, "from": [IMG_REL],
         "label": "Qiskit 2.6, November snapshot", "added": "2026-11-03"}
    t.update(kw)
    return t


def _ref(**kw):
    t = {"id": "games", "kind": "ref", "pin": REF_NEW, "from": [REF_REL],
         "label": "two new games", "added": "2026-11-03"}
    t.update(kw)
    return t


def _news(pi, *tested, has_image=lambda image: True):
    data = {"catalogue_version": 9, "demos": [], "tested_updates": list(tested)}
    return cat.tested_news(data, pi["manifests"], pi["home"], pi["repo"], has_image)


def _chose(pi, key, rel, chosen, label):
    f = os.path.join(pi["home"], pi["repo"], "demos", ".demo-versions")
    with open(f, "a") as fh:
        fh.write(f"{key}\t{rel}\t{chosen}\t{label}\n")


# --- which entries a Pi takes ------------------------------------------------------

def test_sound_entries_pass(pi):
    for t in (_image(), _ref(), _image(note="Qiskit 2.6.1", download_mb=900)):
        assert cat.tested_problems(t, "t", pi["manifests"]) == []


@pytest.mark.parametrize("change, problem", [
    (dict(pin="ghcr.io/someone-else/lab@sha256:" + "2" * 64), "is not an image of ghcr.io/example/lab"),
    (dict(pin=REPO + ":latest"), "not an image digest"),
    (dict(pin=REPO + "@sha256:" + "2" * 63), "not an image digest"),
    (dict(**{"from": []}), "from is not a list"),
    (dict(**{"from": ["docker.io/evil/lab@sha256:" + "1" * 64]}), "from is not an image of"),
    (dict(kind="tarball"), "kind is not image or ref"),
    (dict(label="x" * 61), "label is not a one-line text"),
    (dict(label="new\x1b[2J"), "label is not a one-line text"),
    (dict(download_mb=-1), "download_mb"),
])
def test_an_image_update_only_from_the_same_image(pi, change, problem):
    found = cat.tested_problems(_image(**change), "t", pi["manifests"])
    assert any(problem in line for line in found), found


def test_a_ref_update_is_a_full_commit(pi):
    assert "pin is not a full commit SHA" in cat.tested_problems(_ref(pin="main"), "t", pi["manifests"])[0]
    # the image kind needs an image pin in the manifest
    assert "not a demo this image ships" in cat.tested_problems(_ref(id="lab"), "t", pi["manifests"])[0]


def test_usable_keeps_the_sound_ones_and_leaves_out_other_images_quietly(pi):
    data = {"catalogue_version": 9, "demos": [],
            "tested_updates": [_image(), _ref(pin="main"), _image(id="not-on-this-image"), _image()]}
    keep, bad = cat.sort_tested(data, pi["manifests"])
    assert keep == [_image()]
    assert any("full commit SHA" in b for b in bad) and any("appears twice" in b for b in bad)
    assert not any("not-on-this-image" in b for b in bad)
    assert cat.usable(data, pi["manifests"])["tested_updates"] == [_image()]


def test_the_shipped_catalogue_has_the_list_and_passes():
    data = json.load(open(os.path.join(_CFG, "known-demos.json")))
    assert isinstance(data["tested_updates"], list)
    assert cat.problems(data, cat.shipped_ids(os.path.join(_CFG, "demo-manifests"))) == []


def test_a_real_shipped_docker_demo_takes_an_update_of_its_own_image():
    mdir = os.path.join(_CFG, "demo-manifests")
    m = json.load(open(os.path.join(mdir, "rq_demo_quantum-lab.json")))
    rel = m["entrypoint"]["docker_image"]
    t = {"id": "quantum-lab", "kind": "image", "pin": rel.split("@")[0] + "@sha256:" + "f" * 64,
         "from": [rel], "label": "newer snapshot"}
    assert cat.tested_problems(t, "t", mdir) == []


# --- who gets the notice -------------------------------------------------------------

def test_a_downloaded_demo_on_its_release_version_gets_it(pi):
    items = _news(pi, _image(), _ref())
    assert [(i["id"], i["update"]) for i in items] == [("lab", "image"), ("games", "ref")]
    assert items[0]["name"] == "Qiskit Live" and items[0]["kind"] == "tested"
    assert items[0]["key"] == f"tested:lab:image:{IMG_NEW}"


def test_not_for_another_release_or_a_demo_that_is_not_downloaded(pi, tmp_path):
    assert _news(pi, _image(**{"from": [IMG_OLDER_TESTED]})) == []
    assert _news(pi, _image(), has_image=lambda image: False) == []
    os.rmdir(os.path.join(pi["home"], "RasQberry-Two", "demos", "games", ".git"))
    assert _news(pi, _ref()) == []


def test_not_for_a_version_chosen_by_hand(pi):
    _chose(pi, "lab:image", IMG_REL, IMG_OLDER_TESTED, "bc4229e-jupyter, 2026-10-02")
    assert _news(pi, _image()) == []


def test_an_earlier_tested_update_moves_on_and_the_new_one_ends_it(pi):
    _chose(pi, "lab:image", IMG_REL, IMG_OLDER_TESTED, cat.TESTED_LABEL + "October fix")
    asked = []
    items = _news(pi, _image(), has_image=lambda image: asked.append(image) or True)
    assert len(items) == 1 and asked == [IMG_OLDER_TESTED]     # the image in use is downloaded
    _chose(pi, "lab:image", IMG_REL, IMG_NEW, cat.TESTED_LABEL + "November")
    assert _news(pi, _image()) == []


def test_a_new_release_wins(pi):
    # the choice was made under the old release pin: the new release's pin counts
    _chose(pi, "lab:image", IMG_OLDER_TESTED, "x", "y")
    assert len(_news(pi, _image())) == 1


# --- what the user sees --------------------------------------------------------------

def test_notice_menu_login_line_and_the_badge_command(pi):
    item = _news(pi, _image())[0]
    assert cat.popup_text(item) == ("A tested update for Qiskit Live is available (Qiskit 2.6, "
                                    "November snapshot). Install it from the RasQberry badge in the taskbar.")
    assert cat.menu_label(item) == "Update Qiskit Live…"
    assert cat.command(item) == ["--tested", "lab:image"]
    assert "sudo rq_demo_update.sh --tested lab:image" in cat.login_line([item])
    argv = ind.catalogue_argv(item)
    assert "sudo /usr/bin/rq_demo_update.sh --tested lab:image ||" in argv[-1]


def test_the_command_line_prints_the_update_for_the_script(pi, tmp_path):
    shipped = tmp_path / "known-demos.json"
    shipped.write_text(json.dumps({"catalogue_version": 9, "demos": [], "tested_updates": [_ref()]}))
    env = dict(os.environ, RQ_MANIFEST_DIR=pi["manifests"], RQ_CATALOGUE_SHIPPED=str(shipped),
               RQ_CATALOGUE_CACHE_DIR=str(tmp_path / "cache"), RQ_USER_HOME=pi["home"])
    run = lambda key: subprocess.run(["python3", os.path.join(_BIN, "rq_catalogue.py"), "--tested", key],
                                     capture_output=True, text=True, env=env)
    out = run("games:ref")
    assert out.returncode == 0 and out.stdout == f"{REF_NEW}\ttwo new games\t0\n"
    assert run("games:image").returncode == 1 and run("lab:image").returncode == 1


def test_the_update_script_dispatches_after_its_functions():
    text = open(os.path.join(_BIN, "rq_demo_update.sh")).read()
    call = text.index('apply_tested "${2:-}"')
    for fn in ("apply_tested() {", "apply_image() {", "apply_ref() {", "updatable() {"):
        assert text.index(fn) < call, fn
    assert '"tested: $label"' in text and cat.TESTED_LABEL == "tested: "
