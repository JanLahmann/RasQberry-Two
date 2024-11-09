# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

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
        color = 0xfa0100 #rot
      if (y == 5):
        color = 0xf9831f #orange
      if (y == 4):
        color = 0xf8df08 #gelb
      if (y == 3):
        color = 0x02a204 #gruen
      if (y == 2):
        color = 0x00c4ad #tuerkis
      if (y == 1):
        color = 0x0041b7 #blau
      if (y == 0):
        color = 0x83209e #lila

    pixels[i] = color

def doibm(toggle):
    # I
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

# B
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

#M
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

pixels = neopixel.NeoPixel_SPI(
    spi, NUM_PIXELS, pixel_order=PIXEL_ORDER, auto_write=False
)
while True:
  doibm(0)
  pixels.show()
  time.sleep(DELAY)
  doibm(1)
  pixels.show()
  time.sleep(DELAY)

pixels.fill(0)
