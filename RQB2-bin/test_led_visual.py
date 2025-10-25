#!/usr/bin/env python3
"""
Visual LED Diagnostic Tool for WS2812 strips
Uses LED animations to indicate which test is running

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_visual.py
"""

import board
import neopixel_spi as neopixel
import time
import sys
from rq_led_utils import get_led_config, create_neopixel_strip


def clear_leds(pixels):
    """Turn off all LEDs"""
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.001)


def visual_countdown(pixels, num_pixels, test_number):
    """
    Visual countdown using LEDs
    Shows test number (1-5) by flashing that many LEDs, then 3-2-1 countdown
    """
    clear_leds(pixels)
    time.sleep(0.5)

    # Flash test number (e.g., 3 flashes for Test 3)
    for flash in range(test_number):
        for i in range(min(10, num_pixels)):
            pixels[i] = (255, 255, 255)  # White
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.3)

        clear_leds(pixels)
        time.sleep(0.3)

    time.sleep(0.5)

    # 3-2-1 countdown using red LEDs
    for count in [3, 2, 1]:
        num_leds = count * 5  # 15, 10, 5 LEDs
        for i in range(min(num_leds, num_pixels)):
            pixels[i] = (255, 0, 0)  # Red
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.7)
        clear_leds(pixels)
        time.sleep(0.3)


def test_1_all_white(pixels, num_pixels):
    """Test 1: All LEDs white at low brightness"""
    print("\n" + "="*60)
    print("TEST 1: ALL WHITE (Low Brightness)")
    print("="*60)

    visual_countdown(pixels, num_pixels, 1)

    # THE TEST: All white at 10% brightness
    pixels.brightness = 0.1
    pixels.fill((255, 255, 255))
    pixels.show()
    time.sleep(0.001)

    print("✓ All LEDs WHITE at 10% brightness")
    print("  Holding for 10 seconds - check if last LEDs are dark...")
    time.sleep(10)


def test_2_sequential_green(pixels, num_pixels):
    """Test 2: Sequential fill from start"""
    print("\n" + "="*60)
    print("TEST 2: SEQUENTIAL GREEN (Start to End)")
    print("="*60)

    visual_countdown(pixels, num_pixels, 2)

    # THE TEST: Sequential green fill
    pixels.brightness = 0.4  # Back to normal brightness
    for i in range(num_pixels):
        pixels[i] = (0, 255, 0)  # Green
        if i % 50 == 0:
            pixels.show()
            time.sleep(0.001)

    pixels.show()
    time.sleep(0.001)

    print("✓ All LEDs should be GREEN")
    print("  Holding for 10 seconds - check which LED starts failing...")
    time.sleep(10)


def test_3_sequential_blue(pixels, num_pixels):
    """Test 3: Sequential fill from end"""
    print("\n" + "="*60)
    print("TEST 3: SEQUENTIAL BLUE (End to Start)")
    print("="*60)

    visual_countdown(pixels, num_pixels, 3)

    # THE TEST: Sequential blue fill backward
    clear_leds(pixels)
    time.sleep(0.5)

    pixels.brightness = 0.4
    for i in range(num_pixels - 1, -1, -1):
        pixels[i] = (0, 0, 255)  # Blue
        if i % 50 == 0:
            pixels.show()
            time.sleep(0.001)

    pixels.show()
    time.sleep(0.001)

    print("✓ All LEDs should be BLUE")
    print("  Holding for 10 seconds - compare to green test...")
    time.sleep(10)


def test_4_sparse_magenta(pixels, num_pixels):
    """Test 4: Every 10th LED"""
    print("\n" + "="*60)
    print("TEST 4: SPARSE MAGENTA (Every 10th LED)")
    print("="*60)

    visual_countdown(pixels, num_pixels, 4)

    # THE TEST: Sparse pattern
    clear_leds(pixels)
    time.sleep(0.5)

    pixels.brightness = 0.4
    count = 0
    for i in range(0, num_pixels, 10):
        pixels[i] = (255, 0, 255)  # Magenta
        count += 1

    pixels.show()
    time.sleep(0.001)

    print(f"✓ {count} LEDs should be MAGENTA (every 10th)")
    print("  Holding for 10 seconds - all should be bright...")
    time.sleep(10)


def test_5_blinking_yellow(pixels, num_pixels):
    """Test 5: Rapid on/off of last 20 LEDs"""
    print("\n" + "="*60)
    print("TEST 5: BLINKING YELLOW (Last 20 LEDs)")
    print("="*60)

    visual_countdown(pixels, num_pixels, 5)

    # THE TEST: Blinking last 20
    clear_leds(pixels)
    time.sleep(0.5)

    pixels.brightness = 0.4
    print("Blinking last 20 LEDs 15 times...")
    for cycle in range(15):
        # On
        for i in range(num_pixels - 20, num_pixels):
            pixels[i] = (255, 255, 0)  # Yellow
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.15)

        # Off
        for i in range(num_pixels - 20, num_pixels):
            pixels[i] = (0, 0, 0)
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.15)

    print("✓ Blink cycle complete")
    time.sleep(2)


def main():
    print("\n" + "="*60)
    print("VISUAL LED DIAGNOSTIC TOOL")
    print("="*60)
    print("\nEach test shows:")
    print("  1. Test number (1-5 white flashes)")
    print("  2. Countdown (red LEDs: 15-10-5)")
    print("  3. The actual test pattern")
    print("="*60)

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

    # Create strip
    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_pixels,
        pixel_order,
        brightness=config['brightness'] / 255.0,
        pi_model=config['pi_model']
    )

    print("\nStarting tests in 3 seconds...")
    time.sleep(3)

    try:
        # Run all tests with visual indicators
        test_1_all_white(pixels, num_pixels)
        test_2_sequential_green(pixels, num_pixels)
        test_3_sequential_blue(pixels, num_pixels)
        test_4_sparse_magenta(pixels, num_pixels)
        test_5_blinking_yellow(pixels, num_pixels)

        # Clean up
        print("\n" + "="*60)
        print("ALL TESTS COMPLETE")
        print("="*60)
        clear_leds(pixels)

        # Summary
        print("\n" + "="*60)
        print("WHAT TO REPORT:")
        print("="*60)
        print("\nTest 1 (WHITE at 10% brightness):")
        print("  - Were all LEDs white?")
        print("  - Were last LEDs dark/dimmer?")
        print()
        print("Test 2 (GREEN sequential forward):")
        print("  - Did all LEDs turn green?")
        print("  - Which LED number started failing?")
        print()
        print("Test 3 (BLUE sequential backward):")
        print("  - Did all LEDs turn blue?")
        print("  - Better/worse than green test?")
        print()
        print("Test 4 (MAGENTA sparse - every 10th):")
        print("  - Were all sparse LEDs bright?")
        print()
        print("Test 5 (YELLOW blinking last 20):")
        print("  - Did they blink consistently?")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        clear_leds(pixels)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        clear_leds(pixels)
        sys.exit(1)


if __name__ == "__main__":
    main()