#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
# Modified for RasQberry: Hardware-aware LED demo using PWM/PIO configuration

import time
from rq_led_utils import get_led_config, create_neopixel_strip, chunked_show

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

# Create LED strip (auto-detects Pi4 PWM or Pi5 PIO)
pixels = create_neopixel_strip(
    NUM_PIXELS,
    pixel_order_str,
    brightness=config['led_default_brightness']
)

# Hardware info no longer printed to avoid terminal pollution in whiptail menus
# (info still available via environment variables if needed)


def set_px(index, color):
    """Set a single pixel, but only when it exists on this strip.

    The "IBM" glyph below is laid out with fixed chain indices chosen for a
    192-LED serpentine. Guarding every write against NUM_PIXELS (derived from
    the active layout) keeps the demo from crashing on shorter strips - the
    out-of-range dots are simply skipped - instead of blindly indexing e.g.
    pixels[191] on a smaller layout.
    """
    if 0 <= index < NUM_PIXELS:
        pixels[index] = color


while True:
    for color in COLORS:
        # Letter "I"
        set_px(0, color)
        set_px(191, color)

        set_px(4, color)
        set_px(5, color)
        set_px(6, color)
        set_px(7, color)
        set_px(187, color)
        set_px(186, color)
        set_px(185, color)
        set_px(184, color)

        set_px(8, color)
        set_px(9, color)
        set_px(10, color)
        set_px(11, color)
        set_px(183, color)
        set_px(182, color)
        set_px(181, color)
        set_px(180, color)

        set_px(176, color)
        set_px(15, color)

        # Letter "B"
        set_px(20, color)
        set_px(21, color)
        set_px(22, color)
        set_px(23, color)
        set_px(171, color)
        set_px(170, color)
        set_px(169, color)
        set_px(168, color)

        set_px(24, color)
        set_px(27, color)
        set_px(164, color)
        set_px(167, color)

        set_px(28, color)
        set_px(31, color)
        set_px(163, color)
        set_px(160, color)

        set_px(32, color)
        set_px(33, color)
        set_px(34, color)
        # set_px(159, color)
        set_px(158, color)
        set_px(157, color)
        set_px(156, color)

        # Letter "M"
        set_px(40, color)
        set_px(41, color)
        set_px(42, color)
        set_px(43, color)
        set_px(151, color)
        set_px(150, color)
        set_px(149, color)
        set_px(148, color)

        set_px(46, color)
        set_px(50, color)
        set_px(51, color)
        set_px(54, color)

        set_px(56, color)
        set_px(57, color)
        set_px(58, color)
        set_px(59, color)
        set_px(132, color)
        set_px(133, color)
        set_px(134, color)
        set_px(135, color)

        chunked_show(pixels)
        time.sleep(16 * DELAY)

        # Animated sweep effect
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
