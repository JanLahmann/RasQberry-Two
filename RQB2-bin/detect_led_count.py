#!/usr/bin/env python3
"""
Detect how many LEDs are actually connected

Lights up LEDs incrementally to visually count them

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 detect_led_count.py
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import create_neopixel_strip

def detect_led_count():
    """Incrementally light up LEDs to count them"""

    # Start with maximum possible
    max_test = 300

    spi = board.SPI()
    pixels = create_neopixel_strip(spi, max_test, neopixel.GRB,
                                   brightness=0.05, pi_model="Pi5")

    chunk_size = 8
    delay = 0.002

    print("\n" + "="*60)
    print("LED COUNT DETECTION")
    print("="*60)
    print(f"\nTesting up to {max_test} LEDs")
    print("Watch the strip and count the lit LEDs\n")

    # Test in batches of 50
    for batch_end in [50, 100, 150, 200, 250, 300]:
        print(f"\nLighting LEDs 0 to {batch_end-1} ({batch_end} total)")
        print(f"Color: {'RED' if batch_end <= 100 else 'GREEN' if batch_end <= 200 else 'BLUE'}")

        # Clear all first
        for i in range(max_test):
            pixels[i] = (0, 0, 0)
            if (i + 1) % chunk_size == 0:
                pixels.show()
                time.sleep(delay)
        pixels.show()
        time.sleep(0.5)

        # Light up to batch_end
        if batch_end <= 100:
            color = (255, 0, 0)  # Red
        elif batch_end <= 200:
            color = (0, 255, 0)  # Green
        else:
            color = (0, 0, 255)  # Blue

        for i in range(batch_end):
            pixels[i] = color
            if (i + 1) % chunk_size == 0:
                pixels.show()
                time.sleep(delay)
        pixels.show()
        time.sleep(delay)

        print(f"  Holding 5 seconds - COUNT the lit LEDs")
        time.sleep(5)

    # Final test - light each LED individually with number
    print("\n" + "="*60)
    print("PRECISE COUNT - Individual LED Test")
    print("="*60)
    print("\nLighting LEDs one by one in groups of 10")
    print("The last lit LED shows the total count\n")

    # Clear all
    for i in range(max_test):
        pixels[i] = (0, 0, 0)
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(delay)
    pixels.show()
    time.sleep(1)

    # Light one by one, showing every 10th
    for i in range(max_test):
        pixels[i] = (255, 255, 0)  # Yellow

        if (i + 1) % 10 == 0:
            pixels.show()
            time.sleep(delay)
            print(f"  LED {i} (count: {i+1})")
            time.sleep(0.5)

    pixels.show()

    print("\n" + "="*60)
    print("DETECTION COMPLETE")
    print("="*60)
    print("\nWhat is the highest LED number that lit up?")
    print("That number + 1 = total LED count")
    print("\nExample:")
    print("  Last lit LED = 255 → Total count = 256")
    print("  Last lit LED = 191 → Total count = 192")
    print("="*60)

    time.sleep(5)

    # Clear
    for i in range(max_test):
        pixels[i] = (0, 0, 0)
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(delay)
    pixels.show()


if __name__ == "__main__":
    try:
        detect_led_count()
    except KeyboardInterrupt:
        print("\n\nDetection interrupted")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()