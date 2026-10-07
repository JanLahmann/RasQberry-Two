#!/usr/bin/env python3
"""
RasQberry rig test: a real keyboard for the desktop (kernel uinput).

Runs ON the Pi, as root (it opens /dev/uinput). Like mouse.py, the key
presses go through the kernel, libinput and labwc, so a page sees the key a
person types. wtype does not: it sends its own keymap, and Chromium reported
its Space as keyCode 27 (Escape), so a RISE slideshow "ignored Space" in two
user tests although a real keyboard moves it on (2026-10-07).

Usage:
    sudo python3 keyboard.py KEY [KEY ...]
KEY: an evdev key code (57 Space, 28 Enter, 1 Esc, 106 Right, 108 Down),
"29+46" for keys pressed together (Ctrl+C), or "sleep0.5" for a pause.
"""

import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_KEY, SYN_REPORT = 0x00, 0x01, 0
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
BUS_USB = 0x03


class Keyboard:
    """A uinput keyboard with the standard keys."""

    def __init__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        for ev in (EV_SYN, EV_KEY):
            fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
        for key in range(1, 128):
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, key)
        dev = struct.pack("80sHHHHI" + "64i" * 4, b"rasqberry-rigtest-keyboard",
                          BUS_USB, 0x1d6b, 0x0105, 1, 0, *([0] * 64 * 4))
        os.write(self.fd, dev)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(1.0)   # udev + libinput + compositor pick up the new device

    def _emit(self, etype, code, value):
        now = time.time()
        os.write(self.fd, struct.pack("llHHi", int(now), int(now % 1 * 1e6), etype, code, value))

    def press(self, keys):
        """Press KEYS together (in order) and release them."""
        for key in keys:
            self._emit(EV_KEY, key, 1)
            self._emit(EV_SYN, SYN_REPORT, 0)
            time.sleep(0.05)
        for key in reversed(keys):
            self._emit(EV_KEY, key, 0)
            self._emit(EV_SYN, SYN_REPORT, 0)
            time.sleep(0.05)

    def close(self):
        """Remove the device."""
        time.sleep(0.3)   # let the last events through before it disappears
        fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def main(argv):
    """Press the keys given on the command line; see the module docstring."""
    if not argv:
        sys.exit(__doc__.split("Usage:")[1])
    kbd = Keyboard()
    try:
        for arg in argv:
            if arg.startswith("sleep"):
                time.sleep(float(arg[5:]))
                continue
            kbd.press([int(k) for k in arg.split("+")])
            time.sleep(0.2)
    finally:
        kbd.close()


if __name__ == "__main__":
    main(sys.argv[1:])
