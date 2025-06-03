# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT
# Modified for 8x24 column-major serpentine LED matrix

import time
import board
import neopixel_spi as neopixel

NUM_PIXELS = 192
PIXEL_ORDER = neopixel.GRB
COLORS = (0xFF0000, 0x00FF00, 0x0000FF)
color_blue = 0x0000FF
color_red = 0xFF0000
color_green = 0x00FF00
DELAY = 5

spi = board.SPI()

def plotcalc(y, x, color, pixels, rainbow):
    """
    Convert (y,x) coordinate to LED index for 8x24 column-major serpentine matrix
    y: 0-7 (row, 0=top)
    x: 0-23 (column, 0=left)
    
    Layout: Column-major with alternating direction
    - Even columns (0,2,4...): go down (y: 0→7)
    - Odd columns (1,3,5...): go up (y: 7→0)
    """
    # Bounds checking
    if x < 0 or x >= 24 or y < 0 or y >= 8:
        return
        
    if x % 2 == 0:  # Even columns go down (0→7)
        i = x * 8 + y
    else:  # Odd columns go up (7→0)
        i = x * 8 + (7 - y)

    if rainbow:
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
        color = rainbow_colors[y]

    pixels[i] = color

def doibm(toggle):
    # I (columns 0-5)
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

# B (columns 8-13)
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

#M (columns 16-22)
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

# Create NeoPixel object
pixels = neopixel.NeoPixel_SPI(
    spi, NUM_PIXELS, pixel_order=PIXEL_ORDER, auto_write=False
)

print("IBM LED Demo - 8x24 Column-Major Serpentine Matrix")
print("Press Ctrl+C to stop")

try:
    while True:
        doibm(0)  # Normal colors
        pixels.show()
        time.sleep(DELAY)
        doibm(1)  # Rainbow colors
        pixels.show()
        time.sleep(DELAY)
except KeyboardInterrupt:
    print("\nStopping demo...")
    pixels.fill(0)  # Turn off all LEDs
    pixels.show()
    print("All LEDs turned off")