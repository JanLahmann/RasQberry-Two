"""
Tests for Fun with Quantum on RasQberry Two: the notebook variants and their
submenu in the menu cache, the offline website bundle (URL, SHA-256, safe
unpacking) and the family page and menu generated from family.json.
"""

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.error

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "RQB2-bin"))

import rq_fwq  # noqa: E402

_MANIFEST = os.path.join(_ROOT, "RQB2-config", "demo-manifests", "rq_demo_fun-with-quantum.json")
_GEN = os.path.join(_ROOT, "RQB2-bin", "rq_demo_generate_menu.sh")
_MENU = os.path.join(_ROOT, "RQB2-config", "RQB2_menu.sh")
_SH = shutil.which("dash") or "/bin/sh"
_SHA = "aa6474614ef1c07b18a4d7ce568eed228d71a273"

# The game notebooks at the root of the pinned Fun-with-Quantum commit
_NOTEBOOKS = {"Readme.ipynb", "Quantum-Coin-Game.ipynb", "GHZ-Game.ipynb",
              "Hardys-Paradox.ipynb", "Mermin-Peres-Game.ipynb", "3sat.ipynb",
              "CHSH-Game.ipynb", "Prisoners-Dilemma.ipynb", "GHZ-on-Real-Devices.ipynb"}


def _manifest():
    with open(_MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------
# Variants and the submenu
# ----------------------------------------------------------------------------

def test_one_variant_per_game_notebook_plus_website_and_family():
    m = _manifest()
    assert m["menu"]["variant_menu"] is True
    variants = {v["id"]: v for v in m["variants"]}
    notebooks = {v["args"][0] for v in m["variants"] if v["entrypoint"]["type"] == "jupyter"}
    assert notebooks == _NOTEBOOKS
    # ids the desktop icons and tests use stay
    assert variants["readme"]["args"] == ["Readme.ipynb"]
    assert variants["coin-game"]["args"] == ["Quantum-Coin-Game.ipynb"]
    # non-notebook entries set their type, or they would inherit "jupyter"
    assert variants["website"]["entrypoint"] == {"type": "script", "launcher": "rq_fwq_portal.sh"}
    assert variants["family"]["entrypoint"] == {"type": "script", "launcher": "rq_fwq_family.sh"}
    assert m["install"]["post_install"] == "rq_fwq.py"
    for launcher in ("rq_fwq_portal.sh", "rq_fwq_family.sh", "rq_fwq.py"):
        assert os.access(os.path.join(_ROOT, "RQB2-bin", launcher), os.X_OK), launcher


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("jq") is None,
                    reason="bash and jq are required")
def test_menu_cache_lists_the_variants(tmp_path):
    cache = tmp_path / "cache.sh"
    env = dict(os.environ, USER_HOME=str(tmp_path / "home"),
               RQ_CONFIG_FILE=str(tmp_path / "none"))
    proc = subprocess.run(["bash", _GEN, "--cache", str(cache)], capture_output=True,
                          text=True, env=env, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert subprocess.run([_SH, "-n", str(cache)]).returncode == 0
    script = ('. "$1"; eval "set -- $(demo_variant_items fun-with-quantum | tr \'\\n\' \' \')"; '
              'printf "%s\\n" "$@"; demo_variant_items quantum-lab || echo none')
    out = subprocess.run([_SH, "-c", script, "sh", str(cache)], capture_output=True,
                         text=True).stdout.splitlines()
    pairs = dict(zip(out[0:-1:2], out[1:-1:2]))
    assert list(pairs) == [v["id"] for v in _manifest()["variants"]]
    assert pairs["hardys-paradox"] == "Hardy's Paradox"
    assert out[-1] == "none"   # demos without variant_menu start directly


def test_raspi_config_menu_opens_the_variant_submenu():
    text = open(_MENU, encoding="utf-8").read()
    assert 'demo_variant_items "$FUN"' in text
    assert 'run_engine_demo "$BIN_DIR/rq_demo_run.sh" "$_dv_id" "$_dv_sel"' in text
    assert subprocess.run([_SH, "-n", _MENU]).returncode == 0


# ----------------------------------------------------------------------------
# Website bundle
# ----------------------------------------------------------------------------

def test_bundle_urls():
    url, sha_url = rq_fwq.bundle_urls(_SHA.upper())
    assert url == ("https://github.com/JanLahmann/Fun-with-Quantum/releases/download/"
                   "portal-bundles/fwq-portal-offline-%s.tar.gz" % _SHA)
    assert sha_url == url + ".sha256"
    for bad in ("", "aa64746", _SHA + "0", "../" + _SHA[3:]):
        with pytest.raises(ValueError):
            rq_fwq.bundle_name(bad)


def test_parse_sha256():
    name = rq_fwq.bundle_name(_SHA)
    digest = "ab" * 32
    assert rq_fwq.parse_sha256("%s  %s\n" % (digest, name), name) == digest
    assert rq_fwq.parse_sha256("%s *%s" % (digest.upper(), name), name) == digest
    assert rq_fwq.parse_sha256(digest, name) == digest
    with pytest.raises(rq_fwq.BundleError):
        rq_fwq.parse_sha256("%s  other.tar.gz" % digest, name)
    with pytest.raises(rq_fwq.BundleError):
        rq_fwq.parse_sha256("not a hash  %s" % name, name)


def _tar(files, links=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, target in links:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    return buf.getvalue()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(bundle, sha_text=None, missing=False):
    name = rq_fwq.bundle_name(_SHA)
    if sha_text is None:
        sha_text = "%s  %s\n" % (hashlib.sha256(bundle).hexdigest(), name)
    calls = []

    def opener(url, timeout=None):
        calls.append(url)
        if missing:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return _Resp(sha_text.encode() if url.endswith(".sha256") else bundle)
    opener.calls = calls
    return opener


def test_fetch_portal_unpacks_a_verified_bundle(tmp_path):
    bundle = _tar({"./index.html": b"<h1>FwQ</h1>", "./play/index.html": b"play"})
    old = tmp_path / "portal" / "dist"
    old.mkdir(parents=True)
    (old / "stale.html").write_text("old")
    site = rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=_opener(bundle))
    assert (tmp_path / "portal" / "dist" / "index.html").read_bytes() == b"<h1>FwQ</h1>"
    assert (tmp_path / "portal" / "dist" / "play" / "index.html").exists()
    assert not (old / "stale.html").exists()
    assert site == str(old)


def test_fetch_portal_refuses_a_wrong_checksum(tmp_path):
    bundle = _tar({"./index.html": b"x"})
    bad = "%s  %s" % ("0" * 64, rq_fwq.bundle_name(_SHA))
    with pytest.raises(rq_fwq.BundleError, match="mismatch"):
        rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=_opener(bundle, bad))
    assert not (tmp_path / "portal" / "dist").exists()


@pytest.mark.parametrize("files,links", [
    ({"../evil.html": b"x", "./index.html": b"x"}, ()),
    ({"./index.html": b"x"}, [("./link", "/etc/passwd")]),
])
def test_fetch_portal_refuses_unsafe_entries(tmp_path, files, links):
    with pytest.raises(rq_fwq.BundleError):
        rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=_opener(_tar(files, links)))
    assert not (tmp_path / "evil.html").exists()
    assert not (tmp_path / "portal" / "dist").exists()
    assert not [p for p in (tmp_path / "portal").iterdir()]   # no temp dir left


def test_unpublished_bundle_is_reported_as_missing(tmp_path):
    opener = _opener(b"", missing=True)
    with pytest.raises(rq_fwq.BundleMissing):
        rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=opener)
    assert opener.calls == [rq_fwq.bundle_urls(_SHA)[1]]   # stops after the .sha256
    assert rq_fwq.bundle_published(_SHA, opener=opener) is False


# ----------------------------------------------------------------------------
# Family page and menu
# ----------------------------------------------------------------------------

_FAMILY = {
    "brand": {"name": "Fun with Quantum"},
    "members": [
        {"id": "fun-with-quantum", "name": "Fun with Quantum", "url": "https://fun-with-quantum.org",
         "short": "Games", "tagline": "The family portal"},
        {"id": "rasqberry-two", "name": "RasQberry Two", "url": "https://rasqberry.org",
         "short": "Pi model", "tagline": "Model of IBM Quantum System Two"},
        {"id": "quantego", "name": "Quantego", "url": "https://quantego.org",
         "short": "LEGO", "tagline": "Quantum computers <built> from LEGO"},
        {"id": "qoffee-maker", "name": "Qoffee-Maker", "url": "https://qoffee-maker.org",
         "short": "Coffee", "tagline": "Order coffee with a quantum circuit"},
        {"id": "qubins", "name": "QuBins", "url": "javascript:alert(1)", "short": "Envs"},
        {"id": "racetraq", "name": "racetraQ", "url": "https://github.com/x", "short": "Racing",
         "footer": False},
    ],
}
_LOCAL = {"fun-with-quantum", "qoffee-maker", "quantum-lab", "grok-bloch"}


def test_family_page_from_family_json():
    page = rq_fwq.render_family_html(_FAMILY, _LOCAL)
    assert "<title>Fun with Quantum family</title>" in page
    assert "racetraQ" not in page                       # footer: false = not shown yet
    assert "Quantum computers &lt;built&gt; from LEGO" in page
    assert "javascript:" not in page                     # only https links
    assert page.count("On this Pi</span>") == 3          # FwQ, Qoffee-Maker, QuBins
    assert "You are using it" in page
    assert '<a href="https://quantego.org">Quantego</a>' in page
    assert "http://" not in page and "<script" not in page and "<link" not in page


def test_family_menu_starts_local_demos_and_opens_websites():
    items = rq_fwq.menu_items(_FAMILY, _LOCAL)
    tags = [t for t, _, _ in items]
    assert tags[0] == "page" and "fun-with-quantum" not in tags and "racetraq" not in tags
    actions = {t: a for t, _, a in items}
    assert actions["qoffee-maker"] == "demo:qoffee-maker"
    assert actions["qubins"] == "demo:quantum-lab"
    assert actions["quantego"] == "url:https://quantego.org"
    assert tags.index("qubins") < tags.index("quantego")   # this Pi first
    # not installed here: the website instead of the demo
    assert rq_fwq.menu_items(_FAMILY, set())[1][2].startswith("url:")


def _setup_dirs(tmp_path, portal_ref=""):
    mdir = tmp_path / "manifests"
    mdir.mkdir()
    (mdir / "rq_demo_qoffee-maker.json").write_text('{"id": "qoffee-maker"}')
    (mdir / "rq_demo_schema.json").write_text('{"id": "nope"}')
    (mdir / "rq_demo_broken.json").write_text("{")
    (mdir / "rq_demo_fun-with-quantum.json").write_text(json.dumps(
        {"id": "fun-with-quantum", "install": {"ref": _SHA, "portal_ref": portal_ref}}))
    demo = tmp_path / "fun-with-quantum"
    (demo / "family").mkdir(parents=True)
    (demo / "family" / "family.json").write_text(json.dumps(_FAMILY))
    return mdir, demo


@pytest.mark.parametrize("portal_ref", ["", _SHA])
def test_setup_writes_the_page_and_never_fails_the_install(tmp_path, monkeypatch, portal_ref):
    mdir, demo = _setup_dirs(tmp_path, portal_ref)
    assert rq_fwq.local_demo_ids([str(mdir)]) == {"qoffee-maker", "fun-with-quantum"}
    monkeypatch.setattr(rq_fwq, "manifest_dirs", lambda: [str(mdir)])
    calls = []

    def offline(url, timeout=None):
        calls.append(url)
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(rq_fwq.urllib.request, "urlopen", offline)
    assert rq_fwq.main(["--path", str(demo)]) == 0
    assert "Qoffee-Maker" in (demo / rq_fwq.FAMILY_PAGE).read_text()
    assert not (demo / "portal").exists()
    assert len(calls) == (1 if portal_ref else 0)        # nothing pinned: no request


# ----------------------------------------------------------------------------
# Website pin (install.portal_ref), separate from the notebook pin
# ----------------------------------------------------------------------------

def test_manifest_pins_the_website_separately():
    inst = _manifest()["install"]
    assert inst["ref"] and "portal_ref" in inst and "portal_sha256" in inst
    ref, sha = rq_fwq.portal_pin(_manifest())
    assert ref == inst["portal_ref"].lower()             # empty until a bundle exists
    assert sha == inst["portal_sha256"].lower()
    assert rq_fwq.portal_pin({"install": {"portal_ref": "abc", "portal_sha256": "x"}}) == ("", "")
    assert rq_fwq.portal_pin({"install": {"portal_ref": _SHA.upper(),
                                          "portal_sha256": "AB" * 32}}) == (_SHA, "ab" * 32)
    assert rq_fwq.portal_pin({}) == ("", "")


def test_pinned_sha256_is_used_and_the_copy_is_stamped(tmp_path):
    bundle = _tar({"./index.html": b"x"})
    opener = _opener(bundle, sha_text="ignored")
    rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=opener,
                        sha256=hashlib.sha256(bundle).hexdigest())
    assert opener.calls == [rq_fwq.bundle_urls(_SHA)[0]]  # no .sha256 request
    assert (tmp_path / rq_fwq.PORTAL_STAMP).read_text().strip() == _SHA
    with pytest.raises(rq_fwq.BundleError, match="mismatch"):
        rq_fwq.fetch_portal(str(tmp_path / "b"), _SHA, opener=opener, sha256="0" * 64)


def test_portal_state(tmp_path):
    bundle = _tar({"./index.html": b"x"})
    assert rq_fwq.portal_state(str(tmp_path), "") == "none"
    assert rq_fwq.portal_state(str(tmp_path), _SHA, opener=_opener(bundle)) == "download"
    assert rq_fwq.portal_state(str(tmp_path), _SHA, opener=_opener(b"", missing=True)) == "none"
    rq_fwq.fetch_portal(str(tmp_path), _SHA, opener=_opener(bundle))
    assert rq_fwq.portal_state(str(tmp_path), _SHA, opener=_opener(b"", missing=True)) == "current"
    other = "b" * 40                                     # a newer pin: fetch it
    assert rq_fwq.portal_state(str(tmp_path), other, opener=_opener(bundle)) == "download"
