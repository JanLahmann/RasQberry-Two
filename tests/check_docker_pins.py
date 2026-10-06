#!/usr/bin/env python3
"""
Check that the registries still offer every Docker image our demos pin.

A digest pin disappears when its publisher prunes old builds: QuBins did
that to Quantum Lab's pin in 2026-10, and its first start failed with "The
registry does not offer ghcr.io/qubins/images@sha256:... (any more)". This
check asks the registry for each image the demo manifests name (the pin and
its docker_image_fallback tag) and for the Docker demos of the catalogue
(known-demos.json, each manifest read at its pinned commit), so CI finds a
pruned pin before users do.

Usage:
    python3 tests/check_docker_pins.py [REPO_ROOT ...] [--no-catalogue]

One line per image: "ok", "GONE" (the registry answers 404 / manifest
unknown) or "ERROR" (no answer). Exit codes: 0 all offered, 1 an image is
gone, 2 a registry could not be asked. Anonymous HEAD requests only
(ghcr.io, Docker Hub and other registries with the standard token flow);
only the Python standard library is used.
"""

import argparse
import glob
import json
import os
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


def parse_image(image):
    """
    Split an image reference into registry, repository and reference.

    Args:
        image (str): e.g. "ghcr.io/qubins/images@sha256:...", "python:3.11"

    Returns:
        tuple: (registry host, repository, tag or digest)
    """
    name, ref = image, "latest"
    if "@" in image:
        name, ref = image.split("@", 1)
    elif ":" in image.rsplit("/", 1)[-1]:
        name, ref = image.rsplit(":", 1)
    first = name.split("/", 1)[0]
    if "/" in name and ("." in first or ":" in first or first == "localhost"):
        registry, repo = name.split("/", 1)
    else:
        registry, repo = "docker.io", name
    if registry == "docker.io":
        registry = "registry-1.docker.io"
        if "/" not in repo:
            repo = "library/" + repo
    return registry, repo, ref


def _open(req):
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def _token(challenge, repo, opener):
    """Anonymous pull token for REPO from a WWW-Authenticate Bearer challenge."""
    fields = dict(re.findall(r'(\w+)="([^"]*)"', challenge or ""))
    realm = fields.get("realm")
    if not realm:
        return None
    url = f"{realm}?scope=repository:{repo}:pull"
    if fields.get("service"):
        url += f"&service={fields['service']}"
    with opener(urllib.request.Request(url)) as resp:
        data = json.load(resp)
    return data.get("token") or data.get("access_token")


def offered(image, opener=_open):
    """
    Ask the registry whether it still offers IMAGE.

    Args:
        image (str): the image reference
        opener (callable): urlopen replacement for tests

    Returns:
        str: "ok", "gone" or "error: <reason>"
    """
    registry, repo, ref = parse_image(image)
    url = f"https://{registry}/v2/{repo}/manifests/{ref}"
    headers = {"Accept": ACCEPT}
    for _attempt in range(2):
        try:
            with opener(urllib.request.Request(url, method="HEAD", headers=headers)):
                return "ok"
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and "Authorization" not in headers:
                try:
                    token = _token(exc.headers.get("WWW-Authenticate", ""), repo, opener)
                except urllib.error.HTTPError as err:
                    # ghcr.io refuses a token for a repository that is gone
                    if err.code in (401, 403):
                        return "gone"
                    return f"error: no token ({err})"
                except (urllib.error.URLError, OSError, ValueError) as err:
                    return f"error: no token ({err})"
                if not token:
                    return "error: no token"
                headers["Authorization"] = f"Bearer {token}"
                continue
            if exc.code == 404:
                return "gone"
            # ghcr.io answers 401/403 for a repository that is gone or private
            if exc.code in (401, 403):
                return "gone"
            return f"error: HTTP {exc.code}"
        except (urllib.error.URLError, OSError) as exc:
            return f"error: {exc}"
    return "error: no answer"


def manifest_images(root):
    """
    The images the shipped demo manifests name, with where they come from.

    Returns:
        list: (image, label) pairs
    """
    out = []
    for path in sorted(glob.glob(os.path.join(root, "RQB2-config", "demo-manifests", "rq_demo_*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        ep = m.get("entrypoint") or {}
        if not isinstance(ep, dict) or ep.get("type") != "docker":
            continue
        for key in ("docker_image", "docker_image_fallback"):
            if ep.get(key):
                out.append((ep[key], f"{m.get('id', os.path.basename(path))} {key}"))
    return out


def catalogue_images(root, opener=_open):
    """
    The images of the catalogue's Docker demos (known-demos.json), each read
    from the demo's manifest at its pinned commit on GitHub.

    Returns:
        tuple: ((image, label) pairs, [error lines])
    """
    path = os.path.join(root, "RQB2-config", "known-demos.json")
    try:
        with open(path, encoding="utf-8") as f:
            demos = json.load(f).get("demos", [])
    except (OSError, ValueError):
        return [], []
    out, errors = [], []
    for d in demos:
        m = re.match(r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", d.get("repo_url", ""))
        if not m or not d.get("ref"):
            continue
        url = (f"https://raw.githubusercontent.com/{m.group(1)}/{d['ref']}/"
               f"{d.get('manifest_path', 'rqb-demo.json')}")
        try:
            with opener(urllib.request.Request(url)) as resp:
                ep = json.load(resp).get("entrypoint") or {}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            errors.append(f"ERROR  catalogue {d.get('id')}: manifest not readable ({exc})")
            continue
        if ep.get("type") == "docker" and ep.get("docker_image"):
            out.append((ep["docker_image"], f"catalogue {d.get('id')}"))
            if ep.get("docker_image_fallback"):
                out.append((ep["docker_image_fallback"], f"catalogue {d.get('id')} fallback"))
    return out, errors


def main(argv=None):
    """Check every root given (default: this checkout); print one line per image."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("roots", nargs="*",
                        default=[os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))])
    parser.add_argument("--no-catalogue", action="store_true")
    args = parser.parse_args(argv)

    gone = error = 0
    seen = {}
    for root in args.roots:
        if len(args.roots) > 1:
            print(f"== {root}")
        images = manifest_images(root)
        errors = []
        if not args.no_catalogue:
            more, errors = catalogue_images(root)
            images += more
        for line in errors:
            print(line)
            error += 1
        for image, label in images:
            if image not in seen:
                seen[image] = offered(image)
            state = seen[image]
            mark = {"ok": "ok   ", "gone": "GONE "}.get(state, "ERROR")
            print(f"{mark}  {label}: {image}" + ("" if state in ("ok", "gone") else f" ({state})"))
            gone += state == "gone"
            error += state not in ("ok", "gone")
    if gone:
        print(f"\n{gone} pinned image(s) no longer offered: re-pin them in the demo manifests "
              "(and check that the fallback tag still exists).")
        return 1
    return 2 if error else 0


if __name__ == "__main__":
    sys.exit(main())
