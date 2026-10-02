"""
Hello, LEDs: light the RasQberry LED panel from your own program.

Run it:  rq_python 03_led_hello.py
         (on a Raspberry Pi 5, python3 03_led_hello.py and Thonny work too;
          a Raspberry Pi 4 needs rq_python, see README.md)

The panel is a grid: x runs from 0 (left) to width-1 (right), y from 0 (top)
to height-1 (bottom). set_xy() finds the right LED, whatever the wiring.
"""
import time

from rq_led_utils import clear_all_leds, get_pixels, matrix_size, set_xy

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

pixels = get_pixels(brightness=0.2)
width, height = matrix_size()
print(f"The panel has {width} x {height} LEDs")

try:
    # The four corners: top-left red, top-right green, bottom-left green,
    # bottom-right blue.
    set_xy(pixels, 0, 0, RED)
    set_xy(pixels, width - 1, 0, GREEN)
    set_xy(pixels, 0, height - 1, GREEN)
    set_xy(pixels, width - 1, height - 1, BLUE)
    pixels.show()                    # nothing changes on the panel before show()
    time.sleep(3)

    # A dot runs across every row, from top to bottom.
    for y in range(height):
        for x in range(width):
            pixels.fill((0, 0, 0))
            set_xy(pixels, x, y, GREEN)
            pixels.show()
            time.sleep(0.02)
finally:
    clear_all_leds()                 # leave the panel dark, also after Ctrl+C
