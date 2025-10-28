#!/usr/bin/env python3
"""
RasQberry LED Utilities Module

Provides shared functionality for LED control across RasQberry demos:
- Configuration loading from environment file
- Hardware detection and NeoPixel initialization (PWM/PIO based)
- Coordinate mapping for LED matrix layouts

This module uses adafruit-circuitpython-neopixel which auto-detects hardware:
- Pi 4: Uses PWM/DMA (rpi_ws281x backend)
- Pi 5: Uses PIO (RP1 chip)
Both approaches support 192+ LEDs without buffer limits or chunking.
"""

import os
from dotenv import dotenv_values

# System-wide environment file location
ENV_FILE = "/usr/config/rasqberry_environment.env"

# Emergency defaults if env file is missing/unreadable
EMERGENCY_DEFAULTS = {
    'PI_MODEL': 'Pi5',
    'LED_COUNT': '192',  # 4*4*12 = 192 LEDs
    'LED_GPIO_PIN': '18',  # GPIO18 for PWM (Pi4) and PIO (Pi5)
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
        'led_gpio_pin': int(config.get('LED_GPIO_PIN', 18)),
        'pixel_order': config.get('LED_PIXEL_ORDER', 'GRB'),
        'brightness': int(config.get('LED_BRIGHTNESS', 100)),
        'layout': config.get('LED_MATRIX_LAYOUT', 'single'),
        'matrix_width': int(config.get('LED_MATRIX_WIDTH', 24)),
        'matrix_height': int(config.get('LED_MATRIX_HEIGHT', 8)),
        'y_flip': config.get('LED_MATRIX_Y_FLIP', 'false').lower() == 'true',
        'n_qubit': int(config.get('N_QUBIT', 192)),
        'led_default_brightness': float(config.get('LED_DEFAULT_BRIGHTNESS', 0.1)),
    }


def create_neopixel_strip(num_pixels, pixel_order, brightness=0.1, gpio_pin=None):
    """
    Factory function to create NeoPixel strip using PWM (Pi4) or PIO (Pi5).

    Uses adafruit-circuitpython-neopixel which auto-detects the platform:
    - Pi 4: Uses rpi_ws281x (PWM/DMA backend) - requires root
    - Pi 5: Uses PIO hardware - requires /dev/pio0

    No SPI, no buffer limits, no chunking needed!

    Args:
        num_pixels (int): Number of LEDs in strip
        pixel_order: Pixel order constant (e.g., neopixel.GRB) or string ('GRB')
        brightness (float): LED brightness 0.0-1.0
        gpio_pin (int, optional): GPIO pin number. If None, reads from config (default 18).

    Returns:
        neopixel.NeoPixel: Configured LED strip object

    Note:
        Requires sudo/root for GPIO access.
        For Pi 5, requires firmware with /dev/pio0 support.
    """
    import board
    import neopixel

    # Get GPIO pin from config if not provided
    if gpio_pin is None:
        config = get_led_config()
        gpio_pin = config['led_gpio_pin']

    # Convert GPIO pin number to board constant
    # GPIO18 = board.D18
    gpio_board_pin = getattr(board, f'D{gpio_pin}')

    # Convert pixel_order string to neopixel constant if needed
    if isinstance(pixel_order, str):
        pixel_order = getattr(neopixel, pixel_order)

    # Create NeoPixel object
    # Library auto-detects Pi4 (PWM) vs Pi5 (PIO)
    pixels = neopixel.NeoPixel(
        gpio_board_pin,
        num_pixels,
        brightness=brightness,
        auto_write=False,
        pixel_order=pixel_order
    )

    # Initialize all LEDs to black
    pixels.fill((0, 0, 0))
    pixels.show()

    return pixels


def chunked_show(pixels, chunk_size=None, delay_ms=None):
    """
    Display pixels on LED strip.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    that just calls pixels.show() for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        # Set pixels to desired colors
        pixels[0] = (255, 0, 0)
        pixels[1] = (0, 255, 0)
        # ...
        # Then update display
        chunked_show(pixels)

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.show()


def chunked_fill(pixels, color, chunk_size=None, delay_ms=None):
    """
    Fill all LEDs with a color.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        color: (R, G, B) tuple (0-255 for each channel)
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        chunked_fill(pixels, (255, 0, 0))  # Fill all red
        chunked_fill(pixels, (0, 0, 0))    # Turn all off

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.fill(color)
    pixels.show()


def chunked_clear(pixels, chunk_size=None, delay_ms=None):
    """
    Turn off all LEDs.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        chunked_clear(pixels)  # Turn off all LEDs

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.fill((0, 0, 0))
    pixels.show()


def map_xy_to_pixel_single(x, y):
    """
    Map (x, y) coordinates to LED pixel index for single serpentine layout.

    Layout: Column-major with alternating direction
    - Even columns (0, 2, 4...): go down (y: 0→height-1)
    - Odd columns (1, 3, 5...): go up (y: height-1→0)

    Args:
        x (int): Column index (0 to width-1, left to right)
        y (int): Row index (0 to height-1, top to bottom)

    Returns:
        int: Pixel index, or None if out of bounds

    Note:
        Reads LED_MATRIX_WIDTH and LED_MATRIX_HEIGHT from environment.
        Respects LED_MATRIX_Y_FLIP configuration for physically upside-down matrices.
    """
    # Get matrix dimensions from config
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']

    # Bounds checking
    if x < 0 or x >= width or y < 0 or y >= height:
        print(f"Warning: Coordinate ({x}, {y}) out of bounds for single layout ({width}x{height})")
        return None

    # Apply Y-flip if configured (for physically upside-down matrices)
    if config.get('y_flip', False):
        y = height - 1 - y

    if x % 2 == 0:  # Even columns go down (0→height-1)
        return x * height + y
    else:  # Odd columns go up (height-1→0)
        return x * height + (height - 1 - y)


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
    print(f"   LED GPIO Pin: {config['led_gpio_pin']}")
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