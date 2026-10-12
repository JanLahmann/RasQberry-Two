#!/usr/bin/env python3
"""
RasQberry: the demo catalogue online (known-demos.json from rasqberry.org).

The image ships a catalogue (/usr/config/known-demos.json). rasqberry.org
publishes the current one (CI copies RQB2-config/known-demos.json from the
development branch to the website). This script fetches it, checks it, and
keeps it in /var/cache/rasqberry/known-demos.json when it is newer than the
image's: rq_catalogue_file (rq_common.sh) and rq_desktop_session.py then use
it, so new demos and new pins reach a Pi without an image update (Jan,
2026-10-12).

Trust: only https://rasqberry.org/known-demos.json (no other host, also not
after a redirect), at most MAX_BYTES. A copy is kept only if every entry has
a kebab-case id, an https:// repo_url and a full 40-hex commit SHA, no id
is a demo the image ships, and its catalogue_version is higher than the
image's and the cached one's (no rollback to an older list). Otherwise the
last good copy stays.

Engine: an entry may need a newer RasQberry ("min_engine", an integer). This
image's is ENGINE; such entries are listed as "needs a newer RasQberry" and
cannot be installed. ENGINE 2: needs_hw.audio and min_engine are known.

News (the tray notice, the login line, the menu):
  new        an entry the image's catalogue does not have, not installed,
             added in the last NEW_DAYS days
  update     an installed catalogue demo whose checkout is not at the pin
  renamed    an installed demo whose id an entry "replaces"
  withdrawn  an installed catalogue demo that is no longer in the catalogue

Usage:
  rq_catalogue.py --refresh [--system]   fetch and keep a newer catalogue (root:
                                         --system also writes the login line)
  rq_catalogue.py --path                 the catalogue file in use
  rq_catalogue.py --news [--json]        what is new for this user's demos
  rq_catalogue.py --line                 the login line (empty if nothing)
  rq_catalogue.py --engine               this image's catalogue engine
  rq_catalogue.py --check FILE           would a Pi take FILE? (CI)

Environment (tests, trials): RQ_CATALOGUE_URL (http(s):// or file://; its host
  replaces rasqberry.org), RQ_CATALOGUE_SHIPPED, RQ_CATALOGUE_CACHE_DIR,
  RQ_MANIFEST_DIR (shipped manifests), RQ_USER_HOME, RQ_CATALOGUE_NOTICE,
  RQ_NOW (ISO date).
"""

import json
import logging
import os
import pwd
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

log = logging.getLogger("rq_catalogue")

CATALOGUE_URL = "https://rasqberry.org/known-demos.json"
ENGINE = 2
MAX_BYTES = 512 * 1024
FETCH_TIMEOUT = 15
NEW_DAYS = 30
CACHE_NAME = "known-demos.json"
NOTICE_FILE = "/var/lib/rasqberry/catalogue-notice"
LOGIN_WIDTH = 80

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG = "/usr/config" if _HERE == "/usr/bin" else os.path.join(os.path.dirname(_HERE), "RQB2-config")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+/[A-Za-z0-9._~/-]+$")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def shipped_file():
    """The image's catalogue."""
    return os.environ.get("RQ_CATALOGUE_SHIPPED") or os.path.join(_CONFIG, CACHE_NAME)


def manifest_dir():
    """The image's demo manifests."""
    return os.environ.get("RQ_MANIFEST_DIR") or os.path.join(_CONFIG, "demo-manifests")


def cache_dir():
    """Where the checked copy from rasqberry.org is kept (root writes it)."""
    return os.environ.get("RQ_CATALOGUE_CACHE_DIR") or "/var/cache/rasqberry"


def source_url():
    """The catalogue's address (RQ_CATALOGUE_URL for tests)."""
    return os.environ.get("RQ_CATALOGUE_URL") or CATALOGUE_URL


def user_home():
    """The desktop user's home: RQ_USER_HOME, else ~ (as root: user 1000)."""
    home = os.environ.get("RQ_USER_HOME")
    if home:
        return home
    if os.geteuid() == 0:
        try:
            return pwd.getpwuid(1000).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_atomic(path, text, mode=0o644):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".rq-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Checking a catalogue (pure)
# ---------------------------------------------------------------------------

def version(data):
    """catalogue_version of a catalogue (0: none, i.e. older than any published one)."""
    v = (data or {}).get("catalogue_version") if isinstance(data, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 0


def shipped_ids(directory=None):
    """Ids of the demos the image ships (rq_demo_<id>.json)."""
    out = set()
    try:
        for name in os.listdir(directory or manifest_dir()):
            m = re.match(r"^rq_demo_(.+)\.json$", name)
            if m and m.group(1) != "schema":
                out.add(m.group(1))
    except OSError:
        pass
    return out


def problems(data, shipped=()):
    """
    Why a catalogue from the website must not be used.

    Args:
        data: the parsed JSON
        shipped (set): ids of the demos the image ships

    Returns:
        list: one line per problem (empty: it may be used)
    """
    if not isinstance(data, dict):
        return ["not a JSON object"]
    out = []
    if not version(data):
        out.append("catalogue_version is missing or not a positive integer")
    demos = data.get("demos")
    if not isinstance(demos, list):
        return out + ["demos is not a list"]
    seen = set()
    for i, d in enumerate(demos):
        if not isinstance(d, dict):
            out.append(f"entry {i}: not an object")
            continue
        did = d.get("id")
        label = did if isinstance(did, str) else f"entry {i}"
        if not isinstance(did, str) or not ID_RE.match(did):
            out.append(f"{label}: id is not kebab-case")
        elif did in seen:
            out.append(f"{label}: id appears twice")
        elif did in shipped:
            out.append(f"{label}: id of a demo the image ships")
        seen.add(did)
        if not isinstance(d.get("repo_url"), str) or not URL_RE.match(d["repo_url"]):
            out.append(f"{label}: repo_url is not an https:// address")
        if not isinstance(d.get("ref"), str) or not SHA_RE.match(d["ref"]):
            out.append(f"{label}: ref is not a full commit SHA")
        mp = d.get("manifest_path", "rqb-demo.json")
        if not isinstance(mp, str) or mp.startswith("/") or ".." in mp.split("/") or not mp:
            out.append(f"{label}: manifest_path is not a path inside the repository")
        me = d.get("min_engine", 1)
        if not isinstance(me, int) or isinstance(me, bool) or me < 1:
            out.append(f"{label}: min_engine is not a positive integer")
        rep = d.get("replaces", [])
        if not isinstance(rep, list) or not all(isinstance(r, str) and ID_RE.match(r) for r in rep):
            out.append(f"{label}: replaces is not a list of ids")
    return out


def needs_newer(entry, engine=ENGINE):
    """Does this entry need a newer RasQberry than this image?"""
    me = entry.get("min_engine", 1)
    return isinstance(me, int) and me > engine


# ---------------------------------------------------------------------------
# The catalogue in use, fetching
# ---------------------------------------------------------------------------

def current(shipped=None, cache=None, manifests=None):
    """
    The catalogue in use: the cached copy from rasqberry.org when it is
    still sound and newer than the image's, else the image's.

    Returns:
        tuple: (data, path)
    """
    shipped = shipped or shipped_file()
    cache_path = os.path.join(cache or cache_dir(), CACHE_NAME)
    base = _read_json(shipped)
    if not isinstance(base, dict):
        base = {"demos": []}
    cached = _read_json(cache_path)
    if (isinstance(cached, dict) and version(cached) > version(base)
            and not problems(cached, shipped_ids(manifests))):
        return cached, cache_path
    return base, shipped


def _host(url):
    return (urllib.parse.urlparse(url).hostname or "").lower()


def refresh(cache=None, shipped=None, manifests=None, timeout=FETCH_TIMEOUT):
    """
    Fetch the catalogue; keep it when it is sound and newer.

    Returns:
        tuple: (status, text) with status 'updated', 'unchanged', 'rejected'
        or 'offline'
    """
    url = source_url()
    host = _host(url)
    cache = cache or cache_dir()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RasQberry-Two catalogue"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.geturl() if hasattr(resp, "geturl") else url
            if url.startswith(("http://", "https://")) and _host(final) != host:
                return "rejected", f"redirected to another host: {_host(final)}"
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return "offline", f"HTTP {e.code}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return "offline", str(e)
    if len(body) > MAX_BYTES:
        return "rejected", f"larger than {MAX_BYTES // 1024} KB"
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "rejected", "not JSON"
    bad = problems(data, shipped_ids(manifests))
    if bad:
        return "rejected", "; ".join(bad[:5])
    have, _ = current(shipped, cache, manifests)
    if version(data) <= version(have):
        return "unchanged", f"version {version(data)} (in use: {version(have)})"
    try:
        _write_atomic(os.path.join(cache, CACHE_NAME), json.dumps(data, indent=1) + "\n")
    except OSError as e:
        return "offline", f"cannot keep it: {e}"
    return "updated", f"version {version(data)}"


# ---------------------------------------------------------------------------
# What is new for this Pi's demos
# ---------------------------------------------------------------------------

def checkout_head(path):
    """The commit a checkout is at ('' if unknown). The add-flow checks out a SHA (detached)."""
    head = ""
    try:
        with open(os.path.join(path, ".git", "HEAD")) as f:
            head = f.read().strip()
    except OSError:
        return ""
    if head.startswith("ref: "):
        ref = head[5:]
        try:
            with open(os.path.join(path, ".git", ref)) as f:
                return f.read().strip()
        except OSError:
            return ""
    return head if SHA_RE.match(head) else ""


def installed(home=None, repo=None):
    """
    The catalogue demos installed for the user: {id: {name, head}}.
    The add-flow copies their manifests to ~/.local/config/demo-manifests.
    """
    home = home or user_home()
    repo = repo or os.environ.get("REPO") or "RasQberry-Two"
    directory = os.path.join(home, ".local", "config", "demo-manifests")
    out = {}
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return out
    for name in names:
        if not (name.startswith("rq_demo_") and name.endswith(".json")):
            continue
        m = _read_json(os.path.join(directory, name))
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            continue
        wd = (m.get("entrypoint") or {}).get("working_dir") or ""
        head = checkout_head(os.path.join(home, repo, "demos", wd)) if wd and "/" not in wd else ""
        out[m["id"]] = {"name": m.get("name") or m["id"], "head": head}
    return out


def _today():
    t = os.environ.get("RQ_NOW", "")
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).date() if t else date.today()
    except ValueError:
        return date.today()


def news(catalogue, base, have, today=None, engine=ENGINE):
    """
    What the catalogue brings for this Pi.

    Args:
        catalogue (dict): the catalogue in use
        base (dict): the image's catalogue (what came with the image is not news)
        have (dict): installed() result
        today (date)

    Returns:
        list: dicts with kind (new, update, renamed, withdrawn), id, name,
        and key (one notice per key); new: provider, summary; update: ref;
        renamed: new (the new id)
    """
    today = today or _today()
    demos = [d for d in catalogue.get("demos") or [] if isinstance(d, dict)]
    by_id = {d.get("id"): d for d in demos}
    base_ids = {d.get("id") for d in (base or {}).get("demos") or [] if isinstance(d, dict)}
    out = []
    replaced = set()
    for did, info in sorted(have.items()):
        entry = by_id.get(did)
        if entry is None:
            succ = next((d for d in demos if did in (d.get("replaces") or [])), None)
            if succ is not None:
                replaced.add(succ.get("id"))
                if not needs_newer(succ, engine) and succ.get("id") not in have:
                    out.append({"kind": "renamed", "id": did, "name": info["name"],
                                "new": succ["id"], "new_name": succ.get("name") or succ["id"],
                                "key": f"renamed:{did}:{succ['id']}"})
            elif did not in shipped_ids():
                out.append({"kind": "withdrawn", "id": did, "name": info["name"],
                            "key": f"withdrawn:{did}"})
            continue
        if info["head"] and info["head"] != entry.get("ref") and not needs_newer(entry, engine):
            out.append({"kind": "update", "id": did, "name": entry.get("name") or info["name"],
                        "ref": entry.get("ref"), "key": f"update:{did}:{entry.get('ref')}"})
    for d in demos:
        did = d.get("id")
        if did in have or did in base_ids or did in replaced or needs_newer(d, engine):
            continue
        try:
            added = date.fromisoformat(str(d.get("added", "")))
        except ValueError:
            continue
        if 0 <= (today - added).days <= NEW_DAYS:
            out.append({"kind": "new", "id": did, "name": d.get("name") or did,
                        "provider": d.get("provider") or "", "summary": d.get("summary") or "",
                        "key": f"new:{did}"})
    return out


def popup_text(item):
    """The one-time desktop notice for one news item."""
    k, name = item["kind"], item["name"]
    if k == "new":
        by = f" by {item['provider']}" if item.get("provider") else ""
        return (f"New in the demo catalogue: {name}{by}. Add it from the RasQberry "
                f"badge in the taskbar, or the RasQberry menu (Quantum Demos > Manage demos).")
    if k == "update":
        return f"An update for {name} is available. Install it from the RasQberry badge in the taskbar."
    if k == "renamed":
        return (f"{name} is now called {item['new_name']}. Move to it from the RasQberry "
                f"badge in the taskbar.")
    return (f"{name} was removed from the demo catalogue. It still runs; remove it from "
            f"the RasQberry badge in the taskbar if you no longer want it.")


def menu_label(item):
    """The tray menu's action for one news item."""
    k, name = item["kind"], item["name"]
    if k == "new":
        return f"New demo: {name}…"
    if k == "update":
        return f"Update {name}…"
    if k == "renamed":
        return f"Move {name} to {item['new_name']}…"
    return f"Remove {name} (withdrawn)…"


def command(item):
    """The rq_demo_add_external.sh arguments that act on a news item."""
    k = item["kind"]
    if k == "new":
        return [item["id"]]
    if k in ("update", "renamed"):
        return ["--update", item["id"]]
    return ["--remove", item["id"]]


def login_line(items, width=LOGIN_WIDTH):
    """One line for an SSH or console login ('' when nothing is new)."""
    if not items:
        return ""
    new = [i["name"] for i in items if i["kind"] == "new"]
    act = [i for i in items if i["kind"] != "new"]
    parts = []
    if new:
        parts.append("New in the demo catalogue: " + ", ".join(new) + ".")
    if act:
        parts.append(f"{len(act)} catalogue demo{'s' if len(act) > 1 else ''} to update: "
                     + ", ".join(f"rq_demo_add_external.sh {' '.join(command(i))}" for i in act))
    line = " ".join(parts)
    if new and not act:
        line += " RasQberry menu: Quantum Demos > Manage demos."
    return line if len(line) <= width * 2 else line[:width * 2 - 3] + "..."


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main(argv=None):
    """Command line; see the module docstring."""
    argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.split("Usage:", 1)[1].split("Environment", 1)[0].rstrip())
        return 0
    if argv[0] == "--engine":
        print(ENGINE)
        return 0
    if argv[0] == "--check":
        # CI: would a Pi take this file? (--check FILE)
        data = _read_json(argv[1]) if len(argv) > 1 else None
        bad = problems(data, shipped_ids())
        for line in bad:
            print(line)
        if not bad:
            print(f"OK: catalogue_version {version(data)}, {len(data['demos'])} demos")
        return 1 if bad else 0
    if argv[0] == "--refresh":
        status, text = refresh()
        print(f"Demo catalogue: {status} ({text})")
        if "--system" in argv:
            base = _read_json(shipped_file()) or {}
            cat, _ = current()
            line = login_line(news(cat, base, installed()))
            notice = os.environ.get("RQ_CATALOGUE_NOTICE") or NOTICE_FILE
            try:
                if line:
                    _write_atomic(notice, line + "\n")
                elif os.path.exists(notice):
                    os.unlink(notice)
            except OSError as e:
                print(f"Could not write {notice}: {e}", file=sys.stderr)
        return 0 if status in ("updated", "unchanged") else 1
    cat, path = current()
    if argv[0] == "--path":
        print(path)
        return 0
    if argv[0] in ("--news", "--line"):
        items = news(cat, _read_json(shipped_file()) or {}, installed())
        if argv[0] == "--line":
            line = login_line(items)
            if line:
                print(line)
        elif "--json" in argv:
            print(json.dumps(items))
        else:
            for i in items:
                print(popup_text(i))
        return 0
    print(f"Unknown option: {argv[0]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
