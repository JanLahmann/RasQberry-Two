#!/usr/bin/env python3
"""
Test script for virtual LED display.

This script tests the VirtualNeoPixel class by displaying a simple pattern.
Run the GUI first: python3 rq_led_virtual_gui.py

Usage:
    LED_VIRTUAL=true python3 test_virtual_led.py
"""

import os
import sys
import time

# Set virtual mode for testing
os.environ['LED_VIRTUAL'] = 'true'

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rq_led_virtual import VirtualNeoPixel

# Matrix dimensions
WIDTH = 24
HEIGHT = 8
NUM_PIXELS = WIDTH * HEIGHT


def map_xy_to_pixel(x, y):
    """Column-major serpentine layout (matches rq_led_utils.py)."""
    if x % 2 == 0:
        return x * HEIGHT + y
    else:
        return x * HEIGHT + (HEIGHT - 1 - y)


def test_basic_colors():
    """Test basic color display."""
    print("Creating virtual NeoPixel...")
    pixels = VirtualNeoPixel(None, NUM_PIXELS, brightness=1.0)

    print("\nTest 1: All RED")
    pixels.fill((255, 0, 0))
    pixels.show()
    time.sleep(1)

    print("Test 2: All GREEN")
    pixels.fill((0, 255, 0))
    pixels.show()
    time.sleep(1)

    print("Test 3: All BLUE")
    pixels.fill((0, 0, 255))
    pixels.show()
    time.sleep(1)

    print("Test 4: Clear (all off)")
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.5)


def test_pattern():
    """Test pattern display with coordinate mapping."""
    print("\nTest 5: Rainbow columns")
    pixels = VirtualNeoPixel(None, NUM_PIXELS, brightness=1.0)

    # Rainbow colors for each column
    for x in range(WIDTH):
        hue = int(255 * x / WIDTH)
        r, g, b = wheel(hue)
        for y in range(HEIGHT):
            idx = map_xy_to_pixel(x, y)
            pixels[idx] = (r, g, b)

    pixels.show()
    time.sleep(2)


def test_scrolling():
    """Test scrolling animation."""
    print("\nTest 6: Scrolling animation")
    pixels = VirtualNeoPixel(None, NUM_PIXELS, brightness=1.0)

    for frame in range(50):
        for x in range(WIDTH):
            for y in range(HEIGHT):
                hue = int(255 * ((x + frame) % WIDTH) / WIDTH)
                r, g, b = wheel(hue)
                idx = map_xy_to_pixel(x, y)
                pixels[idx] = (r, g, b)
        pixels.show()
        time.sleep(0.05)

    print("Test complete!")
    pixels.fill((0, 0, 0))
    pixels.show()


def wheel(pos):
    """Generate rainbow colors (0-255)."""
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    else:
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)


def main():
    print("=" * 50)
    print("Virtual LED Display Test")
    print("=" * 50)
    print(f"Matrix size: {WIDTH}x{HEIGHT} ({NUM_PIXELS} pixels)")
    print()
    print("Make sure the GUI is running:")
    print("  python3 rq_led_virtual_gui.py")
    print()

    test_basic_colors()
    test_pattern()
    test_scrolling()

    print("\nAll tests completed!")


if __name__ == "__main__":
    main()
