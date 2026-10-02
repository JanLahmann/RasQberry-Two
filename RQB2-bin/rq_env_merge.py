#!/usr/bin/env python3
"""
Merge a newly shipped rasqberry_environment.env into the one on the device.

rasqberry_environment.env holds shipped defaults AND device state written at
runtime (LED layout from the first-login wizard, *_INSTALLED flags, first-login
bookkeeping, ...). Replacing it on an update wipes that state (issue #290).

The merged file takes its layout and comments from the NEW defaults, so new
settings and documentation arrive, but every key the device already has keeps
the device's value. Keys the device has that the new defaults no longer ship
are kept at the end, so nothing written at runtime is lost.

Usage:
    rq_env_merge.py <new-defaults.env> <current.env> <output.env>

Exit status 0 on success, 2 on a usage or read error. A summary goes to stdout.
"""

import re
import sys
from pathlib import Path

_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=")

# Keys that must not survive an update even though the device has them.
# INTERACTIVE, ASK_TO_REBOOT and CONFIG are raspi-config's own variables: the
# env file is loaded inside raspi-config, and these switched it to
# non-interactive mode (R-001). MARKER_QRT named a file the pinned Raspberry
# Tie checkout no longer has.
RETIRED_KEYS = ("INTERACTIVE", "ASK_TO_REBOOT", "CONFIG", "MARKER_QRT")

KEPT_HEADER = (
    "\n# -----------------------------------------------------------------------------\n"
    "# Device settings that the shipped defaults do not (or no longer) contain.\n"
    "# Kept by rq_update_from_branch.sh so runtime state survives an update.\n"
    "# -----------------------------------------------------------------------------\n"
)


def key_of(line):
    """
    Return the variable name assigned on this line, or None.

    Args:
        line (str): One line of an env file.

    Returns:
        str | None: The key for KEY=VALUE / export KEY=VALUE lines.
    """
    match = _KEY_RE.match(line)
    return match.group(1) if match else None


def assignments(lines):
    """
    Map key -> its last assignment line (the value the shell ends up with).

    Args:
        lines (list[str]): Lines of an env file, without newlines.

    Returns:
        dict: {key: line}, in first-seen order.
    """
    found = {}
    for line in lines:
        key = key_of(line)
        if key:
            found[key] = line
    return found


def merge(new_lines, current_lines):
    """
    Merge shipped defaults with the device's current file.

    Args:
        new_lines (list[str]): Lines of the newly shipped defaults.
        current_lines (list[str]): Lines of the file on the device.

    Returns:
        tuple: (merged_lines, added, kept, carried) where added are keys new
        in the defaults, kept are keys whose device value differs from the new
        default, and carried are device-only keys appended at the end.
        Device-only keys listed in RETIRED_KEYS are dropped.
    """
    current = assignments(current_lines)
    shipped = set()
    merged, added, kept = [], [], []

    for line in new_lines:
        key = key_of(line)
        if key is None:
            merged.append(line)
            continue
        if key in shipped:
            # A key assigned twice in the defaults: the device value is
            # already in place at the first occurrence.
            continue
        shipped.add(key)
        if key in current:
            if current[key].strip() != line.strip():
                kept.append(key)
            merged.append(current[key])
        else:
            added.append(key)
            merged.append(line)

    carried = [k for k in current if k not in shipped and k not in RETIRED_KEYS]
    if carried:
        merged.extend(KEPT_HEADER.rstrip("\n").split("\n"))
        merged.extend(current[k] for k in carried)
    return merged, added, kept, carried


def main(argv):
    """Entry point: write the merged file and print a summary."""
    if len(argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    new_path, current_path, out_path = (Path(a) for a in argv[1:])
    try:
        new_lines = new_path.read_text(encoding="utf-8").splitlines()
        current_lines = current_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    merged, added, kept, carried = merge(new_lines, current_lines)
    out_path.write_text("\n".join(merged) + "\n", encoding="utf-8")

    print(f"env merge: {len(added)} new setting(s), {len(kept)} device value(s) kept, "
          f"{len(carried)} device-only setting(s) carried over")
    for label, keys in (("new", added), ("kept", kept), ("carried", carried)):
        if keys:
            print(f"  {label}: {' '.join(keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
