#!/usr/bin/env python3
"""
RasQberry LED Renderer - root-confined physical LED render service (Phase A2).

This is the ONLY component that touches GPIO. It reads logical frames from the
virtual-transport mmap (transport v2, see rq_led_virtual.py) and drives the
physical NeoPixel strip. Demos run as the unprivileged user and only write
frames into the same mmap through the library API - they never get root and
never touch GPIO. The mmap is the universal frame bus: this physical renderer,
the virtual GUI, and the future web view are all just consumers of one buffer.

Enabled by LED_RENDER_MODE=service (rasqberry-led-renderer.service). In the
default LED_RENDER_MODE=direct mode this service is not used.

Brightness note: the writer (VirtualNeoPixel.show()) ALREADY applies the
configured brightness to the RGB values before writing them into the mmap.
Applying brightness again here would double-attenuate, so the physical strip is
created at brightness=1.0 and the mmap values are pushed through verbatim.

Usage:
    rq_led_renderer.py            # run the render loop (systemd service)
    rq_led_renderer.py --once     # process at most one frame, then exit 0
    rq_led_renderer.py --status   # print mmap header geometry and exit
"""

import argparse
import mmap
import os
import signal
import struct
import sys
import time

# Reuse the transport-v2 constants/helpers from rq_led_virtual when importable
# (both are installed to /usr/bin). Fall back to identical local definitions so
# the renderer stays dependency-light and importable/testable standalone.
try:
    from rq_led_virtual import (
        MMAP_MAGIC,
        MMAP_HEADER_SIZE,
        MMAP_DIRTY_SIZE,
        MMAP_DIRTY_OFFSET,
        MMAP_PIXEL_OFFSET,
        mmap_total_size,
        mmap_path,
    )
except Exception:  # pragma: no cover - exercised only if rq_led_virtual missing
    MMAP_MAGIC = b'RQL1'
    MMAP_HEADER_SIZE = 16
    MMAP_DIRTY_SIZE = 1
    MMAP_DIRTY_OFFSET = MMAP_HEADER_SIZE
    MMAP_PIXEL_OFFSET = MMAP_HEADER_SIZE + MMAP_DIRTY_SIZE

    def mmap_total_size(count):
        return MMAP_HEADER_SIZE + MMAP_DIRTY_SIZE + count * 3

    def mmap_path():
        return os.environ.get("RQB2_LED_MMAP_PATH",
                              "/tmp/rasqberry_virtual_led2.mmap")

# Poll interval for the dirty flag (~20 ms -> up to 50 fps).
POLL_INTERVAL_S = 0.02
# How often to re-stat the mmap file to detect recreation by a writer.
RESTAT_INTERVAL_S = 0.5
# Bounded wait for a frame in --once mode.
ONCE_TIMEOUT_S = 5.0


def parse_header(mm):
    """
    Parse the transport-v2 header from a mapped buffer.

    Args:
        mm: mmap object positioned anywhere (seek is handled here).

    Returns:
        tuple(magic, width, height, count) or None if the buffer is too small.
    """
    mm.seek(0)
    raw = mm.read(MMAP_HEADER_SIZE)
    if len(raw) < 10:
        return None
    magic = raw[0:4]
    width, height, count = struct.unpack('<HHH', raw[4:10])
    return magic, width, height, count


def read_frame(mm):
    """
    Read one frame from the mmap if it is dirty, clearing the dirty flag.

    This is the core, hardware-free frame-extraction step (unit-testable):
    it implements the dirty-flag handshake with the writer. When the writer has
    set the dirty byte, this returns the pixel payload and clears the byte so
    the next call returns None until the writer produces a new frame.

    Args:
        mm: read/write mmap of the transport file.

    Returns:
        list[tuple(int, int, int)]: the RGB frame, or None if not dirty / the
        header magic is invalid.
    """
    mm.seek(MMAP_DIRTY_OFFSET)
    if mm.read(MMAP_DIRTY_SIZE) != b'\x01':
        return None

    header = parse_header(mm)
    if header is None or header[0] != MMAP_MAGIC:
        return None
    count = header[3]

    mm.seek(MMAP_PIXEL_OFFSET)
    data = mm.read(count * 3)
    # Tolerate a short read (writer mid-recreate): only decode complete pixels.
    count = min(count, len(data) // 3)
    frame = [(data[i * 3], data[i * 3 + 1], data[i * 3 + 2]) for i in range(count)]

    # Clear the dirty flag to acknowledge consumption (the handshake).
    mm.seek(MMAP_DIRTY_OFFSET)
    mm.write(b'\x00')
    return frame


def create_mmap_file(path, count, width, height):
    """
    Create the transport file with a valid header so writers can attach.

    The renderer may start before any demo, so it seeds the mmap from the
    configured layout. The file is chmod 0666 afterwards: this service runs as
    root but the mmap must stay writable by the unprivileged demo processes.
    Acceptable because RasQberry is a trusted single-user device; there is no
    multi-tenant boundary to protect on /tmp.
    """
    size = mmap_total_size(count)
    header = MMAP_MAGIC + struct.pack('<HHH', width & 0xFFFF,
                                      height & 0xFFFF, count & 0xFFFF)
    header += b'\x00' * (MMAP_HEADER_SIZE - len(header))
    with open(path, 'wb') as f:
        f.write(header)
        f.write(b'\x00' * (size - MMAP_HEADER_SIZE))
    # chmod ignores umask, so 0666 is guaranteed regardless of the service umask.
    os.chmod(path, 0o666)


def _load_config():
    """Load LED config via rq_led_utils, with a hard-coded emergency fallback."""
    try:
        import rq_led_utils
        return rq_led_utils.get_led_config()
    except Exception as e:  # pragma: no cover - only if rq_led_utils unavailable
        print(f"Warning: could not load LED config ({e}); using defaults")
        return {
            'led_gpio_pin': 18,
            'pixel_order': 'GRB',
            'led_count': 192,
            'led_layout': 'single-24x8',
        }


class LedRenderer:
    """Owns the mmap, the physical strip, and the render loop."""

    def __init__(self, config):
        self.config = config
        self.path = mmap_path()
        self._mmap = None
        self._file = None
        self._size = 0
        self._ino = 0
        self._strip = None
        self._running = True

    # -- geometry -----------------------------------------------------------

    def _configured_geometry(self):
        """(count, width, height) from the configured layout, count fallback."""
        count = int(self.config.get('led_count', 192))
        width, height = count, 1
        try:
            import rq_led_utils
            layout = rq_led_utils.get_layout(self.config.get('led_layout'))
            if layout:
                width, height = layout['width'], layout['height']
                count = layout['count']
        except Exception:
            pass
        return count, width, height

    # -- mmap lifecycle -----------------------------------------------------

    def open_mmap(self):
        """Open the transport mmap, creating it from config if absent."""
        if not os.path.exists(self.path):
            count, width, height = self._configured_geometry()
            create_mmap_file(self.path, count, width, height)
        self._file = open(self.path, 'r+b')
        st = os.fstat(self._file.fileno())
        self._size = st.st_size
        self._ino = st.st_ino
        self._mmap = mmap.mmap(self._file.fileno(), self._size)

    def _close_mmap(self):
        if self._mmap is not None:
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def _maybe_reopen(self):
        """
        Reopen the mmap if a writer recreated the file (size/identity change).

        Guards against reading a half-written file: only commits to a reopen
        once the new file has a valid magic and a self-consistent size.
        """
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            return  # keep current mapping; a writer may recreate it shortly
        if st.st_ino == self._ino and st.st_size == self._size:
            return
        if st.st_size < MMAP_PIXEL_OFFSET:
            return  # writer mid-recreate; retry next tick
        try:
            with open(self.path, 'rb') as f:
                raw = f.read(MMAP_HEADER_SIZE)
        except OSError:
            return
        if len(raw) < 10 or raw[0:4] != MMAP_MAGIC:
            return
        count = struct.unpack('<HHH', raw[4:10])[2]
        if st.st_size != mmap_total_size(count):
            return  # not fully written yet
        self._close_mmap()
        self.open_mmap()

    # -- physical strip -----------------------------------------------------

    def create_strip(self):
        """Create the real NeoPixel strip directly (root, brightness 1.0)."""
        import board
        import neopixel

        pin = int(self.config.get('led_gpio_pin', 18))
        order_name = self.config.get('pixel_order', 'GRB')
        order = getattr(neopixel, order_name) if isinstance(order_name, str) else order_name
        count = int(self.config.get('led_count', 192))
        # brightness=1.0: the writer already pre-applied brightness (see module
        # docstring); attenuating again here would darken the strip twice.
        strip = neopixel.NeoPixel(
            getattr(board, f'D{pin}'),
            count,
            brightness=1.0,
            auto_write=False,
            pixel_order=order,
        )
        strip.fill((0, 0, 0))
        strip.show()
        self._strip = strip

    def _push(self, frame):
        """Copy a frame onto the strip and latch it."""
        strip = self._strip
        n = min(len(frame), len(strip))
        for i in range(n):
            strip[i] = frame[i]
        strip.show()

    def _blank(self):
        """Best-effort clear of the physical strip (clean shutdown)."""
        if self._strip is None:
            return
        try:
            self._strip.fill((0, 0, 0))
            self._strip.show()
        except Exception:
            pass

    # -- signals / lifecycle ------------------------------------------------

    def _install_signal_handlers(self):
        def _stop(signum, _frame):
            self._running = False
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

    # -- entry points -------------------------------------------------------

    def status(self):
        """Print the mmap header geometry (or configured geometry) and exit 0."""
        if os.path.exists(self.path):
            with open(self.path, 'rb') as f:
                raw = f.read(MMAP_HEADER_SIZE)
            if len(raw) >= 10 and raw[0:4] == MMAP_MAGIC:
                w, h, c = struct.unpack('<HHH', raw[4:10])
                print(f"mmap:     {self.path}")
                print(f"magic:    {raw[0:4].decode('ascii', 'replace')}")
                print(f"geometry: {w}x{h}  count={c}")
                print(f"size:     {os.path.getsize(self.path)} bytes")
            else:
                print(f"mmap:     {self.path} (present, invalid/foreign header)")
            return 0
        count, w, h = self._configured_geometry()
        print(f"mmap:     {self.path} (not present)")
        print(f"configured geometry: {w}x{h}  count={count}")
        return 0

    def run(self, once=False):
        """Run the render loop. With once=True, process at most one frame."""
        self._install_signal_handlers()
        self.open_mmap()
        self.create_strip()

        deadline = time.monotonic() + ONCE_TIMEOUT_S if once else None
        last_restat = time.monotonic()

        while self._running:
            now = time.monotonic()
            if now - last_restat >= RESTAT_INTERVAL_S:
                self._maybe_reopen()
                last_restat = now

            frame = read_frame(self._mmap)
            if frame is not None:
                self._push(frame)
                if once:
                    self._blank()
                    self._close_mmap()
                    return 0
            elif once and deadline is not None and now >= deadline:
                # No frame arrived within the bounded wait: "at most one".
                self._blank()
                self._close_mmap()
                return 0

            time.sleep(POLL_INTERVAL_S)

        # Clean shutdown (SIGTERM/SIGINT): blank the strip.
        self._blank()
        self._close_mmap()
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="RasQberry root-confined LED render service")
    parser.add_argument('--once', action='store_true',
                        help="process at most one frame, then exit 0")
    parser.add_argument('--status', action='store_true',
                        help="print mmap header geometry and exit")
    args = parser.parse_args(argv)

    renderer = LedRenderer(_load_config())
    if args.status:
        return renderer.status()
    return renderer.run(once=args.once)


if __name__ == "__main__":
    sys.exit(main())
