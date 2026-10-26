#!/usr/bin/env python3
"""
QuBins (beta): the image list, the content mounts and the last choices.

rq_qubins.sh asks which QuBins image to run and what to put into the lab.
This helper does the parts that are easier to test in Python:

  images    the QuBins images to offer, one tab-separated line each:
                REF  TAG  QISKIT  VARIANT  DATE  DOWNLOAD_MB  MARKS
            REF is "ghcr.io/qubins/images@sha256:..." (the multi-platform
            index, as the manifest pins it). MARKS: comma-separated "tested"
            (the release pin), "downloaded" (on this Pi), "in-use" (the image
            QuBins ran last), or "-". The tested image comes first, then the
            newest Qiskit versions, xl before small. Only QuBins' monthly
            snapshot tags (2.6-xl-20261020: kept for a year) are offered,
            never a moving tag or a nightly build: the newest snapshot of
            each Qiskit minor version (the newest --minors of them) and
            variant. xxl is left out (on arm64 it equals xl, QuBins README),
            and so is the retiring 2.1-xl-rise.
            Bounded: a short timeout per request, and a list read in the
            last --max-age seconds (--cache) is used without the network.
            Without the registry the cached list (any age) is used, else
            only the tested image (and the one in use); exit status 2 then.
  mounts    the docker run -v arguments for the chosen content, one per
            line: my-work (writable, always), the welcome page, the Pi's
            JupyterLab settings and a start hook that hides the image's own
            empty "work" folder (read-only), and each chosen notebook
            collection at the same place under /home/jovyan as under
            ~/RasQberry-Two/demos, so the notebooks' relative links and
            pictures work: the user's own copy (writable, from --copies),
            with the untouched original read-only under originals/; pictures
            and the licence stay the originals, read-only. The IBM tutorials
            and courses come from one checkout (ibm-quantum-learning): only
            the chosen part is mounted. Content that is not on the Pi is
            left out (a note on stderr).
  prepare   make the user's copies of the chosen content in --copies
            (~/RasQberry-Two/work/qubins), on first use: notebooks and other
            text files copied, anything else hard-linked to the original (no
            space). A copy is never overwritten: when the original is newer
            (Update demos), one note says so, once.
  reset     back to the original: the copies of the given content are made
            again; nothing of the user's changes in them is kept. my-work is
            never touched.
  copies    the content ids that have a copy (for the Reset dialog).
  last      the last choices (a JSON state file): "IMAGE<TAB>LABEL<TAB>CONTENT"
            with CONTENT comma-separated demo ids; exit 1 when there are none.
  remember  write the last choices.

Content ids are the demo ids: ibm-tutorials, ibm-courses, quantum-paradoxes,
fun-with-quantum.

Environment (tests): RQ_QUBINS_REGISTRY_FILE, a JSON file that stands in for
ghcr.io: {"tags": [...], "manifests": {REF: {"digest": D, "body": {...}}},
"blobs": {DIGEST: {...}}}.

Only the Python standard library is used (and rq_image_versions.py, next to
this file).
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rq_image_versions as riv  # noqa: E402

REPO = "qubins/images"
IMAGE = "ghcr.io/" + REPO
ARCH = "arm64"
# A monthly snapshot tag: 2.6-xl-20261020
SNAPSHOT = re.compile(r"^(\d+)\.(\d+)-([a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*)-(20\d{6})$")
VARIANTS = ("xl", "small")
REQUEST_TIMEOUT = 8

CONTAINER_HOME = "/home/jovyan"
ORIGINALS = "originals"
HIDE_WORK_HOOK = "/usr/local/bin/before-notebook.d/90-rasqberry-hide-work.sh"
IBM_DIR = "ibm-quantum-learning"
# What each content choice brings, relative to the demos folder: "copy"
# becomes the user's own, editable copy; "assets" (pictures, licence) stay
# the originals, read-only
CONTENT = {
    "ibm-tutorials": {
        "copy": [f"{IBM_DIR}/WELCOME-tutorials.ipynb", f"{IBM_DIR}/docs/tutorials",
                 f"{IBM_DIR}/docs/guides"],
        "assets": [f"{IBM_DIR}/public/docs/images"],
    },
    "ibm-courses": {
        "copy": [f"{IBM_DIR}/WELCOME-courses.ipynb", f"{IBM_DIR}/learning/courses"],
        "assets": [f"{IBM_DIR}/public/learning/images/courses"],
    },
    "quantum-paradoxes": {"copy": ["quantum-paradoxes"], "assets": []},
    "fun-with-quantum": {"copy": ["fun-with-quantum"], "assets": []},
}
# With either IBM part: the credentials notebook (copied once, never reset)
# and the licence
IBM_SHARED = {"copy": [f"{IBM_DIR}/00-Save-Credentials.ipynb"],
              "assets": [f"{IBM_DIR}/LICENSE-DOCS"]}
# Copied (the user edits them); any other file is hard-linked to the
# original (no space taken) or, on another file system, copied too
TEXT_SUFFIXES = {".ipynb", ".md", ".txt", ".py", ".json", ".csv", ".yaml", ".yml", ".qasm",
                 ".tex", ".rst", ".cfg", ".toml", ".ini", ".html", ".js", ".css", ""}
SKIP_NAMES = {".git", ".rasqberry-converted", "__pycache__", ".ipynb_checkpoints"}
COPIES_STATE = ".qubins-copies.json"


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------

class FileRegistry:
    """Registry answers from a JSON file (tests): same methods as riv.Registry."""

    def __init__(self, path):
        with open(path, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def tags(self):
        return list(self.data.get("tags") or [])

    def manifest(self, ref):
        entry = (self.data.get("manifests") or {}).get(ref)
        if entry is None:
            raise urllib.error.HTTPError(ref, 404, "manifest unknown", None, None)
        return entry.get("digest", ref), entry["body"]

    def blob(self, digest):
        blob = (self.data.get("blobs") or {}).get(digest)
        if blob is None:
            raise urllib.error.HTTPError(digest, 404, "blob unknown", None, None)
        return blob


def parse_tag(tag):
    """
    (major, minor, variant, YYYYMMDD) of a snapshot tag, else None.

    >>> parse_tag("2.6-xl-20261020")
    (2, 6, 'xl', '20261020')
    """
    m = SNAPSHOT.match(tag or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)


def snapshot_candidates(tags, variants=VARIANTS, minors=4):
    """
    The tags to offer: the newest snapshot of each (Qiskit minor, variant),
    for the newest MINORS Qiskit minor versions; newest version first, then
    in the order of VARIANTS.
    """
    best = {}
    for tag in tags:
        p = parse_tag(tag)
        if not p or p[2] not in variants:
            continue
        key = (p[0], p[1], p[2])
        if key not in best or p[3] > best[key][0]:
            best[key] = (p[3], tag)
    versions = sorted({(k[0], k[1]) for k in best}, reverse=True)[:max(minors, 1)]
    keys = [k for k in best if (k[0], k[1]) in versions]
    keys.sort(key=lambda k: (-k[0], -k[1], variants.index(k[2])))
    return [best[k][1] for k in keys]


def _date_of(tag, created=""):
    if created:
        return created[:10]
    p = parse_tag(tag)
    if p:
        return f"{p[3][:4]}-{p[3][4:6]}-{p[3][6:]}"
    return "-"


def entry_for(tag, facts):
    """One list entry from a tag and riv.describe()'s facts."""
    p = parse_tag(tag)
    return {
        "ref": f"{IMAGE}@{facts['digest']}",
        "tag": tag,
        "qiskit": facts.get("qiskit") or (f"{p[0]}.{p[1]}" if p else "-"),
        "variant": p[2] if p else "-",
        "date": _date_of(tag, facts.get("created", "")),
        "mb": int(facts.get("download_mb") or 0),
    }


def read_registry(reg, minors):
    """The entries for the candidate tags (a vanished tag is left out)."""
    tags = snapshot_candidates(reg.tags(), minors=minors)

    def one(tag):
        try:
            facts = riv.describe(reg, tag, ARCH)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        return entry_for(tag, facts) if facts else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        found = list(pool.map(one, tags))
    return [e for e in found if e]


def _version_key(entry):
    nums = tuple(int(n) for n in re.findall(r"\d+", entry.get("qiskit") or ""))
    p = parse_tag(entry.get("tag", ""))
    variant = entry.get("variant", "")
    vrank = VARIANTS.index(variant) if variant in VARIANTS else len(VARIANTS)
    return (nums or ((p[0], p[1]) if p else ()), -vrank, entry.get("date", ""))


def build_list(entries, pin_ref, pin_tag="", pin_mb=0, in_use="", in_use_label="",
               local_digests=()):
    """
    The list to show: the tested image (the release pin) first, then the
    others, newest Qiskit version first. The pin and the image in use are
    always there, also when the registry listing lacks them (offline,
    pruned). Each entry gets its marks.
    """
    local = {d.strip() for d in local_digests if d and d.strip()}
    by_ref = {}
    for e in entries:
        by_ref.setdefault(e["ref"], dict(e))

    def placeholder(ref, tag, mb=0, label=""):
        p = parse_tag(tag)
        return {
            "ref": ref, "tag": tag or label or "-",
            "qiskit": f"{p[0]}.{p[1]}" if p else "-",
            "variant": p[2] if p else "-",
            "date": _date_of(tag), "mb": int(mb or 0),
        }

    if pin_ref and pin_ref not in by_ref:
        by_ref[pin_ref] = placeholder(pin_ref, pin_tag, pin_mb)
    if in_use and in_use not in by_ref:
        tag = in_use_label if parse_tag(in_use_label) else ""
        by_ref[in_use] = placeholder(in_use, tag, 0, in_use_label or "chosen earlier")

    out = []
    for ref, e in by_ref.items():
        marks = []
        if ref == pin_ref:
            marks.append("tested")
        if ref.rsplit("@", 1)[-1] in local:
            marks.append("downloaded")
        if in_use and ref == in_use:
            marks.append("in-use")
        e["marks"] = marks
        out.append(e)
    rest = sorted([e for e in out if e["ref"] != pin_ref], key=_version_key, reverse=True)
    return [e for e in out if e["ref"] == pin_ref] + rest


def format_line(e):
    return "\t".join([e["ref"], e["tag"], e["qiskit"], e["variant"], e["date"],
                      str(e["mb"]), ",".join(e["marks"]) or "-"])


def _load_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("entries"), list):
            return float(data.get("time", 0)), data["entries"]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None, None


def _save_cache(path, entries):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"time": time.time(), "entries": entries}, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def cmd_images(args):
    entries, rc = None, 0
    cached_at, cached = (None, None)
    if args.cache:
        cached_at, cached = _load_cache(args.cache)
        if cached is not None and cached_at and time.time() - cached_at < args.max_age:
            entries = cached
    if entries is None and not args.offline:
        try:
            riv.TIMEOUT = REQUEST_TIMEOUT
            if os.environ.get("RQ_QUBINS_REGISTRY_FILE"):
                reg = FileRegistry(os.environ["RQ_QUBINS_REGISTRY_FILE"])
            else:
                reg = riv.Registry(REPO)
            entries = read_registry(reg, args.minors)
            if args.cache and entries:
                _save_cache(args.cache, entries)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            print(f"The QuBins list on ghcr.io could not be read: {exc}", file=sys.stderr)
            entries = None
    if entries is None:
        rc = 2
        entries = cached or []
    local = (args.local or "").split()
    for e in build_list(entries, args.pin, args.pin_tag, args.pin_mb, args.in_use,
                        args.in_use_label, local):
        print(format_line(e))
    return rc


# ---------------------------------------------------------------------------
# mounts
# ---------------------------------------------------------------------------

def parse_content(text):
    """Known content ids from a comma/space-separated list, in a fixed order."""
    if isinstance(text, (list, tuple)):
        text = ",".join(text)
    want = set(re.split(r"[,\s]+", (text or "").strip())) - {""}
    return [c for c in CONTENT if c in want]


def _content_paths(c):
    """(copy paths, asset paths) of content C, the IBM shared files included."""
    copy, assets = list(CONTENT[c]["copy"]), list(CONTENT[c]["assets"])
    if c.startswith("ibm-"):
        copy += IBM_SHARED["copy"]
        assets += IBM_SHARED["assets"]
    return copy, assets


def mount_args(content, demos_dir, work_dir, welcome="", overrides="", copies="", hook="",
               exists=os.path.exists):
    """
    The docker run -v arguments (a flat list: "-v", "SRC:DST[:ro]", ...)
    and the notes about content that is not on this Pi.

    With COPIES (the folder of the user's copies, ~/RasQberry-Two/work/qubins)
    each chosen notebook folder is the user's copy, writable, at the same
    place as in the demos folder, and the untouched original is read-only
    in originals/; without it, the originals are mounted read-only. HOOK:
    a start hook of the image that hides its own empty "work" folder.
    """
    args = ["-v", f"{work_dir}:{CONTAINER_HOME}/my-work"]
    notes = []
    if welcome and exists(welcome):
        args += ["-v", f"{welcome}:{CONTAINER_HOME}/WELCOME.ipynb:ro"]
    if overrides and exists(overrides):
        args += ["-v", f"{overrides}:/etc/jupyter/labconfig/default_setting_overrides.json:ro"]
    if hook and exists(hook):
        args += ["-v", f"{hook}:{HIDE_WORK_HOOK}:ro"]
    chosen = parse_content(content)
    seen = set()
    for c in chosen:
        if not exists(os.path.join(demos_dir, CONTENT[c]["copy"][0])):
            notes.append(f"{c} is not on this Pi: left out")
            continue
        copy, assets = _content_paths(c)
        for rel in copy + assets:
            if rel in seen:
                continue
            seen.add(rel)
            src = os.path.join(demos_dir, rel)
            if not exists(src):
                continue
            mine = os.path.join(copies, rel) if copies else ""
            if rel in copy and mine and exists(mine):
                args += ["-v", f"{mine}:{CONTAINER_HOME}/{rel}"]
                args += ["-v", f"{src}:{CONTAINER_HOME}/{ORIGINALS}/{rel}:ro"]
            else:
                args += ["-v", f"{src}:{CONTAINER_HOME}/{rel}:ro"]
    return args, notes


def cmd_mounts(args):
    out, notes = mount_args(args.content, args.demos, args.work, args.welcome, args.overrides,
                            args.copies, args.hook)
    for n in notes:
        print(n, file=sys.stderr)
    for a in out:
        print(a)
    return 0


# ---------------------------------------------------------------------------
# the user's copies: prepare / reset / copies
# ---------------------------------------------------------------------------

def content_version(c, demos_dir):
    """
    The version of C's original: the commit of its checkout (and the
    notebook converter's mark, which changes the IBM notebooks in place).
    Empty when it cannot be told.
    """
    root = os.path.join(demos_dir, CONTENT[c]["copy"][0].split("/")[0])
    parts = []
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True,
                                  text=True, timeout=20)
            if head.returncode == 0:
                parts.append(head.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        with open(os.path.join(root, ".rasqberry-converted"), encoding="utf-8") as fh:
            parts.append("converted " + fh.read().strip())
    except OSError:
        pass
    return " ".join(parts)


def _copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.splitext(src)[1].lower() not in TEXT_SUFFIXES:
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)
    os.chmod(dst, os.stat(dst).st_mode | stat.S_IWUSR)


def copy_tree(src, dst):
    """SRC (a file or folder) to DST: text files copied, the rest hard-linked."""
    if os.path.isfile(src):
        _copy_file(src, dst)
        return
    for here, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_NAMES)
        rel = os.path.relpath(here, src)
        target = os.path.normpath(os.path.join(dst, rel))
        os.makedirs(target, exist_ok=True)
        for f in sorted(files):
            if f not in SKIP_NAMES:
                _copy_file(os.path.join(here, f), os.path.join(target, f))


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.unlink(path)


def _load_copies(copies):
    try:
        with open(os.path.join(copies, COPIES_STATE), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_copies(copies, data):
    os.makedirs(copies, exist_ok=True)
    path = os.path.join(copies, COPIES_STATE)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _name(c):
    return {"ibm-tutorials": "IBM Quantum Tutorials", "ibm-courses": "IBM Quantum Courses",
            "quantum-paradoxes": "Quantum Paradoxes", "fun-with-quantum": "Fun with Quantum"}.get(c, c)


def prepare(content, demos_dir, copies):
    """
    Make the user's copies of the chosen content: on first use from the
    original; a copy that is there is never overwritten (a file or folder
    missing from it is added). When the original is newer than the copy
    (Update demos moved it), one note says so, once. Returns the notes.
    """
    state = _load_copies(copies)
    notes = []
    for c in parse_content(content):
        if not os.path.exists(os.path.join(demos_dir, CONTENT[c]["copy"][0])):
            continue
        copy, _ = _content_paths(c)
        version = content_version(c, demos_dir)
        for rel in copy:
            src, dst = os.path.join(demos_dir, rel), os.path.join(copies, rel)
            if os.path.exists(src) and not os.path.lexists(dst):
                copy_tree(src, dst)
        entry = state.get(c)
        if not isinstance(entry, dict):
            state[c] = {"version": version}
        elif version and entry.get("version") != version and entry.get("noticed") != version:
            notes.append(f"{_name(c)}: a newer original is in originals/. Your copy is kept; "
                         "Reset notebooks (in the QuBins start dialog) gives the new one.")
            entry["noticed"] = version
    _save_copies(copies, state)
    return notes


def reset(content, demos_dir, copies):
    """
    Back to the original: the user's copy of each content is removed and
    made again (nothing of the changes in it is kept). The credentials
    notebook shared by the IBM parts and my-work are not touched.
    Returns the names reset.
    """
    state = _load_copies(copies)
    done = []
    for c in parse_content(content):
        if not os.path.exists(os.path.join(demos_dir, CONTENT[c]["copy"][0])):
            continue
        for rel in CONTENT[c]["copy"]:
            src, dst = os.path.join(demos_dir, rel), os.path.join(copies, rel)
            _remove(dst)
            if os.path.exists(src):
                copy_tree(src, dst)
        state[c] = {"version": content_version(c, demos_dir)}
        done.append(_name(c))
    _save_copies(copies, state)
    return done


def copied(copies):
    """The content ids with a copy, in the fixed order."""
    state = _load_copies(copies)
    return [c for c in CONTENT if c in state and any(
        os.path.lexists(os.path.join(copies, rel)) for rel in CONTENT[c]["copy"])]


def cmd_prepare(args):
    for n in prepare(args.content, args.demos, args.copies):
        print(n)
    return 0


def cmd_reset(args):
    for n in reset(args.content, args.demos, args.copies):
        print(n)
    return 0


def cmd_copies(args):
    print(",".join(copied(args.copies)))
    return 0


# ---------------------------------------------------------------------------
# last / remember
# ---------------------------------------------------------------------------

def _is_qubins(ref):
    """A QuBins image: by digest, or by tag (a fallback tag that was downloaded)."""
    return ref.startswith((IMAGE + "@sha256:", IMAGE + ":"))


def load_state(path):
    """The last choices, or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not _is_qubins(str(data.get("image", ""))):
        return None
    content = data.get("content", [])
    if not isinstance(content, list):
        content = []
    return {"image": data["image"], "label": str(data.get("label", "")),
            "content": parse_content(",".join(str(c) for c in content))}


def save_state(path, image, label, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"image": image, "label": label, "content": parse_content(content),
                   "saved": time.strftime("%Y-%m-%d %H:%M")}, fh, indent=1)
    os.replace(tmp, path)


def cmd_last(args):
    state = load_state(args.state)
    if not state:
        return 1
    print("\t".join([state["image"], state["label"] or "-", ",".join(state["content"])]))
    return 0


def cmd_remember(args):
    if not _is_qubins(args.image):
        print(f"Not a QuBins image: {args.image}", file=sys.stderr)
        return 2
    save_state(args.state, args.image, args.label, args.content)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="QuBins (beta) helper for rq_qubins.sh")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("images", help="list the QuBins images to offer")
    p.add_argument("--pin", required=True, help="the release pin (ghcr.io/qubins/images@sha256:...)")
    p.add_argument("--pin-tag", default="", help="the pin's snapshot tag")
    p.add_argument("--pin-mb", type=int, default=0, help="the pin's download size (MB)")
    p.add_argument("--in-use", default="", help="the image QuBins runs now")
    p.add_argument("--in-use-label", default="", help="its tag, if known")
    p.add_argument("--local", default="", help="digests of the QuBins images on this Pi")
    p.add_argument("--minors", type=int, default=4, help="how many Qiskit minor versions")
    p.add_argument("--cache", default="", help="file for the last list read")
    p.add_argument("--max-age", type=float, default=6 * 3600, help="seconds a cached list is used")
    p.add_argument("--offline", action="store_true", help="do not ask the registry")
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("mounts", help="the docker -v arguments, one per line")
    p.add_argument("--content", default="", help="comma-separated content ids")
    p.add_argument("--demos", required=True, help="the demos folder (~/RasQberry-Two/demos)")
    p.add_argument("--work", required=True, help="the my-work folder")
    p.add_argument("--welcome", default="", help="the welcome notebook")
    p.add_argument("--overrides", default="", help="JupyterLab default_setting_overrides.json")
    p.add_argument("--copies", default="", help="the folder of the user's copies (work/qubins)")
    p.add_argument("--hook", default="", help="the start hook that hides the image's work folder")
    p.set_defaults(func=cmd_mounts)

    for name, func, text in (("prepare", cmd_prepare, "make the copies of the chosen content"),
                             ("reset", cmd_reset, "reset the copies of the content to the original")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--content", default="", help="comma-separated content ids")
        p.add_argument("--demos", required=True, help="the demos folder")
        p.add_argument("--copies", required=True, help="the folder of the user's copies")
        p.set_defaults(func=func)

    p = sub.add_parser("copies", help="the content ids with a copy, comma-separated")
    p.add_argument("--copies", required=True)
    p.set_defaults(func=cmd_copies)

    p = sub.add_parser("last", help="print the last choices")
    p.add_argument("--state", required=True)
    p.set_defaults(func=cmd_last)

    p = sub.add_parser("remember", help="save the choices")
    p.add_argument("--state", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--label", default="")
    p.add_argument("--content", default="")
    p.set_defaults(func=cmd_remember)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
