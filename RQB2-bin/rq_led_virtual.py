#!/usr/bin/env python3
"""
RasQberry Virtual NeoPixel Implementation

A drop-in replacement for neopixel.NeoPixel that writes to shared memory
instead of GPIO. Used when LED_VIRTUAL=true in environment.

The VirtualNeoPixel class mimics the interface of adafruit-circuitpython-neopixel,
allowing existing demos to run without hardware by displaying on the virtual
LED matrix GUI (rq_led_virtual_gui.py).

Communication uses a memory-mapped file at /tmp/rasqberry_virtual_led2.mmap
(transport v2 - self-describing header, dynamic size).
"""

import mmap
import os
import struct

# Shared memory file location (v2: renamed so old GUIs and new writers can't
# misread each other's incompatible formats).
MMAP_FILE = "/tmp/rasqberry_virtual_led2.mmap"


def mmap_path():
    """
    Resolve the transport mmap path.

    Defaults to MMAP_FILE. The RQB2_LED_MMAP_PATH environment variable overrides
    it (used by the unit tests to point writer + renderer at a temp file, and
    available for advanced multi-bus setups). Resolved at call time so callers
    that set the env var before constructing a writer pick it up.
    """
    return os.environ.get("RQB2_LED_MMAP_PATH", MMAP_FILE)

# Memory layout (transport v2):
#   [0:4]   magic  b'RQL1'
#   [4:6]   width  (uint16, little-endian)
#   [6:8]   height (uint16, little-endian)
#   [8:10]  count  (uint16, little-endian)
#   [10:16] reserved (6 bytes, zero)
#   [16]    dirty flag byte (0=clean, 1=dirty/updated)
#   [17:..] pixel data (count x 3 bytes RGB)
MMAP_MAGIC = b'RQL1'
MMAP_HEADER_SIZE = 16
MMAP_DIRTY_SIZE = 1
# Offsets
MMAP_DIRTY_OFFSET = MMAP_HEADER_SIZE            # 16
MMAP_PIXEL_OFFSET = MMAP_HEADER_SIZE + MMAP_DIRTY_SIZE  # 17


def mmap_total_size(count):
    """Total mmap file size in bytes for a given pixel count."""
    return MMAP_HEADER_SIZE + MMAP_DIRTY_SIZE + count * 3


class VirtualNeoPixel:
    """
    NeoPixel-compatible class that writes to shared memory for virtual display.

    Implements the same interface as neopixel.NeoPixel:
    - __getitem__, __setitem__ for pixel access: pixels[i] = (r, g, b)
    - fill(color) to set all pixels
    - show() to update display
    - brightness property

    Example:
        pixels = VirtualNeoPixel(None, 192, brightness=0.5)
        pixels[0] = (255, 0, 0)  # Set first pixel to red
        pixels.fill((0, 0, 255))  # Set all pixels to blue
        pixels.show()  # Update virtual display
    """

    def __init__(self, pin, num_pixels, brightness=0.5, auto_write=False,
                 pixel_order=None, width=None, height=None):
        """
        Initialize virtual NeoPixel strip.

        Args:
            pin: Ignored (no GPIO needed for virtual display)
            num_pixels (int): Number of LEDs in strip
            brightness (float): LED brightness 0.0-1.0
            auto_write (bool): If True, update display on every pixel change
            pixel_order: Ignored (always uses RGB internally)
            width (int, optional): Logical matrix width for the mmap header.
                If None, derived from the configured layout (fallback num_pixels).
            height (int, optional): Logical matrix height for the mmap header.
                If None, derived from the configured layout (fallback 1).
        """
        self.n = num_pixels
        self._brightness = brightness
        self.auto_write = auto_write
        self._pixels = [(0, 0, 0)] * num_pixels

        # Resolve geometry for the self-describing header.
        if width is None or height is None:
            d_w, d_h = self._derive_geometry(num_pixels)
            width = d_w if width is None else width
            height = d_h if height is None else height
        self._width = int(width)
        self._height = int(height)

        self._total_size = mmap_total_size(num_pixels)
        # Resolve the target path once at construction (honours
        # RQB2_LED_MMAP_PATH); default is unchanged.
        self._mmap_path = mmap_path()
        self._mmap = None
        self._mmap_file = None
        self._init_mmap()

    @staticmethod
    def _derive_geometry(num_pixels):
        """Best-effort (width, height) from the configured layout."""
        try:
            import rq_led_utils
            layout = rq_led_utils.get_layout()
            if layout:
                return layout['width'], layout['height']
        except Exception:
            pass
        return num_pixels, 1

    def _init_mmap(self):
        """Create/open the shared memory file, recreating it on size/magic mismatch."""
        try:
            path = self._mmap_path
            need_create = True
            if os.path.exists(path):
                if os.path.getsize(path) == self._total_size:
                    with open(path, 'rb') as f:
                        if f.read(len(MMAP_MAGIC)) == MMAP_MAGIC:
                            need_create = False

            # (Re)create the file at the correct size if needed.
            if need_create:
                with open(path, 'wb') as f:
                    f.write(b'\x00' * self._total_size)

            # Open file for read/write
            self._mmap_file = open(path, 'r+b')
            self._mmap = mmap.mmap(self._mmap_file.fileno(), self._total_size)
            self._write_header()
        except Exception as e:
            print(f"Warning: Could not initialize virtual LED mmap: {e}")
            self._mmap = None

    def _write_header(self):
        """Write the self-describing header (magic + geometry)."""
        if self._mmap is None:
            return
        header = MMAP_MAGIC + struct.pack(
            '<HHH', self._width & 0xFFFF, self._height & 0xFFFF, self.n & 0xFFFF
        )
        header += b'\x00' * (MMAP_HEADER_SIZE - len(header))  # reserved bytes
        self._mmap.seek(0)
        self._mmap.write(header)
        self._mmap.flush()

    def __len__(self):
        """Return number of pixels."""
        return self.n

    def __setitem__(self, index, color):
        """
        Set pixel color.

        Args:
            index (int): Pixel index
            color (tuple): RGB color as (r, g, b) tuple
        """
        if isinstance(index, slice):
            # Handle slice assignment
            start, stop, step = index.indices(self.n)
            for i, c in zip(range(start, stop, step), color):
                self._pixels[i] = self._normalize_color(c)
        else:
            if index < 0:
                index = self.n + index
            if 0 <= index < self.n:
                self._pixels[index] = self._normalize_color(color)

        if self.auto_write:
            self.show()

    def __getitem__(self, index):
        """
        Get pixel color.

        Args:
            index (int): Pixel index

        Returns:
            tuple: RGB color as (r, g, b) tuple
        """
        if isinstance(index, slice):
            return [self._pixels[i] for i in range(*index.indices(self.n))]
        if index < 0:
            index = self.n + index
        return self._pixels[index]

    def _normalize_color(self, color):
        """
        Normalize color to (r, g, b) tuple.

        Args:
            color: Can be tuple (r, g, b), list [r, g, b], or int 0xRRGGBB

        Returns:
            tuple: (r, g, b) with values 0-255
        """
        if isinstance(color, int):
            # Convert 0xRRGGBB to (r, g, b)
            return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
        elif isinstance(color, (list, tuple)):
            if len(color) >= 3:
                return (int(color[0]), int(color[1]), int(color[2]))
            elif len(color) == 1:
                # Single value, treat as grayscale
                return (int(color[0]), int(color[0]), int(color[0]))
        return (0, 0, 0)

    def fill(self, color):
        """
        Fill all pixels with a color.

        Args:
            color (tuple): RGB color as (r, g, b) tuple
        """
        normalized = self._normalize_color(color)
        self._pixels = [normalized] * self.n
        if self.auto_write:
            self.show()

    def show(self):
        """Write pixel data to shared memory for virtual display."""
        if self._mmap is None:
            return

        try:
            # Build pixel data buffer sized to the full strip (no 192 cap).
            data = bytearray(self.n * 3)
            for i, (r, g, b) in enumerate(self._pixels):
                # Apply brightness
                r = int(r * self._brightness)
                g = int(g * self._brightness)
                b = int(b * self._brightness)
                # Clamp values
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                # Write RGB
                offset = i * 3
                data[offset] = r
                data[offset + 1] = g
                data[offset + 2] = b

            # Write dirty flag + pixel payload (header is written once at init).
            self._mmap.seek(MMAP_DIRTY_OFFSET)
            self._mmap.write(b'\x01')  # Set dirty flag
            self._mmap.write(data)
            self._mmap.flush()
        except Exception as e:
            print(f"Warning: Could not write to virtual LED display: {e}")

    @property
    def brightness(self):
        """Get current brightness (0.0-1.0)."""
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        """Set brightness (0.0-1.0)."""
        self._brightness = max(0.0, min(1.0, float(value)))

    def deinit(self):
        """Clean up resources."""
        if self._mmap:
            try:
                self._mmap.close()
            except Exception:
                pass
            # Null the reference so __del__ can't touch a closed mmap
            # (fixes the 'mmap closed or invalid' warning).
            self._mmap = None
        if self._mmap_file:
            try:
                self._mmap_file.close()
            except Exception:
                pass
            self._mmap_file = None

    def __del__(self):
        """Destructor - clean up resources."""
        self.deinit()


class MirrorNeoPixel:
    """
    Proxy that writes to both real and virtual NeoPixel simultaneously.

    Used when LED_VIRTUAL_MIRROR=true to display on both the physical LEDs
    and the virtual GUI display for debugging.

    Example:
        real_pixels = neopixel.NeoPixel(...)
        virtual_pixels = VirtualNeoPixel(...)
        pixels = MirrorNeoPixel(real_pixels, virtual_pixels)
        pixels[0] = (255, 0, 0)  # Updates both displays
        pixels.show()  # Refreshes both displays
    """

    def __init__(self, real, virtual):
        """
        Initialize mirror display.

        Args:
            real: Real NeoPixel object for physical LEDs
            virtual: VirtualNeoPixel object for GUI display
        """
        self.real = real
        self.virtual = virtual
        self.n = real.n if hasattr(real, 'n') else len(real)

    def __len__(self):
        """Return number of pixels."""
        return self.n

    def __setitem__(self, index, color):
        """Set pixel color on both displays."""
        self.real[index] = color
        self.virtual[index] = color

    def __getitem__(self, index):
        """Get pixel color (from real display)."""
        return self.real[index]

    def fill(self, color):
        """Fill all pixels on both displays."""
        self.real.fill(color)
        self.virtual.fill(color)

    def show(self):
        """Update both displays."""
        self.real.show()
        self.virtual.show()

    @property
    def brightness(self):
        """Get current brightness."""
        return self.real.brightness

    @brightness.setter
    def brightness(self, value):
        """Set brightness on both displays."""
        self.real.brightness = value
        self.virtual.brightness = value

    def deinit(self):
        """Clean up resources on both displays."""
        if hasattr(self.real, 'deinit'):
            self.real.deinit()
        if hasattr(self.virtual, 'deinit'):
            self.virtual.deinit()

    def __del__(self):
        """Destructor - clean up resources."""
        self.deinit()
