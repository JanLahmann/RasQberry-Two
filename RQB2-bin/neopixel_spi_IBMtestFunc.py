# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
# Modified for RasQberry: Layout-aware IBM LED demo with hardware detection

import time
import board
import neopixel_spi as neopixel
from rq_led_utils import get_led_config, create_neopixel_strip, map_xy_to_pixel

# Load configuration from environment file
config = get_led_config()

# Rainbow colors for y-axis (row-based coloring)
rainbow_colors = [
    0x83209e,  # y=0: purple
    0x0041b7,  # y=1: blue
    0x00c4ad,  # y=2: turquoise
    0x02a204,  # y=3: green
    0xf8df08,  # y=4: yellow
    0xf9831f,  # y=5: orange
    0xfa0100,  # y=6: red
    0xfb80bf   # y=7: pink
]

# Color definitions
color_blue = 0x0000FF
color_red = 0xFF0000
color_green = 0x00FF00
DELAY = 5

# Initialize SPI
spi = board.SPI()

# Get pixel order from config and convert to neopixel constant
pixel_order_str = config['pixel_order']
pixel_order = getattr(neopixel, pixel_order_str)

# Create LED strip with correct parameters for Pi4/Pi5
pixels = create_neopixel_strip(
    spi,
    config['led_count'],
    pixel_order,
    brightness=0.1,
    pi_model=config['pi_model']
)

def doibm(toggle):
    """
    Draw IBM logo on LED matrix.

    Args:
        toggle: If True, use rainbow colors; if False, use solid colors (green/red/blue)

    Note:
        Coordinates are now (x, y) format - x=column, y=row
        Layout is auto-detected from environment configuration
    """

    # Letter "I" (green)
    i = map_xy_to_pixel(0, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green
    i = map_xy_to_pixel(1, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green
    i = map_xy_to_pixel(2, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green
    i = map_xy_to_pixel(3, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green
    i = map_xy_to_pixel(4, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green
    i = map_xy_to_pixel(5, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_green

    i = map_xy_to_pixel(0, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green
    i = map_xy_to_pixel(1, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green
    i = map_xy_to_pixel(2, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green
    i = map_xy_to_pixel(3, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green
    i = map_xy_to_pixel(4, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green
    i = map_xy_to_pixel(5, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_green

    i = map_xy_to_pixel(2, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_green
    i = map_xy_to_pixel(3, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_green

    i = map_xy_to_pixel(2, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_green
    i = map_xy_to_pixel(3, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_green

    i = map_xy_to_pixel(2, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_green
    i = map_xy_to_pixel(3, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_green

    i = map_xy_to_pixel(2, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_green
    i = map_xy_to_pixel(3, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_green

    i = map_xy_to_pixel(0, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green
    i = map_xy_to_pixel(1, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green
    i = map_xy_to_pixel(2, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green
    i = map_xy_to_pixel(3, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green
    i = map_xy_to_pixel(4, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green
    i = map_xy_to_pixel(5, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_green

    i = map_xy_to_pixel(0, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green
    i = map_xy_to_pixel(1, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green
    i = map_xy_to_pixel(2, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green
    i = map_xy_to_pixel(3, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green
    i = map_xy_to_pixel(4, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green
    i = map_xy_to_pixel(5, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_green

    # Letter "B" (red)
    i = map_xy_to_pixel(8, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_red
    i = map_xy_to_pixel(9, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_red
    i = map_xy_to_pixel(10, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_red
    i = map_xy_to_pixel(11, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_red
    i = map_xy_to_pixel(12, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_red

    i = map_xy_to_pixel(8, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_red
    i = map_xy_to_pixel(9, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_red
    i = map_xy_to_pixel(12, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_red
    i = map_xy_to_pixel(13, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_red

    i = map_xy_to_pixel(8, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_red
    i = map_xy_to_pixel(9, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_red
    i = map_xy_to_pixel(12, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_red
    i = map_xy_to_pixel(13, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_red

    i = map_xy_to_pixel(8, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_red
    i = map_xy_to_pixel(9, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_red
    i = map_xy_to_pixel(10, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_red
    i = map_xy_to_pixel(11, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_red
    i = map_xy_to_pixel(12, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_red

    i = map_xy_to_pixel(8, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_red
    i = map_xy_to_pixel(9, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_red
    i = map_xy_to_pixel(10, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_red
    i = map_xy_to_pixel(11, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_red
    i = map_xy_to_pixel(12, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_red

    i = map_xy_to_pixel(8, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_red
    i = map_xy_to_pixel(9, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_red
    i = map_xy_to_pixel(12, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_red
    i = map_xy_to_pixel(13, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_red

    i = map_xy_to_pixel(8, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_red
    i = map_xy_to_pixel(9, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_red
    i = map_xy_to_pixel(12, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_red
    i = map_xy_to_pixel(13, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_red

    i = map_xy_to_pixel(8, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_red
    i = map_xy_to_pixel(9, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_red
    i = map_xy_to_pixel(10, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_red
    i = map_xy_to_pixel(11, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_red
    i = map_xy_to_pixel(12, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_red

    # Letter "M" (blue)
    i = map_xy_to_pixel(16, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_blue
    i = map_xy_to_pixel(17, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_blue
    i = map_xy_to_pixel(21, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_blue
    i = map_xy_to_pixel(22, 0)
    pixels[i] = rainbow_colors[0] if toggle else color_blue

    i = map_xy_to_pixel(16, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_blue
    i = map_xy_to_pixel(17, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_blue
    i = map_xy_to_pixel(21, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_blue
    i = map_xy_to_pixel(22, 1)
    pixels[i] = rainbow_colors[1] if toggle else color_blue

    i = map_xy_to_pixel(16, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_blue
    i = map_xy_to_pixel(17, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_blue
    i = map_xy_to_pixel(21, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_blue
    i = map_xy_to_pixel(22, 2)
    pixels[i] = rainbow_colors[2] if toggle else color_blue

    i = map_xy_to_pixel(16, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_blue
    i = map_xy_to_pixel(17, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_blue
    i = map_xy_to_pixel(21, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_blue
    i = map_xy_to_pixel(22, 3)
    pixels[i] = rainbow_colors[3] if toggle else color_blue

    i = map_xy_to_pixel(16, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_blue
    i = map_xy_to_pixel(17, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_blue
    i = map_xy_to_pixel(19, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_blue
    i = map_xy_to_pixel(21, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_blue
    i = map_xy_to_pixel(22, 4)
    pixels[i] = rainbow_colors[4] if toggle else color_blue

    i = map_xy_to_pixel(16, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue
    i = map_xy_to_pixel(17, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue
    i = map_xy_to_pixel(18, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue
    i = map_xy_to_pixel(20, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue
    i = map_xy_to_pixel(21, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue
    i = map_xy_to_pixel(22, 5)
    pixels[i] = rainbow_colors[5] if toggle else color_blue

    i = map_xy_to_pixel(16, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_blue
    i = map_xy_to_pixel(17, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_blue
    i = map_xy_to_pixel(21, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_blue
    i = map_xy_to_pixel(22, 6)
    pixels[i] = rainbow_colors[6] if toggle else color_blue

    i = map_xy_to_pixel(16, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_blue
    i = map_xy_to_pixel(22, 7)
    pixels[i] = rainbow_colors[7] if toggle else color_blue


# Main loop
print(f"IBM LED Demo - RasQberry")
print(f"Layout: {config['layout']}")
print(f"Hardware: {config['pi_model']} with {config['led_count']} LEDs")
print(f"Pixel order: {config['pixel_order']}")
print()

while True:
    # Show solid color IBM logo
    pixels.fill(0)
    doibm(False)
    pixels.show()
    time.sleep(16 * DELAY * 0.025)

    # Show rainbow IBM logo
    pixels.fill(0)
    doibm(True)
    pixels.show()
    time.sleep(16 * DELAY * 0.025)

    # Animated sweep effect
    pixels.fill(0)
    for i in range(config['led_count']):
        for j in range(min(4, config['led_count'] - i)):
            if i + j < config['led_count']:
                pixels[i + j] = color_blue
        pixels.show()
        time.sleep(DELAY * 0.0025)
        pixels.fill(0)
