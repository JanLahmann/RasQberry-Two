#!/usr/bin/env python3
"""
Unit tests for the learner-facing LED API in rq_led_utils (R-129, R-157).

- get_led_config() parses the env file once and again only after it changes,
  so map_xy_to_pixel(x, y) in a per-pixel loop no longer re-reads the file for
  every pixel (3.2 s per 24x8 frame on a Pi 4 before).
- matrix_size() and set_xy() let a program address LEDs by (x, y) without
  knowing the wiring, and drawing off the edge is ignored instead of raising.

No hardware: the strip is a plain list.
"""

import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_utils as lu  # noqa: E402


def _parse_env(path):
    """Minimal KEY=value parser standing in for dotenv_values."""
    values = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
    return values


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """A private env file plus a parse counter; the module cache starts empty."""
    path = tmp_path / "rasqberry_environment.env"
    path.write_text("LED_LAYOUT=single-24x8\nLED_DEFAULT_BRIGHTNESS=0.4\n")
    calls = []

    def counting_parser(p):
        calls.append(p)
        return _parse_env(p)

    monkeypatch.setattr(lu, "ENV_FILE", str(path))
    monkeypatch.setattr(lu, "dotenv_values", counting_parser)
    monkeypatch.setattr(lu, "_env_cache", None)
    monkeypatch.setattr(lu, "_env_cache_key", None)
    monkeypatch.delenv("LED_RENDER_MODE", raising=False)
    return path, calls


def test_env_file_is_parsed_once_for_a_whole_frame(env_file):
    _, calls = env_file
    for y in range(8):
        for x in range(24):
            assert lu.map_xy_to_pixel(x, y) is not None
    assert len(calls) == 1


def test_env_file_is_parsed_again_after_it_changes(env_file):
    path, calls = env_file
    assert lu.get_led_config()["led_layout"] == "single-24x8"
    path.write_text("LED_LAYOUT=quad-4x12\nLED_DEFAULT_BRIGHTNESS=0.4\n")
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    assert lu.get_led_config()["led_layout"] == "quad-4x12"
    assert len(calls) == 2


def test_render_mode_override_still_applies_with_a_cached_file(env_file, monkeypatch):
    assert lu.get_led_config()["render_mode"] == "direct"
    monkeypatch.setenv("LED_RENDER_MODE", "service")
    assert lu.get_led_config()["render_mode"] == "service"


def test_missing_env_file_falls_back_to_defaults_and_reports_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lu, "ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setattr(lu, "_env_cache", None)
    monkeypatch.setattr(lu, "_env_cache_key", None)
    for _ in range(5):
        assert lu.get_led_config()["led_count"] == 192
    assert capsys.readouterr().out.count("Config file not found") == 1


def test_matrix_size_of_presets_and_configured_layout(env_file):
    assert lu.matrix_size("single-24x8") == (24, 8)
    assert lu.matrix_size("quad-4x12") == (24, 8)
    assert lu.matrix_size() == (24, 8)


def test_set_xy_sets_the_mapped_led(env_file):
    pixels = [(0, 0, 0)] * 192
    assert lu.set_xy(pixels, 5, 3, (255, 0, 0)) is True
    assert pixels[lu.map_xy_to_pixel(5, 3)] == (255, 0, 0)
    assert sum(1 for p in pixels if p != (0, 0, 0)) == 1


@pytest.mark.parametrize("x,y", [(-1, 0), (24, 0), (0, -1), (0, 8), (100, 100)])
def test_set_xy_ignores_positions_off_the_matrix(env_file, x, y):
    pixels = [(0, 0, 0)] * 192
    assert lu.set_xy(pixels, x, y, (255, 0, 0)) is False
    assert all(p == (0, 0, 0) for p in pixels)


def test_set_xy_follows_an_explicit_layout(env_file):
    pixels = [(0, 0, 0)] * 192
    lu.set_xy(pixels, 0, 0, (1, 2, 3), layout="quad-4x12")
    assert pixels[lu.map_xy_to_pixel(0, 0, layout="quad-4x12")] == (1, 2, 3)


def test_pi4_permission_error_names_rq_python(monkeypatch):
    monkeypatch.setattr(lu.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(lu.sys, "argv", ["/home/rasqberry/my_leds.py"])
    error = lu._with_root_hint(RuntimeError("NeoPixel support requires running with sudo, please try again!"))
    assert isinstance(error, RuntimeError)
    assert "rq_python my_leds.py" in str(error)


def test_other_errors_and_root_get_no_hint(monkeypatch):
    original = RuntimeError("GPIO busy")
    monkeypatch.setattr(lu.os, "geteuid", lambda: 1000)
    assert lu._with_root_hint(original) is original
    monkeypatch.setattr(lu.os, "geteuid", lambda: 0)
    sudo_error = RuntimeError("requires running with sudo")
    assert lu._with_root_hint(sudo_error) is sudo_error
