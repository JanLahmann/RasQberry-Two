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
    'LED_DEFAULT_BRIGHTNESS': '0.4',
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
        'layout': config.get('LED_MATRIX_LAYOUT', 'single'),
        'matrix_width': int(config.get('LED_MATRIX_WIDTH', 24)),
        'matrix_height': int(config.get('LED_MATRIX_HEIGHT', 8)),
        'y_flip': config.get('LED_MATRIX_Y_FLIP', 'false').lower() == 'true',
        'n_qubit': int(config.get('N_QUBIT', 192)),
        'led_default_brightness': float(config.get('LED_DEFAULT_BRIGHTNESS', 0.4)),
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


def create_text_bitmap(text):
    """
    Create a simple 5x7 font bitmap for scrolling text.
    Returns list of columns (each column is 7-bit value).

    Each character is 5 pixels wide, 7 pixels tall.
    Designed for LED matrix text display.

    Args:
        text (str): Text to convert to bitmap

    Returns:
        list: List of column values (0x00-0x7F), 5 columns per character + 1 space

    Example:
        columns = create_text_bitmap("HELLO")
        # Returns list of column values for displaying "HELLO"
    """
    # Simple 5x7 font (uppercase letters, numbers, punctuation)
    # Each character is represented as 5 columns, each column is 7 bits (0x00-0x7F)
    FONT = {
        '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
        '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
        '2': [0x62, 0x51, 0x49, 0x49, 0x46],
        '3': [0x22, 0x49, 0x49, 0x49, 0x36],
        '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
        '5': [0x27, 0x45, 0x45, 0x45, 0x39],
        '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
        '7': [0x01, 0x71, 0x09, 0x05, 0x03],
        '8': [0x36, 0x49, 0x49, 0x49, 0x36],
        '9': [0x06, 0x49, 0x49, 0x29, 0x1E],
        '.': [0x00, 0x60, 0x60, 0x00, 0x00],
        ':': [0x00, 0x36, 0x36, 0x00, 0x00],
        '*': [0x14, 0x08, 0x3E, 0x08, 0x14],
        ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
        'A': [0x7E, 0x09, 0x09, 0x09, 0x7E],
        'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
        'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
        'D': [0x7F, 0x41, 0x41, 0x41, 0x3E],
        'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
        'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
        'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
        'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
        'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
        'N': [0x7F, 0x02, 0x04, 0x08, 0x7F],
        'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
        'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
        'S': [0x26, 0x49, 0x49, 0x49, 0x32],
        'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
        'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
        'W': [0x7F, 0x20, 0x10, 0x20, 0x7F],
    }

    columns = []

    for char in text.upper():
        if char in FONT:
            # Add character columns
            for col in FONT[char]:
                columns.append(col)
            # Add 1 pixel space between characters
            columns.append(0x00)
        else:
            # Unknown character - show space
            for _ in range(5):
                columns.append(0x00)

    return columns


def display_scrolling_text(pixels, text, duration_seconds=30, scroll_speed=0.1, color=(0, 100, 255)):
    """
    Display scrolling text on LED matrix for specified duration.

    Uses configured LED matrix layout to display text scrolling horizontally.
    Automatically adapts to single or quad panel layouts.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display
        duration_seconds (int): How long to display (seconds)
        scroll_speed (float): Delay between scroll steps (seconds)
        color (tuple): RGB color tuple (0-255 per channel), default bright blue

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_scrolling_text(pixels, "Hello World!", duration_seconds=20)
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate number of scroll positions needed
    total_columns = len(text_columns) + width  # Text + blank screen at end

    start_time = time.time()
    position = 0

    while time.time() - start_time < duration_seconds:
        # Clear all pixels
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)

        # Display current scroll position
        for x in range(width):
            text_col_idx = position + x

            if 0 <= text_col_idx < len(text_columns):
                col_data = text_columns[text_col_idx]

                # Display this column on the LED matrix
                for y in range(min(height, 7)):  # Font is 7 pixels tall
                    if col_data & (1 << y):
                        # Convert x,y to LED index using common mapping function
                        led_index = map_xy_to_pixel(x, y, layout)
                        if led_index is not None:
                            pixels[led_index] = color

        pixels.show()

        # Advance scroll position
        position += 1
        if position >= total_columns:
            position = 0  # Loop

        time.sleep(scroll_speed)

    # Clear LEDs when done
    chunked_clear(pixels)


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