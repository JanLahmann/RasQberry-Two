#!/usr/bin/env python3
"""
RasQberry: is a newer release worth telling this Pi about? (#242)

The rules behind the desktop update notice (rq_slot_indicator.py) and the
one-line notice at an SSH or console login. Never installs anything: it only
says what is available and where it would go.

Data, all optional and cached (a Pi without network uses the last good copy):
  RQB-releases.json           the newest release of each stream (dev, beta, stable)
  highlights.json             short "what's new" lines per stream (curated)
  RQB-release-controls.json   per release tag: notify_after, rollout, withdrawn,
                              reason (404 = defaults for every release)

Rules:
  - Streams rank dev < beta < stable. The running system hears about newer
    releases of its own stream or a more stable one: a dev system about
    development builds (not feature-branch dev-* builds), betas and stable
    releases; a beta system about betas and stable releases.
  - The other slot, if it holds a beta or stable system, hears the same way
    ("Slot A (beta) can be updated to ...").
  - A release either slot already holds is not offered.
  - An update always goes into the slot that is not running (ping-pong): after
    its trial start it becomes the start slot, the other one the fallback.
    The window warns, with the rules of `rq_slot_manager.sh plan-update`
    (plan_update below is a copy; tests/unit/data/plan_update_cases.json
    keeps the two the same): a downgrade (a lower stream, or an older beta
    or stable release, than the target slot holds), and above all
    overwriting the last beta or stable system on the card (the target
    holds beta/stable and the running slot does not).
  - Staged rollout: a release is announced only after a grace period (dev 0,
    beta 3, stable 7 days after its release, or the control's notify_after),
    and only to the share of Pis given by "rollout" (0-100, default 100). A
    Pi's share is decided on the Pi: sha256(<board serial>:<tag>) % 100, with
    /etc/machine-id when the board has no serial. Nothing is sent anywhere.
  - A withdrawn release is never announced.

Usage:
  rq_release_notice.py                  what this Pi would be told now (cached data)
  rq_release_notice.py --refresh        fetch the data into ~/.cache/rasqberry, then the same
  rq_release_notice.py --refresh --system
                                        as root (daily timer): fetch into /var/cache/rasqberry
                                        and write the login line to /var/lib/rasqberry/update-notice
  rq_release_notice.py --line           the login line from the cached data (empty if none)
  rq_release_notice.py --bucket TAG     this Pi's rollout number (0-99) for TAG

Environment (tests, trials): RQ_RELEASES_URL, RQ_RELEASE_CONTROLS_URL,
  RQ_HIGHLIGHTS_URL (http(s):// or file://), RQ_SLOT_STATUS_FILE,
  RQ_VERSION_FILE, RQ_NOTICE_FILE, RQ_SYSTEM_CACHE_DIR, RQ_SERIAL (bucket
  tests), RQ_NOW (ISO time, tests).
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

log = logging.getLogger("rq_release_notice")

RELEASES_URL = "https://rasqberry.org/RQB-releases.json"
CONTROLS_URL = "https://rasqberry.org/RQB-release-controls.json"
HIGHLIGHTS_URL = "https://rasqberry.org/highlights.json"
SYSTEM_CACHE_DIR = "/var/cache/rasqberry"
NOTICE_FILE = "/var/lib/rasqberry/update-notice"
STATUS_FILE = "/run/rasqberry/slot-status"
VERSION_FILE = "/etc/rasqberry-version"
SLOT_MANAGER = "/usr/bin/rq_slot_manager.sh"
FETCH_TIMEOUT = 15

# Release streams, as rq_slot_manager.sh plan-update ranks them; a version of
# no known stream is "unknown": it ranks like dev and never counts as safe
RANK = {"dev": 0, "beta": 1, "stable": 2}
SAFE_STREAMS = ("beta", "stable")
GRACE_DAYS = {"dev": 0, "beta": 3, "stable": 7}
# "New <noun> available", "the <adjective> system in Slot B"
NOUN = {"dev": "development build", "beta": "beta", "stable": "stable release"}
ADJECTIVE = {"dev": "development", "beta": "beta", "stable": "stable"}
NOT_A_VERSION = {"", "EMPTY", "INCOMPLETE", "UNKNOWN", "SYSTEM"}
LOGIN_WIDTH = 80
MENU_HINT = " (Software & Image Updates)"
# Commit subjects that are not news (dev highlights come from the changelog)
NOISE = re.compile(r"^(Bump version|Merge |Generate RQB-|Update RQB-)", re.I)


# ---------------------------------------------------------------------------
# Versions, streams, times
# ---------------------------------------------------------------------------

def version_stream(version):
    """
    Release stream of a version or release tag - rq_slot_manager.sh
    version_stream, the same patterns in the same order.

    Args:
        version (str): e.g. 'beta-2026-10-03-095636', 'v1.0.0', '1.0.0'

    Returns:
        str: 'beta', 'dev', 'stable' or 'unknown'
    """
    version = version or ""
    if version.startswith("beta-"):
        return "beta"
    if version.startswith(("development-", "dev-")):
        return "dev"
    if re.match(r"v[0-9]|[0-9]|stable-", version):
        return "stable"
    return "unknown"


def stream_of(version):
    """
    Release stream of a version or tag (version_stream), None for what is
    not a version (EMPTY, INCOMPLETE, UNKNOWN, SYSTEM, '').

    Returns:
        str or None: 'dev', 'beta', 'stable', 'unknown'
    """
    version = (version or "").strip()
    if version in NOT_A_VERSION:
        return None
    return version_stream(version)


def rank(stream):
    """A stream's rank: dev 0 < beta 1 < stable 2; unknown ranks like dev."""
    return RANK.get(stream, 0)


def tag_time(tag):
    """
    Build time in a tag (...-YYYY-MM-DD-HHMMSS, UTC).

    Returns:
        datetime or None
    """
    found = re.findall(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})", tag or "")
    if not found:
        return None
    try:
        return datetime(*(int(x) for x in found[-1]), tzinfo=timezone.utc)
    except ValueError:
        return None


def semver(tag):
    """(major, minor, patch) of 'v1.2.3' or '1.2.3', else None."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def parse_time(text):
    """
    A time from the release data: ISO 8601 ('2026-10-12T08:00:00Z'),
    'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'. Times without a zone are UTC.

    Returns:
        datetime or None
    """
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for parse in (datetime.fromisoformat,
                  lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M"),
                  lambda t: datetime.strptime(t, "%Y-%m-%d")):
        try:
            value = parse(text)
        except ValueError:
            continue
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
    return None


def release_time(tag, entry):
    """
    When a release came out: the later of its release_date and the build
    time in its tag (a date-only release_date is midnight, the tag is precise).

    Returns:
        datetime or None
    """
    times = [t for t in (parse_time((entry or {}).get("release_date")), tag_time(tag)) if t]
    return max(times) if times else None


def is_newer(tag, entry, version):
    """
    Is release <tag> newer than the installed <version>? Unsure means no.

    Both with a build time: compare those. Both v1.2.3: compare the numbers.
    Else the release date against the version's build time.

    Returns:
        bool
    """
    version = (version or "").strip()
    if not tag or version in NOT_A_VERSION or tag == version:
        return False
    new_t, old_t = tag_time(tag), tag_time(version)
    if new_t and old_t:
        return new_t > old_t
    new_v, old_v = semver(tag), semver(version)
    if new_v and old_v:
        return new_v > old_v
    if old_t:
        published = release_time(tag, entry)
        return bool(published and published > old_t)
    return False


# ---------------------------------------------------------------------------
# Jan's guard: a copy of rq_slot_manager.sh plan-update
# ---------------------------------------------------------------------------
# Keep every function here in step with its namesake in rq_slot_manager.sh;
# tests/unit/data/plan_update_cases.json runs both.

def _content(text):
    """A slot's content as the shell sees it (tr -d '[:space:]')."""
    return "".join((text or "").split())


def content_stream(content):
    """Stream of what a slot holds: 'none' without a system (content_stream)."""
    if content in ("EMPTY", "INCOMPLETE"):
        return "none"
    if content in ("SYSTEM", "UNKNOWN", ""):
        return "unknown"
    return version_stream(content)


def holds_text(content):
    """'<stream> <version>', or why there is no version (holds_text)."""
    words = {"EMPTY": "none empty", "INCOMPLETE": "none unfinished",
             "SYSTEM": "unknown system", "UNKNOWN": "unknown unknown", "": "unknown unknown"}
    return words.get(content) or f"{version_stream(content)} {content}"


def _digit(c):
    return "0" <= c <= "9"


def _vercmp_order(s, pos):
    # gnulib filevercmp's order(): '~' < the end < a digit < a letter < the rest
    if pos == len(s):
        return -1
    c = s[pos]
    if _digit(c):
        return 0
    if c.isascii() and c.isalpha():
        return ord(c)
    if c == "~":
        return -2
    return ord(c) + 256


def _verrevcmp(a, b):
    i = j = 0
    while i < len(a) or j < len(b):
        first_diff = 0
        while (i < len(a) and not _digit(a[i])) or (j < len(b) and not _digit(b[j])):
            ca, cb = _vercmp_order(a, i), _vercmp_order(b, j)
            if ca != cb:
                return ca - cb
            i += 1
            j += 1
        while i < len(a) and a[i] == "0":
            i += 1
        while j < len(b) and b[j] == "0":
            j += 1
        while i < len(a) and j < len(b) and _digit(a[i]) and _digit(b[j]):
            if not first_diff:
                first_diff = ord(a[i]) - ord(b[j])
            i += 1
            j += 1
        if i < len(a) and _digit(a[i]):
            return 1
        if j < len(b) and _digit(b[j]):
            return -1
        if first_diff:
            return first_diff
    return 0


def _prefix_len(s):
    # The part before a file suffix (\.[A-Za-z~][A-Za-z0-9~]*)*$
    i = prefix = 0
    while i < len(s):
        i += 1
        prefix = i
        while (i + 1 < len(s) and s[i] == "."
               and ((s[i + 1].isascii() and s[i + 1].isalpha()) or s[i + 1] == "~")):
            i += 2
            while i < len(s) and ((s[i].isascii() and s[i].isalnum()) or s[i] == "~"):
                i += 1
    return prefix


def version_compare(a, b):
    """
    `sort -V` order of two strings (GNU filevercmp, then plain text when
    the versions are equal, like sort's last resort).

    Returns:
        int: < 0, 0 or > 0
    """
    if a == b:
        return 0
    if not a or not b:
        return -1 if not a else 1
    if a[0] == "." or b[0] == ".":
        if b[0] != ".":
            return -1
        if a[0] != ".":
            return 1
    pa, pb = _prefix_len(a), _prefix_len(b)
    result = _verrevcmp(a[:pa], b[:pb])
    if not result and not (pa == len(a) and pb == len(b)):
        result = _verrevcmp(a, b)
    return result or (-1 if a < b else 1)


def version_older(a, b):
    """
    Is release <a> older than <b> of the same stream (version_older)? Beta
    tags compare by their date and time, stable ones by version number.
    """
    def bare(v):
        for prefix in ("beta-", "stable-", "v"):
            if v.startswith(prefix):
                v = v[len(prefix):]
        return v
    a, b = bare(a), bare(b)
    return a != b and version_compare(a, b) < 0


def plan_update(tag, target_content, running_content):
    """
    What installing <tag> into the slot that is not running would replace -
    `rq_slot_manager.sh plan-update` without the slot letters and advice:
      downgrade       'stream' if the new stream ranks below the target's,
                      'older' if an older beta or stable release than the
                      target's (dev over dev never warns), else 'none'
      last_safe_slot  'yes' if the target holds beta/stable and the running
                      slot does not
    An empty, unfinished or unknown target gives no warning.

    Args:
        tag (str): the release tag
        target_content, running_content (str): what each slot holds: a
            version, EMPTY, INCOMPLETE, SYSTEM or UNKNOWN

    Returns:
        dict: target_holds, running_holds, new, downgrade, last_safe_slot -
        the strings plan-update prints
    """
    t_content, r_content = _content(target_content), _content(running_content)
    t_stream, r_stream = content_stream(t_content), content_stream(r_content)
    n_stream = version_stream(tag)
    downgrade = "none"
    if t_stream not in ("none", "unknown"):
        if rank(n_stream) < rank(t_stream):
            downgrade = "stream"
        elif (n_stream == t_stream and n_stream in SAFE_STREAMS
              and version_older(tag, t_content)):
            downgrade = "older"
    last_safe = t_stream in SAFE_STREAMS and r_stream not in SAFE_STREAMS
    return {
        "target_holds": holds_text(t_content),
        "running_holds": holds_text(r_content),
        "new": f"{n_stream} {tag}",
        "downgrade": downgrade,
        "last_safe_slot": "yes" if last_safe else "no",
    }


# ---------------------------------------------------------------------------
# Controls: grace, rollout, withdrawn
# ---------------------------------------------------------------------------

def controls_for(controls, tag):
    """
    The control entry of one release tag. The file maps tag -> entry, at the
    top level or under "releases"; anything else is ignored.

    Returns:
        dict (empty: defaults)
    """
    if not isinstance(controls, dict) or not tag:
        return {}
    table = controls.get("releases") if isinstance(controls.get("releases"), dict) else controls
    entry = table.get(tag)
    return entry if isinstance(entry, dict) else {}


def is_withdrawn(controls, tag):
    """(withdrawn, reason) of a release tag."""
    entry = controls_for(controls, tag)
    if entry.get("withdrawn") is True:
        return True, str(entry.get("reason") or "").strip()
    return False, ""


def device_serial(dt_path="/proc/device-tree/serial-number", cpuinfo="/proc/cpuinfo",
                  machine_id="/etc/machine-id"):
    """
    The board's serial number (stable across slots, updates and new cards),
    else /etc/machine-id. Used only on the Pi, for the rollout number.

    Returns:
        str ('' if neither can be read)
    """
    if os.environ.get("RQ_SERIAL") is not None:
        return os.environ["RQ_SERIAL"]
    serial = ""
    try:
        with open(dt_path, "rb") as f:
            serial = f.read().replace(b"\0", b"").decode("ascii", "ignore").strip()
    except OSError:
        pass
    if not serial.strip("0"):
        serial = ""
        try:
            with open(cpuinfo) as f:
                for line in f:
                    if line.startswith("Serial"):
                        serial = line.split(":", 1)[-1].strip()
                        break
        except OSError:
            pass
    if not serial.strip("0"):
        try:
            with open(machine_id) as f:
                serial = f.read().strip()
        except OSError:
            serial = ""
    return serial


def rollout_bucket(serial, tag):
    """This Pi's number 0-99 for a release: sha256(serial:tag) % 100."""
    digest = hashlib.sha256(f"{serial}:{tag}".encode()).hexdigest()
    return int(digest, 16) % 100


def eligible(stream, tag, entry, controls, serial, now):
    """
    May this Pi be told about release <tag> now?

    Returns:
        tuple: (bool, reason) - reason is one of '', 'withdrawn',
        'feature-branch build', 'not yet', 'no date', 'rollout'
    """
    if is_withdrawn(controls, tag)[0]:
        return False, "withdrawn"
    if stream == "dev" and not tag.startswith("development-"):
        return False, "feature-branch build"
    ctl = controls_for(controls, tag)
    after = parse_time(ctl.get("notify_after"))
    if after is None:
        published = release_time(tag, entry)
        if published is None:
            return False, "no date"
        after = published + timedelta(days=GRACE_DAYS.get(stream, 7))
    if now < after:
        return False, "not yet"
    try:
        rollout = max(0, min(100, int(ctl.get("rollout", 100))))
    except (TypeError, ValueError):
        rollout = 100
    if rollout_bucket(serial, tag) >= rollout:
        return False, "rollout"
    return True, ""


# ---------------------------------------------------------------------------
# What to tell this Pi
# ---------------------------------------------------------------------------

def heads(releases):
    """stream -> (tag, entry) of the newest release of each stream."""
    out = {}
    streams = (releases or {}).get("streams") if isinstance(releases, dict) else None
    if not isinstance(streams, dict):
        return out
    for stream in RANK:
        entry = streams.get(stream)
        if isinstance(entry, dict) and isinstance(entry.get("tag"), str) and entry["tag"]:
            out[stream] = (entry["tag"], entry)
    return out


def other_slot(slot):
    """The other slot of A/B, None otherwise."""
    return {"A": "B", "B": "A"}.get(slot)


def advise(device, releases, controls, serial, now):
    """
    What this Pi is told, most stable stream first.

    Args:
        device (dict): ab (bool: two systems on this card), current ('A'/'B'),
            version (running), other_version (what the other slot holds:
            a version, EMPTY, INCOMPLETE, UNKNOWN or SYSTEM)
        releases, controls (dict): the parsed JSON files
        serial (str): for the rollout number
        now (datetime): aware

    Returns:
        list of dict, each with 'kind':
          'update'    tag, stream, entry, for_running (newer than the running
                      system), other (the other slot, when it is that slot's
                      system that is out of date, else None), target (the slot
                      it goes into: the one not running; None with one
                      system), plan (plan_update for the target)
          'withdrawn' tag, reason: the running release was withdrawn
    """
    out = []
    running_v = (device.get("version") or "").strip()
    s_run = stream_of(running_v)
    ab = bool(device.get("ab")) and device.get("current") in ("A", "B")
    current = device.get("current") if ab else None
    other = other_slot(current)
    other_v = (device.get("other_version") or "").strip() if ab else ""
    s_other = stream_of(other_v)
    held = {running_v, other_v} - NOT_A_VERSION
    newest = heads(releases)

    run_withdrawn, why = is_withdrawn(controls, running_v)
    if run_withdrawn:
        out.append({"kind": "withdrawn", "tag": running_v, "reason": why})

    for stream in ("stable", "beta", "dev"):
        if stream not in newest:
            continue
        tag, entry = newest[stream]
        if tag in held:
            continue
        if not eligible(stream, tag, entry, controls, serial, now)[0]:
            continue
        for_running = bool(s_run) and RANK[stream] >= rank(s_run) and is_newer(tag, entry, running_v)
        for_other = (other is not None and s_other in SAFE_STREAMS
                     and RANK[stream] >= rank(s_other) and is_newer(tag, entry, other_v))
        if for_running or for_other:
            out.append({"kind": "update", "tag": tag, "stream": stream, "entry": entry,
                        "for_running": for_running, "other": other if for_other else None,
                        "target": other,
                        "plan": plan_update(tag, other_v, running_v) if other else None})
    return out


def updates(advices):
    """Only the 'update' advices."""
    return [a for a in advices if a["kind"] == "update"]


# ---------------------------------------------------------------------------
# Wording (STYLE.md: British English, short, says where to go)
# ---------------------------------------------------------------------------

def headline(advice, device):
    """One line: 'New beta available: <tag>' or 'Slot A (beta) can be updated to <tag>'."""
    if advice["for_running"] or not advice.get("other"):
        return f"New {NOUN[advice['stream']]} available: {advice['tag']}"
    other_stream = stream_of(device.get("other_version"))
    return (f"Slot {advice['other']} ({ADJECTIVE.get(other_stream, 'other')}) "
            f"can be updated to {advice['tag']}")


def popup_text(advice, device):
    """The one-time desktop notice for a release."""
    return f"{headline(advice, device)}. Click the RasQberry slot icon for what's new."


def login_line(advices, device, width=LOGIN_WIDTH):
    """
    One line for the login message (fits <width> columns where it can), or ''.
    """
    ups = updates(advices)
    if not ups:
        return ""
    first = ups[0]
    candidates = [headline(first, device) + MENU_HINT]
    if first["for_running"] or not first.get("other"):
        candidates.append(f"New {NOUN[first['stream']]}: {first['tag']}{MENU_HINT}")
    candidates.append(headline(first, device))
    for line in candidates:
        if len(line) <= width:
            return line
    return candidates[-1]


def version_text(version):
    """A version with its stream where the tag does not say it: 'stable v1.0.0'."""
    stream = stream_of(version)
    if stream == "stable" and not version.startswith("stable"):
        return f"stable {version}"
    return version


def describe_content(content):
    """What a slot holds, in words."""
    words = {"EMPTY": "empty", "INCOMPLETE": "unfinished update", "UNKNOWN": "not known yet",
             "SYSTEM": "a system without version information", "": "not known yet"}
    return words.get(content, None) or version_text(content)


def warning_text(advice, device):
    """
    What installing would replace in the target slot, and Jan's guard.

    Returns:
        tuple: (text or '', strong) - strong when it would overwrite the last
        beta or stable system on the card
    """
    target = advice.get("target")
    if not target:
        return "", False
    content = (device.get("other_version") or "").strip()
    if content in ("EMPTY", "INCOMPLETE"):
        return "", False
    plan = advice.get("plan") or plan_update(advice["tag"], content, device.get("version"))
    stream = stream_of(content)
    strong = plan["last_safe_slot"] == "yes"
    if stream in RANK:
        text = f"This replaces Slot {target}'s {ADJECTIVE[stream]} system ({content})"
    elif stream:
        text = f"This replaces the system in Slot {target} ({content})"
    else:
        text = f"This replaces the system in Slot {target}"
    if strong:
        text += ", the only stable or beta system on this card"
    text += "."
    noun = NOUN[advice["stream"]]
    if plan["downgrade"] == "stream":
        text += f" That is a downgrade to a {noun}."
    elif plan["downgrade"] == "older":
        text += f" That is a downgrade to an older {noun}."
    if strong:
        text += (f" Safer: switch to Slot {target} first, then install into "
                 f"Slot {device.get('current')}.")
    return text + " Your files on /data are kept.", strong


def route_text(advice, device):
    """Where the update goes; the updater does the rest."""
    target = advice.get("target")
    if not target:
        return ("This Pi has one system: write the new image to a card "
                "(rasqberry.org/latest/). Copy your notebooks and ~/.qiskit first.")
    return (f"It goes into Slot {target}, the slot that is not running. After a good "
            f"trial start, Slot {target} becomes the start slot and Slot "
            f"{device.get('current')} stays as the fallback.")


def size_text(entry):
    """'about 1.7 GB' for the A/B image download, '' if unknown."""
    try:
        size = int((entry or {}).get("ab_image_download_size") or 0)
    except (TypeError, ValueError):
        size = 0
    return f"about {size / 1e9:.1f} GB" if size > 0 else ""


def date_text(tag, entry):
    """'3 October 2026', '' if unknown."""
    when = release_time(tag, entry)
    return f"{when.day} {when.strftime('%B %Y')}" if when else ""


def highlight_lines(stream, releases, highlights, limit=6):
    """
    'What's new' lines for the newest release of <stream>: the curated
    highlights.json first, else the release list's own (without commit noise).

    Returns:
        list of str
    """
    lines = []
    if isinstance(highlights, dict) and isinstance(highlights.get(stream), list):
        lines = [h for h in highlights[stream] if isinstance(h, str) and h.strip()]
    if not lines:
        entry = heads(releases).get(stream, (None, {}))[1]
        lines = [h for h in (entry.get("highlights") or [])
                 if isinstance(h, str) and h.strip() and not NOISE.match(h.strip())]
    return [h.strip() for h in lines[:limit]]


# ---------------------------------------------------------------------------
# Data: fetch with a cache, read the device
# ---------------------------------------------------------------------------

SOURCES = {
    "releases": ("RQ_RELEASES_URL", RELEASES_URL),
    "controls": ("RQ_RELEASE_CONTROLS_URL", CONTROLS_URL),
    "highlights": ("RQ_HIGHLIGHTS_URL", HIGHLIGHTS_URL),
}


def source_url(name):
    """The URL of a data file (environment override first)."""
    env, default = SOURCES[name]
    return os.environ.get(env) or default


def user_cache_dir():
    """~/.cache/rasqberry (XDG_CACHE_HOME respected)."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "rasqberry")


def system_cache_dir():
    """/var/cache/rasqberry (written by the daily root check)."""
    return os.environ.get("RQ_SYSTEM_CACHE_DIR") or SYSTEM_CACHE_DIR


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_atomic(path, text, mode=0o644):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".rq-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def fetch(name, cache_dir, now=None, timeout=FETCH_TIMEOUT):
    """
    Fetch one data file into <cache_dir>/<name>.json, with a conditional GET
    when the cache has an ETag or Last-Modified. A missing controls file
    (404) is cached as {}: every release gets the defaults.

    Returns:
        bool: the cache is now up to date (False: offline or an error; the
        last good copy stays)
    """
    now = now or datetime.now(timezone.utc)
    url = source_url(name)
    data_path = os.path.join(cache_dir, f"{name}.json")
    meta_path = os.path.join(cache_dir, f"{name}.meta.json")
    meta = _read_json(meta_path) or {}
    headers = {"User-Agent": "RasQberry-Two update notice"}
    if url.startswith(("http://", "https://")) and os.path.exists(data_path):
        if meta.get("etag"):
            headers["If-None-Match"] = meta["etag"]
        if meta.get("last_modified"):
            headers["If-Modified-Since"] = meta["last_modified"]
    body = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                    timeout=timeout) as resp:
            body = resp.read()
            meta = {"etag": resp.headers.get("ETag", "") if resp.headers else "",
                    "last_modified": resp.headers.get("Last-Modified", "") if resp.headers else ""}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            meta["fetched"] = now.isoformat()
            _write_atomic(meta_path, json.dumps(meta))
            return True
        if e.code == 404 and name == "controls":
            body, meta = b"{}", {}
        else:
            log.info("%s: HTTP %s", url, e.code)
            return False
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.info("%s: %s", url, e)
        return False
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        log.info("%s: not JSON", url)
        return False
    if not isinstance(parsed, dict):
        log.info("%s: not a JSON object", url)
        return False
    meta["fetched"] = now.isoformat()
    _write_atomic(data_path, json.dumps(parsed))
    _write_atomic(meta_path, json.dumps(meta))
    return True


def fetch_all(cache_dir, now=None):
    """Fetch the three files. Returns True when the release list is fresh."""
    ok = fetch("releases", cache_dir, now)
    if ok:
        fetch("controls", cache_dir, now)
        fetch("highlights", cache_dir, now)
    return ok


def load_cached(name, dirs):
    """
    The freshest cached copy of a data file among <dirs>.

    Returns:
        tuple: (data or None, fetched datetime or None)
    """
    best, best_t = None, None
    for directory in dirs:
        data = _read_json(os.path.join(directory, f"{name}.json"))
        if not isinstance(data, dict):
            continue
        meta = _read_json(os.path.join(directory, f"{name}.meta.json")) or {}
        fetched = parse_time(meta.get("fetched")) or datetime.min.replace(tzinfo=timezone.utc)
        if best_t is None or fetched > best_t:
            best, best_t = data, fetched
    return best, best_t


def load_all(dirs):
    """dict name -> data ({} for controls/highlights when never fetched)."""
    out = {}
    for name in SOURCES:
        data, _ = load_cached(name, dirs)
        out[name] = data if data is not None else ({} if name != "releases" else None)
    return out


def read_kv(path):
    """key=value lines of a file as a dict (empty if it cannot be read)."""
    out = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    out[key] = value
    except OSError:
        pass
    return out


def read_first_line(path):
    """First line of a file, '' if it cannot be read."""
    try:
        with open(path) as f:
            return f.readline().strip()
    except OSError:
        return ""


def read_slot_status(status_file=None, slot_manager=None):
    """
    What the slots hold: /run/rasqberry/slot-status (written by root at boot
    and after slot changes; it can read the other slot), else
    `rq_slot_manager.sh summary` (as a normal user the other slot is UNKNOWN).

    Returns:
        dict: the key=value pairs ({} if nothing could be read); 'source' says
        which one ('file' or 'summary')
    """
    path = status_file or os.environ.get("RQ_SLOT_STATUS_FILE") or STATUS_FILE
    status = read_kv(path)
    if status.get("layout"):
        status["source"] = "file"
        return status
    try:
        proc = subprocess.run([slot_manager or SLOT_MANAGER, "summary"], capture_output=True,
                              text=True, timeout=30)
        status = {}
        for line in proc.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                status[key] = value
    except (OSError, subprocess.SubprocessError) as e:
        log.info("summary: %s", e)
        status = {}
    if status:
        status["source"] = "summary"
    return status


def device_from_status(status, version):
    """
    The device dict advise() needs, from the slot status and the running
    version. Single-system cards and the standard image count as one system.
    """
    ab = (status.get("layout") == "ab"
          and status.get("card_mode", "") not in ("single", "single-pending")
          and status.get("current") in ("A", "B"))
    current = status.get("current") if ab else None
    other = other_slot(current)
    other_v = status.get(f"slot_{other.lower()}", "") if other else ""
    return {"ab": ab, "current": current, "version": version, "other_version": other_v}


def now_utc():
    """Now (RQ_NOW overrides, for tests)."""
    return parse_time(os.environ.get("RQ_NOW", "")) or datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _device():
    version = read_first_line(os.environ.get("RQ_VERSION_FILE") or VERSION_FILE)
    return device_from_status(read_slot_status(), version)


def _report(advices, device, data):
    lines = []
    for a in advices:
        if a["kind"] == "update":
            lines.append(headline(a, device))
            warning = warning_text(a, device)[0]
            if warning:
                lines.append("  " + warning)
        elif a["kind"] == "withdrawn":
            lines.append(f"This release ({a['tag']}) was withdrawn"
                         + (f": {a['reason']}" if a["reason"] else "."))
    if data.get("releases") is None:
        lines.append("No release list yet (offline?).")
    elif not lines:
        lines.append("Nothing new for this Pi.")
    return "\n".join(lines)


def main(argv=None):
    """Command line; see the module docstring."""
    argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__.split("Usage:", 1)[1].split("Environment", 1)[0].rstrip())
        return 0
    if argv[:1] == ["--bucket"]:
        if len(argv) < 2:
            print("Usage: rq_release_notice.py --bucket TAG", file=sys.stderr)
            return 1
        print(rollout_bucket(device_serial(), argv[1]))
        return 0
    system = "--system" in argv
    cache = system_cache_dir() if system else user_cache_dir()
    if "--refresh" in argv:
        fetch_all(cache, now_utc())
    dirs = [cache] if system else [user_cache_dir(), system_cache_dir()]
    data = load_all(dirs)
    device = _device()
    advices = advise(device, data["releases"], data["controls"], device_serial(), now_utc())
    if "--line" in argv:
        line = login_line(advices, device)
        if line:
            print(line)
        return 0
    if system and "--refresh" in argv:
        notice = os.environ.get("RQ_NOTICE_FILE") or NOTICE_FILE
        line = login_line(advices, device)
        try:
            if line:
                _write_atomic(notice, line + "\n")
            elif os.path.exists(notice):
                os.unlink(notice)
        except OSError as e:
            print(f"Could not write {notice}: {e}", file=sys.stderr)
    print(_report(advices, device, data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
