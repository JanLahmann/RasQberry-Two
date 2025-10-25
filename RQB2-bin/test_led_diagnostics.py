#!/usr/bin/env python3
"""
LED Diagnostic Tool for WS2812 strips
Tests various scenarios to identify power vs timing issues

Usage:
    sudo python3 test_led_diagnostics.py

This script runs several tests:
1. Turn all LEDs white at low brightness (tests power at constant load)
2. Sequential fill from start to end (identifies where LEDs start failing)
3. Sequential fill from end to start (tests reverse direction)
4. Turn on every 10th LED (tests if reduced power usage helps)
5. Rapid on/off cycle (tests timing/reset issues)
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import get_led_config, create_neopixel_strip


def test_all_white(pixels, num_pixels):
    """Test 1: All LEDs white at low brightness"""
    print("\n=== Test 1: All White (Low Brightness) ===")
    print("Expected: All LEDs should turn white")
    print("If last LEDs are dark: Power supply issue (voltage drop)")

    pixels.brightness = 0.1  # 10% brightness = ~6mA per LED
    for i in range(num_pixels):
        pixels[i] = (255, 255, 255)  # White

    pixels.show()
    time.sleep(0.001)  # 1ms reset delay (50µs minimum for WS2812)

    input("Press Enter to continue to next test...")


def test_sequential_fill_forward(pixels, num_pixels):
    """Test 2: Sequential fill from start to end"""
    print("\n=== Test 2: Sequential Fill (Start to End) ===")
    print("Expected: LEDs light up one by one from first to last")
    print("Note which LED number starts having issues")

    # Clear all
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.1)

    # Fill one at a time with delay
    for i in range(num_pixels):
        pixels[i] = (0, 255, 0)  # Green
        pixels.show()
        time.sleep(0.001)  # 1ms reset delay

        if i % 20 == 0:
            print(f"  LED {i}/{num_pixels} lit")

    print(f"All {num_pixels} LEDs should be green now")
    input("Press Enter to continue to next test...")


def test_sequential_fill_backward(pixels, num_pixels):
    """Test 3: Sequential fill from end to start"""
    print("\n=== Test 3: Sequential Fill (End to Start) ===")
    print("Expected: LEDs light up one by one from last to first")
    print("If this works better than forward: Confirms power/voltage drop")

    # Clear all
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.1)

    # Fill one at a time from end
    for i in range(num_pixels - 1, -1, -1):
        pixels[i] = (0, 0, 255)  # Blue
        pixels.show()
        time.sleep(0.001)  # 1ms reset delay

        if i % 20 == 0:
            print(f"  LED {i}/{num_pixels} lit")

    print(f"All {num_pixels} LEDs should be blue now")
    input("Press Enter to continue to next test...")


def test_sparse_pattern(pixels, num_pixels):
    """Test 4: Every 10th LED only"""
    print("\n=== Test 4: Sparse Pattern (Every 10th LED) ===")
    print("Expected: Only every 10th LED lights up")
    print("If this works perfectly: Power supply can't handle full load")

    # Clear all
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.1)

    # Light every 10th LED
    for i in range(0, num_pixels, 10):
        pixels[i] = (255, 0, 255)  # Magenta

    pixels.show()
    time.sleep(0.001)  # 1ms reset delay

    print(f"{num_pixels // 10} LEDs should be magenta")
    input("Press Enter to continue to next test...")


def test_timing_cycle(pixels, num_pixels):
    """Test 5: Rapid on/off cycle for last 10 LEDs"""
    print("\n=== Test 5: Timing Test (Last 10 LEDs Rapid Cycle) ===")
    print("Expected: Last 10 LEDs blink rapidly")
    print("If this fails: Timing/reset issue")

    # Clear all
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.1)

    print("Blinking last 10 LEDs 20 times...")
    for cycle in range(20):
        # Turn on last 10
        for i in range(num_pixels - 10, num_pixels):
            pixels[i] = (255, 255, 0)  # Yellow
        pixels.show()
        time.sleep(0.001)  # 1ms reset delay
        time.sleep(0.05)  # 50ms visible delay

        # Turn off last 10
        for i in range(num_pixels - 10, num_pixels):
            pixels[i] = (0, 0, 0)
        pixels.show()
        time.sleep(0.001)  # 1ms reset delay
        time.sleep(0.05)  # 50ms visible delay

    print("Cycle complete")
    input("Press Enter to finish...")


def main():
    print("=" * 60)
    print("LED Diagnostic Tool for WS2812 Strips")
    print("=" * 60)

    # Load configuration
    config = get_led_config()
    num_pixels = config['led_count']
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)

    print(f"\nConfiguration:")
    print(f"  LEDs: {num_pixels}")
    print(f"  Pin: GPIO{config['led_pin']}")
    print(f"  Pi Model: {config['pi_model']}")
    print(f"  Pixel Order: {pixel_order_str}")
    print(f"  Brightness: {config['brightness']}/255")

    # Create strip
    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_pixels,
        pixel_order,
        brightness=config['brightness'] / 255.0,
        pi_model=config['pi_model']
    )

    print("\nThis diagnostic will run 5 tests to identify LED issues.")
    print("Watch the LEDs carefully and note any problems.\n")
    input("Press Enter to start tests...")

    try:
        # Run all tests
        test_all_white(pixels, num_pixels)
        test_sequential_fill_forward(pixels, num_pixels)
        test_sequential_fill_backward(pixels, num_pixels)
        test_sparse_pattern(pixels, num_pixels)
        test_timing_cycle(pixels, num_pixels)

        # Clean up
        print("\n=== Tests Complete ===")
        print("Turning off all LEDs...")
        pixels.fill((0, 0, 0))
        pixels.show()
        time.sleep(0.001)

        print("\n" + "=" * 60)
        print("Diagnostic Summary:")
        print("=" * 60)
        print("If Test 1 (all white) shows dark LEDs at the end:")
        print("  → Power supply voltage drop (most likely)")
        print("  → Solution: Add power injection every 50-100 LEDs")
        print()
        print("If Test 2 fails but Test 3 works better:")
        print("  → Confirms power supply issue")
        print()
        print("If Test 4 (sparse) works perfectly:")
        print("  → Power supply can't handle full load")
        print()
        print("If Test 5 (timing) fails:")
        print("  → Timing/reset delay issue or signal integrity")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        pixels.fill((0, 0, 0))
        pixels.show()
    except Exception as e:
        print(f"\nError during test: {e}")
        pixels.fill((0, 0, 0))
        pixels.show()


if __name__ == "__main__":
    main()
