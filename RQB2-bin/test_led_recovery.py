#!/usr/bin/env python3
"""
Test LED recovery after failed write

Tests whether we can recover from a failed (non-chunked) write
without rebooting or power-cycling the LEDs.

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_recovery.py
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import get_led_config, create_neopixel_strip


def test_recovery_attempt(pixels, num_pixels, recovery_name, recovery_func):
    """
    Test a recovery method after a failed write

    Args:
        pixels: NeoPixel strip object
        num_pixels: Number of LEDs
        recovery_name: Description of recovery method
        recovery_func: Function to call for recovery
    """
    print(f"\n{'='*60}")
    print(f"RECOVERY TEST: {recovery_name}")
    print(f"{'='*60}")

    # Step 1: Cause a failure (single write to 256 LEDs)
    print("Step 1: Causing failure with single write to 256 LEDs...")
    pixels.fill((255, 0, 0))  # Red
    pixels.show()
    time.sleep(0.001)

    print("  Expected: Only first ~168 LEDs are red")
    print("  Holding 3 seconds...")
    time.sleep(3)

    # Step 2: Attempt recovery
    print(f"Step 2: Attempting recovery - {recovery_name}...")
    recovery_func(pixels, num_pixels)

    # Step 3: Try chunked write
    print("Step 3: Testing if recovery worked with chunked green...")
    for i in range(num_pixels):
        pixels[i] = (0, 255, 0)
        if (i + 1) % 32 == 0:
            pixels.show()
            time.sleep(0.001)
    pixels.show()
    time.sleep(0.001)

    print("  If recovery worked: All 256 LEDs should be GREEN")
    print("  If recovery failed: Only ~168 LEDs are green")
    print("  Holding 5 seconds...")
    time.sleep(5)

    # Clear
    for i in range(num_pixels):
        pixels[i] = (0, 0, 0)
        if (i + 1) % 32 == 0:
            pixels.show()
            time.sleep(0.001)
    pixels.show()
    time.sleep(1)


def recovery_simple_clear(pixels, num_pixels):
    """Recovery: Simple chunked clear"""
    for i in range(num_pixels):
        pixels[i] = (0, 0, 0)
        if (i + 1) % 32 == 0:
            pixels.show()
            time.sleep(0.001)
    pixels.show()
    time.sleep(0.1)


def recovery_reverse_clear(pixels, num_pixels):
    """Recovery: Clear in reverse order"""
    for i in range(num_pixels - 1, -1, -1):
        pixels[i] = (0, 0, 0)
        if i % 32 == 0:
            pixels.show()
            time.sleep(0.001)
    pixels.show()
    time.sleep(0.1)


def recovery_multiple_passes(pixels, num_pixels):
    """Recovery: Multiple clear passes"""
    for pass_num in range(3):
        print(f"    Pass {pass_num + 1}/3...")
        for i in range(num_pixels):
            pixels[i] = (0, 0, 0)
            if (i + 1) % 32 == 0:
                pixels.show()
                time.sleep(0.001)
        pixels.show()
        time.sleep(0.05)


def recovery_toggle_pattern(pixels, num_pixels):
    """Recovery: Toggle LEDs on/off multiple times"""
    for cycle in range(3):
        print(f"    Cycle {cycle + 1}/3...")
        # On
        for i in range(num_pixels):
            pixels[i] = (50, 50, 50)
            if (i + 1) % 32 == 0:
                pixels.show()
                time.sleep(0.001)
        pixels.show()
        time.sleep(0.05)

        # Off
        for i in range(num_pixels):
            pixels[i] = (0, 0, 0)
            if (i + 1) % 32 == 0:
                pixels.show()
                time.sleep(0.001)
        pixels.show()
        time.sleep(0.05)


def recovery_long_delay(pixels, num_pixels):
    """Recovery: Clear with long delays"""
    for i in range(num_pixels):
        pixels[i] = (0, 0, 0)
        if (i + 1) % 32 == 0:
            pixels.show()
            time.sleep(0.1)  # 100ms delay
    pixels.show()
    time.sleep(0.5)


def main():
    print("\n" + "="*60)
    print("LED RECOVERY TEST")
    print("="*60)
    print("\nTesting if we can recover from failed writes")
    print("without rebooting or power-cycling LEDs\n")

    config = get_led_config()
    num_pixels = 256  # Force 256 for this test
    pixel_order = getattr(neopixel, config['pixel_order'])
    pi_model = config['pi_model']

    spi = board.SPI()

    # Create strip WITHOUT auto-initialization
    # (to test recovery methods)
    params = {'auto_write': False}
    if pi_model == 'Pi4':
        params['bit0'] = 0b10000000

    pixels = neopixel.NeoPixel_SPI(
        spi,
        num_pixels,
        brightness=0.05,
        pixel_order=pixel_order,
        **params
    )

    print("Testing 5 different recovery methods...")
    print("After each test, observe if all 256 LEDs turn green\n")

    input("Press Enter to start tests...")

    try:
        # Test 1: Simple chunked clear
        test_recovery_attempt(pixels, num_pixels,
                            "Simple Chunked Clear",
                            recovery_simple_clear)

        # Test 2: Reverse clear
        test_recovery_attempt(pixels, num_pixels,
                            "Reverse Order Clear",
                            recovery_reverse_clear)

        # Test 3: Multiple passes
        test_recovery_attempt(pixels, num_pixels,
                            "Multiple Clear Passes",
                            recovery_multiple_passes)

        # Test 4: Toggle pattern
        test_recovery_attempt(pixels, num_pixels,
                            "Toggle On/Off Pattern",
                            recovery_toggle_pattern)

        # Test 5: Long delays
        test_recovery_attempt(pixels, num_pixels,
                            "Long Delay Clear",
                            recovery_long_delay)

        print("\n" + "="*60)
        print("ALL TESTS COMPLETE")
        print("="*60)
        print("\nResults:")
        print("  If ANY recovery method worked:")
        print("    → We can recover in software")
        print("  If NONE worked:")
        print("    → Physical power cycle required")
        print("="*60)

        # Final cleanup
        recovery_simple_clear(pixels, num_pixels)

    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        recovery_simple_clear(pixels, num_pixels)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()