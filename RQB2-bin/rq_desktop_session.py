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
4. Desktop icons start at a double-click (quick_exec, T1). The demos are
   sorted into one folder per group (demo-groups.json: LED panel, Play, ...);
   the desktop shows the system icons, a few starters (also in their folders)
   and one icon per group, which opens its folder. They are laid out for the
   screen and touch mode, RasQberry Setup last (R-008, R-035); on a screen
   too small for all of them the starters go first. This happens only when
   the screen, touch mode or the set of icons changed, so icons the user
   moved stay where they are. A group's icon opens its window
   (rq_group_window.py): the group's demos as icons, not the raw folder.
   The Touch Mode icon is on the desktop only while a touchscreen is
   connected (udev: ID_INPUT_TOUCHSCREEN=1); without one it waits out of
   sight (Desktop Settings in the RasQberry menu switch touch mode too).
   RasQberry Setup is the last icon, and goes once the setup checklist is
   done (the menu keeps the checklist).
5. Browser (BROWSER_AUTOSTART): rasqberry.org, or a local page that says what
   to do without internet (R-101, Q15). With DEMO_LOOP_AT_LOGIN=true (Demo
   Loop menu, off as shipped) the Demo Loop starts in a terminal window
   instead, for a stand (R-123).

Usage:
    rq_desktop_session.py                 everything (the autostart)
    rq_desktop_session.py --no-browser    steps 1-4 only
    rq_desktop_session.py --relayout      step 4 only (a catalogue demo's
                                          launcher came or went)
    rq_desktop_session.py --open-group ID open a group's window (its icon)
    rq_desktop_session.py --touchscreen   exit 0 if a touchscreen is connected
    rq_desktop_session.py --quick-exec [CONF]
                                          set quick_exec=1 in the profile's
                                          pcmanfm.conf (or CONF)
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
# "?from=pi": the site greets a Pi (start with First 15 minutes) instead of
# offering to write the SD card that is already in it (fresh-card test
# 2026-10-08, F4); the Chromium policy's home page says the same
HOMEPAGE = "https://rasqberry.org/?from=pi"
SMALL_WIDTH, SMALL_HEIGHT = 1600, 900

# Every launcher the image puts on the desktop (stage 06). Where each one
# goes - loose on the desktop or into a group folder - and the order of the
# loose ones come from demo-groups.json and the demo manifests.
ICON_ORDER = [
    "rasqberry-setup", "rasqberry-menu", "my-quantum-programs", "touch-mode",
    "learning-paths", "composer", "grok-bloch", "quantum-fractals",
    "led-ibm-demo", "quantum-lights-out", "rasq-led", "quantum-raspberry-tie",
    "led-painter", "qoffee-maker", "quantum-mixer", "entangible", "quantum-paradoxes",
    "qiskit-tutorials", "doqumentation", "fun-with-quantum", "quantum-coin-game", "ibm-quantum-tutorials",
    "ibm-quantum-courses", "quantum-lab", "demo-loop", "clear-leds",
]
MORE_DIR = "More"
MARGIN = 10                # first icon at x=y=10 (bookworm: below the panel)
CHROMIUM_X = 480           # where the labwc rule puts Chromium on large screens
NORMAL_GRID = 110
LABEL_HEIGHT = 40          # two lines of PibotoLt 12 under an icon (bookworm)
LABEL_HEIGHT_NUNITO = 54   # two lines of Nunito Sans Light 12 (trixie), measured
ITEM_WIDTH = 120           # an icon's label is up to ~110 px wide
# Catalogue demos put their launchers on the desktop as rq-ext-<id>.desktop:
# they are laid out after RasQberry's own, in the same grid (T5)
CATALOGUE_PREFIX = "rq-ext-"
# Demo groups (demo-groups.json): a folder per group, out of sight, and a
# launcher per group on the desktop that opens it. pcmanfm-pi shows no custom
# icon for a folder (libfm reads no .directory file), so the desktop gets a
# launcher with the group's own icon instead of the folder itself.
GROUP_PREFIX = "rq-group-"
_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = "/usr/config" if _HERE == "/usr/bin" else os.path.join(os.path.dirname(_HERE), "RQB2-config")
GROUPS_FILE = os.path.join(CONFIG_DIR, "demo-manifests", "demo-groups.json")
KNOWN_DEMOS = os.path.join(CONFIG_DIR, "known-demos.json")
ICON_DIR = "/usr/share/icons/rasqberry"
# pcmanfm profiles whose icon positions count from the top of the screen.
# Trixie's pcmanfm-pi ("default" profile) places x/y on the whole screen, so
# y=10 is under the panel and pcmanfm pushed the first row down onto the
# second (T5). Bookworm's (LXDE-pi) counts below the panel.
SCREEN_POSITION_PROFILES = ("default",)
# Launchers on the desktop only while a touchscreen is connected; without one
# they wait in HIDDEN_DIR (under the home) and come back with one (Jan,
# 2026-10-08). udev marks a touchscreen's input device ID_INPUT_TOUCHSCREEN=1.
TOUCHSCREEN_ONLY = ("touch-mode",)
HIDDEN_DIR = ".local/share/rasqberry/desktop-hidden"
# RasQberry Setup is the last icon, and only until the setup checklist is
# done (rq_firstlogin.sh writes this mark: no step pending, or "Don't show
# again and remove the icon"); the checklist stays in the RasQberry menu
# (Jan, 2026-10-08)
SETUP_LAUNCHER = "rasqberry-setup"
SETUP_DONE = ".local/state/rasqberry/setup-done"
UDEV_DATA = "/run/udev/data"


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


def has_touchscreen(udev_data=UDEV_DATA):
    """
    Tell whether a touchscreen is connected.

    udev's input_id marks a touchscreen's input devices
    ID_INPUT_TOUCHSCREEN=1 (libinput goes by the same mark); udev keeps each
    device's properties in /run/udev/data (c13:<minor> for the event nodes,
    +input:inputN for the devices), readable by everyone.

    Args:
        udev_data (str): udev's database directory (tests).

    Returns:
        bool: True if an input device is a touchscreen.
    """
    try:
        names = os.listdir(udev_data)
    except OSError:
        return False
    for name in names:
        if not (name.startswith("c13:") or name.startswith("+input:")):
            continue
        try:
            with open(os.path.join(udev_data, name), encoding="utf-8", errors="replace") as fh:
                if re.search(r"^E:ID_INPUT_TOUCHSCREEN=1$", fh.read(), re.M):
                    return True
        except OSError:
            continue
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
def pcmanfm_conf(profile=None, home=None):
    """
    The person's pcmanfm.conf for the profile the desktop runs with.

    Args:
        profile (str): pcmanfm profile (default: the desktop's).
        home (str): Home directory (tests).

    Returns:
        str: ~/.config/pcmanfm/<profile>/pcmanfm.conf.
    """
    return os.path.join(home or HOME, ".config/pcmanfm", profile or pcmanfm_profile(), "pcmanfm.conf")


def _ini_value(text, key):
    m = re.search(r"^%s=(.*)$" % re.escape(key), text, re.M)
    return m.group(1).strip() if m else None


def libfm_icon_size(path=None, libfm=None):
    """
    Read the desktop icon size (big_icon_size; touch mode makes it 72).

    Trixie's pcmanfm-pi takes it from the profile's pcmanfm.conf and no
    longer reads ~/.config/libfm/libfm.conf; bookworm's from libfm.conf.

    Args:
        path (str): The profile's pcmanfm.conf.
        libfm (str): ~/.config/libfm/libfm.conf.

    Returns:
        int: Icon size in pixels (48 if unknown).
    """
    for conf in (path or pcmanfm_conf(), libfm or os.path.join(HOME, ".config/libfm/libfm.conf")):
        try:
            with open(conf, encoding="utf-8") as fh:
                value = _ini_value(fh.read(), "big_icon_size")
        except OSError:
            continue
        if value and value.isdigit():
            return int(value)
    return 48


def set_ini_value(text, section, key, value):
    """
    Set KEY=VALUE in SECTION of an ini text (the section is added if missing).

    Args:
        text (str): File content.
        section (str): Section name without brackets.
        key (str): Key.
        value (str): Value.

    Returns:
        str: The new content.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "[%s]" % section), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["[%s]" % section, "%s=%s" % (key, value)]
        return "\n".join(lines) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    for i in range(start + 1, end):
        if lines[i].split("=", 1)[0].strip() == key:
            lines[i] = "%s=%s" % (key, value)
            break
    else:
        lines.insert(start + 1, "%s=%s" % (key, value))
    return "\n".join(lines) + "\n"


def ensure_quick_exec(profile=None, conf=None, system_dir="/etc/xdg/pcmanfm"):
    """
    Desktop icons start at a double-click, without the "Execute File" question.

    libfm asks "This text file ... seems to be an executable script. What do
    you want to do with it?" unless quick_exec=1. Trixie's pcmanfm-pi reads
    that from the profile's pcmanfm.conf only, not from libfm.conf where
    the image set it for bookworm, so every icon asked (T1). The person's
    pcmanfm.conf replaces the system one, so a new one starts as a copy of it.

    Args:
        profile (str): pcmanfm profile (default: the desktop's).
        conf (str): The person's pcmanfm.conf (tests).
        system_dir (str): /etc/xdg/pcmanfm (tests).

    Returns:
        bool: True if the file was written (pcmanfm must reload it).
    """
    profile = profile or pcmanfm_profile()
    conf = conf or pcmanfm_conf(profile)
    try:
        with open(conf, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        try:
            with open(os.path.join(system_dir, profile, "pcmanfm.conf"), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = ""
    else:
        if re.search(r"^quick_exec=1\s*$", text, re.M):
            return False
    new = set_ini_value(text, "config", "quick_exec", "1")
    try:
        os.makedirs(os.path.dirname(conf), exist_ok=True)
        with open(conf, "w", encoding="utf-8") as fh:
            fh.write(new)
    except OSError as exc:
        logger.warning("could not write %s: %s", conf, exc)
        return False
    return True


def label_height(conf=None):
    """
    Height of a two-line icon label in the desktop's font.

    Args:
        conf (str): desktop-items-0.conf (its [*] desktop_font).

    Returns:
        int: LABEL_HEIGHT for PibotoLt (bookworm), LABEL_HEIGHT_NUNITO else.
    """
    conf = conf or os.path.join(HOME, ".config/pcmanfm", pcmanfm_profile(), "desktop-items-0.conf")
    try:
        with open(conf, encoding="utf-8") as fh:
            font = _ini_value(fh.read(), "desktop_font") or ""
    except OSError:
        font = ""
    return LABEL_HEIGHT if "piboto" in font.lower() else LABEL_HEIGHT_NUNITO


def plan_layout(names, width, height, touch=False, icon=48, grid=None, panel=None,
                label=None, top=0):
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
        label (int): Height of a two-line label (default LABEL_HEIGHT).
        top (int): Added to every y: the panel height where pcmanfm counts
            from the top of the screen (trixie), 0 where it counts below
            the panel.

    Returns:
        tuple: (positions, overflow): positions maps a name (or MORE_DIR) to
        (x, y); overflow lists the names that go into the More folder.
    """
    panel = panel or (64 if touch else 36)
    min_grid = icon + 30
    grid = max(grid or (140 if touch else NORMAL_GRID), min_grid)
    cell_h = icon + (label or LABEL_HEIGHT)

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
        # the last column's labels end left of Chromium: they are wider
        # than the icons (touch mode: they ran under the browser, T5)
        def cols_left(g):
            return max(1, (CHROMIUM_X - MARGIN - max(g - 10, ITEM_WIDTH)) // g + 1)
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
        positions[name] = (MARGIN + (i % cols) * grid, top + MARGIN + (i // cols) * step_y(grid))
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
    # a removed catalogue demo's launcher, or one now in a group folder,
    # leaves no stale entry either
    kept = [s for s in sections if s.strip() and s.split("]", 1)[0][1:] not in ours
            and not s.startswith("[" + CATALOGUE_PREFIX) and not s.startswith("[" + GROUP_PREFIX)]
    out = "".join(s if s.endswith("\n") else s + "\n" for s in kept)
    for name, (x, y) in positions.items():
        key = name if name == MORE_DIR else name + ".desktop"
        out += "[%s]\nx=%d\ny=%d\ntrusted=true\n" % (key, x, y)
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write(out)


def sort_into_more(desktop, overflow, names=None):
    """
    Move the overflow launchers into Desktop/More and the rest back out.

    Only RasQberry's own launchers (ICON_ORDER) and catalogue launchers are
    moved; a copy on the desktop wins over one in the folder. An empty More
    folder is removed.

    Args:
        desktop (str): ~/Desktop.
        overflow (list): Names that go into the folder.
        names (list): The launchers laid out (default ICON_ORDER).
    """
    more = os.path.join(desktop, MORE_DIR)
    if overflow:
        os.makedirs(more, exist_ok=True)
    for name in dict.fromkeys(list(names or ICON_ORDER) + list(overflow)):
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


def present_launchers(desktop, root=None, groups=None):
    """
    List RasQberry's launchers on the desktop, in a group folder or in More.

    Args:
        desktop (str): ~/Desktop.
        root (str): group_dir() (default: none, as before the groups).
        groups (dict): load_groups() (its starters, system icons, launchers).

    Returns:
        list: Names in ICON_ORDER order, then catalogue launchers by name.
    """
    folders = [desktop, os.path.join(desktop, MORE_DIR)]
    if root:
        try:
            folders += [os.path.join(root, d) for d in sorted(os.listdir(root))]
        except OSError:
            pass
    known = list(ICON_ORDER)
    if groups:
        known += [n for n in groups["system"] + groups["starters"] + list(groups["launchers"])
                  if n not in known]
    found = [n for n in known
             if any(os.path.exists(os.path.join(f, n + ".desktop")) for f in folders)]
    extra = set()
    for folder in folders:
        try:
            entries = os.listdir(folder)
        except OSError:
            continue
        extra |= {f[:-len(".desktop")] for f in entries
                  if f.startswith(CATALOGUE_PREFIX) and f.endswith(".desktop")}
    return found + sorted(extra)


# --------------------------------------------------------------------------
# 4a. Demo groups
# --------------------------------------------------------------------------
def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load_groups(path=None):
    """
    Read demo-groups.json.

    Args:
        path (str): The file (default: next to the shipped manifests).

    Returns:
        dict: groups (list of {id, title, icon, ...}), starters, system and
        launchers; no groups when the file is missing or damaged (the desktop
        is then laid out flat, as before the groups).
    """
    data = _read_json(path or GROUPS_FILE)
    if not isinstance(data, dict):
        data = {}
    groups = [g for g in data.get("groups") or []
              if isinstance(g, dict) and re.match(r"^[a-z0-9][a-z0-9-]*$", str(g.get("id", "")))
              and g.get("title") and "/" not in g["title"]]
    return {"groups": groups,
            "starters": list(data.get("starters") or []),
            "system": list(data.get("system") or []),
            "last": list(data.get("last") or []),
            "launchers": dict(data.get("launchers") or {})}


def manifest_dirs(home=None):
    """
    The manifest search path: shipped, then the user's (catalogue demos).

    Args:
        home (str): Home directory (tests).

    Returns:
        list: Directories.
    """
    return [os.path.join(CONFIG_DIR, "demo-manifests"),
            os.path.join(home or HOME, ".local/config/demo-manifests")]


def find_manifest(demo_id, dirs=None):
    """
    Read a demo's manifest (rq_demo_<id>.json; the shipped one wins).

    Args:
        demo_id (str): Demo id.
        dirs (list): Manifest directories.

    Returns:
        dict: The manifest, or None.
    """
    for folder in dirs or manifest_dirs():
        data = _read_json(os.path.join(folder, "rq_demo_%s.json" % demo_id))
        if isinstance(data, dict):
            return data
    return None


def demo_group(demo_id, groups, dirs=None, known=None):
    """
    The group of a demo, decided like rq_demo_group in rq_common.sh.

    A catalogue demo (one in known-demos.json, or a manifest that is not
    shipped) goes to its known-demos.json entry's group (it is curated; an
    install under an earlier name, listed in an entry's "replaces", goes to
    that entry's group), else to the group marked "catalogue" (Contributed
    demos) - not to the group its own manifest names. A shipped demo goes to
    its manifest's "group", else a guess: an LED panel demo to led-panel, a
    game or visualization to play, anything else to learn. A value
    demo-groups.json does not list counts as none.

    Args:
        demo_id (str): Demo id.
        groups (dict): load_groups().
        dirs (list): Manifest directories, the shipped one first.
        known (str): known-demos.json.

    Returns:
        str: Group id, or None without groups.
    """
    ids = [g["id"] for g in groups["groups"]]
    if not ids:
        return None
    dirs = dirs or manifest_dirs()
    registry = _read_json(known or KNOWN_DEMOS) or {}
    manifest = find_manifest(demo_id, dirs)
    demos = [d for d in registry.get("demos") or [] if isinstance(d, dict)]
    entry = ([d for d in demos if d.get("id") == demo_id]
             + [d for d in demos if demo_id in (d.get("replaces") or [])])
    for group in (d.get("group") for d in entry):
        if group in ids:
            return group
    shipped = os.path.isfile(os.path.join(dirs[0], "rq_demo_%s.json" % demo_id)) or manifest is None
    catalogue = next((g["id"] for g in groups["groups"] if g.get("catalogue") is True), None)
    if (entry or not shipped) and catalogue:
        return catalogue
    manifest = manifest or {}
    if manifest.get("group") in ids:
        return manifest["group"]
    if (manifest.get("needs_hw") or {}).get("leds") is True:
        guess = "led-panel"
    elif manifest.get("category") in ("game", "visualization"):
        guess = "play"
    else:
        guess = "learn"
    return guess if guess in ids else ids[0]


def launcher_demo(path):
    """
    The demo a launcher starts: rq_demo_run.sh/rq_demo_choose.sh <id> in Exec.

    Args:
        path (str): The .desktop file.

    Returns:
        str: Demo id, or None.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"^Exec=.*\brq_demo_(?:run|choose)\.sh\s+([a-z0-9][a-z0-9-]*)", text, re.M)
    return m.group(1) if m else None


def launcher_group(name, path, groups, dirs=None, known=None):
    """
    The group folder a launcher goes into.

    Catalogue launchers (rq-ext-<id>) and launchers that start a demo take the
    demo's group; demo-groups.json names the few without a manifest (Demo
    Loop, My Quantum Programs). System icons have none.

    Args:
        name (str): Launcher name without ".desktop".
        path (str): Its file.
        groups (dict): load_groups().
        dirs (list): Manifest directories.
        known (str): known-demos.json.

    Returns:
        str: Group id, or None (stays on the desktop).
    """
    ids = [g["id"] for g in groups["groups"]]
    if not ids or name in groups["system"]:
        return None
    if name.startswith(CATALOGUE_PREFIX):
        return demo_group(name[len(CATALOGUE_PREFIX):], groups, dirs, known)
    if name in groups["launchers"]:
        group = groups["launchers"][name]
        return group if group in ids else None
    demo = launcher_demo(path)
    if not demo and find_manifest(name, dirs):
        demo = name
    return demo_group(demo, groups, dirs, known) if demo else None


def group_dir(home=None):
    """
    Where the group folders are (out of sight; their launchers open them).

    Args:
        home (str): Home directory (tests).

    Returns:
        str: ~/.local/share/rasqberry/desktop-groups.
    """
    return os.path.join(home or HOME, ".local/share/rasqberry/desktop-groups")


def group_folder(group, root=None):
    """
    A group's folder: named by its title (the file manager shows it, the
    group's window is titled the same).

    Args:
        group (dict): One entry of load_groups()["groups"].
        root (str): group_dir().

    Returns:
        str: Path.
    """
    return os.path.join(root or group_dir(), group["title"])


def group_launcher_text(group, exe=None, icon_dir=ICON_DIR):
    """
    The desktop launcher of a group: its icon opens the group's window.

    Args:
        group (dict): One entry of load_groups()["groups"].
        exe (str): This script (default: where it is installed).
        icon_dir (str): Where the group icons are installed.

    Returns:
        str: .desktop file content.
    """
    icon = os.path.join(icon_dir, group.get("icon") or "")
    if not group.get("icon") or not os.path.isfile(icon):
        icon = "folder"
    lines = ["[Desktop Entry]", "Type=Application", "Name=%s" % group["title"]]
    if group.get("description"):
        lines.append("Comment=%s" % group["description"])
    lines += ["Icon=%s" % icon,
              "Exec=%s --open-group %s" % (exe or os.path.abspath(__file__), group["id"]),
              "Terminal=false"]
    return "\n".join(lines) + "\n"


def ensure_group_launchers(desktop, groups, exe=None, icon_dir=ICON_DIR):
    """
    Write one launcher per group on the desktop; remove those of old groups.

    Written as a hidden file and renamed into place: pcmanfm reads a launcher
    once, when it appears, so it must appear complete.

    Args:
        desktop (str): ~/Desktop.
        groups (dict): load_groups().
        exe (str): This script (tests).
        icon_dir (str): Group icons (tests).

    Returns:
        bool: True if a launcher was written or removed.
    """
    changed = False
    wanted = set()
    for group in groups["groups"]:
        name = GROUP_PREFIX + group["id"] + ".desktop"
        wanted.add(name)
        path = os.path.join(desktop, name)
        text = group_launcher_text(group, exe, icon_dir)
        try:
            with open(path, encoding="utf-8") as fh:
                if fh.read() == text:
                    continue
        except OSError:
            pass
        os.makedirs(desktop, exist_ok=True)
        tmp = os.path.join(desktop, "." + name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o755)
        os.replace(tmp, path)
        changed = True
    try:
        entries = os.listdir(desktop)
    except OSError:
        entries = []
    for name in entries:
        if name.startswith(GROUP_PREFIX) and name.endswith(".desktop") and name not in wanted:
            os.remove(os.path.join(desktop, name))
            changed = True
    return changed


def _launcher_copies(name, desktop, root):
    """All copies of a launcher: on the desktop, in group folders, in More."""
    fname = name + ".desktop"
    places = [desktop]
    try:
        places += [os.path.join(root, d) for d in sorted(os.listdir(root))]
    except OSError:
        pass
    places.append(os.path.join(desktop, MORE_DIR))
    return [os.path.join(p, fname) for p in places if os.path.isfile(os.path.join(p, fname))]


def sort_into_groups(desktop, assignment, on_desktop, groups, root=None):
    """
    Put each launcher into its group's folder, and on the desktop if it stays there.

    A copy on the desktop (e.g. reinstalled) wins over the folder's. A
    launcher that is no longer on the desktop is only in its folder; starters
    are in both. Copies elsewhere (another group's folder, the More folder of
    older desktops) are removed, and so are empty folders of old groups and
    an empty More folder.

    Args:
        desktop (str): ~/Desktop.
        assignment (dict): Launcher name -> group id (None: no folder).
        on_desktop (set): Names that stay on the desktop.
        groups (dict): load_groups().
        root (str): group_dir().
    """
    root = root or group_dir()
    folders = {g["id"]: group_folder(g, root) for g in groups["groups"]}
    for folder in folders.values():
        os.makedirs(folder, exist_ok=True)
    for name, gid in assignment.items():
        fname = name + ".desktop"
        copies = _launcher_copies(name, desktop, root)
        if not copies:
            continue
        on_desk = os.path.join(desktop, fname)
        target = os.path.join(folders[gid], fname) if gid in folders else None
        source = on_desk if on_desk in copies else (target if target in copies else copies[0])
        if target and source != target:
            shutil.copy2(source, target)
        if name in on_desktop or not target:
            if source != on_desk:
                shutil.copy2(source, on_desk)
        elif os.path.exists(on_desk):
            os.remove(on_desk)
        for path in copies:
            if path not in (on_desk, target) and os.path.exists(path):
                os.remove(path)
    stale = [os.path.join(desktop, MORE_DIR)]
    try:
        stale += [os.path.join(root, d) for d in os.listdir(root)
                  if os.path.join(root, d) not in folders.values()]
    except OSError:
        pass
    for folder in stale:
        try:
            os.rmdir(folder)  # only when empty
        except OSError:
            pass


def desktop_order(names, assignment, groups):
    """
    The icons left on the desktop, in their order: the system icons, the
    starters, one per group, any other launcher without a group, and last
    the "last" ones (RasQberry Setup, a temporary icon).

    Args:
        names (list): Launchers present (present_launchers).
        assignment (dict): Launcher name -> group id.
        groups (dict): load_groups().

    Returns:
        list: Names (group launchers as rq-group-<id>).
    """
    present = set(names)
    last = [n for n in groups.get("last", []) if n in present]
    order = [n for n in groups["system"] if n in present and n not in last]
    order += [n for n in groups["starters"] if n in present and n not in order + last]
    order += [GROUP_PREFIX + g["id"] for g in groups["groups"]]
    order += [n for n in names if assignment.get(n) is None and n not in order + last]
    return order + last


def setup_done(home=None):
    """
    Tell whether the setup checklist is done (its mark, rq_firstlogin.sh).

    Args:
        home (str): Home directory (default: this user's; XDG_STATE_HOME
            counts there, as in the checklist).

    Returns:
        bool: True if the mark exists.
    """
    if home is None or os.path.abspath(home) == os.path.abspath(HOME):
        state = os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local/state")
        return os.path.exists(os.path.join(state, "rasqberry", "setup-done"))
    return os.path.exists(os.path.join(home, SETUP_DONE))


def place_conditional_launchers(desktop, shown, hidden=None):
    """
    Put launchers that come and go on the desktop, or away.

    A launcher that should not show moves to HIDDEN_DIR; one that should
    comes back from there. A launcher in neither place (the person deleted
    it) stays deleted.

    Args:
        desktop (str): ~/Desktop.
        shown (dict): Launcher name -> whether it belongs on the desktop.
        hidden (str): Where they wait (default: HIDDEN_DIR in the home the
            desktop belongs to).

    Returns:
        bool: True if a launcher moved.
    """
    hidden = hidden or os.path.join(os.path.dirname(os.path.abspath(desktop)), HIDDEN_DIR)
    changed = False
    for name, show in shown.items():
        fname = name + ".desktop"
        on_desk, away = os.path.join(desktop, fname), os.path.join(hidden, fname)
        # (older small-screen desktops kept it in the More folder)
        present = [p for p in (on_desk, os.path.join(desktop, MORE_DIR, fname)) if os.path.exists(p)]
        if show and not present and os.path.exists(away):
            os.replace(away, on_desk)
            changed = True
        elif not show and present:
            os.makedirs(hidden, exist_ok=True)
            os.replace(present[0], away)
            for path in present[1:]:
                os.remove(path)
            changed = True
    return changed


def place_touchscreen_launchers(desktop, touchscreen, hidden=None):
    """
    Put the touchscreen-only launchers (Touch Mode) on the desktop or away.

    Args:
        desktop (str): ~/Desktop.
        touchscreen (bool): A touchscreen is connected.
        hidden (str): Where they wait (tests).

    Returns:
        bool: True if a launcher moved.
    """
    return place_conditional_launchers(desktop, {n: touchscreen for n in TOUCHSCREEN_ONLY}, hidden)


def group_window_script():
    """rq_group_window.py next to this script, or None."""
    path = os.path.join(_HERE, "rq_group_window.py")
    return path if os.path.isfile(path) else None


def open_group(gid, groups=None, root=None, window=None):
    """
    Open a group's window (the group icon's command): its demos as icons,
    rq_group_window.py; without that script the folder in the file manager.

    Args:
        gid (str): Group id.
        groups (dict): load_groups().
        root (str): group_dir().

    Returns:
        int: 1 for an unknown group; otherwise it does not return.
    """
    groups = groups or load_groups()
    group = next((g for g in groups["groups"] if g["id"] == gid), None)
    if not group:
        logger.warning("unknown demo group: %s", gid)
        return 1
    folder = group_folder(group, root)
    os.makedirs(folder, exist_ok=True)
    window = group_window_script() if window is None else window
    if window:
        # it opens the folder in pcmanfm itself when GTK is missing
        os.execv(sys.executable, [sys.executable, window, gid])
    os.execvp("pcmanfm", ["pcmanfm", folder])
    return 0


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


def layout_top(touch, profile=None):
    """
    What every icon's y gets added: the panel where pcmanfm counts from the top.

    Args:
        touch (bool): Touch mode (a taller panel).
        profile (str): pcmanfm profile (default: the desktop's).

    Returns:
        int: Pixels.
    """
    if (profile or pcmanfm_profile()) in SCREEN_POSITION_PROFILES:
        return 64 if touch else 36
    return 0


def layout_desktop(size, touch, desktop=None, conf=None, record=None, force=False,
                   root=None, groups=None, dirs=None, known=None, exe=None, icon_dir=ICON_DIR,
                   touchscreen=None, setup=None):
    """
    Sort the launchers into their group folders and lay the desktop out, when
    the screen, touch mode or the icon set changed.

    Args:
        size (tuple): (width, height).
        touch (bool): Touch mode.
        desktop (str): ~/Desktop.
        conf (str): pcmanfm desktop-items-0.conf.
        record (str): File remembering what the last layout was made for.
        force (bool): Lay out even if nothing changed.
        root (str): group_dir() (tests).
        groups (dict): load_groups() (tests).
        dirs (list): Manifest directories (tests).
        known (str): known-demos.json (tests).
        exe (str): This script, for the group launchers (tests).
        icon_dir (str): Group icons (tests).
        touchscreen (bool): A touchscreen is connected (default: ask udev);
            without one the Touch Mode icon leaves the desktop.
        setup (bool): The setup checklist is done (default: its mark); then
            the RasQberry Setup icon leaves the desktop.

    Returns:
        bool: True if the desktop changed (pcmanfm must reload).
    """
    desktop = desktop or os.path.join(HOME, "Desktop")
    # the home the desktop belongs to
    root = root or group_dir(os.path.dirname(os.path.abspath(desktop)))
    groups = groups if groups is not None else load_groups()
    profile = pcmanfm_profile()
    conf = conf or os.path.join(HOME, ".config/pcmanfm", profile, "desktop-items-0.conf")
    record = record or os.path.join(HOME, ".config/rasqberry/desktop-layout")
    changed = ensure_group_launchers(desktop, groups, exe, icon_dir) if groups["groups"] else False
    touchscreen = has_touchscreen() if touchscreen is None else touchscreen
    home = os.path.dirname(os.path.abspath(desktop))
    setup = setup_done(home) if setup is None else setup
    shown = {n: touchscreen for n in TOUCHSCREEN_ONLY}
    shown[SETUP_LAUNCHER] = not setup
    changed = place_conditional_launchers(desktop, shown) or changed
    names = present_launchers(desktop, root, groups)
    assignment = {}
    for name in names:
        copies = _launcher_copies(name, desktop, root)
        assignment[name] = launcher_group(name, copies[0] if copies else "", groups, dirs, known)
    top = desktop_order(names, assignment, groups) if groups["groups"] else list(names)
    icon = libfm_icon_size()
    label = label_height(conf)
    offset = layout_top(touch, profile)
    key = json.dumps({"screen": list(size), "touch": touch, "icon": icon, "icons": top,
                      "groups": assignment, "label": label, "top": offset})
    try:
        with open(record, encoding="utf-8") as fh:
            if fh.read().strip() == key and not force:
                return changed
    except OSError:
        pass
    spacing = env_value("TOUCH_DESKTOP_GRID_SPACING", "140")
    grid = (int(spacing) if spacing.isdigit() else 140) if touch else None

    def plan(names_):
        return plan_layout(names_, size[0], size[1], touch=touch, icon=icon, grid=grid,
                           label=label, top=offset)

    positions, overflow = plan(top)
    # too small for all: the starters leave the desktop first (they are in
    # their folders), the last one first
    droppable = [n for n in reversed(groups["starters"]) if n in top and assignment.get(n)]
    while overflow and droppable:
        top.remove(droppable.pop(0))
        positions, overflow = plan(top)
    if groups["groups"]:
        sort_into_groups(desktop, assignment, set(top), groups, root)
    sort_into_more(desktop, overflow, top)
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


DEMO_LOOP_CMD = ["/usr/bin/rq_hold_on_error.sh", "-t", "Demo Loop",
                 "/usr/bin/rq_demo_loop.sh", "--at-login"]


def start_demo_loop(terminal=None):
    """
    Start the Demo Loop in a terminal window if DEMO_LOOP_AT_LOGIN=true.

    The terminal is the one desktop launchers use (x-terminal-emulator -e).
    The loop asks nothing at login: demos not on this Pi are left out.

    Args:
        terminal (list): Terminal command line before the loop's.

    Returns:
        bool: True if the loop was started (then the browser is not).
    """
    if env_value("DEMO_LOOP_AT_LOGIN", "false") != "true":
        return False
    time.sleep(int(os.environ.get("RQ_LOOP_DELAY", "10")))  # LED driver, desktop
    cmd = list(terminal or ["x-terminal-emulator", "-e"]) + DEMO_LOOP_CMD
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as exc:
        logger.warning("could not start the Demo Loop: %s", exc)
        return False
    return True


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
        touch = "--touch" in argv
        # the desktop the first login sorts the launchers into
        groups = load_groups()
        names = ICON_ORDER
        if groups["groups"]:
            names = desktop_order(list(dict.fromkeys(groups["system"] + groups["starters"])),
                                  {}, groups)
        positions, _ = plan_layout(names, w, h, touch=touch, label=label_height(argv[2]),
                                   top=layout_top(touch))
        write_positions(argv[2], positions)
        return 0
    if argv[:1] == ["--open-group"] and len(argv) > 1:
        return open_group(argv[1])
    if argv[:1] == ["--touchscreen"]:
        return 0 if has_touchscreen() else 1
    if argv[:1] == ["--quick-exec"]:
        # the image build (CONF given) and the first login: no "Execute File"
        ensure_quick_exec(conf=argv[1] if len(argv) > 1 else None)
        return 0
    if argv[:1] == ["--relayout"]:
        # a catalogue demo added or removed its launcher: into the grid now
        size = screen_size()
        if size and layout_desktop(size, touch_mode_on()):
            run_quietly(["pcmanfm", "--reconfigure"])
        return 0
    reset_chromium_exit()
    touch = touch_mode_on()
    apply_touch_css(touch)
    size = screen_size()
    small = bool(size and is_small(size))
    set_small_screen_flag(small)
    reload_pcmanfm = ensure_quick_exec()
    if size:
        if set_chromium_rule(small) and os.environ.get("LABWC_PID"):
            run_quietly(["labwc", "--reconfigure"])
        reload_pcmanfm = layout_desktop(size, touch) or reload_pcmanfm
    if reload_pcmanfm:
        run_quietly(["pcmanfm", "--reconfigure"])
    if "--no-browser" not in argv:
        # a stand: the Demo Loop instead of the browser (R-123)
        if not start_demo_loop():
            start_browser(small)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
