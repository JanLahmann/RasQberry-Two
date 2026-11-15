"""The shipped demo launchers come from the demo manifests (B5); CI runs
rq_demo_generate_desktop.py --check on the committed ones."""

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "RQB2-bin"))

import rq_demo_generate_desktop as gen  # noqa: E402


def test_a_dev_variant_launcher_is_marked():
    manifest = {"id": "demo", "name": "Demo", "keywords": ["q"], "icon": {"path": "i.svg"}}
    variant = {"id": "v", "name": "Variant", "maturity": "dev"}
    text = gen.render("rq_demo_demo.json", manifest, {"comment": "Try it", "title": True}, variant)
    assert "Name=Variant (beta)\n" in text and "Comment=(beta) Try it\n" in text
    assert 'Exec=/usr/bin/rq_hold_on_error.sh -t "Variant" /usr/bin/rq_demo_run.sh demo v\n' in text
    assert "X-RasQberry-OnDesktop" not in text


def test_a_server_demo_keeps_its_window_and_a_variant_its_own_entrypoint():
    manifest = {"id": "srv", "name": "Server", "entrypoint": {"type": "docker"}}
    text = gen.render("m.json", manifest, {"terminal": False}, None)
    assert "Terminal=true\n" in text and "Exec=/usr/bin/rq_hold_on_error.sh /usr/bin/rq_demo_run.sh srv\n" in text
    web = {"id": "web", "name": "Web", "entrypoint": {"type": "browser", "browser_url": "https://x.example/"}}
    text = gen.render("m.json", {"id": "d", "name": "D", "entrypoint": {"type": "browser"}},
                      {"comment": "c", "terminal": False}, web)
    assert "Exec=chromium --password-store=basic https://x.example/\n" in text
    assert "X-RasQberry-Demo=d web\n" in text


def test_a_title_with_shell_characters_is_refused():
    with pytest.raises(SystemExit):
        gen.render("m.json", {"id": "d", "name": 'Cost $5'}, {"comment": "c", "title": True}, None)


def test_a_dropped_demo_loses_its_launcher_whatever_the_file_name(tmp_path):
    import rq_demo_level
    path = tmp_path / "ibm-composer.desktop"
    path.write_text(gen.render("m.json", {"id": "composer", "name": "C", "description": "d",
                                          "entrypoint": {"type": "browser", "browser_url": "https://c.example/"}},
                               {"terminal": False, "file": "ibm-composer"}, None))
    assert not rq_demo_level.bookmark_kept(str(path), kept={})
