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
import rq_led_wizard_probe as pw  # noqa: E402


# ---------------------------------------------------------------------------
# Simulated answer sets - one per shipped preset. These describe what a user
# would physically observe for each wiring; the inference must map each back to
# its preset by mapping equivalence.
# ---------------------------------------------------------------------------

PRESET_ANSWERS = {
    "single-24x8": {
        # single-24x8 is TOP-LEFT origin (no y_flip): pixel 0 sits top-left.
        "arrangement": "single", "panel_width": 24, "panel_height": 8,
        "panel_count": 1, "first_pixel_corner": "top-left",
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


def _maps_identical(name_a, name_b):
    """True if two presets produce the same (x,y)->index map over their grid."""
    la, lb = lu.get_layout(name_a), lu.get_layout(name_b)
    if (la["width"], la["height"]) != (lb["width"], lb["height"]):
        return False
    for y in range(la["height"]):
        for x in range(la["width"]):
            if lu.map_xy_to_pixel(x, y, layout=name_a) != \
               lu.map_xy_to_pixel(x, y, layout=name_b):
                return False
    return True


@pytest.mark.parametrize("preset_name", sorted(PRESET_ANSWERS.keys()))
def test_each_preset_recoverable(preset_name):
    """Every shipped preset is recovered from its simulated answer set.

    single-24x8 and triple-8x8 are the SAME top-origin column-serpentine map (one
    24-wide panel vs three 8-wide), so the matcher may return either name for
    those two - accept any map-identical preset rather than the exact string."""
    status, name, layout = w.resolve(PRESET_ANSWERS[preset_name])
    assert status == "preset", f"{preset_name}: expected a preset match, got {status}/{name}"
    assert name == preset_name or _maps_identical(name, preset_name), \
        f"expected {preset_name} (or a map-identical preset), inferred {name}"
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
# quad-4x12 ground truth (Pi 4 rig, measured 2026-07-13)
#
# The rig quad has mixed per-panel start corners (top panels start top-left,
# bottom panels start top-right) that the single-corner general inference cannot
# express, so quad-4x12 is a NAMED standard selected directly by the wizard, not
# recovered from a PRESET_ANSWERS set. These tests pin the preset to the exact
# index->coordinate formula measured on the physical panel.
# ---------------------------------------------------------------------------

def _quad_4x12_measured_coord(idx):
    """Rig-measured chain-index -> (x, y) for the quad-4x12 mounting (2026-07-13).

    base=48*p; n=idx-base; c=n//4 (column in chain order); r=n%4.
    TOP panels (p0 top-left, p1 top-left/right region) start top-left and their
    first column DESCENDS -> y_top = r on even columns, 3-r on odd.
    BOTTOM panels (p2, p3) start BOTTOM-right and their first column ASCENDS from
    the bottom edge -> region y_bot = 3-r on even columns, r on odd; y = 4+y_bot.
    Anchors: idx0=(0,0), idx48=(12,0), idx96=(23,7), idx144=(11,7).
    """
    p = idx // 48
    n = idx - p * 48
    c = n // 4
    r = n % 4
    if p == 0:
        y_top = r if c % 2 == 0 else 3 - r
        return (c, y_top)
    if p == 1:
        y_top = r if c % 2 == 0 else 3 - r
        return (12 + c, y_top)
    y_bot = (3 - r) if c % 2 == 0 else r
    if p == 2:
        return (23 - c, 4 + y_bot)
    return (11 - c, 4 + y_bot)


def test_quad_4x12_matches_measured_rig_mapping():
    """quad-4x12 reproduces the Pi 4 rig's measured index->coord formula exactly."""
    for idx in range(192):
        x, y = _quad_4x12_measured_coord(idx)
        assert lu.map_xy_to_pixel(x, y, layout="quad-4x12") == idx, \
            f"quad-4x12: pixel {idx} expected at ({x},{y})"


def test_quad_4x12_is_a_bijection_over_24x8():
    """Every logical (x,y) in the 24x8 matrix maps to a unique pixel in 0..191."""
    seen = set()
    for y in range(8):
        for x in range(24):
            idx = lu.map_xy_to_pixel(x, y, layout="quad-4x12")
            assert idx is not None and 0 <= idx < 192, f"({x},{y}) -> {idx}"
            assert idx not in seen, f"duplicate pixel {idx} at ({x},{y})"
            seen.add(idx)
    assert len(seen) == 192


def test_quad_4x12_equals_legacy_quad_y_flipped():
    """The corrected rig quad is EXACTLY the legacy quad-2x2-12x4 y-flipped.

    Cross-validation: quad-4x12 was authored from the Pi 4 re-probe (2026-07-13,
    bottom panels start lower-right) and quad-2x2-12x4 from the legacy arithmetic,
    yet they agree pixel-for-pixel under a global y-flip. Two independently-derived
    maps coinciding is strong evidence the re-probed geometry is right. (The
    earlier mis-read 'top-right' bottom panels did NOT produce this equality.)
    """
    for y in range(8):
        for x in range(24):
            assert lu.map_xy_to_pixel(x, y, layout="quad-4x12") == \
                lu.map_xy_to_pixel(x, 7 - y, layout="quad-2x2-12x4"), \
                f"quad-4x12 should equal quad-2x2-12x4 y-flipped at ({x},{y})"


# ---------------------------------------------------------------------------
# Standards-first: x_flip mapper support + apply_standard / flipped_variant
# ---------------------------------------------------------------------------

def test_x_flip_mirrors_columns():
    """x_flip mirrors the logical x axis before the panel walk (like y_flip does y)."""
    import copy
    base = lu._load_layouts()["triple-8x8"]   # no flips shipped -> clean baseline
    flipped = copy.deepcopy(base)
    flipped["x_flip"] = True
    width, height = base["width"], base["height"]
    for y in range(height):
        for x in range(width):
            assert lu.map_xy_to_pixel(x, y, layout=flipped) == \
                lu.map_xy_to_pixel(width - 1 - x, y, layout=base)


def test_apply_standard_no_flip_returns_base_preset():
    """With no flip correction, a standard resolves straight to its base preset."""
    status, name, layout = w.apply_standard("quad-4x12")
    assert status == "preset" and name == "quad-4x12"


def test_apply_standard_unknown_raises():
    with pytest.raises(w.WizardInferenceError):
        w.apply_standard("no-such-layout")


@pytest.mark.parametrize("base", ["single-24x8", "quad-4x12", "triple-8x8"])
@pytest.mark.parametrize("tx,ty", [(True, False), (False, True), (True, True)])
def test_flipped_variant_corrects_relative_to_base(base, tx, ty):
    """flipped_variant(base, tx, ty).map(x,y) == base.map(mirror_x, mirror_y).

    This is the exact correction contract: a panel mounted mirrored on an axis is
    fixed by asking the base preset for the mirror-image coordinate.
    """
    layout = w.flipped_variant(base, tx, ty)
    width, height = layout["width"], layout["height"]
    for y in range(height):
        for x in range(width):
            xx = (width - 1 - x) if tx else x
            yy = (height - 1 - y) if ty else y
            assert lu.map_xy_to_pixel(x, y, layout=layout) == \
                lu.map_xy_to_pixel(xx, yy, layout=base), \
                f"{base} flip(x={tx},y={ty}) wrong at ({x},{y})"


def test_flipped_variant_sets_flag_on_noflip_base():
    """single-24x8 is now top-origin (no flip), so toggling y SETS y_flip."""
    layout = w.flipped_variant("single-24x8", toggle_x=False, toggle_y=True)
    assert layout.get("y_flip", False) is True    # false XOR toggle -> true
    layout2 = w.flipped_variant("single-24x8", toggle_x=True, toggle_y=False)
    assert layout2.get("x_flip", False) is True   # false XOR toggle -> true
    assert layout2.get("y_flip", False) is False  # untouched, stays false


def test_flipped_variant_toggle_clears_a_baked_in_flag():
    """XOR semantics: toggling an axis on a base that ALREADY ships that flip
    CLEARS it (does not stack) - kept as coverage even though no shipped preset
    carries a flip today."""
    registry = {
        "flipped-base": {
            "width": 24, "height": 8, "y_flip": True,
            "panels": [{"w": 24, "h": 8, "origin": [0, 0],
                        "serpentine": "column", "start": "top-left"}],
        }
    }
    layout = w.flipped_variant("flipped-base", toggle_x=False, toggle_y=True,
                               registry=registry)
    assert layout.get("y_flip", False) is False   # true XOR toggle -> false


def test_apply_standard_flip_is_valid_bijection():
    """A 180-degree-corrected standard still maps every coord to a unique pixel."""
    status, name, layout = w.apply_standard("quad-4x12", toggle_x=True, toggle_y=True)
    assert status in ("preset", "custom")
    seen = set()
    for y in range(layout["height"]):
        for x in range(layout["width"]):
            idx = lu.map_xy_to_pixel(x, y, layout=layout)
            assert idx is not None and idx not in seen
            seen.add(idx)
    assert len(seen) == 192


def test_cli_standard_mode(capsys):
    """The --standard CLI path prints 'PRESET <name>' for an unflipped standard."""
    rc = w.main(["--standard", "quad-4x12"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "PRESET quad-4x12"


def _footprint(layout, n):
    """Set of logical (x, y) whose chain index is < n (the lit signature area)."""
    ldef = lu.get_layout(layout)
    fp = set()
    for y in range(ldef["height"]):
        for x in range(ldef["width"]):
            idx = lu.map_xy_to_pixel(x, y, layout=layout)
            if idx is not None and idx < n:
                fp.add((x, y))
    return fp


def test_signature_probe_distinguishes_all_three_standards():
    """The first-48-pixel signature paints a distinct footprint per standard, so a
    single probe + question identifies the layout (plan R1, Jan 2026-07-13)."""
    quad = _footprint("quad-4x12", 48)
    single = _footprint("single-24x8", 48)
    triple = _footprint("triple-8x8", 48)

    # quad's 4-tall columns -> a WIDE, SHORT 12x4 block (the top-left quarter).
    assert quad == {(x, y) for y in range(4) for x in range(12)}
    # single/triple's 8-tall columns -> a NARROW, TALL 6x8 strip up the left side.
    strip = {(x, y) for y in range(8) for x in range(6)}
    assert single == strip and triple == strip
    # So quad is unmistakably different from the strip layouts...
    assert quad != strip
    # ...and single vs triple are now the SAME top-origin map (pixel 0 at the
    # top-left for both): a 3x8x8 is wired like a single-24x8, so the wizard
    # treats them as one. Both put chain 0 at logical (0,0).
    assert lu.map_xy_to_pixel(0, 0, layout="single-24x8") == 0
    assert lu.map_xy_to_pixel(0, 0, layout="triple-8x8") == 0
    assert _maps_identical("single-24x8", "triple-8x8")


def _twoblock_fingerprint(base, tx, ty):
    """Coloured-cell map of the two-block signature (R=0-47, G=144-191, W=0-3)
    as physically seen for a `base` panel mounted with the given flips."""
    _, _, layout = w.apply_standard(base, toggle_x=tx, toggle_y=ty)
    fp = {}
    for y in range(layout["height"]):
        for x in range(layout["width"]):
            idx = lu.map_xy_to_pixel(x, y, layout=layout)
            if idx is None:
                continue
            if idx in pw._WHITE_MARKER_INDICES:
                fp[(x, y)] = "W"
            elif idx < 48:
                fp[(x, y)] = "R"
            elif idx >= 144:
                fp[(x, y)] = "G"
    return fp


def test_twoblock_signature_distinguishes_all_eight_states():
    """The two-block + white-marker image is unique for each of the 8 real states
    (single/quad x normal/x-flip/y-flip/180) - so the wizard can identify any
    mounting from one image. The white marker is essential: without it single's
    normal vs y-flip (and x-flip vs 180) would be identical full-height strips."""
    states = [("single-24x8", tx, ty) for tx in (False, True) for ty in (False, True)] \
        + [("quad-4x12", tx, ty) for tx in (False, True) for ty in (False, True)]
    fps = [_twoblock_fingerprint(*s) for s in states]
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            assert fps[i] != fps[j], f"{states[i]} and {states[j]} look identical"

    # And the white marker specifically is what separates single's y states:
    assert _twoblock_fingerprint("single-24x8", False, False) != \
        _twoblock_fingerprint("single-24x8", False, True)


@pytest.mark.parametrize("base", ["single-24x8", "quad-4x12"])
@pytest.mark.parametrize("tx,ty", [(False, False), (True, False), (False, True), (True, True)])
def test_glyph_preview_matches_saved_layout(base, tx, ty):
    """The glyph preview maps identically to the layout apply_standard would save.

    Critical: the operator confirms orientation from the glyph, so the previewed
    layout MUST equal the one written to LED_LAYOUT, or they'd confirm one
    orientation and get another.
    """
    eff = pw._effective_glyph_layout(base, tx, ty)
    _, _, saved = w.apply_standard(base, toggle_x=tx, toggle_y=ty)
    width, height = saved["width"], saved["height"]
    for y in range(height):
        for x in range(width):
            assert lu.map_xy_to_pixel(x, y, layout=eff) == \
                lu.map_xy_to_pixel(x, y, layout=saved), \
                f"{base} flip(x={tx},y={ty}): preview != saved at ({x},{y})"


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


# ---------------------------------------------------------------------------
# Render-mode env override (fix F1) - the wizard's render-hold mechanism.
#
# The wizard holds each probe pattern lit across the whiptail prompt by running
# the persistent renderer and routing probes through it in service mode. It
# switches a probe subprocess into service mode via an os.environ override
# (LED_RENDER_MODE=service) rather than rewriting the root-owned env file. These
# tests pin that seam: get_led_config()['render_mode'] must honour the override.
# ---------------------------------------------------------------------------

def test_render_mode_env_override_forces_service(monkeypatch):
    """LED_RENDER_MODE=service in the environment switches render_mode, so the
    wizard can route probes through the renderer without touching the env file."""
    monkeypatch.setenv("LED_RENDER_MODE", "service")
    assert lu.get_led_config()["render_mode"] == "service"


def test_render_mode_defaults_to_direct_without_override(monkeypatch):
    """With no override the default direct mode is used (probe opens GPIO)."""
    monkeypatch.delenv("LED_RENDER_MODE", raising=False)
    assert lu.get_led_config()["render_mode"] == "direct"


def test_render_mode_override_is_case_insensitive(monkeypatch):
    """The override is lower-cased like the file value, so 'SERVICE' works too."""
    monkeypatch.setenv("LED_RENDER_MODE", "SERVICE")
    assert lu.get_led_config()["render_mode"] == "service"


# ---------------------------------------------------------------------------
# Virtual-GUI singleton / reaper (plan R1 follow-up).
#
# With LED_VIRTUAL=true (the shipped default) every probe/demo process that
# enables a virtual target auto-launches the on-screen emulator. These tests pin
# the pidfile/liveness bookkeeping that keeps exactly ONE window and lets the
# wizard reap it on exit - WITHOUT spawning any real GUI (only the helpers are
# exercised). They are portable: _gui_pid_alive branches on /proc existence.
# ---------------------------------------------------------------------------

def test_gui_pid_alive_rejects_bogus_pids():
    """None / 0 / negative are never a live GUI."""
    assert lu._gui_pid_alive(None) is False
    assert lu._gui_pid_alive(0) is False
    assert lu._gui_pid_alive(-1) is False


def test_gui_pid_alive_false_for_unused_pid():
    """A PID that maps to no process is not a live GUI (Linux /proc or os.kill)."""
    assert lu._gui_pid_alive(2_000_000_000) is False


def test_read_gui_pid_roundtrip(tmp_path, monkeypatch):
    """_read_gui_pid parses the pidfile; a missing or garbage file yields None."""
    pidfile = tmp_path / "gui.pid"
    monkeypatch.setattr(lu, "_VIRTUAL_GUI_PIDFILE", str(pidfile))
    assert lu._read_gui_pid() is None            # missing file
    pidfile.write_text("4321\n")
    assert lu._read_gui_pid() == 4321
    pidfile.write_text("not-a-pid")
    assert lu._read_gui_pid() is None            # garbage


def test_reap_is_idempotent_without_pidfile(tmp_path, monkeypatch):
    """Reaping when nothing is tracked is a safe no-op (wizard cleanup path)."""
    pidfile = tmp_path / "gui.pid"
    monkeypatch.setattr(lu, "_VIRTUAL_GUI_PIDFILE", str(pidfile))
    lu.reap_virtual_led_gui()                    # must not raise
    assert not pidfile.exists()


def test_reap_clears_stale_pidfile(tmp_path, monkeypatch):
    """A pidfile naming a dead process is cleared so it cannot mislead later."""
    pidfile = tmp_path / "gui.pid"
    pidfile.write_text("2000000000")             # not a live process
    monkeypatch.setattr(lu, "_VIRTUAL_GUI_PIDFILE", str(pidfile))
    lu.reap_virtual_led_gui()
    assert not pidfile.exists()


def test_reap_only_touches_pidfile_not_pgrep(tmp_path, monkeypatch):
    """reap_virtual_led_gui reaps ONLY the pidfile-tracked GUI (one WE spawned);
    a hand-started window with no pidfile is left alone - so it never consults
    the pgrep fallback that _running_gui_pid uses for the singleton check."""
    pidfile = tmp_path / "gui.pid"
    monkeypatch.setattr(lu, "_VIRTUAL_GUI_PIDFILE", str(pidfile))

    called = {"pgrep": False}
    real_read = lu._read_gui_pid

    def _tracking_running_pid():
        called["pgrep"] = True
        return 4321
    monkeypatch.setattr(lu, "_running_gui_pid", _tracking_running_pid)

    lu.reap_virtual_led_gui()                    # no pidfile -> nothing to reap
    assert called["pgrep"] is False              # never fell back to pgrep


# ---------------------------------------------------------------------------
# Logo-based standards wizard (Jan 2026-07-13): render the IBM logo THROUGH each
# candidate layout; only the geometry that matches the physical panel forms the
# upright logo, the wrong one scatters it. These pin that discrimination with no
# LED hardware - just the shared mapper + the probe's IBM bitmap.
# ---------------------------------------------------------------------------

def _logo_bitmap():
    """The IBM bitmap as a plain filled/blank grid (colour letters -> '#')."""
    return tuple(row.replace('I', '#').replace('B', '#').replace('M', '#')
                 for row in pw._IBM_LOGO)


def _logo_on_single_panel(via_layout):
    """Physical render of the IBM logo (drawn THROUGH `via_layout`) on a panel
    that is physically wired as single-24x8: chain k sits at single-24x8's
    inverse map, so drawing through single-24x8 is the identity."""
    inv = {}
    for y in range(8):
        for x in range(24):
            inv[lu.map_xy_to_pixel(x, y, layout="single-24x8")] = (x, y)
    grid = [[' '] * 24 for _ in range(8)]
    for y, row in enumerate(pw._IBM_LOGO):
        for x, cell in enumerate(row):
            if cell != ' ':
                px, py = inv[lu.map_xy_to_pixel(x, y, layout=via_layout)]
                grid[py][px] = '#'
    return tuple(''.join(r) for r in grid)


def test_logo_reads_upright_only_through_matching_geometry():
    """On a single-wired panel the IBM logo drawn through single-24x8 reproduces
    the upright bitmap; drawn through quad-4x12 it scatters (does NOT) - which is
    exactly the signal the operator judges in the alternating blue/red display."""
    assert _logo_on_single_panel("single-24x8") == _logo_bitmap()
    assert _logo_on_single_panel("quad-4x12") != _logo_bitmap()


def test_logo_render_differs_between_single_and_quad():
    """The single-map and quad-map logo renders light different pixel sets, so
    the alternating blue/red display shows two visibly distinct images."""
    def lit(layout):
        return {lu.map_xy_to_pixel(x, y, layout=layout)
                for y, row in enumerate(pw._IBM_LOGO)
                for x, cell in enumerate(row) if cell != ' '}
    assert lit("single-24x8") != lit("quad-4x12")


def test_logo_bitmap_is_top_origin():
    """The probe's IBM bitmap is top-origin (row 0 is the top of the logo)."""
    assert pw._IBM_LOGO[0] == "IIIIII  BBBBB   M     M "
    assert pw._IBM_LOGO[-1] == "IIIIII  BBBBB   MM   MM "
