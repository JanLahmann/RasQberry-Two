# Rig test: real images on real Pis

Tests a RasQberry image on the test Pis the way a person uses it (issue #234):
boot, services, Qiskit, every demo started from a desktop terminal and stopped
with Ctrl+C, and - with a camera on the LED panels - whether LED demos actually
light their panel. Complements the unit tests in `tests/unit/` and CI, which
cannot see a dark panel, a demo that will not stop or a service that fails at
boot.

## Setup

- Test Pis with key-based SSH login for the desktop user
  (`ssh-copy-id rasqberry@<pi>`). A freshly flashed image needs this once; slot
  updates made with `rq_update_slot.sh` keep the key (#275).
- Optional: an RTSP camera covering the LED panels.
- This machine: `ssh`, `ffmpeg`, Python 3 with Pillow, and `gh` for `--update`.
- `cp rig.example.json rig.json` and fill in hosts, camera URL and each Pi's
  panel position in the camera frame (`panel_crop`, fractions of the frame).
  `rig.json` and `results/` are git-ignored.

## Running

```bash
python3 tests/rig/rig_test.py                          # all Pis, all demos
python3 tests/rig/rig_test.py --pi pi5 --demos rasq-led,quantum-lights-out
python3 tests/rig/rig_test.py --checks-only            # system checks only, ~1 min
python3 tests/rig/rig_test.py --update beta-2026-09-30-142314   # install a release first
python3 tests/rig/rig_test.py --docker                 # include docker demos (big pulls)
```

`--update TAG` switches each Pi to Slot A, installs the release's A/B image into
Slot B with this checkout's `rq_update_slot.sh`, waits for the new slot and its
health check, then tests it. Slot A is never written.

The report goes to `results/<timestamp>/report.md`, with a desktop screenshot per
demo and, for LED demos, the camera frame. Exit status 1 if anything failed.

## What is checked

| Area | How |
|---|---|
| Boot, slot, failed units, network | `pi/checks.sh` |
| venv, Qiskit + Aer import, a GHZ circuit on AerSimulator | `pi/checks.sh` |
| Build metadata, menu cache, LED config and verification | `pi/checks.sh` |
| Every shipped unit enabled; LED renderer and update poller disabled | `pi/checks.sh` |
| VNC on, no initramfs, update check answers | `pi/checks.sh` |
| Each demo: starts, still running after N s, no traceback, Jupyter/browser URL answers, stops on Ctrl+C with nothing left over | `pi/demo_smoke.sh` |
| LED demos light the Pi's panel | camera frames vs. a fresh frame with every panel off, taken right before the demo |

## How a demo is driven, and why

`demo_smoke.sh` opens a real terminal window (`lxterminal`), as the desktop
icons do, and types Ctrl+C into it. Shortcuts gave false results:

- LED demos run under `sudo`, which puts the terminal in raw mode and passes the
  keystroke into its own pty, so a `SIGINT` sent from outside is not the same as
  pressing the key.
- Jupyter asks "Shutdown this server?" on the first Ctrl+C; the test presses
  twice, as a person would.
- Demos that open a window (SenseHAT emulator, browser) take the keyboard
  focus, so the keystroke is injected into the terminal's input queue
  (`TIOCSTI`, as root) instead of sent through a keyboard tool.

Some demos can't be judged by "start it and watch the panel". `DEMO_HINTS` in
`rig_test.py` handles them:

- LED text and logo display open dialogs first: the test presses Enter through
  them (accepting the defaults) so the demo reaches its LED output.
- Quantum Lights Out computes its solution before it lights up (~20 s on a
  Pi 4): it runs for 60 s.
- Clear LEDs should leave the panel dark: the test lights the panel first
  (`pi/led_fill.py`), then judges the demo's last frame; a lit panel is the
  failure.

## Camera judgement

The panels share one camera view, and daylight and the camera's auto exposure
drift during a run. A baseline taken at the start went stale and made a dark
panel score 0.01-0.04 ("still lit"). So before every LED demo the test switches
every Pi's panel off, waits 3 s and takes a fresh baseline, and it holds a lock
(`$TMPDIR/rasqberry-rigtest-panels.lock`) for the whole LED demo, so no other
Pi - another thread or a second harness process run side by side - lights its
panel in the meantime.

`panel_crop` must cover only the Pi's LEDs: frame edges, the table (it reflects
the lower panel) and the cables at the lower right change with ambient light.
To find it, fill one panel at a time and diff against a dark frame:

```bash
sudo /home/rasqberry/RasQberry-Two/venv/RQB2/bin/python /tmp/rigtest/led_fill.py 0 80 0   # on the Pi
```

Rows and columns where at least 15% of the pixels brighten by 80+ grey levels,
plus a 0.02 margin, give the crop. Check that each Pi's fill scores 0 in the
other Pi's crop.
- LED Painter starts with an empty canvas: instead of the camera, the test
  checks that the LED renderer service that drives the panel is running.
