#!/usr/bin/env python3
"""
Reference documentation of RasQberry Two, generated from the code.

What a person sees on the Pi - the RasQberry menu, the desktop, the settings,
the commands and the demos - read from the files that make it, so the pages
cannot drift from the code. They ground the RasQberry helpers (the tester bot
first) and serve as a reference for advanced users.

Sources:
  RQB2-config/RQB2_menu.sh                 the menu tree (show_menu / ab_menu calls)
  RQB2-config/demo-manifests/*.json        demos, their groups and variants
  RQB2-config/known-demos.json             the catalogue
  RQB2-config/desktop-bookmarks/*.desktop  desktop launchers
  RQB2-bin/rq_desktop_session.py           which folder a launcher goes into
  RQB2-system/etc/xdg/autostart/*.desktop  what starts at login (taskbar items)
  RQB2-config/rasqberry_environment.env    the settings
  RQB2-bin/rq_device_settings.sh           which settings survive A/B updates
  RQB2-bin/rq_*                            the commands (their header comments)

Writes, next to this script: index.md, menu.md, desktop.md, settings.md,
commands.md, demos.md.

Usage: python3 docs/reference/reference_docs.py [--check]
  --check   exit 1 when the written files are out of date (tests use it)
"""

import argparse
import configparser
import glob
import importlib.util
import json
import os
import re
import shlex
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CONFIG = os.path.join(ROOT, "RQB2-config")
BIN = os.path.join(ROOT, "RQB2-bin")
MENU = os.path.join(CONFIG, "RQB2_menu.sh")
MANIFESTS = os.path.join(CONFIG, "demo-manifests")
GROUPS_FILE = os.path.join(MANIFESTS, "demo-groups.json")
CATALOGUE = os.path.join(CONFIG, "known-demos.json")
BOOKMARKS = os.path.join(CONFIG, "desktop-bookmarks")
AUTOSTART = os.path.join(ROOT, "RQB2-system", "etc", "xdg", "autostart")
ENV_FILE = os.path.join(CONFIG, "rasqberry_environment.env")
DEVICE_SETTINGS = os.path.join(BIN, "rq_device_settings.sh")

SCRIPT = "docs/reference/reference_docs.py"
HEADER = f"<!-- Generated from the code by {SCRIPT}; do not edit. -->\n\n"

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def read(path):
    """Return a file's text (UTF-8)."""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_json(path):
    """Return a JSON file's data."""
    return json.loads(read(path))


def manifests():
    """
    The shipped demo manifests, by id.

    Returns:
        dict: id -> (manifest, file name)
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(MANIFESTS, "rq_demo_*.json"))):
        if path.endswith("rq_demo_schema.json"):
            continue
        data = load_json(path)
        out[data["id"]] = (data, os.path.basename(path))
    return out


def groups_data():
    """demo-groups.json."""
    return load_json(GROUPS_FILE)


def group_titles():
    """Group id -> title, in menu order."""
    return {g["id"]: g["title"] for g in groups_data()["groups"]}


def catalogue_group():
    """The group catalogue demos go to by default (Contributed demos)."""
    return next((g["id"] for g in groups_data()["groups"] if g.get("catalogue") is True), None)


def demo_needs_tags(manifest, group):
    """
    The short needs a demo's menu entry shows ("internet, 32 GB"), as
    demo_needs in rq_demo_generate_menu.sh.

    Args:
        manifest (dict): The demo manifest.
        group (str): Its group id.

    Returns:
        str: The tags, comma-separated (empty when none).
    """
    hw = manifest.get("needs_hw") or {}
    tags = []
    if hw.get("leds") is True and group != "led-panel":
        tags.append("LED panel")
    if hw.get("network") is True:
        tags.append("internet")
    if manifest.get("needs_ibm_token") == "required":
        tags.append("IBM account")
    entry = manifest.get("entrypoint") or {}
    if entry.get("type") == "docker" or (manifest.get("install") or {}).get("docker_image_of"):
        tags.append("32 GB")
    return ", ".join(tags)


def menu_label(manifest, group):
    """A demo's entry in its group menu: name, (beta), [needs]."""
    label = manifest["name"]
    if manifest.get("maturity"):
        label += " (beta)"
    tags = demo_needs_tags(manifest, group)
    return label + (f" [{tags}]" if tags else "")


def demo_group(demo_id, manifest):
    """
    A shipped demo's group, as rq_demo_group: its manifest's group, else a
    guess (LED panel demos: led-panel; game or visualization: play; else learn).
    """
    ids = list(group_titles())
    if manifest.get("group") in ids:
        return manifest["group"]
    if (manifest.get("needs_hw") or {}).get("leds") is True:
        guess = "led-panel"
    elif manifest.get("category") in ("game", "visualization"):
        guess = "play"
    else:
        guess = "learn"
    return guess if guess in ids else ids[0]


def in_group_menu(manifest):
    """Does a demo get its own entry in its group menu (menu.show, no parent)?"""
    menu = manifest.get("menu") or {}
    return menu.get("show") is not False and not menu.get("parent")


def group_demos(group_id):
    """
    The shipped demos of a group menu, in menu order (menu.order, then file).

    Returns:
        list: (id, manifest) pairs
    """
    rows = []
    for demo_id, (data, fname) in manifests().items():
        if demo_group(demo_id, data) == group_id and in_group_menu(data):
            rows.append(((data.get("menu") or {}).get("order", 50), fname, demo_id, data))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(r[2], r[3]) for r in rows]


def catalogue_demos():
    """known-demos.json's entries."""
    return [d for d in load_json(CATALOGUE).get("demos") or [] if isinstance(d, dict)]


# ---------------------------------------------------------------------------
# The menu (RQB2_menu.sh)
# ---------------------------------------------------------------------------

MENU_CALLS = ("show_menu", "ab_menu")

# What a few command substitutions in labels stand for
KNOWN_VALUES = {
    "hotspot_state": "on/off",
    "audio_delay_ms": "ms",
    "browser_autostart_state": "on/off",
    "demo_loop_login_state": "on/off",
    "_rq_hs_admin_label": "auto: on/off, yes or no",
}


def shell_functions(text):
    """
    The functions of a shell file.

    Returns:
        dict: name -> body (the lines between "name() {" and "}")
    """
    funcs, name, body = {}, None, []
    for line in text.splitlines():
        if name is None:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{\s*$", line)
            if m:
                name, body = m.group(1), []
            continue
        if line.startswith("}"):
            funcs[name] = body
            name = None
            continue
        body.append(line)
    return funcs


def statement_at(lines, i):
    """The statement starting at line i, with its continuation lines joined."""
    parts = []
    while i < len(lines):
        line = lines[i]
        if line.rstrip().endswith("\\"):
            parts.append(line.rstrip()[:-1])
            i += 1
            continue
        parts.append(line)
        break
    return " ".join(p.strip() for p in parts)


def call_text(stmt, call):
    """The arguments of a $(call ...) in a statement, up to its closing paren."""
    start = stmt.index(call) + len(call)
    depth, quote, i = 1, None, start
    while i < len(stmt):
        ch = stmt[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return stmt[start:i]
        i += 1
    return stmt[start:]


def tokens(text):
    """Shell words, without expanding anything ($@ stays a word)."""
    text = re.sub(r"\$\{[^}]*--default-item[^}]*\}", " ", text)
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def literal_assignments(body, only=False):
    """
    The variables a function sets to a plain text (the first such text).

    Args:
        body (list): The lines before the menu call.
        only (bool): Only variables set nowhere else (a prompt that changes
            with the Pi's state is left out rather than shown in one form).

    Returns:
        dict: name -> text
    """
    out, count = {}, {}
    for line in body:
        for name in re.findall(r"(?:^|[\s;(])([A-Za-z_][A-Za-z0-9_]*)=", line):
            count[name] = count.get(name, 0) + 1
        m = re.match(r'^\s*(?:local\s+)?([A-Za-z_][A-Za-z0-9_]*)="([^"$`]*)"\s*$', line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    if only:
        out = {k: v for k, v in out.items() if count.get(k) == 1}
    return out


def short_var(name):
    """_ra_ssh -> ssh; HOTSPOT_AT_BOOT stays."""
    name = name.lstrip("_")
    parts = name.split("_", 1)
    if len(parts) == 2 and len(parts[0]) <= 3 and parts[0].islower():
        return parts[1]
    return name


def resolve(text, assigned):
    """
    A label or prompt as a reader sees it: shell expansions become their
    plain value (a variable set to one text) or a <placeholder>.
    """
    def cmd(m):
        word = m.group(1).split()[0].strip('"').split("/")[-1]
        return "<" + KNOWN_VALUES.get(word, word) + ">"

    def brace(m):
        name, op, rest = m.group(1), m.group(2) or "", m.group(3) or ""
        if op == ":+":
            return ""
        if op == ":-" and "$" not in rest and rest:
            return f"<{short_var(name)}>"
        return assigned.get(name, f"<{short_var(name)}>")

    def plain(m):
        return assigned.get(m.group(1), f"<{short_var(m.group(1))}>")

    text = re.sub(r"\$\(([^()]*(?:\([^()]*\))?[^()]*)\)", cmd, text)
    text = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:[-+])?([^}]*)\}", brace, text)
    text = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", plain, text)
    text = text.replace("\\n", " ").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


def pairs(words):
    """
    Menu items from shell words: ("tag", "label") pairs; "$@" marks where
    earlier items go (returned as the pair ("$@", None)).
    """
    out, i = [], 0
    while i < len(words):
        if words[i] == "$@":
            out.append(("$@", None))
            i += 1
            continue
        if i + 1 < len(words):
            out.append((words[i], words[i + 1]))
        i += 2
    return out


class Menu:
    """One menu: its title, prompt, items, and the menus its items open."""

    def __init__(self, func, title, prompt, items, children, notes):
        self.func = func
        self.title = title
        self.prompt = prompt
        self.items = items          # [(tag, label, conditional)]
        self.children = children    # tag -> function name (a menu)
        self.notes = notes          # tag -> extra text


def parse_menu(name, body, menu_funcs):
    """
    Read one menu function: the show_menu/ab_menu call, the "set --" lines
    that build its items, and the case arms that open other menus.

    Returns:
        Menu: or None when the function shows no menu
    """
    call_line = None
    for i, line in enumerate(body):
        if any(f"{c} " in line for c in MENU_CALLS) and "$(" in line and "FUN=" in line or \
                any(re.search(rf"=\$\((?:\w+=\S+\s+)?{c}\b", line) for c in MENU_CALLS):
            call_line = i
            break
    if call_line is None:
        return None
    assigned = literal_assignments(body[:call_line])
    stmt = statement_at(body, call_line)
    call = next(c for c in MENU_CALLS if c in stmt)
    words = [w for w in tokens(call_text(stmt, call)) if w not in ("--tags", "--notags")]
    # a plain --default-item TAG (where the cursor starts) is not the title
    while len(words) > 1 and words[0] == "--default-item":
        words = words[2:]
    if len(words) < 2:
        return None
    title, prompt = resolve(words[0], assigned), words[1]
    indent = len(body[call_line]) - len(body[call_line].lstrip())

    # Items built before the call with "set --"
    built = []
    for i, line in enumerate(body[:call_line]):
        s = line.strip()
        m = re.search(r"(?:^|&&|\|\||;|\bthen\b|\belse\b)\s*set --(.*)$", s)
        if not m or s.startswith("#") or s.startswith("eval"):
            continue
        rest = statement_at(body, i)
        rest = rest[rest.index("set --") + len("set --"):]
        lead = len(line) - len(line.lstrip())
        cond = lead > indent or not s.startswith("set --")
        new = pairs(tokens(rest))
        if new and new[0] == ("$@", None):
            built += [(t, l, cond) for t, l in new[1:] if t != "$@"]
        else:
            built = [(t, l, cond) for t, l in new if t != "$@"]
    items = []
    for tag, label in pairs(words[2:]):
        if tag == "$@":
            items += built
        else:
            items.append((tag, label, False))
    items = [(t, resolve(l, assigned), c) for t, l, c in items if l is not None]

    # Which items open another menu: the case arms after the call
    children = {}
    for line in body[call_line + 1:]:
        m = re.match(r"^\s*([A-Za-z0-9_|\"' -]+)\)\s*(.*)$", line)
        if not m:
            continue
        for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", m.group(2)):
            if word in menu_funcs and word != name:
                for tag in m.group(1).replace('"', "").split("|"):
                    children.setdefault(tag.strip(), word)
                break
    if re.fullmatch(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", prompt):
        # the whole prompt is a variable: only when it is always the same text
        prompt = literal_assignments(body[:call_line], only=True).get(prompt.strip("${}"), "")
    return Menu(name, title, resolve(prompt, assigned), items, children, {})


def menu_tree():
    """
    Every menu reachable from the RasQberry main menu.

    Returns:
        (dict, dict): function name -> Menu, and the menu functions' bodies
    """
    funcs = shell_functions(read(MENU))
    menu_funcs = {n for n, b in funcs.items()
                  if any(re.search(rf"\b{c}\b", " ".join(b)) for c in MENU_CALLS) and n not in MENU_CALLS}
    menus = {}
    for n in menu_funcs:
        m = parse_menu(n, funcs[n], menu_funcs)
        if m:
            menus[n] = m
    return menus, funcs


def group_fixed_entries(funcs):
    """
    The fixed entries do_demo_group_menu adds to a group's demos.

    Returns:
        dict: group id -> {"before": [(tag, label)], "after": [...],
              "after_first": [...]}
    """
    body = funcs.get("do_demo_group_menu", [])
    text = "\n".join(body)
    m = re.search(r'case "\$_dg_id" in\n(.*?)\n\s*esac', text, re.S)
    out = {}
    if not m:
        return out
    arms = re.split(r"\n\s*(?=[a-z][a-z-]*\)\s)", "\n" + m.group(1))
    for arm in arms:
        am = re.match(r"\s*([a-z][a-z-]*)\)\s*(.*)", arm, re.S)
        if not am:
            continue
        gid, code = am.group(1), am.group(2)
        code = re.sub(r"\\\n\s*", " ", code)
        entry = {"before": [], "after": [], "after_first": []}
        for stmt in re.findall(r"set --([^\n;]*)", code):
            words = tokens(stmt)
            plist = pairs([w for w in words if not w.startswith("$_dg")])
            if any(w.startswith("$_dg") for w in words):
                where = "after_first"
            elif plist and plist[0] == ("$@", None):
                where = "after"
            else:
                where = "before"
            for tag, label in plist:
                if tag != "$@" and tag.isupper():
                    if (tag, label) not in sum(entry.values(), []):
                        entry[where].append((tag, label))
            if where == "after_first":
                break
        out[gid] = entry
    return out


def render_menu(menu, menus, depth, lines, seen, special, shown=None):
    """
    Write one menu and its submenus as a nested list. A menu reached a second
    time is named, not repeated (shown: the menus already written).
    """
    pad = "  " * depth
    shown = shown if shown is not None else set()
    if menu.items and all(re.fullmatch(r"<[^>]+>", lab) for tg, lab, _c in menu.items if tg.strip()):
        lines.append(f"{pad}- *(its entries are made when it opens)*")
        return
    for tag, label, cond in menu.items:
        if not tag.strip():
            heading = label.strip("- ").strip()
            if heading:
                lines.append(f"{pad}- *{heading}*")
            continue
        when = " *(only when it applies)*" if cond else ""
        if menu.func in special and tag in special[menu.func]:
            lines.append(f"{pad}- **{label}**{when}")
            special[menu.func][tag](depth + 1, lines)
            continue
        child = menu.children.get(tag)
        if child and child in menus and child not in seen:
            sub = menus[child]
            if child in shown:
                lines.append(f"{pad}- **{label}**{when} → menu \"{sub.title}\" (as above)")
                continue
            shown.add(child)
            lines.append(f"{pad}- **{label}**{when} → menu \"{sub.title}\""
                         + (f": {sub.prompt}" if sub.prompt else ""))
            render_menu(sub, menus, depth + 1, lines, seen | {child}, special, shown)
        else:
            lines.append(f"{pad}- {label}{when}")


def menu_md():
    """menu.md: the RasQberry menu tree."""
    menus, funcs = menu_tree()
    titles = group_titles()
    fixed = group_fixed_entries(funcs)
    mans = manifests()
    group_menu = parse_menu("do_demo_group_menu", funcs["do_demo_group_menu"], set(menus))
    dispatch = group_menu.children if group_menu else {}
    variant_menu = menus.get("do_demo_variant_menu")
    shown = set()

    def demo_entries(gid, depth, lines):
        pad = "  " * depth
        entries = []
        demos = group_demos(gid)
        f = fixed.get(gid, {"before": [], "after": [], "after_first": []})
        entries += [("fixed", t, l) for t, l in f["before"]]
        for k, (demo_id, data) in enumerate(demos):
            entries.append(("demo", demo_id, menu_label(data, gid)))
            if k == 0:
                entries += [("fixed", t, l) for t, l in f["after_first"]]
        if not demos:
            entries += [("fixed", t, l) for t, l in f["after_first"]]
        cats = [d for d in catalogue_demos()
                if (d.get("group") if d.get("group") in titles else catalogue_group()) == gid]
        for d in cats:
            label = d.get("name", d["id"]) + (" (beta)" if d.get("maturity") else "")
            entries.append(("catalogue", d["id"], label))
        entries += [("fixed", t, l) for t, l in f["after"]]
        for kind, tag, label in entries:
            if kind == "catalogue":
                lines.append(f"{pad}- {label} *(catalogue demo: shown once added)*")
                continue
            child = dispatch.get(tag)
            sub = menus.get(child) if child else None
            if sub:
                if child in shown:
                    lines.append(f"{pad}- **{label}** → menu \"{sub.title}\" (as above)")
                    continue
                shown.add(child)
                lines.append(f"{pad}- **{label}** → menu \"{sub.title}\""
                             + (f": {sub.prompt}" if sub.prompt else ""))
                render_menu(sub, menus, depth + 1, lines, {child}, {}, shown)
                continue
            data = mans.get(tag, (None,))[0] if kind == "demo" else None
            variants = (data or {}).get("variants") or []
            if data and (data.get("menu") or {}).get("variant_menu") and variants:
                title = f"RasQberry: {data['name']}"
                lines.append(f"{pad}- **{label}** → menu \"{title}\""
                             + (f": {variant_menu.prompt}" if variant_menu and variant_menu.prompt else ""))
                for v in variants:
                    vlabel = v.get("name", v.get("id")) + (" (beta)" if v.get("maturity") else "")
                    lines.append(f"{pad}  - {vlabel}")
            else:
                lines.append(f"{pad}- {label}")

    def groups_entries(depth, lines):
        pad = "  " * depth
        for g in groups_data()["groups"]:
            line = g.get("menu", "")
            lines.append(f"{pad}- **{g['title']}**" + (f": {line}" if line else "")
                         + f" → menu \"RasQberry: {g['title']}\"")
            demo_entries(g["id"], depth + 1, lines)

    qd = menus["do_quantum_demo_menu"]
    # the groups stand where the call has "$@"
    qd.items = [i for i in qd.items]
    special = {"do_quantum_demo_menu": {}}
    groups_tag = "<groups>"
    items = []
    call = statement_at(funcs["do_quantum_demo_menu"], next(
        i for i, l in enumerate(funcs["do_quantum_demo_menu"]) if "show_menu" in l))
    for tag, label in pairs([w for w in tokens(call_text(call, "show_menu"))
                             if w not in ("--tags", "--notags")][2:]):
        if tag == "$@":
            items.append((groups_tag, "Demo groups", False))
        else:
            items.append((tag, label, False))
    qd.items = items
    special["do_quantum_demo_menu"][groups_tag] = groups_entries

    main = menus["do_rasqberry_menu"]
    lines = [HEADER + "# The RasQberry menu",
             "",
             "Open it from the desktop icon **RasQberry Configuration (raspi-config)**, or in a "
             "terminal with `sudo raspi-config` and then **0 RasQberry**. The menu runs inside "
             "raspi-config, as root. Arrow keys move, Enter selects, Esc or *Back* goes back.",
             "",
             "Values in <angle brackets> change with the Pi's state (for example <on/off>). "
             "Entries marked *(only when it applies)* appear only on some Pis, for example "
             "only on an A/B image or only while Raspberry Pi Connect is installed.",
             "",
             f"## {main.title}",
             ""]
    if main.prompt:
        lines += [main.prompt, ""]
    render_menu(main, menus, 0, lines, {"do_rasqberry_menu"}, special, shown)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The desktop
# ---------------------------------------------------------------------------


def desktop_entry(path):
    """A .desktop file's [Desktop Entry] section as a dict."""
    cp = configparser.RawConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read_string(read(path))
    return dict(cp["Desktop Entry"]) if cp.has_section("Desktop Entry") else {}


def session_module():
    """rq_desktop_session.py, imported (its folder rules are the real ones)."""
    spec = importlib.util.spec_from_file_location("rq_desktop_session",
                                                  os.path.join(BIN, "rq_desktop_session.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def what_it_opens(exec_line):
    """A launcher's Exec line, shortened to the command that matters."""
    m = re.search(r"\b(rq_demo_(?:run|choose)\.sh(?:\s+[\w-]+){1,2})", exec_line)
    if m:
        return "`" + m.group(1) + "`"
    # the command behind rq_hold_on_error.sh (it only keeps a failed window open)
    found = [c for c in re.findall(r"/usr/bin/(rq_[\w.]+(?:\s+(?:--?)?[a-z][\w-]*)*)", exec_line)
             if not c.startswith("rq_hold_on_error")]
    if found:
        return "`" + found[-1].strip() + "`"
    m = re.search(r"-e \"([^\"]+)\"", exec_line)
    if m:
        return "`" + m.group(1) + "`"
    m = re.search(r"https?://\S+", exec_line)
    if m:
        return "the browser at " + m.group(0)
    return "`" + exec_line.split()[0].split("/")[-1] + "`"


def desktop_md():
    """desktop.md: icons, folders, the taskbar and what starts at login."""
    sess = session_module()
    groups = sess.load_groups(GROUPS_FILE)
    gd = groups_data()
    launchers = {}
    for path in sorted(glob.glob(os.path.join(BOOKMARKS, "*.desktop"))):
        name = os.path.basename(path)[:-len(".desktop")]
        launchers[name] = (path, desktop_entry(path))
    # The image puts the ICON_ORDER launchers on the desktop (the stage's list,
    # test_every_desktop_launcher_has_a_place_in_the_layout); the others are
    # only in the applications menu (rig mission 2026-10-16: LED Test was
    # listed in the LED panel folder)
    order = [n for n in sess.ICON_ORDER if n in launchers]
    menu_only = sorted(n for n in launchers if n not in sess.ICON_ORDER)

    def row(name):
        path, e = launchers[name]
        comment = e.get("Comment", "").strip()
        title = e.get("Name", name)
        if title.endswith(" (beta)"):        # said once, on the name
            comment = comment.removeprefix("(beta) ")
        if comment and comment[-1] not in ".!?":
            comment += "."
        return f"- **{title}**: {comment} Opens {what_it_opens(e.get('Exec', ''))}."

    lines = [HEADER + "# The desktop",
             "",
             "The desktop shows a few system icons, some starter demos, and one icon per demo "
             "group. A group icon opens a window with the group's demos as icons. Icons start "
             "with a double-click (one tap in touch mode). On a small screen the starters "
             "leave the desktop first; they stay in their group windows. "
             f"(Layout: `rq_desktop_session.py`, at every login.)",
             "",
             "## On the desktop itself",
             ""]
    for name in groups["system"]:
        if name in launchers:
            extra = ""
            if name in getattr(sess, "TOUCHSCREEN_ONLY", ()):
                extra = " *(only while a touchscreen is connected)*"
            if name == getattr(sess, "SETUP_LAUNCHER", ""):
                extra = " *(last icon; it goes once the setup checklist is done)*"
            lines.append(row(name) + extra)
    lines += ["", "Starters (also in their group windows):", ""]
    for name in groups["starters"]:
        if name in launchers:
            lines.append(row(name))
    lines += ["", "## Group icons and their windows", ""]
    for g in gd["groups"]:
        lines += [f"### {g['title']}", "", g.get("description", ""), ""]
        members = [n for n in order
                   if sess.launcher_group(n, launchers[n][0], groups, [MANIFESTS], CATALOGUE) == g["id"]]
        for n in members:
            lines.append(row(n))
        cats = [d for d in catalogue_demos()
                if (d.get("group") if d.get("group") in group_titles() else catalogue_group()) == g["id"]]
        for d in cats:
            beta = " (beta)" if d.get("maturity") == "beta" else ""
            lines.append(f"- **{d.get('name', d['id'])}{beta}** *(catalogue demo: its icon comes when it "
                         f"is added)*: {d.get('summary', '')}")
        if g.get("catalogue"):
            lines.append("- Demos added from the catalogue land here unless the catalogue names "
                         "another group; the window offers adding one.")
        if not members and not cats and not g.get("catalogue"):
            lines.append("- (no icons)")
        lines.append("")
    loose = [n for n in order if n not in groups["system"] and n not in groups["starters"]
             and sess.launcher_group(n, launchers[n][0], groups, [MANIFESTS], CATALOGUE) is None]
    if loose:
        lines += ["## Other launchers", ""] + [row(n) for n in loose] + [""]
    lines += ["## Taskbar, main menu and login", ""]
    if os.path.isdir(os.path.join(ROOT, "desktop-icons", "start-here")):
        lines.append("- **Main menu button** (top left of the taskbar): the RasQberry icon.")
    if os.path.exists(os.path.join(CONFIG, "desktop-categories", "rasqberry.directory")):
        line = "- The applications menu has a **RasQberry** section with the demo launchers."
        if menu_only:
            line += " Only there: " + ", ".join(
                f"**{launchers[n][1].get('Name', n)}**" for n in menu_only) + "."
        lines.append(line)
    for path in sorted(glob.glob(os.path.join(AUTOSTART, "*.desktop"))):
        e = desktop_entry(path)
        lines.append(f"- **{e.get('Name', '')}** (at login): {e.get('Comment', '').strip()}")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def kept_settings_re():
    """The KEY_RE of rq_device_settings.sh: settings kept on /data."""
    m = re.search(r"^KEY_RE='([^']+)'", read(DEVICE_SETTINGS), re.M)
    return re.compile(m.group(1)) if m else None


ACRONYMS = {"LED", "LEDS", "IBM", "SSH", "VNC", "API", "URL", "GPIO"}


def sentence_case(text):
    """LED CONFIGURATION -> LED configuration; DISPLAY/INTERFACE -> Display/interface."""
    words = []
    for k, word in enumerate(text.split()):
        parts = []
        for part in word.split("/"):
            if part in ACRONYMS:
                parts.append(part)
            else:
                parts.append(part.lower())
        word = "/".join(parts)
        if k == 0 and word[:1].islower():
            word = word[0].upper() + word[1:]
        words.append(word)
    return " ".join(words)


def settings_md():
    """settings.md: every setting, its default and its comment, by section."""
    kept = kept_settings_re()
    lines = [HEADER + "# Settings",
             "",
             "RasQberry's settings live in `/usr/config/rasqberry_environment.env` "
             "(shipped defaults below). Change them in the RasQberry menu where it offers them, "
             "or under **Advanced > Edit a RasQberry Two setting**. Settings marked **kept** "
             "are also stored on the /data partition, so they survive an A/B image update.",
             ""]
    comment, installed = [], []
    section = None
    for raw in read(ENV_FILE).splitlines():
        line = raw.strip()
        m = re.match(r"^#\s*\d+\.\s+([A-Z][A-Z/ -]+)(\(.*\))?\s*$", line)
        if m:
            section = sentence_case(m.group(1).strip())
            lines += ["", f"## {section}", ""]
            comment = []
            continue
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if text and not set(text) <= set("=-"):
                comment.append(text)
            continue
        if not line:
            comment = []
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if key.endswith("_INSTALLED"):
            installed.append(key)
            comment = []
            continue
        flag = " **kept**" if kept and kept.match(key + "=") else ""
        shown = value if value != "" else "(empty)"
        desc = " ".join(comment)
        lines.append(f"- `{key}` = `{shown}`{flag}" + (f": {desc}" if desc else ""))
        comment = []
    # a section with only internal flags has nothing left to show
    cleaned = []
    for k, line in enumerate(lines):
        if line.startswith("## "):
            end = next((j for j in range(k + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
            if not any(x.startswith("- ") for x in lines[k + 1:end]):
                continue
        cleaned.append(line)
    lines = cleaned
    if installed:
        lines += ["", "## Installed demos (internal)", "",
                  "Flags the demo installers set (true/false), one per demo: "
                  + ", ".join(f"`{k}`" for k in installed) + "."]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

# More commands for people, beyond rq_help's list (rq_help names the ones to
# type first). Everything else in RQB2-bin is run by RasQberry itself (menu,
# services, boot, desktop, build) and is listed by name only.
MORE_COMMANDS = [
    "rq_version.sh", "rq_demo_choose.sh", "rq_demo_add_external.sh", "rq_demo_update.sh",
    "rq_demo_validate.sh", "rq_docker_demos.sh", "rq_led_brightness.sh", "rq_led_painter.sh",
    "rq_led_display_logo.sh", "rq_led_web.py", "rq_audio_delay_calibrate.sh", "rq_hotspot.sh",
    "rq_set_qiskit_ibm_token.py", "rq_doqumentation.sh", "rq_entangible.sh",
    "rq_slot_status.sh", "rq_update_slot.sh", "rq_ab_releases.sh", "rq_expand_ab.sh",
    "rq_update_from_branch.sh", "rq_install_qiskit.sh", "rq_user_rename.sh",
]


def help_sections():
    """
    rq_help's list: its headings, each with (command line, what it does).

    Returns:
        list: (heading, [(command, text)])
    """
    text = read(os.path.join(BIN, "rq_help"))
    m = re.search(r"cat <<'EOF'\n(.*?)\nEOF", text, re.S)
    out = []
    for line in (m.group(1) if m else "").splitlines()[1:]:
        if not line.strip():
            continue
        if not line.startswith(" "):
            out.append((line.strip(), []))
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if out:
            out[-1][1].append((parts[0], parts[1] if len(parts) > 1 else ""))
    return out


def script_of(command):
    """The RQB2-bin script a command line runs (rq_demo_run.sh <demo> -> rq_demo_run.sh)."""
    for word in command.split():
        if word.startswith("rq_") and os.path.exists(os.path.join(BIN, word)):
            return word
    return None


def header_comment(text):
    """The leading comment block of a script (shell # lines or a docstring)."""
    if re.match(r"^(#![^\n]*\n)?\s*(\"\"\"|''')", text):
        m = re.search(r"(\"\"\"|''')(.*?)\1", text, re.S)
        return m.group(2) if m else ""
    block = []
    for line in text.splitlines()[1:80]:
        s = line.strip()
        if s.startswith("#"):
            block.append(s[1:].rstrip())
        elif s.startswith("set ") or not s:
            if block and not s:
                block.append("")
            continue
        else:
            break
    return "\n".join(block)


def first_sentence(text, limit=240):
    """The first sentence of a paragraph, on one line ("e.g." does not end it)."""
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.+?(?<!e\.g)(?<!i\.e)[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0] + " …"
    return out


def describe(name):
    """
    A command's one-line description and its usage lines.

    Returns:
        (str, list): description, usage lines
    """
    head = header_comment(read(os.path.join(BIN, name)))
    lines = head.splitlines()
    desc = ""
    for line in lines[:3]:
        m = re.match(rf"\s*(?:RasQberry(?: Two)?:\s*)?{re.escape(name)}\s+-\s+(.+)", line)
        if m:
            desc = first_sentence(re.sub(r"\s*\([A-Z]-?\d+\)\s*$", "", m.group(1)))
            desc = desc[:1].upper() + desc[1:]
            break
    for i, line in enumerate(lines):
        if desc:
            break
        m = re.match(r"\s*Description:\s*(.*)", line)
        if m:
            para = [m.group(1)]
            for nxt in lines[i + 1:]:
                if not nxt.strip() or re.match(r"\s*(Usage|Usage:)", nxt):
                    break
                para.append(nxt)
            desc = first_sentence(" ".join(para))
            break
    if not desc:
        for line in lines:
            s = line.strip().strip("=").strip()
            if not s or s.startswith("!"):
                continue
            s = re.sub(rf"^(RasQberry( Two)?:\s*|{re.escape(name)}\s*[-:]\s*)", "", s)
            if s:
                desc = first_sentence(s)
                break
    usage = []
    for i, line in enumerate(lines):
        m = re.match(r"\s*Usage:?\s*(.*)", line)
        if m:
            first = m.group(1).rstrip()
            block = []
            for nxt in lines[i + 1:]:
                bare = nxt.strip()
                if not bare or not nxt.startswith((" ", "\t")) \
                        or (re.match(r"[A-Z][A-Za-z ()/-]*:", bare) and not bare.startswith(name)):
                    break
                block.append(nxt.rstrip())
            block = textwrap.dedent("\n".join(block)).splitlines() if block else []
            usage = ([first.strip()] if first.strip() else []) + block
            break
    if len(usage) > 10:
        usage = usage[:10] + ["…"]
    if desc:
        desc = desc[:1].upper() + desc[1:]
    return desc, usage


def command_block(name, lines):
    """One command's description and usage."""
    desc, usage = describe(name)
    if desc:
        lines += [desc, ""]
    if usage:
        lines += ["```", *usage, "```", ""]


def commands_md():
    """commands.md: rq_help's commands, more for people, and the names of the rest."""
    lines = [HEADER + "# Commands",
             "",
             "RasQberry's commands are in `/usr/bin` (from `RQB2-bin/` in the repository). "
             "`rq_help` lists the ones to type first; changes need `sudo`.",
             ""]
    done = {"rq_help"}
    for heading, entries in help_sections():
        lines += [f"## {heading}", ""]
        for command, what in entries:
            lines.append(f"- `{command}`: {what}")
        lines.append("")
        for command, _ in entries:
            name = script_of(command)
            if name and name not in done:
                done.add(name)
                lines += [f"### {name}", ""]
                command_block(name, lines)
    more = [n for n in MORE_COMMANDS if n not in done and os.path.exists(os.path.join(BIN, n))]
    if more:
        lines += ["## More commands", "", "Not in `rq_help`'s list, for advanced use.", ""]
        for name in more:
            done.add(name)
            lines += [f"### {name}", ""]
            command_block(name, lines)
    rest = sorted(os.path.basename(p) for p in glob.glob(os.path.join(BIN, "*"))
                  if os.path.isfile(p) and os.path.basename(p) not in done
                  and not p.endswith(".md") and not os.path.basename(p).startswith("_"))
    lines += ["## Run by RasQberry itself", "",
              "Used by the menu, the desktop, services and the image build, not meant to be "
              "run by hand: " + ", ".join(f"`{n}`" for n in rest) + "."]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Demos
# ---------------------------------------------------------------------------


def needs_text(m):
    """What a demo needs, in words."""
    hw = m.get("needs_hw") or {}
    out = []
    if hw.get("leds") is True:
        out.append("the LED panel (or its on-screen view)")
    if hw.get("network") is True:
        out.append("internet")
    disp = hw.get("display")
    if disp == "required":
        out.append("a screen")
    elif disp == "none":
        out.append("works without a screen")
    ibm = m.get("needs_ibm_token")
    if ibm == "required":
        out.append("an IBM Quantum account")
    elif ibm == "prefer":
        out.append("an IBM Quantum account for real quantum computers (optional)")
    if (m.get("install") or {}).get("docker_image_of") or (m.get("entrypoint") or {}).get("type") == "docker":
        out.append("a 32 GB card (Docker)")
    if re.search(r"\b(webcam|camera)\b", m.get("description", ""), re.I):
        out.append("a camera")
    return out


def demos_md():
    """demos.md: every demo and how to start it."""
    titles = group_titles()
    mans = manifests()
    lines = [HEADER + "# Demos",
             "",
             "Every demo starts from its group in the RasQberry menu (**Quantum Demos > "
             "<group>**), from its icon in the group's desktop window, or in a terminal with "
             "`rq_demo_run.sh <id>` (variants: `rq_demo_run.sh <id> <variant>`). "
             "*(beta)*: new or less tested.",
             ""]
    for g in groups_data()["groups"]:
        gid = g["id"]
        ids = [d for d, data in sorted(mans.items(), key=lambda kv: kv[1][0]["name"].lower())
               if demo_group(d, data[0]) == gid]
        cats = [d for d in catalogue_demos()
                if (d.get("group") if d.get("group") in titles else catalogue_group()) == gid]
        if not ids and not cats:
            continue
        lines += [f"## {g['title']}", ""]
        for demo_id in ids:
            m = mans[demo_id][0]
            beta = " *(beta)*" if m.get("maturity") else ""
            lines.append(f"### {m['name']}{beta}")
            lines.append("")
            lines.append(m.get("description", "").rstrip(".") + ".")
            lines.append("")
            facts = [f"id `{demo_id}`"]
            menu = m.get("menu") or {}
            if menu.get("show") is not False and not menu.get("parent"):
                facts.append(f"menu: Quantum Demos > {g['title']} > {m['name']}")
            elif menu.get("parent"):
                facts.append(f"menu: Quantum Demos > {g['title']} (its entries stand there directly)")
            if (m.get("desktop") or {}).get("show"):
                facts.append(f"desktop: {g['title']} window")
            need = needs_text(m)
            if need:
                facts.append("needs " + ", ".join(need))
            dl = (m.get("install") or {}).get("download") or {}
            if dl.get("download_mb"):
                facts.append(f"download about {dl['download_mb']} MB on first start")
            lines.append("- " + "; ".join(facts) + ".")
            for v in m.get("variants") or []:
                vb = " *(beta)*" if v.get("maturity") else ""
                lines.append(f"  - variant `{v.get('id')}`: {v.get('name')}{vb}")
            lines.append("")
        for d in cats:
            beta = " *(beta)*" if d.get("maturity") else ""
            lines.append(f"### {d.get('name', d['id'])}{beta}")
            lines.append("")
            facts = [f"id `{d['id']}`", "from the catalogue: add it with Quantum Demos > Manage "
                     "demos > Add demo from catalogue (or `rq_demo_add_external.sh " + d["id"] + "`)"]
            if d.get("provider"):
                facts.append(f"provided by {d['provider']}")
            if d.get("leds"):
                facts.append("drives the LED panel")
            dl = d.get("download") or {}
            if dl.get("download_mb"):
                facts.append(f"download about {dl['download_mb']} MB")
            lines.append((d.get("summary", "").capitalize() + ".") if d.get("summary") else "")
            lines.append("")
            lines.append("- " + "; ".join(facts) + ".")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Index and main
# ---------------------------------------------------------------------------

PAGES = [
    ("menu.md", "The RasQberry menu", "every menu and entry of the RasQberry menu in raspi-config"),
    ("desktop.md", "The desktop", "icons, group windows, the taskbar and what starts at login"),
    ("demos.md", "Demos", "every demo, what it needs and how to start it"),
    ("settings.md", "Settings", "every setting with its default, and which survive updates"),
    ("commands.md", "Commands", "the terminal commands for people"),
]


def index_md():
    """index.md: the pages."""
    lines = [HEADER + "# RasQberry Two reference",
             "",
             "These pages are generated from the RasQberry Two code (development branch) by "
             f"`{SCRIPT}`, so they say what the Pi actually does. They are a reference for "
             "advanced users and the knowledge of the RasQberry helpers; the user guide is "
             "rasqberry.org. Rebuild them after a change with "
             f"`python3 {SCRIPT}`; a unit test fails while they are out of date.",
             ""]
    for fname, title, what in PAGES:
        lines.append(f"- [{title}]({fname}): {what}.")
    return "\n".join(lines) + "\n"


def build():
    """All pages: file name -> text."""
    return {
        "index.md": index_md(),
        "menu.md": menu_md(),
        "desktop.md": desktop_md(),
        "demos.md": demos_md(),
        "settings.md": settings_md(),
        "commands.md": commands_md(),
    }


def main():
    """Write the pages, or check them."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when the files are out of date")
    args = parser.parse_args()
    pages = build()
    stale = []
    for fname, text in pages.items():
        path = os.path.join(HERE, fname)
        old = read(path) if os.path.exists(path) else None
        if old != text:
            stale.append(fname)
            if not args.check:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
    if args.check and stale:
        print("Out of date: " + ", ".join(stale) + f". Run: python3 {SCRIPT}", file=sys.stderr)
        return 1
    if not args.check:
        print("Wrote " + ", ".join(pages) if stale else "Up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
