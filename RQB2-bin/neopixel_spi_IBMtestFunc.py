# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
# Modified for RasQberry: Pi4/Pi5 compatible IBM LED demo with original layout

import time
import board
import neopixel_spi as neopixel
from rq_led_utils import get_led_config, create_neopixel_strip

# Load configuration from environment file
config = get_led_config()

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

def plotcalc(y, x, color, pixels, rainbow):
    """
    Calculate pixel index for 192-LED strip in specific serpentine layout.

    Args:
        y: Row index (0-7)
        x: Column index (0-23)
        color: Base color value
        pixels: NeoPixel strip object
        rainbow: If True, override color with rainbow gradient based on y

    Note: This uses the original (y, x) coordinate system and layout calculation.
    """
    # top row
    x1 = x * 4 + (0 if x % 2 == 0 else 3)
    y1 = (7 - y if x % 2 == 0 else y - 7)

    # bottom row
    x2 = 96 + (23 - x) * 4 + (0 if x % 2 == 0 else 3)
    y2 = (3 - y if x % 2 == 0 else y - 3)

    i = x2 + y2 if y < 4 else x1 + y1

    if rainbow:
        if (y == 7):
            color = 0xfb80bf #pink
        if (y == 6):
            color = 0xfa0100 #red
        if (y == 5):
            color = 0xf9831f #orange
        if (y == 4):
            color = 0xf8df08 #yellow
        if (y == 3):
            color = 0x02a204 #green
        if (y == 2):
            color = 0x00c4ad #turquoise
        if (y == 1):
            color = 0x0041b7 #blue
        if (y == 0):
            color = 0x83209e #purple

    pixels[i] = color

def doibm(toggle):
    """
    Draw IBM logo on LED matrix.

    Args:
        toggle: If True, use rainbow colors; if False, use solid colors (green/red/blue)
    """
    # Letter "I" (green)
    plotcalc(0,0,color_green,pixels,toggle)
    plotcalc(0,1,color_green,pixels,toggle)
    plotcalc(0,2,color_green,pixels,toggle)
    plotcalc(0,3,color_green,pixels,toggle)
    plotcalc(0,4,color_green,pixels,toggle)
    plotcalc(0,5,color_green,pixels,toggle)
    plotcalc(1,0,color_green,pixels,toggle)
    plotcalc(1,1,color_green,pixels,toggle)
    plotcalc(1,2,color_green,pixels,toggle)
    plotcalc(1,3,color_green,pixels,toggle)
    plotcalc(1,4,color_green,pixels,toggle)
    plotcalc(1,5,color_green,pixels,toggle)
    plotcalc(2,2,color_green,pixels,toggle)
    plotcalc(2,3,color_green,pixels,toggle)
    plotcalc(3,2,color_green,pixels,toggle)
    plotcalc(3,3,color_green,pixels,toggle)
    plotcalc(4,2,color_green,pixels,toggle)
    plotcalc(4,3,color_green,pixels,toggle)
    plotcalc(5,2,color_green,pixels,toggle)
    plotcalc(5,3,color_green,pixels,toggle)
    plotcalc(6,0,color_green,pixels,toggle)
    plotcalc(6,1,color_green,pixels,toggle)
    plotcalc(6,2,color_green,pixels,toggle)
    plotcalc(6,3,color_green,pixels,toggle)
    plotcalc(6,4,color_green,pixels,toggle)
    plotcalc(6,5,color_green,pixels,toggle)
    plotcalc(7,0,color_green,pixels,toggle)
    plotcalc(7,1,color_green,pixels,toggle)
    plotcalc(7,2,color_green,pixels,toggle)
    plotcalc(7,3,color_green,pixels,toggle)
    plotcalc(7,4,color_green,pixels,toggle)
    plotcalc(7,5,color_green,pixels,toggle)

    # Letter "B" (red)
    plotcalc(0,8,color_red,pixels,toggle)
    plotcalc(0,9,color_red,pixels,toggle)
    plotcalc(0,10,color_red,pixels,toggle)
    plotcalc(0,11,color_red,pixels,toggle)
    plotcalc(0,12,color_red,pixels,toggle)
    plotcalc(1,8,color_red,pixels,toggle)
    plotcalc(1,9,color_red,pixels,toggle)
    plotcalc(1,12,color_red,pixels,toggle)
    plotcalc(1,13,color_red,pixels,toggle)
    plotcalc(2,8,color_red,pixels,toggle)
    plotcalc(2,9,color_red,pixels,toggle)
    plotcalc(2,12,color_red,pixels,toggle)
    plotcalc(2,13,color_red,pixels,toggle)
    plotcalc(3,8,color_red,pixels,toggle)
    plotcalc(3,9,color_red,pixels,toggle)
    plotcalc(3,10,color_red,pixels,toggle)
    plotcalc(3,11,color_red,pixels,toggle)
    plotcalc(3,12,color_red,pixels,toggle)
    plotcalc(4,8,color_red,pixels,toggle)
    plotcalc(4,9,color_red,pixels,toggle)
    plotcalc(4,10,color_red,pixels,toggle)
    plotcalc(4,11,color_red,pixels,toggle)
    plotcalc(4,12,color_red,pixels,toggle)
    plotcalc(5,8,color_red,pixels,toggle)
    plotcalc(5,9,color_red,pixels,toggle)
    plotcalc(5,12,color_red,pixels,toggle)
    plotcalc(5,13,color_red,pixels,toggle)
    plotcalc(6,8,color_red,pixels,toggle)
    plotcalc(6,9,color_red,pixels,toggle)
    plotcalc(6,12,color_red,pixels,toggle)
    plotcalc(6,13,color_red,pixels,toggle)
    plotcalc(7,8,color_red,pixels,toggle)
    plotcalc(7,9,color_red,pixels,toggle)
    plotcalc(7,10,color_red,pixels,toggle)
    plotcalc(7,11,color_red,pixels,toggle)
    plotcalc(7,12,color_red,pixels,toggle)

    # Letter "M" (blue)
    plotcalc(0,16,color_blue,pixels,toggle)
    plotcalc(0,17,color_blue,pixels,toggle)
    plotcalc(0,21,color_blue,pixels,toggle)
    plotcalc(0,22,color_blue,pixels,toggle)
    plotcalc(1,16,color_blue,pixels,toggle)
    plotcalc(1,17,color_blue,pixels,toggle)
    plotcalc(1,21,color_blue,pixels,toggle)
    plotcalc(1,22,color_blue,pixels,toggle)
    plotcalc(2,16,color_blue,pixels,toggle)
    plotcalc(2,17,color_blue,pixels,toggle)
    plotcalc(2,21,color_blue,pixels,toggle)
    plotcalc(2,22,color_blue,pixels,toggle)
    plotcalc(3,16,color_blue,pixels,toggle)
    plotcalc(3,17,color_blue,pixels,toggle)
    plotcalc(3,21,color_blue,pixels,toggle)
    plotcalc(3,22,color_blue,pixels,toggle)
    plotcalc(4,16,color_blue,pixels,toggle)
    plotcalc(4,17,color_blue,pixels,toggle)
    plotcalc(4,19,color_blue,pixels,toggle)
    plotcalc(4,21,color_blue,pixels,toggle)
    plotcalc(4,22,color_blue,pixels,toggle)
    plotcalc(5,16,color_blue,pixels,toggle)
    plotcalc(5,17,color_blue,pixels,toggle)
    plotcalc(5,18,color_blue,pixels,toggle)
    plotcalc(5,20,color_blue,pixels,toggle)
    plotcalc(5,21,color_blue,pixels,toggle)
    plotcalc(5,22,color_blue,pixels,toggle)
    plotcalc(6,16,color_blue,pixels,toggle)
    plotcalc(6,17,color_blue,pixels,toggle)
    plotcalc(6,21,color_blue,pixels,toggle)
    plotcalc(6,22,color_blue,pixels,toggle)
    plotcalc(7,16,color_blue,pixels,toggle)
    plotcalc(7,22,color_blue,pixels,toggle)

# Main loop - simple toggle between solid colors and rainbow
# Hardware info not printed to avoid terminal pollution in whiptail menus
import sys
import select

print("Press Enter to stop...")
print()

try:
    while True:
        doibm(0)  # Solid colors: I=green, B=red, M=blue
        pixels.show()
        time.sleep(DELAY)
        doibm(1)  # Rainbow gradient based on rows
        pixels.show()
        time.sleep(DELAY)

        # Check for Enter key press (non-blocking)
        if select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()
            print("\nStopping demo...")
            break
except KeyboardInterrupt:
    print("\nStopping demo...")

# Turn off all LEDs
pixels.fill(0)
pixels.show()
