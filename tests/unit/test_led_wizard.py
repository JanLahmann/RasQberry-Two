#!/usr/bin/env python3
"""
Unit tests for the LED setup wizard inference (rq_led_wizard_infer).

Pure-function tests: no LED hardware, no GPIO, no neopixel/board imports are
exercised. They prove that:
  - every shipped registry preset is recoverable from a simulated answer set
    (mapping-equivalence match),
  - serpentine vs progressive wiring is distinguished,
  - corner/flip choices change the mapping (flip detection),
  - a non-preset answer set yields a valid custom layout dict and no match,
  - out-of-range / contradictory answers raise a clear error, not a crash,
  - the user-local registry overlay wins over shipped presets, so a written
    custom layout is loaded back by rq_led_utils.

Run with:
    python3 -m pytest tests/unit/ -q
"""

import json
import os
import sys

import pytest

# Make RQB2-bin importable (rq_led_* live there; /usr/bin when installed).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO_ROOT, "RQB2-bin"))

import rq_led_wizard_infer as w  # noqa: E402
import rq_led_utils as lu  # noqa: E402


# ---------------------------------------------------------------------------
# Simulated answer sets - one per shipped preset. These describe what a user
# would physically observe for each wiring; the inference must map each back to
# its preset by mapping equivalence.
# ---------------------------------------------------------------------------

PRESET_ANSWERS = {
    "single-24x8": {
        # single-24x8 bakes in y_flip: physically pixel 0 sits bottom-left.
        "arrangement": "single", "panel_width": 24, "panel_height": 8,
        "panel_count": 1, "first_pixel_corner": "bottom-left",
        "run_axis": "vertical", "wiring": "serpentine",
    },
    "single-8x32": {
        "arrangement": "single", "panel_width": 32, "panel_height": 8,
        "panel_count": 1, "first_pixel_corner": "top-left",
        "run_axis": "vertical", "wiring": "serpentine",
    },
    "triple-8x8": {
        "arrangement": "chain-horizontal", "panel_width": 8, "panel_height": 8,
        "panel_count": 3, "first_pixel_corner": "top-left",
        "run_axis": "vertical", "wiring": "serpentine", "chain_start": "left",
    },
    "quad-2x2-12x4": {
        "arrangement": "grid-2x2", "panel_width": 12, "panel_height": 4,
        "panel_count": 4, "first_pixel_corner": "bottom-left",
        "run_axis": "vertical", "wiring": "serpentine",
    },
}


@pytest.mark.parametrize("preset_name", sorted(PRESET_ANSWERS.keys()))
def test_each_preset_recoverable(preset_name):
    """Every shipped preset is recovered from its simulated answer set."""
    status, name, layout = w.resolve(PRESET_ANSWERS[preset_name])
    assert status == "preset", f"{preset_name}: expected a preset match, got {status}/{name}"
    assert name == preset_name, f"expected {preset_name}, inferred {name}"
    # Derived count agrees with the preset's own derived count.
    assert sum(p["w"] * p["h"] for p in layout["panels"]) == lu._layout_count(preset_name)


@pytest.mark.parametrize("preset_name", sorted(PRESET_ANSWERS.keys()))
def test_recovered_mapping_matches_preset_exactly(preset_name):
    """The inferred layout produces the identical (x,y)->index mapping as the preset."""
    _, _, layout = w.resolve(PRESET_ANSWERS[preset_name])
    width, height = layout["width"], layout["height"]
    for y in range(height):
        for x in range(width):
            assert lu.map_xy_to_pixel(x, y, layout=layout) == \
                lu.map_xy_to_pixel(x, y, layout=preset_name), \
                f"{preset_name}: mapping mismatch at ({x},{y})"


# ---------------------------------------------------------------------------
# Serpentine vs progressive
# ---------------------------------------------------------------------------

def _single_answers(**overrides):
    base = {
        "arrangement": "single", "panel_width": 8, "panel_height": 8,
        "panel_count": 1, "first_pixel_corner": "top-left",
        "run_axis": "vertical", "wiring": "serpentine",
    }
    base.update(overrides)
    return base


def test_serpentine_vs_progressive_distinguished():
    """Progressive wiring sets zigzag=False; serpentine omits it, and the two
    produce different mappings on a multi-row/column panel."""
    serp = w.infer_layout(_single_answers(wiring="serpentine"))
    prog = w.infer_layout(_single_answers(wiring="progressive"))

    assert "zigzag" not in serp["panels"][0]          # serpentine == default
    assert prog["panels"][0]["zigzag"] is False        # progressive marked

    serp_map = {(x, y): lu.map_xy_to_pixel(x, y, layout=serp)
                for y in range(8) for x in range(8)}
    prog_map = {(x, y): lu.map_xy_to_pixel(x, y, layout=prog)
                for y in range(8) for x in range(8)}
    assert serp_map != prog_map, "serpentine and progressive should map differently"


def test_progressive_column_runs_do_not_reverse():
    """In a progressive column-serpentine panel, every column runs the same way,
    so column 0 and column 1 both start at y=0 (indices 0 and h)."""
    prog = w.infer_layout(_single_answers(panel_width=4, panel_height=4,
                                          wiring="progressive"))
    assert lu.map_xy_to_pixel(0, 0, layout=prog) == 0
    assert lu.map_xy_to_pixel(1, 0, layout=prog) == 4   # progressive: col1 also starts at top
    # Serpentine equivalent reverses column 1 (top of col1 is the LAST index of that column).
    serp = w.infer_layout(_single_answers(panel_width=4, panel_height=4,
                                          wiring="serpentine"))
    assert lu.map_xy_to_pixel(1, 0, layout=serp) == 7


# ---------------------------------------------------------------------------
# Flip detection (start corner changes the mapping)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("corner", list(w.VALID_CORNERS))
def test_start_corner_propagates_to_panel(corner):
    """The observed first-pixel corner becomes the panel start corner."""
    layout = w.infer_layout(_single_answers(first_pixel_corner=corner))
    assert layout["panels"][0]["start"] == corner


def test_flip_changes_mapping():
    """Different corners (x-flip and y-flip) yield different chain mappings."""
    tl = w.infer_layout(_single_answers(first_pixel_corner="top-left"))
    tr = w.infer_layout(_single_answers(first_pixel_corner="top-right"))   # x flip
    bl = w.infer_layout(_single_answers(first_pixel_corner="bottom-left"))  # y flip

    p_tl = lu.map_xy_to_pixel(0, 0, layout=tl)
    p_tr = lu.map_xy_to_pixel(0, 0, layout=tr)
    p_bl = lu.map_xy_to_pixel(0, 0, layout=bl)
    assert p_tl != p_tr, "x-flip should move logical (0,0) to a different pixel"
    assert p_tl != p_bl, "y-flip should move logical (0,0) to a different pixel"


def test_run_axis_selects_serpentine_axis():
    """Vertical first-run => column serpentine; horizontal => row serpentine."""
    vert = w.infer_layout(_single_answers(run_axis="vertical"))
    horiz = w.infer_layout(_single_answers(run_axis="horizontal"))
    assert vert["panels"][0]["serpentine"] == "column"
    assert horiz["panels"][0]["serpentine"] == "row"


# ---------------------------------------------------------------------------
# Custom (non-preset) result
# ---------------------------------------------------------------------------

def test_custom_layout_is_valid_and_unmatched():
    """A novel geometry yields a valid layout dict and no preset match."""
    answers = _single_answers(panel_width=16, panel_height=16)
    status, name, layout = w.resolve(answers)
    assert status == "custom"
    assert name == "custom-16x16"
    # Valid layout dict: dimensions, panels, derived count.
    assert layout["width"] == 16 and layout["height"] == 16
    assert layout["panels"], "custom layout must have at least one panel"
    assert sum(p["w"] * p["h"] for p in layout["panels"]) == 256
    # And it maps cleanly through the generic mapper (every coord unique).
    seen = set()
    for y in range(16):
        for x in range(16):
            idx = lu.map_xy_to_pixel(x, y, layout=layout)
            assert idx is not None and idx not in seen
            seen.add(idx)
    assert len(seen) == 256


def test_chain_start_right_reverses_panel_order():
    """chain_start='right' places panel 0 on the right-hand side."""
    left = w.infer_layout(_single_answers(arrangement="chain-horizontal",
                                          panel_count=3, chain_start="left"))
    right = w.infer_layout(_single_answers(arrangement="chain-horizontal",
                                           panel_count=3, chain_start="right"))
    assert left["panels"][0]["origin"] == [0, 0]
    assert right["panels"][0]["origin"] == [16, 0]   # rightmost slot (2*8)


# ---------------------------------------------------------------------------
# Error handling: out-of-bounds / contradictory answers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("answers", [
    {},                                                   # empty
    _single_answers(panel_width=0),                        # zero width
    _single_answers(panel_height=-4),                      # negative height
    _single_answers(panel_count=0),                        # zero count
    _single_answers(arrangement="bogus"),                  # bad arrangement
    _single_answers(first_pixel_corner="middle"),          # bad corner
    _single_answers(run_axis="diagonal"),                  # bad axis
    _single_answers(wiring="magic"),                       # bad wiring
    _single_answers(arrangement="grid-2x2", panel_count=3),  # grid needs 4
    _single_answers(arrangement="single", panel_count=2),  # single needs 1
    _single_answers(panel_width="abc"),                    # non-numeric
])
def test_bad_answers_raise_clear_error(answers):
    """Invalid or contradictory answers raise WizardInferenceError, not crash."""
    with pytest.raises(w.WizardInferenceError):
        w.infer_layout(answers)


def test_upper_bound_contradiction_raises():
    """A derived count exceeding the stated safe upper bound is a contradiction."""
    answers = _single_answers(panel_width=32, panel_height=8, upper_bound_leds=100)
    with pytest.raises(w.WizardInferenceError):
        w.infer_layout(answers)   # 256 > 100


def test_upper_bound_ok_when_within_budget():
    """Within the budget, the upper bound is accepted."""
    answers = _single_answers(panel_width=8, panel_height=8, upper_bound_leds=100)
    layout = w.infer_layout(answers)   # 64 <= 100
    assert layout["width"] == 8 and layout["height"] == 8


def test_non_dict_answers_raise():
    """A non-dict answers argument fails cleanly."""
    with pytest.raises(w.WizardInferenceError):
        w.infer_layout(["not", "a", "dict"])


# ---------------------------------------------------------------------------
# User-local registry overlay (rq_led_utils) - custom layouts win over shipped
# ---------------------------------------------------------------------------

def test_user_overlay_wins_and_is_loaded(tmp_path, monkeypatch):
    """A custom layout written to the user overlay is loaded back by
    rq_led_utils, and a user entry overrides a shipped preset of the same name."""
    # Point USER_HOME at a temp dir so _user_layouts_file resolves under it.
    monkeypatch.setenv("USER_HOME", str(tmp_path))
    overlay_dir = tmp_path / ".local" / "config"
    overlay_dir.mkdir(parents=True)
    overlay = overlay_dir / "led-layouts.json"

    # A brand-new custom layout plus an override of a shipped preset name.
    overlay.write_text(json.dumps({
        "custom-16x16": {
            "description": "test custom",
            "width": 16, "height": 16,
            "panels": [{"w": 16, "h": 16, "origin": [0, 0],
                        "serpentine": "column", "start": "top-left"}],
        },
        # Same NAME as a shipped preset but different geometry -> user must win.
        "single-8x32": {
            "description": "overridden",
            "width": 8, "height": 8,
            "panels": [{"w": 8, "h": 8, "origin": [0, 0],
                        "serpentine": "row", "start": "top-left"}],
        },
    }))

    # Reset the module-level cache so the overlay is picked up.
    lu._layouts_cache = None
    lu._layouts_cache_key = None
    try:
        custom = lu.get_layout("custom-16x16")
        assert custom is not None and custom["count"] == 256

        overridden = lu.get_layout("single-8x32")
        assert overridden["width"] == 8 and overridden["height"] == 8, \
            "user overlay must WIN over the shipped preset of the same name"
    finally:
        # Clear cache so later tests see the shipped-only registry again.
        lu._layouts_cache = None
        lu._layouts_cache_key = None


def test_resolve_via_registry_argument_is_hardware_free():
    """match_preset accepts an explicit registry, so matching needs no files."""
    registry = {
        "my-8x8": {
            "width": 8, "height": 8,
            "panels": [{"w": 8, "h": 8, "origin": [0, 0],
                        "serpentine": "column", "start": "top-left"}],
        }
    }
    layout = w.infer_layout(_single_answers(panel_width=8, panel_height=8))
    assert w.match_preset(layout, registry=registry) == "my-8x8"
