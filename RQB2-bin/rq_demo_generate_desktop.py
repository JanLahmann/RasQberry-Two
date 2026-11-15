#!/usr/bin/env python3
"""
Write the desktop launchers of the shipped demos from their manifests.

The manifest is the one place a demo is declared (#B5): its "desktop" block,
and a variant's own "desktop" block for a variant that has a launcher of its
own, give the launcher's file name, label, tooltip and window title. This
writes RQB2-config/desktop-bookmarks/<file>.desktop for each of them; the
launchers that belong to no demo (setup, menu, touch mode, ...) stay hand
written there. Catalogue demos get theirs on the Pi (rq_demo_desktop_entry.sh).

Usage:
    rq_demo_generate_desktop.py           # write the launchers
    rq_demo_generate_desktop.py --check   # exit 1 if a committed one differs
"""

import argparse
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(os.path.dirname(_HERE), "RQB2-config")
MANIFESTS = os.path.join(CONFIG, "demo-manifests")
BOOKMARKS = os.path.join(CONFIG, "desktop-bookmarks")
BIN = "/usr/bin"
HEADER = "# Generated from demo-manifests/{manifest} by RQB2-bin/rq_demo_generate_desktop.py - edit the manifest\n"
# A launcher of a demo at level dev says so (rq_demo_maturity in rq_common.sh);
# rq_demo_level.py drops the mark again on beta and prod images
MARK = "(beta)"


def shipped_manifests():
    """The shipped demo manifests, by file name."""
    for path in sorted(glob.glob(os.path.join(MANIFESTS, "rq_demo_*.json"))):
        if not path.endswith("_schema.json"):
            with open(path, encoding="utf-8") as f:
                yield os.path.basename(path), json.load(f)


def launchers(manifest):
    """(desktop block, variant or None) for each launcher a manifest declares."""
    desktop = manifest.get("desktop", {})
    if desktop.get("show", True) and "comment" in desktop:
        yield desktop, None
    for variant in manifest.get("variants", []):
        if "desktop" in variant:
            yield variant["desktop"], variant


def exec_line(manifest, desktop, variant):
    """Exec and TryExec: a browser demo opens Chromium, everything else goes
    through rq_demo_run.sh (or the variant chooser) in a window that stays
    open on an error (rq_hold_on_error.sh)."""
    entry = manifest.get("entrypoint", {})
    if entry.get("type") == "browser" and not desktop.get("terminal", True):
        return f"chromium --password-store=basic {entry['browser_url']}", "chromium"
    title = f' -t "{desktop["title"]}"' if "title" in desktop else ""
    if desktop.get("chooser"):
        cmd = f"{BIN}/rq_demo_choose.sh {manifest['id']}"
    else:
        cmd = f"{BIN}/rq_demo_run.sh {manifest['id']}" + (f" {variant['id']}" if variant else "")
    return f"{BIN}/rq_hold_on_error.sh{title} {cmd}", f"{BIN}/rq_demo_run.sh"


def render(name, manifest, desktop, variant):
    """The .desktop text of one launcher."""
    source = variant or manifest
    label = desktop.get("name", source["name"])
    comment = desktop["comment"]
    maturity = (variant or {}).get("maturity") or manifest.get("maturity")
    if maturity == "dev":
        label, comment = f"{label} {MARK}", f"{MARK} {comment}"
    icon = desktop.get("icon") or manifest.get("icon", {}).get("path", "applications-science")
    keywords = desktop.get("keywords", manifest.get("keywords", []))
    exec_cmd, try_exec = exec_line(manifest, desktop, variant)
    lines = [
        HEADER.format(manifest=name).rstrip("\n"),
        "[Desktop Entry]",
        "Version=1.1",
        f"Name={label}",
        f"Comment={comment}",
        f"Icon={icon}",
        "Type=Application",
        "Categories=RasQberry;",
        f"Exec={exec_cmd}",
        f"Terminal={'true' if desktop.get('terminal', True) else 'false'}",
        "StartupNotify=true",
        "Keywords=" + "".join(k + ";" for k in keywords),
        "X-GNOME-TextColor=#000000",
        f"TryExec={try_exec}",
        "NoDisplay=false",
    ]
    # In the applications menu only, not on the desktop (stage 06)
    if not desktop.get("on_desktop", True):
        lines.append("X-RasQberry-OnDesktop=false")
    return "\n".join(lines) + "\n"


def generated():
    """{launcher file name: text} for every shipped demo launcher."""
    out = {}
    for name, manifest in shipped_manifests():
        for desktop, variant in launchers(manifest):
            fname = desktop.get("file", (variant or manifest)["id"]) + ".desktop"
            if fname in out:
                sys.exit(f"{fname} is declared twice (second time in {name})")
            out[fname] = render(name, manifest, desktop, variant)
    return out


def main():
    """Write the launchers, or with --check report the ones that differ."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="compare only, exit 1 on a difference")
    args = parser.parse_args()
    stale = []
    launchers_now = generated()
    for fname, text in launchers_now.items():
        path = os.path.join(BOOKMARKS, fname)
        try:
            with open(path, encoding="utf-8") as f:
                current = f.read()
        except FileNotFoundError:
            current = None
        if current == text:
            continue
        stale.append(fname)
        if not args.check:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(path, 0o755)
    # A generated launcher whose manifest entry is gone
    for path in glob.glob(os.path.join(BOOKMARKS, "*.desktop")):
        with open(path, encoding="utf-8") as f:
            ours = f.readline().startswith("# Generated from demo-manifests/")
        if ours and os.path.basename(path) not in launchers_now:
            stale.append(os.path.basename(path))
            if not args.check:
                os.remove(path)
    if args.check and stale:
        print("Launchers differ from the manifests (run RQB2-bin/rq_demo_generate_desktop.py): "
              + ", ".join(sorted(stale)), file=sys.stderr)
        return 1
    for fname in sorted(stale):
        print(f"{'differs' if args.check else 'written'}: {fname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
