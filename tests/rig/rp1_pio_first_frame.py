#!/usr/bin/env python3
"""
Pi 5 LED driver: how often does the first frame after opening /dev/pio0 time out?

On the rig (Pi 5, Bookworm, kernel 6.12.109) about one open in 60 of the RP1
PIO driver hung on its FIRST frame: the write blocked for the kernel's 1 s
timeout and dmesg logged "rp1-pio ...: DMA wait timed out", whatever came
before (0.1 s or minutes after the previous program). Reopening cured it.
rq_led_utils recovers it quietly; this script measures the rate without
RasQberry code, for an upstream report (raspberrypi/linux).

Each round is a fresh process: open the PIO (Adafruit Pi 5 NeoPixel library),
write one frame, wait for it to go out, close by exiting. The parent counts
first writes that took longer than --slow seconds and new "DMA wait timed
out" lines in dmesg.

Usage (on the Pi 5, nothing else using the LED panel; dmesg readable):
    ~/RasQberry-Two/venv/RQB2/bin/python3 tests/rig/rp1_pio_first_frame.py \
        [--rounds 600] [--gap 0.5] [--pin 18] [--leds 192]
"""
import argparse
import subprocess
import sys
import time

TIMEOUT_LINE = "DMA wait timed out"


def child(pin, leds):
    """One round: open the PIO, write one dim frame, let it out, exit."""
    import board
    import digitalio
    import adafruit_raspberry_pi5_neopixel_write as pio
    gpio = digitalio.DigitalInOut(getattr(board, f"D{pin}"))
    gpio.direction = digitalio.Direction.OUTPUT
    buf = bytearray([0, 0, 8] * leds)
    start = time.monotonic()
    pio.neopixel_write(gpio, buf)
    took = time.monotonic() - start
    time.sleep(0.05)            # the frame goes out before the PIO is closed
    pio.free_pio()
    print(f"{took:.4f}")


def dmesg_timeouts():
    """Count the kernel's PIO DMA timeouts so far."""
    out = subprocess.run(["dmesg"], capture_output=True, text=True).stdout
    return out.count(TIMEOUT_LINE)


def main():
    """Run the rounds and print the rate."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rounds", type=int, default=600)
    ap.add_argument("--gap", type=float, default=0.5, help="seconds between rounds")
    ap.add_argument("--pin", type=int, default=18)
    ap.add_argument("--leds", type=int, default=192)
    ap.add_argument("--slow", type=float, default=0.5, help="a first write this slow timed out")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.child:
        child(args.pin, args.leds)
        return 0
    before = dmesg_timeouts()
    slow = failed = 0
    for i in range(1, args.rounds + 1):
        r = subprocess.run([sys.executable, __file__, "--child", "--pin", str(args.pin),
                            "--leds", str(args.leds)], capture_output=True, text=True)
        try:
            took = float(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            failed += 1
            print(f"round {i}: failed: {r.stderr.strip().splitlines()[-1:]}", flush=True)
            continue
        if took > args.slow:
            slow += 1
            print(f"round {i}: first frame took {took:.2f} s", flush=True)
        if i % 50 == 0:
            print(f"{i} rounds: {slow} slow first frames, "
                  f"{dmesg_timeouts() - before} dmesg timeouts", flush=True)
        time.sleep(args.gap)
    logged = dmesg_timeouts() - before
    done = args.rounds - failed
    rate = f"1 in {done / slow:.0f}" if slow else "none"
    print(f"RESULT rounds={done} failed={failed} slow_first_frames={slow} "
          f"dmesg_timeouts={logged} rate={rate}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
