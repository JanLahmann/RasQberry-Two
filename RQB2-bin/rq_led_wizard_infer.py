#!/usr/bin/env python3
"""
RasQberry LED setup wizard - layout inference (pure, testable).

This module turns the answers a user gives to the whiptail walkthrough
(rq_led_setup_wizard.sh) into a concrete LED layout definition and matches it
against the shipped registry presets. It is the "brain" of the wizard.

Design notes:
- The core inference (:func:`infer_layout`) is a PURE function: answers dict ->
  layout dict. It performs NO hardware access and imports nothing at module
  level that would fail on CI. Hardware- and registry-touching code
  (rq_led_utils) is imported lazily inside the functions that need it, so
  ``import rq_led_wizard_infer`` always succeeds.
- Preset matching is done by MAPPING EQUIVALENCE, not structural equality: a
  candidate layout matches a preset when both produce the identical
  (x, y) -> chain-index mapping for every logical coordinate. This elegantly
  handles equivalent-but-differently-described wirings - e.g. a single 24x8
  panel observed as "pixel 0 at bottom-left" reproduces the shipped
  ``single-24x8`` preset, which encodes the same physical wiring via y_flip +
  top-left start.

Credit: the probe/observe/infer approach is adapted (with credit, per plan
decision D3) from barkol's diagnose_wiring.py, shared in
JanLahmann/RasQberry-Two#261. barkol's script prints raw questions for a human
to report; this module formalises the same observations into an answer schema
and derives the layout automatically.

Answer schema (all keys the wizard collects; see rq_led_setup_wizard.sh):
    arrangement        'single' | 'chain-horizontal' | 'grid-2x2'
    panel_width        int  > 0   physical panel width  (columns)
    panel_height       int  > 0   physical panel height (rows)
    panel_count        int  > 0   number of physical panels
    first_pixel_corner 'top-left'|'top-right'|'bottom-left'|'bottom-right'
                                  corner where chain pixel 0 physically lit
    run_axis           'vertical' | 'horizontal'
                                  direction the first contiguous run travelled
                                  (vertical -> column serpentine, horizontal -> row)
    wiring             'serpentine' | 'progressive'
                                  whether alternate rows/columns reverse
    chain_start        'left' | 'right'   (chain-horizontal only; default 'left')
                                  which side of the matrix holds panel 0
    upper_bound_leds   int, optional      safety cap the user gave before probing;
                                  a contradiction (derived count exceeds it) is an error
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_CORNERS = ('top-left', 'top-right', 'bottom-left', 'bottom-right')
VALID_ARRANGEMENTS = ('single', 'chain-horizontal', 'grid-2x2')


class WizardInferenceError(ValueError):
    """Raised when the answer set is invalid or self-contradictory.

    A ValueError subclass so callers that only catch ValueError still work.
    Carries a human-readable message suitable for a whiptail msgbox.
    """


def _require_int(answers, key, minimum=1):
    """Fetch answers[key] as an int >= minimum or raise WizardInferenceError."""
    if key not in answers:
        raise WizardInferenceError(f"missing required answer: '{key}'")
    try:
        value = int(answers[key])
    except (TypeError, ValueError):
        raise WizardInferenceError(f"answer '{key}' must be a whole number, got {answers[key]!r}")
    if value < minimum:
        raise WizardInferenceError(f"answer '{key}' must be >= {minimum}, got {value}")
    return value


def _require_choice(answers, key, valid):
    """Fetch answers[key] and ensure it is one of `valid`, else raise."""
    if key not in answers:
        raise WizardInferenceError(f"missing required answer: '{key}'")
    value = answers[key]
    if value not in valid:
        raise WizardInferenceError(
            f"answer '{key}'={value!r} is not one of {', '.join(valid)}"
        )
    return value


def _serpentine_axis(run_axis):
    """Map the observed first-run direction to a panel serpentine axis."""
    return 'column' if run_axis == 'vertical' else 'row'


def _make_panel(w, h, origin, serpentine, start, zigzag):
    """Build one panel dict; omit zigzag when True to match shipped-preset shape."""
    panel = {
        'w': w,
        'h': h,
        'origin': list(origin),
        'serpentine': serpentine,
        'start': start,
    }
    if not zigzag:
        panel['zigzag'] = False
    return panel


def _legacy_quad_panels():
    """The exact legacy quad-2x2-12x4 panel chain (see led-layouts.json).

    The legacy quad wiring snakes bottom-left -> bottom-right -> top-right ->
    top-left with alternating panel start corners - a non-obvious boustrophedon
    the original authors themselves mis-documented. The wizard recognises the
    2x2-grid-of-12x4 arrangement as this known template rather than trying to
    reconstruct its mixed-orientation chain from first principles.
    """
    return [
        {'w': 12, 'h': 4, 'origin': [0, 4], 'serpentine': 'column', 'start': 'bottom-left'},
        {'w': 12, 'h': 4, 'origin': [12, 4], 'serpentine': 'column', 'start': 'bottom-left'},
        {'w': 12, 'h': 4, 'origin': [12, 0], 'serpentine': 'column', 'start': 'top-right'},
        {'w': 12, 'h': 4, 'origin': [0, 0], 'serpentine': 'column', 'start': 'top-right'},
    ]


def infer_layout(answers):
    """
    Infer an LED layout definition from wizard answers (pure function).

    Args:
        answers (dict): The observations gathered by the walkthrough (see the
            module docstring for the schema).

    Returns:
        dict: A layout definition in led-layouts.json shape, with keys
            'description', 'width', 'height', 'panels' (and 'zigzag': False on
            panels for progressive wiring). Not augmented with 'name'/'count'.

    Raises:
        WizardInferenceError: if the answers are missing, out of range, or
            mutually contradictory (e.g. grid-2x2 with panel_count != 4, or a
            derived count exceeding the user's stated safe upper bound).
    """
    if not isinstance(answers, dict):
        raise WizardInferenceError("answers must be a dict")

    arrangement = _require_choice(answers, 'arrangement', VALID_ARRANGEMENTS)
    pw = _require_int(answers, 'panel_width')
    ph = _require_int(answers, 'panel_height')
    count = _require_int(answers, 'panel_count')
    start = _require_choice(answers, 'first_pixel_corner', VALID_CORNERS)
    run_axis = _require_choice(answers, 'run_axis', ('vertical', 'horizontal'))
    wiring = _require_choice(answers, 'wiring', ('serpentine', 'progressive'))

    serpentine = _serpentine_axis(run_axis)
    zigzag = (wiring == 'serpentine')

    if arrangement == 'single':
        if count != 1:
            raise WizardInferenceError(
                f"'single' arrangement needs panel_count=1, got {count}"
            )
        width, height = pw, ph
        panels = [_make_panel(pw, ph, (0, 0), serpentine, start, zigzag)]

    elif arrangement == 'chain-horizontal':
        chain_start = answers.get('chain_start', 'left')
        if chain_start not in ('left', 'right'):
            raise WizardInferenceError(
                f"chain_start must be 'left' or 'right', got {chain_start!r}"
            )
        width, height = pw * count, ph
        panels = []
        for i in range(count):
            # Panel 0 sits on the chain_start side; successive panels tile across.
            slot = i if chain_start == 'left' else (count - 1 - i)
            panels.append(
                _make_panel(pw, ph, (slot * pw, 0), serpentine, start, zigzag)
            )

    else:  # grid-2x2
        if count != 4:
            raise WizardInferenceError(
                f"'grid-2x2' arrangement needs panel_count=4, got {count}"
            )
        width, height = pw * 2, ph * 2
        if pw == 12 and ph == 4:
            # Known legacy quad template - reproduce its exact chain/mapping.
            panels = _legacy_quad_panels()
        else:
            # Best-effort uniform 2x2 grid, chained row-major (top-left first),
            # every panel same serpentine/start. Documented approximation for
            # non-legacy grid hardware.
            logger.warning(
                "grid-2x2 at %dx%d is not the legacy quad geometry; emitting a "
                "best-effort uniform grid (verify orientation on hardware)", pw, ph
            )
            panels = []
            for gy in range(2):
                for gx in range(2):
                    panels.append(
                        _make_panel(pw, ph, (gx * pw, gy * ph),
                                    serpentine, start, zigzag)
                    )

    derived = sum(p['w'] * p['h'] for p in panels)

    upper_bound = answers.get('upper_bound_leds')
    if upper_bound is not None:
        try:
            upper_bound = int(upper_bound)
        except (TypeError, ValueError):
            raise WizardInferenceError(
                f"upper_bound_leds must be a whole number, got {upper_bound!r}"
            )
        if derived > upper_bound:
            raise WizardInferenceError(
                f"inferred layout needs {derived} LEDs but the stated safe "
                f"upper bound is {upper_bound}; re-check the panel size/count"
            )

    layout = {
        'description': (
            f"Custom layout from LED setup wizard: {width}x{height}, "
            f"{count} panel(s) of {pw}x{ph}, {serpentine} {wiring}, "
            f"pixel 0 at {start}."
        ),
        'width': width,
        'height': height,
        'panels': panels,
    }
    return layout


def suggest_name(layout):
    """Suggest a stable custom registry name for an inferred layout dict."""
    return f"custom-{layout['width']}x{layout['height']}"


def _mapping_signature(layout_def, width, height):
    """Compute the full (x, y) -> chain-index mapping for a layout dict.

    Imports rq_led_utils lazily (its hardware deps are themselves lazy, so this
    stays CI-safe) to reuse the canonical registry-driven mapper - no duplicate
    walk logic to drift out of sync.
    """
    import rq_led_utils as lu
    sig = {}
    for y in range(height):
        for x in range(width):
            sig[(x, y)] = lu.map_xy_to_pixel(x, y, layout=layout_def)
    return sig


def match_preset(layout, registry=None):
    """
    Return the name of a registry preset whose mapping equals `layout`, or None.

    Matching is by full mapping equivalence over the whole grid, so a custom
    layout that is physically identical to a preset (even if described
    differently) is recognised.

    Args:
        layout (dict): An inferred layout definition (from infer_layout).
        registry (dict, optional): name -> layout-def mapping to search. When
            None, the live registry from rq_led_utils is used.

    Returns:
        str or None: Matching preset name, or None if the layout is novel.
    """
    width, height = layout['width'], layout['height']
    candidate_sig = _mapping_signature(layout, width, height)

    if registry is None:
        import rq_led_utils as lu
        registry = lu._load_layouts()

    for name, preset in registry.items():
        if preset.get('width') != width or preset.get('height') != height:
            continue
        try:
            preset_sig = _mapping_signature(preset, width, height)
        except Exception:  # pragma: no cover - defensive against malformed presets
            continue
        if preset_sig == candidate_sig:
            return name
    return None


def flipped_variant(base_name, toggle_x, toggle_y, registry=None):
    """Build a flip-corrected copy of a base preset for a rotated mounting.

    The wizard renders a candidate standard, and if the operator reports it looks
    flipped, corrects it by mirroring the axis/axes. A panel physically mounted
    mirrored on an axis is corrected by TOGGLING that axis flip relative to the
    base preset (so a 180-degree/upside-down mounting toggles BOTH axes). The
    toggle is relative to the base's own flags, so it composes correctly even for
    presets that already ship a flip (e.g. single-24x8 has y_flip=true).

    Args:
        base_name (str): a registry preset name.
        toggle_x (bool): mirror left/right relative to the base.
        toggle_y (bool): mirror top/bottom relative to the base.
        registry (dict, optional): preset registry (defaults to live registry).

    Returns:
        dict: a layout dict (base geometry + corrected x_flip/y_flip flags).

    Raises:
        WizardInferenceError: if base_name is not a known preset.
    """
    if registry is None:
        import rq_led_utils as lu
        registry = lu._load_layouts()
    if base_name not in registry:
        raise WizardInferenceError(f"unknown base preset: {base_name!r}")

    import copy
    base = registry[base_name]
    layout = {
        'description': base.get('description', ''),
        'width': base['width'],
        'height': base['height'],
        'panels': copy.deepcopy(base['panels']),
    }
    x_flip = bool(base.get('x_flip', False)) ^ bool(toggle_x)
    y_flip = bool(base.get('y_flip', False)) ^ bool(toggle_y)
    if x_flip:
        layout['x_flip'] = True
    if y_flip:
        layout['y_flip'] = True
    return layout


def _flip_suffix(toggle_x, toggle_y):
    """Stable name suffix describing which mirror the wizard applied."""
    if toggle_x and toggle_y:
        return 'rot180'
    if toggle_x:
        return 'flipx'
    if toggle_y:
        return 'flipy'
    return ''


def apply_standard(base_name, toggle_x=False, toggle_y=False, registry=None):
    """Resolve a chosen standard (optionally flip-corrected) to a layout to apply.

    Args:
        base_name (str): the standard preset the wizard identified.
        toggle_x, toggle_y (bool): flip corrections the operator asked for.
        registry (dict, optional): preset registry (defaults to live registry).

    Returns:
        tuple: (status, name, layout). With no flip, this is the base preset
            as-is. With a flip, the corrected layout is matched against the
            registry: if some existing preset already reproduces it, that preset
            is returned ('preset'); otherwise a named custom variant ('custom').

    Raises:
        WizardInferenceError: if base_name is unknown.
    """
    if not toggle_x and not toggle_y:
        if registry is None:
            import rq_led_utils as lu
            registry = lu._load_layouts()
        if base_name not in registry:
            raise WizardInferenceError(f"unknown base preset: {base_name!r}")
        return 'preset', base_name, registry[base_name]

    layout = flipped_variant(base_name, toggle_x, toggle_y, registry=registry)
    matched = match_preset(layout, registry=registry)
    if matched is not None:
        return 'preset', matched, layout
    return 'custom', f"{base_name}-{_flip_suffix(toggle_x, toggle_y)}", layout


def resolve(answers, registry=None):
    """
    High-level helper: infer a layout, then match it to a preset.

    Args:
        answers (dict): wizard answers.
        registry (dict, optional): preset registry (defaults to live registry).

    Returns:
        tuple: (status, name, layout) where status is 'preset' or 'custom',
            name is the preset name or a suggested custom name, and layout is
            the inferred layout dict.

    Raises:
        WizardInferenceError: on invalid/contradictory answers.
    """
    layout = infer_layout(answers)
    matched = match_preset(layout, registry=registry)
    if matched is not None:
        return 'preset', matched, layout
    return 'custom', suggest_name(layout), layout


# ---------------------------------------------------------------------------
# CLI entry point (used by rq_led_setup_wizard.sh)
# ---------------------------------------------------------------------------

def _write_custom_entry(name, layout):
    """Merge a custom layout into the user-local overlay file; return its path.

    Uses rq_led_utils._user_layouts_file() so the path matches what the loader
    reads back. Creates the directory and file as needed. The caller (root, in
    the raspi-config context) is expected to fix ownership afterwards.
    """
    import json
    import os
    import rq_led_utils as lu

    path = lu._user_layouts_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    data = {}
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except Exception:
            logger.warning("existing user overlay %s unreadable; recreating", path)
            data = {}

    entry = dict(layout)
    entry['description'] = layout.get('description', '') + " (wizard)"
    data[name] = entry

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    return path


def main(argv=None):
    """CLI: read an answers JSON file, print '<STATUS> <name>', optionally commit.

    Contract with the shell wizard:
      stdout: exactly one line 'PRESET <name>' or 'CUSTOM <name>' on success.
      exit 0 success, 2 on a clear inference error (message on stderr).
      --commit : when the result is custom, write it to the user overlay first.
      --json   : dump the full result as JSON to stdout instead (diagnostics/tests).
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="LED setup wizard inference")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument('--answers-file',
                     help="JSON file with the wizard answers dict (general inference)")
    src.add_argument('--standard',
                     help="a standard preset name to apply directly (standards-first)")
    parser.add_argument('--flip-x', action='store_true',
                        help="mirror the standard left/right (rotated mounting)")
    parser.add_argument('--flip-y', action='store_true',
                        help="mirror the standard top/bottom (upside-down mounting)")
    parser.add_argument('--commit', action='store_true',
                        help="write a custom (non-preset) layout to the user overlay")
    parser.add_argument('--json', action='store_true',
                        help="emit the full result as JSON")
    args = parser.parse_args(argv)

    try:
        if args.standard:
            status, name, layout = apply_standard(
                args.standard, toggle_x=args.flip_x, toggle_y=args.flip_y)
        else:
            with open(args.answers_file, 'r') as f:
                answers = json.load(f)
            status, name, layout = resolve(answers)
    except WizardInferenceError as e:
        print(str(e), file=sys.stderr)
        return 2
    except OSError as e:
        print(f"could not read answers file: {e}", file=sys.stderr)
        return 2

    path = None
    if status == 'custom' and args.commit:
        try:
            path = _write_custom_entry(name, layout)
        except Exception as e:  # pragma: no cover - filesystem failure
            print(f"failed to write custom layout: {e}", file=sys.stderr)
            return 2

    if args.json:
        out = {
            'status': status,
            'name': name,
            'count': sum(p['w'] * p['h'] for p in layout['panels']),
            'width': layout['width'],
            'height': layout['height'],
            'layout': layout,
        }
        if path:
            out['path'] = path
        print(json.dumps(out, indent=2))
    else:
        print(f"{status.upper()} {name}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
