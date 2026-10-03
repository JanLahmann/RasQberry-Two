# My Quantum Programs

This folder is yours: write, change and run your own quantum programs here.
Everything runs on this Raspberry Pi with local simulators, so you do not need
an IBM Quantum account to start.

## Start with a notebook

The desktop icon **My Quantum Programs** opens JupyterLab in this folder, at
`Hello-World.ipynb`: your first circuit, two entangled qubits, run on a
perfect simulator, on a simulator with the noise of a real device and, with
an IBM Quantum account, on a real quantum computer. It is the Hello World of
[doQumentation](https://doqumentation.org), so the tutorials there continue
where it ends.

- Run a cell with **Shift+Enter**. Change things and run them again: this copy
  is yours.
- New notebook: **File > New > Notebook**. It is saved in this folder.
- From a terminal, `jupyter lab` opens JupyterLab in the current folder.

## Python programs

| File | What it does |
|---|---|
| `01_bell_state.py` | Two entangled qubits on the built-in simulator |
| `02_ghz_histogram.py` | Three entangled qubits on Qiskit Aer, results saved as a chart |
| `03_led_hello.py` | Lights the LED panel from your own program |
| `04_bell_on_leds.py` | Qiskit and LEDs together: every shot becomes a column of light |

Run them in a terminal (`python3 01_bell_state.py`; terminals start with the
RasQberry Python environment active, the prompt shows `(RQB2)`), with
`rq_python 01_bell_state.py` from anywhere (also over SSH), or in **Thonny**
(**Run**) or **Geany** (**Build > Execute**) from menu > Programming: both use
the RasQberry Python, which has Qiskit.

The original files are kept in `/usr/config/my-quantum-programs/`, so you can
always copy a fresh one back.

## The LED panel

    from rq_led_utils import get_pixels, set_xy, matrix_size, clear_all_leds

    pixels = get_pixels(brightness=0.2)
    width, height = matrix_size()        # 24 x 8 on the RasQberry panels
    set_xy(pixels, 0, 0, (255, 0, 0))    # top-left LED red
    pixels.show()                        # nothing changes before show()
    clear_all_leds()

These four functions are the supported LED API: your programs keep working
with later RasQberry releases. Other functions in `rq_led_utils` are internal
and may change.

- **Coordinates**: x runs from 0 (left) to width-1 (right), y from 0 (top) to
  height-1 (bottom). `set_xy` finds the right LED for the configured panel,
  whatever its wiring. Positions off the panel are ignored, so shapes may run
  over the edge. Avoid `pixels[number]`: raw numbers follow the cables
  (`pixels[0]` to `pixels[7]` run down the first column, the next column runs
  back up), not rows.
- **Speed**: `set_xy` takes about 0.1 ms per LED on a Pi 4, fine for
  animations. For the fastest loops, look the layout up once:
  `layout = get_layout()`, then `set_xy(pixels, x, y, color, layout=layout)`.
- **Who may switch the LEDs on**:
  - **Raspberry Pi 5**: your programs drive the panel directly, from Thonny,
    a terminal or Jupyter. No `sudo` needed.
  - **Raspberry Pi 4**: the LED driver needs administrator (root) rights.
    Run LED programs with `rq_python`, for example `rq_python 03_led_hello.py`:
    it starts the RasQberry LED renderer for the run, and your program itself
    runs without root. In Thonny on a Pi 4 an LED program stops with a message
    that says exactly this. Do not use `sudo python3`: that is the system
    Python, without Qiskit and without the LED libraries.
- **Panel stays lit** after a program crashed: run `rq_clear_leds.sh` or use
  the desktop icon **Clear All LEDs**.

## Real quantum computers

The programs here use simulators. To run on IBM Quantum hardware you need an
IBM Quantum account and its API key. The **IBM Quantum Tutorials** (desktop
icon) begin with a notebook that saves the key; after that your own programs
can use `QiskitRuntimeService()` as the tutorials show.

## Extra Python packages

    pip install <package>

in a terminal installs into the RasQberry Python environment. Never use
`sudo pip`. Do not upgrade the packages RasQberry ships (qiskit, numpy, ...)
unless you have to: the demos are tested with these versions. If the
environment breaks, `rq_venv_repair.sh` repairs it (see `rq_venv_repair.sh --help`).

## Keeping your work

- **A/B image:** this folder lives on the data partition (`/data`), like
  `~/Shared` and your IBM Quantum account, so an update into the other slot
  keeps it. An update never overwrites your files and does not bring back
  starter files you deleted.
- **Standard image:** the folder is in your home folder. Updates from a GitHub
  branch leave it alone.
- **Writing a new image to the card** erases everything on it, also `/data`:
  copy this folder to a USB stick or another computer first.
