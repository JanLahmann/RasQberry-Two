#!/usr/bin/env python3
"""
RasQberry: A/B slot indicator in the taskbar (#242).

A small badge in the wf-panel-pi tray with the running slot's letter:
  green   confirmed: this system started properly and is the default
  amber   being checked (the trial start of a new system), or a restart into
          the other slot is due
  red "!" the last update or switch did not work and the Pi went back; red
          until the menu has been opened once
  dot     a newer release is available (rq_release_notice.py decides which)
Hover: slot, state and version. Click or tap: a menu with both slots, System
Info, Software & Image Updates and "What's new in <release>". It never
installs anything: every action opens the RasQberry menu in a terminal.

On the standard image and on a card with one system (an A/B image on a card
under 64 GB) there are no slots: the indicator stays invisible until a newer
release is available for this Pi (the same rules: stream, grace period,
rollout, withdrawn), then shows a plain grey RasQberry badge "Q" with the
dot, and the menu: version, System Info, Software & Image Updates, "What's
new in <release>". It hides again (drops its tray name) when nothing is new.

Two one-time notices use wf-panel-pi's own popup (the desktop has no
notification server): a failed update (once per failure) and a new release
(once per release).

Runs as the desktop user from /etc/xdg/autostart/rasqberry-slot-indicator.desktop.

Written with Gio D-Bus (org.kde.StatusNotifierItem + com.canonical.dbusmenu)
and pycairo, no extra packages (spike: .local/spike-242). Facts from the
spike: wf-panel-pi shows IconPixmap (one 64 px pixmap, scaled to 32), not
IconName; the a(iiay) value is built once from GLib.Bytes (else each read
took seconds); ItemIsMenu makes a click or tap open the menu.

Data: /run/rasqberry/slot-status (root writes it at boot and after slot
changes: rq_slot_status.sh write), live files on /boot/config
(target-slot, slot-confirmed, autoboot.txt, last-switch-failed,
slot-<X>-incomplete), else `rq_slot_manager.sh summary`. Own state:
~/.local/state/rasqberry/slot-indicator.json.

Usage: rq_slot_indicator.py [--fake-failed] [--log FILE]
  --fake-failed  show a made-up failed update (trials; nothing is written)
Environment (trials, tests): RQ_SLOT_STATUS_FILE, RQ_BOOT_CONFIG_DIR,
  RQ_VERSION_FILE, XDG_STATE_HOME, XDG_CACHE_HOME, and the release URLs of
  rq_release_notice.py.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rq_release_notice as rn  # noqa: E402

log = logging.getLogger("rq_slot_indicator")

BOOT_CONFIG = "/boot/config"
RUN_DIR = "/run/rasqberry"
POLL_SECONDS = 60
FETCH_EVERY = 24 * 3600
FETCH_RETRY = 30 * 60
FIRST_FETCH_DELAY = 20
NOTICE_GAP = 16                     # wf-panel-pi shows a notice for about 15 s
ICON_SIZE = 64                      # one pixmap; the panel scales it to 32
BUS_NAME = "org.rasqberry.SlotIndicator"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
UPDATES_CMD = ["lxterminal", "-t", "RasQberry: Software & Image Updates", "-e",
               "sudo raspi-config nonint do_ab_boot_menu"]
SYSINFO_CMD = ["lxterminal", "-t", "RasQberry System Information", "-e",
               "sudo raspi-config nonint do_show_system_info"]

COLOURS = {
    "ok": (0x24, 0x8a, 0x3d),
    "checking": (0xd9, 0x7e, 0x00),
    "pending": (0xd9, 0x7e, 0x00),
    "failed": (0xc6, 0x28, 0x28),
    "plain": (0x5f, 0x63, 0x68),        # no slots: neutral grey
}
DOT = (0x1a, 0x73, 0xe8)
PLAIN_LETTER = "Q"                      # RasQberry, not a slot letter


# ---------------------------------------------------------------------------
# Slot state (pure: tests feed these functions dicts)
# ---------------------------------------------------------------------------

def should_run(status):
    """
    The A/B badge (slot letter, state colours)? Only on an A/B card with two
    systems (or the second not set up yet): not on the standard image, not
    in single-system mode - there the plain badge (indicator_mode 'plain').

    Args:
        status (dict): slot-status / summary key=value pairs

    Returns:
        bool
    """
    return (status.get("layout") == "ab"
            and status.get("current") in ("A", "B")
            and status.get("card_mode", "") not in ("single", "single-pending"))


def indicator_mode(status):
    """'ab' (the slot badge) or 'plain' (no slots: standard image, one system)."""
    return "ab" if should_run(status) else "plain"


def wants_icon(mode, advices):
    """In the tray? The slot badge always; the plain badge only while a release is new."""
    return mode == "ab" or bool(rn.updates(advices))


def autoboot_default(text):
    """The slot autoboot.txt [all] starts (boot_partition 2 = A, 3 = B), '' if unknown."""
    section = "all"
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif section == "all" and line.startswith("boot_partition="):
            return {"2": "A", "3": "B"}.get(line.split("=", 1)[1].strip(), "")
    return ""


def read_live(config_dir):
    """
    The switch state on the CONFIG partition, read now (it changes without
    a status rewrite: a switch, a confirm, a rollback).

    Returns:
        dict: target ('A'/'B'/''), confirmed (bool), default ('A'/'B'/''),
        failed (dict, empty if none), incomplete (set of slots), present (bool)
    """
    def first(name):
        return rn.read_first_line(os.path.join(config_dir, name))

    try:
        with open(os.path.join(config_dir, "autoboot.txt")) as f:
            autoboot = f.read()
    except OSError:
        autoboot = ""
    return {
        "present": bool(autoboot),
        "target": first("target-slot").strip() if first("target-slot").strip() in ("A", "B") else "",
        "confirmed": os.path.exists(os.path.join(config_dir, "slot-confirmed")),
        "default": autoboot_default(autoboot),
        "failed": rn.read_kv(os.path.join(config_dir, "last-switch-failed")),
        "incomplete": {s for s in "AB"
                       if os.path.exists(os.path.join(config_dir, f"slot-{s}-incomplete"))},
    }


def slot_info(status, live, version, fake_failed=None):
    """
    Everything the badge, tooltip and menu show, from the status file (or
    summary), the live CONFIG files and the running version. Live files win
    over the status snapshot.

    Returns:
        dict: current, other, version, contents {'A': .., 'B': ..},
        confirmed, target, default, failure (dict or None), card_mode
    """
    current = status.get("current", "")
    other = rn.other_slot(current) or ""
    contents = {s: status.get(f"slot_{s.lower()}", "UNKNOWN") or "UNKNOWN" for s in "AB"}
    if current in contents and version:
        contents[current] = version
    for s in live.get("incomplete", ()):
        contents[s] = "INCOMPLETE"
    if live.get("present"):
        confirmed, target, default = live["confirmed"], live["target"], live["default"]
    else:
        confirmed = status.get("confirmed") == "yes"
        target = status.get("pending", "") if status.get("pending") in ("A", "B") else ""
        default = status.get("default", "") if status.get("default") in ("A", "B") else ""
    failure = dict(live.get("failed") or {}) or None
    if fake_failed and not failure:
        failure = dict(fake_failed)
    return {"current": current, "other": other, "version": version, "contents": contents,
            "confirmed": confirmed, "target": target, "default": default,
            "failure": failure, "card_mode": status.get("card_mode", "")}


def failure_key(failure):
    """What identifies one failure (its time=, else the whole notice)."""
    if not failure:
        return ""
    return failure.get("time") or json.dumps(failure, sort_keys=True)


def base_state(info):
    """
    'pending', 'checking' or 'ok', ignoring a failure. Order matters: a
    requested switch first (slot-confirmed is deleted when one is requested),
    then the trial start, then a different start slot (after a rollback),
    then a start the health check has not confirmed yet.

    Returns:
        tuple: (state, next slot or '')
    """
    current, target, default = info["current"], info["target"], info["default"]
    if target in ("A", "B") and target != current:
        return "pending", target
    if not info["confirmed"] and target == current:
        return "checking", ""
    if default in ("A", "B") and default != current:
        return "pending", default
    if not info["confirmed"]:
        return "checking", ""
    return "ok", ""


def badge_state(info, acked=""):
    """
    The badge: 'failed' while a failure has not been seen in the menu, else
    base_state's.

    Returns:
        tuple: (state, next slot or '')
    """
    if info["failure"] and failure_key(info["failure"]) != acked:
        return "failed", ""
    return base_state(info)


def _version_or_empty(content):
    return "" if (content or "") in rn.NOT_A_VERSION else content


def failure_was_update(failure):
    """
    Did an update write the failed slot (update=yes, or a notice from an
    older health check without update=), or was it a plain switch (update=no)?
    """
    return (failure.get("update") or "").strip() != "no"


def failure_text(failure, current, version, contents):
    """
    The one sentence about a failed update or switch (Jan): it names both
    slots and says it "didn't work" - the new system may well have started
    and then failed a check. "The update of Slot B to <v>" when an update had
    written the slot (update=yes, or no update= in an older notice), else
    "Switching to Slot B". The same wording as `rq_slot_status.sh
    failure-notice` (tests/unit/test_slot_indicator.py runs both).

    Args:
        failure (dict): last-switch-failed (slot, reason, time, version)
        current (str): the running slot
        version (str): the running version
        contents (dict): what each slot holds (for the failed version when
            the notice has none)
    """
    failed = failure.get("slot", "")
    if failed not in ("A", "B"):
        failed = rn.other_slot(current) or "B"
    if not failure_was_update(failure):
        head = f"Switching to Slot {failed}"
    else:
        new = failure.get("version") or _version_or_empty(contents.get(failed, ""))
        head = f"The update of Slot {failed} to {new}" if new else f"The update of Slot {failed}"
    if failed == current:
        reason = (failure.get("reason") or "").strip()
        return f"{head} didn't work" + (f": {reason}." if reason else ".")
    running = f" ({version})" if version else ""
    return f"{head} didn't work, so Slot {current}{running} is running again."


STATE_LABEL = {"ok": "confirmed", "checking": "being checked", "pending": "restart pending"}


def describe_other(info):
    """
    'Slot A: <what it holds> (start slot|fallback)': the slot a normal start
    boots is the start slot; a system in the other slot is the fallback.
    """
    other = info["other"]
    content = info["contents"].get(other, "UNKNOWN")
    if other == "B" and info["card_mode"] == "dual-pending" and content in ("EMPTY", "UNKNOWN"):
        return f"Slot {other}: not set up yet"
    note = ""
    if info["default"] == other:
        note = " (start slot)"
    elif content not in rn.NOT_A_VERSION or content == "SYSTEM":
        note = " (fallback)"
    return f"Slot {other}: {rn.describe_content(content)}{note}"


def device_for_advice(info):
    """The device dict rq_release_notice.advise() takes."""
    return {"ab": True, "current": info["current"], "version": info["version"],
            "other_version": info["contents"].get(info["other"], "")}


def tooltip(info, state, next_slot, advices, device):
    """
    (title, body) - wf-panel-pi shows 'title: body', a newline starts a line.
    """
    if state == "failed":
        label = ("the update didn't work" if failure_was_update(info["failure"])
                 else "the switch didn't work")
    else:
        label = STATE_LABEL[state]
    title = f"RasQberry - Slot {info['current']} ({label})"
    lines = [f"Version: {rn.version_text(info['version']) or 'unknown'}"]
    if state == "failed":
        lines.append(failure_text(info["failure"], info["current"], info["version"], info["contents"]))
    elif state == "pending":
        lines.append(f"Slot {next_slot} starts at the next restart.")
    elif state == "checking":
        lines.append("The health check confirms it after a good start.")
    ups = rn.updates(advices)
    if ups:
        lines.append(rn.headline(ups[0], device))
    return title, "\n".join(lines)


def split_sentence(text):
    """Two menu lines from a long notice (at ', so ' or ': '), else one."""
    for sep, keep in ((", so ", "so "), (": ", "")):
        if sep in text and len(text) > 60:
            head, tail = text.split(sep, 1)
            return [head + sep[0], keep + tail]
    return [text]


def menu_items(info, state, next_slot, advices, device):
    """
    The menu as (id, properties) pairs, top to bottom. Disabled lines first
    (what runs, what the other slot holds, a failure, updates), then actions.
    Properties are plain Python values: label (str), enabled (bool),
    type ('separator'), icon-name (str). Action ids: 11 System Info,
    12 Software & Image Updates, 100+i What's new in update i.
    """
    items = []
    base, base_next = base_state(info)
    running = STATE_LABEL[base]
    items.append((1, {"label": f"Running: Slot {info['current']} ({running})", "enabled": False}))
    items.append((2, {"label": f"Version: {rn.version_text(info['version']) or 'unknown'}",
                      "enabled": False}))
    items.append((3, {"label": describe_other(info), "enabled": False}))
    next_id = 4
    if base == "pending":
        items.append((next_id, {"label": f"Slot {base_next} starts at the next restart",
                                "enabled": False}))
        next_id += 1
    if info["failure"]:
        text = failure_text(info["failure"], info["current"], info["version"], info["contents"])
        for line in split_sentence(text):
            items.append((next_id, {"label": line, "enabled": False}))
            next_id += 1
        reason = (info["failure"].get("reason") or "").strip()
        if reason and info["failure"].get("slot") != info["current"]:
            items.append((next_id, {"label": f"Reason: {reason}", "enabled": False}))
            next_id += 1
    for a in advices:
        if a["kind"] == "withdrawn":
            text = f"This release was withdrawn" + (f": {a['reason']}" if a["reason"] else "")
            items.append((next_id, {"label": text, "enabled": False}))
            next_id += 1
    ups = rn.updates(advices)
    for a in ups:
        items.append((next_id, {"label": rn.headline(a, device), "enabled": False}))
        next_id += 1
    items.append((10, {"type": "separator"}))
    items.append((11, {"label": "System Info…", "icon-name": "dialog-information"}))
    items.append((12, {"label": "Software & Image Updates…"}))
    if ups:
        items.append((13, {"type": "separator"}))
    for i, a in enumerate(ups):
        items.append((100 + i, {"label": f"What's new in {a['tag']}…"}))
    return items


def update_wait(info):
    """
    Why an update has to wait, in the words of rq_update_slot.sh's exit
    code 28 (running_slot_settled, the same two checks in the same order):
    the running slot is still on trial (the other slot is the way back), or
    the next restart starts the other slot (a rollback waiting for it).

    Returns:
        str: the sentence, '' when an update can go ahead
    """
    current, target, default = info["current"], info["target"], info["default"]
    if current not in ("A", "B"):
        return ""           # no slots: nothing to wait for
    if not info["confirmed"] and target == current:
        return (f"Slot {current}, the system you are running, is still on trial. "
                f"Updates wait until the health check has confirmed it, a few minutes "
                f"after a good start.")
    if default in ("A", "B") and default != current:
        return (f"The next restart starts Slot {default}, not Slot {current} that is "
                f"running now. Updates wait until then: restart first.")
    return ""


def plain_tooltip(version, advices, device):
    """(title, body) of the plain badge: no slots, a newer release."""
    lines = [f"Version: {rn.version_text(version) or 'unknown'}"]
    ups = rn.updates(advices)
    if ups:
        lines.append(rn.headline(ups[0], device))
    return "RasQberry", "\n".join(lines)


def plain_menu_items(version, advices, device):
    """
    The plain badge's menu: the version, the new releases, System Info,
    Software & Image Updates and "What's new in <tag>" (the ids of
    menu_items).
    """
    items = [(1, {"label": f"Version: {rn.version_text(version) or 'unknown'}",
                  "enabled": False})]
    next_id = 2
    for a in advices:
        if a["kind"] == "withdrawn":
            text = "This release was withdrawn" + (f": {a['reason']}" if a["reason"] else "")
            items.append((next_id, {"label": text, "enabled": False}))
            next_id += 1
    ups = rn.updates(advices)
    for a in ups:
        items.append((next_id, {"label": rn.headline(a, device), "enabled": False}))
        next_id += 1
    items.append((10, {"type": "separator"}))
    items.append((11, {"label": "System Info…", "icon-name": "dialog-information"}))
    items.append((12, {"label": "Software & Image Updates…"}))
    if ups:
        items.append((13, {"type": "separator"}))
    for i, a in enumerate(ups):
        items.append((100 + i, {"label": f"What's new in {a['tag']}…"}))
    return items


def whats_new(advice, device, releases, highlights, wait=""):
    """
    The 'What's new' window's text.

    Args:
        wait (str): update_wait() - when set, the window says so and has no
            Install button (install_label is '')

    Returns:
        dict: title, heading, meta (date and size), highlights (list),
        route, warning, strong (the warning is about the last beta/stable
        system), wait, release_url, install_label ('' = no Install button:
        while updates wait, and with one system, where the route says how
        to write the new image instead)
    """
    entry = advice.get("entry") or {}
    meta = ", ".join(x for x in (rn.date_text(advice["tag"], entry), rn.size_text(entry)) if x)
    lines = rn.highlight_lines(advice["stream"], releases, highlights)
    warning, strong = rn.warning_text(advice, device)
    target = advice.get("target")
    if target and not wait:
        # the slot rq_slot_manager.sh plan-update targets: the one not running
        install_label = f"Install into Slot {target}…"
    else:
        install_label = ""
    return {
        "title": f"What's new in {advice['tag']}",
        "heading": rn.headline(advice, device),
        "meta": f"Released {meta}" if meta else "",
        "highlights": lines or ["No summary yet: see the release notes."],
        "route": rn.route_text(advice, device),
        "warning": warning,
        "strong": strong,
        "wait": wait,
        "release_url": entry.get("release_url", ""),
        "install_label": install_label,
    }


# ---------------------------------------------------------------------------
# What was already said (once per failure, once per release)
# ---------------------------------------------------------------------------

def state_dir():
    """~/.local/state/rasqberry (XDG_STATE_HOME respected)."""
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "rasqberry")


class NoticeBook:
    """
    The notices already shown and the failure already seen in the menu,
    kept in <dir>/slot-indicator.json.
    """

    KEEP = 50

    def __init__(self, directory=None):
        self.path = os.path.join(directory or state_dir(), "slot-indicator.json")
        data = rn._read_json(self.path) or {}
        self.failures = [x for x in data.get("failures_noticed", []) if isinstance(x, str)]
        self.acked = data.get("failure_acked", "") if isinstance(data.get("failure_acked"), str) else ""
        self.releases = [x for x in data.get("releases_noticed", []) if isinstance(x, str)]

    def save(self):
        """Write the book (best effort)."""
        data = {"failures_noticed": self.failures[-self.KEEP:], "failure_acked": self.acked,
                "releases_noticed": self.releases[-self.KEEP:]}
        try:
            rn._write_atomic(self.path, json.dumps(data, indent=1) + "\n", 0o600)
        except OSError as e:
            log.warning("cannot save %s: %s", self.path, e)

    def failure_to_announce(self, failure):
        """True once for each failure."""
        key = failure_key(failure)
        if not key or key in self.failures:
            return False
        self.failures.append(key)
        return True

    def releases_to_announce(self, advices):
        """
        The update advices not announced yet; all of them count as announced
        from now on (one popup per check, for the first).
        """
        new = [a for a in rn.updates(advices) if a["tag"] not in self.releases]
        for a in new:
            self.releases.append(a["tag"])
        return new

    def ack(self, failure):
        """The menu was opened: the failure was seen. Returns True if that is news."""
        key = failure_key(failure)
        if key and key != self.acked:
            self.acked = key
            return True
        return False


# ---------------------------------------------------------------------------
# The tray item (Gio D-Bus, pycairo, Gtk for the window)
# ---------------------------------------------------------------------------

SNI_XML = """
<node>
 <interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="i" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="OverlayIconName" type="s" access="read"/>
  <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
  <property name="AttentionIconName" type="s" access="read"/>
  <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
  <property name="AttentionMovieName" type="s" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
  <signal name="NewTitle"/>
  <signal name="NewIcon"/>
  <signal name="NewAttentionIcon"/>
  <signal name="NewOverlayIcon"/>
  <signal name="NewToolTip"/>
  <signal name="NewStatus"><arg name="status" type="s"/></signal>
 </interface>
</node>"""

MENU_XML = """
<node>
 <interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
   <arg type="i" name="parentId" direction="in"/>
   <arg type="i" name="recursionDepth" direction="in"/>
   <arg type="as" name="propertyNames" direction="in"/>
   <arg type="u" name="revision" direction="out"/>
   <arg type="(ia{sv}av)" name="layout" direction="out"/>
  </method>
  <method name="GetGroupProperties">
   <arg type="ai" name="ids" direction="in"/>
   <arg type="as" name="propertyNames" direction="in"/>
   <arg type="a(ia{sv})" name="properties" direction="out"/>
  </method>
  <method name="GetProperty">
   <arg type="i" name="id" direction="in"/>
   <arg type="s" name="name" direction="in"/>
   <arg type="v" name="value" direction="out"/>
  </method>
  <method name="Event">
   <arg type="i" name="id" direction="in"/>
   <arg type="s" name="eventId" direction="in"/>
   <arg type="v" name="data" direction="in"/>
   <arg type="u" name="timestamp" direction="in"/>
  </method>
  <method name="EventGroup">
   <arg type="a(isvu)" name="events" direction="in"/>
   <arg type="ai" name="idErrors" direction="out"/>
  </method>
  <method name="AboutToShow">
   <arg type="i" name="id" direction="in"/>
   <arg type="b" name="needUpdate" direction="out"/>
  </method>
  <method name="AboutToShowGroup">
   <arg type="ai" name="ids" direction="in"/>
   <arg type="ai" name="updatesNeeded" direction="out"/>
   <arg type="ai" name="idErrors" direction="out"/>
  </method>
  <signal name="ItemsPropertiesUpdated">
   <arg type="a(ia{sv})" name="updatedProps"/>
   <arg type="a(ias)" name="removedProps"/>
  </signal>
  <signal name="LayoutUpdated">
   <arg type="u" name="revision"/>
   <arg type="i" name="parent"/>
  </signal>
  <signal name="ItemActivationRequested">
   <arg type="i" name="id"/>
   <arg type="u" name="timestamp"/>
  </signal>
 </interface>
</node>"""


def render_badge(letter, state, dot):
    """
    The badge as an SNI pixmap: a rounded square in the state's colour with
    the slot letter; failed adds "!" (colour is never the only cue); an
    available update adds a blue dot in the top right corner.

    Returns:
        tuple: (width, height, ARGB32 bytes in network order)
    """
    import cairo
    size = ICON_SIZE
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    m, r = size * 0.04, size * 0.22
    w = size - 2 * m
    cr.new_sub_path()
    cr.arc(m + w - r, m + r, r, -1.5708, 0)
    cr.arc(m + w - r, m + w - r, r, 0, 1.5708)
    cr.arc(m + r, m + w - r, r, 1.5708, 3.1416)
    cr.arc(m + r, m + r, r, 3.1416, 4.7124)
    cr.close_path()
    cr.set_source_rgb(*(c / 255 for c in COLOURS[state]))
    cr.fill()
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_source_rgb(1, 1, 1)
    if state == "failed":
        cr.set_font_size(size * 0.62)
        ext = cr.text_extents(letter)
        cr.move_to(size * 0.40 - ext.width / 2 - ext.x_bearing,
                   size / 2 - ext.height / 2 - ext.y_bearing)
        cr.show_text(letter)
        cr.set_font_size(size * 0.66)
        ext = cr.text_extents("!")
        cr.move_to(size * 0.80 - ext.width / 2 - ext.x_bearing,
                   size / 2 - ext.height / 2 - ext.y_bearing)
        cr.show_text("!")
    else:
        cr.set_font_size(size * 0.74)
        ext = cr.text_extents(letter)
        cr.move_to(size / 2 - ext.width / 2 - ext.x_bearing,
                   size / 2 - ext.height / 2 - ext.y_bearing)
        cr.show_text(letter)
    if dot:
        cx, cy, rad = size * 0.80, size * 0.20, size * 0.19
        cr.arc(cx, cy, rad, 0, 6.2832)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
        cr.arc(cx, cy, rad * 0.70, 0, 6.2832)
        cr.set_source_rgb(*(c / 255 for c in DOT))
        cr.fill()
    surf.flush()
    data = bytes(surf.get_data())
    stride = surf.get_stride()
    out = bytearray(size * size * 4)
    o = 0
    for y in range(size):
        row = data[y * stride:y * stride + size * 4]
        for i in range(0, size * 4, 4):
            b, g, rr, a = row[i], row[i + 1], row[i + 2], row[i + 3]
            if 0 < a < 255:     # cairo is premultiplied, SNI is not
                rr, g, b = (min(255, c * 255 // a) for c in (rr, g, b))
            out[o:o + 4] = bytes((a, rr, g, b))
            o += 4
    return size, size, bytes(out)


class SlotIndicator:
    """StatusNotifierItem + dbusmenu on the session bus, refreshed from files."""

    def __init__(self, args, loop):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.args = args
        self.loop = loop
        self.config_dir = os.environ.get("RQ_BOOT_CONFIG_DIR") or BOOT_CONFIG
        self.version_file = os.environ.get("RQ_VERSION_FILE") or rn.VERSION_FILE
        self.book = NoticeBook()
        self.fake_failed = None
        if args.fake_failed:
            self.fake_failed = {"slot": "", "reason": "(trial) a made-up failure",
                                "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        self.menu_rev = 1
        self.view = None
        self.items = []
        self.advices = []
        self.device = {}
        self.data = {"releases": None, "controls": {}, "highlights": {}}
        self.panel_present = False
        self.notices = []
        self.noticing = False
        self.fetching = False
        self.next_fetch = time.monotonic() + FIRST_FETCH_DELAY
        self.window = None
        self.refresh_pending = False
        self.monitors = []

        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # In the tray only while wants_icon(): the plain badge comes and goes
        # with a new release. Its item name is owned while it is shown; the
        # tray drops an item whose name goes away.
        self.mode = ""
        self.shown = False
        self.name = ""
        self.name_id = 0
        self.name_count = 0
        self.watcher = False
        self.update_view(initial=True)
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self.bus.register_object(ITEM_PATH, sni, self._sni_call, self._sni_prop, None)
        self.bus.register_object(MENU_PATH, menu, self._menu_call, self._menu_prop, None)
        self._show(wants_icon(self.mode, self.advices))
        Gio.bus_watch_name_on_connection(self.bus, "org.kde.StatusNotifierWatcher",
                                         Gio.BusNameWatcherFlags.NONE, self._on_watcher,
                                         self._on_watcher_gone)
        Gio.bus_watch_name_on_connection(self.bus, "org.wayfire.wfpanel",
                                         Gio.BusNameWatcherFlags.NONE,
                                         self._on_panel, self._on_panel_gone)
        for path in (RUN_DIR, self.config_dir):
            try:
                mon = Gio.File.new_for_path(path).monitor_directory(Gio.FileMonitorFlags.NONE, None)
                mon.connect("changed", self._on_file_changed)
                self.monitors.append(mon)
            except Exception as e:      # GLib.Error: a missing directory
                log.info("no monitor on %s: %s", path, e)
        GLib.timeout_add_seconds(POLL_SECONDS, self._tick)
        GLib.timeout_add_seconds(FIRST_FETCH_DELAY, self._first_fetch)

    # -- state ---------------------------------------------------------------
    def read_info(self):
        """Status file (or summary), live CONFIG files, running version."""
        status = rn.read_slot_status()
        live = read_live(self.config_dir)
        version = rn.read_first_line(self.version_file)
        fake = None
        if self.fake_failed:
            fake = dict(self.fake_failed)
            fake["slot"] = rn.other_slot(status.get("current", "")) or "B"
        return status, slot_info(status, live, version, fake)

    def update_view(self, initial=False):
        """Recompute everything; tell the panel what changed."""
        status, info = self.read_info()
        if not status.get("layout") and not initial:
            return      # status unreadable for a moment: keep what is shown
        mode = indicator_mode(status)
        if mode != self.mode:
            log.info("mode: %s (layout=%s card_mode=%s)", mode, status.get("layout", "?"),
                     status.get("card_mode", "?"))
            self.mode = mode
        self.info = info
        self.data = rn.load_all([rn.user_cache_dir(), rn.system_cache_dir()])
        if mode == "ab":
            self.device = device_for_advice(info)
        else:
            self.device = rn.device_from_status(status, info["version"])
        self.advices = rn.advise(self.device, self.data["releases"], self.data["controls"],
                                 rn.device_serial(), rn.now_utc())
        dot = bool(rn.updates(self.advices))
        if mode == "ab":
            state, next_slot = badge_state(info, self.book.acked)
            letter = info["current"] or "?"
            title, body = tooltip(info, state, next_slot, self.advices, self.device)
            items = menu_items(info, state, next_slot, self.advices, self.device)
        else:
            state, letter = "plain", PLAIN_LETTER
            title, body = plain_tooltip(info["version"], self.advices, self.device)
            items = plain_menu_items(info["version"], self.advices, self.device)
        view = (state, letter, dot, title, body)
        if view != self.view:
            w, h, pix = render_badge(letter, state, dot)
            self.pixmap = self._pixmap_variant(w, h, pix)
            self.title, self.body = title, body
            if self.view is not None:
                for sig in ("NewIcon", "NewToolTip", "NewTitle"):
                    self._emit(sig)
            log.info("view: %s %s dot=%s | %s | %s", state, info["current"], dot, title,
                     body.replace("\n", " / "))
            self.view = view
        if items != self.items:
            self.items = items
            self.menu_rev += 1
            if not initial:
                self.bus.emit_signal(None, MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated",
                                     self.GLib.Variant("(ui)", (self.menu_rev, 0)))
        if not initial:
            self._show(wants_icon(mode, self.advices))
        self._queue_notices()

    def _pixmap_variant(self, w, h, data):
        GLib = self.GLib
        item = GLib.Variant.new_tuple(
            GLib.Variant("i", w), GLib.Variant("i", h),
            GLib.Variant.new_from_bytes(GLib.VariantType("ay"), GLib.Bytes.new(data), True))
        return GLib.Variant.new_array(GLib.VariantType("(iiay)"), [item])

    def _schedule_refresh(self, delay_ms=500):
        if not self.refresh_pending:
            self.refresh_pending = True
            self.GLib.timeout_add(delay_ms, self._do_refresh)

    def _do_refresh(self):
        self.refresh_pending = False
        self.update_view()
        return False

    def _on_file_changed(self, monitor, file, other, event):
        name = file.get_basename() if file else ""
        if os.path.dirname(file.get_path() or "") == RUN_DIR and name != "slot-status":
            return      # /run/rasqberry/other-slot and friends
        self._schedule_refresh()

    def _tick(self):
        self.update_view()
        if not self.fetching and time.monotonic() >= self.next_fetch:
            self._start_fetch()
        return True

    # -- release data (a thread: urllib blocks) ---------------------------------
    def _first_fetch(self):
        self._start_fetch()
        return False

    def _start_fetch(self):
        if self.fetching:
            return
        self.fetching = True

        def work():
            ok = False
            try:
                ok = rn.fetch_all(rn.user_cache_dir())
            except Exception as e:
                log.warning("release check failed: %s", e)
            self.GLib.idle_add(self._fetched, ok)

        threading.Thread(target=work, daemon=True).start()

    def _fetched(self, ok):
        self.fetching = False
        self.next_fetch = time.monotonic() + (FETCH_EVERY if ok else FETCH_RETRY)
        log.info("release check: %s", "ok" if ok else "offline or failed (using the cache)")
        self.update_view()
        return False

    # -- notices (wf-panel-pi's popup) ---------------------------------------
    def _queue_notices(self):
        if (self.mode == "ab" and self.info.get("failure")
                and self.book.failure_to_announce(self.info["failure"])):
            f = self.info
            self.notices.append(failure_text(f["failure"], f["current"], f["version"], f["contents"]))
            self.book.save()
        new = self.book.releases_to_announce(self.advices)
        if new:
            self.notices.append(rn.popup_text(new[0], self.device))
            self.book.save()
        self._send_notices()

    def _send_notices(self):
        if self.noticing or not self.panel_present or not self.notices:
            return
        text = self.notices.pop(0)
        log.info("notice: %s", text)
        # Fire and forget: wf-panel-pi never answers this call
        self.bus.call("org.wayfire.wfpanel", "/org/wayfire/wfpanel", "org.wayfire.wfpanel",
                      "command", self.GLib.Variant("(ss)", ("notify", text)), None,
                      self.Gio.DBusCallFlags.NO_AUTO_START, 2000, None, self._notified)
        self.noticing = True
        self.GLib.timeout_add_seconds(NOTICE_GAP, self._notice_done)

    def _notified(self, conn, res):
        try:
            conn.call_finish(res)
        except Exception:
            pass        # the expected timeout: the popup is shown all the same

    def _notice_done(self):
        self.noticing = False
        self._send_notices()
        return False

    def _on_panel(self, conn, name, owner):
        log.info("panel %s appeared (%s)", name, owner)
        self.panel_present = True
        self.GLib.timeout_add_seconds(3, lambda: self._send_notices() and False)

    def _on_panel_gone(self, conn, name):
        self.panel_present = False

    # -- SNI -------------------------------------------------------------------
    def _show(self, on):
        """
        Into the tray or out of it. In: own a fresh item name and register
        it with the tray. Out: release the name - the tray drops the item.
        """
        if on == self.shown:
            return
        Gio = self.Gio
        if on:
            self.name_count += 1
            self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-{self.name_count}"
            self.name_id = Gio.bus_own_name_on_connection(self.bus, self.name,
                                                          Gio.BusNameOwnerFlags.NONE, None, None)
            self.shown = True
            log.info("in the tray as %s", self.name)
            if self.watcher:
                self._register()
        else:
            Gio.bus_unown_name(self.name_id)
            self.name_id = 0
            self.shown = False
            log.info("out of the tray (nothing new)")

    def _register(self):
        self.bus.call("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher",
                      "org.kde.StatusNotifierWatcher", "RegisterStatusNotifierItem",
                      self.GLib.Variant("(s)", (self.name,)), None,
                      self.Gio.DBusCallFlags.NONE, -1, None, self._registered)

    def _on_watcher(self, conn, name, owner):
        log.info("tray %s owned by %s%s", name, owner, " - registering" if self.shown else "")
        self.watcher = True
        if self.shown:
            self._register()

    def _on_watcher_gone(self, conn, name):
        self.watcher = False

    def _registered(self, conn, res):
        try:
            conn.call_finish(res)
        except Exception as e:
            log.warning("tray registration failed: %s", e)

    def _emit(self, signal_name, params=None):
        self.bus.emit_signal(None, ITEM_PATH, "org.kde.StatusNotifierItem", signal_name, params)

    def _sni_prop(self, conn, sender, path, iface, prop):
        GLib = self.GLib
        empty = GLib.Variant("a(iiay)", [])
        values = {
            "Category": GLib.Variant("s", "SystemServices"),
            "Id": GLib.Variant("s", "rasqberry-slot"),
            "Title": GLib.Variant("s", self.title),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", ""),
            "IconThemePath": GLib.Variant("s", ""),
            "IconPixmap": self.pixmap,
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": empty,
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": empty,
            "AttentionMovieName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], self.title, self.body)),
            "ItemIsMenu": GLib.Variant("b", True),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(prop)

    def _sni_call(self, conn, sender, path, iface, method, params, inv):
        inv.return_value(None)

    # -- dbusmenu --------------------------------------------------------------
    def _props(self, props):
        GLib = self.GLib
        out = {}
        for key, value in props.items():
            if isinstance(value, bool):
                out[key] = GLib.Variant("b", value)
            else:
                out[key] = GLib.Variant("s", str(value))
        return out

    def _menu_prop(self, conn, sender, path, iface, prop):
        GLib = self.GLib
        return {"Version": GLib.Variant("u", 3),
                "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"),
                "IconThemePath": GLib.Variant("as", [])}.get(prop)

    def _menu_call(self, conn, sender, path, iface, method, params, inv):
        GLib = self.GLib
        args = params.unpack()
        items = {i: self._props(p) for i, p in self.items}
        if method == "GetLayout":
            parent = args[0]
            if parent == 0:
                kids = [GLib.Variant("(ia{sv}av)", (i, items[i], [])) for i, _ in self.items]
                layout = (0, {"children-display": GLib.Variant("s", "submenu")}, kids)
            else:
                layout = (parent, items.get(parent, {}), [])
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (self.menu_rev, layout)))
        elif method == "GetGroupProperties":
            ids = args[0] or list(items)
            inv.return_value(GLib.Variant("(a(ia{sv}))", ([(i, items[i]) for i in ids if i in items],)))
        elif method == "GetProperty":
            value = items.get(args[0], {}).get(args[1], GLib.Variant("s", ""))
            inv.return_value(GLib.Variant("(v)", (value,)))
        elif method == "Event":
            if args[1] == "clicked":
                self.GLib.idle_add(self._clicked, args[0])
            inv.return_value(None)
        elif method == "EventGroup":
            for event in args[0]:
                if event[1] == "clicked":
                    self.GLib.idle_add(self._clicked, event[0])
            inv.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            if args[0] == 0:
                self.GLib.idle_add(self._menu_opened)
            inv.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            if 0 in args[0]:
                self.GLib.idle_add(self._menu_opened)
            inv.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            inv.return_value(None)

    def _menu_opened(self):
        if self.info.get("failure") and self.book.ack(self.info["failure"]):
            log.info("failure seen in the menu")
            self.book.save()
            self.update_view()
        return False

    def _clicked(self, item_id):
        log.info("menu item %s", item_id)
        if item_id == 11:
            self.spawn(SYSINFO_CMD)
        elif item_id == 12:
            self.spawn(UPDATES_CMD)
        elif item_id >= 100:
            ups = rn.updates(self.advices)
            if item_id - 100 < len(ups):
                self.show_whats_new(ups[item_id - 100])
        return False

    def spawn(self, argv):
        """Start a program on its own (GLib reaps it: no zombies)."""
        try:
            self.GLib.spawn_async(argv, flags=self.GLib.SpawnFlags.SEARCH_PATH)
        except Exception as e:
            log.warning("cannot start %s: %s", argv[0], e)

    # -- What's new ------------------------------------------------------------
    def show_whats_new(self, advice):
        """A small window: highlights, where it goes, Release notes / Install / Later."""
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
        if self.window is not None:
            self.window.destroy()
        text = whats_new(advice, self.device, self.data["releases"], self.data["highlights"],
                         wait=update_wait(self.info) if self.mode == "ab" else "")
        win = Gtk.Window(title=text["title"])
        win.set_default_size(480, -1)
        win.set_position(Gtk.WindowPosition.CENTER)
        win.set_icon_name("system-software-update")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(16)
        win.add(box)

        def label(s, markup=False, dim=False):
            lab = Gtk.Label()
            s = s.replace("/data", "/\u2060data")      # no line break inside "/data"
            if markup:
                lab.set_markup(s)
            else:
                lab.set_text(s)
            lab.set_line_wrap(True)
            lab.set_max_width_chars(60)
            lab.set_xalign(0)
            if dim:
                lab.get_style_context().add_class("dim-label")
            box.pack_start(lab, False, False, 0)
            return lab

        from gi.repository import GLib as _GLib
        label(f"<b>{_GLib.markup_escape_text(text['heading'])}</b>", markup=True)
        if text["meta"]:
            label(text["meta"], dim=True)
        for line in text["highlights"]:
            label(f"•  {line}")
        label(text["route"])
        if text["warning"]:
            warning = _GLib.markup_escape_text(text["warning"])
            label(f"<b>{warning}</b>" if text["strong"] else warning, markup=True)
        if text["wait"]:
            label(f"<b>{_GLib.markup_escape_text(text['wait'])}</b>", markup=True)
        buttons = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        buttons.set_layout(Gtk.ButtonBoxStyle.END)
        buttons.set_spacing(8)
        box.pack_end(buttons, False, False, 8)
        if text["release_url"]:
            notes = Gtk.Button(label="Release notes")
            notes.connect("clicked", lambda *_: self.open_url(text["release_url"]))
            buttons.add(notes)
        if text["install_label"]:
            install = Gtk.Button(label=text["install_label"])

            def on_install(*_):
                self.spawn(UPDATES_CMD)
                win.destroy()

            install.connect("clicked", on_install)
            buttons.add(install)
        later = Gtk.Button(label="Later")
        later.connect("clicked", lambda *_: win.destroy())
        buttons.add(later)
        win.connect("destroy", self._window_closed)
        self.window = win
        win.show_all()
        later.grab_focus()

    def _window_closed(self, *_):
        self.window = None

    def open_url(self, url):
        """The release page in the browser, through rq_common.sh's rq_open_browser."""
        common = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rq_common.sh")
        self.spawn(["bash", "-c", '. "$1" && rq_open_browser "$2"', "rq-open", common, url])


def main(argv=None):
    """Start the indicator: the slot badge on an A/B card with two systems, else
    the plain badge, invisible until a newer release is there."""
    p = argparse.ArgumentParser(description="RasQberry A/B slot indicator")
    p.add_argument("--fake-failed", action="store_true",
                   help="show a made-up failed update (trials; nothing is written)")
    p.add_argument("--log", default=os.path.join(state_dir(), "slot-indicator.log"))
    args = p.parse_args(argv)
    try:
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        if os.path.getsize(args.log) > 256 * 1024:
            os.truncate(args.log, 0)
    except OSError:
        pass
    try:
        logging.basicConfig(filename=args.log, level=logging.INFO,
                            format="%(asctime)s %(message)s")
    except OSError:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    try:
        import cairo  # noqa: F401
        from gi.repository import Gio, GLib
    except ImportError as e:
        log.warning("cannot show the indicator: %s", e)
        return 0

    loop = GLib.MainLoop()
    # One indicator per session: a second start leaves before it shows anything
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                          "RequestName", GLib.Variant("(su)", (BUS_NAME, 4)),   # 4: DO_NOT_QUEUE
                          GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    if reply.unpack()[0] not in (1, 4):     # 1: now the owner, 4: owned already by us
        log.info("another indicator is running - exit")
        return 0
    SlotIndicator(args, loop)
    log.info("started (pid %s)", os.getpid())
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: loop.quit() or False)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: loop.quit() or False)
    loop.run()
    log.info("exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
