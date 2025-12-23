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

# Configuration
MMAP_FILE = "/tmp/rasqberry_virtual_led.mmap"
MATRIX_WIDTH = 24
MATRIX_HEIGHT = 8
NUM_PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT  # 192

# GUI settings
LED_SIZE = 20       # Diameter of each LED circle in pixels
LED_GAP = 3         # Gap between LEDs
PADDING = 10        # Padding around the matrix
REFRESH_MS = 50     # GUI refresh rate (20 FPS)
BG_COLOR = "#1a1a1a"  # Dark background
LED_OFF_COLOR = "#2a2a2a"  # Very dim gray for "off" LEDs

# Memory layout (must match rq_led_virtual.py)
MMAP_HEADER_SIZE = 1
MMAP_PIXEL_SIZE = NUM_PIXELS * 3
MMAP_TOTAL_SIZE = MMAP_HEADER_SIZE + MMAP_PIXEL_SIZE


class VirtualLEDMatrix:
    """
    Tkinter GUI displaying a virtual 24x8 LED matrix.

    Reads pixel data from memory-mapped file and displays as colored circles.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("RasQberry Virtual LED Matrix")
        self.root.configure(bg=BG_COLOR)

        # Calculate canvas size
        canvas_width = PADDING * 2 + MATRIX_WIDTH * (LED_SIZE + LED_GAP) - LED_GAP
        canvas_height = PADDING * 2 + MATRIX_HEIGHT * (LED_SIZE + LED_GAP) - LED_GAP

        # Create canvas
        self.canvas = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg=BG_COLOR,
            highlightthickness=0
        )
        self.canvas.pack(padx=5, pady=5)

        # Create LED circles
        self.leds = []
        for y in range(MATRIX_HEIGHT):
            row = []
            for x in range(MATRIX_WIDTH):
                x_pos = PADDING + x * (LED_SIZE + LED_GAP) + LED_SIZE // 2
                y_pos = PADDING + y * (LED_SIZE + LED_GAP) + LED_SIZE // 2
                radius = LED_SIZE // 2

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
    print(f"Shared memory: {MMAP_FILE}")
    print()
    print("Run LED demos with LED_VIRTUAL=true to see output here.")
    print()

    app = VirtualLEDMatrix()
    app.run()


if __name__ == "__main__":
    main()
