#!/usr/bin/env python3
"""
RasQberry LED setup wizard - probe pattern renderer.

Renders ONE unambiguous probe pattern per invocation on the physical strip so
the whiptail walkthrough (rq_led_setup_wizard.sh) can ask the user what they
see and infer the layout. Patterns light RAW chain indices (physical wiring
order), not logical (x, y) coordinates - the whole point is to reveal the
wiring before any layout is assumed.

Rendering always goes through rq_led_utils.create_neopixel_strip(), never raw
neopixel calls, so it transparently supports both render modes:
  - LED_RENDER_MODE=direct : the library opens the GPIO strip in-process (root).
  - LED_RENDER_MODE=service: the library returns a VirtualNeoPixel that writes
    frames into the mmap; the root rasqberry-led-renderer.service drives the
    physical strip. No code path here needs to know which mode is active - the
    factory decides from the environment file (as every demo does).

SAFETY: these matrices can draw serious current at full white. Probes run at
LOW brightness (default 0.15) and this script hard-caps brightness so a stray
argument cannot blast the strip.

Credit: pattern set adapted (with credit, per plan decision D3) from barkol's
diagnose_wiring.py in JanLahmann/RasQberry-Two#261 - single-pixel, first-run,
second-run (serpentine reveal), panel-boundary and gradient probes.

Usage (one pattern per call):
    rq_led_wizard_probe.py --pattern corner     --count 192 [--index 0]
    rq_led_wizard_probe.py --pattern edge       --count 192 --index 0 --run 8
    rq_led_wizard_probe.py --pattern row2       --count 192 --run 8
    rq_led_wizard_probe.py --pattern gradient   --count 192
    rq_led_wizard_probe.py --pattern boundaries --count 192 --panel 64
    rq_led_wizard_probe.py --pattern clear      --count 192
"""

import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hard safety cap on brightness - probes never need more, and full white on a
# large matrix can exceed the supply's current budget.
MAX_PROBE_BRIGHTNESS = 0.30
DEFAULT_PROBE_BRIGHTNESS = 0.15

# A few visually distinct colours for boundary/gradient probes.
_PALETTE = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (255, 128, 0), (128, 0, 255),
]


def _clamp_brightness(value):
    """Clamp a requested brightness into the safe (0, MAX_PROBE_BRIGHTNESS] band."""
    try:
        b = float(value)
    except (TypeError, ValueError):
        b = DEFAULT_PROBE_BRIGHTNESS
    if b <= 0:
        b = DEFAULT_PROBE_BRIGHTNESS
    if b > MAX_PROBE_BRIGHTNESS:
        logger.warning("brightness %.2f exceeds probe cap; clamping to %.2f",
                       b, MAX_PROBE_BRIGHTNESS)
        b = MAX_PROBE_BRIGHTNESS
    return b


def _make_strip(count, brightness):
    """Create a strip via the library factory (imported lazily => CI-safe import).

    The factory honours LED_RENDER_MODE, so the same call works in direct and
    service mode.
    """
    from rq_led_utils import get_led_config, create_neopixel_strip
    config = get_led_config()
    return create_neopixel_strip(count, config['pixel_order'], brightness=brightness)


def _wheel(pos):
    """Simple 0-255 hue wheel -> (r, g, b), reused from the RasQberry palette."""
    pos &= 255
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    pos -= 170
    return (0, pos * 3, 255 - pos * 3)


def render_pattern(pattern, count, index=0, run=8, panel=64,
                   brightness=DEFAULT_PROBE_BRIGHTNESS):
    """
    Render one probe pattern on the strip and return.

    Args:
        pattern (str): one of corner|edge|row2|gradient|boundaries|clear.
        count (int): total pixels to allocate on the strip (the user's safe
            upper bound / total LED count).
        index (int): starting chain index (corner/edge patterns).
        run (int): run length for edge/row2 patterns (typically panel height).
        panel (int): pixels per panel for the boundaries pattern.
        brightness (float): requested brightness (hard-capped for safety).

    The pattern must stay lit while the shell asks its question, then the shell
    advances to the next pattern (which clears first). Whether the pattern
    survives this process exiting depends on the render mode: in service mode
    the frame is written to the mmap and the persistent renderer latches it, so
    it stays lit; in direct mode the GPIO is deinitialised on exit and the strip
    blanks immediately. The wizard therefore runs its probes in service mode
    (see rq_led_setup_wizard.sh start_render_hold) so the operator still sees
    the pattern when answering.
    """
    brightness = _clamp_brightness(brightness)
    from rq_led_utils import chunked_show

    pixels = _make_strip(count, brightness)
    pixels.fill((0, 0, 0))

    def _set(i, color):
        if 0 <= i < count:
            pixels[i] = color

    if pattern == 'clear':
        chunked_show(pixels)
        return

    if pattern == 'corner':
        # Single pixel at `index` (default chain pixel 0) -> "which corner lit?"
        _set(index, (255, 0, 0))

    elif pattern == 'edge':
        # A short contiguous run from `index` as a green->the-strip gradient,
        # revealing the direction the first run travels (an edge of the panel).
        for k in range(run):
            _set(index + k, (0, 255, 0))
        # Mark the very first pixel red so the user sees where the run starts.
        _set(index, (255, 0, 0))

    elif pattern == 'row2':
        # First run in red, SECOND run in green. If the green run reverses
        # relative to the red one, the wiring is serpentine; if it repeats in
        # the same direction, it is progressive.
        for k in range(run):
            _set(k, (255, 0, 0))
        for k in range(run):
            _set(run + k, (0, 255, 0))

    elif pattern == 'gradient':
        # Whole-strip hue gradient in a few distinct steps -> overview of the
        # chain order across the matrix.
        steps = max(1, count)
        for i in range(count):
            _set(i, _wheel(int(i * 255 / steps)))

    elif pattern == 'boundaries':
        # Light the first pixel of each panel in a distinct colour to reveal
        # panel count and chain order.
        if panel <= 0:
            raise ValueError("--panel must be > 0 for the boundaries pattern")
        p = 0
        start = 0
        while start < count:
            _set(start, _PALETTE[p % len(_PALETTE)])
            start += panel
            p += 1

    else:
        raise ValueError(f"unknown pattern: {pattern}")

    chunked_show(pixels)


def main(argv=None):
    """Parse arguments and render the requested pattern."""
    parser = argparse.ArgumentParser(description="LED setup wizard probe renderer")
    parser.add_argument('--pattern', required=True,
                        choices=['corner', 'edge', 'row2', 'gradient',
                                 'boundaries', 'clear'])
    parser.add_argument('--count', type=int, required=True,
                        help="total LED count / safe upper bound to allocate")
    parser.add_argument('--index', type=int, default=0,
                        help="starting chain index (corner/edge)")
    parser.add_argument('--run', type=int, default=8,
                        help="run length for edge/row2 (typically panel height)")
    parser.add_argument('--panel', type=int, default=64,
                        help="pixels per panel for the boundaries pattern")
    parser.add_argument('--brightness', type=float, default=DEFAULT_PROBE_BRIGHTNESS,
                        help=f"brightness 0-{MAX_PROBE_BRIGHTNESS} (hard-capped)")
    args = parser.parse_args(argv)

    if args.count <= 0:
        parser.error("--count must be > 0")

    try:
        render_pattern(args.pattern, args.count, index=args.index, run=args.run,
                       panel=args.panel, brightness=args.brightness)
    except Exception as e:
        logger.error("probe failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
