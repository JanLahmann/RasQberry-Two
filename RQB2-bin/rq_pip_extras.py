#!/usr/bin/env python3
"""
Split an external demo's requirements.txt into "extras" the venv lacks.

Run with the TARGET venv's interpreter. It writes two files into <out-dir>:

  extras.txt       the requirement lines whose distribution is NOT installed
  constraints.txt  ``name==version`` for every distribution that IS installed

Installing with ``pip install -c constraints.txt -r extras.txt`` then adds
only what the demo is missing and can never move a package the image already
ships, no matter what version the demo pinned. A requirement that asks for a
different version of an installed package is reported and kept at the
installed version (issue #285).

Usage:
    rq_pip_extras.py <requirements.txt> <out-dir>

Exit status is 0 when the files were written (even if there is nothing extra
to install), 2 on a usage or read error.
"""

import re
import sys
from importlib import metadata
from pathlib import Path

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name):
    """Normalise a distribution name the way pip does (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_distributions():
    """
    Map normalised name -> version for every distribution in this interpreter.

    Returns:
        dict: {normalised_name: version}
    """
    found = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        if name and dist.version:
            found.setdefault(normalize(name), dist.version)
    return found


def requirement_name(line):
    """
    Extract the distribution name from one requirements.txt line.

    Args:
        line (str): A raw line from requirements.txt.

    Returns:
        str | None: The normalised name, or None for blank/comment/option lines.
    """
    stripped = line.split("#", 1)[0].strip()
    if not stripped or stripped.startswith("-"):
        return None
    match = _NAME_RE.match(stripped)
    return normalize(match.group(1)) if match else None


def split_requirements(lines, installed):
    """
    Partition requirement lines into extras and already-installed ones.

    Args:
        lines (list[str]): Lines of requirements.txt.
        installed (dict): Output of installed_distributions().

    Returns:
        tuple: (extras, kept) where extras are the lines to install and kept
        is a list of (line, installed_version) for lines that were skipped.
    """
    extras, kept = [], []
    for line in lines:
        name = requirement_name(line)
        if name is None:
            continue
        if name in installed:
            kept.append((line.strip(), installed[name]))
        else:
            extras.append(line.rstrip("\n"))
    return extras, kept


def main(argv):
    """Entry point: write extras.txt and constraints.txt, print a summary."""
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    req_path, out_dir = Path(argv[1]), Path(argv[2])
    try:
        lines = req_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR: cannot read {req_path}: {exc}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    installed = installed_distributions()
    extras, kept = split_requirements(lines, installed)

    (out_dir / "extras.txt").write_text(
        "\n".join(extras) + ("\n" if extras else ""), encoding="utf-8"
    )
    (out_dir / "constraints.txt").write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(installed.items())),
        encoding="utf-8",
    )

    for line, version in kept:
        print(f"keep installed: {line}  (venv has {version})")
    for line in extras:
        print(f"install extra:  {line}")
    print(f"summary: {len(extras)} to install, {len(kept)} already present")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
