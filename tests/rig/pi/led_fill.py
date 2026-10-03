#!/usr/bin/env python3
"""
RasQberry rig test: fill the whole LED panel with one colour (or clear it).

Runs ON the Pi, as root, with the RasQberry venv python (it needs the LED
modules), through the same rq_led_utils path the demos use:

    sudo <venv>/bin/python led_fill.py 0 60 0     # dim green
    sudo <venv>/bin/python led_fill.py 0 0 0      # off

The rig test lights the panel before "Clear LEDs" (so the demo has something
to switch off) and uses fills to find each Pi's panel in the camera frame.
Exit status 1 if the panel could not be written (e.g. GPIO busy).
"""

import os
import sys

os.environ.setdefault("RQ_LED_NO_WINDOW", "1")   # the physical panel only
sys.path.insert(0, "/usr/bin")                     # rq_led_utils lives there


def main():
    """Fill the panel with the colour given as R G B arguments."""
    try:
        color = tuple(int(v) for v in sys.argv[1:4])
        assert len(color) == 3
    except (ValueError, AssertionError):
        sys.exit("usage: led_fill.py R G B")
    import time
    import rq_led_utils
    # images before RQ_LED_NO_WINDOW: don't start the on-screen view either
    if hasattr(rq_led_utils, "_ensure_virtual_led_gui_running"):
        rq_led_utils._ensure_virtual_led_gui_running = lambda *a, **k: None
    try:
        pixels = rq_led_utils.get_pixels()
        pixels.fill(color)
        pixels.show()
        # Pi 5: let the frame out before exiting (older images: just wait)
        getattr(rq_led_utils, "_wait_for_last_frame", lambda: time.sleep(0.3))()
    except Exception as exc:     # report, don't trace back: the caller logs it
        print(f"led_fill: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
