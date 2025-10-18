#!/usr/bin/env python3
#
# RasQ-LED Display - Quantum Measurement Visualization on LED Strip
# Based on NeoPixel library strandtest example by Tony DiCola (tony@tonydicola.com)
# Updated for Pi4/Pi5 compatibility using SPI driver
#
# Usage:
#   python3 RasQ-LED-display.py 001010100100100
#   python3 RasQ-LED-display.py 0 -c    # Clear the strip

from time import sleep
import board
import neopixel_spi as neopixel
import argparse
from rq_led_utils import get_led_config, create_neopixel_strip

# Load configuration from system-wide environment
config = get_led_config()
NUM_PIXELS = config['led_count']
pixel_order_str = config['pixel_order']
pixel_order = getattr(neopixel, pixel_order_str)

# Color definitions - using neopixel_spi format (24-bit RGB)
G = 0x00FF00  # Green
R = 0xFF0000  # Red
B = 0x0000FF  # Blue
K = 0x000000  # Black (off)

# Qubit state to color mapping
to_color = {'1': B, '0': R}  # 1=Blue, 0=Red
wait_ms = 7  # delay in display cycle

def display_on_strip(pixels, measurement):
    """Display quantum measurement result on LED strip"""
    print(f"Displaying measurement: {measurement}")

    # Convert measurement string to colors
    measurement_list = list(measurement)

    # Clear all pixels first
    pixels.fill(K)

    # Set colors for measurement bits (up to available pixels)
    for i, bit in enumerate(measurement_list):
        if i >= NUM_PIXELS:
            print(f"Warning: Measurement has {len(measurement_list)} bits, but only {NUM_PIXELS} LEDs available")
            break

        color = to_color.get(bit, K)  # Get color or black for invalid bits
        pixels[i] = color
        pixels.show()
        sleep(wait_ms / 1000.0)

def color_wipe(pixels, color=K, wait_ms=wait_ms):
    """Wipe color across display a pixel at a time"""
    for i in range(NUM_PIXELS):
        pixels[i] = color
        pixels.show()
        sleep(wait_ms / 1000.0)

def clear_strip(pixels):
    """Clear all LEDs immediately"""
    pixels.fill(K)
    pixels.show()
    print("All LEDs cleared")

# Main program logic
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser(
        description="Display quantum measurement results on LED strip",
        epilog="Examples:\n"
               "  python3 RasQ-LED-display.py 001010100100100\n"
               "  python3 RasQ-LED-display.py 0 -c",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("measurement", help="Binary string representing qubit states (0=Red, 1=Blue)")
    parser.add_argument('-c', '--clear', action='store_true', help='Clear the display and exit')
    args = parser.parse_args()

    # Create NeoPixel object using rq_led_utils
    try:
        spi = board.SPI()
        pixels = create_neopixel_strip(
            spi,
            NUM_PIXELS,
            pixel_order,
            brightness=config['brightness'] / 255.0,
            pi_model=config['pi_model']
        )
        print(f"Initialized {NUM_PIXELS} LEDs ({config['pi_model']}, {pixel_order_str} pixel order)")
    except Exception as e:
        print(f"Error initializing LED strip: {e}")
        print("Make sure SPI is enabled: sudo raspi-config -> Interface Options -> SPI -> Enable")
        exit(1)

    try:
        if args.clear:
            # Clear mode - turn off all LEDs
            color_wipe(pixels, K, 10)
            exit(0)

        # Validate measurement string
        measurement = args.measurement
        if not all(bit in '01' for bit in measurement):
            print("Error: Measurement must contain only '0' and '1' characters")
            exit(1)

        if len(measurement) > NUM_PIXELS:
            print(f"Warning: Measurement has {len(measurement)} bits, truncating to {NUM_PIXELS}")
            measurement = measurement[:NUM_PIXELS]

        # Display the measurement
        display_on_strip(pixels, measurement)

        print(f"Displayed {len(measurement)} qubits. Press Ctrl+C to clear and exit.")

        # Keep the display on until interrupted
        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            print("\nClearing LEDs and exiting...")
            clear_strip(pixels)

    except KeyboardInterrupt:
        print("\nClearing LEDs and exiting...")
        clear_strip(pixels)
    except Exception as e:
        print(f"Error: {e}")
        try:
            clear_strip(pixels)
        except:
            pass
        exit(1)
