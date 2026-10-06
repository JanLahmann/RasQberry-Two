#!/usr/bin/env python3
"""
rpi-imager.json: the RasQberry sublist for the official Raspberry Pi Imager.

The official Imager list links to this file with "subitems_url"; it is served
at https://rasqberry.org/rpi-imager.json (gh-pages public/). It differs from
RQB-images.json (our own --repo list):

- {"os_list": [...]} only: no "imager" key (that belongs to the top-level list)
- only the newest release of the most stable stream: beta until a stable
  release exists, then stable only
- two entries from that release: the A/B image (recommended) first, then the
  single-system image
- no stock Raspberry Pi OS entry, no developer builds
- the description names the user (always rasqberry) but not the password

Imager drops an invalid entry silently, and a sublist that fails to load
leaves an empty folder in the official list. So the list is checked against
Imager's schema (vendored: .github/imager/os-list-schema.json, from
raspberrypi/rpi-imager doc/json-schema at 4f15f487, 2026-07-08) and our own
stricter rules, and each image URL must answer with its size, BEFORE the file
is written. A list that fails is never written: the previous one stays.

Used by consolidate_json.py (write_sublist). By hand:
    rpi_imager_list.py --release-json DIR [--out FILE] [--no-url-check]
    rpi_imager_list.py --check FILE_OR_URL      (a published list)
"""
import argparse
import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "imager"
SCHEMA_FILE = ASSETS / "os-list-schema.json"
ICON_FILE = ASSETS / "rasqberry-40.png"

# Published next to the list (gh-pages public/imager/)
ICON_PATH = "imager/rasqberry-40.png"
ICON_URL = "https://rasqberry.org/" + ICON_PATH
WEBSITE = "https://rasqberry.org"
DEVICES = ["pi5-64bit", "pi4-64bit"]
ARCHITECTURE = "armv8"
INIT_FORMAT = "systemd"

# Raspberry Pi Connect in Imager's customisation. Switch on only after the
# image's Connect fix (firstrun.sh: the token goes to rasqberry, not to the
# name typed in Imager; dev-imager-connect) has passed a rig test.
RPI_CONNECT = False

USER_NOTE = "Username is always rasqberry."
SINGLE = " — single system"
# (branch, entry name), most stable first: the first stream with a release wins
STREAMS = (("main", "RasQberry Two"), ("beta", "RasQberry Two Beta"))

UA = {"User-Agent": "RasQberry-Workflow"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SublistError(Exception):
    """The sublist cannot be built or does not pass its checks."""


def load_releases(json_dir):
    """The release assets (RQB-images.json of each release) as the workflow
    downloaded them, with _branch, _published and _release_tag added."""
    releases = []
    for f in sorted(Path(json_dir).glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError) as e:
            print(f"  rpi-imager.json: skipping {f.name}: {e}")
            continue
        if data.get("_branch"):
            releases.append(data)
    return releases


def _rasqberry_entries(release):
    return [e for e in release.get("os_list", [])
            if "RasQberry" in e.get("name", "") and "Dev" not in e.get("name", "")]


def pick_release(releases):
    """(stream name, release) of the newest release of the most stable stream."""
    for branch, label in STREAMS:
        candidates = [r for r in releases if r.get("_branch") == branch and _rasqberry_entries(r)]
        if candidates:
            return label, max(candidates, key=lambda r: r.get("_published", ""))
    raise SublistError("no stable or beta release found")


def _is_ab(entry):
    return entry.get("image_type") == "ab" or "A/B" in entry.get("name", "")


def _date(entry, release):
    """release_date as YYYY-MM-DD (dev builds carry a time too)."""
    for value in (entry.get("release_date") or "", release.get("_published") or ""):
        if DATE.match(value[:10]):
            return value[:10]
    raise SublistError(f"no release date for {entry.get('url')}")


def _entry(src, release, name, description):
    entry = {
        "name": name,
        "description": description,
        "icon": ICON_URL,
        "url": src.get("url"),
        "extract_size": src.get("extract_size"),
        "extract_sha256": src.get("extract_sha256"),
        "image_download_size": src.get("image_download_size"),
        "image_download_sha256": src.get("image_download_sha256") or src.get("image_sha256"),
        "release_date": _date(src, release),
        "init_format": INIT_FORMAT,
        "devices": list(DEVICES),
        "architecture": ARCHITECTURE,
        "website": WEBSITE,
    }
    if RPI_CONNECT:
        entry["capabilities"] = ["rpi_connect"]
    return entry


def build_sublist(releases):
    """The sublist document for the newest release of the most stable stream."""
    label, release = pick_release(releases)
    entries = _rasqberry_entries(release)
    ab = next((e for e in entries if _is_ab(e)), None)
    std = next((e for e in entries if not _is_ab(e)), None)
    tag = release.get("_release_tag", "?")
    if not ab or not std:
        missing = "A/B" if not ab else "single-system"
        raise SublistError(f"{tag} has no {missing} image")
    return {"os_list": [
        _entry(ab, release, label,
               "Recommended. Two systems with safe updates on 64 GB+ cards, one system on "
               f"smaller ones. Best: 128 GB A2/U3. Pi 4/5. {USER_NOTE}"),
        _entry(std, release, label + SINGLE,
               "One system, no updates in place. 16 GB+ card, 32 GB+ for Docker demos. "
               f"Pi 4/5. {USER_NOTE}"),
    ]}


def check_sublist(doc, schema=None):
    """Errors (a list of strings) of a sublist: Imager's schema, then our rules.

    The schema accepts an entry as an image OR a folder (anyOf), so every
    entry is also checked against the image variant alone: a folder would be
    an empty one in the official list.
    """
    import jsonschema  # CI: pip install jsonschema

    if schema is None:
        schema = json.loads(SCHEMA_FILE.read_text())
    errors = [f"schema: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(doc)]
    if not isinstance(doc, dict):
        return errors or ["not a JSON object"]
    if "imager" in doc:
        errors.append('the "imager" key belongs to the top-level list only')
    os_list = doc.get("os_list")
    if not isinstance(os_list, list) or not os_list:
        return errors + ["os_list is empty"]
    image_schema = schema["properties"]["os_list"]["items"]["anyOf"][0]
    for i, e in enumerate(os_list):
        where = f"os_list[{i}] ({e.get('name', '?') if isinstance(e, dict) else '?'})"
        for err in jsonschema.Draft7Validator(image_schema).iter_errors(e):
            errors.append(f"{where}: {err.message}")
        if not isinstance(e, dict):
            continue
        for key in ("extract_sha256", "image_download_sha256"):
            if not SHA256.match(str(e.get(key, ""))):
                errors.append(f"{where}: {key} is not a sha256")
        for key in ("extract_size", "image_download_size"):
            if not (isinstance(e.get(key), int) and e[key] > 0):
                errors.append(f"{where}: {key} is not a positive size")
        if not DATE.match(str(e.get("release_date", ""))):
            errors.append(f"{where}: release_date is not YYYY-MM-DD")
        if e.get("devices") != DEVICES:
            errors.append(f"{where}: devices must be {DEVICES}")
        if e.get("init_format") != INIT_FORMAT or e.get("architecture") != ARCHITECTURE:
            errors.append(f"{where}: init_format/architecture must be {INIT_FORMAT}/{ARCHITECTURE}")
        for key in ("url", "icon", "website"):
            if not str(e.get(key, "")).startswith("https://") or " " in str(e.get(key, "")):
                errors.append(f"{where}: {key} must be an https URL without spaces")
        if "Qiskit1!" in e.get("description", ""):
            errors.append(f"{where}: the description must not publish the password")
    return errors


def head_size(url, timeout=60):
    """Content-Length of a HEAD request (redirects followed)."""
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(r.headers.get("Content-Length", -1))


def check_urls(doc, head=head_size):
    """Errors: each image URL must answer with image_download_size bytes."""
    errors = []
    for e in doc.get("os_list", []):
        url = e.get("url", "")
        try:
            size = head(url)
        except Exception as ex:  # HTTPError, URLError, timeout
            errors.append(f"{url}: {ex}")
            continue
        if size != e.get("image_download_size"):
            errors.append(f"{url}: {size} bytes, the list says {e.get('image_download_size')}")
    return errors


def write_sublist(json_dir, out_file, url_check=True, head=head_size):
    """Build, check and write the sublist and its icon (next to it).

    Returns True when written. On any failure nothing is written (the
    previous file stays) and the errors are printed as GitHub annotations.
    """
    out_file = Path(out_file)
    try:
        doc = build_sublist(load_releases(json_dir))
        errors = check_sublist(doc)
        if not errors and url_check:
            errors = check_urls(doc, head=head)
        if errors:
            raise SublistError("; ".join(errors))
    except Exception as e:  # SublistError, or no jsonschema, a bad asset...
        print(f"::error title=rpi-imager.json not updated::{e}")
        return False
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    tmp.replace(out_file)
    icon = out_file.parent / ICON_PATH
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_FILE, icon)
    print(f"\n=== {out_file.name}: {', '.join(e['name'] for e in doc['os_list'])} ===")
    print(json.dumps(doc, indent=2))
    return True


def _load(source):
    if re.match(r"^https?://", source):
        with urllib.request.urlopen(urllib.request.Request(source, headers=UA), timeout=60) as r:
            return json.loads(r.read().decode())
    return json.loads(Path(source).read_text())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--release-json", help="directory of release RQB-images.json files")
    p.add_argument("--out", default="public/rpi-imager.json")
    p.add_argument("--no-url-check", action="store_true", help="skip the HEAD requests")
    p.add_argument("--check", metavar="FILE_OR_URL", help="check a published sublist and its URLs")
    args = p.parse_args(argv)
    if args.check:
        doc = _load(args.check)
        errors = check_sublist(doc) + ([] if args.no_url_check else check_urls(doc))
        for e in errors:
            print(f"::error title=rpi-imager.json::{e}")
        print(f"{args.check}: {'OK' if not errors else f'{len(errors)} error(s)'}")
        return 1 if errors else 0
    if not args.release_json:
        p.error("--release-json or --check is required")
    return 0 if write_sublist(args.release_json, args.out, url_check=not args.no_url_check) else 1


if __name__ == "__main__":
    sys.exit(main())
