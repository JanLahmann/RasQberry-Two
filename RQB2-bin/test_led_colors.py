#!/usr/bin/env python3
"""
Test different colors with chunked writes to understand which work with 256 LEDs

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_colors.py
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import get_led_config, create_neopixel_strip


def clear_leds(pixels):
    """Turn off all LEDs"""
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.001)


def test_color(pixels, num_pixels, color, color_name):
    """
    Test a specific color with chunked writes
    """
    print(f"\n{'='*60}")
    print(f"TEST: {color_name} - RGB{color}")
    print(f"{'='*60}")

    clear_leds(pixels)
    time.sleep(0.5)

    # Fill in chunks of 50
    chunk_size = 50
    for i in range(num_pixels):
        pixels[i] = color

        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(0.001)

    # Final show
    pixels.show()
    time.sleep(0.001)

    print(f"✓ All {num_pixels} LEDs should be {color_name}")
    print(f"  Holding for 6 seconds - COUNT HOW MANY ARE LIT")
    time.sleep(6)

    clear_leds(pixels)


def main():
    print("\n" + "="*60)
    print("COLOR COMPATIBILITY TEST")
    print("="*60)
    print("\nTesting which colors work with all 256 LEDs\n")

    config = get_led_config()
    num_pixels = config['led_count']
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)
    pi_model = config['pi_model']

    print(f"Configuration:")
    print(f"  LEDs: {num_pixels}")
    print(f"  Brightness: 5%")

    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_pixels,
        pixel_order,
        brightness=0.05,
        pi_model=pi_model
    )

    print("\nStarting in 3 seconds...")
    time.sleep(3)

    try:
        # Test 1: Pure white (all channels 255)
        test_color(pixels, num_pixels, (255, 255, 255), "WHITE")

        # Test 2: Dim white (all channels equal but lower)
        test_color(pixels, num_pixels, (128, 128, 128), "DIM WHITE")

        # Test 3: Pure red
        test_color(pixels, num_pixels, (255, 0, 0), "RED")

        # Test 4: Pure green
        test_color(pixels, num_pixels, (0, 255, 0), "GREEN")

        # Test 5: Pure blue
        test_color(pixels, num_pixels, (0, 0, 255), "BLUE")

        # Test 6: Yellow (R+G)
        test_color(pixels, num_pixels, (255, 255, 0), "YELLOW")

        # Test 7: Cyan (G+B)
        test_color(pixels, num_pixels, (0, 255, 255), "CYAN")

        # Test 8: Magenta (R+B)
        test_color(pixels, num_pixels, (255, 0, 255), "MAGENTA")

        # Test 9: Orange (unequal values)
        test_color(pixels, num_pixels, (255, 128, 0), "ORANGE")

        # Test 10: Purple (unequal values)
        test_color(pixels, num_pixels, (128, 0, 255), "PURPLE")

        # Clean up
        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)
        clear_leds(pixels)

        print("\n" + "="*60)
        print("PLEASE REPORT RESULTS:")
        print("="*60)
        print("For each color, how many LEDs lit up?")
        print("  - 256 = SUCCESS (all LEDs)")
        print("  - 168 = FAILED (buffer limit)")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        clear_leds(pixels)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        clear_leds(pixels)


if __name__ == "__main__":
    main()