"""
A pinned Docker image that its registry no longer offers (2026-10-06).

QuBins prunes old builds, and Quantum Lab's pin (a digest) went with them:
its first start failed with "The registry does not offer ghcr.io/qubins/
images@sha256:... (any more)". Now:

  * rq_docker_pull downloads the manifest's fallback tag
    (entrypoint.docker_image_fallback) instead, with one line saying so, but
    only when the registry does not offer the pin; offline, no space or
    access denied still stop;
  * rq_demo_docker_pull records the fallback as the version in use for that
    release pin, so the next start runs it and a newer release's pin wins;
  * the engine and the Docker launchers run the image that was downloaded;
  * every shipped digest pin has a fallback tag of the same image;
  * "Update demos" lists the versions there are when the one in use is gone;
  * tests/check_docker_pins.py asks the registries (online part skipped
    offline).
"""

import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import urllib.error
from contextlib import redirect_stdout

import pytest

from test_demo_consent import box, _exe, _common, _ENGINE  # noqa: F401

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_BIN = os.path.join(_ROOT, "RQB2-bin")
_MANIFESTS = os.path.join(_ROOT, "RQB2-config", "demo-manifests")

_PIN = "ghcr.io/x/demo@sha256:" + "1" * 64
_TAG = "ghcr.io/x/demo:2.5-xl"


def _docker(box, pull_error, have=""):
    """
    A docker stub: "pull" of a digest fails with PULL_ERROR (a tag pulls),
    "image inspect" finds the images pulled so far and those in HAVE.
    """
    log = box.tmp / "docker.log"
    pulled = box.tmp / "pulled"
    pulled.write_text(have)
    _exe(box.stubs / "docker", f'''#!/bin/sh
echo "$*" >> "{log}"
case "$1 $2" in
  "info "*) exit 0 ;;
  "image inspect") grep -qxF "$3" "{pulled}"; exit $? ;;
  "images -q") grep -qxF "$3" "{pulled}" && echo abc123; exit 0 ;;
  "container inspect") exit 1 ;;
esac
if [ "$1" = pull ]; then
  case "$3" in
    *@sha256:*) [ -n "{pull_error}" ] && {{ echo "{pull_error}" >&2; exit 1; }} ;;
  esac
  echo "$3" >> "{pulled}"
  exit 0
fi
exit 0
''')
    return log


_GONE = "Error response from daemon: manifest for ghcr.io/x/demo@sha256:111 not found: manifest unknown: manifest unknown"


# --- rq_docker_pull -----------------------------------------------------------

def test_a_pruned_pin_falls_back_to_the_tag(box):
    log = _docker(box, _GONE)
    proc = _common(box, f'rq_docker_pull "{_PIN}" "Demo X" 500 "{_TAG}"; echo "PULLED=$RQ_DOCKER_PULLED"')
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"PULLED={_TAG}" in proc.stdout
    calls = log.read_text()
    assert f"pull -q {_PIN}" in calls and f"pull -q {_TAG}" in calls
    lines = [line for line in out.splitlines() if "no longer offers" in line]
    assert lines == ["INFO: The registry no longer offers the tested version of Demo X; "
                     "downloading x/demo:2.5-xl instead."], out


def test_the_pin_itself_is_used_when_it_is_there(box):
    log = _docker(box, "")
    proc = _common(box, f'rq_docker_pull "{_PIN}" "Demo X" 500 "{_TAG}"; echo "PULLED=$RQ_DOCKER_PULLED"')
    assert f"PULLED={_PIN}" in proc.stdout
    assert _TAG not in log.read_text()


@pytest.mark.parametrize("error, says", [
    ("Error response from daemon: Get \"https://ghcr.io/v2/\": dial tcp: lookup ghcr.io: no such host",
     "Could not download Demo X"),
    ("Error response from daemon: Get \"https://ghcr.io/v2/\": net/http: TLS handshake timeout",
     "Could not download Demo X"),
    ("failed to register layer: write /var/lib/docker/x: no space left on device",
     "Not enough free space for Demo X"),
    ("Error response from daemon: denied", "The registry does not offer"),
])
def test_no_fallback_on_other_errors(box, error, says):
    log = _docker(box, error)
    proc = _common(box, f'rq_docker_pull "{_PIN}" "Demo X" 500 "{_TAG}"; echo "AFTER"')
    assert proc.returncode == 1 and "AFTER" not in proc.stdout
    assert says in proc.stderr, proc.stderr
    assert _TAG not in log.read_text()
    assert "no longer offers" not in proc.stdout


def test_without_a_fallback_a_pruned_pin_still_says_why(box):
    _docker(box, _GONE)
    proc = _common(box, f'rq_docker_pull "{_PIN}" "Demo X"')
    assert proc.returncode == 1
    assert f"The registry does not offer {_PIN} (any more)" in proc.stderr


def test_a_fallback_that_fails_too_stops_with_its_reason(box):
    _exe(box.stubs / "docker", f'#!/bin/sh\necho "{_GONE}" >&2\nexit 1\n')
    proc = _common(box, f'rq_docker_pull "{_PIN}" "Demo X" 500 "{_TAG}"')
    assert proc.returncode == 1
    assert f"The registry does not offer {_TAG} (any more)" in proc.stderr


# --- rq_demo_docker_pull: the fallback is remembered for this release pin ------

def _user_docker_manifest(box, pin=_PIN, fallback=_TAG):
    d = box.home / ".local" / "config" / "demo-manifests"
    d.mkdir(parents=True, exist_ok=True)
    m = {"id": "pin-demo", "name": "Pin Demo", "category": "tool", "description": "t",
         "entrypoint": {"type": "docker", "docker_image": pin, "docker_port": 8000},
         "install": {"download": {"download_mb": 5, "disk_mb": 10}}}
    if fallback:
        m["entrypoint"]["docker_image_fallback"] = fallback
    path = d / "rq_demo_pin-demo.json"
    path.write_text(json.dumps(m))
    return path


def test_the_fallback_becomes_the_version_in_use_until_a_new_pin(box):
    _docker(box, _GONE)
    mf = _user_docker_manifest(box)
    proc = _common(box, f'''
        rq_demo_docker_pull pin-demo "{_PIN}" "Pin Demo" 5 "{mf}"
        echo "PULLED=$RQ_DOCKER_PULLED"
        echo "IMAGE=$(rq_demo_image pin-demo "{mf}")"
        echo "LABEL=$(rq_demo_chosen_label pin-demo:image)"
    ''')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"PULLED={_TAG}" in proc.stdout
    assert f"IMAGE={_TAG}" in proc.stdout
    assert "LABEL=2.5-xl (the release version is no longer offered)" in proc.stdout
    # a newer release ships a new pin: that one is used again
    mf2 = _user_docker_manifest(box, pin="ghcr.io/x/demo@sha256:" + "2" * 64)
    proc = _common(box, f'echo "IMAGE=$(rq_demo_image pin-demo "{mf2}")"')
    assert "IMAGE=ghcr.io/x/demo@sha256:" + "2" * 64 in proc.stdout


def test_the_engine_installs_the_fallback_and_counts_it_as_installed(box):
    log = _docker(box, _GONE)
    _user_docker_manifest(box)
    proc = box([_ENGINE, "pin-demo", "--install-only"])
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "no longer offers the tested version of Pin Demo" in out
    assert f"pull -q {_TAG}" in log.read_text()
    # the next start finds it, without a download (also offline)
    assert box([_ENGINE, "pin-demo", "--is-installed"]).returncode == 0


def test_the_quantum_lab_launcher_runs_the_fallback(box):
    # rq_quantum_lab.sh up to its docker run: course notebooks there, the
    # pinned digest gone from the registry
    log = _docker(box, _GONE)
    docs = box.home / "RasQberry-Two" / "demos" / "ibm-quantum-learning"
    docs.mkdir(parents=True)
    (docs / "WELCOME-courses.ipynb").write_text("{}")
    _exe(box.stubs / "id", '#!/bin/sh\necho "uid=1000 gid=1000 groups=1000,995(docker)"\n')
    _exe(box.stubs / "groups", '#!/bin/sh\necho "rasqberry docker"\n')
    _exe(box.stubs / "ss", '#!/bin/sh\nexit 0\n')
    lab = json.load(open(os.path.join(_MANIFESTS, "rq_demo_quantum-lab.json")))
    fallback = lab["entrypoint"]["docker_image_fallback"]
    proc = box([os.path.join(_BIN, "rq_quantum_lab.sh")],
               extra={"RQ_AUTO_INSTALL": "1", "RQ_DEMO_CONSENT": "yes"})
    calls = log.read_text()
    run = [c for c in calls.splitlines() if c.startswith("run ")]
    assert f"pull -q {lab['entrypoint']['docker_image']}" in calls, proc.stdout + proc.stderr
    assert f"pull -q {fallback}" in calls, proc.stdout + proc.stderr
    assert run and run[0].endswith(fallback), (run, proc.stdout + proc.stderr)


def test_the_engine_and_launchers_pull_with_the_fallback():
    for name, count in [("rq_demo_run.sh", 2), ("rq_quantum_lab.sh", 1),
                        ("rq_doqumentation.sh", 1), ("qoffee-maker.sh", 1)]:
        with open(os.path.join(_BIN, name)) as fh:
            text = fh.read()
        assert text.count('rq_demo_docker_pull "$') + text.count("rq_demo_docker_pull quantum-lab") \
            + text.count("rq_demo_docker_pull doqumentation") \
            + text.count("rq_demo_docker_pull qoffee-maker") == count, name
        assert 'rq_docker_pull "$DOCKER_IMAGE"' not in text, name
        assert "RQ_DOCKER_PULLED" in text, name


# --- shipped manifests ---------------------------------------------------------

def test_every_shipped_digest_pin_has_a_fallback_tag_of_the_same_image():
    pins = 0
    for f in sorted(os.listdir(_MANIFESTS)):
        if not f.startswith("rq_demo_") or f == "rq_demo_schema.json":
            continue
        ep = json.load(open(os.path.join(_MANIFESTS, f))).get("entrypoint", {})
        image = ep.get("docker_image", "")
        if "@sha256:" not in image:
            continue
        pins += 1
        fallback = ep.get("docker_image_fallback", "")
        assert fallback.startswith(image.split("@")[0] + ":"), f
        assert "@" not in fallback and "/" not in fallback.rsplit(":", 1)[1], f
    assert pins >= 3


def test_the_validator_wants_the_fallback(tmp_path):
    src = json.load(open(os.path.join(_MANIFESTS, "rq_demo_quantum-lab.json")))
    for fallback, ok in [(None, False), ("ghcr.io/qubins/images:2.5-xl", True),
                         ("ghcr.io/other/images:2.5-xl", False),
                         ("ghcr.io/qubins/images@sha256:" + "a" * 64, False)]:
        m = json.loads(json.dumps(src))
        if fallback is None:
            del m["entrypoint"]["docker_image_fallback"]
        else:
            m["entrypoint"]["docker_image_fallback"] = fallback
        path = tmp_path / "rq_demo_quantum-lab.json"
        path.write_text(json.dumps(m))
        proc = subprocess.run(["bash", os.path.join(_BIN, "rq_demo_validate.sh"), str(path)],
                              capture_output=True, text=True, timeout=60)
        assert (proc.returncode == 0) == ok, (fallback, proc.stdout)


# --- "Update demos" when the version in use is gone ----------------------------

def _versions(monkeypatch, facts, tags, argv):
    spec = importlib.util.spec_from_file_location("rq_image_versions",
                                                  os.path.join(_BIN, "rq_image_versions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class FakeRegistry:
        def __init__(self, repo):
            self.repo = repo

        def tags(self):
            return tags

    monkeypatch.setattr(mod, "Registry", FakeRegistry)
    monkeypatch.setattr(mod, "describe", lambda reg, ref, arch: facts.get(ref))
    monkeypatch.setattr(sys, "argv", ["rq_image_versions.py", *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = mod.main()
    return rc, [line.split("\t") for line in buf.getvalue().splitlines()]


def test_update_demos_lists_the_versions_when_the_one_in_use_is_gone(monkeypatch):
    def fact(d, t):
        return {"digest": d, "created": t, "download_mb": 890, "note": ""}
    facts = {"2.4-xl": fact("sha256:24", "2026-10-06T10:56:50Z"),
             "2.5-xl": fact("sha256:25", "2026-10-06T10:57:27Z"),
             "latest-xl": fact("sha256:25", "2026-10-06T10:57:27Z"),
             "2.3-xl": fact("sha256:23", "2026-10-06T10:58:01Z")}   # built last
    gone = "ghcr.io/qubins/images@sha256:" + "a" * 64
    rc, rows = _versions(monkeypatch, facts, ["2.3-xl", "2.4-xl", "2.5-xl"],
                         [gone, "--tags", r"^[0-9]+\.[0-9]+-xl$", "--latest", "latest-xl"])
    assert rc == 0
    # same build day: by version, not by the seconds between the builds
    assert [r[1] for r in rows[:-1]] == ["latest-xl (latest), 2.5-xl", "2.4-xl", "2.3-xl"]
    assert all(r[-1] == "newer" for r in rows[:-1])
    assert rows[-1] == [gone, "-", "-", "0", "no longer offered", "current"]


# --- tests/check_docker_pins.py -----------------------------------------------

def _pins_module():
    spec = importlib.util.spec_from_file_location(
        "check_docker_pins", os.path.join(_ROOT, "tests", "check_docker_pins.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("image, parts", [
    ("ghcr.io/qubins/images@sha256:abc", ("ghcr.io", "qubins/images", "sha256:abc")),
    ("ghcr.io/qubins/images:2.5-xl", ("ghcr.io", "qubins/images", "2.5-xl")),
    ("ghcr.io/janlahmann/traqmania", ("ghcr.io", "janlahmann/traqmania", "latest")),
    ("python:3.11", ("registry-1.docker.io", "library/python", "3.11")),
    ("someone/app", ("registry-1.docker.io", "someone/app", "latest")),
    ("localhost:5000/app:1", ("localhost:5000", "app", "1")),
])
def test_pin_check_parses_image_names(image, parts):
    assert _pins_module().parse_image(image) == parts


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_registry(manifests):
    """An opener: 401 + Bearer challenge without a token, then MANIFESTS[url] (a status)."""
    def opener(req):
        url = req.full_url
        if "/token?" in url:
            return _Resp(b'{"token": "t"}')
        if req.get_header("Authorization") is None:
            raise urllib.error.HTTPError(url, 401, "auth", {
                "WWW-Authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io"'}, None)
        status = manifests.get(url, 404)
        if status == "offline":
            raise urllib.error.URLError("no such host")
        if status != 200:
            raise urllib.error.HTTPError(url, status, "x", {}, None)
        return _Resp(b"")
    return opener


def test_pin_check_tells_offered_gone_and_no_answer():
    mod = _pins_module()
    ok = "https://ghcr.io/v2/qubins/images/manifests/2.5-xl"
    opener = _fake_registry({ok: 200,
                             "https://ghcr.io/v2/x/down/manifests/1": "offline"})
    assert mod.offered("ghcr.io/qubins/images:2.5-xl", opener) == "ok"
    assert mod.offered("ghcr.io/qubins/images@sha256:aaa", opener) == "gone"
    assert mod.offered("ghcr.io/x/down:1", opener).startswith("error")


def test_pin_check_reads_the_shipped_manifests():
    images = dict(_pins_module().manifest_images(_ROOT))
    lab = json.load(open(os.path.join(_MANIFESTS, "rq_demo_quantum-lab.json")))["entrypoint"]
    assert images[lab["docker_image"]] == "quantum-lab docker_image"
    assert images[lab["docker_image_fallback"]] == "quantum-lab docker_image_fallback"


def _online():
    try:
        socket.create_connection(("ghcr.io", 443), timeout=3).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(os.environ.get("RQ_OFFLINE") == "1" or not _online(),
                    reason="ghcr.io not reachable (offline)")
def test_every_pinned_image_is_still_offered():
    # the shipped manifests only: the catalogue is the daily workflow's part
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _pins_module().main([_ROOT, "--no-catalogue"])
    out = buf.getvalue()
    if rc == 2:
        pytest.skip("a registry did not answer:\n" + out)
    assert rc == 0, out
