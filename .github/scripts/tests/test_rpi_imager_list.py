"""
rpi-imager.json, the sublist for the official Raspberry Pi Imager
(rpi_imager_list.py): what goes in, Imager's schema, and that a list that
fails is never written.

    python3 -m pytest .github/scripts/tests -q
"""
import copy
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rpi_imager_list as ril  # noqa: E402

GH = "https://github.com/JanLahmann/RasQberry-Two/releases/download"


def _release(branch, stamp, published, ab=True, std=True):
    """A release's RQB-images.json as consolidate-json.yaml downloads it."""
    tag = f"{branch}-{stamp}"
    day = stamp[:10]
    os_list = []
    if std:
        os_list.append({
            "name": "RasQberry Two Beta (64-bit)" if branch == "beta" else "RasQberry Two (64-bit)",
            "description": "RasQberry beta release with latest features (may be unstable)",
            "icon": "https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png",
            "url": f"{GH}/{tag}/rasqberry-{branch}-{day}.img.xz",
            "extract_size": 9076473856,
            "extract_sha256": "6e7642344407cd6904a4cf34c73409f33da2224cf89dda2a4de7a10c45229994",
            "image_download_size": 1645458180,
            "image_sha256": "9cbfafcd4ec4a3a4e1b4ba2610498e7aab1c949e0783a63846d9b831f45b5e2e",
            "release_date": day,
            "init_format": "systemd",
            "devices": ["pi5-64bit", "pi4-64bit"],
            "website": "https://rasqberry.org",
            "image_type": "standard",
        })
    if ab:
        os_list.append({
            "name": "RasQberry Two Beta A/B (64-bit)",
            "description": "RasQberry beta release with A/B boot support",
            "icon": "https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png",
            "url": f"{GH}/{tag}/rasqberry-{branch}-{day}-ab.img.xz",
            "extract_size": 12398362624,
            "extract_sha256": "6a5c427bcad75f328b195a49c6217bb62abe8f9a9161f0ce09d779aa3575dbf7",
            "image_download_size": 1663679844,
            "image_sha256": "38f912f8c0608c6104f2f16930c38b5d55336e0b748b45c0585a20c3a086117a",
            "release_date": day,
            "init_format": "systemd",
            "devices": ["pi5-64bit", "pi4-64bit"],
            "website": "https://rasqberry.org",
            "image_type": "ab",
        })
    return {"imager": {"latest_version": "1.8.5"}, "os_list": os_list,
            "_release_tag": tag, "_branch": branch, "_published": published}


BETA_OLD = _release("beta", "2026-09-30-221656", "2026-09-30T20:17:00Z")
BETA = _release("beta", "2026-10-04-143935", "2026-10-04T12:40:11Z")
DEV = _release("development", "2026-10-06-003602", "2026-10-05T22:36:41Z")
for _e in DEV["os_list"]:
    _e["release_date"] = "2026-10-06 00:36"
STABLE = _release("main", "2026-11-20-101500", "2026-11-20T09:15:00Z")


def _dir(tmp_path, *releases):
    d = tmp_path / "release-json"
    d.mkdir()
    for r in releases:
        (d / f"{r['_release_tag']}.json").write_text(json.dumps(r))
    return d


def _sizes(doc):
    return {e["url"]: e["image_download_size"] for e in doc["os_list"]}


def test_newest_beta_until_a_stable_exists(tmp_path):
    doc = ril.build_sublist(ril.load_releases(_dir(tmp_path, BETA_OLD, BETA, DEV)))
    assert set(doc) == {"os_list"}  # no "imager" key in a sublist
    ab, std = doc["os_list"]
    assert "/beta-2026-10-04-143935/" in ab["url"] and ab["url"].endswith("-ab.img.xz")
    assert "/beta-2026-10-04-143935/" in std["url"] and not std["url"].endswith("-ab.img.xz")
    assert ab["name"] == "RasQberry Two Beta" and std["name"] == "RasQberry Two Beta — single system"
    assert ab["description"].startswith("Recommended.")
    assert ril.check_sublist(doc) == []


def test_stable_only_once_a_stable_exists(tmp_path):
    doc = ril.build_sublist(ril.load_releases(_dir(tmp_path, BETA, STABLE, DEV)))
    assert all("/main-2026-11-20-101500/" in e["url"] for e in doc["os_list"])
    assert [e["name"] for e in doc["os_list"]] == ["RasQberry Two", "RasQberry Two — single system"]


def test_entry_fields(tmp_path):
    ab, std = ril.build_sublist(ril.load_releases(_dir(tmp_path, BETA)))["os_list"]
    src = {e["image_type"]: e for e in BETA["os_list"]}
    assert ab["image_download_sha256"] == src["ab"]["image_sha256"]
    assert ab["extract_sha256"] == src["ab"]["extract_sha256"] and ab["extract_size"] == src["ab"]["extract_size"]
    assert std["image_download_size"] == src["standard"]["image_download_size"]
    for e in (ab, std):
        assert e["release_date"] == "2026-10-04"
        assert e["devices"] == ["pi5-64bit", "pi4-64bit"]
        assert e["architecture"] == "armv8" and e["init_format"] == "systemd"
        assert e["website"] == "https://rasqberry.org"
        assert e["icon"] == "https://rasqberry.org/imager/rasqberry-40.png"
        assert "image_type" not in e and "image_sha256" not in e
        # the user, never the password
        assert "Username is always rasqberry" in e["description"] and "Qiskit1!" not in e["description"]
        # Connect: on since its rig test (2026-10-07)
        assert e["capabilities"] == ["rpi_connect"]


def test_rpi_connect_is_one_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(ril, "RPI_CONNECT", True)
    doc = ril.build_sublist(ril.load_releases(_dir(tmp_path, BETA)))
    assert all(e["capabilities"] == ["rpi_connect"] for e in doc["os_list"])
    assert ril.check_sublist(doc) == []


def test_release_date_is_a_plain_date(tmp_path):
    beta = copy.deepcopy(BETA)
    for e in beta["os_list"]:
        e["release_date"] = "2026-10-04 14:39"
    doc = ril.build_sublist(ril.load_releases(_dir(tmp_path, beta)))
    assert {e["release_date"] for e in doc["os_list"]} == {"2026-10-04"}


@pytest.mark.parametrize("releases", [(), (DEV,)], ids=["nothing", "dev-only"])
def test_no_release_no_list(tmp_path, releases):
    with pytest.raises(ril.SublistError):
        ril.build_sublist(ril.load_releases(_dir(tmp_path, *releases)))


@pytest.mark.parametrize("missing", ["ab", "std"])
def test_both_images_or_none(tmp_path, missing):
    beta = _release("beta", "2026-10-04-143935", "2026-10-04T12:40:11Z",
                    ab=missing != "ab", std=missing != "std")
    with pytest.raises(ril.SublistError):
        ril.build_sublist(ril.load_releases(_dir(tmp_path, beta)))


def _valid():
    return ril.build_sublist([BETA])


@pytest.mark.parametrize("break_it,why", [
    (lambda d: d.update(imager={"latest_version": "2.0"}), "imager"),
    (lambda d: d.update(os_list=[]), "empty"),
    (lambda d: d["os_list"][0].pop("extract_sha256"), "extract_sha256"),
    (lambda d: d["os_list"][0].update(extract_size="12398362624"), "extract_size"),
    (lambda d: d["os_list"][0].update(release_date="2026-10-04 14:39"), "release_date"),
    (lambda d: d["os_list"][0].update(init_format="cloud-init"), "init_format"),
    (lambda d: d["os_list"][0].update(devices=["pi5"]), "devices"),
    (lambda d: d["os_list"][0].update(icon="https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png"), "icon"),
    (lambda d: d["os_list"][0].update(capabilities=["rpi-connect"]), "capabilities"),
    (lambda d: d["os_list"][0].update(description="Login rasqberry / Qiskit1!"), "password"),
    (lambda d: d["os_list"].append({"name": "Folder", "description": "x", "subitems": []}), "folder"),
], ids=lambda x: x if isinstance(x, str) else "")
def test_check_catches(break_it, why):
    doc = _valid()
    break_it(doc)
    assert ril.check_sublist(doc), why


def test_vendored_schema_is_imagers():
    schema = json.loads(ril.SCHEMA_FILE.read_text())
    assert schema["title"] == "Imager oslist.json schema"
    image = schema["properties"]["os_list"]["items"]["anyOf"][0]
    assert "extract_sha256" in image["required"] and "rpi_connect" in image["properties"]["capabilities"]["items"]["enum"]


def test_icon_is_40px_with_transparency():
    im = Image.open(ril.ICON_FILE)
    assert im.format == "PNG" and im.size == (40, 40) and im.mode == "RGBA"
    assert im.getchannel("A").getextrema()[0] == 0  # transparent corners
    assert " " not in ril.ICON_URL and ril.ICON_URL.endswith("/" + ril.ICON_PATH)


def test_url_check_wants_the_listed_size():
    doc = _valid()
    sizes = _sizes(doc)
    assert ril.check_urls(doc, head=lambda u: sizes[u]) == []
    wrong = ril.check_urls(doc, head=lambda u: sizes[u] - 1)
    assert len(wrong) == 2 and "the list says" in wrong[0]

    def gone(url):
        raise OSError("HTTP Error 404: Not Found")
    assert len(ril.check_urls(doc, head=gone)) == 2


def test_written_with_its_icon(tmp_path):
    out = tmp_path / "public" / "rpi-imager.json"
    sizes = _sizes(ril.build_sublist([BETA]))
    assert ril.write_sublist(_dir(tmp_path, BETA, DEV), out, head=lambda u: sizes[u])
    assert json.loads(out.read_text()) == ril.build_sublist([BETA])
    assert (out.parent / "imager" / "rasqberry-40.png").read_bytes() == ril.ICON_FILE.read_bytes()


@pytest.mark.parametrize("case", ["no-release", "url-gone"])
def test_a_failing_list_keeps_the_previous_one(tmp_path, case, capsys):
    out = tmp_path / "rpi-imager.json"
    out.write_text("previous\n")

    def gone(url):
        raise OSError("HTTP Error 404: Not Found")
    releases = _dir(tmp_path, DEV) if case == "no-release" else _dir(tmp_path, BETA)
    assert not ril.write_sublist(releases, out, head=gone)
    assert out.read_text() == "previous\n"
    assert "::error" in capsys.readouterr().out


def test_check_command_on_a_file(tmp_path):
    f = tmp_path / "rpi-imager.json"
    f.write_text(json.dumps(_valid()))
    assert ril.main(["--check", str(f), "--no-url-check"]) == 0
    f.write_text(json.dumps({"os_list": []}))
    assert ril.main(["--check", str(f), "--no-url-check"]) == 1
