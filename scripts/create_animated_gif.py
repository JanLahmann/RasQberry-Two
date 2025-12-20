#!/usr/bin/env python3
"""
create_animated_gif.py - Create animated GIF from PNG images

Usage:
    python3 create_animated_gif.py <input_directory> <output_file.gif> [duration_ms]

Example:
    python3 create_animated_gif.py ./images output.gif 500
"""

import sys
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library not found.")
    print("Install with: pip install Pillow")
    sys.exit(1)


def create_animated_gif(input_dir, output_file, duration=500):
    """
    Create an animated GIF from PNG images in a directory.

    Args:
        input_dir: Directory containing PNG images
        output_file: Output GIF filename
        duration: Duration of each frame in milliseconds (default: 500ms)
    """
    # Get all PNG files and sort them
    png_files = sorted(Path(input_dir).glob('*.png'))

    if not png_files:
        print(f"Error: No PNG files found in {input_dir}")
        sys.exit(1)

    print(f"Found {len(png_files)} PNG images:")
    for f in png_files:
        print(f"  - {f.name}")

    # Load all images
    images = []
    for png_file in png_files:
        try:
            img = Image.open(png_file)
            # Convert to RGB if needed (GIF doesn't support RGBA well)
            if img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                images.append(background)
            else:
                images.append(img.convert('RGB'))
        except Exception as e:
            print(f"Warning: Could not load {png_file.name}: {e}")

    if not images:
        print("Error: No images could be loaded")
        sys.exit(1)

    # Save as animated GIF
    print(f"\nCreating animated GIF: {output_file}")
    print(f"Frame duration: {duration}ms")
    print(f"Total frames: {len(images)}")

    images[0].save(
        output_file,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0,  # 0 = infinite loop
        optimize=True
    )

    # Get file size
    file_size = os.path.getsize(output_file)
    size_mb = file_size / (1024 * 1024)

    print(f"\n✓ Success!")
    print(f"Output: {output_file}")
    print(f"Size: {file_size:,} bytes ({size_mb:.2f} MB)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_dir = sys.argv[1]
    output_file = sys.argv[2]
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else 500

    if not os.path.isdir(input_dir):
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)

    create_animated_gif(input_dir, output_file, duration)


if __name__ == '__main__':
    main()