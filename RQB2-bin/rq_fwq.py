#!/usr/bin/env python3
"""
Fun with Quantum on RasQberry Two: the offline website and the family page.

The Fun-with-Quantum repository publishes every build of its website as
fwq-portal-<commit>.tar.gz (+ .sha256) on the "portal-bundles" release. Only
commits that change the website have one, so the manifest pins the website
separately from the notebooks: install.portal_ref (a commit with a bundle) and
install.portal_sha256 (optional; else the published .sha256 is used). Empty
portal_ref: no local copy, the menu entry opens the online website.

The demo engine runs this script after it has fetched the notebooks
(install.post_install, as "rq_fwq.py --path DIR"): it downloads the pinned
bundle, checks its SHA-256 and unpacks it into DIR/portal/dist, and it writes
the family page from DIR/family/family.json (the notebook pin). No step needs
the network when the pages are viewed.

Usage:
    rq_fwq.py --path DIR                      post-install: website + family page
    rq_fwq.py portal --path DIR               download the pinned website (2: none)
    rq_fwq.py portal-state --path DIR         current | download | none
    rq_fwq.py family-page --path DIR [--out FILE]
    rq_fwq.py family-menu --path DIR          menu items: tag<TAB>label<TAB>action
"""

import argparse
import hashlib
import html
import io
import json
import logging
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("rq_fwq")

REPO = "JanLahmann/Fun-with-Quantum"
RELEASE_TAG = "portal-bundles"
SITE_URL = "https://fun-with-quantum.org"
SITE_SUBDIR = os.path.join("portal", "dist")
FAMILY_JSON = os.path.join("family", "family.json")
FAMILY_PAGE = "rasqberry-family.html"
PORTAL_STAMP = os.path.join("portal", ".rasqberry-portal-ref")
DEMO_ID = "fun-with-quantum"
MAX_BUNDLE_BYTES = 200 * 1000 * 1000

# Family members that are RasQberry demos: family id -> demo id
FAMILY_DEMOS = {
    "fun-with-quantum": "fun-with-quantum",
    "qoffee-maker": "qoffee-maker",
    "qubins": "quantum-lab",
    "doqumentation": "doqumentation",
    "racetraq": "racetraq",
}
THIS_PI = "rasqberry-two"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HEX256_RE = re.compile(r"^[0-9a-f]{64}$")


class BundleMissing(Exception):
    """The release has no bundle for this commit (yet)."""


class BundleError(Exception):
    """The bundle could not be downloaded, verified or unpacked."""


def bundle_name(commit):
    """
    File name of the website bundle for a commit.

    Args:
        commit (str): Full 40-character commit SHA.

    Returns:
        str: fwq-portal-<commit>.tar.gz
    """
    commit = (commit or "").strip().lower()
    if not _SHA_RE.match(commit):
        raise ValueError("not a full commit SHA: %r" % commit)
    return "fwq-portal-%s.tar.gz" % commit


def bundle_urls(commit, repo=REPO, tag=RELEASE_TAG):
    """
    Download URLs of a commit's bundle and its checksum file.

    Args:
        commit (str): Full commit SHA.
        repo (str): GitHub owner/name.
        tag (str): Release tag that holds the bundles.

    Returns:
        tuple: (bundle URL, .sha256 URL)
    """
    url = "https://github.com/%s/releases/download/%s/%s" % (repo, tag, bundle_name(commit))
    return url, url + ".sha256"


def parse_sha256(text, name):
    """
    The hash from a sha256sum line ("<hex>  <name>" or "<hex>").

    Args:
        text (str): Contents of the .sha256 file.
        name (str): Expected file name, when the line names one.

    Returns:
        str: The 64-digit hex hash.
    """
    for line in (text or "").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        digest = parts[0].lower()
        listed = parts[1].lstrip("*") if len(parts) > 1 else name
        if _HEX256_RE.match(digest) and os.path.basename(listed) == name:
            return digest
    raise BundleError("no SHA-256 for %s in the checksum file" % name)


def _get(url, opener=None, limit=MAX_BUNDLE_BYTES):
    """Fetch a URL into memory; a 404 means the bundle is not published."""
    opener = opener or urllib.request.urlopen
    try:
        with opener(url, timeout=60) as resp:
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BundleMissing(url) from exc
        raise BundleError("%s: HTTP %s" % (url, exc.code)) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise BundleError("%s: %s" % (url, exc)) from exc
    if len(data) > limit:
        raise BundleError("%s is larger than expected" % url)
    return data


def _safe_extract(data, dest):
    """Unpack a .tar.gz into dest, refusing links and paths outside it."""
    root = os.path.realpath(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            target = os.path.realpath(os.path.join(root, m.name))
            if not (m.isfile() or m.isdir()):
                raise BundleError("unexpected entry in the bundle: %s" % m.name)
            if target != root and not target.startswith(root + os.sep):
                raise BundleError("path outside the bundle: %s" % m.name)
        for m in members:
            m.mode = 0o755 if m.isdir() else 0o644
            m.uid = m.gid = 0
            m.uname = m.gname = ""
        if hasattr(tarfile, "data_filter"):
            tar.extractall(root, members=members, filter="data")
        else:  # pragma: no cover - Python without extraction filters
            tar.extractall(root, members=members)


def bundle_published(commit, opener=None):
    """
    Is the commit's bundle on the release? (Short request for the .sha256.)

    Args:
        commit (str): Full commit SHA.
        opener (callable): urlopen replacement for tests.

    Returns:
        bool: True if it can be downloaded now.
    """
    try:
        _get(bundle_urls(commit)[1], opener, limit=4096)
        return True
    except (BundleMissing, BundleError):
        return False


def fetch_portal(path, commit, opener=None, sha256=""):
    """
    Download, verify and unpack the website of a commit into path/portal/dist.

    The old copy is replaced only when the new one is complete.

    Args:
        path (str): Demo directory.
        commit (str): Full commit SHA.
        opener (callable): urlopen replacement for tests.
        sha256 (str): Pinned hash; empty = use the published .sha256.

    Returns:
        str: The directory the website is in.
    """
    url, sha_url = bundle_urls(commit)
    name = bundle_name(commit)
    if sha256:
        expected = sha256.strip().lower()
        if not _HEX256_RE.match(expected):
            raise BundleError("pinned SHA-256 is not 64 hex digits")
    else:
        expected = parse_sha256(_get(sha_url, opener, limit=4096).decode("utf-8", "replace"), name)
    data = _get(url, opener)
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise BundleError("SHA-256 mismatch for %s" % name)
    site = os.path.join(path, SITE_SUBDIR)
    os.makedirs(os.path.dirname(site), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".dist-", dir=os.path.dirname(site))
    try:
        _safe_extract(data, tmp)
        if not os.path.isfile(os.path.join(tmp, "index.html")):
            raise BundleError("%s has no index.html" % name)
        os.chmod(tmp, 0o755)
        if os.path.isdir(site):
            shutil.rmtree(site)
        os.rename(tmp, site)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    with open(os.path.join(path, PORTAL_STAMP), "w", encoding="utf-8") as fh:
        fh.write(commit.lower() + "\n")
    return site


def portal_pin(manifest):
    """
    The website pin of the manifest: (commit, sha256), "" when not set.

    Args:
        manifest (dict): Parsed rq_demo_fun-with-quantum.json.

    Returns:
        tuple: (portal_ref, portal_sha256), lower case; invalid values count as unset.
    """
    inst = manifest.get("install", {}) if isinstance(manifest, dict) else {}
    ref = str(inst.get("portal_ref") or "").strip().lower()
    sha = str(inst.get("portal_sha256") or "").strip().lower()
    return (ref if _SHA_RE.match(ref) else "", sha if _HEX256_RE.match(sha) else "")


def portal_state(path, ref, opener=None):
    """
    What the website needs: "current", "download" or "none".

    Args:
        path (str): Demo directory.
        ref (str): Pinned website commit ("" = none pinned).
        opener (callable): urlopen replacement for tests.

    Returns:
        str: "current" (the pinned copy is here), "download" (it is published
        and not here), "none" (nothing pinned, or not published).
    """
    if not ref:
        return "none"
    try:
        with open(os.path.join(path, PORTAL_STAMP), encoding="utf-8") as fh:
            stamp = fh.read().strip()
    except OSError:
        stamp = ""
    if stamp == ref and os.path.isfile(os.path.join(path, SITE_SUBDIR, "index.html")):
        return "current"
    return "download" if bundle_published(ref, opener=opener) else "none"


# ----------------------------------------------------------------------------
# Family page and menu
# ----------------------------------------------------------------------------

def manifest_dirs(script_dir=None, home=None):
    """
    Where demo manifests live: the shipped directory and the user's.

    Args:
        script_dir (str): Directory of this script (default: its own).
        home (str): The user's home (default: USER_HOME or HOME).

    Returns:
        list: Existing directories.
    """
    script_dir = script_dir or os.path.dirname(os.path.abspath(__file__))
    home = home or os.environ.get("USER_HOME") or os.path.expanduser("~")
    if script_dir == "/usr/bin":
        shipped = "/usr/config/demo-manifests"
    else:
        shipped = os.path.join(os.path.dirname(script_dir), "RQB2-config", "demo-manifests")
    dirs = [shipped, os.path.join(home, ".local", "config", "demo-manifests")]
    return [d for d in dirs if os.path.isdir(d)]


def local_demo_ids(dirs):
    """
    Ids of the demos this Pi knows (shipped or added from the catalogue).

    Args:
        dirs (list): Manifest directories.

    Returns:
        set: Demo ids.
    """
    ids = set()
    for d in dirs:
        for f in sorted(os.listdir(d)):
            if not (f.startswith("rq_demo_") and f.endswith(".json")) or f == "rq_demo_schema.json":
                continue
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    ids.add(json.load(fh).get("id", ""))
            except (OSError, ValueError, AttributeError):
                continue
    ids.discard("")
    return ids


def find_manifest(dirs, demo_id=DEMO_ID):
    """
    The manifest of a demo in the manifest directories (shipped first).

    Args:
        dirs (list): Manifest directories.
        demo_id (str): Demo id.

    Returns:
        dict: Parsed manifest, or {} when there is none.
    """
    for d in dirs:
        try:
            with open(os.path.join(d, "rq_demo_%s.json" % demo_id), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("id") == demo_id:
            return data
    return {}


def family_members(family, local_ids):
    """
    The members to show, each with what this Pi can do with it.

    Members with "footer": false are not shown yet (as on the websites).

    Args:
        family (dict): Parsed family.json.
        local_ids (set): Demo ids on this Pi.

    Returns:
        list: dicts with id, name, url (https or ""), text, short, demo (demo id
        or ""), this_pi (bool).
    """
    out = []
    for m in family.get("members", []):
        if not isinstance(m, dict) or m.get("footer") is False:
            continue
        mid = str(m.get("id", ""))
        url = str(m.get("url", ""))
        demo = FAMILY_DEMOS.get(mid, "")
        out.append({
            "id": mid,
            "name": str(m.get("name", mid)),
            "url": url if url.startswith("https://") else "",
            "text": str(m.get("tagline") or m.get("short") or ""),
            "short": str(m.get("short") or m.get("tagline") or ""),
            "demo": demo if demo in local_ids else "",
            "this_pi": mid == THIS_PI,
        })
    return out


_CSS = """
:root{--bg:#f6f6f8;--card:#fff;--fg:#1d1d24;--mute:#5b5b66;--line:#dcdce3;--acc:#6929c4;--ok:#0e6027;--okbg:#defbe6}
@media (prefers-color-scheme:dark){:root{--bg:#16161b;--card:#22222a;--fg:#eeeef2;--mute:#a8a8b3;--line:#3a3a45;--acc:#be95ff;--ok:#a7f0ba;--okbg:#0e3a1d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}h1{margin:0 0 4px;font-size:1.7rem}
p.lead{color:var(--mute);margin:0 0 20px}ul{list-style:none;padding:0;margin:0;display:grid;gap:12px}
li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
h2{font-size:1.1rem;margin:0 0 4px}h2 a{color:var(--acc)}p{margin:0}
.tag{display:inline-block;font-size:.8rem;border-radius:999px;padding:1px 10px;margin:8px 8px 0 0;border:1px solid var(--line);color:var(--mute)}
.tag.pi{background:var(--okbg);color:var(--ok);border-color:transparent;font-weight:600}
"""


def render_family_html(family, local_ids):
    """
    The family page: every member with its description and what works offline.

    Args:
        family (dict): Parsed family.json.
        local_ids (set): Demo ids on this Pi.

    Returns:
        str: A self-contained HTML page (no network needed to show it).
    """
    esc = html.escape
    brand = family.get("brand", {}) if isinstance(family.get("brand"), dict) else {}
    title = "%s family" % brand.get("name", "Fun with Quantum")
    items = []
    for m in family_members(family, local_ids):
        name = esc(m["name"])
        head = '<a href="%s">%s</a>' % (esc(m["url"]), name) if m["url"] else name
        tags = []
        if m["this_pi"]:
            tags.append('<span class="tag pi">You are using it</span>')
        elif m["demo"]:
            tags.append('<span class="tag pi">On this Pi</span>')
        if m["url"]:
            tags.append('<span class="tag">Website: needs internet</span>')
        items.append('<li><h2>%s</h2><p>%s</p>%s</li>' % (head, esc(m["text"]), "".join(tags)))
    return (
        '<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s</title><style>%s</style></head><body><main>"
        "<h1>%s</h1>"
        '<p class="lead">Projects marked <b>On this Pi</b> run on this RasQberry Two, without '
        "the internet once downloaded. Start them from the RasQberry menu: Quantum Demos &rarr; "
        "Play &rarr; Fun with Quantum &rarr; Fun with Quantum family. The websites need the internet.</p>"
        "<ul>%s</ul></main></body></html>\n"
    ) % (esc(title), _CSS, esc(title), "\n".join(items))


def menu_items(family, local_ids):
    """
    Entries for the family menu: the page, then each member.

    Args:
        family (dict): Parsed family.json.
        local_ids (set): Demo ids on this Pi.

    Returns:
        list: (tag, label, action) with action "page", "demo:<id>" or "url:<url>".
    """
    local, web = [], []
    for m in family_members(family, local_ids):
        if m["id"] == "fun-with-quantum":
            continue  # the menu this one is opened from
        label = "%s: %s" % (m["name"], m["short"])
        if m["demo"]:
            local.append((m["id"], label + " (on this Pi)", "demo:" + m["demo"]))
        elif m["url"]:
            suffix = " (this Pi)" if m["this_pi"] else " (website, needs internet)"
            web.append((m["id"], label + suffix, "url:" + m["url"]))
    items = [("page", "About the family (page, works offline)", "page")] + local + web
    return [(t, l.replace("\t", " ").replace("\n", " "), a) for t, l, a in items]


def load_family(path):
    """
    Read family.json from the demo checkout.

    Args:
        path (str): Demo directory.

    Returns:
        dict: Parsed family.json.
    """
    with open(os.path.join(path, FAMILY_JSON), encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("family.json is not an object")
    return data


def write_family_page(path, out=None):
    """
    Write the family page into the demo directory.

    Args:
        path (str): Demo directory.
        out (str): Output file (default: path/rasqberry-family.html).

    Returns:
        str: The file written.
    """
    out = out or os.path.join(path, FAMILY_PAGE)
    page = render_family_html(load_family(path), local_demo_ids(manifest_dirs()))
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(page)
    os.replace(tmp, out)
    return out


def _pin(args):
    """The website pin: command-line overrides, else the manifest."""
    ref, sha = portal_pin(find_manifest(manifest_dirs()))
    if args.ref is not None:
        ref, sha = args.ref.strip().lower(), (args.sha256 or "").strip().lower()
    return ref, sha


def _portal(path, ref, sha256):
    """Download the pinned website; 2 = none pinned or not published."""
    if not ref:
        logger.info("No Fun with Quantum website is pinned for offline use; "
                    "the menu entry opens fun-with-quantum.org.")
        return 2
    try:
        site = fetch_portal(path, ref, sha256=sha256)
    except (BundleMissing, ValueError):
        logger.info("The Fun with Quantum website %s is not published.", ref[:7])
        return 2
    except (BundleError, OSError) as exc:
        logger.warning("The Fun with Quantum website could not be downloaded: %s", exc)
        return 1
    logger.info("Fun with Quantum website saved for offline use: %s", site)
    return 0


def main(argv=None):
    """
    Command-line entry point.

    Args:
        argv (list): Arguments (default: sys.argv[1:]).

    Returns:
        int: Exit status.
    """
    p = argparse.ArgumentParser(description="Fun with Quantum: offline website and family page")
    p.add_argument("command", nargs="?", default="setup",
                   choices=["setup", "portal", "portal-state", "family-page", "family-menu"])
    p.add_argument("--path", required=True, help="the fun-with-quantum demo directory")
    p.add_argument("--out", help="family-page: output file")
    p.add_argument("--ref", help="portal: website commit instead of install.portal_ref")
    p.add_argument("--sha256", help="portal: its SHA-256 (with --ref)")
    args = p.parse_args(argv)
    path = os.path.abspath(args.path)

    if args.command == "portal":
        return _portal(path, *_pin(args))
    if args.command == "portal-state":
        print(portal_state(path, _pin(args)[0]))
        return 0
    if args.command == "family-page":
        print(write_family_page(path, args.out))
        return 0
    if args.command == "family-menu":
        for item in menu_items(load_family(path), local_demo_ids(manifest_dirs())):
            print("\t".join(item))
        return 0
    # setup (post-install): neither step may fail the notebook install
    _portal(path, *_pin(args))
    try:
        write_family_page(path)
    except (OSError, ValueError) as exc:
        logger.warning("The family page could not be written: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
