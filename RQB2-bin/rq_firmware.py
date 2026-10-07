#!/usr/bin/env python3
"""
RasQberry: is the Pi's bootloader firmware (EEPROM) outdated?

An old EEPROM causes real problems: on a Pi 5 with the 2025-05-08 EEPROM the
firmware crypto service was missing, so Raspberry Pi Connect from Imager could
not sign in ("could not read device identity", user test 2026-10-07). This
finds such a Pi and offers the update. It never updates on its own.

  check [--write]  look now (root): the EEPROM date, whether rpi-eeprom-update
                   has a newer one, on a Pi 5 whether the crypto service works
                   (rpi-fw-crypto get-num-otp-keys). --write saves the result
                   to /run/rasqberry/firmware-status for System Info, the setup
                   checklist and the desktop notice (rasqberry-firmware-check
                   .service runs this at start-up).
  line             one line for System Info: "8 May 2025 (update available)"
  due              exit 0 when the update should be offered (and print the
                   notice text): an update is available and the firmware is
                   older than about six months, or the crypto service fails
  update [--no-restart]
                   (root, in a terminal) ask, run rpi-eeprom-update -a, then
                   ask to restart. On an A/B card the bootloader reads the
                   update from the CONFIG partition (the first one on the
                   card), not from the slot's /boot/firmware, so BOOTFS points
                   there. --no-restart (setup checklist): say that the next
                   restart finishes it instead of asking.

Environment (tests): RQ_FIRMWARE_STATUS, RQ_DT_BOOTLOADER_DIR, RQ_DT_COMPATIBLE,
  RQ_EEPROM_UPDATE, RQ_FW_CRYPTO, RQ_BOOT_CONFIG_DIR
"""

import argparse
import os
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

OLD_DAYS = 182          # "older than about six months"
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


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
        dict: date (str), update ('yes'|'no'|'staged'|'unknown'), old (bool),
        crypto ('ok'|'fail'|'na'), due (bool: offer the update), key (str:
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
    note = {"yes": "update available", "no": "up to date",
            "staged": "update installed, finishes at the next restart"}.get(a["update"], "")
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


def eeprom_env(environ, boot_config):
    """
    rpi-eeprom-update's environment: on an A/B card BOOTFS is the CONFIG
    partition, the card's first, where the boot ROM looks for recovery.bin
    (by default it would use the slot's /boot/firmware, which the ROM never
    reads on a Pi 4).
    """
    env = dict(environ)
    if os.path.isfile(os.path.join(boot_config, "autoboot.txt")):
        env["BOOTFS"] = boot_config
    return env


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


def write_status(lines, path=None):
    """Write the status file atomically, readable by everyone."""
    path = path or STATUS_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


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


def _whiptail(*args):
    return subprocess.call(["whiptail", *args])


def update(no_restart=False):
    """The interactive update (root, in a terminal). Returns the exit code."""
    if os.geteuid() != 0:
        print("Run this with sudo: sudo rq_firmware.py update")
        return 1
    title = "Firmware update"
    print("Looking for a firmware update...")
    model, eeprom, crypto = check()
    if eeprom["update"] != "yes":
        write_status(status_lines(model, eeprom, crypto, time.time()))
        _whiptail("--title", title, "--msgbox",
                  f"The firmware is up to date ({date_text(eeprom['current_ts']) or 'unknown date'}).", "8", "64")
        return 0
    if _whiptail("--title", title, "--yes-button", "Update", "--no-button", "Cancel", "--defaultno", "--yesno",
                 f"Update the Pi's firmware?\n\nNow: {date_text(eeprom['current_ts'])}\n"
                 f"New: {date_text(eeprom['latest_ts'])}\n\n"
                 "The firmware lives in a chip on the Pi, not on the SD card. The update "
                 "finishes at the next restart: do not switch the Pi off during that restart.",
                 "14", "72") != 0:
        return 0
    print("Updating the firmware...")
    try:
        p = subprocess.run([EEPROM_UPDATE, "-a"], env=eeprom_env(os.environ, BOOT_CONFIG),
                           capture_output=True, text=True, timeout=300)
        rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        rc, out = 2, str(e)
    print(out)
    if rc != 0:
        tail = "\n".join([line for line in out.splitlines() if line.strip()][-6:])
        _whiptail("--title", title, "--msgbox",
                  f"The firmware update did not work (exit {rc}):\n\n{tail}", "16", "76")
        return rc
    eeprom["update"] = "staged"
    write_status(status_lines(model, eeprom, crypto, time.time()))
    if no_restart:
        _whiptail("--title", title, "--msgbox",
                  "The new firmware is ready. It is installed at the next restart.", "8", "70")
        return 0
    if _whiptail("--title", title, "--yes-button", "Restart now", "--no-button", "Later", "--yesno",
                 "The new firmware is ready. Restart now to install it?\n\n"
                 "Save your work first. The restart may take a little longer than usual.",
                 "11", "72") == 0:
        subprocess.call(["systemctl", "reboot"])
    return 0


def main(argv=None):
    """Command line: check, line, due, update."""
    p = argparse.ArgumentParser(description="RasQberry firmware (EEPROM) check")
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("check")
    c.add_argument("--write", action="store_true")
    sub.add_parser("line")
    sub.add_parser("due")
    u = sub.add_parser("update")
    u.add_argument("--no-restart", action="store_true")
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
    if args.cmd == "due":
        status = read_status()
        if assess(status, time.time())["due"]:
            print(notice_text(status, time.time()))
            return 0
        return 1
    if args.cmd == "update":
        return update(args.no_restart)
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
