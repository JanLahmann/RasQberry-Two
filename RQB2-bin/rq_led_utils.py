#!/usr/bin/env python3
"""
RasQberry LED Utilities Module

Provides shared functionality for LED control across RasQberry demos:
- Configuration loading from environment file
- Hardware detection and NeoPixel initialization (PWM/PIO based)
- Coordinate mapping for LED matrix layouts

This module uses adafruit-circuitpython-neopixel which auto-detects hardware:
- Pi 4: Uses PWM/DMA (rpi_ws281x backend)
- Pi 5: Uses PIO (RP1 chip)
Both approaches support 192+ LEDs without buffer limits or chunking.
"""

import os
import sys
import json

# dotenv is only needed for reading the environment file. Guard the import so
# the pure coordinate-mapping / layout-registry functions remain importable in
# environments (e.g. CI) where python-dotenv is not installed.
try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - exercised only without python-dotenv
    dotenv_values = None

# System-wide environment file location
ENV_FILE = "/usr/config/rasqberry_environment.env"

# Layout registry file. Installed system: /usr/config/led-layouts.json.
# Running from a checkout: RQB2-config/led-layouts.json next to RQB2-bin.
LAYOUTS_FILENAME = "led-layouts.json"

# Global singleton NeoPixel object - prevents GPIO conflicts on Pi 5
_pixels_singleton = None

# Cache for the parsed layout registry (keyed by (shipped_path, user_path,
# user_mtime) so a freshly written user overlay is picked up).
_layouts_cache = None
_layouts_cache_key = None

# Back-compat aliases: legacy LED_MATRIX_LAYOUT values -> registry layout names
_LEGACY_LAYOUT_ALIASES = {
    'single': 'single-24x8',
    'quad': 'quad-2x2-12x4',
}

# Fallback layout name when nothing else can be resolved
_DEFAULT_LAYOUT_NAME = 'single-24x8'

# Emergency defaults if env file is missing/unreadable
EMERGENCY_DEFAULTS = {
    'PI_MODEL': 'Pi5',
    'LED_COUNT': '192',  # 4*4*12 = 192 LEDs
    'LED_GPIO_PIN': '18',  # GPIO18 for PWM (Pi4) and PIO (Pi5)
    'LED_PIXEL_ORDER': 'GRB',
    'LED_DEFAULT_BRIGHTNESS': '0.4',
    'LED_MATRIX_LAYOUT': 'single',
    'LED_MATRIX_WIDTH': '24',
    'LED_MATRIX_HEIGHT': '8',
    'N_QUBIT': '192',  # 4*4*12 = 192 qubits
}


def get_led_config():
    """
    Load LED configuration from system-wide environment file.

    Returns:
        dict: Configuration dictionary with LED settings

    Note:
        If environment file is missing or unreadable, returns emergency defaults.
        All values are trusted (no validation per Issue #6, #13 decisions).
    """
    if dotenv_values is None:
        print("ERROR: python-dotenv not available, cannot read config")
        print("Using emergency defaults")
        config = EMERGENCY_DEFAULTS
    elif not os.path.exists(ENV_FILE):
        print(f"ERROR: Config file not found: {ENV_FILE}")
        print("Using emergency defaults")
        config = EMERGENCY_DEFAULTS
    elif not os.access(ENV_FILE, os.R_OK):
        print(f"ERROR: Cannot read config file: {ENV_FILE}")
        print("Using emergency defaults")
        config = EMERGENCY_DEFAULTS
    else:
        try:
            config = dotenv_values(ENV_FILE)
        except Exception as e:
            print(f"ERROR: Failed to parse config: {e}")
            print("Using emergency defaults")
            config = EMERGENCY_DEFAULTS

    # --- Resolve the active layout name (LED_LAYOUT is authoritative) ---------
    # New model: LED_LAYOUT names a registry entry directly. For back-compat the
    # legacy LED_MATRIX_LAYOUT=single|quad values map onto the registry presets
    # when LED_LAYOUT is unset.
    if config.get('LED_LAYOUT'):
        layout_name = config.get('LED_LAYOUT')
    else:
        legacy = config.get('LED_MATRIX_LAYOUT', 'single')
        layout_name = _LEGACY_LAYOUT_ALIASES.get(legacy, legacy)

    # LED count becomes derivable from the layout. When LED_LAYOUT is set we
    # trust the layout-derived count over the (possibly stale) LED_COUNT value.
    led_count = int(config.get('LED_COUNT', 192))
    if config.get('LED_LAYOUT'):
        derived = _layout_count(layout_name)
        if derived is not None:
            led_count = derived

    # --- Output-target booleans (independent flags, #231) ---------------------
    # LED_PHYSICAL / LED_VIRTUAL / LED_WEB are the modern, independent flags.
    # LED_VIRTUAL_MIRROR is DEPRECATED: it maps to LED_PHYSICAL=true + LED_VIRTUAL=true.
    raw_virtual = config.get('LED_VIRTUAL', 'false').lower() == 'true'
    raw_mirror = config.get('LED_VIRTUAL_MIRROR', 'false').lower() == 'true'

    if 'LED_PHYSICAL' in config:
        led_physical = config.get('LED_PHYSICAL', 'true').lower() == 'true'
    else:
        # Legacy fallback: physical is on unless the config asked for virtual-only.
        led_physical = raw_mirror or (not raw_virtual)
    led_virtual = raw_virtual or raw_mirror
    led_web = config.get('LED_WEB', 'false').lower() == 'true'

    # Convert to standardized dictionary with type conversions
    return {
        'pi_model': config.get('PI_MODEL', 'Pi5'),
        'led_count': led_count,
        'led_gpio_pin': int(config.get('LED_GPIO_PIN', 18)),
        'pixel_order': config.get('LED_PIXEL_ORDER', 'GRB'),
        # New layout model
        'led_layout': layout_name,
        # Legacy key kept for back-compat with callers that read config['layout']
        'layout': config.get('LED_MATRIX_LAYOUT', 'single'),
        'matrix_width': int(config.get('LED_MATRIX_WIDTH', 24)),
        'matrix_height': int(config.get('LED_MATRIX_HEIGHT', 8)),
        'y_flip': config.get('LED_MATRIX_Y_FLIP', 'false').lower() == 'true',
        'n_qubit': int(config.get('N_QUBIT', 192)),
        'led_default_brightness': float(config.get('LED_DEFAULT_BRIGHTNESS', 0.4)),
        # Output targets
        'led_physical': led_physical,
        'led_virtual': led_virtual,
        'led_web': led_web,
        # Port for the LED_WEB browser emulator (rq_led_web.py).
        'led_web_port': int(config.get('LED_WEB_PORT', 8098)),
        # Render mode: 'direct' (in-process GPIO, default) or 'service' (frames
        # go to the mmap only; rasqberry-led-renderer.service drives the strip).
        # An os.environ override lets a caller switch a subprocess into service
        # mode without rewriting the root-owned env file - used by the LED setup
        # wizard, which runs a private renderer for its lifetime so probe frames
        # are latched across the whiptail prompt. Same env-override pattern as
        # mmap_path()/RQB2_LED_MMAP_PATH.
        'render_mode': os.environ.get(
            'LED_RENDER_MODE', config.get('LED_RENDER_MODE', 'direct')).lower(),
        # Deprecated, retained so existing callers keep working
        'led_virtual_mirror': raw_mirror,
    }


# Logo asset directory name (under RQB2-config / /usr/config)
LOGO_DIRNAME = "LED-Logos"


def get_logo_dir():
    """
    Return the directory holding the LED-Logos image assets.

    The images ship with the OS image at /usr/config/LED-Logos. A user-local
    copy at $USER_HOME/$REPO/RQB2-config/LED-Logos is not populated by default,
    so demos that only looked there failed (#264). Resolution order, user copy
    first so custom logos win:

      1. ~/$REPO/RQB2-config/LED-Logos, if it exists
      2. /usr/config/LED-Logos (where the assets ship) - always returned as the
         fallback, even if absent, so callers have a stable path to report.

    Returns:
        str: Path to the LED-Logos directory.
    """
    repo = os.environ.get('REPO', 'RasQberry-Two')
    user_dir = os.path.expanduser(
        os.path.join('~', repo, 'RQB2-config', LOGO_DIRNAME)
    )
    if os.path.isdir(user_dir):
        return user_dir
    return os.path.join('/usr/config', LOGO_DIRNAME)


# ============================================================================
# Layout registry + generic coordinate mapper
# ============================================================================

def _find_layouts_file():
    """
    Locate the SHIPPED LED layout registry JSON using the dual-path convention.

    Returns:
        str: Path to the shipped led-layouts.json (installed path preferred,
             repo path fallback). The returned path may not exist if neither is
             present.
    """
    installed = os.path.join("/usr/config", LAYOUTS_FILENAME)
    if os.path.exists(installed):
        return installed
    # Development checkout: RQB2-bin/rq_led_utils.py -> ../RQB2-config/<file>
    here = os.path.dirname(os.path.abspath(__file__))
    repo_path = os.path.join(os.path.dirname(here), "RQB2-config", LAYOUTS_FILENAME)
    return repo_path


def _user_layouts_file():
    """
    Path to the USER-LOCAL layout overlay (may not exist).

    Custom layouts written by the LED setup wizard live here so they survive
    OS image updates (which replace /usr/config). Unlike the demo-manifest
    search path - where the shipped/trusted copy WINS on id collision - the user
    overlay WINS here: a custom layout the user just built for their own hardware
    must take precedence over any shipped preset of the same name.

    Resolution mirrors rq_common.sh's USER_HOME convention so it works in the
    raspi-config (root) context: $USER_HOME first, then ~$SUDO_USER, then ~.

    Returns:
        str: Path to $USER_HOME/.local/config/led-layouts.json (or the best
             available home). The file itself may be absent.
    """
    home = os.environ.get('USER_HOME')
    if not home:
        sudo_user = os.environ.get('SUDO_USER')
        home = os.path.expanduser('~' + sudo_user) if sudo_user else os.path.expanduser('~')
    return os.path.join(home, '.local', 'config', LAYOUTS_FILENAME)


def _read_layouts_file(path):
    """Parse one layout registry file, dropping '_'-prefixed metadata keys.

    Returns {} (and prints a diagnostic) when the file is missing or invalid.
    """
    try:
        with open(path, 'r') as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items() if not k.startswith('_')}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"ERROR: Failed to parse layout registry {path}: {e}")
        return {}


def _load_layouts():
    """
    Load and cache the layout registry (shipped presets + user overlay).

    The shipped registry provides the presets; the user-local overlay
    (_user_layouts_file) is merged on top and WINS on name collision, so custom
    layouts emitted by the setup wizard take precedence over shipped presets.

    Returns:
        dict: Mapping of layout name -> layout definition. Registry metadata
              keys (those starting with '_') are excluded. Returns {} if no
              file is present or parseable.
    """
    global _layouts_cache, _layouts_cache_key

    shipped = _find_layouts_file()
    user = _user_layouts_file()
    user_mtime = os.path.getmtime(user) if os.path.exists(user) else None
    key = (shipped, user, user_mtime)

    if _layouts_cache is not None and _layouts_cache_key == key:
        return _layouts_cache

    layouts = _read_layouts_file(shipped)
    if not layouts and not os.path.exists(shipped):
        print(f"ERROR: Layout registry not found: {shipped}")

    # User overlay wins on name collision (opposite of the manifest search path).
    if os.path.exists(user):
        layouts.update(_read_layouts_file(user))

    _layouts_cache = layouts
    _layouts_cache_key = key
    return layouts


def _resolve_layout_name(name):
    """Map legacy layout aliases (single/quad) to registry names; pass through
    names that are already registry entries."""
    if name is None:
        return None
    return _LEGACY_LAYOUT_ALIASES.get(name, name)


def _layout_count(name):
    """
    Compute the derived LED count for a layout (sum of panel w*h).

    Args:
        name (str): Layout name (registry name or legacy alias).

    Returns:
        int or None: Total pixel count, or None if the layout is unknown.
    """
    layout = _load_layouts().get(_resolve_layout_name(name))
    if not layout:
        return None
    return sum(p['w'] * p['h'] for p in layout.get('panels', []))


def get_layout(name=None):
    """
    Return the parsed definition for a layout, including its derived pixel count.

    Args:
        name (str, optional): Layout name (registry name such as 'single-24x8',
            or a legacy alias 'single'/'quad'). If None, the configured layout
            (LED_LAYOUT, or the legacy mapping) is used.

    Returns:
        dict or None: A copy of the layout definition augmented with 'name' and
            'count' keys, or None if the layout cannot be found.

    Example:
        layout = get_layout('quad-2x2-12x4')
        print(layout['count'])   # 192
    """
    if name is None:
        name = get_led_config()['led_layout']
    resolved = _resolve_layout_name(name)
    layout = _load_layouts().get(resolved)
    if not layout:
        return None
    result = dict(layout)
    result['name'] = resolved
    result['count'] = sum(p['w'] * p['h'] for p in layout.get('panels', []))
    return result


def _panel_local_index(lx, ly, w, h, serpentine, start, zigzag=True):
    """
    Compute the panel-local pixel index for a coordinate inside one panel.

    Implements a boustrophedon walk parameterised by the stepping axis and the
    corner that holds panel-local index 0.

    Args:
        lx (int): Panel-local x (0..w-1).
        ly (int): Panel-local y (0..h-1).
        w (int): Panel width.
        h (int): Panel height.
        serpentine (str): 'column' (step along columns) or 'row' (step along rows).
        start (str): 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'.
        zigzag (bool): True (default) for serpentine wiring where alternate
            rows/columns reverse direction; False for PROGRESSIVE wiring where
            every row/column runs in the same direction. Absent from shipped
            presets (all serpentine), so their behaviour is unchanged; the LED
            setup wizard sets zigzag=False for custom progressive panels.

    Returns:
        int: Panel-local index in [0, w*h).
    """
    top = start in ('top-left', 'top-right')
    left = start in ('top-left', 'bottom-left')

    if serpentine == 'row':
        # Primary axis = rows (stepped, alternating), secondary = x within a row.
        r = ly if top else (h - 1 - ly)
        s = lx if left else (w - 1 - lx)
        if zigzag and r % 2 == 1:
            s = w - 1 - s
        return r * w + s

    # Default: 'column'. Primary axis = columns, secondary = y within a column.
    c = lx if left else (w - 1 - lx)
    s = ly if top else (h - 1 - ly)
    if zigzag and c % 2 == 1:
        s = h - 1 - s
    return c * h + s


def map_xy_to_pixel(x, y, layout=None):
    """
    Map logical (x, y) coordinates to a chain pixel index for any layout.

    Generic, registry-driven panel walk (replaces the former hardcoded
    single/quad mappers). Pure function - unit-testable without hardware.

    Args:
        x (int): Column index in logical coordinates (0..width-1, left to right).
        y (int): Row index in logical coordinates (0..height-1, top to bottom).
        layout (str or dict, optional): Layout name (registry name or legacy
            'single'/'quad' alias) or an already-parsed layout dict. If None,
            the configured layout is used.

    Returns:
        int: Chain pixel index, or None if (x, y) is out of bounds or the layout
             is unknown.

    Example:
        pixel_index = map_xy_to_pixel(5, 3)                     # configured layout
        pixel_index = map_xy_to_pixel(5, 3, layout='quad')      # legacy alias
        pixel_index = map_xy_to_pixel(5, 3, layout='single-8x32')
    """
    if isinstance(layout, dict):
        ldef = layout
    else:
        ldef = get_layout(layout)
    if not ldef:
        print(f"Warning: Unknown LED layout '{layout}'")
        return None

    width = ldef['width']
    height = ldef['height']

    # Bounds check against the logical matrix
    if x < 0 or x >= width or y < 0 or y >= height:
        return None

    # Optional per-layout flips for physically rotated/mirrored matrices (D4).
    # y_flip mirrors rows (upside-down top/bottom); x_flip mirrors columns
    # (left/right). Both together = a 180 degree rotation, the common case for a
    # standard panel mounted the other way up in the 3D-printed model. The LED
    # setup wizard writes these onto a base preset to correct a flipped mounting.
    if ldef.get('y_flip', False):
        y = height - 1 - y
    if ldef.get('x_flip', False):
        x = width - 1 - x

    # Walk panels in chain order; each panel occupies a contiguous index block.
    offset = 0
    for panel in ldef.get('panels', []):
        w = panel['w']
        h = panel['h']
        ox, oy = panel['origin']
        if ox <= x < ox + w and oy <= y < oy + h:
            local = _panel_local_index(
                x - ox, y - oy, w, h,
                panel.get('serpentine', 'column'),
                panel.get('start', 'top-left'),
                panel.get('zigzag', True),
            )
            return offset + local
        offset += w * h

    # Coordinate is within the logical bounds but not covered by any panel.
    return None


# Virtual-GUI singleton bookkeeping. Every probe/demo process that enables a
# virtual target calls _ensure_virtual_led_gui_running(); the wizard fires probes
# back to back, so without serialisation each one could spawn its own window and
# they would all linger (detached with start_new_session). A pidfile records the
# one GUI we launched and an flock makes the check-then-spawn atomic, so exactly
# one window ever exists and reap_virtual_led_gui() can tear it down on exit.
_VIRTUAL_GUI_PIDFILE = "/tmp/rasqberry_virtual_led_gui.pid"
_VIRTUAL_GUI_LOCKFILE = "/tmp/rasqberry_virtual_led_gui.lock"
_VIRTUAL_GUI_PATTERN = "rq_led_virtual_gui"

# Web emulator (LED_WEB) singleton bookkeeping - same pidfile+flock scheme as the
# Tk GUI above, so concurrent demos start at most one server and it can be reaped.
_VIRTUAL_WEB_PIDFILE = "/tmp/rasqberry_virtual_led_web.pid"
_VIRTUAL_WEB_LOCKFILE = "/tmp/rasqberry_virtual_led_web.lock"
_VIRTUAL_WEB_PATTERN = "rq_led_web"


def _proc_pid_alive(pid, pattern):
    """True if `pid` is a live process whose command line contains `pattern`.

    Verifies the process command line (Linux /proc) so a reused PID belonging to
    an unrelated process is not mistaken for ours. Falls back to a bare liveness
    probe on platforms without /proc. Shared by the GUI and web-emulator
    singletons so both get the same reused-PID safety.
    """
    if not pid or pid <= 0:
        return False
    if os.path.isdir("/proc"):
        # Linux (the Pi): verify the command line so a reused PID belonging to an
        # unrelated process is not mistaken for ours. A missing entry (dead
        # process) or PID whose cmdline no longer matches counts as not-alive.
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                return pattern.encode() in f.read()
        except OSError:
            return False
    # No /proc (dev laptop): best-effort liveness only.
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pidfile(pidfile):
    """Return the PID recorded in `pidfile`, or None if missing/garbage."""
    try:
        with open(pidfile) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def _running_singleton_pid(pidfile, pattern):
    """PID of a live singleton: the tracked pidfile first, then a pgrep sweep.

    The pgrep fallback catches an instance started outside this mechanism (older
    code or a manual launch) so we still never double-spawn alongside it.
    """
    pid = _read_pidfile(pidfile)
    if _proc_pid_alive(pid, pattern):
        return pid
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', pattern],
                                capture_output=True, timeout=5, text=True)
        if result.returncode == 0:
            for token in result.stdout.split():
                try:
                    return int(token)
                except ValueError:
                    continue
    except Exception:
        pass
    return None


# Thin GUI-named wrappers (names/signatures preserved for callers and tests).
def _gui_pid_alive(pid):
    """True if `pid` is a live virtual-LED-GUI process (see _proc_pid_alive)."""
    return _proc_pid_alive(pid, _VIRTUAL_GUI_PATTERN)


def _read_gui_pid():
    """Return the PID recorded in the GUI pidfile, or None."""
    return _read_pidfile(_VIRTUAL_GUI_PIDFILE)


def _running_gui_pid():
    """PID of a live GUI: the tracked pidfile first, then a pgrep sweep."""
    return _running_singleton_pid(_VIRTUAL_GUI_PIDFILE, _VIRTUAL_GUI_PATTERN)


def _ensure_singleton(pidfile, lockfile, pattern, script_name,
                      extra_env=None, ready_msg=None):
    """Singleton-launch `script_name` (idempotent, race-safe via flock+pidfile).

    An exclusive flock serialises the check-then-spawn so concurrent probe/demo
    processes start at most ONE instance; its PID is written to `pidfile` so the
    matching reaper can tear it down instead of leaving it lingering. Shared by
    the virtual LED GUI and the web emulator.
    """
    import subprocess
    import shutil
    import fcntl
    import time

    lock_fd = None
    try:
        lock_fd = os.open(lockfile, os.O_CREAT | os.O_RDWR, 0o666)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except OSError:
        lock_fd = None  # best effort: proceed without the lock

    try:
        if _running_singleton_pid(pidfile, pattern) is not None:
            return  # already running - singleton

        script = shutil.which(script_name) or ('/usr/bin/' + script_name)
        env = {**os.environ}
        if extra_env:
            env.update(extra_env)
        proc = subprocess.Popen(
            ['python3', script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        try:
            with open(pidfile, 'w') as f:
                f.write(str(proc.pid))
        except OSError:
            pass
        # Diagnostics go to STDERR so they never pollute a whiptail TUI (#19).
        if ready_msg:
            print(ready_msg, file=sys.stderr)
        time.sleep(1)  # Give the process time to initialize
    except Exception as e:
        print(f"Warning: Could not auto-start {script_name}: {e}", file=sys.stderr)
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def _reap_singleton(pidfile, pattern):
    """Terminate the singleton recorded in `pidfile` and clear it.

    Best-effort and idempotent - safe to call when nothing is running. Only the
    process recorded in the pidfile (i.e. one WE auto-launched) is reaped; an
    instance a user started by hand has no pidfile and is left alone.
    """
    import signal
    pid = _read_pidfile(pidfile)
    if _proc_pid_alive(pid, pattern):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        os.remove(pidfile)
    except OSError:
        pass


def _ensure_virtual_led_gui_running():
    """Singleton-launch the virtual LED GUI (idempotent, race-safe)."""
    _ensure_singleton(
        _VIRTUAL_GUI_PIDFILE, _VIRTUAL_GUI_LOCKFILE, _VIRTUAL_GUI_PATTERN,
        'rq_led_virtual_gui.py',
        extra_env={'DISPLAY': os.environ.get('DISPLAY', ':0')},
        ready_msg="Auto-started virtual LED GUI",
    )


def reap_virtual_led_gui():
    """Terminate the auto-launched virtual LED GUI and clear its pidfile.

    The setup wizard calls this on exit so the window it caused to spawn does not
    linger. Reaps only the GUI recorded in the pidfile (one WE launched).
    """
    _reap_singleton(_VIRTUAL_GUI_PIDFILE, _VIRTUAL_GUI_PATTERN)


def _ensure_virtual_led_web_running():
    """Singleton-launch the LED web emulator (idempotent, race-safe).

    The browser analog of _ensure_virtual_led_gui_running(): starts at most one
    rq_led_web.py server (shared frame bus) so concurrent demos don't each spawn
    one. The server itself also refuses to double-bind its port, as a backstop.
    """
    _ensure_singleton(
        _VIRTUAL_WEB_PIDFILE, _VIRTUAL_WEB_LOCKFILE, _VIRTUAL_WEB_PATTERN,
        'rq_led_web.py',
        ready_msg="Auto-started LED web emulator (port %s)"
                  % os.environ.get('LED_WEB_PORT', '8098'),
    )


def reap_virtual_led_web():
    """Terminate the auto-launched LED web emulator and clear its pidfile."""
    _reap_singleton(_VIRTUAL_WEB_PIDFILE, _VIRTUAL_WEB_PATTERN)


def create_neopixel_strip(num_pixels, pixel_order, brightness=0.1, gpio_pin=None):
    """
    Factory function to create NeoPixel strip using PWM (Pi4), PIO (Pi5), or Virtual.

    Uses adafruit-circuitpython-neopixel which auto-detects the platform:
    - Pi 4: Uses rpi_ws281x (PWM/DMA backend) - requires root
    - Pi 5: Uses PIO hardware - requires /dev/pio0
    - Virtual: Uses VirtualNeoPixel when LED_VIRTUAL=true (no hardware needed)

    No SPI, no buffer limits, no chunking needed!

    Render mode (LED_RENDER_MODE, Phase A2):
    - 'direct' (default): current behaviour. This process opens the physical
      strip in-process (needs root/GPIO) when LED_PHYSICAL=true, composing the
      virtual GUI target on top when LED_VIRTUAL=true.
    - 'service': this process NEVER opens a real neopixel strip. It always
      returns a VirtualNeoPixel writer that only writes frames into the mmap.
      The root rasqberry-led-renderer.service is the sole GPIO writer and turns
      those frames physical, so LED_PHYSICAL=true is satisfied WITHOUT this
      (unprivileged) process touching GPIO. LED_VIRTUAL adds nothing extra -
      the GUI simply reads the same mmap - it only decides whether the on-screen
      emulator is auto-launched. This is how demos run as the user with no sudo.

    Args:
        num_pixels (int): Number of LEDs in strip
        pixel_order: Pixel order constant (e.g., neopixel.GRB) or string ('GRB')
        brightness (float): LED brightness 0.0-1.0
        gpio_pin (int, optional): GPIO pin number. If None, reads from config (default 18).

    Returns:
        neopixel.NeoPixel, VirtualNeoPixel, or MirrorNeoPixel: Configured LED strip object

    Note:
        Requires sudo/root for GPIO access (unless using virtual-only mode).
        For Pi 5, requires firmware with /dev/pio0 support.
    """
    config = get_led_config()

    # Compose output targets from the independent LED_PHYSICAL / LED_VIRTUAL /
    # LED_WEB flags (#231). LED_VIRTUAL_MIRROR is folded into these by
    # get_led_config(). A virtual mmap writer feeds the frame bus that BOTH
    # on-screen targets read: the Tk GUI (LED_VIRTUAL) and the browser emulator
    # (LED_WEB). So a virtual writer is needed for either; LED_VIRTUAL launches
    # the GUI and LED_WEB launches the web server, independently.
    led_physical = config.get('led_physical', True)
    led_virtual = config.get('led_virtual', False)
    led_web = config.get('led_web', False)
    render_mode = config.get('render_mode', 'direct')
    need_virtual = led_virtual or led_web

    # Virtual geometry (width/height) drives the mmap v2 self-describing header.
    layout = get_layout(config['led_layout'])
    v_width = layout['width'] if layout else num_pixels
    v_height = layout['height'] if layout else 1

    def _make_virtual():
        from rq_led_virtual import VirtualNeoPixel
        if led_virtual:
            _ensure_virtual_led_gui_running()
        if led_web:
            _ensure_virtual_led_web_running()
        return VirtualNeoPixel(
            None,  # No GPIO pin needed
            num_pixels,
            brightness=brightness,
            auto_write=False,
            pixel_order=pixel_order,
            width=v_width,
            height=v_height,
        )

    def _make_real():
        import board
        import neopixel

        pin = config['led_gpio_pin'] if gpio_pin is None else gpio_pin
        gpio_board_pin = getattr(board, f'D{pin}')
        order = getattr(neopixel, pixel_order) if isinstance(pixel_order, str) else pixel_order
        real_pixels = neopixel.NeoPixel(
            gpio_board_pin,
            num_pixels,
            brightness=brightness,
            auto_write=False,
            pixel_order=order
        )
        real_pixels.fill((0, 0, 0))
        real_pixels.show()
        return real_pixels

    # Service mode: never open GPIO in-process. The renderer service consumes
    # the mmap and drives the strip, so LED_PHYSICAL is served by a single
    # VirtualNeoPixel writer. _make_virtual() auto-launches the on-screen GUI
    # only when LED_VIRTUAL is set and the web emulator only when LED_WEB is set.
    # All diagnostics go to STDERR so they never pollute a whiptail TUI (#19).
    if render_mode == 'service':
        print("LED_RENDER_MODE=service: writing frames to mmap "
              "(rasqberry-led-renderer.service drives the physical strip)",
              file=sys.stderr)
        return _make_virtual()

    # Physical + any virtual target (GUI and/or web) -> mirror proxy
    if led_physical and need_virtual:
        from rq_led_virtual import MirrorNeoPixel
        print("LED_PHYSICAL + virtual target: driving both real and virtual displays",
              file=sys.stderr)
        return MirrorNeoPixel(_make_real(), _make_virtual())

    # Virtual/web only (no physical strip)
    if need_virtual and not led_physical:
        print("Virtual LED target only (GUI/web), no physical strip", file=sys.stderr)
        return _make_virtual()

    # Physical only (also the fallback when no target flag is set)
    if not led_physical and not need_virtual:
        print("Warning: no LED target set (physical/virtual/web); defaulting to physical",
              file=sys.stderr)

    import board
    import neopixel

    # Get GPIO pin from config if not provided
    if gpio_pin is None:
        gpio_pin = config['led_gpio_pin']

    # Convert GPIO pin number to board constant
    # GPIO18 = board.D18
    gpio_board_pin = getattr(board, f'D{gpio_pin}')

    # Convert pixel_order string to neopixel constant if needed
    if isinstance(pixel_order, str):
        pixel_order = getattr(neopixel, pixel_order)

    # Create NeoPixel object
    # Library auto-detects Pi4 (PWM) vs Pi5 (PIO)
    pixels = neopixel.NeoPixel(
        gpio_board_pin,
        num_pixels,
        brightness=brightness,
        auto_write=False,
        pixel_order=pixel_order
    )

    # Initialize all LEDs to black
    pixels.fill((0, 0, 0))
    pixels.show()

    return pixels


def get_pixels(brightness=None):
    """
    Get or create the singleton NeoPixel object.

    This function returns a shared NeoPixel instance to prevent GPIO conflicts
    that occur when multiple NeoPixel objects access the same pin on Pi 5.
    Use this instead of create_neopixel_strip() when you need to share the
    LED strip across multiple modules (e.g., LED Painter's display and clear functions).

    Args:
        brightness (float, optional): LED brightness 0.0-1.0. If None, uses config default.

    Returns:
        neopixel.NeoPixel: Shared LED strip object

    Example:
        pixels = get_pixels()
        pixels[0] = (255, 0, 0)
        pixels.show()
    """
    global _pixels_singleton

    config = get_led_config()

    if brightness is None:
        brightness = config['led_default_brightness']

    if _pixels_singleton is None:
        _pixels_singleton = create_neopixel_strip(
            config['led_count'],
            config['pixel_order'],
            brightness=brightness,
            gpio_pin=config['led_gpio_pin']
        )
    else:
        # Update brightness if specified
        _pixels_singleton.brightness = brightness

    return _pixels_singleton


def clear_all_leds():
    """
    Turn off all LEDs using the singleton NeoPixel object.

    This function uses the shared NeoPixel instance to prevent GPIO conflicts.
    Safe to call from multiple modules (e.g., LED Painter's clear and atexit).

    Example:
        clear_all_leds()  # Turn off all LEDs
    """
    try:
        pixels = get_pixels()
        pixels.fill((0, 0, 0))
        pixels.show()
    except Exception as e:
        print(f"Error clearing LEDs: {e}")


def chunked_show(pixels, chunk_size=None, delay_ms=None):
    """
    Display pixels on LED strip.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    that just calls pixels.show() for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        # Set pixels to desired colors
        pixels[0] = (255, 0, 0)
        pixels[1] = (0, 255, 0)
        # ...
        # Then update display
        chunked_show(pixels)

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.show()


def chunked_fill(pixels, color, chunk_size=None, delay_ms=None):
    """
    Fill all LEDs with a color.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        color: (R, G, B) tuple (0-255 for each channel)
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        chunked_fill(pixels, (255, 0, 0))  # Fill all red
        chunked_fill(pixels, (0, 0, 0))    # Turn all off

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.fill(color)
    pixels.show()


def chunked_clear(pixels, chunk_size=None, delay_ms=None):
    """
    Turn off all LEDs.

    With PWM/PIO drivers, no chunking is needed - this is a simple wrapper
    for backward compatibility with existing code.

    Args:
        pixels: NeoPixel strip object
        chunk_size: Ignored (kept for API compatibility)
        delay_ms: Ignored (kept for API compatibility)

    Usage:
        chunked_clear(pixels)  # Turn off all LEDs

    Note:
        No chunking needed with PWM/PIO drivers - supports 1000+ LEDs.
    """
    pixels.fill((0, 0, 0))
    pixels.show()


def map_xy_to_pixel_single(x, y):
    """
    DEPRECATED thin wrapper for the legacy 'single' layout.

    Prefer ``map_xy_to_pixel(x, y, layout='single-24x8')`` (or simply rely on the
    configured layout). Retained for API compatibility; delegates to the generic
    registry-driven mapper via the 'single-24x8' layout, which bakes in the
    historical LED_MATRIX_Y_FLIP=true behaviour.

    Args:
        x (int): Column index (0..width-1, left to right)
        y (int): Row index (0..height-1, top to bottom)

    Returns:
        int: Pixel index, or None if out of bounds
    """
    return map_xy_to_pixel(x, y, layout='single-24x8')


def map_xy_to_pixel_quad(x, y):
    """
    DEPRECATED thin wrapper for the legacy 'quad' layout.

    Prefer ``map_xy_to_pixel(x, y, layout='quad-2x2-12x4')``. Retained for API
    compatibility; delegates to the generic registry-driven mapper, which
    reproduces the legacy quad arithmetic exactly.

    Args:
        x (int): Column index (0-23, left to right)
        y (int): Row index (0-7, top to bottom)

    Returns:
        int: Pixel index (0-191), or None if out of bounds
    """
    return map_xy_to_pixel(x, y, layout='quad-2x2-12x4')


def create_text_bitmap(text):
    """
    Create a simple 5x7 font bitmap for scrolling text.
    Returns list of columns (each column is 7-bit value).

    Each character is 5 pixels wide, 7 pixels tall.
    Designed for LED matrix text display.

    Args:
        text (str): Text to convert to bitmap

    Returns:
        list: List of column values (0x00-0x7F), 5 columns per character + 1 space

    Example:
        columns = create_text_bitmap("HELLO")
        # Returns list of column values for displaying "HELLO"
    """
    # Simple 5x7 font (uppercase letters, numbers, punctuation)
    # Each character is represented as 5 columns, each column is 7 bits (0x00-0x7F)
    FONT = {
        # Numbers
        '0': [0x3E, 0x51, 0x49, 0x45, 0x3E],
        '1': [0x00, 0x42, 0x7F, 0x40, 0x00],
        '2': [0x62, 0x51, 0x49, 0x49, 0x46],
        '3': [0x22, 0x49, 0x49, 0x49, 0x36],
        '4': [0x18, 0x14, 0x12, 0x7F, 0x10],
        '5': [0x27, 0x45, 0x45, 0x45, 0x39],
        '6': [0x3C, 0x4A, 0x49, 0x49, 0x30],
        '7': [0x01, 0x71, 0x09, 0x05, 0x03],
        '8': [0x36, 0x49, 0x49, 0x49, 0x36],
        '9': [0x06, 0x49, 0x49, 0x29, 0x1E],

        # Uppercase letters (complete A-Z)
        'A': [0x7E, 0x09, 0x09, 0x09, 0x7E],
        'B': [0x7F, 0x49, 0x49, 0x49, 0x36],
        'C': [0x3E, 0x41, 0x41, 0x41, 0x22],
        'D': [0x7F, 0x41, 0x41, 0x41, 0x3E],
        'E': [0x7F, 0x49, 0x49, 0x49, 0x41],
        'F': [0x7F, 0x09, 0x09, 0x09, 0x01],
        'G': [0x3E, 0x41, 0x49, 0x49, 0x7A],  # NEW
        'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
        'I': [0x00, 0x41, 0x7F, 0x41, 0x00],
        'J': [0x20, 0x40, 0x41, 0x3F, 0x01],  # NEW
        'K': [0x7F, 0x08, 0x14, 0x22, 0x41],  # NEW
        'L': [0x7F, 0x40, 0x40, 0x40, 0x40],
        'M': [0x7F, 0x02, 0x0C, 0x02, 0x7F],  # NEW
        'N': [0x7F, 0x02, 0x04, 0x08, 0x7F],
        'O': [0x3E, 0x41, 0x41, 0x41, 0x3E],
        'P': [0x7F, 0x09, 0x09, 0x09, 0x06],
        'Q': [0x3E, 0x41, 0x51, 0x21, 0x5E],  # NEW
        'R': [0x7F, 0x09, 0x19, 0x29, 0x46],  # NEW
        'S': [0x26, 0x49, 0x49, 0x49, 0x32],
        'T': [0x01, 0x01, 0x7F, 0x01, 0x01],
        'U': [0x3F, 0x40, 0x40, 0x40, 0x3F],
        'V': [0x1F, 0x20, 0x40, 0x20, 0x1F],  # NEW
        'W': [0x7F, 0x20, 0x10, 0x20, 0x7F],
        'X': [0x63, 0x14, 0x08, 0x14, 0x63],  # NEW
        'Y': [0x07, 0x08, 0x70, 0x08, 0x07],  # NEW
        'Z': [0x61, 0x51, 0x49, 0x45, 0x43],  # NEW

        # Punctuation and symbols
        ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
        '.': [0x00, 0x60, 0x60, 0x00, 0x00],
        ',': [0x00, 0xA0, 0x60, 0x00, 0x00],  # NEW
        ':': [0x00, 0x36, 0x36, 0x00, 0x00],
        ';': [0x00, 0x56, 0x36, 0x00, 0x00],  # NEW
        '!': [0x00, 0x00, 0x5F, 0x00, 0x00],  # NEW
        '?': [0x02, 0x01, 0x51, 0x09, 0x06],  # NEW
        '-': [0x08, 0x08, 0x08, 0x08, 0x08],  # NEW
        '+': [0x08, 0x08, 0x3E, 0x08, 0x08],  # NEW
        '=': [0x14, 0x14, 0x14, 0x14, 0x14],  # NEW
        '/': [0x60, 0x10, 0x08, 0x04, 0x03],  # NEW
        '*': [0x14, 0x08, 0x3E, 0x08, 0x14],
        '#': [0x14, 0x7F, 0x14, 0x7F, 0x14],  # NEW
        '@': [0x3E, 0x41, 0x5D, 0x55, 0x1E],  # NEW
        '(': [0x00, 0x1C, 0x22, 0x41, 0x00],  # NEW
        ')': [0x00, 0x41, 0x22, 0x1C, 0x00],  # NEW
        '[': [0x00, 0x7F, 0x41, 0x41, 0x00],  # NEW
        ']': [0x00, 0x41, 0x41, 0x7F, 0x00],  # NEW
        '<': [0x08, 0x14, 0x22, 0x41, 0x00],  # NEW
        '>': [0x00, 0x41, 0x22, 0x14, 0x08],  # NEW
        '%': [0x46, 0x26, 0x10, 0x68, 0x64],  # NEW
        '&': [0x36, 0x49, 0x55, 0x22, 0x50],  # NEW
    }

    columns = []

    for char in text.upper():
        if char in FONT:
            # Add character columns
            for col in FONT[char]:
                columns.append(col)
            # Add 1 pixel space between characters
            columns.append(0x00)
        else:
            # Unknown character - show space
            for _ in range(5):
                columns.append(0x00)

    return columns


def display_scrolling_text(pixels, text, duration_seconds=30, scroll_speed=0.1, color=(0, 100, 255)):
    """
    Display scrolling text on LED matrix for specified duration.

    Uses configured LED matrix layout to display text scrolling horizontally.
    Automatically adapts to single or quad panel layouts.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display
        duration_seconds (int): How long to display (seconds)
        scroll_speed (float): Delay between scroll steps (seconds)
        color (tuple): RGB color tuple (0-255 per channel), default bright blue

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_scrolling_text(pixels, "Hello World!", duration_seconds=20)
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate number of scroll positions needed
    total_columns = len(text_columns) + width  # Text + blank screen at end

    start_time = time.time()
    position = 0

    while time.time() - start_time < duration_seconds:
        # Clear all pixels
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)

        # Display current scroll position
        for x in range(width):
            text_col_idx = position + x

            if 0 <= text_col_idx < len(text_columns):
                col_data = text_columns[text_col_idx]

                # Display this column on the LED matrix
                for y in range(min(height, 7)):  # Font is 7 pixels tall
                    if col_data & (1 << y):
                        # Convert x,y to LED index using common mapping function
                        led_index = map_xy_to_pixel(x, y, layout)
                        if led_index is not None:
                            pixels[led_index] = color

        pixels.show()

        # Advance scroll position
        position += 1
        if position >= total_columns:
            position = 0  # Loop

        time.sleep(scroll_speed)

    # Clear LEDs when done
    chunked_clear(pixels)


def display_static_text(pixels, text, duration_seconds=5, color=(255, 255, 255), center=True):
    """
    Display static (non-scrolling) text on LED matrix.

    Text is displayed centered or left-aligned and held for the specified duration.
    Useful for status messages, boot sequences, or short notifications.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display (max ~4 chars for 24-wide matrix)
        duration_seconds (float): How long to display (seconds)
        color (tuple): RGB color tuple (0-255 per channel), default white
        center (bool): If True, center text horizontally. If False, left-align.

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_static_text(pixels, "BOOT", duration_seconds=2, color=(255, 255, 0))
        display_static_text(pixels, "READY", duration_seconds=3, color=(0, 255, 0))
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate starting x position
    text_width = len(text_columns)
    if center and text_width < width:
        start_x = (width - text_width) // 2
    else:
        start_x = 0

    # Clear all pixels
    for i in range(config['led_count']):
        pixels[i] = (0, 0, 0)

    # Display text
    for col_idx, col_data in enumerate(text_columns):
        x = start_x + col_idx
        if x >= width:
            break  # Text too long for display

        # Display this column on the LED matrix
        for y in range(min(height, 7)):  # Font is 7 pixels tall
            if col_data & (1 << y):
                led_index = map_xy_to_pixel(x, y, layout)
                if led_index is not None:
                    pixels[led_index] = color

    pixels.show()

    # Hold for duration
    time.sleep(duration_seconds)

    # Clear LEDs when done
    chunked_clear(pixels)


def display_flashing_text(pixels, text, flash_count=5, flash_speed=0.3, color=(255, 0, 0), center=True):
    """
    Display flashing (blinking) text on LED matrix.

    Text blinks on and off for the specified number of times.
    Useful for alerts, errors, or attention-getting messages.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display (max ~4 chars for 24-wide matrix)
        flash_count (int): Number of times to flash on/off
        flash_speed (float): Time for each on/off cycle (seconds)
        color (tuple): RGB color tuple (0-255 per channel), default red
        center (bool): If True, center text horizontally. If False, left-align.

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_flashing_text(pixels, "ERROR", flash_count=5, color=(255, 0, 0))
        display_flashing_text(pixels, "ALERT", flash_count=3, color=(255, 128, 0))
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate starting x position
    text_width = len(text_columns)
    if center and text_width < width:
        start_x = (width - text_width) // 2
    else:
        start_x = 0

    # Flash loop
    for _ in range(flash_count):
        # Turn ON - display text
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)

        for col_idx, col_data in enumerate(text_columns):
            x = start_x + col_idx
            if x >= width:
                break

            for y in range(min(height, 7)):
                if col_data & (1 << y):
                    led_index = map_xy_to_pixel(x, y, layout)
                    if led_index is not None:
                        pixels[led_index] = color

        pixels.show()
        time.sleep(flash_speed / 2)

        # Turn OFF - clear display
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)
        pixels.show()
        time.sleep(flash_speed / 2)

    # Clear LEDs when done
    chunked_clear(pixels)


def wheel(pos):
    """
    Generate rainbow colors using HSV-to-RGB color wheel algorithm.

    Maps position (0-255) to smooth RGB color transitions through the spectrum.
    This creates a perceptually uniform rainbow effect suitable for LED displays.

    Algorithm divides the 256-position wheel into three equal segments:
    - Segment 1 (0-84):   Red → Green (R decreases, G increases, B=0)
    - Segment 2 (85-169): Green → Blue (G decreases, B increases, R=0)
    - Segment 3 (170-255): Blue → Red (B decreases, R increases, G=0)

    Each transition uses linear interpolation (factor of 3 for smooth steps):
    - pos * 3: Increases color component from 0 to 255
    - 255 - pos * 3: Decreases color component from 255 to 0

    Args:
        pos (int): Position in color wheel (0-255)

    Returns:
        tuple: RGB color tuple (0-255 per channel)

    Examples:
        wheel(0)    # Returns (0, 255, 0)     - Pure red start
        wheel(85)   # Returns (255, 0, 0)     - Pure green
        wheel(170)  # Returns (0, 0, 255)     - Pure blue
        wheel(128)  # Returns (127, 0, 128)   - Purple (between green/blue)

    Note:
        This is a simplified HSV color wheel with fixed saturation and value.
        Full HSV: Hue=(pos*360/256), Saturation=100%, Value=100%
    """
    if pos < 85:
        # Red → Green transition (first third of spectrum)
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        # Green → Blue transition (middle third of spectrum)
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        # Blue → Red transition (final third of spectrum)
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


def display_scrolling_text_rainbow(pixels, text, duration_seconds=30, scroll_speed=0.1):
    """
    Display scrolling text with rainbow color gradient.

    Each character cycles through the color spectrum, creating a
    smooth rainbow gradient effect across the text.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display
        duration_seconds (int): How long to display (seconds)
        scroll_speed (float): Delay between scroll steps (seconds)

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_scrolling_text_rainbow(pixels, "RAINBOW TEXT!", duration_seconds=20)
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate number of scroll positions needed
    total_columns = len(text_columns) + width

    start_time = time.time()
    position = 0
    color_offset = 0

    while time.time() - start_time < duration_seconds:
        # Clear all pixels
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)

        # Display current scroll position
        for x in range(width):
            text_col_idx = position + x

            if 0 <= text_col_idx < len(text_columns):
                col_data = text_columns[text_col_idx]

                # Calculate rainbow color based on column position
                color_pos = (text_col_idx * 8 + color_offset) % 256
                color = wheel(color_pos)

                # Display this column on the LED matrix
                for y in range(min(height, 7)):
                    if col_data & (1 << y):
                        led_index = map_xy_to_pixel(x, y, layout)
                        if led_index is not None:
                            pixels[led_index] = color

        pixels.show()

        # Advance scroll position and color offset
        position += 1
        if position >= total_columns:
            position = 0

        color_offset = (color_offset + 2) % 256  # Cycle colors

        time.sleep(scroll_speed)

    # Clear LEDs when done
    chunked_clear(pixels)


def display_static_text_rainbow(pixels, text, duration_seconds=5, center=True, cycle_speed=0.05):
    """
    Display static text with color cycling rainbow effect.

    Text remains stationary while colors cycle through the rainbow spectrum,
    creating a dynamic color-changing effect.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display (max ~4 chars for 24-wide matrix)
        duration_seconds (float): How long to display (seconds)
        center (bool): If True, center text horizontally. If False, left-align.
        cycle_speed (float): Speed of color cycling (seconds per step)

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        display_static_text_rainbow(pixels, "COOL", duration_seconds=10)
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate starting x position
    text_width = len(text_columns)
    if center and text_width < width:
        start_x = (width - text_width) // 2
    else:
        start_x = 0

    start_time = time.time()
    color_offset = 0

    while time.time() - start_time < duration_seconds:
        # Clear all pixels
        for i in range(config['led_count']):
            pixels[i] = (0, 0, 0)

        # Display text with cycling rainbow colors
        for col_idx, col_data in enumerate(text_columns):
            x = start_x + col_idx
            if x >= width:
                break

            # Calculate rainbow color based on column position
            color_pos = (col_idx * 8 + color_offset) % 256
            color = wheel(color_pos)

            # Display this column on the LED matrix
            for y in range(min(height, 7)):
                if col_data & (1 << y):
                    led_index = map_xy_to_pixel(x, y, layout)
                    if led_index is not None:
                        pixels[led_index] = color

        pixels.show()

        # Cycle colors
        color_offset = (color_offset + 4) % 256
        time.sleep(cycle_speed)

    # Clear LEDs when done
    chunked_clear(pixels)


def display_text_gradient(pixels, text, duration_seconds=5, color1=(255, 0, 0), color2=(0, 0, 255), center=True):
    """
    Display static text with a color gradient between two colors.

    Text displays with a smooth color transition from color1 to color2
    across the width of the text.

    Args:
        pixels: NeoPixel object
        text (str): Text string to display (max ~4 chars for 24-wide matrix)
        duration_seconds (float): How long to display (seconds)
        color1 (tuple): Starting color RGB tuple (0-255 per channel)
        color2 (tuple): Ending color RGB tuple (0-255 per channel)
        center (bool): If True, center text horizontally. If False, left-align.

    Example:
        pixels = create_neopixel_strip(192, 'GRB', 0.3)
        # Red to blue gradient
        display_text_gradient(pixels, "GRAD", duration_seconds=5,
                            color1=(255, 0, 0), color2=(0, 0, 255))
    """
    import time

    # Get configuration
    config = get_led_config()
    width = config['matrix_width']
    height = config['matrix_height']
    layout = config['layout']

    # Create text bitmap
    text_columns = create_text_bitmap(text)

    if not text_columns:
        return

    # Calculate starting x position
    text_width = len(text_columns)
    if center and text_width < width:
        start_x = (width - text_width) // 2
    else:
        start_x = 0

    # Clear all pixels
    for i in range(config['led_count']):
        pixels[i] = (0, 0, 0)

    # Display text with gradient
    for col_idx, col_data in enumerate(text_columns):
        x = start_x + col_idx
        if x >= width:
            break

        # Calculate gradient color based on position
        if text_width > 1:
            ratio = col_idx / (text_width - 1)
        else:
            ratio = 0.5

        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        color = (r, g, b)

        # Display this column on the LED matrix
        for y in range(min(height, 7)):
            if col_data & (1 << y):
                led_index = map_xy_to_pixel(x, y, layout)
                if led_index is not None:
                    pixels[led_index] = color

    pixels.show()

    # Hold for duration
    time.sleep(duration_seconds)

    # Clear LEDs when done
    chunked_clear(pixels)


# Module self-test
if __name__ == "__main__":
    print("RasQberry LED Utilities Module Test")
    print("=" * 50)

    # Test configuration loading
    print("\n1. Testing configuration loading...")
    config = get_led_config()
    print(f"   Pi Model: {config['pi_model']}")
    print(f"   LED Count: {config['led_count']}")
    print(f"   LED GPIO Pin: {config['led_gpio_pin']}")
    print(f"   Pixel Order: {config['pixel_order']}")
    print(f"   Layout: {config['layout']}")

    # Test coordinate mapping - single layout
    print("\n2. Testing single layout coordinate mapping...")
    test_coords_single = [(0, 0), (1, 0), (0, 7), (23, 7)]
    for x, y in test_coords_single:
        idx = map_xy_to_pixel_single(x, y)
        print(f"   ({x:2d}, {y:2d}) -> pixel {idx}")

    # Test coordinate mapping - quad layout
    print("\n3. Testing quad layout coordinate mapping...")
    test_coords_quad = [(0, 0), (12, 0), (0, 4), (12, 4)]
    for x, y in test_coords_quad:
        idx = map_xy_to_pixel_quad(x, y)
        print(f"   ({x:2d}, {y:2d}) -> pixel {idx}")

    # Test bounds checking
    print("\n4. Testing bounds checking...")
    invalid_coords = [(-1, 0), (24, 0), (0, -1), (0, 8)]
    for x, y in invalid_coords:
        idx = map_xy_to_pixel(x, y)
        print(f"   ({x:2d}, {y:2d}) -> {idx}")

    print("\n" + "=" * 50)
    print("Module test complete!")