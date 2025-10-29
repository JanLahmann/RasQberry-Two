#!/usr/bin/env python3
"""
RasQberry IP Address Display on LED Matrix

Displays the device's IP address(es) scrolling across the LED matrix.
Designed for boot-time display to help identify device on networks.

Usage:
    python3 rq_display_ip.py [--duration SECONDS] [--speed SPEED]
"""

import sys
import argparse
from pathlib import Path

# Add RQB2-bin to path for LED utilities
sys.path.insert(0, str(Path(__file__).parent))

try:
    from rq_led_utils import (
        get_led_config,
        create_neopixel_strip,
        display_scrolling_text
    )
except ImportError as e:
    print(f"Error importing LED utilities: {e}", file=sys.stderr)
    sys.exit(1)


def get_ip_addresses():
    """Get all IPv4 addresses for active network interfaces."""
    try:
        import netifaces
    except ImportError:
        print("Error: netifaces module not found", file=sys.stderr)
        return []

    addresses = []

    # Priority order for interfaces
    priority_interfaces = ['eth0', 'wlan0', 'usb0']
    other_interfaces = []

    for iface in netifaces.interfaces():
        if iface == 'lo':  # Skip loopback
            continue
        # Skip docker and other virtual interfaces
        if iface.startswith(('docker', 'br-', 'veth')):
            continue
        if iface in priority_interfaces:
            continue
        other_interfaces.append(iface)

    # Check priority interfaces first
    for iface in priority_interfaces + other_interfaces:
        try:
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get('addr')
                    if ip and not ip.startswith('127.'):
                        # Format: "eth0: 192.168.1.42"
                        addresses.append(f"{iface}: {ip}")
        except (ValueError, KeyError):
            continue

    return addresses


def main():
    parser = argparse.ArgumentParser(
        description='Display IP address(es) on LED matrix at boot'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=30,
        help='Display duration in seconds (default: 30)'
    )
    parser.add_argument(
        '--speed',
        type=float,
        default=0.08,
        help='Scroll speed in seconds between steps (default: 0.08)'
    )
    parser.add_argument(
        '--brightness',
        type=float,
        default=0.3,
        help='LED brightness 0.0-1.0 (default: 0.3)'
    )

    args = parser.parse_args()

    try:
        # Get LED configuration using common utility
        config = get_led_config()

        # Get IP addresses
        addresses = get_ip_addresses()

        if not addresses:
            print("No IP addresses found - device may not be connected to network yet")
            # Display "NO IP" message
            text = "NO IP"
        else:
            # Join all addresses with separator
            text = "  ***  ".join(addresses)

        print(f"Displaying: {text}")

        # Create NeoPixel object using common utility
        pixels = create_neopixel_strip(
            config['led_count'],
            config['pixel_order'],
            brightness=args.brightness
        )

        # Calculate minimum duration needed for full scroll
        # Each character is ~6 columns (5 + 1 space), matrix is 24 columns wide
        # Need time for: text_width + matrix_width positions
        # At 0.08s per step, typical IP needs ~15s for one full scroll
        text_chars = len(text)
        text_columns = text_chars * 6  # Approximate column count
        matrix_width = config['matrix_width']
        scroll_positions = text_columns + matrix_width
        min_duration = scroll_positions * args.speed

        # Use at least the minimum duration, or user-specified duration (whichever is longer)
        # Add 50% extra to ensure text scrolls through at least 1.5 times
        actual_duration = max(args.duration, min_duration * 1.5)

        print(f"Scroll duration: {actual_duration:.1f}s (ensures complete scroll)")

        # Display scrolling IP using common utility function
        display_scrolling_text(
            pixels,
            text,
            duration_seconds=int(actual_duration),
            scroll_speed=args.speed
        )

        print("IP display completed")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()