#!/usr/bin/env python3
"""
RasQberry: check or move the pins of the starter notebooks (development tool).

Some starter notebooks in RQB2-config/my-quantum-programs/ are copies of
notebooks from other projects, pinned in RQB2-config/starter-notebooks.json
like the demos: repository, commit, path and SHA-256. The Hello World notebook
is doQumentation's, so the first circuit on the Pi is the one on
doqumentation.org. rq_learner_setup.sh copies them into ~/My-Quantum-Programs;
nothing on the Pi downloads them.

"edits" change single cells of the upstream file, the way the demo patches
change a pinned demo: a cell that contains a text ("cell_contains"), or the
cell with an id ("cell_id"), gets a replacement inside it ("replace"/"with")
or a new source ("source"). upstream_sha256 is the file as published, sha256
the copy we ship. An edit that matches no cell fails, so an upstream change
cannot slip past it.

Usage:
    rq_starter_sync.py             check the copies against their pins (offline)
    rq_starter_sync.py --upstream  also download each pinned file and compare,
                                   and say whether upstream changed it since
    rq_starter_sync.py --update [--ref SHA]
                                   move every pin to SHA (default: the newest
                                   commit of the default branch) and rewrite
                                   the copies; review the diff, then commit
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PINS = os.path.join(_ROOT, "RQB2-config", "starter-notebooks.json")
STARTERS = os.path.join(_ROOT, "RQB2-config", "my-quantum-programs")


def sha256(data):
    """
    Return the SHA-256 of bytes as hex.

    Args:
        data (bytes): Content.

    Returns:
        str: 64 hex digits.
    """
    return hashlib.sha256(data).hexdigest()


def owner_repo(repo_url):
    """
    Return "owner/repo" of a GitHub URL.

    Args:
        repo_url (str): https://github.com/<owner>/<repo>[.git]

    Returns:
        str: owner/repo
    """
    path = repo_url.rstrip("/").split("github.com/", 1)[1]
    return path[:-4] if path.endswith(".git") else path


def fetch(url):
    """
    Download a URL.

    Args:
        url (str): https URL.

    Returns:
        bytes: The body.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "rasqberry-starter-sync"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def raw_file(entry, ref):
    """
    Download the pinned file at a commit.

    Args:
        entry (dict): A notebooks[] entry.
        ref (str): Commit SHA.

    Returns:
        bytes: The file.
    """
    return fetch("https://raw.githubusercontent.com/%s/%s/%s"
                 % (owner_repo(entry["repo_url"]), ref, entry["path"]))


def newest_commit(entry, path=None):
    """
    Return the newest commit of the default branch (that touched PATH).

    Args:
        entry (dict): A notebooks[] entry.
        path (str): Limit to commits that changed this file.

    Returns:
        str: Commit SHA.
    """
    url = "https://api.github.com/repos/%s/commits?per_page=1" % owner_repo(entry["repo_url"])
    if path:
        url += "&path=" + path
    return json.loads(fetch(url))[0]["sha"]


def apply_edits(data, edits):
    """
    Apply the cell edits to a notebook.

    Args:
        data (bytes): The upstream notebook.
        edits (list): {"cell_contains" or "cell_id", "replace", "with"} or
            {"cell_contains" or "cell_id", "source"} entries.

    Returns:
        bytes: The edited notebook, written as Jupyter writes it.

    Raises:
        ValueError: An edit matches no cell.
    """
    if not edits:
        return data
    nb = json.loads(data)
    for edit in edits:
        if "cell_id" in edit:
            cells = [c for c in nb["cells"] if c.get("id") == edit["cell_id"]]
            if not cells:
                raise ValueError("no cell has the id %r" % edit["cell_id"])
        else:
            cells = [c for c in nb["cells"] if edit["cell_contains"] in "".join(c["source"])]
            if not cells:
                raise ValueError("no cell contains %r" % edit["cell_contains"])
        for cell in cells:
            if "source" in edit:
                text = edit["source"]
            else:
                text = "".join(cell["source"])
                if edit["replace"] not in text:
                    raise ValueError("%r not found" % edit["replace"])
                text = text.replace(edit["replace"], edit["with"])
            cell["source"] = text.splitlines(True)
    return (json.dumps(nb, indent=1) + "\n").encode("utf-8")


def main():
    """
    Check or update the pins.

    Returns:
        int: 0 when everything matches, 1 otherwise.
    """
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--upstream", action="store_true", help="compare with the pinned upstream files")
    ap.add_argument("--update", action="store_true", help="move the pins and rewrite the copies")
    ap.add_argument("--ref", help="commit to pin to with --update (default: newest)")
    args = ap.parse_args()

    with open(PINS, encoding="utf-8") as fh:
        pins = json.load(fh)
    ok = True
    for entry in pins["notebooks"]:
        local = os.path.join(STARTERS, entry["file"])
        if args.update:
            ref = args.ref or newest_commit(entry)
            upstream = raw_file(entry, ref)
            data = apply_edits(upstream, entry.get("edits"))
            with open(local, "wb") as fh:
                fh.write(data)
            entry["ref"], entry["sha256"] = ref, sha256(data)
            entry["upstream_sha256"] = sha256(upstream)
            logger.info("%s: pinned to %s", entry["file"], ref[:12])
            continue
        with open(local, "rb") as fh:
            have = sha256(fh.read())
        if have != entry["sha256"]:
            ok = False
            logger.error("%s: differs from its pin (sha256 %s, pinned %s)", entry["file"], have, entry["sha256"])
        if args.upstream:
            upstream = raw_file(entry, entry["ref"])
            if sha256(upstream) != entry.get("upstream_sha256", entry["sha256"]) \
                    or sha256(apply_edits(upstream, entry.get("edits"))) != entry["sha256"]:
                ok = False
                logger.error("%s: the upstream file at %s (with our edits) has another sha256",
                             entry["file"], entry["ref"][:12])
            last = newest_commit(entry, entry["path"])
            if last != entry["ref"] and sha256(raw_file(entry, last)) != entry.get("upstream_sha256"):
                logger.info("%s: upstream changed it since (%s); --update moves the pin", entry["file"], last[:12])
        if ok:
            logger.info("%s: matches %s@%s", entry["file"], owner_repo(entry["repo_url"]), entry["ref"][:12])
    if args.update:
        with open(PINS, "w", encoding="utf-8") as fh:
            json.dump(pins, fh, indent=2)
            fh.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
