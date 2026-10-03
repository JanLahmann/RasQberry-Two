#!/usr/bin/env python3
"""
List the newer versions of a demo's Docker image on ghcr.io.

"Update demos" (rq_demo_update.sh) offers the latest build and the versions
in between: every tag that matches the demo's pattern and was built after
the version in use, with its date, download size and Qiskit version.

Usage:
    rq_image_versions.py IMAGE_IN_USE --tags REGEX [--latest TAG] [--arch arm64]

IMAGE_IN_USE is "ghcr.io/OWNER/NAME@sha256:..." (or ":TAG"). One line per
version, newest first, tab-separated:
    REF  TAGS  DATE  DOWNLOAD_MB  NOTE  STATE
REF is "ghcr.io/OWNER/NAME@sha256:<digest>", STATE is "newer" or "current"
(the version in use, last). Only the Python standard library is used.

Exit codes: 0 listed (maybe nothing newer), 2 registry not reachable or an
unexpected answer, 3 not a ghcr.io image.
"""

import argparse
import concurrent.futures
import json
import re
import sys
import urllib.error
import urllib.request

ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
TIMEOUT = 20


class Registry:
    """Anonymous read access to one ghcr.io repository."""

    def __init__(self, repo):
        self.repo = repo
        url = f"https://ghcr.io/token?scope=repository:{repo}:pull"
        self.token = self._json(url, auth=False)["token"]

    def _get(self, url, accept=None, auth=True):
        req = urllib.request.Request(url)
        if auth:
            req.add_header("Authorization", f"Bearer {self.token}")
        if accept:
            req.add_header("Accept", accept)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(), resp.headers

    def _json(self, url, accept=None, auth=True):
        body, _ = self._get(url, accept, auth)
        return json.loads(body)

    def tags(self):
        """All tags of the repository."""
        data = self._json(f"https://ghcr.io/v2/{self.repo}/tags/list?n=10000")
        return data.get("tags") or []

    def manifest(self, ref):
        """(digest, manifest) for a tag or digest."""
        body, headers = self._get(f"https://ghcr.io/v2/{self.repo}/manifests/{ref}", ACCEPT)
        return headers.get("Docker-Content-Digest", ref), json.loads(body)

    def blob(self, digest):
        return self._json(f"https://ghcr.io/v2/{self.repo}/blobs/{digest}")


def describe(reg, ref, arch):
    """
    Facts about one tag or digest.

    Returns:
        dict: digest, created, download_mb, note - or None if the image has
        no build for this architecture.
    """
    digest, man = reg.manifest(ref)
    if "manifests" in man:  # multi-platform index: pick our architecture
        plat = [m for m in man["manifests"]
                if m.get("platform", {}).get("architecture") == arch
                and m.get("platform", {}).get("os") == "linux"]
        if not plat:
            return None
        _, man = reg.manifest(plat[0]["digest"])
    config = reg.blob(man["config"]["digest"])
    if "manifests" not in man and config.get("architecture") not in (arch, None):
        # a single-platform image of another architecture still runs on arm64
        # if it is arm (v7); say so instead of hiding it
        note_arch = f"{config.get('architecture')}{config.get('variant', '')}"
    else:
        note_arch = ""
    labels = (config.get("config") or {}).get("Labels") or {}
    notes = []
    qiskit = labels.get("org.qubins.qiskit.patch") or labels.get("org.qubins.qiskit.version")
    if qiskit:
        notes.append(f"Qiskit {qiskit}")
    rev = labels.get("org.opencontainers.image.revision", "")
    if rev:
        notes.append(f"commit {rev[:7]}")
    if note_arch:
        notes.append(note_arch)
    return {
        "digest": digest,
        "created": labels.get("org.opencontainers.image.created") or config.get("created") or "",
        "download_mb": sum(layer.get("size", 0) for layer in man.get("layers", [])) // 1000000,
        "note": ", ".join(notes),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("image", help="the image in use, ghcr.io/OWNER/NAME@sha256:... or :TAG")
    parser.add_argument("--tags", required=True, help="regular expression for the version tags")
    parser.add_argument("--latest", default="", help="tag of the newest build, e.g. 'jupyter'")
    parser.add_argument("--arch", default="arm64")
    args = parser.parse_args()

    m = re.match(r"^ghcr\.io/([^@:]+)(?:[@:](.+))?$", args.image)
    if not m:
        print(f"Only images on ghcr.io can be listed: {args.image}", file=sys.stderr)
        return 3
    repo, current_ref = m.group(1).lower(), m.group(2) or "latest"

    try:
        reg = Registry(repo)
        pattern = re.compile(args.tags)
        tags = [t for t in reg.tags() if pattern.search(t)]
        if args.latest:
            tags.append(args.latest)
        refs = [current_ref] + sorted(set(tags) - {current_ref})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            facts = dict(zip(refs, pool.map(lambda r: _safe(reg, r, args.arch), refs)))
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        print(f"The registry ghcr.io could not be read: {exc}", file=sys.stderr)
        return 2

    current = facts.get(current_ref)
    if not current:
        print(f"The version in use was not found on ghcr.io: {args.image}", file=sys.stderr)
        return 2

    # One line per image (tags that share a digest are listed together)
    versions = {}
    for ref, info in facts.items():
        if not info:
            continue
        entry = versions.setdefault(info["digest"], dict(info, tags=[]))
        if not ref.startswith("sha256:"):
            entry["tags"].append(f"{ref} (latest)" if ref == args.latest else ref)

    cur = versions[current["digest"]]
    newer = [v for d, v in versions.items()
             if d != current["digest"] and _order(v) > _order(cur)]
    newer.sort(key=_order, reverse=True)
    for v, state in [(v, "newer") for v in newer] + [(cur, "current")]:
        print("\t".join([
            f"ghcr.io/{repo}@{v['digest']}",
            ", ".join(sorted(v["tags"], key=lambda t: "(latest)" not in t)) or "-",
            v["created"][:10],
            str(v["download_mb"]),
            v["note"] or "-",
            state,
        ]))
    return 0


def _order(version):
    """
    Sort key: build date, then the highest version number among its tags
    (QuBins builds all its tags with one timestamp, so 2.5-xl and 2.4-xl tie).
    """
    numbers = [tuple(int(n) for n in re.findall(r"\d+", t.split("-")[0]))
               for t in version["tags"] if re.match(r"^\d+(\.\d+)*", t)]
    return (version["created"], max(numbers, default=()))


def _safe(reg, ref, arch):
    """describe(), with a tag that vanished meanwhile counted as absent."""
    try:
        return describe(reg, ref, arch)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


if __name__ == "__main__":
    sys.exit(main())
