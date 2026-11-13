"""Demo levels (rq_demo_level.py): dev / beta / prod images ship the right demos."""

import importlib.util
import json
import os
import shutil

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "rq_demo_level", os.path.join(_ROOT, "RQB2-bin", "rq_demo_level.py"))
lvl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lvl)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def tree(tmp_path):
    cfg = tmp_path / "RQB2-config"
    m = cfg / "demo-manifests"
    _write(str(m / "rq_demo_schema.json"), {"title": "schema"})
    _write(str(m / "rq_demo_ready.json"), {"id": "ready", "maturity": "prod"})
    _write(str(m / "rq_demo_old.json"), {"id": "old", "maturity": "stable"})
    _write(str(m / "rq_demo_trial.json"), {"id": "trial", "maturity": "beta"})
    _write(str(m / "rq_demo_new.json"), {"id": "new"})
    _write(str(m / "rq_demo_games.json"), {"id": "games", "maturity": "dev", "variants": [
        {"id": "coin", "maturity": "prod"}, {"id": "chsh", "maturity": "beta"}, {"id": "ghz"}]})
    _write(str(m / "learning-paths.json"), {"paths": [
        {"id": "a", "steps": [{"demo": "ready"}, {"demo": "new"}, {"command": "x"}],
         "next": [{"path": "b"}, {"url": "https://example.org"}]},
        {"id": "b", "steps": [{"demo": "games", "variant": "ghz"}, {"demo": "trial"}]}]})
    _write(str(m / "demo-groups.json"), {"groups": [{"id": "play"}, {"id": "beta", "beta": True}]})
    _write(str(cfg / "known-demos.json"), {"demos": [
        {"id": "cat-prod", "maturity": "prod"}, {"id": "cat-beta", "maturity": "beta"},
        {"id": "cat-none"}]})
    b = cfg / "desktop-bookmarks"
    _write(str(b / "ready.desktop"), "[Desktop Entry]\nExec=/usr/bin/rq_demo_run.sh ready\n")
    _write(str(b / "new.desktop"), "[Desktop Entry]\nExec=/usr/bin/rq_demo_run.sh new\n")
    _write(str(b / "coin.desktop"), "[Desktop Entry]\nExec=rq_demo_run.sh games coin\n")
    _write(str(b / "ghz.desktop"), "[Desktop Entry]\nExec=rq_demo_run.sh games ghz\n")
    _write(str(b / "pick.desktop"), "[Desktop Entry]\nExec=rq_demo_choose.sh games\n")
    _write(str(b / "trial.desktop"), "[Desktop Entry]\nExec=chromium https://example.org\n")
    _write(str(b / "menu.desktop"), "[Desktop Entry]\nExec=/usr/bin/rq_menu.sh\n")
    return cfg


def _ids(cfg):
    m = cfg / "demo-manifests"
    return sorted(f[len("rq_demo_"):-5] for f in os.listdir(str(m))
                  if f.startswith("rq_demo_") and f != "rq_demo_schema.json")


def test_levels_and_defaults():
    assert lvl.level_of(None) == "dev"
    assert lvl.level_of("stable") == "prod"
    assert lvl.level_of("bogus") == "dev"
    assert lvl.level_of(None, "beta") == "beta"
    assert [lvl.for_branch(b) for b in ("main", "beta", "development", "dev-x")] == \
        ["prod", "beta", "dev", "dev"]


def test_image_level_from_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv("RQ_DEMO_LEVEL", "beta")
    assert lvl.image_level() == "beta"
    monkeypatch.delenv("RQ_DEMO_LEVEL")
    monkeypatch.setattr(lvl, "LEVEL_FILE", str(tmp_path / "missing"))
    assert lvl.image_level() == "dev"


def test_dev_image_keeps_all_and_writes_the_levels(tree):
    lvl.apply(str(tree), "dev")
    assert _ids(tree) == ["games", "new", "old", "ready", "trial"]
    m = tree / "demo-manifests"
    # a missing level stays missing: the Pi marks only an explicit dev
    assert "maturity" not in _read(str(m / "rq_demo_new.json"))
    assert _read(str(m / "rq_demo_trial.json"))["maturity"] == "beta"
    assert _read(str(m / "rq_demo_old.json"))["maturity"] == "stable"
    games = _read(str(m / "rq_demo_games.json"))
    assert games["maturity"] == "dev"
    assert [(v["id"], v.get("maturity")) for v in games["variants"]] == \
        [("coin", "prod"), ("chsh", "beta"), ("ghz", None)]
    assert len(os.listdir(str(tree / "desktop-bookmarks"))) == 7
    assert [g["id"] for g in _read(str(m / "demo-groups.json"))["groups"]] == ["play", "beta"]
    assert len(_read(str(m / "learning-paths.json"))["paths"]) == 2


def test_beta_image(tree):
    kept = lvl.apply(str(tree), "beta")
    assert _ids(tree) == ["games", "old", "ready", "trial"]
    assert kept["games"] == {"coin", "chsh"}
    m = tree / "demo-manifests"
    # nothing left at level dev: nothing is marked '(beta)' in a beta image
    for demo in _ids(tree):
        data = _read(str(m / ("rq_demo_%s.json" % demo)))
        assert data["maturity"] in ("beta", "prod", "stable"), demo
        assert all(v.get("maturity", data["maturity"]) != "dev" for v in data.get("variants", []))
    # a dev demo kept for its variants gets their best level
    assert _read(str(m / "rq_demo_games.json"))["maturity"] == "prod"
    assert [d["id"] for d in _read(str(tree / "known-demos.json"))["demos"]] == \
        ["cat-prod", "cat-beta"]
    # path b is left with one step: no tour, dropped (and its "next" link)
    paths = _read(str(m / "learning-paths.json"))["paths"]
    assert [p["id"] for p in paths] == ["a"]
    assert [g["id"] for g in _read(str(m / "demo-groups.json"))["groups"]] == ["play"]
    assert paths[0]["steps"] == [{"demo": "ready"}, {"command": "x"}]
    assert paths[0]["next"] == [{"url": "https://example.org"}]
    assert sorted(os.listdir(str(tree / "desktop-bookmarks"))) == \
        ["coin.desktop", "menu.desktop", "pick.desktop", "ready.desktop", "trial.desktop"]


def test_prod_image(tree):
    lvl.apply(str(tree), "prod")
    assert _ids(tree) == ["games", "old", "ready"]
    assert [v["id"] for v in _read(str(tree / "demo-manifests" / "rq_demo_games.json"))["variants"]] \
        == ["coin"]
    assert [d["id"] for d in _read(str(tree / "known-demos.json"))["demos"]] == ["cat-prod"]
    # a web launcher named after a dropped demo goes too
    assert not (tree / "desktop-bookmarks" / "trial.desktop").exists()


def test_unlabelled_demo_with_labelled_variants(tmp_path):
    # Fun with Quantum: no level of its own, dev and beta variants
    m = tmp_path / "RQB2-config" / "demo-manifests"
    _write(str(m / "rq_demo_fwq.json"), {"id": "fwq", "variants": [
        {"id": "coin", "maturity": "beta"}, {"id": "chsh", "maturity": "dev"}]})
    lvl.apply(str(tmp_path / "RQB2-config"), "dev")
    assert "maturity" not in _read(str(m / "rq_demo_fwq.json"))      # stays in Play, unmarked
    lvl.apply(str(tmp_path / "RQB2-config"), "beta")
    data = _read(str(m / "rq_demo_fwq.json"))
    assert data["maturity"] == "beta" and [v["id"] for v in data["variants"]] == ["coin"]


def test_real_config_trims_cleanly(tmp_path):
    cfg = tmp_path / "RQB2-config"
    shutil.copytree(os.path.join(_ROOT, "RQB2-config"), str(cfg))
    for level in ("prod", "beta", "dev"):
        assert lvl.main(["apply", str(cfg), level]) == 0
        assert os.path.isfile(str(cfg / "demo-manifests" / "rq_demo_schema.json"))


def test_beta_image_turns_online_steps_into_web_steps_and_unmarks_launchers(tmp_path):
    cfg = tmp_path / "RQB2-config"
    m = cfg / "demo-manifests"
    _write(str(m / "rq_demo_docs.json"), {"id": "docs", "maturity": "dev"})
    _write(str(m / "rq_demo_ready.json"), {"id": "ready", "maturity": "beta"})
    _write(str(m / "learning-paths.json"), {"paths": [{"id": "p", "steps": [
        {"demo": "docs", "name": "Quickstart", "page": "/q", "online": "https://example.org/q", "try": "t"},
        {"demo": "docs"},
        {"demo": "ready"}]}]})
    b = cfg / "desktop-bookmarks"
    _write(str(b / "paths.desktop"),
           "[Desktop Entry]\nName=Learning paths (beta)\nComment=(beta) Short tours\nExec=/usr/bin/rq_learning_paths.sh\n")
    lvl.apply(str(cfg), "beta")
    steps = _read(str(m / "learning-paths.json"))["paths"][0]["steps"]
    assert steps == [{"name": "Quickstart", "try": "t", "url": "https://example.org/q"}, {"demo": "ready"}]
    text = (b / "paths.desktop").read_text()
    assert "Name=Learning paths\n" in text and "Comment=Short tours\n" in text


def test_dev_image_keeps_the_beta_marks(tmp_path):
    b = tmp_path / "RQB2-config" / "desktop-bookmarks"
    _write(str(tmp_path / "RQB2-config" / "demo-manifests" / "rq_demo_x.json"), {"id": "x"})
    _write(str(b / "paths.desktop"), "[Desktop Entry]\nName=Learning paths (beta)\n")
    lvl.apply(str(tmp_path / "RQB2-config"), "dev")
    assert "Name=Learning paths (beta)" in (b / "paths.desktop").read_text()
