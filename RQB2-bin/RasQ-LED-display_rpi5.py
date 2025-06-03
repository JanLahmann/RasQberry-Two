#!/usr/bin/env python3
# 
# RasQ-LED Display - Raspberry Pi 5 Compatible Version
# Based on NeoPixel library strandtest example by Tony DiCola (tony@tonydicola.com)
# Updated for RPi 5 compatibility using SPI driver instead of PWM
#
# Usage:
#   python3 RasQ-LED-display_rpi5.py 001010100100100 
#   python3 RasQ-LED-display_rpi5.py 0 -c    # Clear the strip

from time import sleep
import board
import neopixel_spi as neopixel
import argparse
import os

# Load environment configuration
def load_config():
    """Load LED configuration from environment file with fallbacks"""
    config = {}
    config_paths = [
        "/usr/config/rasqberry_environment.env",
        os.path.expanduser("~/.local/config/rasqberry_environment.env"),
        "rasqberry_environment.env"
    ]
    
    # Try to load from available paths
    for config_path in config_paths:
        if os.path.exists(config_path):
            from dotenv import dotenv_values
            config = dotenv_values(config_path)
            print(f"Loaded config from: {config_path}")
            break
    else:
        print("Warning: Could not find environment config, using defaults")
    
    return config

# Parse LED configuration with safe defaults
config = load_config()
NUM_PIXELS = int(config.get("LED_COUNT", 192))
PIXEL_ORDER = neopixel.GRB
LED_BRIGHTNESS = int(config.get("LED_BRIGHTNESS", 100))  # 0-255

# Color definitions - using neopixel_spi format (24-bit RGB)
G = 0x00FF00  # Green
R = 0xFF0000  # Red  
B = 0x0000FF  # Blue
K = 0x000000  # Black (off)

# Qubit state to color mapping
to_color = {'1': B, '0': R}  # 1=Blue, 0=Red
wait_ms = 7  # delay in display cycle

def create_pixels():
    """Create NeoPixel_SPI object"""
    spi = board.SPI()
    return neopixel.NeoPixel_SPI(
        spi, NUM_PIXELS, 
        pixel_order=PIXEL_ORDER, 
        auto_write=False,
        brightness=LED_BRIGHTNESS / 255.0  # Convert to 0.0-1.0 range
    )

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
               "  python3 RasQ-LED-display_rpi5.py 001010100100100\n"
               "  python3 RasQ-LED-display_rpi5.py 0 -c",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("measurement", help="Binary string representing qubit states (0=Red, 1=Blue)")
    parser.add_argument('-c', '--clear', action='store_true', help='Clear the display and exit')
    args = parser.parse_args()

    # Create NeoPixel object
    try:
        pixels = create_pixels()
        print(f"Initialized {NUM_PIXELS} LEDs using SPI interface (RPi 5 compatible)")
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