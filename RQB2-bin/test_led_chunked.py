#!/usr/bin/env python3
"""
Test LED strip with chunked writes to work around buffer limit

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_chunked.py
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


def test_chunked_fill(pixels, num_pixels, color, chunk_size, test_name):
    """
    Fill all LEDs with chunked writes

    Args:
        pixels: NeoPixel strip object
        num_pixels: Total number of LEDs
        color: (R, G, B) tuple
        chunk_size: Number of LEDs to update before calling show()
        test_name: Description for output
    """
    print(f"\n{'='*60}")
    print(f"{test_name}")
    print(f"Chunk size: {chunk_size} LEDs")
    print(f"{'='*60}")

    clear_leds(pixels)
    time.sleep(0.5)

    # Fill in chunks
    for i in range(num_pixels):
        pixels[i] = color

        # Call show() every chunk_size LEDs
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(0.001)
            print(f"  Updated LEDs 0-{i} ({i+1} total)")

    # Final show() for any remaining LEDs
    pixels.show()
    time.sleep(0.001)

    print(f"\n✓ All {num_pixels} LEDs should be lit")
    print(f"  Holding for 8 seconds - count how many are ON...")
    time.sleep(8)

    clear_leds(pixels)


def main():
    print("\n" + "="*60)
    print("CHUNKED WRITE TEST")
    print("="*60)
    print("\nTesting different chunk sizes to find optimal value")
    print("that works around 4096-byte buffer limit\n")

    # Load configuration
    config = get_led_config()
    num_pixels = config['led_count']
    pixel_order_str = config['pixel_order']
    pixel_order = getattr(neopixel, pixel_order_str)
    pi_model = config['pi_model']

    print(f"Configuration:")
    print(f"  LEDs: {num_pixels}")
    print(f"  Pi Model: {pi_model}")

    # Create strip
    spi = board.SPI()
    pixels = create_neopixel_strip(
        spi,
        num_pixels,
        pixel_order,
        brightness=0.05,  # 5% brightness to avoid Pi reboot from power draw
        pi_model=pi_model
    )

    print("\nStarting tests in 3 seconds...")
    time.sleep(3)

    try:
        # Test different chunk sizes
        # Each RGB pixel = 24 SPI bytes
        # 4096 byte buffer ÷ 24 = 170 LEDs max per chunk

        # Test 1: Chunk size 50 (what worked in sequential test)
        test_chunked_fill(pixels, num_pixels, (255, 255, 255), 50,
                         "TEST 1: WHITE - Chunk size 50")

        # Test 2: Chunk size 100
        test_chunked_fill(pixels, num_pixels, (0, 255, 0), 100,
                         "TEST 2: GREEN - Chunk size 100")

        # Test 3: Chunk size 128 (power of 2)
        test_chunked_fill(pixels, num_pixels, (0, 0, 255), 128,
                         "TEST 3: BLUE - Chunk size 128")

        # Test 4: Chunk size 160 (near theoretical limit)
        test_chunked_fill(pixels, num_pixels, (255, 0, 255), 160,
                         "TEST 4: MAGENTA - Chunk size 160")

        # Test 5: Single write (should fail for >168 LEDs)
        print(f"\n{'='*60}")
        print("TEST 5: YELLOW - Single write (no chunking)")
        print(f"{'='*60}")

        clear_leds(pixels)
        time.sleep(0.5)

        pixels.fill((255, 255, 0))
        pixels.show()
        time.sleep(0.001)

        print(f"\n✓ Single show() called")
        print(f"  Holding for 8 seconds - should see ~168 LEDs only...")
        time.sleep(8)

        # Clean up
        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)
        clear_leds(pixels)

        print("\n" + "="*60)
        print("RESULTS INTERPRETATION")
        print("="*60)
        print("\nIf chunking works:")
        print("  - Tests 1-4: All 256 LEDs should light up")
        print("  - Test 5: Only ~168 LEDs (buffer limit)")
        print("\nIf all tests show ~168 LEDs:")
        print("  - Chunking doesn't help")
        print("  - Library has deeper limitations")
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