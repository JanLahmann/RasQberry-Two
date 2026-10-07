#!/usr/bin/env python3
"""
RasQberry IP Address Display on LED Matrix

Displays the device's network name and IP address(es) scrolling across the
LED matrix. Designed for boot-time display to help identify device on networks.
The addresses shown are written to /run/rasqberry/ip-shown: the NetworkManager
hook (90-rasqberry-ip-display) scrolls them again when they change (R-016).
Until the LED layout is verified (setup checklist), the passes alternate
between the two kit layouts, so the address is readable on either kit.

Usage:
    python3 rq_display_ip.py [--duration SECONDS] [--speed SPEED]
    python3 rq_display_ip.py --once     one pass in the configured layout (the
                                        LED panel check shows it after Saved)
"""

import os
import socket
import subprocess
import sys
import argparse
from pathlib import Path

SHOWN_FILE = os.environ.get("RQ_IP_SHOWN", "/run/rasqberry/ip-shown")

# The two LED kits: one 24x8 panel, or four 4x12 panels as mounted in the model
KIT_LAYOUTS = ("single-24x8", "quad-4x12")

# Add RQB2-bin to path for LED utilities
sys.path.insert(0, str(Path(__file__).parent))

try:
    from rq_led_utils import (
        get_led_config,
        create_neopixel_strip,
        display_scrolling_text,
        scroll_pass_columns
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
                    if ip and not ip.startswith(('127.', '169.254.')):
                        # Format: "eth0: 192.168.1.42"
                        addresses.append(f"{iface}: {ip}")
        except (ValueError, KeyError):
            continue

    return addresses


def get_network_name():
    """
    Return the name other computers reach this Pi by.

    With several Pis called "rasqberry" on one network, avahi calls the later
    ones rasqberry-2.local, -3 ... (R-063), so ask avahi; fall back to the
    hostname.

    Returns:
        str: e.g. "rasqberry-2.local"
    """
    try:
        out = subprocess.run(
            ["busctl", "--system", "call", "org.freedesktop.Avahi", "/",
             "org.freedesktop.Avahi.Server", "GetHostNameFqdn"],
            capture_output=True, text=True, timeout=3).stdout.strip()
        if out.startswith('s "') and out.endswith('"') and len(out) > 4:
            return out[3:-1]
    except (OSError, subprocess.SubprocessError):
        pass
    return socket.gethostname() + ".local"


def record_shown(addresses):
    """
    Write the shown IPs (one per line, sorted) for the NetworkManager hook.

    Args:
        addresses (list): "iface: ip" strings
    """
    ips = sorted({a.split(": ", 1)[-1] for a in addresses})
    try:
        os.makedirs(os.path.dirname(SHOWN_FILE), exist_ok=True)
        with open(SHOWN_FILE, "w") as fh:
            fh.write("\n".join(ips))
    except OSError:
        pass  # not root (run by hand): the hook just finds nothing


def pass_layouts(passes, config):
    """
    The LED layout of each scroll pass.

    A new card ships LED_LAYOUT=single-24x8 with LED_LAYOUT_VERIFIED=false
    until the setup checklist's LED step is answered, and on the four-panel
    kit (quad-4x12) that layout scrambles the text (rig, 2026-10-04). Until
    the layout is verified, the passes alternate between the configured
    layout and the other kit layout - an even number, at least two of each -
    so every second pass reads right on either kit. A verified layout is used
    for every pass.

    Args:
        passes (int): Passes wanted (about a minute per address)
        config (dict): get_led_config() result

    Returns:
        list: One layout name per pass
    """
    configured = config['led_layout']
    if config.get('layout_verified') == 'true':
        return [configured] * max(1, passes)
    other = KIT_LAYOUTS[0] if configured == KIT_LAYOUTS[1] else KIT_LAYOUTS[1]
    return [configured, other] * max(2, (passes + 1) // 2)


def scroll_text(pixels, text, config, wanted_seconds, speed):
    """
    Scroll TEXT for about WANTED_SECONDS in whole passes, each pass in its
    layout from pass_layouts() on the same strip.

    Args:
        pixels: The LED strip
        text (str): Text to scroll
        config (dict): get_led_config() result
        wanted_seconds (float): How long, about
        speed (float): Seconds per scroll step

    Returns:
        list: The layout of each pass, in order
    """
    # About a minute per address, in whole passes: the text never stops
    # half-way, so the last pass can be read to its end (item 23). The
    # log says what really happens (it said "60s" for a run that the
    # clock jump after NTP ended after ~11 s).
    pass_seconds = scroll_pass_columns(text, config) * speed
    passes = max(1, round(wanted_seconds / pass_seconds)) if pass_seconds > 0 else 1
    layouts = pass_layouts(passes, config)
    if len(set(layouts)) > 1:
        print(f"LED layout not verified yet: alternating {layouts[0]} and {layouts[1]} "
              f"between passes, so every second pass reads right on either kit")
    print(f"Scrolling {len(layouts)} time(s), about {len(layouts) * pass_seconds:.0f}s "
          f"({pass_seconds:.0f}s per pass)")
    for layout in layouts:
        display_scrolling_text(pixels, text, scroll_speed=speed, passes=1, layout=layout)
    return layouts


def blank(pixels):
    """Turn every LED off; best effort (the driver may be gone)."""
    try:
        pixels.fill((0, 0, 0))
        pixels.show()
    except Exception:
        pass


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
    parser.add_argument(
        '--once',
        action='store_true',
        help='Scroll once in the configured layout, then clear (LED panel check)'
    )

    args = parser.parse_args()
    # Stopped early - "Stop It" when a demo needs the panel, systemctl stop,
    # or (--once) the person closed the message: end like Ctrl+C, through the
    # exit handlers, so the LED driver is released cleanly, and with exit 0
    # (the boot unit ended "failed" on the signal)
    import signal
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    try:
        # Get LED configuration using common utility
        config = get_led_config()

        # Get IP addresses
        addresses = get_ip_addresses()
        if not args.once:
            record_shown(addresses)

        if not addresses:
            print("No IP addresses found - device may not be connected to network yet")
            # Display "NO IP" message
            text = "NO IP"
        else:
            # The name first, then each address
            text = "  ***  ".join([get_network_name()] + addresses)

        print(f"Displaying: {text}")

        # Create NeoPixel object using common utility
        pixels = create_neopixel_strip(
            config['led_count'],
            config['pixel_order'],
            brightness=args.brightness
        )

        try:
            if args.once:
                display_scrolling_text(pixels, text, scroll_speed=args.speed, passes=1,
                                       layout=config['led_layout'])
                print("IP display completed (one pass)")
                return
            num_ips = len(addresses) if addresses else 1  # At least 1 for "NO IP" message
            scroll_text(pixels, text, config, max(args.duration, num_ips * 60), args.speed)
            print("IP display completed")
        except (KeyboardInterrupt, SystemExit):
            # not a frozen half of the address on the panel
            blank(pixels)
            raise

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