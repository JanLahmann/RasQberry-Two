#!/usr/bin/env python3
#
# RasQ-LED Display - Quantum Measurement Visualization on LED Strip
# Based on NeoPixel library strandtest example by Tony DiCola (tony@tonydicola.com)
# Updated for Pi4/Pi5 compatibility using PWM/PIO drivers
#
# Usage:
#   python3 RasQ-LED-display.py 001010100100100
#   python3 RasQ-LED-display.py 0 -c    # Clear the strip

from time import sleep
import argparse
from rq_led_utils import (
    get_led_config,
    create_neopixel_strip,
    chunked_show,
    map_xy_to_pixel,
    get_layout,
)

# Load configuration from system-wide environment
config = get_led_config()
NUM_PIXELS = config['led_count']
pixel_order_str = config['pixel_order']

# Logical matrix geometry for the active layout, so the qubit readout is laid out
# in xy space (row-major, TOP-LEFT origin) rather than following the raw
# serpentine chain - it tracks LED_LAYOUT (single/quad/y-flip) and renders the
# same way on the physical panel and the virtual GUI.
_layout = get_layout(config.get('led_layout')) or {}
WIDTH = _layout.get('width') or NUM_PIXELS
HEIGHT = _layout.get('height') or 1


def set_qubit(pixels, i, color):
    """Light the i-th qubit at logical (x, y) = (i % WIDTH, i // WIDTH).

    Row-major from the top-left, mapped through the active layout. Cells beyond
    the logical grid map to None and are skipped, so a longer bitstring degrades
    gracefully instead of indexing a raw chain position.
    """
    idx = map_xy_to_pixel(i % WIDTH, i // WIDTH)
    if idx is not None and 0 <= idx < NUM_PIXELS:
        pixels[idx] = color

# Color definitions - using (R, G, B) tuple format
G = (0, 255, 0)    # Green
R = (255, 0, 0)    # Red
B = (0, 0, 255)    # Blue
K = (0, 0, 0)      # Black (off)

# Qubit state to color mapping
to_color = {'1': B, '0': R}  # 1=Blue, 0=Red
wait_ms = 7  # delay in display cycle

def display_on_strip(pixels, measurement, animate=True, animation_duration=0.5):
    """Display quantum measurement result on LED strip with optional sequential animation

    Args:
        pixels: NeoPixel strip object
        measurement: Binary string of quantum measurement
        animate: If True, display LEDs sequentially; if False, show all at once
        animation_duration: Total time in seconds for sequential animation
    """
    print(f"Displaying measurement: {measurement}")

    # Convert measurement string to colors
    measurement_list = list(measurement)

    # Clear all pixels first
    pixels.fill(K)
    chunked_show(pixels)

    if animate and len(measurement_list) > 0:
        # Sequential animation - display each LED one at a time
        delay_per_led = animation_duration / len(measurement_list)

        for i, bit in enumerate(measurement_list):
            if i >= NUM_PIXELS:
                print(f"Warning: Measurement has {len(measurement_list)} bits, but only {NUM_PIXELS} LEDs available")
                break

            color = to_color.get(bit, K)  # Get color or black for invalid bits
            set_qubit(pixels, i, color)
            chunked_show(pixels)
            sleep(delay_per_led)
    else:
        # Instant display - set all LEDs at once
        for i, bit in enumerate(measurement_list):
            if i >= NUM_PIXELS:
                print(f"Warning: Measurement has {len(measurement_list)} bits, but only {NUM_PIXELS} LEDs available")
                break

            color = to_color.get(bit, K)  # Get color or black for invalid bits
            set_qubit(pixels, i, color)

        # Show all LEDs at once after setting colors
        chunked_show(pixels)

def color_wipe(pixels, color=K, wait_ms=wait_ms):
    """Wipe color across display a pixel at a time.

    Walks the RAW chain order on purpose: a wipe (used to clear the strip) must
    touch every physical pixel, including any not covered by the logical (x, y)
    grid, so it addresses pixels by chain index rather than via the layout map.
    """
    for i in range(NUM_PIXELS):
        pixels[i] = color
        chunked_show(pixels)
        sleep(wait_ms / 1000.0)

def clear_strip(pixels):
    """Clear all LEDs immediately"""
    pixels.fill(K)
    chunked_show(pixels)
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
    parser.add_argument('-t', '--timeout', type=float, default=None,
                        help='Auto-clear after N seconds (default: wait indefinitely)')
    args = parser.parse_args()

    # Create NeoPixel object using rq_led_utils
    # Uses PWM (Pi4) or PIO (Pi5) - auto-detects platform
    try:
        pixels = create_neopixel_strip(
            NUM_PIXELS,
            pixel_order_str,
            brightness=config['led_default_brightness']
        )
        print(f"Initialized {NUM_PIXELS} LEDs ({config['pi_model']}, {pixel_order_str} pixel order, GPIO{config['led_gpio_pin']})")
    except Exception as e:
        print(f"Error initializing LED strip: {e}")
        print("Note: This script requires root/sudo for GPIO access")
        print("Try: sudo python3 RasQ-LED-display.py ...")
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

        # Handle timeout or wait for interrupt
        if args.timeout is not None:
            print(f"Displayed {len(measurement)} qubits. Auto-clearing in {args.timeout}s...")
            sleep(args.timeout)
            clear_strip(pixels)
        else:
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
