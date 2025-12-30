#!/usr/bin/env python3
"""
RasQberry Virtual LED Matrix Display

A Tkinter-based GUI that displays a virtual 24x8 LED matrix.
Reads pixel data from shared memory, updated by rq_led_utils.py when using
VirtualNeoPixel (LED_VIRTUAL=true).

Follows the SenseHat emulator pattern - run as a separate process before
starting LED demos.

Usage:
    python3 rq_led_virtual_gui.py

    # Then in another terminal, with LED_VIRTUAL=true:
    python3 demo_led_text_rainbow_scroll.py
"""

import tkinter as tk
import mmap
import os
import sys

# Try to load configuration from environment file
ENV_FILE = "/usr/config/rasqberry_environment.env"
try:
    from dotenv import dotenv_values
    _config = dotenv_values(ENV_FILE) if os.path.exists(ENV_FILE) else {}
except ImportError:
    _config = {}

# Configuration from environment or defaults
MMAP_FILE = "/tmp/rasqberry_virtual_led.mmap"
MATRIX_WIDTH = int(_config.get('LED_MATRIX_WIDTH', 24))
MATRIX_HEIGHT = int(_config.get('LED_MATRIX_HEIGHT', 8))
MATRIX_LAYOUT = _config.get('LED_MATRIX_LAYOUT', 'single')  # 'single' or 'quad'
NUM_PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT  # 192

# Quad panel configuration (4 panels of 4x12 arranged 2x2)
PANEL_WIDTH = 12
PANEL_HEIGHT = 4
PANELS_X = 2
PANELS_Y = 2
PANEL_GAP = 8  # Visual gap between panels in quad mode

# GUI settings
LED_SIZE = 20       # Diameter of each LED circle in pixels
LED_GAP = 3         # Gap between LEDs
PADDING = 10        # Padding around the matrix
REFRESH_MS = 50     # GUI refresh rate (20 FPS)
BG_COLOR = "#1a1a1a"  # Dark background
LED_OFF_COLOR = "#2a2a2a"  # Very dim gray for "off" LEDs
PANEL_SEP_COLOR = "#444444"  # Panel separator color

# Memory layout (must match rq_led_virtual.py)
MMAP_HEADER_SIZE = 1
MMAP_PIXEL_SIZE = NUM_PIXELS * 3
MMAP_TOTAL_SIZE = MMAP_HEADER_SIZE + MMAP_PIXEL_SIZE


class VirtualLEDMatrix:
    """
    Tkinter GUI displaying a virtual LED matrix.

    Supports two layouts:
    - 'single': 24x8 serpentine (column-major)
    - 'quad': 4 panels of 4x12, arranged 2x2

    Reads pixel data from memory-mapped file and displays as colored circles.
    """

    def __init__(self):
        self.root = tk.Tk()
        layout_desc = f"{MATRIX_WIDTH}x{MATRIX_HEIGHT} ({MATRIX_LAYOUT})"
        self.root.title(f"RasQberry Virtual LED Matrix - {layout_desc}")
        self.root.configure(bg=BG_COLOR)

        # Dynamic sizing variables
        self.led_size = LED_SIZE      # Current LED diameter
        self.led_gap = LED_GAP        # Current gap between LEDs
        self.min_led_size = 8         # Minimum LED size
        self.last_width = 0           # Track last resize
        self.last_height = 0

        # Calculate initial canvas size
        canvas_width = PADDING * 2 + MATRIX_WIDTH * (LED_SIZE + LED_GAP) - LED_GAP
        canvas_height = PADDING * 2 + MATRIX_HEIGHT * (LED_SIZE + LED_GAP) - LED_GAP

        # Set minimum window size
        self.root.minsize(300, 150)

        # Create canvas (expandable)
        self.canvas = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg=BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Bind resize event
        self.canvas.bind('<Configure>', self.on_resize)

        # Create LED circles
        self.leds = []
        for y in range(MATRIX_HEIGHT):
            row = []
            for x in range(MATRIX_WIDTH):
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

        # Status label (must be created before _init_mmap)
        self.status_var = tk.StringVar()
        self.status_var.set("Waiting for LED data...")

        # Memory mapping
        self._mmap = None
        self._mmap_file = None
        self._init_mmap()
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="#666666",
            bg=BG_COLOR,
            font=("Courier", 10)
        )
        self.status_label.pack(pady=(0, 5))

        # Start refresh timer
        self.root.after(REFRESH_MS, self.update_display)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_mmap(self):
        """Open the shared memory file for reading."""
        try:
            if not os.path.exists(MMAP_FILE):
                # Create file if it doesn't exist
                with open(MMAP_FILE, 'wb') as f:
                    f.write(b'\x00' * MMAP_TOTAL_SIZE)

            self._mmap_file = open(MMAP_FILE, 'r+b')
            self._mmap = mmap.mmap(self._mmap_file.fileno(), MMAP_TOTAL_SIZE)
            self.status_var.set(f"Connected: {MMAP_FILE}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            self._mmap = None

    def map_xy_to_pixel(self, x, y):
        """
        Map (x, y) coordinates to pixel index based on configured layout.

        Dispatches to single or quad mapping based on MATRIX_LAYOUT config.
        """
        if MATRIX_LAYOUT == 'quad':
            return self.map_xy_to_pixel_quad(x, y)
        return self.map_xy_to_pixel_single(x, y)

    def map_xy_to_pixel_single(self, x, y):
        """
        Map (x, y) coordinates to pixel index using column-major serpentine layout.

        Matches the 'single' layout in rq_led_utils.py:
        - Even columns (0, 2, 4...): go down (y: 0→height-1)
        - Odd columns (1, 3, 5...): go up (y: height-1→0)
        """
        if x % 2 == 0:
            # Even columns go down (0→height-1)
            return x * MATRIX_HEIGHT + y
        else:
            # Odd columns go up (height-1→0)
            return x * MATRIX_HEIGHT + (MATRIX_HEIGHT - 1 - y)

    def map_xy_to_pixel_quad(self, x, y):
        """
        Map (x, y) coordinates to pixel index for quad panel layout.

        4 panels of 4x12 each, arranged 2x2:
        - Panel 0: top-left (x=0-11, y=0-3)
        - Panel 1: top-right (x=12-23, y=0-3)
        - Panel 2: bottom-left (x=0-11, y=4-7)
        - Panel 3: bottom-right (x=12-23, y=4-7)
        """
        # Determine which panel (0-3)
        panel_x = x // PANEL_WIDTH
        panel_y = y // PANEL_HEIGHT
        panel_idx = panel_y * PANELS_X + panel_x

        # Local coordinates within panel
        local_x = x % PANEL_WIDTH
        local_y = y % PANEL_HEIGHT

        # Each panel has PANEL_WIDTH * PANEL_HEIGHT LEDs
        panel_offset = panel_idx * PANEL_WIDTH * PANEL_HEIGHT

        # Column-major serpentine within panel
        if local_x % 2 == 0:
            return panel_offset + local_x * PANEL_HEIGHT + local_y
        else:
            return panel_offset + local_x * PANEL_HEIGHT + (PANEL_HEIGHT - 1 - local_y)

    def on_resize(self, event):
        """Handle window resize - scale LEDs to fit."""
        # Skip if size unchanged (avoid unnecessary redraws)
        if event.width == self.last_width and event.height == self.last_height:
            return
        self.last_width = event.width
        self.last_height = event.height

        # Calculate new LED size to fit window
        available_width = event.width - 2 * PADDING
        available_height = event.height - 2 * PADDING

        # Calculate LED size that fits both dimensions
        led_width = (available_width + self.led_gap) / MATRIX_WIDTH - self.led_gap
        led_height = (available_height + self.led_gap) / MATRIX_HEIGHT - self.led_gap
        self.led_size = max(self.min_led_size, min(led_width, led_height))

        # Recalculate gap proportionally
        self.led_gap = max(1, self.led_size * 0.15)

        # Reposition all LED circles
        self.redraw_leds()

    def redraw_leds(self):
        """Reposition and resize all LED circles."""
        for y in range(MATRIX_HEIGHT):
            for x in range(MATRIX_WIDTH):
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
                self._mmap.seek(0)
                header = self._mmap.read(1)

                if header[0] == 1:  # Dirty flag set
                    # Read pixel data
                    pixel_data = self._mmap.read(MMAP_PIXEL_SIZE)

                    # Update LED colors
                    for y in range(MATRIX_HEIGHT):
                        for x in range(MATRIX_WIDTH):
                            pixel_index = self.map_xy_to_pixel(x, y)
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
                    self._mmap.seek(0)
                    self._mmap.write(b'\x00')

                    self.status_var.set("Receiving LED data...")

            except Exception as e:
                self.status_var.set(f"Read error: {e}")

        # Schedule next update
        self.root.after(REFRESH_MS, self.update_display)

    def on_close(self):
        """Clean up and close."""
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
        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Main entry point."""
    print("RasQberry Virtual LED Matrix Display")
    print(f"Matrix size: {MATRIX_WIDTH}x{MATRIX_HEIGHT} ({NUM_PIXELS} LEDs)")
    print(f"Layout: {MATRIX_LAYOUT}")
    if MATRIX_LAYOUT == 'quad':
        print(f"  Panels: {PANELS_X}x{PANELS_Y} of {PANEL_WIDTH}x{PANEL_HEIGHT} each")
    print(f"Shared memory: {MMAP_FILE}")
    print()
    print("Run LED demos with LED_VIRTUAL=true to see output here.")
    print()

    app = VirtualLEDMatrix()
    app.run()


if __name__ == "__main__":
    main()
