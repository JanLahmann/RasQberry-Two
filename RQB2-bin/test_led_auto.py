#!/usr/bin/env python3
"""
Automated LED Diagnostic Tool for WS2812 strips
Runs all tests automatically and reports results

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_auto.py
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


def test_all_white(pixels, num_pixels):
    """Test 1: All LEDs white at low brightness"""
    print("\n" + "="*60)
    print("TEST 1: ALL WHITE (Low Brightness)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("NOW - ALL LEDS SHOULD BE WHITE\n")

    pixels.brightness = 0.1  # 10% brightness
    pixels.fill((255, 255, 255))
    pixels.show()
    time.sleep(0.001)

    print(f"✓ Set all {num_pixels} LEDs to white at 10% brightness")
    print("  LOOK AT THE STRIP - Are all LEDs white?")
    print("  Are the last LEDs dark or dimmer?")
    print("\nHolding for 8 seconds...")
    time.sleep(8)

    return True


def test_sequential_forward(pixels, num_pixels):
    """Test 2: Sequential fill from start"""
    print("\n" + "="*60)
    print("TEST 2: SEQUENTIAL GREEN (Start to End)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("NOW - LEDS FILLING GREEN FROM START TO END\n")

    clear_leds(pixels)
    time.sleep(0.5)

    print(f"Lighting LEDs 0 to {num_pixels-1} sequentially...")
    for i in range(num_pixels):
        pixels[i] = (0, 255, 0)  # Green
        if i % 50 == 0:
            pixels.show()
            time.sleep(0.001)

    pixels.show()
    time.sleep(0.001)

    print(f"\n✓ All {num_pixels} LEDs should be GREEN now")
    print("  LOOK - Do all green LEDs light up?")
    print("  Note which LED position starts failing (if any)")
    print("\nHolding for 8 seconds...")
    time.sleep(8)

    return True


def test_sequential_backward(pixels, num_pixels):
    """Test 3: Sequential fill from end"""
    print("\n" + "="*60)
    print("TEST 3: SEQUENTIAL BLUE (End to Start)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("NOW - LEDS FILLING BLUE FROM END TO START\n")

    clear_leds(pixels)
    time.sleep(0.5)

    print(f"Lighting LEDs {num_pixels-1} to 0 sequentially...")
    for i in range(num_pixels - 1, -1, -1):
        pixels[i] = (0, 0, 255)  # Blue
        if i % 50 == 0:
            pixels.show()
            time.sleep(0.001)

    pixels.show()
    time.sleep(0.001)

    print(f"\n✓ All {num_pixels} LEDs should be BLUE now")
    print("  LOOK - Does this work better than green forward?")
    print("  If yes → confirms power supply issue")
    print("\nHolding for 8 seconds...")
    time.sleep(8)

    return True


def test_sparse_pattern(pixels, num_pixels):
    """Test 4: Every 10th LED"""
    print("\n" + "="*60)
    print("TEST 4: SPARSE MAGENTA (Every 10th LED)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("NOW - EVERY 10th LED SHOULD BE MAGENTA/PINK\n")

    clear_leds(pixels)
    time.sleep(0.5)

    count = 0
    for i in range(0, num_pixels, 10):
        pixels[i] = (255, 0, 255)  # Magenta
        count += 1

    pixels.show()
    time.sleep(0.001)

    print(f"✓ {count} LEDs should be MAGENTA/PINK (every 10th)")
    print("  LOOK - Are all sparse LEDs bright, even at the end?")
    print("  If perfect here but Test 1 failed → Power supply issue")
    print("\nHolding for 8 seconds...")
    time.sleep(8)

    return True


def test_rapid_cycle(pixels, num_pixels):
    """Test 5: Rapid on/off of last 20 LEDs"""
    print("\n" + "="*60)
    print("TEST 5: BLINKING YELLOW (Last 20 LEDs)")
    print("="*60)
    print("Starting in 3 seconds...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1...")
    time.sleep(1)
    print("NOW - LAST 20 LEDS BLINKING YELLOW\n")

    clear_leds(pixels)
    time.sleep(0.5)

    print("Blinking last 20 LEDs 10 times...")
    for cycle in range(10):
        # On
        for i in range(num_pixels - 20, num_pixels):
            pixels[i] = (255, 255, 0)  # Yellow
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.1)

        # Off
        for i in range(num_pixels - 20, num_pixels):
            pixels[i] = (0, 0, 0)
        pixels.show()
        time.sleep(0.001)
        time.sleep(0.1)

    print("\n✓ Blink cycle complete")
    print("  LOOK - Did they blink consistently?")
    print("  If inconsistent → Timing/reset issue")
    print("\nHolding for 3 seconds...")
    time.sleep(3)

    return True


def main():
    print("\n" + "="*60)
    print("AUTOMATED LED DIAGNOSTIC TOOL")
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

    print("\nRunning 5 diagnostic tests...")
    print("Watch the LED strip and observe the behavior.\n")

    time.sleep(2)

    try:
        results = []

        # Run all tests
        results.append(("All White", test_all_white(pixels, num_pixels)))
        results.append(("Sequential Forward", test_sequential_forward(pixels, num_pixels)))
        results.append(("Sequential Backward", test_sequential_backward(pixels, num_pixels)))
        results.append(("Sparse Pattern", test_sparse_pattern(pixels, num_pixels)))
        results.append(("Rapid Cycle", test_rapid_cycle(pixels, num_pixels)))

        # Clean up
        print("\n" + "="*60)
        print("TESTS COMPLETE - Turning off LEDs")
        print("="*60)
        clear_leds(pixels)

        # Summary
        print("\n" + "="*60)
        print("DIAGNOSTIC SUMMARY")
        print("="*60)
        print("\nInterpretation Guide:")
        print("-" * 60)
        print("If Test 1 (all white) has dark LEDs at end:")
        print("  → Power supply voltage drop (MOST LIKELY)")
        print("  → Solution: Add power injection every 50-100 LEDs")
        print()
        print("If Test 2 fails but Test 3 works better:")
        print("  → Confirms power supply voltage drop issue")
        print()
        print("If Test 4 (sparse) works but Test 1 doesn't:")
        print("  → Power supply cannot handle full current load")
        print()
        print("If Test 5 (rapid cycle) is inconsistent:")
        print("  → Timing/reset delay issue or signal problems")
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