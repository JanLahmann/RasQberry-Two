#!/usr/bin/env python3
"""
RasQberry Virtual NeoPixel Implementation

A drop-in replacement for neopixel.NeoPixel that writes to shared memory
instead of GPIO. Used when LED_VIRTUAL=true in environment.

The VirtualNeoPixel class mimics the interface of adafruit-circuitpython-neopixel,
allowing existing demos to run without hardware by displaying on the virtual
LED matrix GUI (rq_led_virtual_gui.py).

Communication uses a memory-mapped file at /tmp/rasqberry_virtual_led.mmap.
"""

import mmap
import os
import struct

# Shared memory file location
MMAP_FILE = "/tmp/rasqberry_virtual_led.mmap"

# Memory layout:
# Byte 0: Dirty flag (0=clean, 1=dirty/updated)
# Bytes 1-576: Pixel data (192 pixels x 3 bytes RGB)
MMAP_HEADER_SIZE = 1
MMAP_PIXEL_SIZE = 192 * 3  # 576 bytes
MMAP_TOTAL_SIZE = MMAP_HEADER_SIZE + MMAP_PIXEL_SIZE  # 577 bytes


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

    def __init__(self, pin, num_pixels, brightness=0.5, auto_write=False, pixel_order=None):
        """
        Initialize virtual NeoPixel strip.

        Args:
            pin: Ignored (no GPIO needed for virtual display)
            num_pixels (int): Number of LEDs in strip
            brightness (float): LED brightness 0.0-1.0
            auto_write (bool): If True, update display on every pixel change
            pixel_order: Ignored (always uses RGB internally)
        """
        self.n = num_pixels
        self._brightness = brightness
        self.auto_write = auto_write
        self._pixels = [(0, 0, 0)] * num_pixels
        self._mmap = None
        self._mmap_file = None
        self._init_mmap()

    def _init_mmap(self):
        """Create or open the shared memory file."""
        try:
            # Create file if it doesn't exist
            if not os.path.exists(MMAP_FILE):
                with open(MMAP_FILE, 'wb') as f:
                    f.write(b'\x00' * MMAP_TOTAL_SIZE)

            # Open file for read/write
            self._mmap_file = open(MMAP_FILE, 'r+b')
            self._mmap = mmap.mmap(self._mmap_file.fileno(), MMAP_TOTAL_SIZE)
        except Exception as e:
            print(f"Warning: Could not initialize virtual LED mmap: {e}")
            self._mmap = None

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
            # Build pixel data buffer
            data = bytearray(MMAP_PIXEL_SIZE)
            for i, (r, g, b) in enumerate(self._pixels):
                if i >= 192:
                    break
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

            # Write to mmap: header byte (dirty flag) + pixel data
            self._mmap.seek(0)
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
        if self._mmap_file:
            try:
                self._mmap_file.close()
            except Exception:
                pass

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
