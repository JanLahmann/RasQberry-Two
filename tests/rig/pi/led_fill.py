#!/usr/bin/env python3
"""
RasQberry rig test: fill the whole LED panel with one colour (or clear it).

Runs ON the Pi, as root, with the RasQberry venv python (it needs the LED
modules), through the same rq_led_utils path the demos use:

    sudo <venv>/bin/python led_fill.py 0 60 0     # dim green
    sudo <venv>/bin/python led_fill.py 0 0 0      # off
    sudo <venv>/bin/python led_fill.py --hold 300 --pidfile F 0 60 0
    sudo <venv>/bin/python led_fill.py --corners --hold 60 60 60 60

Without --hold the light may not outlive the helper: the LED drivers clean up
at exit (Pi 4 ws281x, Pi 5 on newer images). --hold keeps the panel lit and
the LED device open for up to SECONDS, like a program that still owns the
panel; a SIGTERM/SIGINT ends it at once WITHOUT clearing (a foreign program
that leaves the panel lit - the hard case for "Clear LEDs").

The rig test lights the panel before "Clear LEDs" (so the demo has something
to switch off and a holder to stop) and uses fills to find each Pi's panel in
the camera frame. --corners lights only a 2x2 block in each corner of the
logical matrix, mapped through the Pi's configured LED layout: on the camera
the four blocks sit in the panel's four corners only if that layout matches
the wiring (a wrong layout put Lights Out's grid in one corner). Exit status 1
if the panel could not be written.
"""

import os
import signal
import sys
import time

os.environ.setdefault("RQ_LED_NO_WINDOW", "1")   # the physical panel only
sys.path.insert(0, "/usr/bin")                     # rq_led_utils lives there

USAGE = "usage: led_fill.py [--corners] [--hold SECONDS] [--pidfile FILE] R G B"


def parse(argv):
    """
    Parse the command line.

    Args:
        argv (list): arguments without the program name.

    Returns:
        tuple: (colour tuple, hold seconds or None, pidfile or None, corners)
    """
    hold = pidfile = None
    corners = False
    while argv and argv[0].startswith("--"):
        if argv[0] == "--corners":
            corners, argv = True, argv[1:]
        elif argv[0] == "--hold" and len(argv) > 1:
            hold, argv = float(argv[1]), argv[2:]
        elif argv[0] == "--pidfile" and len(argv) > 1:
            pidfile, argv = argv[1], argv[2:]
        else:
            sys.exit(USAGE)
    try:
        color = tuple(int(v) for v in argv)
    except ValueError:
        sys.exit(USAGE)
    if len(color) != 3:
        sys.exit(USAGE)
    return color, hold, pidfile, corners


def light_corners(rq_led_utils, pixels, color):
    """
    Light a 2x2 block in each corner of the configured layout's matrix.

    Returns:
        str: the layout name as rq_led_utils resolves it (what demos use).
    """
    layout = rq_led_utils.get_layout()
    if not layout:
        raise RuntimeError("no LED layout configured")
    w, h = rq_led_utils.matrix_size(layout)
    pixels.fill((0, 0, 0))
    for x in (0, 1, w - 2, w - 1):
        for y in (0, 1, h - 2, h - 1):
            rq_led_utils.set_xy(pixels, x, y, color, layout)
    return layout["name"]


def main():
    """Fill the panel with the colour given as R G B arguments."""
    color, hold, pidfile, corners = parse(sys.argv[1:])
    import rq_led_utils
    # images before RQ_LED_NO_WINDOW: don't start the on-screen view either
    if hasattr(rq_led_utils, "_ensure_virtual_led_gui_running"):
        rq_led_utils._ensure_virtual_led_gui_running = lambda *a, **k: None
    try:
        pixels = rq_led_utils.get_pixels()
        if corners:
            print(f"led_fill: corners, layout {light_corners(rq_led_utils, pixels, color)}", flush=True)
        else:
            pixels.fill(color)
        pixels.show()
        # Pi 5: let the frame out before exiting (older images: just wait)
        getattr(rq_led_utils, "_wait_for_last_frame", lambda: time.sleep(0.3))()
    except Exception as exc:     # report, don't trace back: the caller logs it
        print(f"led_fill: {exc}")
        sys.exit(1)
    if hold:
        # end at once on a signal, skipping the drivers' exit clean-up
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, lambda *_: os._exit(0))
        if pidfile:
            with open(pidfile, "w") as fh:
                fh.write(f"{os.getpid()}\n")
        print(f"led_fill: holding the panel lit for up to {hold:.0f} s", flush=True)
        time.sleep(hold)
        os._exit(0)


if __name__ == "__main__":
    main()
