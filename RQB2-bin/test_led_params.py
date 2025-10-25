#!/usr/bin/env python3
"""
Experiment with different chunk sizes and delays

Usage:
    sudo PYTHONPATH=/usr/bin ~/RasQberry-Two/venv/RQB2/bin/python3 test_led_params.py
"""

import board
import neopixel_spi as neopixel
import time
from rq_led_utils import get_led_config

def test_params(pixels, num_pixels, chunk_size, delay_ms, color, test_name):
    """Test a specific combination of parameters"""
    print(f"\n{'='*60}")
    print(f"{test_name}")
    print(f"  Chunk size: {chunk_size} LEDs")
    print(f"  Delay: {delay_ms}ms between chunks")
    print(f"  Color: {color}")
    print(f"{'='*60}")

    # Fill with chunking
    for i in range(num_pixels):
        pixels[i] = color
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(delay_ms / 1000.0)

    pixels.show()
    time.sleep(delay_ms / 1000.0)

    print(f"  ALL {num_pixels} LEDs should be lit")
    print(f"  Holding 4 seconds - COUNT how many are ON")
    time.sleep(4)

    # Clear with same params
    for i in range(num_pixels):
        pixels[i] = (0, 0, 0)
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(delay_ms / 1000.0)

    pixels.show()
    time.sleep(delay_ms / 1000.0)

    print(f"  Holding 2 seconds - check if ALL turned OFF")
    time.sleep(2)


def main():
    print("\n" + "="*60)
    print("LED PARAMETER EXPERIMENT")
    print("="*60)
    print("\nTesting different chunk sizes and delays\n")

    config = get_led_config()
    num_pixels = 256
    pixel_order = getattr(neopixel, config['pixel_order'])
    pi_model = config['pi_model']

    spi = board.SPI()

    # Create with initialization
    from rq_led_utils import create_neopixel_strip
    pixels = create_neopixel_strip(spi, num_pixels, pixel_order,
                                   brightness=0.05, pi_model=pi_model)

    print("Testing various chunk sizes and delays...")
    print("For each test, report:")
    print("  - How many LEDs turned ON")
    print("  - How many turned OFF")
    print()

    try:
        # Baseline: What we know works
        test_params(pixels, num_pixels, 32, 1, (255, 255, 255),
                   "TEST 1: Baseline (chunk=32, delay=1ms, WHITE)")

        # Try larger chunks with small delay
        test_params(pixels, num_pixels, 64, 1, (0, 255, 0),
                   "TEST 2: Larger chunk (chunk=64, delay=1ms, GREEN)")

        # Try even larger with longer delay
        test_params(pixels, num_pixels, 100, 5, (0, 0, 255),
                   "TEST 3: Large chunk + delay (chunk=100, delay=5ms, BLUE)")

        # Try small chunks with no delay
        test_params(pixels, num_pixels, 16, 0, (255, 0, 0),
                   "TEST 4: Small chunk, no delay (chunk=16, delay=0ms, RED)")

        # Try very small chunks
        test_params(pixels, num_pixels, 8, 1, (255, 255, 0),
                   "TEST 5: Tiny chunks (chunk=8, delay=1ms, YELLOW)")

        # Try one LED at a time with delay
        test_params(pixels, num_pixels, 1, 0.1, (255, 0, 255),
                   "TEST 6: Individual LEDs (chunk=1, delay=0.1ms, MAGENTA)")

        # Try optimal middle ground
        test_params(pixels, num_pixels, 48, 2, (0, 255, 255),
                   "TEST 7: Middle ground (chunk=48, delay=2ms, CYAN)")

        print("\n" + "="*60)
        print("TESTS COMPLETE")
        print("="*60)
        print("\nPlease report which configurations worked:")
        print("  - Chunk size =")
        print("  - Delay =")
        print("  - Did all 256 turn ON?")
        print("  - Did all 256 turn OFF?")
        print("="*60)

        # Final cleanup
        for i in range(num_pixels):
            pixels[i] = (0, 0, 0)
            if (i + 1) % 32 == 0:
                pixels.show()
                time.sleep(0.001)
        pixels.show()

    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()