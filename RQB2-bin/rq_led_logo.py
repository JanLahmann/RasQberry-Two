#!/usr/bin/env python3
"""
RasQberry LED Logo Display Module

Provides PIL/Pillow integration for displaying images and logos on LED matrix.
Builds on the existing rq_led_utils infrastructure with no conflicts.

Key features:
- Load PNG/JPG images and display on LED matrix
- Automatic resizing to fit matrix dimensions
- Fade-in/fade-out effects
- Support for both single and quad panel layouts
"""

import os
import time
from PIL import Image

# Import LED utilities
from rq_led_utils import (
    get_led_config,
    create_neopixel_strip,
    map_xy_to_pixel,
    chunked_clear
)


def load_image_as_led_array(image_path, target_width=None, target_height=None):
    """
    Load image file and convert to LED pixel array.

    Args:
        image_path (str): Path to image file (PNG, JPG, etc.)
        target_width (int, optional): Target width. If None, uses config.
        target_height (int, optional): Target height. If None, uses config.

    Returns:
        list: 2D array of (r, g, b) tuples indexed by [x][y]

    Raises:
        FileNotFoundError: If image file doesn't exist
        IOError: If image can't be loaded

    Example:
        led_array = load_image_as_led_array("logo.png", 24, 8)
        # Returns 24x8 array of RGB tuples
    """
    # Check if file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Get target dimensions from config if not specified
    if target_width is None or target_height is None:
        config = get_led_config()
        target_width = target_width or config['matrix_width']
        target_height = target_height or config['matrix_height']

    # Load image
    try:
        img = Image.open(image_path)
    except Exception as e:
        raise IOError(f"Failed to load image: {e}")

    # Convert to RGB (handles RGBA, grayscale, etc.)
    img = img.convert('RGB')

    # Resize to target dimensions
    # Use LANCZOS for high-quality downscaling
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Convert to 2D array of RGB tuples
    led_array = []
    for x in range(target_width):
        column = []
        for y in range(target_height):
            r, g, b = img.getpixel((x, y))
            column.append((r, g, b))
        led_array.append(column)

    return led_array


def display_static_image(pixels, image_array, duration=10, brightness=1.0, layout=None):
    """
    Display static image on LED matrix.

    Args:
        pixels: NeoPixel object
        image_array: 2D array of (r, g, b) tuples from load_image_as_led_array()
        duration (float): How long to display (seconds)
        brightness (float): Brightness multiplier 0.0-1.0
        layout (str, optional): 'single' or 'quad'. If None, uses config.

    Example:
        led_array = load_image_as_led_array("logo.png")
        display_static_image(pixels, led_array, duration=10, brightness=0.5)
    """
    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    if layout is None:
        layout = config['layout']

    # Clear all pixels first
    for i in range(config['led_count']):
        pixels[i] = (0, 0, 0)

    # Display image array on LEDs
    for x in range(min(width, len(image_array))):
        for y in range(min(height, len(image_array[x]))):
            r, g, b = image_array[x][y]

            # Apply brightness
            r = int(r * brightness)
            g = int(g * brightness)
            b = int(b * brightness)

            # Map to LED index and set color
            led_index = map_xy_to_pixel(x, y, layout)
            if led_index is not None:
                pixels[led_index] = (r, g, b)

    pixels.show()

    # Hold for duration
    time.sleep(duration)

    # Clear when done
    chunked_clear(pixels)


def display_image_with_fade(pixels, image_array, duration=10, fade_in=True, fade_out=True,
                           fade_steps=20, layout=None):
    """
    Display image with fade-in and/or fade-out effects.

    Args:
        pixels: NeoPixel object
        image_array: 2D array of (r, g, b) tuples from load_image_as_led_array()
        duration (float): How long to display at full brightness (seconds)
        fade_in (bool): If True, fade in from black
        fade_out (bool): If True, fade out to black
        fade_steps (int): Number of steps in fade animation
        layout (str, optional): 'single' or 'quad'. If None, uses config.

    Example:
        led_array = load_image_as_led_array("logo.png")
        display_image_with_fade(pixels, led_array, duration=15, fade_in=True, fade_out=True)
    """
    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    if layout is None:
        layout = config['layout']

    fade_delay = 0.05  # Delay between fade steps (seconds)

    # Fade in
    if fade_in:
        for step in range(fade_steps + 1):
            brightness = step / fade_steps

            # Clear all pixels
            for i in range(config['led_count']):
                pixels[i] = (0, 0, 0)

            # Display with current brightness
            for x in range(min(width, len(image_array))):
                for y in range(min(height, len(image_array[x]))):
                    r, g, b = image_array[x][y]
                    r = int(r * brightness)
                    g = int(g * brightness)
                    b = int(b * brightness)

                    led_index = map_xy_to_pixel(x, y, layout)
                    if led_index is not None:
                        pixels[led_index] = (r, g, b)

            pixels.show()
            time.sleep(fade_delay)

    # Hold at full brightness
    time.sleep(duration)

    # Fade out
    if fade_out:
        for step in range(fade_steps, -1, -1):
            brightness = step / fade_steps

            # Clear all pixels
            for i in range(config['led_count']):
                pixels[i] = (0, 0, 0)

            # Display with current brightness
            for x in range(min(width, len(image_array))):
                for y in range(min(height, len(image_array[x]))):
                    r, g, b = image_array[x][y]
                    r = int(r * brightness)
                    g = int(g * brightness)
                    b = int(b * brightness)

                    led_index = map_xy_to_pixel(x, y, layout)
                    if led_index is not None:
                        pixels[led_index] = (r, g, b)

            pixels.show()
            time.sleep(fade_delay)

    # Clear when done
    chunked_clear(pixels)


def display_logo(image_path, duration=10, brightness=0.5, fade_in=False, fade_out=False):
    """
    High-level convenience function to display a logo from file.

    Loads image, creates NeoPixel strip, and displays with optional fade effects.
    This is the simplest way to display a logo - one function call!

    Args:
        image_path (str): Path to image file
        duration (float): How long to display (seconds)
        brightness (float): Brightness 0.0-1.0
        fade_in (bool): If True, fade in from black
        fade_out (bool): If True, fade out to black

    Example:
        # Simple usage
        display_logo("logo.png", duration=10, brightness=0.5)

        # With fade effects
        display_logo("logo.png", duration=15, brightness=0.6, fade_in=True, fade_out=True)
    """
    # Get configuration
    config = get_led_config()

    # Create NeoPixel strip
    pixels = create_neopixel_strip(
        config['led_count'],
        config['pixel_order'],
        brightness=config['led_default_brightness']
    )

    # Load image
    led_array = load_image_as_led_array(image_path)

    # Display with or without fade
    if fade_in or fade_out:
        display_image_with_fade(
            pixels,
            led_array,
            duration=duration,
            fade_in=fade_in,
            fade_out=fade_out
        )
    else:
        display_static_image(
            pixels,
            led_array,
            duration=duration,
            brightness=brightness
        )


# Module self-test
if __name__ == "__main__":
    print("RasQberry LED Logo Display Module Test")
    print("=" * 50)

    # Test configuration loading
    print("\n1. Testing configuration loading...")
    config = get_led_config()
    print(f"   Matrix: {config['matrix_width']}x{config['matrix_height']}")
    print(f"   Layout: {config['layout']}")

    # Test image loading (if test image exists)
    print("\n2. Testing image loading...")
    test_image_path = os.path.expanduser("~/RasQberry-Two/RQB2-config/Artwork/Logo-Wallpaper/RasQberry Cube Logo 1000x1000.png")
    if os.path.exists(test_image_path):
        print(f"   Loading: {test_image_path}")
        try:
            led_array = load_image_as_led_array(test_image_path, 24, 8)
            print(f"   Success! Array size: {len(led_array)}x{len(led_array[0])}")
            print(f"   Sample pixel [0][0]: {led_array[0][0]}")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print(f"   Test image not found: {test_image_path}")

    print("\n" + "=" * 50)
    print("Module test complete!")
    print("\nTo display a logo, run:")
    print("  sudo python3 rq_led_logo.py <image_path>")