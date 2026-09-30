"""
Every entry in RQB2-config/ must be classified in RQB2-config/CONFIG_FILES.md
(issue #290), and the branch updater must treat the classes accordingly.
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_CONFIG = os.path.join(_ROOT, "RQB2-config")
_UPDATER = os.path.join(_ROOT, "RQB2-bin", "rq_update_from_branch.sh")

_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(default|state|generated|build)\s*\|")


def _inventory():
    rows = {}
    with open(os.path.join(_CONFIG, "CONFIG_FILES.md"), encoding="utf-8") as fh:
        for line in fh:
            match = _ROW.match(line)
            if match:
                rows[match.group(1).rstrip("/")] = match.group(2)
    return rows


def test_every_config_entry_is_classified():
    inventory = _inventory()
    entries = [e for e in os.listdir(_CONFIG) if not e.startswith(".")]
    missing = sorted(set(entries) - set(inventory))
    assert not missing, (
        f"Add these to RQB2-config/CONFIG_FILES.md (default/state/generated/build): {missing}"
    )


def test_inventory_has_no_stale_rows():
    stale = sorted(set(_inventory()) - set(os.listdir(_CONFIG)))
    assert not stale, f"CONFIG_FILES.md lists entries that no longer exist: {stale}"


def test_updater_does_not_plainly_copy_state_generated_or_build_files():
    updater = open(_UPDATER, encoding="utf-8").read()
    special = [name for name, cls in _inventory().items() if cls != "default"]
    for name in special:
        assert re.search(rf"^\s*{re.escape(name)}[|)]", updater, re.M) or re.search(
            rf"\|\s*{re.escape(name)}\)", updater
        ), f"rq_update_from_branch.sh needs a case for {name} (class != default)"
