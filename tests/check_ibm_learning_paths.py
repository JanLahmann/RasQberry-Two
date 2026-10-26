#!/usr/bin/env python3
"""
Compare IBM Quantum's learning paths with ours (weekly, ibm-learning-paths.yml).

learning-paths.json lists IBM Quantum's "Multi-resource learning paths" under
ibm_learning (Continue with IBM Quantum Learning). IBM publishes no data file
for them: its Learning page links each path as "?modal=<slug>", and only these
slugs are in the page's HTML. What a path contains (its materials and times)
is loaded by the browser, so this check cannot see it without one; it compares
the slugs only.

It reports and never fails: a difference, or a page it cannot read, is a
warning in the job log and the job summary. Exit code 0 either way.

Usage: check_ibm_learning_paths.py [LEARNING_PATHS_JSON]
"""

import json
import os
import re
import sys
import urllib.request

PAGE = "https://quantum.cloud.ibm.com/learning/en"
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(_HERE, "..", "RQB2-config", "demo-manifests", "learning-paths.json")


def slugs_on_page(html):
    """
    The learning path slugs a Learning page links to.

    Args:
        html (str): the page's HTML

    Returns:
        list: the slugs, in page order, each once
    """
    out = []
    for slug in re.findall(r"[?&]modal=([a-z0-9][a-z0-9-]*)", html):
        if slug not in out:
            out.append(slug)
    return out


def our_slugs(path):
    """
    The slugs in learning-paths.json (ibm_learning.paths).

    Args:
        path (str): the file

    Returns:
        list: the slugs, in file order
    """
    with open(path, encoding="utf-8") as fh:
        return [p["slug"] for p in json.load(fh).get("ibm_learning", {}).get("paths", [])]


def compare(ours, theirs):
    """
    Say how two slug lists differ.

    Args:
        ours (list): our slugs
        theirs (list): the page's slugs

    Returns:
        list: lines describing the difference; empty when they match
    """
    lines = []
    new = [s for s in theirs if s not in ours]
    gone = [s for s in ours if s not in theirs]
    if new:
        lines.append("New on IBM's page: " + ", ".join(new))
    if gone:
        lines.append("No longer on IBM's page: " + ", ".join(gone))
    return lines


def report(lines):
    """Print lines as GitHub warnings and add them to the job summary."""
    for line in lines:
        print(f"::warning title=IBM learning paths::{line}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## IBM Quantum learning paths\n\n")
            fh.write("".join(f"- {line}\n" for line in lines))


def main(argv):
    """Fetch the page, compare, report. Always returns 0."""
    path = argv[1] if len(argv) > 1 else DEFAULT_FILE
    ours = our_slugs(path)
    try:
        req = urllib.request.Request(PAGE, headers={"User-Agent": "Mozilla/5.0 (RasQberry link check)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # network, HTTP error: report, do not fail
        report([f"Could not read {PAGE}: {exc}"])
        return 0
    theirs = slugs_on_page(html)
    if not theirs:
        report([f"{PAGE} links no learning paths (?modal=...): the page changed; check it by hand."])
        return 0
    lines = compare(ours, theirs)
    if lines:
        lines.append("Update ibm_learning in RQB2-config/demo-manifests/learning-paths.json "
                     "(the Pi, the website and IBM: Introduction to quantum use it).")
        report(lines)
    else:
        print(f"OK: the {len(ours)} learning paths match {PAGE}: {', '.join(ours)}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(f"IBM Quantum learning paths: all {len(ours)} slugs match.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
