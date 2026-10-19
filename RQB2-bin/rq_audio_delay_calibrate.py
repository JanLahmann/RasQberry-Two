#!/usr/bin/env python3
"""
Calibrate the sound delay (RQ_AUDIO_DELAY_MS) with a tick and a flash.

Four ticks in a quickening rhythm, then a pause, again and again; the LED
panel flashes with each tick, the flash moved by the delay. The rhythm only
lines up at the right delay, so a delay a tick or a block off cannot pass.
The user changes the delay until tick and flash come together: a Bluetooth
speaker plays 100-300 ms late, so the flash has to wait for it. Enter writes the value to --out; the launcher
(rq_audio_delay_calibrate.sh) saves it.

Runs as the desktop user (in the LED sandbox), so the tick goes to the
user's default sound output, like a demo's sound.
"""

import argparse
import logging
import math
import os
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
import tty

from rq_led_utils import get_pixels

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RATE = 48000
ONSETS = (0.0, 0.6, 1.05, 1.35)   # four ticks, the gaps shorter each time
CYCLE = 2.6           # ... then a pause, and the block again
FLASH = 0.08          # how long the panel lights, in seconds
# No two blocks look alike within CYCLE, so delays up to MAX_MS tell apart
MAX_MS = 2000
COLOUR = (0, 90, 255)


def tick():
    """
    One cycle of sound: a tick at each of ONSETS, silence between and
    after (mono, 16 bit, RATE).

    Returns:
        bytes: raw little-endian samples, played again and again
    """
    # 30 ms of a 1.5 kHz tone, fading out: loud and clear on a Bluetooth
    # speaker (a 6 ms click was too quiet there)
    click_len = int(RATE * 0.03)
    click = b"".join(
        struct.pack("<h", int(30000 * (1 - i / click_len) ** 2
                              * math.sin(2 * math.pi * 1500 * i / RATE)))
        for i in range(click_len))
    total = int(RATE * CYCLE)
    out = bytearray(2 * total)
    for onset in ONSETS:
        start = 2 * int(RATE * onset)
        out[start:start + len(click)] = click
    return bytes(out)


def player():
    """
    Return the command that plays raw samples from stdin on the default output.

    Returns:
        list: the command, or None when no player is installed
    """
    for cmd in (["pw-cat", "--playback", "--raw", "--rate", str(RATE), "--channels", "1",
                 "--format", "s16", "-"],
                ["paplay", "--raw", f"--rate={RATE}", "--channels=1", "--format=s16le"],
                ["aplay", "-q", "-D", "default", "-t", "raw", "-f", "S16_LE",
                 "-r", str(RATE), "-c", "1"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


def start_ticks(cmd, sound):
    """
    Start the player and feed it SOUND in a loop from a thread.

    The pipe blocks while the player's buffer is full, so the loop runs at
    the speed of the sound output.

    Args:
        cmd (list): the player command
        sound (bytes): one period of samples

    Returns:
        subprocess.Popen: the player
    """
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def feed():
        try:
            while True:
                proc.stdin.write(sound)
                proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            pass

    threading.Thread(target=feed, daemon=True).start()
    return proc


def stop_ticks(proc):
    """
    Stop the player quietly: its pipe closes without a "Broken pipe" error.

    Args:
        proc (subprocess.Popen): the player from start_ticks
    """
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    try:
        proc.stdin.close()
    except (BrokenPipeError, OSError, ValueError):
        pass


def read_key(timeout):
    """
    Read one key press, waiting at most TIMEOUT seconds.

    Args:
        timeout (float): seconds to wait

    Returns:
        str: "up", "down", "pgup", "pgdn", "enter", "quit", another character, or ""
    """
    if timeout > 0 and not select.select([sys.stdin], [], [], timeout)[0]:
        return ""
    if timeout <= 0 and not select.select([sys.stdin], [], [], 0)[0]:
        return ""
    ch = os.read(sys.stdin.fileno(), 1).decode(errors="ignore")
    if ch == "\x1b":
        seq = ""
        while select.select([sys.stdin], [], [], 0.02)[0] and len(seq) < 4:
            seq += os.read(sys.stdin.fileno(), 1).decode(errors="ignore")
        return {"[A": "up", "[B": "down", "[5~": "pgup", "[6~": "pgdn",
                "OA": "up", "OB": "down"}.get(seq, "quit" if not seq else "")
    if ch in ("\r", "\n"):
        return "enter"
    if ch in ("q", "Q", "\x03"):
        return "quit"
    return {"+": "up", "=": "up", "-": "down"}.get(ch, ch)


def status(delay):
    """Show the current delay on one line."""
    sys.stdout.write(f"\r  Sound delay: {delay:4d} ms   ")
    sys.stdout.flush()


def calibrate(start, out):
    """
    Run the tick and the flash until the user saves or cancels.

    Args:
        start (int): the delay to begin with, in ms
        out (str): file the saved value is written to

    Returns:
        int: 0 when saved or cancelled (only a save writes --out), 2 when no
        sound could be played
    """
    pixels = get_pixels()
    cmd = player()
    if cmd is None:
        logger.error("No sound player found (pw-cat, paplay or aplay).")
        return 2
    sound = tick()

    delay = max(0, min(MAX_MS, start))
    print("Four ticks in a quickening rhythm, then a pause; the LED panel")
    print("flashes with each tick.")
    print("Change the delay until you hear each tick when you see its flash,")
    print("and the rhythm of the ticks is the rhythm of the flashes.")
    print("  Up/Down: 10 ms   Page Up/Page Down: 50 ms   Enter: save   Q: cancel")
    print()

    old = termios.tcgetattr(sys.stdin)
    proc = start_ticks(cmd, sound)
    t0 = time.monotonic()
    lit = False
    saved = False
    restarts = 0
    try:
        tty.setcbreak(sys.stdin.fileno())
        status(delay)
        while True:
            if proc.poll() is not None:
                # the player stopped (e.g. the output went away): start again,
                # but not without end
                restarts += 1
                if restarts > 3:
                    print()
                    logger.error("The tick could not be played (%s stopped).", cmd[0])
                    return 2
                stop_ticks(proc)
                proc = start_ticks(cmd, sound)
                t0 = time.monotonic()
            now = time.monotonic()
            # where in the cycle the flash should be
            cycle = (now - t0 - delay / 1000.0) % CYCLE
            on = any(o <= cycle < o + FLASH for o in ONSETS)
            # wait until the flash changes, or a key comes
            edges = [e for o in ONSETS for e in (o, o + FLASH)] + [CYCLE]
            wait = min(e for e in edges if e > cycle) - cycle
            if on != lit:
                pixels.fill(COLOUR if on else (0, 0, 0))
                pixels.show()
                lit = on
            key = read_key(max(0.001, min(wait, 0.05)))
            if key in ("up", "down", "pgup", "pgdn"):
                step = {"up": 10, "down": -10, "pgup": 50, "pgdn": -50}[key]
                delay = max(0, min(MAX_MS, delay + step))
                status(delay)
            elif key == "enter":
                with open(out, "w") as f:
                    f.write(f"{delay}\n")
                saved = True
                break
            elif key == "quit":
                break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        stop_ticks(proc)
        pixels.fill((0, 0, 0))
        pixels.show()
        print()
    if saved:
        print(f"Saved: {delay} ms.")
    else:
        print("Cancelled: the sound delay stays as it was.")
    return 0


def main():
    """Parse the arguments and run the calibration."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--start", type=int, default=0, help="delay to begin with, in ms")
    parser.add_argument("--out", required=True, help="file the saved value goes to")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        logger.error("The calibration needs a terminal window for the keys.")
        return 2
    # a closed window or a stop from outside: the finally block cleans up
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    signal.signal(signal.SIGHUP, lambda *_: sys.exit(129))
    try:
        return calibrate(args.start, args.out)
    except KeyboardInterrupt:
        print("\nCancelled: the sound delay stays as it was.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
