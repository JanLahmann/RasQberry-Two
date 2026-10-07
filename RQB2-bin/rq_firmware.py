#!/usr/bin/env python3
"""
RasQberry: is the Pi's bootloader firmware (EEPROM) outdated?

An old EEPROM causes real problems: on a Pi 5 with the 2025-05-08 EEPROM the
firmware crypto service was missing, so Raspberry Pi Connect from Imager could
not sign in ("could not read device identity", user test 2026-10-07). This
finds such a Pi and says so. It never updates the firmware: it points to
Raspberry Pi's own tools (Jan, 2026-10-07).

  check [--write]  look now (root): the EEPROM date, whether rpi-eeprom-update
                   has a newer one, on a Pi 5 whether the crypto service works
                   (rpi-fw-crypto get-num-otp-keys). --write saves the result
                   to /run/rasqberry/firmware-status for System Info, the setup
                   checklist and the desktop notice (rasqberry-firmware-check
                   .service runs this at start-up).
  line             one line for System Info: "8 May 2025 (update available)"
  due              exit 0 when an update should be suggested (and print the
                   notice text): an update is available and the firmware is
                   older than about six months, or the crypto service fails
  howto            the notice text and how to update, for the checklist
  ab-bootfs        (root, at start-up) on an A/B card, set BOOTFS=/boot/config
                   in /etc/default/rpi-eeprom-update, so that Raspberry Pi's
                   own tools (rpi-eeprom-update -a, raspi-config's Bootloader
                   Version) stage the update on the card's first partition.
                   The Pi 4 boot ROM loads recovery.bin from there only; one in
                   a slot's boot partition stops the Pi from starting
                   (raspberrypi/rpi-eeprom#499). Idempotent; a BOOTFS line that
                   is there already is left alone; nothing on a standard card.

Environment (tests): RQ_FIRMWARE_STATUS, RQ_DT_BOOTLOADER_DIR, RQ_DT_COMPATIBLE,
  RQ_EEPROM_UPDATE, RQ_FW_CRYPTO, RQ_BOOT_CONFIG_DIR, RQ_EEPROM_DEFAULTS,
  RQ_BOOT_CONFIG_SOURCE
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

STATUS_FILE = os.environ.get("RQ_FIRMWARE_STATUS") or "/run/rasqberry/firmware-status"
DT_BOOTLOADER = os.environ.get("RQ_DT_BOOTLOADER_DIR") or "/proc/device-tree/chosen/bootloader"
DT_COMPATIBLE = os.environ.get("RQ_DT_COMPATIBLE") or "/proc/device-tree/compatible"
EEPROM_UPDATE = os.environ.get("RQ_EEPROM_UPDATE") or "rpi-eeprom-update"
FW_CRYPTO = os.environ.get("RQ_FW_CRYPTO") or "rpi-fw-crypto"
BOOT_CONFIG = os.environ.get("RQ_BOOT_CONFIG_DIR") or "/boot/config"
EEPROM_DEFAULTS = os.environ.get("RQ_EEPROM_DEFAULTS") or "/etc/default/rpi-eeprom-update"

OLD_DAYS = 182          # "older than about six months"
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
# Raspberry Pi's guide: raspi-config's Bootloader Version, rpi-eeprom-update
DOC_URL = ("https://www.raspberrypi.com/documentation/computers/raspberry-pi.html"
           "#update-the-bootloader-configuration")
# The command on a line of its own, so it can be selected and copied (over
# VNC, too); the desktop notice shows the three parts with a Copy button
UPDATE_CMD = "sudo rpi-eeprom-update -a"
HOWTO_INTRO = "To update, run this in a terminal, then restart:"
HOWTO_OR = "Or: sudo raspi-config, Advanced Options, Bootloader Version."
HOWTO = f"{HOWTO_INTRO}\n\n    {UPDATE_CMD}\n\n{HOWTO_OR}"


# ---------------------------------------------------------------------------
# Pure parts (tests feed these strings and dicts)
# ---------------------------------------------------------------------------

def model_of(compatible):
    """'pi5' (BCM2712), 'pi4' (BCM2711) or 'other' from the device-tree compatible list."""
    text = (compatible or "").replace("\0", " ")
    if "bcm2712" in text:
        return "pi5"
    if "bcm2711" in text:
        return "pi4"
    return "other"


def parse_eeprom_update(text, rc):
    """
    The bootloader part of rpi-eeprom-update's output (the VL805 lines that
    follow have CURRENT/LATEST too: only the first pair counts).

    Args:
        text (str): stdout of rpi-eeprom-update
        rc (int): its exit code (0 up to date, 1 update available)

    Returns:
        dict: current_ts, latest_ts (int or None), update ('yes'|'no'|'unknown')
    """
    current = latest = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        for key in ("CURRENT:", "LATEST:"):
            if line.startswith(key) and line.endswith(")") and "(" in line:
                value = line.rsplit("(", 1)[1].rstrip(")")
                if value.isdigit():
                    if key == "CURRENT:" and current is None:
                        current = int(value)
                    elif key == "LATEST:" and latest is None:
                        latest = int(value)
        if line.startswith("VL805"):
            break
    if rc == 1:
        update = "yes"
    elif rc == 0:
        update = "no"
    else:
        update = "unknown"
    if update == "unknown" and current and latest:
        update = "yes" if latest > current else "no"
    return {"current_ts": current, "latest_ts": latest, "update": update}


def date_text(ts):
    """'8 May 2025' (UTC), '' without a timestamp."""
    if not ts:
        return ""
    t = time.gmtime(int(ts))
    return f"{t.tm_mday} {MONTHS[t.tm_mon - 1]} {t.tm_year}"


def assess(status, now):
    """
    What the status means.

    Args:
        status (dict): the status file (strings)
        now (float): seconds since the epoch

    Returns:
        dict: date (str), update ('yes'|'no'|'unknown'), old (bool),
        crypto ('ok'|'fail'|'na'), due (bool: suggest the update), key (str:
        the firmware version the notice is about), connect (bool: say that it
        fixes Raspberry Pi Connect from Imager)
    """
    try:
        current = int(status.get("current_ts") or 0)
    except ValueError:
        current = 0
    update = status.get("update") or "unknown"
    crypto = status.get("crypto") or "na"
    old = bool(current) and (now - current) > OLD_DAYS * 86400
    due = update == "yes" and (old or crypto == "fail")
    return {"date": date_text(current), "update": update, "old": old, "crypto": crypto,
            "due": due, "key": str(current or ""),
            "connect": status.get("model") == "pi5" or crypto == "fail"}


def info_line(status, now):
    """System Info: '8 May 2025 (update available)'."""
    a = assess(status, now)
    if not a["date"]:
        return "unknown"
    note = {"yes": "update available", "no": "up to date"}.get(a["update"], "")
    if a["crypto"] == "fail":
        note = (note + ", " if note else "") + "crypto service missing"
    return f"{a['date']} ({note})" if note else a["date"]


def notice_text(status, now):
    """The desktop notice and the checklist's reason, in one or two sentences."""
    a = assess(status, now)
    text = f"The Pi's firmware is from {a['date'] or 'an older release'}."
    if a["connect"]:
        return text + " A newer version fixes problems, e.g. Raspberry Pi Connect from Imager."
    return text + " A newer version fixes problems."


def status_lines(model, eeprom, crypto, checked):
    """The status file's key=value lines."""
    return [f"model={model}",
            f"current_ts={eeprom.get('current_ts') or ''}",
            f"latest_ts={eeprom.get('latest_ts') or ''}",
            f"update={eeprom.get('update') or 'unknown'}",
            f"crypto={crypto}",
            f"checked={int(checked)}"]


def is_first_partition(source):
    """/dev/mmcblk0p1, /dev/sda1, /dev/nvme0n1p1: partition 1 of its disk."""
    return bool(re.search(r"(?:\dp1|[a-z]1)$", source or ""))


def with_bootfs(text, bootfs):
    """
    /etc/default/rpi-eeprom-update with BOOTFS set, or None when nothing
    changes: a BOOTFS line that is there already (ours or someone else's)
    is left alone; every other line stays as it is.
    """
    for raw in (text or "").splitlines():
        if re.match(r"\s*(export\s+)?BOOTFS=", raw):
            return None
    out = text or ""
    if out and not out.endswith("\n"):
        out += "\n"
    return out + ("# RasQberry A/B card: the boot ROM loads recovery.bin only from the\n"
                  "# card's first partition (CONFIG), not from a slot's /boot/firmware\n"
                  f"BOOTFS={bootfs}\n")


# ---------------------------------------------------------------------------
# Files and commands
# ---------------------------------------------------------------------------

def read_status(path=None):
    """The status file as a dict ({} when missing)."""
    out = {}
    try:
        with open(path or STATUS_FILE) as f:
            for raw in f:
                if "=" in raw:
                    k, v = raw.rstrip("\n").split("=", 1)
                    out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _write_atomic(path, text, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def write_status(lines, path=None):
    """Write the status file atomically, readable by everyone."""
    _write_atomic(path or STATUS_FILE, "\n".join(lines) + "\n", 0o644)


def _read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def dt_timestamp():
    """The running bootloader's build time from the device tree (None if unknown)."""
    raw = _read_bytes(os.path.join(DT_BOOTLOADER, "build-timestamp"))
    return int.from_bytes(raw[:4], "big") if len(raw) >= 4 else None


def _run(argv, timeout=60, env=None):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return None, ""


def check():
    """Look now: (model, eeprom dict, crypto)."""
    model = model_of(_read_bytes(DT_COMPATIBLE).decode("ascii", "replace"))
    if model == "other":
        return model, {"current_ts": None, "latest_ts": None, "update": "unknown"}, "na"
    rc, out = _run([EEPROM_UPDATE])
    eeprom = parse_eeprom_update(out, rc if rc is not None else -1)
    if not eeprom["current_ts"]:
        eeprom["current_ts"] = dt_timestamp()
    crypto = "na"
    if model == "pi5" and shutil.which(FW_CRYPTO):
        rc, _ = _run([FW_CRYPTO, "get-num-otp-keys"], timeout=15)
        crypto = "ok" if rc == 0 else "fail"
    return model, eeprom, crypto


def current_status():
    """The saved status; without one, at least the running firmware's date."""
    status = read_status()
    if not status.get("current_ts"):
        ts = dt_timestamp()
        if ts:
            status = {"current_ts": str(ts), "update": "unknown"}
    return status


def config_source():
    """The device mounted at the CONFIG mount point ('' if none)."""
    if "RQ_BOOT_CONFIG_SOURCE" in os.environ:
        return os.environ["RQ_BOOT_CONFIG_SOURCE"]
    rc, out = _run(["findmnt", "-n", "-o", "SOURCE", "--mountpoint", BOOT_CONFIG], timeout=10)
    return out.strip() if rc == 0 else ""


def ab_bootfs():
    """
    BOOTFS=/boot/config for Raspberry Pi's EEPROM tools on an A/B card: the
    CONFIG partition holds autoboot.txt and is the card's first partition.
    Returns a short message (for the journal).
    """
    if not os.path.isfile(os.path.join(BOOT_CONFIG, "autoboot.txt")):
        return "not an A/B card: nothing to do"
    source = config_source()
    if not is_first_partition(source):
        return f"{BOOT_CONFIG} is not the card's first partition ({source or 'not mounted'}): nothing to do"
    try:
        with open(EEPROM_DEFAULTS) as f:
            text = f.read()
        mode = os.stat(EEPROM_DEFAULTS).st_mode & 0o777
    except OSError:
        text, mode = "", 0o644
    new = with_bootfs(text, BOOT_CONFIG)
    if new is None:
        return f"{EEPROM_DEFAULTS} has a BOOTFS line already"
    _write_atomic(EEPROM_DEFAULTS, new, mode)
    return f"BOOTFS={BOOT_CONFIG} added to {EEPROM_DEFAULTS}"


def main(argv=None):
    """Command line: check, line, due, howto, ab-bootfs."""
    p = argparse.ArgumentParser(description="RasQberry firmware (EEPROM) check")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("--write", action="store_true")
    sub.add_parser("line")
    sub.add_parser("due")
    sub.add_parser("howto")
    sub.add_parser("ab-bootfs")
    args = p.parse_args(argv)
    if args.cmd == "check":
        model, eeprom, crypto = check()
        lines = status_lines(model, eeprom, crypto, time.time())
        if args.write:
            try:
                write_status(lines)
            except OSError as e:
                print(f"cannot write {STATUS_FILE}: {e}", file=sys.stderr)
        print("\n".join(lines))
        return 0
    if args.cmd == "line":
        print(info_line(current_status(), time.time()))
        return 0
    if args.cmd in ("due", "howto"):
        status = read_status()
        due = assess(status, time.time())["due"]
        if args.cmd == "howto":
            print(notice_text(status, time.time()) + "\n\n" + HOWTO + "\n\nDetails: " + DOC_URL)
        elif due:
            print(notice_text(status, time.time()))
        return 0 if due else 1
    if args.cmd == "ab-bootfs":
        try:
            print(ab_bootfs())
        except OSError as e:
            print(f"cannot set BOOTFS: {e}", file=sys.stderr)
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
