# Contributing to RasQberry Two

Thanks for helping. Most contributions are one of two kinds:

- **A demo:** it lives in your own repository and reaches every RasQberry
  through the demo catalogue. No change to this repository's code is needed.
- **A change to RasQberry itself:** a fix, a feature or documentation, as a
  pull request against the `development` branch.

## Add your demo to the catalogue

### 1. Your repository

A public GitHub repository with a licence (e.g. Apache-2.0) and a file
`rqb-demo.json` at its root. The repository name becomes the demo's directory
on the Pi, so `entrypoint.working_dir` must equal it.

```json
{
  "id": "my-quantum-demo",
  "name": "My Quantum Demo",
  "category": "led-demo",
  "description": "One line on what visitors see and learn",
  "entrypoint": {
    "type": "python",
    "script": "main.py",
    "working_dir": "my-quantum-demo"
  },
  "install": {
    "preinstalled": false,
    "repo_url": "https://github.com/<owner>/my-quantum-demo.git",
    "marker_file": "main.py",
    "pip_requirements": true
  },
  "needs_hw": { "leds": true, "display": "none", "audio": "optional", "network": false },
  "needs_ibm_token": "none",
  "loop_ok": true,
  "menu": { "show": true },
  "desktop": { "show": true, "terminal": true }
}
```

- **Types:** `python`, `jupyter`, `browser`, `docker` and `web-static` (a
  folder of static files served on a port).
- **Python:** a `python` demo runs with the RasQberry venv, so `qiskit`,
  `qiskit-aer` and `numpy` are already there. List only extra packages, in
  `requirements.txt` with exact versions (`package==1.2.3`). Packages the
  image ships keep its versions.
- **Not allowed:** launcher scripts, patches and shell command strings in the
  manifest. The demo must run as published.
- **Stopping:** the window stops the demo with Enter, Ctrl+C or by closing it,
  so it needs no stop logic of its own. It should end cleanly on SIGTERM. A
  program that reads the keyboard sets `entrypoint.keyboard: true`; it then
  stops with Ctrl+C only.
- **Variants** (e.g. chapters or a short booth version):
  `"variants": [{"id": "short", "args": ["--short"]}]`.
- **Loop:** with `loop_ok: true` the demo can run in RasQberry's demo loop,
  and it should then end by itself.

### 2. LEDs

Draw through `rq_led_utils`, never through `neopixel` directly. These four
functions are the supported API and stay stable across releases:

```python
from rq_led_utils import get_pixels, matrix_size, set_xy, clear_all_leds

pixels = get_pixels()            # the panel, at the user's brightness
width, height = matrix_size()    # e.g. 24 x 8, or 32 x 8
set_xy(pixels, x, y, (r, g, b))  # (0, 0) = top left; off-panel is ignored
pixels.show()
```

- **Panel size:** panels differ, so read it from `matrix_size()` and don't
  hard-code it.
- **Brightness:** `get_pixels()` uses the brightness the user set. Don't raise
  it in code: scenes that light every LED draw the most power.
- **No root:** LED demos run as the desktop user in a sandbox. They have the
  desktop, the network and sound. They have no `sudo` and no Docker, and the
  system and the home folder are read-only: write into your demo's own
  folder (the working directory) or `$XDG_CACHE_HOME`. On a Pi 4,
  `get_pixels()` sends the frames to a small RasQberry service that drives
  the LEDs.

### 3. Sound

Set `needs_hw.audio` to `optional` or `required`. Before the start, the
launcher names the output, or says how to connect a speaker.

- **Default output only:** play through PipeWire (e.g. `pw-play narration.ogg`,
  or a Python library that uses the default device), never a fixed ALSA device
  such as `hw:0`. HDMI, USB and Bluetooth speakers then all work.
- **Recorded, not text-to-speech:** a file (Ogg or WAV, 48 kHz) works offline
  and sounds the same on every Pi.
- **Speakers:** a Bluetooth or USB speaker, or a monitor with speakers. Sound
  boards on the GPIO pins don't work, because they need the LED pin.
- **Pi 4 headphone jack:** it shares hardware with the LED panel. With the
  LEDs on, it can go silent until the Pi restarts. The launcher warns about
  this.
- **Timing:** take the LED timing from the playback position, not from
  sleeps, so the LEDs stay in step over a long demo.
- **Sound delay:** Bluetooth speakers play 100–300 ms late. Users set the
  delay once for all demos (RasQberry menu: Desktop Settings > Sound delay,
  where a tick and a flash help to find it), and the launcher passes it as
  `RQ_AUDIO_DELAY_MS` (whole milliseconds, 0–2000, default 0). Show the LEDs
  for the part that is being heard:

  ```python
  import os

  delay = int(os.environ.get("RQ_AUDIO_DELAY_MS", "0")) / 1000  # seconds
  heard = playback_position() - delay   # your player's position, in seconds
  show_frame_for(heard)
  ```

### 4. Test it on your Pi

On a Pi running a current RasQberry image:

```bash
git clone https://github.com/<owner>/my-quantum-demo.git ~/RasQberry-Two/demos/my-quantum-demo
cd ~/RasQberry-Two/demos/my-quantum-demo
rq_demo_validate.sh --external rqb-demo.json
mkdir -p ~/.local/config/demo-manifests
cp rqb-demo.json ~/.local/config/demo-manifests/rq_demo_my-quantum-demo.json
rq_demo_run.sh my-quantum-demo
```

This runs the demo the way the catalogue will: same checks, same window, same
sandbox. To remove it, delete the two copies again.

### 5. Into the catalogue

Open an issue with the repository link and the commit to use. We test the demo
on a Pi 4 and a Pi 5 and add it to `RQB2-config/known-demos.json`:

- The entry pins that exact commit and names you as the provider. A new
  version means a new commit and a new pin, so nothing changes on users' Pis
  without a review.
- A demo with sound gets `"min_engine": 2`. Older RasQberry versions then say
  that it needs a newer RasQberry.
- Pis fetch the catalogue daily and show the demo as new. Users install it
  from the menu (Quantum Demos > Manage demos) or the desktop.

The full rules, including the catalogue fields and the security model, are in
[EXTERNAL_DEMOS.md](RQB2-config/demo-manifests/EXTERNAL_DEMOS.md).

## Change RasQberry itself

- **Branches:** work on a branch off `development` and open the pull request
  against `development`. A push to a `dev*` branch builds an image in CI.
- **Shell scripts:** start from [`RQB2-bin/_TEMPLATE.sh`](RQB2-bin/_TEMPLATE.sh)
  and use the shared library [`rq_common.sh`](RQB2-bin/RQ_COMMON_README.md)
  (`load_rqb2_env`, `die`, `show_yesno`, `activate_venv`, ...). Don't redefine
  `USER_HOME`. `RQB2_menu.sh` runs inside raspi-config: no `set -eu` there.
- **Python:** docstrings, and `logging` for errors.
- **Text people read** (dialogs, menus, docs, the website): follow the
  [style guide](docs/STYLE.md).
- **Tests:** run `python3 -m pytest tests/unit` before a pull request. CI
  runs `tests/test_basic_validation.sh`, the menu tests and the up-to-date
  checks of the generated pages (`docs/testing/tester_missions.py --check`,
  `docs/reference/reference_docs.py --check`), and the whole unit suite (for
  now as advice only). Add a unit test with a fix, and test on a Pi through the
  real paths (menu, desktop icon), not only from a shell.

## Issues

Search the [existing issues](https://github.com/JanLahmann/RasQberry-Two/issues)
first. Include the RasQberry version (`cat /etc/rasqberry-version`), the Pi
model, the LED setup and the steps to reproduce.

## Conduct and licence

Be kind and constructive, and respect other views. Contributions are licensed
under the project's [Apache-2.0 licence](LICENSE).
