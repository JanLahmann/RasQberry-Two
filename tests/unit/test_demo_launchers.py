"""The shipped demo launchers come from the demo manifests (B5); CI runs
rq_demo_generate_desktop.py --check on the committed ones."""

import os
import sys

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
