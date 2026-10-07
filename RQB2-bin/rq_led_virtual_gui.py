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
OPEN_FOCUS_GRACE_S = 1.5  # focus offers this soon after opening are declined
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


def _proc_stat(pid):
    """
    Fields of /proc/PID/stat after the command name.

    Returns:
        list: [state, ppid, pgrp, session, tty_nr, tpgid, ...], or None.
    """
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None


def led_writers(path, proc="/proc"):
    """
    PIDs of the other processes that have the LED frame bus mapped.

    These are the demos drawing on the view (and the LED renderer service,
    which has no terminal).
    """
    pids = []
    me = os.getpid()
    try:
        entries = os.listdir(proc)
    except OSError:
        return pids
    for entry in entries:
        if not entry.isdigit() or int(entry) == me:
            continue
        try:
            with open(os.path.join(proc, entry, "maps")) as f:
                if any(line.rstrip().endswith(path) for line in f):
                    pids.append(int(entry))
        except OSError:
            continue
    return pids


def terminal_foreground_group(pid, stat=_proc_stat):
    """
    The foreground process group of the terminal PID runs in.

    A demo started from the RasQberry menu runs in a session of its own
    without a terminal: its parents are asked then.

    Returns:
        int: the process group, or None if no parent has a terminal.
    """
    seen = set()
    while pid and pid > 1 and pid not in seen:
        seen.add(pid)
        fields = stat(pid)
        if not fields or len(fields) < 6:
            return None
        tty_nr, tpgid = int(fields[4]), int(fields[5])
        if tty_nr != 0:
            return tpgid if tpgid > 0 else None
        pid = int(fields[1])
    return None


def stop_led_demo(path, writers=led_writers, group=terminal_foreground_group):
    """
    Stop the LED demo drawing on the view, as Ctrl+C in its window does.

    Ctrl+C sends SIGINT to the foreground process group of the window's
    terminal; every demo window stops its demo on it (the demo itself, the
    "press Enter or Ctrl+C" wait, the RasQberry menu's wait).

    Returns:
        bool: True if a demo was asked to stop.
    """
    import signal
    groups = set()
    for pid in writers(path):
        pgrp = group(pid)
        if pgrp:
            groups.add(pgrp)
    for pgrp in groups:
        try:
            os.killpg(pgrp, signal.SIGINT)
        except OSError:
            pass
    return bool(groups)


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
        self._focus_on_open()

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
        self._last_frame = None
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
        # Clicked and typed into anyway: Enter, Escape and Ctrl+C here stop
        # the demo just as in its own window
        for key in ("<Return>", "<KP_Enter>", "<Escape>", "<Control-c>"):
            self.root.bind(key, self.on_stop_key)

    def _focus_on_open(self):
        """
        Open without taking the keyboard focus, but stay a normal window.

        The demo's window must keep the focus, so that "press Enter or
        Ctrl+C" works right after this view opens. labwc (Trixie, 0.20)
        focuses a new X window that asks for input (ICCCM Passive). The view
        uses the ICCCM "Globally Active" model instead: WM_HINTS input=False
        plus WM_TAKE_FOCUS. labwc then offers the focus (WM_TAKE_FOCUS) and
        the view declines the offer that comes with opening and accepts
        later ones: a click on the view or its taskbar entry. labwc lists a
        Globally Active window in the taskbar only with the window type
        NORMAL (Tk sets none by default); the "No Input" model (input=False
        alone) had no taskbar entry, so a covered view could not be found.
        Must be set before the window is first mapped (mainloop).
        """
        self._mapped_at = None
        self.root.wm_focusmodel("active")
        try:
            self.root.attributes("-type", "normal")
        except tk.TclError:
            pass  # not X11
        self.root.protocol("WM_TAKE_FOCUS", self.on_take_focus)
        self.root.bind("<Map>", self.on_map, add="+")

    def on_map(self, event):
        """Note when the window first appeared."""
        if event.widget is self.root and self._mapped_at is None:
            self._mapped_at = time.monotonic()

    def on_take_focus(self):
        """The window manager offers the focus: take it, except on opening."""
        if self._mapped_at is None or time.monotonic() - self._mapped_at < OPEN_FOCUS_GRACE_S:
            return
        self.root.focus_force()

    def on_stop_key(self, event=None):
        """Enter, Escape or Ctrl+C in the view: stop the demo."""
        stopped = stop_led_demo(MMAP_FILE)
        self.status_var.set("Stopping the demo..." if stopped else "No LED demo to stop")

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
        """
        Read from mmap and update the canvas when the frame changed.

        The dirty flag is left alone (#6). In service mode the LED renderer
        consumes it, and while this window cleared it too, each frame went to
        whichever of the two looked first: a picture shown once (LED-Painter,
        the wizard's probes) reached the panel or this window, rarely both.
        Comparing with the last frame shown needs no flag (the browser view
        works the same way).
        """
        if self._mmap is not None:
            try:
                self._mmap.seek(MMAP_PIXEL_OFFSET)
                pixel_data = self._mmap.read(self.pixel_bytes)

                if pixel_data != self._last_frame:
                    self._last_frame = pixel_data
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
