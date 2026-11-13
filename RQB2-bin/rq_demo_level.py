#!/usr/bin/env python3
"""
Demo levels: which demos an image ships (Jan, 2026-11-13).

Every demo, variant and catalogue entry has a level in its "maturity" field:

    dev   only in development images (also not in the catalogue elsewhere)
    beta  in development and beta images
    prod  in every image ("stable" is the old name of prod)

Without a value, a demo is dev, and a variant takes its demo's level: a new
demo reaches a beta or prod image only once someone has marked it. The
level of an image comes from its branch (main: prod, beta: beta, anything
else: dev; the build can override it) and is stored in /etc/rasqberry-demo-level.

"apply" trims a RQB2-config tree to one level. It runs in the image build
before RQB2-config is deployed, and after "Update from GitHub Branch":
  - drops the manifests, variants and catalogue entries below the level;
  - drops the learning-path steps of dropped demos (and paths left empty);
  - drops desktop-bookmarks/ launchers that start a dropped demo or variant;
  - rewrites "maturity" to what the Pi shows: "beta" (the '(beta)' mark and
    the "Beta: try & tell us" group) only for a dev demo in a dev image,
    nothing otherwise. The rest of RasQberry reads only that.

Usage:
    rq_demo_level.py apply CONFIG_DIR [LEVEL]   (LEVEL: default the image's)
    rq_demo_level.py image                      (print the image's level)
    rq_demo_level.py for-branch BRANCH          (print a branch's level)
"""

import glob
import json
import os
import re
import sys

LEVELS = ("dev", "beta", "prod")
ALIASES = {"stable": "prod"}
LEVEL_FILE = "/etc/rasqberry-demo-level"
# A launcher's Exec: rq_demo_run.sh ID [VARIANT] or rq_demo_choose.sh ID
_EXEC = re.compile(r"rq_demo_(?:run|choose)\.sh\s+([a-z0-9][a-z0-9-]*)(?:\s+([a-z0-9][a-z0-9-]*))?")


def level_of(value, default="dev"):
    """
    The level a maturity value stands for.

    Args:
        value (str): A "maturity" field (None when missing).
        default (str): The level of a missing or unknown value.

    Returns:
        str: dev, beta or prod.
    """
    value = ALIASES.get(value, value)
    return value if value in LEVELS else default


def ships(level, image_level):
    """
    Does an image of image_level ship something of level?

    Args:
        level (str): The demo's level.
        image_level (str): The image's level.

    Returns:
        bool: True when level is at least image_level.
    """
    return LEVELS.index(level) >= LEVELS.index(image_level)


def for_branch(branch):
    """
    The level of an image built from a branch.

    Args:
        branch (str): Git branch.

    Returns:
        str: prod for main, beta for beta, dev for anything else.
    """
    return {"main": "prod", "beta": "beta"}.get(branch, "dev")


def image_level():
    """
    The level of this image: RQ_DEMO_LEVEL, else /etc/rasqberry-demo-level.

    Returns:
        str: dev, beta or prod (dev when neither is set).
    """
    value = os.environ.get("RQ_DEMO_LEVEL", "")
    if not value:
        try:
            with open(LEVEL_FILE, encoding="utf-8") as f:
                value = f.read().strip()
        except OSError:
            value = ""
    return level_of(value)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _mark(item, level, image):
    # What the Pi shows: "beta" only for a dev demo in a dev image
    if image == "dev" and level == "dev":
        item["maturity"] = "beta"
    else:
        item.pop("maturity", None)


def trim_manifests(manifest_dir, image):
    """
    Drop the manifests and variants below the image level, mark the rest.

    Args:
        manifest_dir (str): demo-manifests/.
        image (str): The image's level.

    Returns:
        tuple: ({demo id: set of kept variant ids, or None without variants},
        set of dropped demo ids).
    """
    kept = {}
    dropped = set()
    for path in sorted(glob.glob(os.path.join(manifest_dir, "rq_demo_*.json"))):
        if os.path.basename(path) == "rq_demo_schema.json":
            continue
        data = _load(path)
        demo_id = data.get("id") or os.path.basename(path)[len("rq_demo_"):-len(".json")]
        level = level_of(data.get("maturity"))
        variants = data.get("variants")
        if isinstance(variants, list) and variants:
            keep = []
            for variant in variants:
                vlevel = level_of(variant.get("maturity"), level)
                if ships(vlevel, image):
                    _mark(variant, vlevel, image)
                    keep.append(variant)
            # a demo with variants ships while one of them does
            if not keep:
                os.remove(path)
                dropped.add(demo_id)
                continue
            data["variants"] = keep
            kept[demo_id] = {v.get("id") for v in keep}
        elif ships(level, image):
            kept[demo_id] = None
        else:
            os.remove(path)
            dropped.add(demo_id)
            continue
        _mark(data, level, image)
        _save(path, data)
    return kept, dropped


def trim_catalogue(path, image):
    """
    Drop the catalogue entries below the image level, mark the rest.

    Args:
        path (str): known-demos.json.
        image (str): The image's level.
    """
    if not os.path.isfile(path):
        return
    data = _load(path)
    demos = []
    for entry in data.get("demos") or []:
        level = level_of(entry.get("maturity"))
        if ships(level, image):
            _mark(entry, level, image)
            demos.append(entry)
    data["demos"] = demos
    _save(path, data)


def _step_kept(step, kept):
    demo = step.get("demo")
    if not demo:
        return True             # a command or a web page
    if demo not in kept:
        return False
    variant = step.get("variant")
    return not variant or kept[demo] is None or variant in kept[demo]


def trim_learning_paths(path, kept):
    """
    Drop the steps of dropped demos, and the paths left without a step.

    Args:
        path (str): learning-paths.json.
        kept (dict): trim_manifests()[0].
    """
    if not os.path.isfile(path):
        return
    data = _load(path)
    paths = []
    for p in data.get("paths") or []:
        p["steps"] = [s for s in p.get("steps") or [] if _step_kept(s, kept)]
        if p["steps"]:
            paths.append(p)
    ids = {p.get("id") for p in paths}
    for p in paths:
        if isinstance(p.get("next"), list):
            p["next"] = [n for n in p["next"] if not n.get("path") or n["path"] in ids]
    data["paths"] = paths
    _save(path, data)


def bookmark_kept(path, kept):
    """
    Does a launcher start a demo (and variant) the image ships?

    Args:
        path (str): A .desktop file.
        kept (dict): trim_manifests()[0].

    Returns:
        bool: False only for a launcher of a dropped demo or variant.
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return True
    for line in text.splitlines():
        if line.startswith("Exec="):
            m = _EXEC.search(line)
            if m:
                return _step_kept({"demo": m.group(1), "variant": m.group(2)}, kept)
    return True


def trim_bookmarks(bookmark_dir, kept, dropped):
    """
    Drop the launchers of dropped demos and variants: the ones that start
    one, and the ones named after one (a web link like composer.desktop).

    Args:
        bookmark_dir (str): desktop-bookmarks/.
        kept (dict): trim_manifests()[0].
        dropped (set): trim_manifests()[1].
    """
    for path in glob.glob(os.path.join(bookmark_dir, "*.desktop")):
        if os.path.basename(path)[:-len(".desktop")] in dropped or not bookmark_kept(path, kept):
            os.remove(path)


def apply(config_dir, image):
    """
    Trim a RQB2-config tree (or /usr/config) to one image level.

    Args:
        config_dir (str): The tree.
        image (str): dev, beta or prod.

    Returns:
        dict: The kept demos (trim_manifests()[0]).
    """
    manifests = os.path.join(config_dir, "demo-manifests")
    kept, dropped = trim_manifests(manifests, image)
    trim_catalogue(os.path.join(config_dir, "known-demos.json"), image)
    trim_learning_paths(os.path.join(manifests, "learning-paths.json"), kept)
    trim_bookmarks(os.path.join(config_dir, "desktop-bookmarks"), kept, dropped)
    return kept


def main(argv):
    """
    Command line: apply, image or for-branch.

    Args:
        argv (list): Arguments without the program name.

    Returns:
        int: Exit code.
    """
    if argv[:1] == ["image"]:
        print(image_level())
        return 0
    if argv[:1] == ["for-branch"] and len(argv) == 2:
        print(for_branch(argv[1]))
        return 0
    if argv[:1] == ["apply"] and len(argv) in (2, 3):
        image = level_of(argv[2]) if len(argv) == 3 else image_level()
        kept = apply(argv[1], image)
        print("demo level %s: %d demos kept (%s)" % (image, len(kept), ", ".join(sorted(kept))))
        return 0
    print(__doc__.strip().split("Usage:")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
