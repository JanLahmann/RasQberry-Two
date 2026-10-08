#!/usr/bin/env python3
"""
RasQberry Two: the window of a demo group (its desktop icon opens it).

A demo group's desktop icon (rq-group-<id>.desktop, written by
rq_desktop_session.py) used to open the group's folder in the file manager:
a window with a menu bar, a path bar showing ~/.local/share/rasqberry/...,
a tree of the whole file system and a status bar. This window shows only
what matters: the group's title and one-line description, and its demos as
large icons with their names (Jan, 2026-10-08). The file manager's own
settings stay as they are.

- The icons are the launchers in the group's folder
  (~/.local/share/rasqberry/desktop-groups/<Title>/), so demos added from
  the catalogue show up by themselves. Launchers with NoDisplay=true or
  Hidden=true, or whose TryExec program is missing, are left out.
- Order as in the group's RasQberry menu: My Quantum Programs first, then by
  the demo manifest's menu.order, Clear All LEDs and Demo Loop last.
- One click or tap starts a demo, the same way a double-click on the desktop
  does: the launcher's Exec line in the desktop's environment, in the home
  folder, Terminal=true launchers in the terminal libfm.conf names
  ("x-terminal-emulator -e ..."). The window then closes, like a menu.
- Keyboard: arrow keys, Enter or Space starts, typing a name's first letters
  selects it, Esc closes.
- One window per group: clicking the group's icon again brings the open
  window back to the front (and reads the folder again).
- Touch mode: bigger icons.
- Without GTK (or without a display) the folder opens in the file manager,
  as before.

Usage:
    rq_group_window.py GROUP_ID          open the window (the group icon's command)
    rq_group_window.py --list GROUP_ID   print the launchers it would show
                                         (name, then the command; rig tests)
"""

import logging
import os
import re
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rq_desktop_session as ds  # noqa: E402

logging.basicConfig(level=logging.INFO, format="rq_group_window: %(message)s")
logger = logging.getLogger(__name__)

# Order inside a group, as in its RasQberry menu (do_demo_group_menu)
FIRST = ("my-quantum-programs",)
LAST = ("clear-leds", "demo-loop")
DEFAULT_ORDER = 50
ICON_SIZE, TOUCH_ICON_SIZE = 64, 96
# Where libfm (the desktop's file manager) reads its terminal
LIBFM_CONFS = ("~/.config/libfm/libfm.conf", "/etc/xdg/libfm/libfm.conf")
DEFAULT_TERMINAL = "x-terminal-emulator"
# The selected icon: a light tint, the name stays readable (the theme's own
# selection colour made it light grey on grey)
CSS = b"""
flowbox flowboxchild { border-radius: 10px; }
flowbox flowboxchild:hover { background-color: alpha(@theme_selected_bg_color, 0.12); }
flowbox flowboxchild:selected { background-color: alpha(@theme_selected_bg_color, 0.28);
                                color: @theme_fg_color; }
"""
# Field codes of the Desktop Entry spec that expand to files or URLs: a
# launcher started without any expands them to nothing
_FILE_CODES = ("%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N", "%v", "%m")


# --------------------------------------------------------------------------
# Launchers
# --------------------------------------------------------------------------
def _unescape(value):
    """Undo the Desktop Entry string escapes (\\s \\n \\t \\r \\\\)."""
    out, i = [], 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            out.append({"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(value[i + 1],
                                                                             "\\" + value[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_desktop_file(path):
    """
    Read the [Desktop Entry] group of a .desktop file.

    Localised keys (Name[de]=...) are skipped: the desktop shows the plain
    ones too.

    Args:
        path (str): The .desktop file.

    Returns:
        dict: key -> value, or None when the file cannot be read or has no
        [Desktop Entry] group.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    entry, group = None, None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
            if group == "Desktop Entry" and entry is None:
                entry = {}
            continue
        if group != "Desktop Entry" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if "[" in key:
            continue
        entry.setdefault(key, _unescape(value.strip()))
    return entry


def _true(value):
    return str(value).strip().lower() == "true"


def _program_exists(prog, which=shutil.which):
    # (shutil.which checks a path with a directory as it is)
    return which(prog) is not None


def entry_shown(entry, which=shutil.which):
    """
    Tell whether a launcher belongs in the window.

    Args:
        entry (dict): parse_desktop_file().
        which (callable): shutil.which (tests).

    Returns:
        bool: True for an application with a name and a command, not
        NoDisplay, not Hidden, and its TryExec program (if any) present.
    """
    if not entry or entry.get("Type", "Application") != "Application":
        return False
    if not entry.get("Name") or not entry.get("Exec"):
        return False
    if _true(entry.get("NoDisplay")) or _true(entry.get("Hidden")):
        return False
    if entry.get("TryExec") and not _program_exists(entry["TryExec"], which):
        return False
    return True


def exec_argv(entry, path=""):
    """
    The command of a launcher as an argument list.

    Quoting as a shell does (libfm and GLib parse it with g_shell_parse_argv);
    the Desktop Entry field codes are expanded for a launch without files.

    Args:
        entry (dict): parse_desktop_file().
        path (str): The .desktop file (%k).

    Returns:
        list: Arguments, empty when the line cannot be parsed.
    """
    try:
        words = shlex.split(entry.get("Exec", ""))
    except ValueError:
        return []
    argv = []
    for word in words:
        if word in _FILE_CODES:
            continue
        if word == "%i":
            if entry.get("Icon"):
                argv += ["--icon", entry["Icon"]]
            continue
        word = re.sub(r"%[fFuUdDnNvm]", "", word)
        word = word.replace("%c", entry.get("Name", "")).replace("%k", path)
        argv.append(word.replace("%%", "%"))
    return argv


def terminal_command(confs=None, home=None):
    """
    The terminal libfm starts Terminal=true launchers in, with its -e.

    The desktop's double-click runs "x-terminal-emulator -e <command>"
    (libfm.conf: terminal=x-terminal-emulator %s), measured on the Pi.

    Args:
        confs (list): libfm.conf files, the person's first.
        home (str): Home directory for "~" (tests).

    Returns:
        list: e.g. ["x-terminal-emulator", "-e"].
    """
    for conf in confs or LIBFM_CONFS:
        if conf.startswith("~"):
            conf = os.path.join(home or ds.HOME, conf[2:])
        try:
            with open(conf, encoding="utf-8") as fh:
                m = re.search(r"^terminal=(.+)$", fh.read(), re.M)
        except OSError:
            continue
        if m:
            try:
                words = shlex.split(m.group(1))
            except ValueError:
                words = []
            if words:
                return [words[0], "-e"]
    return [DEFAULT_TERMINAL, "-e"]


def launch_argv(launcher, terminal=None):
    """
    What starting a launcher runs.

    Args:
        launcher (dict): One of list_launchers().
        terminal (list): terminal_command().

    Returns:
        list: Arguments.
    """
    argv = list(launcher["argv"])
    if launcher["terminal"] and argv:
        argv = list(terminal or terminal_command()) + argv
    return argv


def _sort_key(launcher, dirs=None):
    name = launcher["id"]
    rank = 0 if name in FIRST else 2 if name in LAST else 1
    demo = ds.launcher_demo(launcher["path"])
    if not demo and name.startswith(ds.CATALOGUE_PREFIX):
        demo = name[len(ds.CATALOGUE_PREFIX):]
    elif not demo:
        demo = name   # a launcher named like its manifest (composer)
    order = DEFAULT_ORDER
    manifest = ds.find_manifest(demo, dirs) if demo else None
    if manifest:
        value = (manifest.get("menu") or {}).get("order")
        if isinstance(value, (int, float)):
            order = value
    return (rank, order, launcher["name"].lower())


def list_launchers(folder, dirs=None, which=shutil.which):
    """
    The launchers a group's window shows, in its order.

    Args:
        folder (str): The group's folder.
        dirs (list): Manifest directories (tests).
        which (callable): shutil.which (tests).

    Returns:
        list: dicts with id, path, name, comment, icon, argv, terminal, cwd.
    """
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for fname in names:
        if not fname.endswith(".desktop") or fname.startswith("."):
            continue
        path = os.path.join(folder, fname)
        entry = parse_desktop_file(path)
        if not entry_shown(entry, which):
            continue
        argv = exec_argv(entry, path)
        if not argv:
            continue
        out.append({"id": fname[:-len(".desktop")], "path": path, "name": entry["Name"],
                    "comment": entry.get("Comment", ""), "icon": entry.get("Icon", ""),
                    "argv": argv, "terminal": _true(entry.get("Terminal")),
                    "cwd": entry.get("Path") or ""})
    out.sort(key=lambda launcher: _sort_key(launcher, dirs))
    return out


def launch(launcher, terminal=None, home=None, popen=subprocess.Popen):
    """
    Start a launcher as the desktop's double-click does.

    It runs in this process's environment (the desktop's: the group icon was
    started by it) and in the home folder (or the launcher's Path). It gets a
    session of its own, so it keeps running when the window closes.

    Args:
        launcher (dict): One of list_launchers().
        terminal (list): terminal_command().
        home (str): Working directory without Path (tests).
        popen (callable): subprocess.Popen (tests).

    Returns:
        bool: True if it was started.
    """
    argv = launch_argv(launcher, terminal)
    cwd = launcher.get("cwd") or home or ds.HOME
    if not os.path.isdir(cwd):
        cwd = home or ds.HOME
    try:
        popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        logger.warning("could not start %s: %s", launcher["path"], exc)
        return False
    return True


# --------------------------------------------------------------------------
# Window size
# --------------------------------------------------------------------------
def icon_size(touch):
    """Icon size in the window: bigger in touch mode."""
    return TOUCH_ICON_SIZE if touch else ICON_SIZE


def cell_width(touch):
    """Width of one icon with its label (two lines of about 14 characters)."""
    return icon_size(touch) + (84 if touch else 64)


def columns(count, screen_width=None, touch=False):
    """
    Columns of the icon grid: a compact block, at most 2/3 of the screen wide.

    Args:
        count (int): Icons.
        screen_width (int): Screen width (None: unknown).
        touch (bool): Touch mode.

    Returns:
        int: 1 to 4 for up to 4 icons, 3 for 5 or 6, else 4; fewer when the
        screen is narrow.
    """
    if count <= 4:
        cols = max(count, 1)
    elif count <= 6:
        cols = 3
    else:
        cols = 4
    if screen_width:
        fit = max(1, (screen_width * 2 // 3 - 40) // (cell_width(touch) + 8))
        cols = min(cols, fit)
    return cols


def app_id(gid):
    """The window's application id: one window per group (D-Bus name)."""
    return "org.rasqberry.DemoGroup." + re.sub(r"[^A-Za-z0-9_]", "_", gid)


# --------------------------------------------------------------------------
# GTK
# --------------------------------------------------------------------------
def load_gtk():
    """
    GTK 3 through python3-gi, with a display.

    Returns:
        tuple: (Gtk, Gdk, Gio, GLib, GdkPixbuf, Pango), or None without GTK or a
        display.
    """
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        gi.require_version("Pango", "1.0")
        from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango
    except (ImportError, ValueError) as exc:
        logger.warning("no GTK (%s): opening the folder instead", exc)
        return None
    ok = Gtk.init_check(sys.argv)
    if isinstance(ok, tuple):
        ok = ok[0]
    if not ok:
        logger.warning("no display: opening the folder instead")
        return None
    return Gtk, Gdk, Gio, GLib, GdkPixbuf, Pango


class GroupWindow:
    """One group's window, inside a Gtk.Application (one per group)."""

    def __init__(self, gtk, group, folder, touch, icon_dir=ds.ICON_DIR):
        self.Gtk, self.Gdk, self.Gio, self.GLib, self.GdkPixbuf, self.Pango = gtk
        self.group, self.folder, self.touch, self.icon_dir = group, folder, touch, icon_dir
        self.window = None
        self.flow = None
        self.scroll = None
        self.launchers = []
        self.typed, self.typed_at = "", 0
        self.terminal = terminal_command()
        self.app = self.Gtk.Application(application_id=app_id(group["id"]),
                                        flags=self.Gio.ApplicationFlags.FLAGS_NONE)
        self.app.connect("activate", self.on_activate)

    def run(self):
        """Run until the window closes; a second start raises the first."""
        return self.app.run([sys.argv[0]])

    # -- building ----------------------------------------------------------------
    def screen_size(self):
        display = self.Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0) if display else None
        if not monitor:
            return None
        geo = monitor.get_geometry()
        return geo.width, geo.height

    def icon_pixbuf(self, icon, size):
        """A launcher's icon: a file, or a name in the icon theme."""
        Gtk, GdkPixbuf, GLib = self.Gtk, self.GdkPixbuf, self.GLib
        if icon and os.path.isabs(icon):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(icon, size, size, True)
            except GLib.Error:
                icon = ""
        theme = Gtk.IconTheme.get_default()
        for name in (icon, "application-x-executable", "image-missing"):
            if not name:
                continue
            name = re.sub(r"\.(png|svg|xpm)$", "", name)
            try:
                pixbuf = theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except GLib.Error:
                continue
            if pixbuf:
                return pixbuf
        return None

    def build(self):
        """The window: title, description, the icon grid."""
        Gtk = self.Gtk
        css = Gtk.CssProvider()
        try:
            css.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_screen(self.Gdk.Screen.get_default(), css,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except self.GLib.Error as exc:
            logger.warning("style: %s", exc)
        win = Gtk.ApplicationWindow(application=self.app, title=self.group["title"])
        win.set_position(Gtk.WindowPosition.CENTER)
        win.set_resizable(False)
        icon_file = os.path.join(self.icon_dir, self.group.get("icon") or "")
        try:
            if self.group.get("icon") and os.path.isfile(icon_file):
                win.set_icon_from_file(icon_file)
            else:
                win.set_icon_name("folder")
        except self.GLib.Error:
            win.set_icon_name("folder")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(18)
        win.add(box)
        title = Gtk.Label(xalign=0)
        title.set_markup("<span size='x-large' weight='bold'>%s</span>"
                         % self.GLib.markup_escape_text(self.group["title"]))
        box.pack_start(title, False, False, 0)
        if self.group.get("description"):
            desc = Gtk.Label(label=self.group["description"], xalign=0)
            desc.set_line_wrap(True)
            desc.set_max_width_chars(48)
            desc.get_style_context().add_class("dim-label")
            box.pack_start(desc, False, False, 0)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_propagate_natural_height(True)
        self.scroll.set_propagate_natural_width(True)
        self.scroll.set_margin_top(12)
        box.pack_start(self.scroll, True, True, 0)
        win.connect("key-press-event", self.on_key)
        self.window = win
        self.fill()
        win.show_all()

    def fill(self):
        """(Re)read the folder and put its launchers into the grid."""
        Gtk = self.Gtk
        self.launchers = list_launchers(self.folder)
        old = self.scroll.get_child()
        if old is not None:
            self.scroll.remove(old)
        size = self.screen_size()
        cols = columns(len(self.launchers), size[0] if size else None, self.touch)
        if size:
            # at most 2/3 of the screen high; the grid scrolls beyond that
            self.scroll.set_max_content_height(max(200, size[1] * 2 // 3 - 120))
        if not self.launchers:
            empty = Gtk.Label(label="No demos in this group yet.\nMore demos: RasQberry "
                                    "Configuration > Quantum Demos > Manage demos.")
            empty.set_justify(Gtk.Justification.CENTER)
            self.scroll.add(empty)
            self.flow = None
            return
        flow = Gtk.FlowBox()
        flow.set_homogeneous(True)
        flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flow.set_activate_on_single_click(True)
        flow.set_min_children_per_line(cols)
        flow.set_max_children_per_line(cols)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)
        flow.connect("child-activated", self.on_activated)
        isize = icon_size(self.touch)
        for launcher in self.launchers:
            item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            item.set_border_width(8)
            item.set_size_request(cell_width(self.touch), -1)
            pixbuf = self.icon_pixbuf(launcher["icon"], isize)
            image = Gtk.Image.new_from_pixbuf(pixbuf) if pixbuf else Gtk.Image()
            image.set_size_request(isize, isize)
            item.pack_start(image, False, False, 0)
            label = Gtk.Label(label=launcher["name"])
            label.set_justify(Gtk.Justification.CENTER)
            label.set_line_wrap(True)
            label.set_max_width_chars(14 if not self.touch else 15)
            label.set_lines(2)
            label.set_ellipsize(self.Pango.EllipsizeMode.END)
            item.pack_start(label, False, False, 0)
            child = Gtk.FlowBoxChild()
            child.add(item)
            if launcher["comment"]:
                child.set_tooltip_text(launcher["comment"])
            flow.add(child)
        self.scroll.add(flow)
        self.flow = flow
        first = flow.get_child_at_index(0)
        flow.select_child(first)
        first.grab_focus()

    # -- events --------------------------------------------------------------------
    def on_activate(self, _app):
        if self.window is None:
            self.build()
            return
        # the group's icon again: read the folder again, to the front. labwc
        # does not raise a window that asks without an activation token (the
        # desktop's launch gives none), but it puts a newly shown window on
        # top: hide it and show it again
        self.window.hide()
        self.fill()
        self.window.show_all()
        self.window.present()

    def on_activated(self, _flow, child):
        launcher = self.launchers[child.get_index()]
        if launch(launcher, self.terminal):
            # like a menu: the window has done its job
            self.window.destroy()
        else:
            dialog = self.Gtk.MessageDialog(transient_for=self.window, modal=True,
                                            message_type=self.Gtk.MessageType.ERROR,
                                            buttons=self.Gtk.ButtonsType.CLOSE,
                                            text="%s could not be started." % launcher["name"])
            dialog.run()
            dialog.destroy()

    def on_key(self, _win, event):
        Gdk = self.Gdk
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()
            return True
        if event.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK):
            return False
        ch = chr(Gdk.keyval_to_unicode(event.keyval) or 0)
        if not self.flow or not ch.isprintable() or not ch.strip() and not self.typed:
            return False
        # type-ahead: the first demo whose name starts with what was typed
        if event.time - self.typed_at > 1000:
            self.typed = ""
        self.typed_at = event.time
        self.typed += ch.lower()
        for i, launcher in enumerate(self.launchers):
            if launcher["name"].lower().startswith(self.typed):
                child = self.flow.get_child_at_index(i)
                self.flow.select_child(child)
                child.grab_focus()
                break
        return True


def find_group(gid, groups=None):
    """The group with this id in demo-groups.json, or None."""
    groups = groups or ds.load_groups()
    return next((g for g in groups["groups"] if g["id"] == gid), None)


def open_folder(folder):
    """The fallback: the folder in the file manager (does not return)."""
    os.execvp("pcmanfm", ["pcmanfm", folder])


def main(argv):
    """
    Open a group's window, or list its launchers.

    Args:
        argv (list): Command-line arguments.

    Returns:
        int: Exit status.
    """
    listing = argv[:1] == ["--list"]
    if listing:
        argv = argv[1:]
    if len(argv) != 1:
        print(__doc__.strip().split("Usage:")[1], file=sys.stderr)
        return 2
    group = find_group(argv[0])
    if not group:
        logger.warning("unknown demo group: %s", argv[0])
        return 1
    folder = ds.group_folder(group)
    if listing:
        for launcher in list_launchers(folder):
            print("%s\t%s" % (launcher["name"], " ".join(shlex.quote(a) for a in launch_argv(launcher))))
        return 0
    os.makedirs(folder, exist_ok=True)
    gtk = load_gtk()
    if gtk is None:
        open_folder(folder)
        return 0
    return GroupWindow(gtk, group, folder, ds.touch_mode_on()).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
