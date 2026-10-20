"""
Tests for the Pi's start URL: rasqberry.org with the image build, Pi model and
LED layout for the RasQberry helper, and nothing that names the Pi or its person.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "RQB2-bin"))

import rq_desktop_session as ds  # noqa: E402


def _files(tmp_path, version="beta-2026-10-10-053754\n", env=""):
    vf = tmp_path / "rasqberry-version"
    if version is not None:
        vf.write_text(version)
    ef = tmp_path / "env"
    ef.write_text(env)
    return str(vf), str(ef)


def test_all_facts(tmp_path):
    vf, ef = _files(tmp_path, env="PI_MODEL=Pi5\nLED_LAYOUT=quad-4x12\nLED_LAYOUT_VERIFIED=true\n")
    assert ds.start_url(vf, ef) == ("https://rasqberry.org/?from=pi&assistant=1&v=beta-2026-10-10-053754"
                                    "&model=pi5&led=quad-4x12&ledcheck=true")


def test_missing_facts_are_left_out(tmp_path):
    vf, ef = _files(tmp_path, version=None, env="")
    assert ds.start_url(vf, ef) == "https://rasqberry.org/?from=pi&assistant=1&ledcheck=false"


def test_odd_values_are_left_out_the_layout_stays_when_skipped(tmp_path):
    vf, ef = _files(tmp_path, version="dev build; rm -rf\n",
                    env="PI_MODEL=Pi3\nLED_LAYOUT=single-24x8\nLED_LAYOUT_VERIFIED=skipped\n")
    assert ds.start_url(vf, ef) == "https://rasqberry.org/?from=pi&assistant=1&led=single-24x8&ledcheck=skipped"


def test_fresh_card(tmp_path):
    vf, ef = _files(tmp_path, env="PI_MODEL=Pi4\nLED_LAYOUT=single-24x8\nLED_LAYOUT_VERIFIED=false\n")
    assert ds.start_url(vf, ef).endswith("&led=single-24x8&ledcheck=false")


def test_quoted_values_and_pi4(tmp_path):
    vf, ef = _files(tmp_path, env='PI_MODEL="Pi4"\nLED_LAYOUT="single-24x8"\n')
    assert ds.start_url(vf, ef).endswith("&model=pi4&led=single-24x8&ledcheck=false")


def test_the_browser_opens_the_start_url():
    src = open(os.path.join(_ROOT, "RQB2-bin", "rq_desktop_session.py")).read()
    assert "url = start_url() if online() else OFFLINE_PAGE" in src
