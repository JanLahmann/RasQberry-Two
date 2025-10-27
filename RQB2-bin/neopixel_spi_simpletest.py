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

while True:
    for color in COLORS:
        # Letter "I"
        pixels[0] = color
        pixels[191] = color

        pixels[4] = color
        pixels[5] = color
        pixels[6] = color
        pixels[7] = color
        pixels[187] = color
        pixels[186] = color
        pixels[185] = color
        pixels[184] = color

        pixels[8] = color
        pixels[9] = color
        pixels[10] = color
        pixels[11] = color
        pixels[183] = color
        pixels[182] = color
        pixels[181] = color
        pixels[180] = color

        pixels[176] = color
        pixels[15] = color

        # Letter "B"
        pixels[20] = color
        pixels[21] = color
        pixels[22] = color
        pixels[23] = color
        pixels[171] = color
        pixels[170] = color
        pixels[169] = color
        pixels[168] = color

        pixels[24] = color
        pixels[27] = color
        pixels[164] = color
        pixels[167] = color

        pixels[28] = color
        pixels[31] = color
        pixels[163] = color
        pixels[160] = color

        pixels[32] = color
        pixels[33] = color
        pixels[34] = color
        # pixels[159] = color
        pixels[158] = color
        pixels[157] = color
        pixels[156] = color

        # Letter "M"
        pixels[40] = color
        pixels[41] = color
        pixels[42] = color
        pixels[43] = color
        pixels[151] = color
        pixels[150] = color
        pixels[149] = color
        pixels[148] = color

        pixels[46] = color
        pixels[50] = color
        pixels[51] = color
        pixels[54] = color

        pixels[56] = color
        pixels[57] = color
        pixels[58] = color
        pixels[59] = color
        pixels[132] = color
        pixels[133] = color
        pixels[134] = color
        pixels[135] = color

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
            # Show every 8 pixels to reduce flickering (no chunking needed with PWM/PIO)
            # Still show last frame to ensure complete display
            if i % 8 == 0 or i == NUM_PIXELS - 1:
                chunked_show(pixels)
            time.sleep(DELAY)
            pixels.fill((0, 0, 0))
