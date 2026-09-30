#!/usr/bin/env python3
"""
RasQberry Virtual LED Matrix Display

A Tkinter-based GUI that displays a virtual LED matrix of any geometry.
Reads pixel data from shared memory (transport v2), written by VirtualNeoPixel
in rq_led_virtual.py when a virtual output target is enabled.

Geometry (width/height/count) is read from the self-describing mmap header, so
the GUI adapts automatically to whichever layout the writer is using. The
coordinate mapping is imported from rq_led_utils (the single shared mapper), so
the virtual view can never disagree with the physical rendering.

Usage:
    python3 rq_led_virtual_gui.py

    # Then in another terminal, with a virtual target enabled (LED_VIRTUAL=true):
    python3 demo_led_text_rainbow_scroll.py
"""

import tkinter as tk
import mmap
import os
import sys
import struct
import time

# Shared mapper + config (both live in RQB2-bin; /usr/bin when installed).
try:
    from rq_led_utils import map_xy_to_pixel, get_led_config
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from rq_led_utils import map_xy_to_pixel, get_led_config

# mmap transport v2 constants (must match rq_led_virtual.py)
MMAP_FILE = "/tmp/rasqberry_virtual_led2.mmap"
MMAP_MAGIC = b'RQL1'
MMAP_HEADER_SIZE = 16
MMAP_DIRTY_OFFSET = 16
MMAP_PIXEL_OFFSET = 17

# GUI settings
LED_SIZE = 20       # Diameter of each LED circle in pixels
LED_GAP = 3         # Gap between LEDs
PADDING = 10        # Padding around the matrix
REFRESH_MS = 50     # GUI refresh rate (20 FPS)
BG_COLOR = "#1a1a1a"       # Dark background
LED_OFF_COLOR = "#2a2a2a"  # Very dim gray for "off" LEDs


def read_header(path):
    """
    Read the mmap header.

    Returns:
        tuple (width, height, count) or None if the file is missing/too small
        or the magic does not match.
    """
    try:
        if not os.path.exists(path) or os.path.getsize(path) < MMAP_HEADER_SIZE:
            return None
        with open(path, 'rb') as f:
            header = f.read(MMAP_HEADER_SIZE)
        if header[:4] != MMAP_MAGIC:
            return None
        width, height, count = struct.unpack('<HHH', header[4:10])
        return width, height, count
    except Exception:
        return None


def wait_for_header(path, timeout=None):
    """Poll until the mmap file exists with a valid header; return (w, h, count)."""
    print(f"Waiting for LED data on {path} ...")
    start = time.time()
    while True:
        geom = read_header(path)
        if geom is not None:
            return geom
        if timeout is not None and (time.time() - start) > timeout:
            return None
        time.sleep(0.2)


class VirtualLEDMatrix:
    """
    Tkinter GUI displaying a virtual LED matrix of arbitrary geometry.

    Geometry comes from the mmap header; the (x, y) -> chain index mapping comes
    from the shared rq_led_utils.map_xy_to_pixel for the configured layout.
    """

    def __init__(self, width, height, count, layout_name):
        self.width = width
        self.height = height
        self.count = count
        self.layout_name = layout_name
        self.pixel_bytes = count * 3

        self.root = tk.Tk()
        self.root.title(
            f"RasQberry Virtual LED Matrix - {width}x{height} ({layout_name})"
        )
        self.root.configure(bg=BG_COLOR)

        # Dynamic sizing variables
        self.led_size = LED_SIZE
        self.led_gap = LED_GAP
        self.min_led_size = 8
        self.last_width = 0
        self.last_height = 0

        # Calculate initial canvas size
        canvas_width = PADDING * 2 + width * (LED_SIZE + LED_GAP) - LED_GAP
        canvas_height = PADDING * 2 + height * (LED_SIZE + LED_GAP) - LED_GAP

        self.root.minsize(300, 150)

        self.canvas = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg=BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self.on_resize)

        # Create LED circles (grid sized from header width/height)
        self.leds = []
        for y in range(height):
            row = []
            for x in range(width):
                x_pos = PADDING + x * (self.led_size + self.led_gap) + self.led_size // 2
                y_pos = PADDING + y * (self.led_size + self.led_gap) + self.led_size // 2
                radius = self.led_size // 2
                led = self.canvas.create_oval(
                    x_pos - radius, y_pos - radius,
                    x_pos + radius, y_pos + radius,
                    fill=LED_OFF_COLOR,
                    outline=""
                )
                row.append(led)
            self.leds.append(row)

        # Status label
        self.status_var = tk.StringVar()
        self.status_var.set("Waiting for LED data...")

        self._mmap = None
        self._mmap_file = None
        self._total_size = MMAP_PIXEL_OFFSET + self.pixel_bytes
        self._init_mmap()

        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="#666666",
            bg=BG_COLOR,
            font=("Courier", 10)
        )
        self.status_label.pack(pady=(0, 5))

        self.root.after(REFRESH_MS, self.update_display)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_mmap(self):
        """Open the shared memory file for reading (must already exist)."""
        try:
            self._mmap_file = open(MMAP_FILE, 'r+b')
            self._mmap = mmap.mmap(self._mmap_file.fileno(), self._total_size)
            self.status_var.set(f"Connected: {MMAP_FILE}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            self._mmap = None

    def map_xy_to_pixel(self, x, y):
        """Map (x, y) to a chain index using the shared mapper for this layout."""
        return map_xy_to_pixel(x, y, layout=self.layout_name)

    def on_resize(self, event):
        """Handle window resize - scale LEDs to fit."""
        if event.width == self.last_width and event.height == self.last_height:
            return
        self.last_width = event.width
        self.last_height = event.height

        available_width = event.width - 2 * PADDING
        available_height = event.height - 2 * PADDING

        led_width = (available_width + self.led_gap) / self.width - self.led_gap
        led_height = (available_height + self.led_gap) / self.height - self.led_gap
        self.led_size = max(self.min_led_size, min(led_width, led_height))
        self.led_gap = max(1, self.led_size * 0.15)

        self.redraw_leds()

    def redraw_leds(self):
        """Reposition and resize all LED circles."""
        for y in range(self.height):
            for x in range(self.width):
                x_pos = PADDING + x * (self.led_size + self.led_gap) + self.led_size / 2
                y_pos = PADDING + y * (self.led_size + self.led_gap) + self.led_size / 2
                radius = self.led_size / 2
                self.canvas.coords(
                    self.leds[y][x],
                    x_pos - radius, y_pos - radius,
                    x_pos + radius, y_pos + radius
                )

    def update_display(self):
        """Read from mmap and update canvas LED colors."""
        if self._mmap is not None:
            try:
                self._mmap.seek(MMAP_DIRTY_OFFSET)
                dirty = self._mmap.read(1)

                if dirty and dirty[0] == 1:
                    pixel_data = self._mmap.read(self.pixel_bytes)

                    for y in range(self.height):
                        for x in range(self.width):
                            pixel_index = self.map_xy_to_pixel(x, y)
                            if pixel_index is None:
                                continue
                            offset = pixel_index * 3
                            if offset + 2 < len(pixel_data):
                                r = pixel_data[offset]
                                g = pixel_data[offset + 1]
                                b = pixel_data[offset + 2]
                                if r == 0 and g == 0 and b == 0:
                                    color = LED_OFF_COLOR
                                else:
                                    color = f"#{r:02x}{g:02x}{b:02x}"
                                self.canvas.itemconfig(self.leds[y][x], fill=color)

                    # Clear dirty flag
                    self._mmap.seek(MMAP_DIRTY_OFFSET)
                    self._mmap.write(b'\x00')

                    self.status_var.set("Receiving LED data...")
            except Exception as e:
                self.status_var.set(f"Read error: {e}")

        self.root.after(REFRESH_MS, self.update_display)

    def on_close(self):
        """Clean up and close."""
        if self._mmap:
            try:
                self._mmap.close()
            except Exception:
                pass
            self._mmap = None
        if self._mmap_file:
            try:
                self._mmap_file.close()
            except Exception:
                pass
            self._mmap_file = None
        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Main entry point."""
    print("RasQberry Virtual LED Matrix Display")

    # Wait for the writer to create the mmap with a valid header.
    geom = wait_for_header(MMAP_FILE)
    if geom is None:
        print("No LED data available; exiting.")
        return
    width, height, count = geom

    # Layout name for the shared mapper (geometry itself comes from the header).
    try:
        layout_name = get_led_config().get('led_layout', 'single-24x8')
    except Exception:
        layout_name = 'single-24x8'

    print(f"Matrix size: {width}x{height} ({count} LEDs)")
    print(f"Layout: {layout_name}")
    print(f"Shared memory: {MMAP_FILE}")
    print()

    app = VirtualLEDMatrix(width, height, count, layout_name)
    app.run()


if __name__ == "__main__":
    main()
