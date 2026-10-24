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
after a redirect), at most MAX_BYTES. A copy is kept only if it is a JSON
object with a demos list and its catalogue_version is higher than the
image's and the cached one's (no rollback to an older list); otherwise the
last good copy stays. An entry is taken only if it has a kebab-case id, an
https:// repo_url whose last part is a plain directory name (not one a
shipped demo uses), a full 40-hex commit SHA, whole numbers for its sizes
and plain one-line texts; any other entry, one whose id appears twice, and
one with the id of a demo this image ships, is left out (and logged), not
the whole catalogue (review B6, B7). A demo that moves into the image keeps
its entry, so older images still have it.

Engine: an entry may need a newer RasQberry ("min_engine", an integer). This
image's is ENGINE; such entries are listed as "needs a newer RasQberry" and
cannot be installed. ENGINE 2: needs_hw.audio and min_engine are known.

News (the tray notice, the login line, the menu):
  new        an entry the image's catalogue does not have, not installed,
             added in the last NEW_DAYS days
  update     an installed catalogue demo whose checkout is not at the pin
  renamed    an installed demo whose id an entry "replaces"
  withdrawn  an installed catalogue demo that is no longer in the catalogue
  tested     a demo the image ships has a newer tested version
             ("tested_updates"; rq_demo_update.sh --tested installs it)

Tested updates (Jan, 2026-10-24): an entry of "tested_updates" moves a demo
the image ships to a newer pin we tested on the Pi 4 and Pi 5, without an
image update: {"id", "kind": "image" | "ref", "pin", "from": [release
pins], "label", "note", "added", "download_mb"}. It is offered only on a Pi
whose release pin is in "from", where the demo is downloaded and still on
its release version or an earlier tested update (not on a version chosen by
hand under Update demos), and only from the same source: an image pin must
be a digest of the image the release uses, a ref a full commit SHA (the
repository is the release's). A newer release ships its own pins, and those
win (rq_demo_set_version keeps a choice only for the release pin it
replaced).

Only demos the add-flow installed count (MARK in their manifest, or the
bare pinned checkout older add-flows left): a manifest written by hand to
test a demo (CONTRIBUTING.md) is never "withdrawn" or "updated" (review B3).

Usage:
  rq_catalogue.py --refresh [--system]   fetch and keep a newer catalogue (root:
                                         --system also writes the login line)
  rq_catalogue.py --path                 the catalogue file in use
  rq_catalogue.py --news [--json]        what is new for this user's demos
  rq_catalogue.py --line                 the login line (empty if nothing)
  rq_catalogue.py --engine               this image's catalogue engine
  rq_catalogue.py --tested ID:KIND       the tested update for this Pi:
                                         "PIN<TAB>LABEL<TAB>DOWNLOAD_MB" (none: exit 1)
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
import subprocess
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
# The label rq_demo_update.sh --tested records in demos/.demo-versions: a
# version chosen by hand has none, and gets no tested-update notice
TESTED_LABEL = "tested: "
TESTED_TEXTS = {"label": 60, "note": 200, "added": 40}
IMAGE_RE = re.compile(r"^([a-z0-9][a-z0-9._/-]{0,199})@sha256:[0-9a-f]{64}$")
LOGIN_WIDTH = 80

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG = "/usr/config" if _HERE == "/usr/bin" else os.path.join(os.path.dirname(_HERE), "RQB2-config")

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+/[A-Za-z0-9._~/-]+$")
# The checkout directory: the last part of repo_url without .git
DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
FILE_RE = DIR_RE
# Control characters (C0, DEL, C1): a text with one could rewrite the terminal
# at a login (the login line) or a notice
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# One-line texts of an entry, with their longest length
TEXTS = {"name": 80, "summary": 200, "provider": 120, "note": 4000, "own_stop_hint": 120,
         "formerly": 80, "maturity": 20, "added": 40}
SIZES = ("download_mb", "disk_mb", "peak_mb")
# Written into the manifest of a demo the add-flow installed
# (rq_demo_add_external.sh): {"ref": ..., "repo_url": ...}
MARK = "x-rasqberry-catalogue"


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


def shipped_dirs(directory=None):
    """The checkout directories (entrypoint.working_dir) of the demos the image ships."""
    directory = directory or manifest_dir()
    out = set()
    for did in shipped_ids(directory):
        m = _read_json(os.path.join(directory, f"rq_demo_{did}.json"))
        if not isinstance(m, dict):
            continue
        for part in [m] + [v for v in m.get("variants") or [] if isinstance(v, dict)]:
            wd = (part.get("entrypoint") or {}).get("working_dir") if isinstance(part.get("entrypoint"), dict) else None
            if isinstance(wd, str) and wd:
                out.add(wd)
    return out


def repo_dir(url):
    """The directory a repo_url is checked out to (rq_demo_add_external.sh repo_dir_name)."""
    base = url.rstrip("/").rsplit("/", 1)[-1]
    return base[:-4] if base.endswith(".git") else base


def clean_text(text, limit=80):
    """A text for a terminal or a notice: no control characters, at most limit characters."""
    text = CONTROL_RE.sub("", text if isinstance(text, str) else str(text or ""))
    return text if len(text) <= limit else text[:limit - 1] + "…"


def file_problems(data):
    """Why a catalogue is not used at all (empty: it may be)."""
    if not isinstance(data, dict):
        return ["not a JSON object"]
    out = []
    if not version(data):
        out.append("catalogue_version is missing or not a positive integer")
    if not isinstance(data.get("demos"), list):
        out.append("demos is not a list")
    return out


def entry_problems(d, label, taken_dirs=()):
    """
    Why one entry cannot be used (empty: it can).

    Args:
        d (dict): the entry
        label (str): how the lines name it
        taken_dirs (set): checkout directories the shipped demos use
    """
    out = []
    did = d.get("id")
    if not isinstance(did, str) or not ID_RE.match(did):
        out.append(f"{label}: id is not kebab-case")
    url = d.get("repo_url")
    if not isinstance(url, str) or not URL_RE.match(url):
        out.append(f"{label}: repo_url is not an https:// address")
    elif not DIR_RE.match(repo_dir(url)):
        out.append(f"{label}: repo_url does not end in a plain directory name")
    elif repo_dir(url) in taken_dirs:
        out.append(f"{label}: repo_url would replace the checkout of a demo the image ships")
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
    for key, limit in TEXTS.items():
        v = d.get(key)
        if v is None:
            continue
        if not isinstance(v, str) or len(v) > limit or CONTROL_RE.search(v):
            out.append(f"{label}: {key} is not a one-line text of at most {limit} characters")
    for key in ("group",):
        if key in d and not (isinstance(d[key], str) and ID_RE.match(d[key])):
            out.append(f"{label}: {key} is not an id")
    if "icon" in d and not (isinstance(d["icon"], str) and FILE_RE.match(d["icon"])):
        out.append(f"{label}: icon is not a file name")
    if "leds" in d and not isinstance(d["leds"], bool):
        out.append(f"{label}: leds is not true or false")
    dl = d.get("download")
    if dl is not None:
        if not isinstance(dl, dict):
            out.append(f"{label}: download is not an object")
        else:
            for key in SIZES:
                v = dl.get(key)
                if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
                    out.append(f"{label}: download.{key} is not a whole number of MB")
    return out


def sort_entries(data, shipped=(), taken_dirs=()):
    """
    The entries of a catalogue a Pi takes, and why the others are left out.
    One bad entry costs that entry, not the catalogue (review B7).

    Args:
        data (dict): a catalogue without file_problems()
        shipped (set): ids of the demos the image ships: their entries are
            left out here (a demo that moved into a newer image keeps its
            entry for the older ones)
        taken_dirs (set): checkout directories of the shipped demos

    Returns:
        tuple: (entries, problems, notes): problems are the lines CI refuses,
        notes the shipped ids
    """
    demos = data.get("demos") if isinstance(data, dict) else None
    if not isinstance(demos, list):
        return [], [], []
    ids, dirs = {}, {}
    for d in demos:
        if isinstance(d, dict):
            ids[d.get("id")] = ids.get(d.get("id"), 0) + 1
            if isinstance(d.get("repo_url"), str):
                dirs[repo_dir(d["repo_url"])] = dirs.get(repo_dir(d["repo_url"]), 0) + 1
    keep, bad, notes = [], [], []
    for i, d in enumerate(demos):
        if not isinstance(d, dict):
            bad.append(f"entry {i}: not an object")
            continue
        did = d.get("id")
        label = did if isinstance(did, str) else f"entry {i}"
        # (a demo that moved into the image keeps its entry and directory)
        found = entry_problems(d, label, () if did in shipped else taken_dirs)
        if isinstance(did, str) and ids.get(did, 0) > 1:
            found.append(f"{label}: id appears twice")
        if isinstance(d.get("repo_url"), str) and dirs.get(repo_dir(d["repo_url"]), 0) > 1:
            found.append(f"{label}: another entry uses the same checkout directory")
        if found:
            bad.extend(found)
        elif did in shipped:
            notes.append(f"{label}: id of a demo the image ships (left out on this image)")
        else:
            keep.append(d)
    return keep, bad, notes


def problems(data, shipped=(), taken_dirs=()):
    """
    Everything wrong with a catalogue (CI --check): file_problems and the
    entries a Pi would leave out for a fault of their own.

    Returns:
        list: one line per problem (empty: every entry may be used)
    """
    bad = file_problems(data)
    if bad:
        return bad
    return sort_entries(data, shipped, taken_dirs)[1] + sort_tested(data)[1]


def usable(data, manifests=None):
    """
    A copy of a catalogue with only the entries this image takes; None when
    the file is not used at all. The lines on the left-out entries are logged.
    """
    if file_problems(data):
        return None
    keep, bad, notes = sort_entries(data, shipped_ids(manifests), shipped_dirs(manifests))
    tested, bad_tested = sort_tested(data, manifests)
    for line in bad + bad_tested + notes:
        log.info("catalogue: left out %s", line)
    out = dict(data)
    out["demos"] = keep
    out["tested_updates"] = tested
    return out


def needs_newer(entry, engine=ENGINE):
    """Does this entry need a newer RasQberry than this image?"""
    me = entry.get("min_engine", 1)
    return isinstance(me, int) and me > engine


def release_pin(manifest, kind):
    """A shipped demo's release pin of KIND ('image' or 'ref'), '' if it has none."""
    if not isinstance(manifest, dict):
        return ""
    if kind == "image":
        ep = manifest.get("entrypoint") if isinstance(manifest.get("entrypoint"), dict) else {}
        v = ep.get("docker_image")
    else:
        inst = manifest.get("install") if isinstance(manifest.get("install"), dict) else {}
        src = inst.get("source") if isinstance(inst.get("source"), dict) else {}
        v = inst.get("ref") or src.get("ref")
    return v if isinstance(v, str) else ""


def _pin_problem(pin, kind, repo):
    """Why PIN cannot be a KIND pin of the image REPO ('' if it can)."""
    if not isinstance(pin, str):
        return "is not a text"
    if kind == "ref":
        return "" if SHA_RE.match(pin) else "is not a full commit SHA"
    m = IMAGE_RE.match(pin)
    if not m:
        return "is not an image digest (repository@sha256:...)"
    return "" if m.group(1) == repo else f"is not an image of {repo}"


def tested_problems(t, label, manifests=None):
    """
    Why one tested update cannot be used on this image (empty: it can).

    Args:
        t (dict): the entry of "tested_updates"
        label (str): how the lines name it
        manifests (str): the image's manifest directory
    """
    did, kind = t.get("id"), t.get("kind")
    if not isinstance(did, str) or not ID_RE.match(did):
        return [f"{label}: id is not kebab-case"]
    if kind not in ("image", "ref"):
        return [f"{label}: kind is not image or ref"]
    m = _read_json(os.path.join(manifests or manifest_dir(), f"rq_demo_{did}.json"))
    rel = release_pin(m, kind)
    if not rel:
        return [f"{label}: not a demo this image ships with a {kind} pin"]
    repo = rel.split("@", 1)[0] if kind == "image" else ""
    out = []
    why = _pin_problem(t.get("pin"), kind, repo)
    if why:
        out.append(f"{label}: pin {why}")
    frm = t.get("from")
    if not isinstance(frm, list) or not frm:
        out.append(f"{label}: from is not a list of release pins")
    else:
        for f in frm:
            why = _pin_problem(f, kind, repo)
            if why:
                out.append(f"{label}: from {why}")
                break
    for key, limit in TESTED_TEXTS.items():
        v = t.get(key)
        if v is None and key != "label":
            continue
        if not isinstance(v, str) or not v or len(v) > limit or CONTROL_RE.search(v):
            out.append(f"{label}: {key} is not a one-line text of at most {limit} characters")
    dl = t.get("download_mb")
    if dl is not None and (not isinstance(dl, int) or isinstance(dl, bool) or dl < 0):
        out.append(f"{label}: download_mb is not a whole number of MB")
    return out


def sort_tested(data, manifests=None):
    """
    The tested updates a Pi with this image takes, and the lines on the
    others. An update for a demo this image does not ship (or ships without
    that kind of pin) is left out without a problem: it is for another image.

    Returns:
        tuple: (entries, problems)
    """
    items = data.get("tested_updates", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return [], ["tested_updates is not a list"]
    keep, bad, seen = [], [], set()
    for i, t in enumerate(items):
        if not isinstance(t, dict):
            bad.append(f"tested_updates {i}: not an object")
            continue
        label = f"tested_updates {t.get('id')}:{t.get('kind')}"
        found = tested_problems(t, label, manifests)
        if (t.get("id"), t.get("kind")) in seen:
            found.append(f"{label}: appears twice")
        seen.add((t.get("id"), t.get("kind")))
        if found and "not a demo this image ships" in found[0]:
            continue
        if found:
            bad.extend(found)
        else:
            keep.append(t)
    return keep, bad


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
    if isinstance(cached, dict) and version(cached) > version(base):
        sound = usable(cached, manifests)
        if sound is not None:
            return sound, cache_path
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
    bad = file_problems(data)
    if bad:
        return "rejected", "; ".join(bad[:5])
    have, _ = current(shipped, cache, manifests)
    if version(data) <= version(have):
        return "unchanged", f"version {version(data)} (in use: {version(have)})"
    # only the entries this image takes: the shell reads the file as it is
    sound = usable(data, manifests)
    left = len(data["demos"]) - len(sound["demos"])
    try:
        _write_atomic(os.path.join(cache, CACHE_NAME), json.dumps(sound, indent=1) + "\n")
    except OSError as e:
        return "offline", f"cannot keep it: {e}"
    return "updated", f"version {version(data)}" + (f", {left} entries left out" if left else "")


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


def added_by_catalogue(manifest, checkout):
    """
    Did the add-flow install this demo? Its manifest has MARK; older
    add-flows left only their bare pinned checkout (git init, fetch the pin,
    detached: no remote). A hand-written test manifest (CONTRIBUTING.md,
    a git clone with its origin) is neither.
    """
    if isinstance(manifest.get(MARK), dict):
        return True
    git = os.path.join(checkout, ".git")
    try:
        with open(os.path.join(git, "HEAD")) as f:
            head = f.read().strip()
        with open(os.path.join(git, "config")) as f:
            config = f.read()
    except OSError:
        return False
    return bool(SHA_RE.match(head)) and "[remote " not in config


def installed(home=None, repo=None):
    """
    The demos in the user's manifest directory: {id: {name, head, catalogue}}.
    The add-flow copies the manifests of catalogue demos there (catalogue
    True); a demo author's test manifest is there too (catalogue False).
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
        if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not ID_RE.match(m["id"]):
            continue        # (its id goes into a command line: kebab-case only)
        ep = m.get("entrypoint") if isinstance(m.get("entrypoint"), dict) else {}
        wd = ep.get("working_dir") or ""
        ok = isinstance(wd, str) and DIR_RE.match(wd)
        checkout = os.path.join(home, repo, "demos", wd) if ok else ""
        out[m["id"]] = {"name": clean_text(m.get("name") or m["id"]),
                        "head": checkout_head(checkout) if ok else "",
                        "catalogue": added_by_catalogue(m, checkout) if ok else isinstance(m.get(MARK), dict)}
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
        if not info.get("catalogue"):
            continue        # not from the catalogue: a demo author's own manifest
        entry = by_id.get(did)
        if entry is None:
            succ = next((d for d in demos if did in (d.get("replaces") or [])), None)
            if succ is not None:
                replaced.add(succ.get("id"))
                if not needs_newer(succ, engine) and succ.get("id") not in have:
                    out.append({"kind": "renamed", "id": did, "name": clean_text(info["name"]),
                                "new": succ["id"], "new_name": clean_text(succ.get("name") or succ["id"]),
                                "key": f"renamed:{did}:{succ['id']}"})
            elif did not in shipped_ids():
                out.append({"kind": "withdrawn", "id": did, "name": clean_text(info["name"]),
                            "key": f"withdrawn:{did}"})
            continue
        if info["head"] and info["head"] != entry.get("ref") and not needs_newer(entry, engine):
            out.append({"kind": "update", "id": did, "name": clean_text(entry.get("name") or info["name"]),
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
            out.append({"kind": "new", "id": did, "name": clean_text(d.get("name") or did),
                        "provider": clean_text(d.get("provider") or "", 120),
                        "summary": clean_text(d.get("summary") or "", 200),
                        "key": f"new:{did}"})
    return out


def demo_versions(home=None, repo=None):
    """demos/.demo-versions (rq_common.sh): {key: (release pin, chosen, label)}."""
    home = home or user_home()
    repo = repo or os.environ.get("REPO") or "RasQberry-Two"
    out = {}
    try:
        with open(os.path.join(home, repo, "demos", ".demo-versions"), encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3 and parts[2]:
                    out[parts[0]] = (parts[1], parts[2], parts[3] if len(parts) > 3 else "")
    except OSError:
        pass
    return out


def docker_has(image):
    """Is IMAGE downloaded? False when Docker cannot be asked (no access, not running)."""
    try:
        return subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", image],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def tested_for(catalogue, did, kind, manifests=None, home=None, repo=None, has_image=docker_has):
    """
    The tested update of one demo for this Pi, or None.

    Returns:
        dict: the entry, plus "name", "current" (the version in use) and
        "release" (the release pin)
    """
    entry = next((t for t in catalogue.get("tested_updates") or []
                  if isinstance(t, dict) and t.get("id") == did and t.get("kind") == kind), None)
    if entry is None or tested_problems(entry, did, manifests):
        return None
    m = _read_json(os.path.join(manifests or manifest_dir(), f"rq_demo_{did}.json"))
    rel = release_pin(m, kind)
    if rel not in entry["from"]:
        return None
    chosen = demo_versions(home, repo).get(f"{did}:{kind}")
    cur = rel
    if chosen and chosen[0] == rel:
        if not chosen[2].startswith(TESTED_LABEL):
            return None     # a version chosen by hand: the user's call
        cur = chosen[1]
    if cur == entry["pin"]:
        return None
    # downloaded: the checkout, or the image in use
    if kind == "ref":
        ep = m.get("entrypoint") if isinstance(m.get("entrypoint"), dict) else {}
        wd = ep.get("working_dir") or ""
        home = home or user_home()
        repo = repo or os.environ.get("REPO") or "RasQberry-Two"
        if not (isinstance(wd, str) and DIR_RE.match(wd)
                and os.path.isdir(os.path.join(home, repo, "demos", wd, ".git"))):
            return None
    elif not has_image(cur):
        return None
    return dict(entry, name=clean_text(m.get("name") or did), current=cur, release=rel)


def tested_news(catalogue, manifests=None, home=None, repo=None, has_image=docker_has):
    """The tested updates for this Pi's downloaded demos (news items, kind 'tested')."""
    out = []
    seen = set()
    for t in catalogue.get("tested_updates") or []:
        if not isinstance(t, dict) or (t.get("id"), t.get("kind")) in seen:
            continue
        seen.add((t.get("id"), t.get("kind")))
        hit = tested_for(catalogue, t.get("id"), t.get("kind"), manifests, home, repo, has_image)
        if hit:
            out.append({"kind": "tested", "id": hit["id"], "name": hit["name"],
                        "update": hit["kind"], "label": clean_text(hit["label"], 60),
                        "key": f"tested:{hit['id']}:{hit['kind']}:{hit['pin']}"})
    return out


def all_news(catalogue=None, base=None):
    """news() and tested_news() for this user: what the badge, the notice and the login line show."""
    if catalogue is None:
        catalogue = current()[0]
    if base is None:
        base = _read_json(shipped_file()) or {}
    return news(catalogue, base, installed()) + tested_news(catalogue)


def popup_text(item):
    """The one-time desktop notice for one news item."""
    k, name = item["kind"], item["name"]
    if k == "new":
        by = f" by {item['provider']}" if item.get("provider") else ""
        return (f"New in the demo catalogue: {name}{by}. Add it from the RasQberry "
                f"badge in the taskbar, or the RasQberry menu (Quantum Demos > Manage demos).")
    if k == "update":
        return f"An update for {name} is available. Install it from the RasQberry badge in the taskbar."
    if k == "tested":
        return (f"A tested update for {name} is available ({item['label']}). Install it from "
                f"the RasQberry badge in the taskbar.")
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
    if k in ("update", "tested"):
        return f"Update {name}…"
    if k == "renamed":
        return f"Move {name} to {item['new_name']}…"
    return f"Remove {name} (withdrawn)…"


def program(item):
    """The script that acts on a news item."""
    return "rq_demo_update.sh" if item["kind"] == "tested" else "rq_demo_add_external.sh"


def command(item):
    """The arguments of program(item) that act on a news item."""
    k = item["kind"]
    if k == "tested":
        return ["--tested", f"{item['id']}:{item['update']}"]
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
        parts.append(f"{len(act)} demo{'s' if len(act) > 1 else ''} to update: "
                     + ", ".join(f"sudo {program(i)} {' '.join(command(i))}" for i in act))
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
        bad = problems(data, shipped_ids(), shipped_dirs())
        for line in bad:
            print(line)
        if not bad:
            for line in sort_entries(data, shipped_ids(), shipped_dirs())[2]:
                print(f"Note: {line}")
            print(f"OK: catalogue_version {version(data)}, {len(data['demos'])} demos")
        return 1 if bad else 0
    if argv[0] == "--refresh":
        status, text = refresh()
        print(f"Demo catalogue: {status} ({text})")
        if "--system" in argv:
            line = login_line(all_news())
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
    if argv[0] == "--tested":
        did, _, kind = (argv[1] if len(argv) > 1 else "").partition(":")
        hit = tested_for(cat, did, kind, has_image=lambda image: True)
        if not hit:
            return 1
        print(f"{hit['pin']}\t{clean_text(hit['label'], 60)}\t{hit.get('download_mb', 0)}")
        return 0
    if argv[0] in ("--news", "--line"):
        items = all_news(cat)
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
