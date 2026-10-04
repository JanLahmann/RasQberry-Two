#!/usr/bin/env python3
"""
RasQberry rig test: fill the whole LED panel with one colour (or clear it).

Runs ON the Pi, as root, with the RasQberry venv python (it needs the LED
modules), through the same rq_led_utils path the demos use:

    sudo <venv>/bin/python led_fill.py 0 60 0     # dim green
    sudo <venv>/bin/python led_fill.py 0 0 0      # off
    sudo <venv>/bin/python led_fill.py --hold 300 --pidfile F 0 60 0

Without --hold the light may not outlive the helper: the LED drivers clean up
at exit (Pi 4 ws281x, Pi 5 on newer images). --hold keeps the panel lit and
the LED device open for up to SECONDS, like a program that still owns the
panel; a SIGTERM/SIGINT ends it at once WITHOUT clearing (a foreign program
that leaves the panel lit - the hard case for "Clear LEDs").

The rig test lights the panel before "Clear LEDs" (so the demo has something
to switch off and a holder to stop) and uses fills to find each Pi's panel in
the camera frame. Exit status 1 if the panel could not be written.
"""

import os
import signal
import sys
import time

os.environ.setdefault("RQ_LED_NO_WINDOW", "1")   # the physical panel only
sys.path.insert(0, "/usr/bin")                     # rq_led_utils lives there

USAGE = "usage: led_fill.py [--hold SECONDS] [--pidfile FILE] R G B"


def parse(argv):
    """
    Parse the command line.

    Args:
        argv (list): arguments without the program name.

    Returns:
        tuple: (colour tuple, hold seconds or None, pidfile or None)
    """
    hold = pidfile = None
    while argv and argv[0].startswith("--"):
        if argv[0] == "--hold" and len(argv) > 1:
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
    return color, hold, pidfile


def main():
    """Fill the panel with the colour given as R G B arguments."""
    color, hold, pidfile = parse(sys.argv[1:])
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
