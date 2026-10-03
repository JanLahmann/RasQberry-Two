#!/usr/bin/env python3
"""
RasQberry rig test: a real mouse for the desktop (kernel uinput).

Runs ON the Pi, as root (it opens /dev/uinput). Creates a USB-style absolute
pointer - like the "tablet" mouse of a virtual machine - moves it and clicks.
The events go through the kernel, libinput and the compositor (labwc), the
same path as a physical mouse, so the desktop sees a real double-click.

Why not a ready-made tool: wlrctl is not packaged for Raspberry Pi OS
bookworm, and ydotool (0.1.8 in bookworm) moves a relative mouse, which the
compositor accelerates, so it cannot hit a given pixel. An absolute pointer
needs no daemon, no package and no acceleration settings.

Usage:
    sudo python3 mouse.py dblclick X Y [SCREEN_W SCREEN_H]
    sudo python3 mouse.py click X Y [SCREEN_W SCREEN_H]
    sudo python3 mouse.py move X Y [SCREEN_W SCREEN_H]
X, Y in screen pixels (default screen 1920x1080, scale 1).
"""

import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
ABS_X, ABS_Y = 0x00, 0x01
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
BUS_USB = 0x03
ABS_RANGE = 32767


class AbsoluteMouse:
    """A uinput absolute pointer with three buttons."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        for ev in (EV_SYN, EV_KEY, EV_ABS):
            fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
        for btn in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE):
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, btn)
        for axis in (ABS_X, ABS_Y):
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
        absmax = [0] * 64
        absmax[ABS_X] = absmax[ABS_Y] = ABS_RANGE
        # struct uinput_user_dev: name, input_id, ff_effects_max, absmax/min/fuzz/flat
        dev = struct.pack("80sHHHHI" + "64i" * 4, b"rasqberry-rigtest-mouse",
                          BUS_USB, 0x1d6b, 0x0104, 1, 0, *absmax, *([0] * 64 * 3))
        os.write(self.fd, dev)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(1.0)   # udev + libinput + compositor pick up the new device

    def _emit(self, etype, code, value):
        now = time.time()
        os.write(self.fd, struct.pack("llHHi", int(now), int(now % 1 * 1e6), etype, code, value))

    def move(self, x, y):
        """Put the pointer on screen pixel (x, y)."""
        self._emit(EV_ABS, ABS_X, round(x * ABS_RANGE / max(1, self.width - 1)))
        self._emit(EV_ABS, ABS_Y, round(y * ABS_RANGE / max(1, self.height - 1)))
        self._emit(EV_SYN, SYN_REPORT, 0)

    def click(self, button=BTN_LEFT):
        """Press and release a button."""
        self._emit(EV_KEY, button, 1)
        self._emit(EV_SYN, SYN_REPORT, 0)
        time.sleep(0.05)
        self._emit(EV_KEY, button, 0)
        self._emit(EV_SYN, SYN_REPORT, 0)

    def close(self):
        """Remove the device."""
        time.sleep(0.3)   # let the last events through before it disappears
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def main(argv):
    """Run one action; see the module docstring."""
    if len(argv) not in (3, 5) or argv[0] not in ("move", "click", "dblclick"):
        sys.exit(__doc__.split("Usage:")[1])
    x, y = int(argv[1]), int(argv[2])
    w, h = (int(argv[3]), int(argv[4])) if len(argv) == 5 else (1920, 1080)
    mouse = AbsoluteMouse(w, h)
    try:
        mouse.move(x, y)
        time.sleep(0.3)   # pointer enters the surface under it first
        if argv[0] != "move":
            mouse.click()
        if argv[0] == "dblclick":
            time.sleep(0.12)   # well inside GTK's 400 ms double-click time
            mouse.click()
    finally:
        mouse.close()


if __name__ == "__main__":
    main(sys.argv[1:])
