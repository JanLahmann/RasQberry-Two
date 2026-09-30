#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
# Modified for RasQberry: Hardware-aware LED demo using PWM/PIO configuration

import time
from rq_led_utils import (
    get_led_config,
    create_neopixel_strip,
    chunked_show,
    map_xy_to_pixel,
)

# Load configuration from environment
config = get_led_config()
NUM_PIXELS = config['led_count']
pixel_order_str = config['pixel_order']

# Color definitions - using (R, G, B) tuple format
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
COLORS = (RED, GREEN, BLUE)
DELAY = 0.0250

# "IBM" glyph in LOGICAL (x, y) coordinates, TOP-LEFT origin (y=0 is the top
# row). Drawn through map_xy_to_pixel so it tracks the active LED_LAYOUT (single,
# quad, y-flip, ...) instead of the old fixed 192-LED chain indices, and so it
# renders upright on both the physical panel and the virtual GUI. Each non-space
# cell is lit; a 24x8 canvas matches the standard matrix (out-of-range cells on
# other layouts are simply skipped).
IBM_GLYPH = [
    "IIIIII  BBBBB   M     M ",
    "IIIIII  BB  BB  MM   MM ",
    "  II    BB  BB  MMM MMM ",
    "  II    BBBBB   MM M MM ",
    "  II    BBBBB   MM   MM ",
    "  II    BB  BB  MM   MM ",
    "IIIIII  BB  BB  MM   MM ",
    "IIIIII  BBBBB   MM   MM ",
]

# Create LED strip (auto-detects Pi4 PWM or Pi5 PIO)
pixels = create_neopixel_strip(
    NUM_PIXELS,
    pixel_order_str,
    brightness=config['led_default_brightness']
)

# Hardware info no longer printed to avoid terminal pollution in whiptail menus
# (info still available via environment variables if needed)


def set_xy(x, y, color):
    """Light logical cell (x, y) via the active layout, skipping off-panel cells.

    map_xy_to_pixel returns None when (x, y) is outside the configured matrix, so
    the "IBM" glyph degrades gracefully on layouts narrower/shorter than 24x8
    instead of crashing on a fixed chain index.
    """
    index = map_xy_to_pixel(x, y)
    if index is not None and 0 <= index < NUM_PIXELS:
        pixels[index] = color


def draw_ibm(color):
    """Draw the top-origin IBM glyph in a single colour."""
    for y, row in enumerate(IBM_GLYPH):
        for x, cell in enumerate(row):
            if cell != ' ':
                set_xy(x, y, color)


while True:
    for color in COLORS:
        pixels.fill((0, 0, 0))
        draw_ibm(color)
        chunked_show(pixels)
        time.sleep(16 * DELAY)

        # Animated sweep effect: a short run walked along the RAW chain order.
        # This is a physical-strip continuity test (chain diagnostic), so it
        # intentionally addresses pixels by chain index rather than (x, y).
        pixels.fill((0, 0, 0))
        for i in range(NUM_PIXELS):
            pixels[i] = color
            if (i + 1) < NUM_PIXELS:
                pixels[i + 1] = color
            if (i + 2) < NUM_PIXELS:
                pixels[i + 2] = color
            if (i + 3) < NUM_PIXELS:
                pixels[i + 3] = color
            # PWM/PIO drivers can update every pixel without flickering!
            chunked_show(pixels)
            time.sleep(DELAY)
            pixels.fill((0, 0, 0))
