#!/usr/bin/env python3
# 
# based on NeoPixel library strandtest example by Tony DiCola (tony@tonydicola.com)
#

# test with    sudo python3 RasQ-LED-display.py  001010100100100 
# blank the strip with     sudo python3 RasQ-LED-display.py  0 -c

from time import sleep
from rpi_ws281x import PixelStrip, Color
import argparse

# Parse LED configuration with safe defaults
from dotenv import dotenv_values
config = dotenv_values("/usr/config/rasqberry_environment.env")  # fixme, making path dynamic

# Parse LED configuration with safe defaults
LED_COUNT_init = int(config.get("LED_COUNT", 0))
LED_PIN        = int(config.get("LED_PIN", 0))
LED_FREQ_HZ    = int(config.get("LED_FREQ_HZ", 0))  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = int(config.get("LED_DMA", 0))      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = int(config.get("LED_BRIGHTNESS", 0))  # Set to 0 for darkest and 255 for brightest
LED_INVERT     = config.get("LED_INVERT", "false").lower() == "true"  # True to invert signal
LED_CHANNEL    = int(config.get("LED_CHANNEL", 0))   # set to '1' for GPIOs 13,19, etc.
#LED_BRIGHTNESS = 100  # Set to 0 for darkest and 255 for brightest

#print("LED_COUNT_init ", LED_COUNT_init, "LED_PIN ", LED_PIN, "LED_FREQ_HZ ", LED_FREQ_HZ, "LED_DMA ", LED_DMA, "LED_BRIGHTNESS ", LED_BRIGHTNESS, "LED_INVERT ", LED_INVERT, "LED_CHANNEL ", LED_CHANNEL, "LED_BRIGHTNESS ", LED_BRIGHTNESS)
G = Color(0, 255, 0) # green
R = Color(255, 0, 0) # red
B = Color(0, 0, 255) # blue
K = Color(0, 0, 0) # black
to_color = {'1':B, '0':R} # translate qubit state to color
wait_ms = 7 # delay in display cycle

def display_on_strip(strip):
  #print("measurement ", measurement)
  color_strip = [to_color.get(n, n) for n in list(measurement)]
  #print("color_strip: ", color_strip)
  for i in range(strip.numPixels()):
      #strip.setPixelColor(i, R)
      strip.setPixelColor(i, color_strip[i])
      strip.show()
      sleep(wait_ms / 1000.0)

def colorWipe(strip, color=K, wait_ms=wait_ms):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        sleep(wait_ms / 1000.0)

# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("measurement")
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    if args.clear:
        strip = PixelStrip(LED_COUNT_init, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        colorWipe(strip, K, 10)
        exit(0)

    measurement=args.measurement
    LED_COUNT = len(measurement)

    # Create NeoPixel object with appropriate configuration.
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    try:
        display_on_strip(strip)
    except KeyboardInterrupt:
        if args.clear:
            colorWipe(strip, K, 10)

