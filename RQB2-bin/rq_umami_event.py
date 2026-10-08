#!/usr/bin/env python3
"""
RasQberry: anonymous usage counts for the project's Umami statistics.

The Pi sends four events to the Umami website that rasqberry.org already uses
(names "RasQberry Two: <what happened>", as on the website):

  RasQberry Two: first start    version, stream, model, card, imager
      once per newly written card, at its first complete start (health check)
  RasQberry Two: update check   version, stream, model, card, update
      once a day per Pi (rasqberry-update-check.service, as root)
  RasQberry Two: update result  from, to, result, reason
      after the trial start of a slot an update wrote: "worked" (sent by the
      updated slot) or "didn't work" (sent by the slot that runs again)
  RasQberry Two: update notice  action, tag
      the taskbar's update notice: "whats-new" opened, "install" clicked
  RasQberry Two: demo start     demo, how, version, model
      every demo start through the demo engine (rq_demo_run.sh); demo is the
      manifest id (id:variant), how "menu", "desktop" or "learning-path" when
      the engine knows; the demo loop's starts are not counted
  RasQberry Two: learning path  path, action
      rq_learning_paths.sh: "start" (first step opened), "finish" (completed)
  RasQberry Two: LED stall      model, brightness
      the Pi 5 LED driver stalled (rq_led_utils.py); at most once per start

No IDs: never the serial number, /etc/machine-id, the hostname, an IP address
or a user name. Each event has a fixed list of data keys (DATA_KEYS); values
are short words, versions and release tags. Like any web server, Umami sees
the sender's IP address; it keeps a monthly salted hash of it and the user
agent as its "session".

Best effort: one POST with a 3 s limit (the name lookup included), never an
exception, never a failed caller; offline nothing is sent. "first start" and
"update result" wait in a small queue (/var/lib/rasqberry/umami/queue) until a
send works, so a Pi that is offline at that moment still counts later.

User agent: "Mozilla/5.0 (X11; Linux aarch64) RasQberry/<version> (Raspberry
Pi 5)". Umami drops what isbot calls a bot, with HTTP 200 and {"beep": "boop"}:
Python's own "Python-urllib/3.x" (and curl) are bots there. The version is in
the user agent only when it looks like a release tag; a feature-branch build
(dev-url-fix-...) could contain one of isbot's words, so it gets its stream.

Usage:
  rq_umami_event.py daily                     queued events, then the update
                                              check (once a day; root)
  rq_umami_event.py flush                     send queued events (root)
  rq_umami_event.py update-notice ACTION TAG  (rq_slot_indicator.py)
  rq_umami_event.py demo-start ID[:VARIANT] [HOW]   (rq_demo_run.sh)
  rq_umami_event.py learning-path ID start|finish  (rq_learning_paths.sh)
  rq_umami_event.py led-stall [BRIGHTNESS]    (rq_led_utils.py; once per start)
  rq_umami_event.py test [source=VALUE]       send "RasQberry Two: test event"
                                              and print Umami's reply
The health check calls boot_started() and boot_finished(). Shell scripts send
in the background with rq_count_event (rq_common.sh).

Environment: RQ_UMAMI=0 sends nothing (also read from
  /usr/config/rasqberry_environment.env, for rig and development Pis).
  Tests: RQ_UMAMI_URL, RQ_UMAMI_STATE, RQ_UMAMI_RUN_DIR, RQ_UMAMI_ENV_FILE, RQ_VERSION_FILE,
  RQ_DT_MODEL, RQ_MEMINFO, RQ_HEALTH_STATUS, RQ_IMAGER_STATE, RQ_NOW and the
  variables of rq_release_notice.py (RQ_SLOT_STATUS_FILE, RQ_SYSTEM_CACHE_DIR,
  RQ_SERIAL).
"""

import fcntl
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.request
from datetime import timedelta

sys.dont_write_bytecode = True     # root runs: no __pycache__ in /usr/bin
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rq_release_notice as rn  # noqa: E402

log = logging.getLogger("rq_umami_event")

ENDPOINT = "https://cloud.umami.is/api/send"
WEBSITE_ID = "97f347ac-e7ba-4be3-b26f-ab4b328bdbf2"
HOSTNAME = "rasqberry.org"
PREFIX = "RasQberry Two: "
TIMEOUT = 3
FLUSH_SECONDS = 12
QUEUE_MAX = 20
QUEUE_DAYS = 60

# The only data each event may carry
DATA_KEYS = {
    "first start": ("version", "stream", "model", "card", "imager"),
    "update check": ("version", "stream", "model", "card", "update"),
    "update result": ("from", "to", "result", "reason"),
    "update notice": ("action", "tag"),
    "demo start": ("demo", "how", "version", "model"),
    "learning path": ("path", "action"),
    "LED stall": ("model", "brightness"),
    "test event": ("source",),
}
NOTICE_ACTIONS = ("whats-new", "install")
DEMO_HOW = ("menu", "desktop", "learning-path")
PATH_ACTIONS = ("start", "finish")
CARD = {"ab": "ab-dual", "single": "ab-single", "standard": "standard"}
# What the A/B code leaves on CONFIG once a card has run (as in
# rq_imager_firstrun.sh): a newly written card has none until its first
# confirmed start
AB_HISTORY = ("target-slot", "slot-confirmed", "current-slot")
FAILED_NOTICE = "last-switch-failed"
RELEASE_TAG = re.compile(r"(beta|development|stable)-\d{4}-\d{2}-\d{2}(-\d{6})?|v?\d+\.\d+\.\d+")

STATE_DIR = "/var/lib/rasqberry/umami"
RUN_DIR = "/dev/shm"           # tmpfs: empty at every start
ENV_FILE = "/usr/config/rasqberry_environment.env"
VERSION_FILE = "/etc/rasqberry-version"
DT_MODEL = "/proc/device-tree/model"
MEMINFO = "/proc/meminfo"
HEALTH_STATUS = "/var/lib/rasqberry-health-check.status"
IMAGER_STATE = "/var/lib/rasqberry"

LAST_REPLY = {}


# ---------------------------------------------------------------------------
# Switch, paths, facts
# ---------------------------------------------------------------------------

def _env_file_value(key):
    """KEY=value from the RasQberry environment file ('' if not there)."""
    path = os.environ.get("RQ_UMAMI_ENV_FILE") or ENV_FILE
    value = ""
    try:
        with open(path) as f:
            for line in f:
                m = re.match(rf"\s*(?:export\s+)?{key}=(.*)$", line)
                if m:
                    value = m.group(1).split("#", 1)[0].strip().strip("'\"")
    except OSError:
        pass
    return value


def enabled():
    """False when RQ_UMAMI is 0/false/no/off (environment, else the environment file)."""
    value = os.environ.get("RQ_UMAMI")
    if value is None:
        value = _env_file_value("RQ_UMAMI")
    return value.strip().lower() not in ("0", "false", "no", "off")


def state_dir():
    """Where the queue and the once-only markers are (one per system/slot)."""
    return os.environ.get("RQ_UMAMI_STATE") or STATE_DIR


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def version():
    """This system's version (/etc/rasqberry-version), 'unknown' if not there."""
    return rn.read_first_line(os.environ.get("RQ_VERSION_FILE") or VERSION_FILE) or "unknown"


def ram_gb(meminfo=None):
    """RAM size as sold (1, 2, 4, 8, 16 GB ...) from MemTotal; 0 if unknown."""
    try:
        with open(meminfo or os.environ.get("RQ_MEMINFO") or MEMINFO) as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    gib = int(line.split()[1]) / (1024 * 1024)
                    size = 1
                    while size < gib and size < 1024:
                        size *= 2
                    return size
    except (OSError, ValueError, IndexError):
        pass
    return 0


def board():
    """
    The board, without anything that identifies it.

    Returns:
        tuple: (model, label) - e.g. ('pi5-8gb', 'Raspberry Pi 5'),
        ('pi4-4gb', 'Raspberry Pi 4'), ('cm4-2gb', 'Raspberry Pi Compute Module 4'),
        ('other', 'Raspberry Pi')
    """
    try:
        with open(os.environ.get("RQ_DT_MODEL") or DT_MODEL, "rb") as f:
            text = f.read().replace(b"\0", b"").decode("ascii", "ignore")
    except OSError:
        text = ""
    m = re.search(r"Raspberry Pi (Compute Module )?(\d+)", text)
    if m:
        kind = ("cm" if m.group(1) else "pi") + m.group(2)
        label = "Raspberry Pi " + (m.group(1) or "") + m.group(2)
    else:
        kind, label = "other", "Raspberry Pi"
    gb = ram_gb()
    return (f"{kind}-{gb}gb" if gb else kind), label


def card(ver=None):
    """'ab-dual' (two systems), 'ab-single' (A/B image, one system) or 'standard'."""
    device = rn.device_from_status(rn.read_slot_status(), ver or version())
    return CARD.get(device.get("card"), "standard")


def facts():
    """version, stream, model, card: what 'first start' and 'update check' share."""
    ver = version()
    return {"version": ver, "stream": rn.version_stream(ver), "model": board()[0],
            "card": card(ver)}


def imager_customised():
    """'yes' when Raspberry Pi Imager's OS customisation was applied (rq_imager_firstrun.sh)."""
    base = os.environ.get("RQ_IMAGER_STATE") or IMAGER_STATE
    return "yes" if os.path.exists(os.path.join(base, "imager-customised")) else "no"


# ---------------------------------------------------------------------------
# The request
# ---------------------------------------------------------------------------

def user_agent(ver=None, label=None):
    """A browser-like user agent that isbot does not drop (see the module docstring)."""
    ver = ver or version()
    shown = ver if RELEASE_TAG.fullmatch(ver) else rn.version_stream(ver)
    return f"Mozilla/5.0 (X11; Linux aarch64) RasQberry/{shown} ({label or board()[1]})"


def _value(value):
    """A data value: a short string of plain characters."""
    return re.sub(r"[^A-Za-z0-9._:+' -]", "", str(value))[:48]


def build_payload(event, data):
    """
    The JSON body Umami's /api/send takes.

    Args:
        event (str): 'first start', 'update check', ... (with or without PREFIX)
        data (dict): only the keys DATA_KEYS lists for the event are kept

    Returns:
        dict

    Raises:
        ValueError: an event that is not in DATA_KEYS
    """
    event = event[len(PREFIX):] if event.startswith(PREFIX) else event
    if event not in DATA_KEYS:
        raise ValueError(f"unknown event: {event}")
    clean = {k: _value(data[k]) for k in DATA_KEYS[event]
             if data.get(k) not in (None, "")}
    return {"type": "event",
            "payload": {"website": WEBSITE_ID, "hostname": HOSTNAME,
                        "url": "/pi/" + re.sub(r"[^a-z0-9]+", "-", event.lower()),
                        "name": PREFIX + event, "data": clean, "language": "en"}}


def _post(body, agent, url, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(4096).decode("utf-8", "replace")


def send(event, data, timeout=TIMEOUT):
    """
    Send one event now. Never raises and never takes much longer than
    <timeout> seconds: the request runs in a daemon thread, so a hanging name
    lookup cannot hold up the caller either.

    Returns:
        bool: Umami answered 2xx
    """
    LAST_REPLY.clear()
    if not enabled():
        return False
    try:
        body = build_payload(event, data)
        agent = user_agent()
        url = os.environ.get("RQ_UMAMI_URL") or ENDPOINT
    except Exception as e:  # noqa: BLE001 - best effort
        log.info("usage count %s not sent: %s", event, e)
        return False
    result = {}

    def work():
        try:
            result["reply"] = _post(body, agent, url, timeout)
        except Exception as e:  # noqa: BLE001 - offline, HTTP error, anything
            result["error"] = str(e)

    worker = threading.Thread(target=work, name="umami", daemon=True)
    worker.start()
    worker.join(timeout + 0.5)
    status, text = result.get("reply") or (None, "")
    LAST_REPLY.update(status=status, body=text, error=result.get("error", "timeout" if not result else ""))
    ok = status is not None and 200 <= status < 300
    if not ok:
        log.info("usage count %s not sent: %s", event, status or LAST_REPLY["error"])
    elif '"beep"' in text:
        log.warning("usage count %s: Umami took the user agent for a bot", event)
    return ok


# ---------------------------------------------------------------------------
# Queue (first start, update results): kept until a send works
# ---------------------------------------------------------------------------

def _queue_dir():
    return os.path.join(state_dir(), "queue")


def queue_event(event, data, now=None):
    """Keep an event for flush(). The oldest go when more than QUEUE_MAX wait."""
    now = now or rn.now_utc()
    qdir = _queue_dir()
    os.makedirs(qdir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", event.lower())
    name = f"{now.strftime('%Y%m%dT%H%M%S')}-{time.monotonic_ns() % 10**9:09d}-{slug}.json"
    _write(os.path.join(qdir, name),
           json.dumps({"event": event, "data": data, "queued": now.isoformat()}))
    for old in sorted(os.listdir(qdir))[:-QUEUE_MAX]:
        os.unlink(os.path.join(qdir, old))


def queued():
    """The waiting events, oldest first: list of (path, entry)."""
    qdir = _queue_dir()
    try:
        names = sorted(n for n in os.listdir(qdir) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        path = os.path.join(qdir, n)
        try:
            with open(path) as f:
                out.append((path, json.load(f)))
        except (OSError, ValueError):
            os.unlink(path)
    return out


def flush(seconds=FLUSH_SECONDS, now=None):
    """
    Send the waiting events, oldest first. Stops at the first one that cannot
    be sent (offline) and after <seconds>; drops events older than QUEUE_DAYS.
    Another flush running at the same time (health check, daily timer): returns.

    Returns:
        int: events sent
    """
    if not enabled():
        return 0
    now = now or rn.now_utc()
    os.makedirs(state_dir(), exist_ok=True)
    with open(os.path.join(state_dir(), ".lock"), "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return 0
        sent, end = 0, time.monotonic() + seconds
        for path, entry in queued():
            when = rn.parse_time(entry.get("queued"))
            if when is None or now - when > timedelta(days=QUEUE_DAYS):
                os.unlink(path)
                continue
            if time.monotonic() >= end or not send(entry.get("event", ""), entry.get("data") or {}):
                break
            os.unlink(path)
            sent += 1
        return sent


# ---------------------------------------------------------------------------
# First start and update results (health check, every start, as root)
# ---------------------------------------------------------------------------

def is_new_card(config_dir):
    """
    Is this start the first complete start of a newly written card?

    No when this system has run the health check before (an older RasQberry
    brought up to date in place), and on an A/B card that has started before
    (AB_HISTORY on CONFIG): a slot an update wrote starts on such a card, so
    it does not count as a new card. Called before the health check confirms
    the slot, which writes those markers.
    """
    if os.path.exists(os.environ.get("RQ_HEALTH_STATUS") or HEALTH_STATUS):
        return False
    config_dir = str(config_dir)
    if os.path.exists(os.path.join(config_dir, "autoboot.txt")):
        return not any(os.path.exists(os.path.join(config_dir, m)) for m in AB_HISTORY)
    return True


def boot_started(config_dir, probation=None):
    """
    The health check, before it confirms the slot: decide once per system
    whether it is the first start of a new card, and keep the update hint of
    a trial start (slot-<X>-updated; confirming removes it).

    Args:
        config_dir: the CONFIG partition (/boot/config)
        probation (str): the slot on its trial start, or None

    Returns:
        dict: for boot_finished()
    """
    ctx = {}
    if not enabled():
        return ctx
    marker = os.path.join(state_dir(), "first-start")
    if not _read(marker):
        _write(marker, "new\n" if is_new_card(config_dir) else "not-new\n")
    if probation:
        hint = os.path.join(str(config_dir), f"slot-{probation}-updated")
        if os.path.exists(hint):
            ctx["updated"] = dict(rn.read_kv(hint), slot=probation)
    return ctx


def queue_first_start():
    """Queue 'first start' once, when boot_started() found a new card."""
    marker = os.path.join(state_dir(), "first-start")
    if _read(marker) != "new":
        return False
    queue_event("first start", dict(facts(), imager=imager_customised()))
    _write(marker, "queued\n")
    return True


def failure_reason(text):
    """A short word for the reason in last-switch-failed (rq_health_check.py)."""
    text = (text or "").lower()
    if "desktop" in text:
        return "desktop-timeout"
    if "not confirmed" in text:
        return "start-timeout"
    if "tried twice" in text or "without success" in text:
        return "no-boot"
    if "virtual environment" in text or "python setup" in text or "qiskit" in text:
        return "health-check"
    return "other"


def _slot_version(text):
    text = (text or "").strip()
    return text if text and text not in rn.NOT_A_VERSION else "unknown"


def queue_update_results(ctx, config_dir, running_slot, confirmed):
    """
    'update result' events the start that just finished decided:
      worked       this slot was on its trial start after an update, and
                   the health check confirmed it
      didn't work  last-switch-failed says an update (update=yes) of the
                   OTHER slot failed: the Pi came back to this one. Once per
                   notice (its slot, time and version).
    Plain switches (no slot-<X>-updated, update=no) are not counted.
    """
    hint = ctx.get("updated")
    if confirmed and hint and hint.get("slot") == running_slot:
        other = {"A": "B", "B": "A"}[running_slot]
        status = rn.read_slot_status()
        queue_event("update result", {"from": _slot_version(status.get(f"slot_{other.lower()}")),
                                      "to": hint.get("version") or version(),
                                      "result": "worked", "reason": "health-check"})
    notice = rn.read_kv(os.path.join(str(config_dir), FAILED_NOTICE))
    slot = notice.get("slot")
    if notice.get("update") != "yes" or slot not in ("A", "B") or slot == running_slot:
        return
    key = f"{slot}|{notice.get('time', '')}|{notice.get('version', '')}"
    seen_path = os.path.join(state_dir(), "update-results")
    seen = _read(seen_path).splitlines()
    if key in seen:
        return
    queue_event("update result", {"from": version(), "to": _slot_version(notice.get("version")),
                                  "result": "didn't work",
                                  "reason": failure_reason(notice.get("detail") or notice.get("reason"))})
    _write(seen_path, "\n".join((seen + [key])[-QUEUE_MAX:]) + "\n")


def boot_finished(ctx, config_dir, running_slot, confirmed):
    """
    The health check, at its end: queue what this start decided (first start,
    update results), then send the queue. Never raises.
    """
    if not enabled():
        return
    for step in (queue_first_start,
                 lambda: queue_update_results(ctx, config_dir, running_slot, confirmed),
                 flush):
        try:
            step()
        except Exception as e:  # noqa: BLE001 - never part of the health check's result
            log.info("usage counts: %s", e)


# ---------------------------------------------------------------------------
# Daily update check (rasqberry-update-check.service)
# ---------------------------------------------------------------------------

def update_status(device, data, serial, now):
    """
    'available' (an update is offered to this Pi), 'withdrawn-seen' (the
    running release, or a newer one of a stream it follows, was withdrawn)
    or 'none'.
    """
    advices = rn.advise(device, data.get("releases"), data.get("controls") or {}, serial, now)
    if rn.updates(advices):
        return "available"
    if any(a["kind"] == "withdrawn" for a in advices):
        return "withdrawn-seen"
    running = device.get("version", "")
    s_run = rn.stream_of(running)
    for stream, (tag, entry) in rn.heads(data.get("releases")).items():
        if (s_run and rn.RANK[stream] >= rn.rank(s_run)
                and rn.is_withdrawn(data.get("controls") or {}, tag)[0]
                and rn.is_newer(tag, entry, running)):
            return "withdrawn-seen"
    return "none"


def daily(now=None):
    """
    Once a day per Pi: send what waits in the queue, then 'update check' -
    once per UTC day, from the release data the timer has just fetched into
    /var/cache/rasqberry.

    Returns:
        bool: 'update check' was sent now
    """
    if not enabled():
        return False
    now = now or rn.now_utc()
    for step in (queue_first_start, flush):
        try:
            step()
        except Exception as e:  # noqa: BLE001
            log.info("usage counts: %s", e)
    day_path = os.path.join(state_dir(), "update-check-day")
    today = now.date().isoformat()
    if _read(day_path) == today:
        return False
    data = rn.load_all([rn.system_cache_dir()])
    info = facts()
    device = rn.device_from_status(rn.read_slot_status(), info["version"])
    info["update"] = update_status(device, data, rn.device_serial(), now)
    if not send("update check", info):
        return False
    _write(day_path, today + "\n")
    return True


# ---------------------------------------------------------------------------
# Demos, learning paths, LED stalls (as the user or root, in the background)
# ---------------------------------------------------------------------------

def once_this_start(name):
    """
    True the first time in this start of the Pi, for any user: a marker in
    /dev/shm (tmpfs, empty after every restart), created exclusively.
    """
    path = os.path.join(os.environ.get("RQ_UMAMI_RUN_DIR") or RUN_DIR, f"rasqberry-umami-{name}")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError:
        return False
    os.close(fd)
    return True


def demo_start(demo, how=""):
    """'demo start' for ID or ID:VARIANT; how only when it is one of DEMO_HOW."""
    return send("demo start", {"demo": demo, "how": how if how in DEMO_HOW else "",
                               "version": version(), "model": board()[0]})


def led_stall(brightness=""):
    """'LED stall', at most once per start of the Pi."""
    if not enabled() or not once_this_start("led-stall"):
        return False
    return send("LED stall", {"model": board()[0], "brightness": brightness})


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main(argv=None):
    """Command line; see the module docstring. Exit 0 unless the usage is wrong
    (or, for 'test', the event was not accepted)."""
    argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = argv[0] if argv else ""
    try:
        if cmd == "daily":
            daily()
        elif cmd == "flush":
            flush()
        elif cmd == "update-notice" and len(argv) == 3 and argv[1] in NOTICE_ACTIONS:
            send("update notice", {"action": argv[1], "tag": argv[2]})
        elif cmd == "demo-start" and len(argv) in (2, 3):
            demo_start(argv[1], argv[2] if len(argv) == 3 else "")
        elif cmd == "learning-path" and len(argv) == 3 and argv[2] in PATH_ACTIONS:
            send("learning path", {"path": argv[1], "action": argv[2]})
        elif cmd == "led-stall" and len(argv) <= 2:
            led_stall(argv[1] if len(argv) == 2 else "")
        elif cmd == "test":
            data = dict(a.split("=", 1) for a in argv[1:] if "=" in a) or {"source": "dev-test"}
            ok = send("test event", data)
            print(f"HTTP {LAST_REPLY.get('status')}: {LAST_REPLY.get('body') or LAST_REPLY.get('error')}"
                  if enabled() else "RQ_UMAMI=0: nothing sent")
            return 0 if ok else 1
        else:
            print(__doc__.split("Usage:", 1)[1].split("Environment", 1)[0].rstrip(), file=sys.stderr)
            return 2
    except Exception as e:  # noqa: BLE001 - never fail a timer or a click
        log.info("usage counts: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
