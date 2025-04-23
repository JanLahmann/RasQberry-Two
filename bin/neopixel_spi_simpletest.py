# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
import neopixel_spi as neopixel

NUM_PIXELS = 192
PIXEL_ORDER = neopixel.GRB
COLORS = (0xFF0000, 0x00FF00, 0x0000FF)
DELAY = 0.0250

spi = board.SPI()

pixels = neopixel.NeoPixel_SPI(
    spi, NUM_PIXELS, pixel_order=PIXEL_ORDER, auto_write=False
)

while True:
    for color in COLORS:
#I
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

#B
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
        #pixels[159] = color
        pixels[158] = color
        pixels[157] = color
        pixels[156] = color

#M
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

        pixels.show()
        time.sleep(16*DELAY)
        pixels.fill(0) 
        for i in range(NUM_PIXELS):
           pixels[i] = color
           if (i+1) < NUM_PIXELS:
             pixels[i+1] = color
           if (i+2) < NUM_PIXELS:
             pixels[i+2] = color 
           if (i+3) < NUM_PIXELS:
             pixels[i+3] = color 
           pixels.show()
           time.sleep(DELAY)
           pixels.fill(0)
