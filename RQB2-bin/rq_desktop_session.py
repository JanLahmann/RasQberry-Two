#!/usr/bin/env python3
"""
RasQberry Two: fit the desktop to the screen at every login, then open the browser.

Started by /etc/xdg/autostart/rasqberry-browser.desktop as the desktop user:

1. Chromium forgets an unclean exit, so "Restore pages?" does not come back
   after every later start (R-154).
2. Touch mode: the GTK touch style is copied again, because labwc-pi deletes
   ~/.config/gtk-3.0/gtk.css at every session start (R-098).
3. Small screens (narrower than 1600 or lower than 900 px: the 7-inch display,
   720p): Chromium opens maximised instead of at x=480, which put most of the
   window off-screen (R-034). The labwc rule that places Chromium next to the
   icons is switched off, and /etc/chromium.d/rasqberry adds --start-maximized.
4. Desktop icons are laid out for the screen and touch mode, RasQberry Setup
   first (R-008, R-035). Icons that do not fit go into a "More" folder. This
   happens only when the screen, touch mode or the set of icons changed, so
   icons the user moved stay where they are.
5. Browser (BROWSER_AUTOSTART): rasqberry.org, or a local page that says what
   to do without internet (R-101, Q15).

Usage:
    rq_desktop_session.py                 everything (the autostart)
    rq_desktop_session.py --no-browser    steps 1-4 only
    rq_desktop_session.py --screen        print the screen size (WxH)
    rq_desktop_session.py --layout WxH CONF [--touch]
                                          write the icon positions for a
                                          WxH screen into CONF (image build)
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

logging.basicConfig(level=logging.INFO, format="rq_desktop_session: %(message)s")
logger = logging.getLogger(__name__)

HOME = os.path.expanduser("~")
ENV_FILE = "/usr/config/rasqberry_environment.env"
TOUCH_STATE = "/var/lib/rasqberry/touch-mode.conf"
TOUCH_CSS = "/usr/config/touch-mode/gtk-touch.css"
OFFLINE_PAGE = "file:///usr/share/rasqberry/offline.html"
HOMEPAGE = "https://rasqberry.org"
SMALL_WIDTH, SMALL_HEIGHT = 1600, 900

# The desktop's own launchers, in the order they are laid out (row by row).
# Setup, the menu and the touch switch come first, then the learning paths
# (a way into the demos), the LED tools last.
ICON_ORDER = [
    "rasqberry-setup", "rasqberry-menu", "my-quantum-programs", "touch-mode",
    "learning-paths", "composer", "grok-bloch", "quantum-fractals",
    "led-ibm-demo", "quantum-lights-out", "rasq-led", "quantum-raspberry-tie",
    "led-painter", "qoffee-maker", "quantum-mixer", "quantum-paradoxes",
    "qiskit-tutorials", "doqumentation", "fun-with-quantum", "quantum-coin-game", "ibm-quantum-tutorials",
    "ibm-quantum-courses", "quantum-lab", "demo-loop", "clear-leds",
]
MORE_DIR = "More"
MARGIN = 10                # first icon at x=y=10, as pcmanfm counts (below the panel)
CHROMIUM_X = 480           # where the labwc rule puts Chromium on large screens
NORMAL_GRID = 110
LABEL_HEIGHT = 40          # two lines of PibotoLt 12 under an icon


def env_value(key, default="", path=ENV_FILE):
    """
    Return the last KEY=value in the RasQberry environment file.

    Args:
        key (str): Variable name.
        default (str): Returned when the file or key is missing.
        path (str): Environment file.

    Returns:
        str: The value without quotes.
    """
    value = default
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith(key + "="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return value


def touch_mode_on(path=TOUCH_STATE):
    """
    Tell whether touch mode is enabled.

    Args:
        path (str): Touch-mode state file.

    Returns:
        bool: True when the state file says TOUCH_MODE=enabled.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return any(line.strip() == "TOUCH_MODE=enabled" for line in fh)
    except OSError:
        return False


# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------
def parse_wlr_randr(text):
    """
    Read the logical size of the first enabled output from wlr-randr's output.

    Args:
        text (str): What `wlr-randr` printed.

    Returns:
        tuple: (width, height) in logical pixels, or None.
    """
    for block in re.split(r"\n(?=\S)", text):
        if not re.search(r"^\s*Enabled: yes", block, re.M):
            continue
        mode = re.search(r"^\s+(\d+)x(\d+) px.*current", block, re.M)
        if not mode:
            continue
        w, h = int(mode.group(1)), int(mode.group(2))
        transform = re.search(r"^\s*Transform: (\S+)", block, re.M)
        if transform and transform.group(1) in ("90", "270", "flipped-90", "flipped-270"):
            w, h = h, w
        scale = re.search(r"^\s*Scale: ([\d.]+)", block, re.M)
        if scale and float(scale.group(1)) > 0:
            w, h = int(w / float(scale.group(1))), int(h / float(scale.group(1)))
        return w, h
    return None


def screen_size():
    """
    Ask the compositor for the screen size.

    Returns:
        tuple: (width, height), or None without wlr-randr or a Wayland display.
    """
    if not shutil.which("wlr-randr"):
        return None
    try:
        out = subprocess.run(["wlr-randr"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_wlr_randr(out)


def is_small(size):
    """
    Tell whether a screen is too small for Chromium next to the icons.

    Args:
        size (tuple): (width, height).

    Returns:
        bool: True below 1600x900.
    """
    return size[0] < SMALL_WIDTH or size[1] < SMALL_HEIGHT


# --------------------------------------------------------------------------
# 1. Chromium: no "Restore pages?" after an unclean exit
# --------------------------------------------------------------------------
def reset_chromium_exit(prefs=None):
    """
    Mark Chromium's last exit as clean (R-154).

    Chromium keeps exit_type "Crashed" across later normal stops, so the
    bubble came back every time. Only runs while Chromium is not running.

    Args:
        prefs (str): Path of the profile's Preferences file.

    Returns:
        bool: True if the file was changed.
    """
    prefs = prefs or os.path.join(HOME, ".config/chromium/Default/Preferences")
    try:
        with open(prefs, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return False
    new = re.sub(r'"exit_type"\s*:\s*"[A-Za-z]+"', '"exit_type":"Normal"', text)
    new = re.sub(r'"exited_cleanly"\s*:\s*false', '"exited_cleanly":true', new)
    if new == text:
        return False
    with open(prefs, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


# --------------------------------------------------------------------------
# 2. Touch mode GTK style
# --------------------------------------------------------------------------
def apply_touch_css(touch, src=TOUCH_CSS, dst=None):
    """
    Copy the GTK touch style again in touch mode (labwc-pi removed it).

    Args:
        touch (bool): Touch mode is on.
        src (str): Shipped style sheet.
        dst (str): ~/.config/gtk-3.0/gtk.css.

    Returns:
        bool: True if the style was copied.
    """
    dst = dst or os.path.join(HOME, ".config/gtk-3.0/gtk.css")
    if not touch or not os.path.isfile(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return True


# --------------------------------------------------------------------------
# 3. Chromium placement
# --------------------------------------------------------------------------
_RULE = re.compile(r'(<windowRule identifier=")(chromium|rasqberry-small-screen-chromium)"[^>]*(>\s*'
                   r'<action name="MoveTo" x="480" y="45"\s*/>)')


def set_chromium_rule(small, rc=None):
    """
    Switch the labwc rule that puts Chromium at x=480 off on small screens.

    The rule keeps the icons visible on a large screen; on a small one it put
    the window off-screen, and it would also move a maximised window. Off
    means a different identifier, so the rest of rc.xml stays as it is.
    type="normal" matchOnce="true": it places only the browser's first window
    (the homepage), not a demo's window opened next to it, which it moved
    480 px to the right when that was maximised before it was shown (#4).
    matchOnce counts every window, also a hidden one Chromium makes first
    (labwc types it "dialog"), so without type="normal" the homepage itself
    was not placed. Older rc.xml files get both here too.

    Args:
        small (bool): The screen is small.
        rc (str): ~/.config/labwc/rc.xml.

    Returns:
        bool: True if rc.xml was changed.
    """
    rc = rc or os.path.join(HOME, ".config/labwc/rc.xml")
    try:
        with open(rc, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return False
    want = "rasqberry-small-screen-chromium" if small else "chromium"
    new = _RULE.sub(lambda m: m.group(1) + want + '" type="normal" matchOnce="true"' + m.group(3), text)
    if new == text:
        return False
    with open(rc, "w", encoding="utf-8") as fh:
        fh.write(new)
    return True


def set_small_screen_flag(small, path=None):
    """
    Create or remove the flag /etc/chromium.d/rasqberry reads (--start-maximized).

    Args:
        small (bool): The screen is small.
        path (str): Flag file (default $XDG_RUNTIME_DIR/rasqberry-small-screen).
    """
    path = path or os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()),
                                "rasqberry-small-screen")
    try:
        if small:
            open(path, "w").close()
        elif os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("small-screen flag: %s", exc)


# --------------------------------------------------------------------------
# 4. Desktop icons
# --------------------------------------------------------------------------
def libfm_icon_size(path=None):
    """
    Read the desktop icon size (libfm big_icon_size; touch mode makes it 72).

    Args:
        path (str): ~/.config/libfm/libfm.conf.

    Returns:
        int: Icon size in pixels (48 if unknown).
    """
    path = path or os.path.join(HOME, ".config/libfm/libfm.conf")
    try:
        with open(path, encoding="utf-8") as fh:
            m = re.search(r"^big_icon_size=(\d+)", fh.read(), re.M)
            return int(m.group(1)) if m else 48
    except OSError:
        return 48


def plan_layout(names, width, height, touch=False, icon=48, grid=None, panel=None):
    """
    Place the icons row by row on a WIDTHxHEIGHT screen.

    On a large screen the icons stay left of Chromium (x < 480) while they fit
    there. Rows and columns never leave the screen: the grid gets tighter
    first, and what still does not fit goes into the More folder, which takes
    the last place.

    Args:
        names (list): Launchers present, in ICON_ORDER order.
        width (int): Screen width.
        height (int): Screen height.
        touch (bool): Touch mode (bigger grid and panel).
        icon (int): Desktop icon size.
        grid (int): Grid spacing (default 110, touch 140).
        panel (int): Panel height (default 36, touch 64).

    Returns:
        tuple: (positions, overflow): positions maps a name (or MORE_DIR) to
        (x, y); overflow lists the names that go into the More folder.
    """
    panel = panel or (64 if touch else 36)
    min_grid = icon + 30
    grid = max(grid or (140 if touch else NORMAL_GRID), min_grid)
    cell_h = icon + LABEL_HEIGHT

    def step_y(g):
        # rows never closer than icon + label: they would overlap
        return max(g, cell_h + 5)

    def fit(g):
        rows = max(1, (height - panel - MARGIN - cell_h) // step_y(g) + 1)
        cols = max(1, (width - MARGIN - (g - 10)) // g + 1)
        return rows, cols

    # a tighter grid (down to icon + 30 px) before anything goes into More
    rows, cols_screen = fit(grid)
    while len(names) > rows * cols_screen and grid - 5 >= min_grid:
        grid -= 5
        rows, cols_screen = fit(grid)
    cols = cols_screen
    if not is_small((width, height)):
        # left of Chromium (a tighter grid if need be), else as few columns
        # as possible
        def cols_left(g):
            return max(1, (CHROMIUM_X - MARGIN - (g - 10)) // g + 1)
        g = grid
        while len(names) > cols_left(g) * fit(g)[0] and g - 5 >= min_grid:
            g -= 5
        if len(names) <= cols_left(g) * fit(g)[0]:
            grid = g
            rows, cols = fit(g)[0], cols_left(g)
        else:
            cols = min(cols_screen, -(-len(names) // rows))
    capacity = cols * rows
    overflow = []
    placed = list(names)
    if len(placed) > capacity:
        placed, overflow = placed[:capacity - 1], placed[capacity - 1:]
        placed.append(MORE_DIR)
    positions = {}
    for i, name in enumerate(placed):
        positions[name] = (MARGIN + (i % cols) * grid, MARGIN + (i // cols) * step_y(grid))
    return positions, overflow


def write_positions(conf, positions):
    """
    Write icon positions into a pcmanfm desktop-items file, keeping the rest.

    Args:
        conf (str): desktop-items-0.conf.
        positions (dict): name -> (x, y); names without ".desktop" are folders.
    """
    try:
        with open(conf, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    # drop the sections we place, keep [*] and everything else
    sections = re.split(r"(?m)^(?=\[)", text)
    ours = {(n if n == MORE_DIR else n + ".desktop") for n in positions}
    ours |= {n + ".desktop" for n in ICON_ORDER} | {MORE_DIR}
    kept = [s for s in sections if s.strip() and s.split("]", 1)[0][1:] not in ours]
    out = "".join(s if s.endswith("\n") else s + "\n" for s in kept)
    for name, (x, y) in positions.items():
        key = name if name == MORE_DIR else name + ".desktop"
        out += "[%s]\nx=%d\ny=%d\ntrusted=true\n" % (key, x, y)
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write(out)


def sort_into_more(desktop, overflow):
    """
    Move the overflow launchers into Desktop/More and the rest back out.

    Only RasQberry's own launchers (ICON_ORDER) are moved; a copy on the
    desktop wins over one in the folder. An empty More folder is removed.

    Args:
        desktop (str): ~/Desktop.
        overflow (list): Names that go into the folder.
    """
    more = os.path.join(desktop, MORE_DIR)
    if overflow:
        os.makedirs(more, exist_ok=True)
    for name in ICON_ORDER:
        fname = name + ".desktop"
        on_desk, in_more = os.path.join(desktop, fname), os.path.join(more, fname)
        if name in overflow and os.path.exists(on_desk):
            os.replace(on_desk, in_more)
        elif name not in overflow and os.path.exists(in_more):
            if os.path.exists(on_desk):
                os.remove(in_more)
            else:
                os.replace(in_more, on_desk)
    try:
        os.rmdir(more)  # only when empty
    except OSError:
        pass


def present_launchers(desktop):
    """
    List RasQberry's launchers on the desktop or in its More folder.

    Args:
        desktop (str): ~/Desktop.

    Returns:
        list: Names in ICON_ORDER order.
    """
    found = []
    for name in ICON_ORDER:
        fname = name + ".desktop"
        if os.path.exists(os.path.join(desktop, fname)) or \
                os.path.exists(os.path.join(desktop, MORE_DIR, fname)):
            found.append(name)
    return found


def pcmanfm_profile(autostart=None):
    """
    The pcmanfm profile the desktop runs with.

    Bookworm's labwc autostart starts "pcmanfm --desktop --profile LXDE-pi";
    trixie's starts pcmanfm-pi, which runs "pcmanfm --desktop": the "default"
    profile. The user's own autostart wins over the system one.

    Args:
        autostart (list): labwc autostart files to read (tests).

    Returns:
        str: Profile name.
    """
    files = autostart or [os.path.join(HOME, ".config/labwc/autostart"), "/etc/xdg/labwc/autostart"]
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        if "pcmanfm" in text:
            m = re.search(r"pcmanfm\b[^\n]*--profile[ =](\S+)", text)
            return m.group(1).rstrip("&") if m else "default"
    return "default"


def layout_desktop(size, touch, desktop=None, conf=None, record=None, force=False):
    """
    Lay the icons out when the screen, touch mode or the icon set changed.

    Args:
        size (tuple): (width, height).
        touch (bool): Touch mode.
        desktop (str): ~/Desktop.
        conf (str): pcmanfm desktop-items-0.conf.
        record (str): File remembering what the last layout was made for.
        force (bool): Lay out even if nothing changed.

    Returns:
        bool: True if a new layout was written.
    """
    desktop = desktop or os.path.join(HOME, "Desktop")
    conf = conf or os.path.join(HOME, ".config/pcmanfm", pcmanfm_profile(), "desktop-items-0.conf")
    record = record or os.path.join(HOME, ".config/rasqberry/desktop-layout")
    names = present_launchers(desktop)
    icon = libfm_icon_size()
    key = json.dumps({"screen": list(size), "touch": touch, "icon": icon, "icons": names})
    try:
        with open(record, encoding="utf-8") as fh:
            if fh.read().strip() == key and not force:
                return False
    except OSError:
        pass
    spacing = env_value("TOUCH_DESKTOP_GRID_SPACING", "140")
    grid = (int(spacing) if spacing.isdigit() else 140) if touch else None
    positions, overflow = plan_layout(names, size[0], size[1], touch=touch, icon=icon, grid=grid)
    sort_into_more(desktop, overflow)
    if os.path.isdir(os.path.dirname(conf)):
        write_positions(conf, positions)
    os.makedirs(os.path.dirname(record), exist_ok=True)
    with open(record, "w", encoding="utf-8") as fh:
        fh.write(key + "\n")
    return True


def run_quietly(cmd):
    """
    Run a command and ignore its failure (pcmanfm/labwc may not be running).

    Args:
        cmd (list): Command line.
    """
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


# --------------------------------------------------------------------------
# 5. Browser
# --------------------------------------------------------------------------
def online(url=HOMEPAGE, timeout=5):
    """
    Tell whether the homepage answers.

    Args:
        url (str): Page to try.
        timeout (int): Seconds.

    Returns:
        bool: True if it answered.
    """
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=timeout)
        return True
    except Exception:  # noqa: BLE001 - any failure means "not now"
        return False


def start_browser(small):
    """
    Open rasqberry.org, or the offline page, unless BROWSER_AUTOSTART=false.

    Args:
        small (bool): The screen is small (Chromium opens maximised then).
    """
    if env_value("BROWSER_AUTOSTART", "true") == "false":
        return
    time.sleep(int(os.environ.get("RQ_BROWSER_DELAY", "10")))  # clock and network
    url = HOMEPAGE if online() else OFFLINE_PAGE
    cmd = ["/usr/bin/chromium"]
    if not small:
        cmd.append("--window-size=1070,1005")
    cmd.append(url)
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as exc:
        logger.warning("could not start Chromium: %s", exc)


def main(argv):
    """
    Run the login steps.

    Args:
        argv (list): Command-line arguments.

    Returns:
        int: Exit status.
    """
    if argv[:1] == ["--screen"]:
        size = screen_size()
        if size:
            print("%dx%d" % size)
        return 0 if size else 1
    if argv[:1] == ["--layout"] and len(argv) >= 3:
        w, h = (int(v) for v in argv[1].split("x"))
        positions, _ = plan_layout(ICON_ORDER, w, h, touch="--touch" in argv)
        write_positions(argv[2], positions)
        return 0
    reset_chromium_exit()
    touch = touch_mode_on()
    apply_touch_css(touch)
    size = screen_size()
    small = bool(size and is_small(size))
    set_small_screen_flag(small)
    if size:
        if set_chromium_rule(small) and os.environ.get("LABWC_PID"):
            run_quietly(["labwc", "--reconfigure"])
        if layout_desktop(size, touch):
            run_quietly(["pcmanfm", "--reconfigure"])
    if "--no-browser" not in argv:
        start_browser(small)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
