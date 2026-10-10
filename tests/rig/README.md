# Rig test: real images on real Pis

Tests a RasQberry image on the test Pis the way a person uses it (issue #234):
boot, services, Qiskit, every demo started from a desktop terminal and stopped
with Ctrl+C, and - with a camera on the LED panels - whether LED demos actually
light their panel. Complements the unit tests in `tests/unit/` and CI, which
cannot see a dark panel, a demo that will not stop or a service that fails at
boot.

## Setup

- Test Pis with key-based SSH login for the desktop user
  (`ssh-copy-id rasqberry@<pi>`; a user named in Imager, e.g. `jan@<pi>`:
  put that user into `host`, or as `"user"`). Everything runs as this user. A freshly flashed image needs this once; slot
  updates made with `rq_update_slot.sh` keep the key (#275).
- Optional: an RTSP camera covering the LED panels.
- This machine: `ssh`, `ffmpeg`, Python 3 with Pillow, and `gh` for `--update`.
- `cp rig.example.json rig.json` and fill in hosts, camera URL and each Pi's
  panel position in the camera frame (`panel_crop`, fractions of the frame).
  `rig.json` and `results/` are git-ignored.
- Usage counts: each run first puts `RQ_UMAMI=0` into the Pi's
  `/usr/config/rasqberry_environment.env`, so rig demo starts, health checks
  and updates do not count in the project's Umami statistics. A freshly
  flashed rig card counts its first start once, before the first run.

## Running

```bash
python3 tests/rig/rig_test.py                          # all Pis, all demos
python3 tests/rig/rig_test.py --pi pi5 --demos rasq-led,quantum-lights-out
python3 tests/rig/rig_test.py --checks-only            # system checks only, ~1 min
python3 tests/rig/rig_test.py --update beta-2026-09-30-142314   # install a release first
python3 tests/rig/rig_test.py --docker                 # include docker demos (big pulls)
python3 tests/rig/rig_test.py --demos none --icons --docker     # desktop icons only
python3 tests/rig/rig_test.py --icons rasq-led.desktop,clear-leds.desktop
python3 tests/rig/rig_test.py --no-web-check           # leave the desktop Chromium alone
```

`--update TAG` installs the release's A/B image into the slot that is not
running (ping-pong) with this checkout's `rq_update_slot.sh`, waits for the new
slot and its health check, then tests it. The running slot is never written; it
stays as the way back. The guard's questions are answered yes
(`--allow-downgrade --force-replace-safe-slot`): the operator chose the release.

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
| Web and Jupyter demos work, not just answer | `pi/webcheck.py` in the demo's own Chromium tab |
| Desktop icons start their demo on a double-click (`--icons`) | `pi/mouse.py`, a kernel-level mouse |
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
- Clear LEDs: a helper (`pi/led_fill.py --hold`) lights the panel and keeps
  holding it, like a program someone left running. The test waits until the
  camera sees the panel lit, runs Clear LEDs (Enter answers its "Stop it?"),
  and requires that the holder was stopped and the last frame is dark. The
  helper ends on SIGTERM without clearing, so the demo itself must switch the
  panel off. The test always kills the helper afterwards (by its pid file).
  `rq_clear_leds.sh` finds holders by the LED devices they have open
  (`led_holders`: fuser on /dev/pio0, /dev/gpiochip*, /dev/gpiomem, /dev/mem),
  so any program counts, not only RasQberry's.

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

## Desktop icons (`--icons`)

`--icons` double-clicks desktop icons with a real mouse: `pi/mouse.py` creates
an absolute pointer through the kernel's uinput (like a virtual machine's
"tablet" mouse), so the click goes through libinput and labwc like a physical
one. wlrctl is not packaged for bookworm, and ydotool moves a relative mouse
that labwc accelerates; the absolute pointer needs neither. The icon's
position comes from pcmanfm's `desktop-items-0.conf`; its centre is x+60,
y+67 (override per Pi with `"icon_offset": [dx, dy]` in rig.json).
For a launcher in a demo group's folder (`~/.local/share/rasqberry/desktop-groups/`),
it double-clicks the group's icon, types the launcher's name into the group's
window (`rq_group_window.py`; its type-ahead selects it) and presses Enter,
which starts it and closes the window (`pi/keyboard.py`). The test
then finds the demo by the log `rq_hold_on_error.sh` writes
(`~/.cache/rasqberry/<name>.log`) and stops it with Ctrl+C as before. Default
icons: RasQ-LED (LED), Quantum Paradoxes (Jupyter), Qoffee-Maker (docker; runs
only with `--docker`). Icons that start Chromium directly (Composer) are not
supported.

Keys for a page: `pi/keyboard.py` is the keyboard of the same kind (evdev
codes, e.g. `57` Space, `29+46` Ctrl+C). wtype is fine for terminals, but
Chromium reads its Space as Escape.

## Web and Jupyter checks

A page that answers 200 can still be blank or broken. For browser, Jupyter and
docker demos the test restarts the desktop Chromium with remote debugging
(127.0.0.1 only, same profile and page), and `pi/webcheck.py` checks the tab
the demo opened:

- every page: it loads (load event, a title or text; polled for 45 s, or
  `load` seconds for a slow page: Composer gets 120 s for the 2 GB Pi 4);
  uncaught JavaScript errors are reported;
- web pages: a key control responds to a real click - the page changes or
  navigates. `DEMO_HINTS[...]["web"]` names text the title must have
  (`title`), the element to wait for and the control (`click`), or a point in
  a canvas app (`click_at`, judged by the picture changing: Grok Bloch's "X"
  gate). A variant's own type counts: Fun with Quantum's website variant is a
  web page, its notebooks are Jupyter;
- Jupyter: the notebook UI renders, and the first safe code cell of the
  notebook shown - or, for a welcome page without code, of the first notebook
  with one nearby (two folder levels down) - runs in a fresh kernel of that
  server, without an error. The kernel has its own session: nothing is saved
  into the demo's notebook. An empty workspace is `web=info`, not a warning.
- a browser demo that opens no tab fails.

**Never credential code.** The check once ran cell 1 of
`00-Save-Credentials.ipynb` as shipped and saved the placeholder over the real
API key on both Pis (`~/.qiskit` is on `/data`, shared by both slots). Now it
skips notebooks named like credentials/accounts/tokens and cells with
`save_account`, `delete_account`, `saved_accounts`, `token=`, `api_key`,
`QISKIT_IBM_TOKEN`, `qiskit-ibm.json` or `.qiskit` ("no safe cell" is
`web=info`). And `demo_smoke.sh` keeps a root-only copy (mode 600, in
`/tmp/rigtest/qiskit-backup`) of `~/.qiskit/qiskit-ibm.json` during each web
check and puts it back if it changed - "restored ~/.qiskit after <demo>" in the
detail, verdict WARN. The file's content is never printed.

After each demo the tabs it opened are closed, and when the Pi is done its
Chromium is restarted as the session starts it. `--no-web-check` skips all
this.

## Pi 5 LED driver: first-frame timeouts

`rp1_pio_first_frame.py` measures how often the first frame after opening
`/dev/pio0` times out ("rp1-pio ...: DMA wait timed out"), without RasQberry
code: each round a fresh process opens the PIO, writes one frame and exits.
Run it on the Pi 5 with nothing else on the panel (about 0.7 s per round):

```bash
cd /tmp && ~/RasQberry-Two/venv/RQB2/bin/python3 ~/rp1_pio_first_frame.py --rounds 600
```

Bookworm, kernel 6.12.109 (2026-10-06): 20 of 1200 rounds (1 in 60). Repeat on the
Trixie image before reporting it upstream.
