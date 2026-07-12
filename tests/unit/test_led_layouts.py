#!/usr/bin/env python3
"""
Unit tests for the RasQberry LED layout registry and generic coordinate mapper.

These are pure-function tests: no LED hardware, no GPIO, no neopixel/board
imports are exercised. They validate every layout in led-layouts.json and prove
that the generic registry-driven mapper reproduces the legacy single/quad
arithmetic exactly (the backward-compatibility regression guard).

Run with:
    python3 -m pytest tests/unit/ -q
"""

import os
import sys

import pytest

# Make RQB2-bin importable (rq_led_utils lives there; /usr/bin when installed).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_utils as lu  # noqa: E402


# ---------------------------------------------------------------------------
# Reference implementations: verbatim copies of the ORIGINAL (pre-rework)
# arithmetic. These are the regression oracle - they must NOT be changed to
# match the new code; the new code must match them.
# ---------------------------------------------------------------------------

def _old_single(x, y, width=24, height=8, y_flip=True):
    """Original map_xy_to_pixel_single, with y_flip=true (env default)."""
    if x < 0 or x >= width or y < 0 or y >= height:
        return None
    if y_flip:
        y = height - 1 - y
    if x % 2 == 0:
        return x * height + y
    else:
        return x * height + (height - 1 - y)


def _old_quad(x, y):
    """Original map_xy_to_pixel_quad (from neopixel_spi_IBMtestFunc.py)."""
    if x < 0 or x >= 24 or y < 0 or y >= 8:
        return None
    x1 = x * 4 + (0 if x % 2 == 0 else 3)
    y1 = (7 - y if x % 2 == 0 else y - 7)
    x2 = 96 + (23 - x) * 4 + (0 if x % 2 == 0 else 3)
    y2 = (3 - y if x % 2 == 0 else y - 3)
    return x2 + y2 if y < 4 else x1 + y1


# ---------------------------------------------------------------------------
# Registry fixtures
# ---------------------------------------------------------------------------

def _all_layout_names():
    return sorted(lu._load_layouts().keys())


def test_registry_loads_and_has_required_layouts():
    """The registry parses and contains all Phase A required layouts."""
    names = set(_all_layout_names())
    required = {"single-24x8", "quad-2x2-12x4", "triple-8x8", "single-8x32"}
    assert required.issubset(names), f"missing layouts: {required - names}"


@pytest.mark.parametrize("name", _all_layout_names())
def test_layout_count_matches_panel_sum(name):
    """get_layout()['count'] equals the sum of panel areas."""
    layout = lu.get_layout(name)
    assert layout is not None
    expected = sum(p["w"] * p["h"] for p in layout["panels"])
    assert layout["count"] == expected
    assert lu._layout_count(name) == expected


@pytest.mark.parametrize("name", _all_layout_names())
def test_every_coordinate_maps_to_unique_index(name):
    """(a) Every (x,y) in width x height maps to a unique index in [0, count)."""
    layout = lu.get_layout(name)
    width, height, count = layout["width"], layout["height"], layout["count"]

    seen = {}
    for y in range(height):
        for x in range(width):
            idx = lu.map_xy_to_pixel(x, y, layout=name)
            assert idx is not None, f"{name}: ({x},{y}) unexpectedly mapped to None"
            assert 0 <= idx < count, f"{name}: ({x},{y}) -> {idx} out of [0,{count})"
            assert idx not in seen, (
                f"{name}: index {idx} produced by both {seen.get(idx)} and ({x},{y})"
            )
            seen[idx] = (x, y)

    # Every index in the panel-covered range must be hit exactly once.
    assert len(seen) == width * height
    # For these layouts the panels tile the whole grid, so all indices are used.
    assert sorted(seen.keys()) == list(range(count))


@pytest.mark.parametrize("name", _all_layout_names())
def test_out_of_bounds_returns_none(name):
    """(b) Out-of-bounds coordinates return None."""
    layout = lu.get_layout(name)
    width, height = layout["width"], layout["height"]
    oob = [
        (-1, 0), (0, -1), (-1, -1),
        (width, 0), (0, height), (width, height),
        (width + 5, 3), (3, height + 5),
    ]
    for x, y in oob:
        assert lu.map_xy_to_pixel(x, y, layout=name) is None, (
            f"{name}: ({x},{y}) should be out of bounds"
        )


def test_quad_matches_legacy_arithmetic():
    """(c) quad-2x2-12x4 equals the hardcoded OLD quad arithmetic (regression)."""
    for y in range(8):
        for x in range(24):
            assert lu.map_xy_to_pixel(x, y, layout="quad-2x2-12x4") == _old_quad(x, y), (
                f"quad mismatch at ({x},{y})"
            )


def test_single_matches_legacy_arithmetic_with_yflip():
    """(d) single-24x8 equals the OLD single algorithm with y_flip=true."""
    for y in range(8):
        for x in range(24):
            assert lu.map_xy_to_pixel(x, y, layout="single-24x8") == _old_single(x, y), (
                f"single mismatch at ({x},{y})"
            )


def test_legacy_aliases_route_to_registry_layouts():
    """Legacy 'single'/'quad' aliases behave like their registry counterparts."""
    for x, y in [(0, 0), (5, 3), (23, 7), (12, 4)]:
        assert lu.map_xy_to_pixel(x, y, layout="single") == \
            lu.map_xy_to_pixel(x, y, layout="single-24x8")
        assert lu.map_xy_to_pixel(x, y, layout="quad") == \
            lu.map_xy_to_pixel(x, y, layout="quad-2x2-12x4")


def test_deprecated_wrappers_match_generic_mapper():
    """The kept-for-compat wrappers delegate to the generic mapper."""
    for y in range(8):
        for x in range(24):
            assert lu.map_xy_to_pixel_single(x, y) == \
                lu.map_xy_to_pixel(x, y, layout="single-24x8")
            assert lu.map_xy_to_pixel_quad(x, y) == \
                lu.map_xy_to_pixel(x, y, layout="quad-2x2-12x4")


def test_single_8x32_has_256_pixels():
    """The Pi 5 rig layout is 256 LEDs (first real >192 layout)."""
    assert lu.get_layout("single-8x32")["count"] == 256
