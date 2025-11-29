#!/usr/bin/env python3
"""
Create LED matrix logo files from existing artwork.

This script creates optimized 24x8 and 16x8 PNG files for LED display
from the existing high-resolution RasQberry logos.
"""

import os
from PIL import Image, ImageDraw, ImageFont


def create_ibm_logo(width=24, height=8):
    """
    Create IBM logo optimized for LED matrix.

    Creates a simple IBM text logo with IBM blue color scheme.
    """
    # Create image with black background
    img = Image.new('RGB', (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # IBM Blue color
    ibm_blue = (0, 100, 200)

    # Simple pixel art "IBM" - 3 letters, each 5 pixels wide, 7 pixels tall
    # Centered on 24x8 matrix

    # Letter I (centered at x=5-7)
    for y in range(1, 8):
        img.putpixel((6, y), ibm_blue)

    # Letter B (centered at x=10-14)
    pixels_B = [
        (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7),  # Left vertical
        (11, 1), (12, 1), (13, 1),  # Top horizontal
        (11, 4), (12, 4),  # Middle horizontal
        (11, 7), (12, 7), (13, 7),  # Bottom horizontal
        (14, 2), (14, 3),  # Top right curve
        (14, 5), (14, 6),  # Bottom right curve
    ]
    for x, y in pixels_B:
        if 0 <= x < width and 0 <= y < height:
            img.putpixel((x, y), ibm_blue)

    # Letter M (centered at x=16-22)
    pixels_M = [
        (17, 1), (17, 2), (17, 3), (17, 4), (17, 5), (17, 6), (17, 7),  # Left vertical
        (18, 2), (19, 3),  # Left diagonal
        (20, 2), (21, 1), (21, 2), (21, 3), (21, 4), (21, 5), (21, 6), (21, 7),  # Right vertical
    ]
    for x, y in pixels_M:
        if 0 <= x < width and 0 <= y < height:
            img.putpixel((x, y), ibm_blue)

    return img


def create_rasqberry_icon(width=24, height=8):
    """
    Create RasQberry icon optimized for LED matrix.

    Creates a simple quantum-inspired icon (Q letter or cube outline).
    """
    # Create image with black background
    img = Image.new('RGB', (width, height), color=(0, 0, 0))

    # RasQberry colors - quantum blue and raspberry red
    quantum_blue = (0, 150, 255)
    raspberry_red = (200, 0, 80)

    # Draw a simple "Q" or quantum symbol
    # Outer circle/square
    for x in range(8, 16):
        for y in range(1, 7):
            # Draw hollow square/Q shape
            if x in [8, 15] or y in [1, 6]:
                img.putpixel((x, y), quantum_blue)

    # Q tail
    img.putpixel((14, 5), raspberry_red)
    img.putpixel((15, 6), raspberry_red)

    # Add some accent pixels
    img.putpixel((11, 3), raspberry_red)
    img.putpixel((12, 4), raspberry_red)

    return img


def resize_existing_logo(source_path, target_width, target_height):
    """
    Resize existing high-resolution logo to LED matrix size.

    Args:
        source_path (str): Path to source image
        target_width (int): Target width in pixels
        target_height (int): Target height in pixels

    Returns:
        PIL.Image: Resized image
    """
    if not os.path.exists(source_path):
        print(f"Warning: Source image not found: {source_path}")
        return None

    img = Image.open(source_path)
    img = img.convert('RGB')
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    return img


def main():
    """Create all logo files."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("Creating LED matrix logo files...")
    print("=" * 50)

    # 1. Create IBM logo (24x8)
    print("\n1. Creating IBM logo (24x8)...")
    ibm_logo = create_ibm_logo(24, 8)
    ibm_path = os.path.join(script_dir, "ibm-logo-24x8.png")
    ibm_logo.save(ibm_path)
    print(f"   Saved: {ibm_path}")

    # 2. Create RasQberry icon (24x8)
    print("\n2. Creating RasQberry icon (24x8)...")
    rq_icon = create_rasqberry_icon(24, 8)
    rq_icon_path = os.path.join(script_dir, "rasqberry-icon-24x8.png")
    rq_icon.save(rq_icon_path)
    print(f"   Saved: {rq_icon_path}")

    # 3. Resize existing RasQberry cube logo
    print("\n3. Creating RasQberry cube logo from artwork...")
    artwork_path = os.path.join(script_dir, "..", "Artwork", "Logo-Wallpaper", "RasQberry Cube Logo 1000x1000.png")
    if os.path.exists(artwork_path):
        cube_logo = resize_existing_logo(artwork_path, 24, 8)
        if cube_logo:
            cube_path = os.path.join(script_dir, "rasqberry-cube-24x8.png")
            cube_logo.save(cube_path)
            print(f"   Saved: {cube_path}")
    else:
        print(f"   Source not found: {artwork_path}")
        print("   Creating placeholder instead...")
        # Use the icon as fallback
        rq_icon.save(os.path.join(script_dir, "rasqberry-cube-24x8.png"))

    # 4. Create 16x8 versions for smaller displays
    print("\n4. Creating 16x8 variants...")
    ibm_logo_16 = create_ibm_logo(16, 8)
    ibm_logo_16.save(os.path.join(script_dir, "ibm-logo-16x8.png"))
    print("   Saved: ibm-logo-16x8.png")

    rq_icon_16 = create_rasqberry_icon(16, 8)
    rq_icon_16.save(os.path.join(script_dir, "rasqberry-icon-16x8.png"))
    print("   Saved: rasqberry-icon-16x8.png")

    print("\n" + "=" * 50)
    print("Logo creation complete!")
    print(f"\nLogos saved to: {script_dir}")
    print("\nCreated files:")
    print("  - ibm-logo-24x8.png")
    print("  - ibm-logo-16x8.png")
    print("  - rasqberry-icon-24x8.png")
    print("  - rasqberry-icon-16x8.png")
    print("  - rasqberry-cube-24x8.png")


if __name__ == "__main__":
    main()