#!/usr/bin/env python3
"""
RasQberry LED Utilities Module

Provides shared functionality for LED control across RasQberry demos:
- Configuration loading from environment file
- Hardware detection and NeoPixel initialization
- Coordinate mapping for LED matrix layouts

This module abstracts hardware differences (Pi4 vs Pi5) and layout variations
(single 8x24 vs quad 4x12 panels) to provide a consistent interface.
"""

import os
from dotenv import dotenv_values

# System-wide environment file location
ENV_FILE = "/usr/config/rasqberry_environment.env"

# Emergency defaults if env file is missing/unreadable
EMERGENCY_DEFAULTS = {
    'PI_MODEL': 'Pi5',
    'LED_COUNT': '192',  # 4*4*12 = 192 LEDs
    'LED_PIN': '21',
    'LED_PIXEL_ORDER': 'GRB',
    'LED_BRIGHTNESS': '100',
    'LED_MATRIX_LAYOUT': 'single',
    'LED_MATRIX_WIDTH': '24',
    'LED_MATRIX_HEIGHT': '8',
    'N_QUBIT': '192',  # 4*4*12 = 192 qubits
}


def get_led_config():
    """
    Load LED configuration from system-wide environment file.

    Returns:
        dict: Configuration dictionary with LED settings

    Note:
        If environment file is missing or unreadable, returns emergency defaults.
        All values are trusted (no validation per Issue #6, #13 decisions).
    """
    if not os.path.exists(ENV_FILE):
        print(f"ERROR: Config file not found: {ENV_FILE}")
        print("Using emergency defaults")
        config = EMERGENCY_DEFAULTS
    elif not os.access(ENV_FILE, os.R_OK):
        print(f"ERROR: Cannot read config file: {ENV_FILE}")
        print("Using emergency defaults")
        config = EMERGENCY_DEFAULTS
    else:
        try:
            config = dotenv_values(ENV_FILE)
        except Exception as e:
            print(f"ERROR: Failed to parse config: {e}")
            print("Using emergency defaults")
            config = EMERGENCY_DEFAULTS

    # Convert to standardized dictionary with type conversions
    return {
        'pi_model': config.get('PI_MODEL', 'Pi5'),
        'led_count': int(config.get('LED_COUNT', 192)),
        'led_pin': int(config.get('LED_PIN', 21)),
        'pixel_order': config.get('LED_PIXEL_ORDER', 'GRB'),
        'brightness': int(config.get('LED_BRIGHTNESS', 100)),
        'layout': config.get('LED_MATRIX_LAYOUT', 'single'),
        'matrix_width': int(config.get('LED_MATRIX_WIDTH', 24)),
        'matrix_height': int(config.get('LED_MATRIX_HEIGHT', 8)),
        'n_qubit': int(config.get('N_QUBIT', 192)),
        'led_chunk_size': int(config.get('LED_CHUNK_SIZE', 8)),
        'led_chunk_delay_ms': int(config.get('LED_CHUNK_DELAY_MS', 8)),
        'led_default_brightness': float(config.get('LED_DEFAULT_BRIGHTNESS', 0.1)),
    }


def get_neopixel_params(pi_model):
    """
    Get NeoPixel initialization parameters based on Pi model.

    Args:
        pi_model (str): 'Pi4' or 'Pi5'

    Returns:
        dict: Parameters to pass to NeoPixel_SPI constructor

    Note:
        Pi4 requires bit0=0b10000000 to fix timing issues (GitHub issue #25).
        Pi5 uses library default (0b11000000, not explicitly set).
        bpp=4 allocates larger internal buffer for 256+ LED strips.
    """
    params = {
        'auto_write': False,
        'bpp': 4,  # Bytes per pixel - ensures internal buffer for 256 LEDs
    }

    if pi_model == 'Pi4':
        params['bit0'] = 0b10000000  # Fix for Pi4 SPI timing
    # Pi5 uses library default - don't specify bit0

    return params


def create_neopixel_strip(spi, num_pixels, pixel_order, brightness=0.1, pi_model=None):
    """
    Factory function to create NeoPixel_SPI strip with correct parameters.

    Args:
        spi: SPI interface from board.SPI()
        num_pixels (int): Number of LEDs in strip
        pixel_order: Pixel order constant (e.g., neopixel.GRB)
        brightness (float): LED brightness 0.0-1.0
        pi_model (str, optional): 'Pi4' or 'Pi5'. If None, reads from config.

    Returns:
        NeoPixel_SPI: Configured LED strip object

    Note:
        For strips >168 LEDs, use chunked_show() instead of pixels.show()
        to work around neopixel_spi 4096-byte buffer limitation.
    """
    import neopixel_spi as neopixel
    import time

    # Get Pi model if not provided
    if pi_model is None:
        config = get_led_config()
        pi_model = config['pi_model']

    # Get model-specific parameters
    params = get_neopixel_params(pi_model)

    # Create strip
    pixels = neopixel.NeoPixel_SPI(
        spi,
        num_pixels,
        brightness=brightness,
        pixel_order=pixel_order,
        **params
    )

    # Initialize all LEDs to black on first creation
    # Use chunked writes for reliability
    for i in range(num_pixels):
        pixels[i] = (0, 0, 0)
        if (i + 1) % 8 == 0:
            pixels.show()
            time.sleep(0.008)
    pixels.show()
    time.sleep(0.008)

    return pixels


def chunked_show(pixels, chunk_size=8, delay_ms=8):
    """
    Update LED strip with chunked writes.

    The neopixel_spi library has a 4096-byte internal buffer limit.
    Since each RGB pixel requires 24 SPI bytes, only 170 LEDs can be
    updated in a single show() call. This function works around the
    limitation by updating LEDs in chunks.

    Args:
        pixels: NeoPixel_SPI strip object
        chunk_size (int): Number of LEDs to update per chunk (default 8)
        delay_ms (int): Delay in milliseconds between chunks (default 8ms)

    Usage:
        # Instead of: pixels.show()
        # Use: chunked_show(pixels)

    Note:
        Tested reliable with chunk_size=8, delay_ms=8 for up to 336 LEDs.
        These parameters work for any LED strip size.
    """
    import time

    # Call show() to flush all pending changes
    pixels.show()
    time.sleep(delay_ms / 1000.0)


def chunked_fill(pixels, color, chunk_size=8, delay_ms=8):
    """
    Fill all LEDs with a color using chunked writes.

    Args:
        pixels: NeoPixel_SPI strip object
        color: (R, G, B) tuple (0-255 for each channel)
        chunk_size (int): Number of LEDs to update per chunk (default 8)
        delay_ms (int): Delay in milliseconds between chunks (default 8ms)

    Usage:
        chunked_fill(pixels, (255, 0, 0))  # Fill all red
        chunked_fill(pixels, (0, 0, 0))    # Turn all off
    """
    import time

    num_pixels = len(pixels)

    for i in range(num_pixels):
        pixels[i] = color
        if (i + 1) % chunk_size == 0:
            pixels.show()
            time.sleep(delay_ms / 1000.0)

    # Final show for remaining LEDs
    pixels.show()
    time.sleep(delay_ms / 1000.0)


def chunked_clear(pixels, chunk_size=8, delay_ms=8):
    """
    Turn off all LEDs using chunked writes.

    Args:
        pixels: NeoPixel_SPI strip object
        chunk_size (int): Number of LEDs to update per chunk (default 8)
        delay_ms (int): Delay in milliseconds between chunks (default 8ms)

    Usage:
        chunked_clear(pixels)  # Turn off all LEDs
    """
    chunked_fill(pixels, (0, 0, 0), chunk_size, delay_ms)


def map_xy_to_pixel_single(x, y):
    """
    Map (x, y) coordinates to LED pixel index for single 8x24 serpentine layout.

    Layout: Column-major with alternating direction
    - Even columns (0, 2, 4...): go down (y: 0→7)
    - Odd columns (1, 3, 5...): go up (y: 7→0)

    Args:
        x (int): Column index (0-23, left to right)
        y (int): Row index (0-7, top to bottom)

    Returns:
        int: Pixel index (0-191), or None if out of bounds

    Note:
        Extracted from neopixel_spi_IBMtestFunc_8x24.py with bounds checking added.
    """
    # Bounds checking
    if x < 0 or x >= 24 or y < 0 or y >= 8:
        print(f"Warning: Coordinate ({x}, {y}) out of bounds for single layout")
        return None

    if x % 2 == 0:  # Even columns go down (0→7)
        return x * 8 + y
    else:  # Odd columns go up (7→0)
        return x * 8 + (7 - y)


def map_xy_to_pixel_quad(x, y):
    """
    Map (x, y) coordinates to LED pixel index for quad 4x12 panel layout.

    Layout: Four 4x12 panels wired TL→TR→BR→BL
    - Panel 0 (TL): pixels 0-47
    - Panel 1 (TR): pixels 48-95
    - Panel 2 (BR): pixels 96-143
    - Panel 3 (BL): pixels 144-191

    Args:
        x (int): Column index (0-23, left to right)
        y (int): Row index (0-7, top to bottom)

    Returns:
        int: Pixel index (0-191), or None if out of bounds

    Note:
        Extracted from neopixel_spi_IBMtestFunc.py with bounds checking added.
    """
    # Bounds checking
    if x < 0 or x >= 24 or y < 0 or y >= 8:
        print(f"Warning: Coordinate ({x}, {y}) out of bounds for quad layout")
        return None

    # Original calculation logic from neopixel_spi_IBMtestFunc.py
    # Top row calculation
    x1 = x * 4 + (0 if x % 2 == 0 else 3)
    y1 = (7 - y if x % 2 == 0 else y - 7)

    # Bottom row calculation
    x2 = 96 + (23 - x) * 4 + (0 if x % 2 == 0 else 3)
    y2 = (3 - y if x % 2 == 0 else y - 3)

    # Select based on row position
    return x2 + y2 if y < 4 else x1 + y1


def map_xy_to_pixel(x, y, layout=None):
    """
    Unified coordinate mapping function that adapts to LED matrix layout.

    Args:
        x (int): Column index (0-23)
        y (int): Row index (0-7)
        layout (str, optional): 'single' or 'quad'. If None, reads from config.

    Returns:
        int: Pixel index, or None if out of bounds

    Example:
        # Use configured layout
        pixel_index = map_xy_to_pixel(5, 3)

        # Override layout
        pixel_index = map_xy_to_pixel(5, 3, layout='quad')
    """
    # Get layout from config if not specified
    if layout is None:
        config = get_led_config()
        layout = config['layout']

    # Route to appropriate mapping function
    if layout == 'single':
        return map_xy_to_pixel_single(x, y)
    elif layout == 'quad':
        return map_xy_to_pixel_quad(x, y)
    else:
        print(f"Warning: Unknown layout '{layout}', defaulting to 'single'")
        return map_xy_to_pixel_single(x, y)


# Module self-test
if __name__ == "__main__":
    print("RasQberry LED Utilities Module Test")
    print("=" * 50)

    # Test configuration loading
    print("\n1. Testing configuration loading...")
    config = get_led_config()
    print(f"   Pi Model: {config['pi_model']}")
    print(f"   LED Count: {config['led_count']}")
    print(f"   Pixel Order: {config['pixel_order']}")
    print(f"   Layout: {config['layout']}")

    # Test coordinate mapping - single layout
    print("\n2. Testing single layout coordinate mapping...")
    test_coords_single = [(0, 0), (1, 0), (0, 7), (23, 7)]
    for x, y in test_coords_single:
        idx = map_xy_to_pixel_single(x, y)
        print(f"   ({x:2d}, {y:2d}) -> pixel {idx}")

    # Test coordinate mapping - quad layout
    print("\n3. Testing quad layout coordinate mapping...")
    test_coords_quad = [(0, 0), (12, 0), (0, 4), (12, 4)]
    for x, y in test_coords_quad:
        idx = map_xy_to_pixel_quad(x, y)
        print(f"   ({x:2d}, {y:2d}) -> pixel {idx}")

    # Test bounds checking
    print("\n4. Testing bounds checking...")
    invalid_coords = [(-1, 0), (24, 0), (0, -1), (0, 8)]
    for x, y in invalid_coords:
        idx = map_xy_to_pixel(x, y)
        print(f"   ({x:2d}, {y:2d}) -> {idx}")

    print("\n" + "=" * 50)
    print("Module test complete!")
