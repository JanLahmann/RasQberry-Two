#!/usr/bin/env python3
"""
RasQberry A/B Boot Health Check

Validates that a booted system is functional and confirms the boot slot.
Runs at every boot (rasqberry-health-check.service); on an A/B card it matters
most on the first boot of a newly installed slot, which the firmware starts
once with the tryboot flag ("on probation").

Success criteria:
- the virtual environment exists and Qiskit is installed in it
- on probation with a desktop (default target graphical.target): the display
  manager came up

If all checks pass: confirms the slot (it becomes the default; no rollback).

If a check fails ON PROBATION: records the failure on the CONFIG partition
(/boot/config/last-switch-failed), clears the pending switch so it is not
retried, and reboots. The tryboot flag only lasts one boot, so the firmware
then starts the slot that worked (autoboot.txt [all]) - automatic rollback,
no power cycle needed (R-054). Outside probation a failure is only reported.
The notice's time= is this clock, or the time the switch was asked for
(switch-requested) when this clock is behind that: early in a trial boot it
may not be set yet (no RTC; see failure_time).

The other halves of the rollback safety net:
- panic=10 in both slots' cmdline.txt: a kernel that cannot start reboots
  instead of hanging (convert-to-ab-boot-v3.sh, rq_update_slot.sh)
- rq_tryboot_retry.sh arms systemd's hardware watchdog (15 s) for the
  probation boot; this script disarms it again after confirming
- rasqberry-probation.timer runs this script with --deadline 15 minutes after
  boot: a probation boot that never got confirmed (hung start-up, emergency
  mode) is rolled back the same way

Usage counts (rq_umami_event.py): before confirming, whether this is the first
start of a newly written card and whether this trial start follows an update;
at the end, "first start" and "update result" are queued and sent. Best
effort: never changes the outcome and adds at most a few seconds at the end.

Timeout: 10 minutes (configured in systemd service)
"""

import logging
import os
import pwd
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

# Paths (overridable for tests)
BOOT_CONFIG_DIR = Path(os.environ.get('RQ_BOOT_CONFIG_DIR', '/boot/config'))
DT_BOOTLOADER_DIR = Path(os.environ.get('RQ_DT_BOOTLOADER_DIR',
                                        '/proc/device-tree/chosen/bootloader'))
FAILED_NOTICE = 'last-switch-failed'
SWITCH_REQUEST = 'switch-requested'    # rq_slot_manager.sh switch-to: when, by a set clock

# Why a trial start failed, as people read it (Slot details, the taskbar
# indicator, the login line). The technical message goes to the log and to
# detail= in last-switch-failed ("virtual environment missing" read as if the
# venv were gone, rig test 2026-10-08).
REASON_VENV = "the demos' Python setup is missing"
REASON_QISKIT = "Qiskit does not work in the demos' Python setup"
REASON_DESKTOP = "the desktop did not come up"
# systemd-timesyncd creates it once the clock is synchronised (each boot: /run)
TIME_SYNCED = Path(os.environ.get('RQ_TIME_SYNCED_FILE', '/run/systemd/timesync/synchronized'))
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
WATCHDOG_MARKER = Path(os.environ.get('RQ_WATCHDOG_MARKER',
                                      '/run/rasqberry/probation-watchdog'))
SLOT_MANAGER = Path(os.environ.get('RQ_SLOT_MANAGER', '/usr/bin/rq_slot_manager.sh'))
SLOT_STATUS = Path(os.environ.get('RQ_SLOT_STATUS', '/usr/bin/rq_slot_status.sh'))
DISPLAY_MANAGER_TIMEOUT = 300      # seconds to wait for the desktop on probation
CLOCK_SYNC_WAIT = float(os.environ.get('RQ_CLOCK_SYNC_WAIT', '20'))  # NTP, before slot-confirmed
DEADLINE_MINUTES = 15              # rasqberry-probation.timer OnBootSec


def _setup_logging() -> logging.Logger:
    handlers = [logging.StreamHandler(sys.stdout)]
    log_file = os.environ.get('RQ_HEALTH_LOG', '/var/log/rasqberry-health-check.log')
    try:
        handlers.append(logging.FileHandler(log_file))
    except OSError:
        pass  # not root (tests) - stdout only
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=handlers)
    return logging.getLogger(__name__)


logger = _setup_logging()

# Anonymous usage counts: optional, never part of the check
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import rq_umami_event as usage_counts
except Exception:  # noqa: BLE001 - a broken counter must not break the check
    usage_counts = None


def desktop_user_home() -> str:
    """
    Home folder of the desktop user (uid 1000).

    Returns:
        str: its home, or /home/rasqberry when there is no uid 1000
    """
    try:
        return pwd.getpwuid(1000).pw_dir
    except KeyError:
        return '/home/rasqberry'


def load_environment() -> dict:
    """
    Load RasQberry environment configuration.

    Returns:
        dict: Environment variables
    """
    env = {}

    # Load from /usr/config/rasqberry_env-config.sh
    config_file = Path('/usr/config/rasqberry_env-config.sh')
    if config_file.exists():
        try:
            # Source the shell script and extract variables
            result = subprocess.run(
                f'source {config_file} && env',
                shell=True,
                capture_output=True,
                text=True,
                executable='/bin/bash'
            )
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    env[key] = value
        except Exception as e:
            logger.warning(f"Could not load environment config: {e}")

    # Set defaults
    # The desktop user is uid 1000, whatever its name (#319: the name typed
    # in Imager); env-config.sh does not export USER_HOME.
    env.setdefault('USER_HOME', desktop_user_home())
    env.setdefault('REPO', 'RasQberry-Two')
    env.setdefault('STD_VENV', 'RQB2')

    return env


def check_venv_exists(env: dict) -> Tuple[bool, str]:
    """
    Check if virtual environment exists.

    Args:
        env: Environment variables

    Returns:
        Tuple of (success, message)
    """
    user_home = env.get('USER_HOME')
    repo = env.get('REPO')
    std_venv = env.get('STD_VENV')

    # Check multiple possible locations
    venv_paths = [
        Path(f"{user_home}/{repo}/venv/{std_venv}"),
        Path(f"{user_home}/.local/venv/{std_venv}"),
        Path(f"{user_home}/venv/{std_venv}"),
    ]

    for venv_path in venv_paths:
        activate_script = venv_path / 'bin' / 'activate'
        if activate_script.exists():
            logger.info(f"✓ Virtual environment found: {venv_path}")
            return True, str(venv_path)

    logger.error(f"✗ Virtual environment not found in: {venv_paths}")
    return False, "Virtual environment not found"


def check_qiskit_installed(venv_path: str) -> Tuple[bool, str]:
    """
    Check if Qiskit is installed in the virtual environment.

    Args:
        venv_path: Path to virtual environment

    Returns:
        Tuple of (success, message)
    """
    pip_executable = Path(venv_path) / 'bin' / 'pip'

    if not pip_executable.exists():
        logger.error(f"✗ pip not found in venv: {pip_executable}")
        return False, "pip not found in virtual environment"

    try:
        result = subprocess.run(
            [str(pip_executable), 'list'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if 'qiskit' in result.stdout.lower():
            # Extract version if possible
            for line in result.stdout.split('\n'):
                if line.lower().startswith('qiskit'):
                    logger.info(f"✓ {line.strip()}")
                    return True, line.strip()

            logger.info("✓ Qiskit is installed")
            return True, "Qiskit is installed"
        else:
            logger.error("✗ Qiskit not found in pip list")
            return False, "Qiskit not installed"

    except subprocess.TimeoutExpired:
        logger.error("✗ pip list command timed out")
        return False, "pip list timeout"
    except Exception as e:
        logger.error(f"✗ Error checking pip list: {e}")
        return False, f"pip list error: {e}"


def detect_ab_layout() -> Tuple[bool, str]:
    """
    Detect if system is using A/B boot.

    Returns:
        Tuple of (is_ab_boot, layout_version)
        layout_version: 'ab' if A/B boot detected, 'none' otherwise
    """
    try:
        # Check for CONFIG partition (A/B boot layout)
        result = subprocess.run(
            ['lsblk', '-no', 'label', '/dev/mmcblk0p1'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Case-insensitive check for CONFIG label
        if result.returncode == 0 and 'config' in result.stdout.lower():
            return True, 'ab'

        return False, 'none'

    except Exception as e:
        logger.warning(f"Could not detect A/B layout: {e}")
        return False, 'none'


# ---------------------------------------------------------------------------
# Probation and automatic rollback (R-054)
# ---------------------------------------------------------------------------

def read_dt_u32(name: str, base: Optional[Path] = None) -> Optional[int]:
    """
    Read a big-endian u32 the bootloader left in the device tree.

    /proc/device-tree/chosen/bootloader/tryboot is 1 when the firmware
    started this boot with the tryboot flag (Pi 4 and Pi 5, checked on the
    rig 2026-10-02).

    Args:
        name (str): property name, e.g. 'tryboot' or 'partition'
        base (Path): directory holding the properties (tests)

    Returns:
        int or None: the value, or None when the property is not there
    """
    path = (base or DT_BOOTLOADER_DIR) / name
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 4:
        return None
    return int.from_bytes(data[:4], 'big')


def slot_from_root(root_dev: str) -> Optional[str]:
    """
    Slot of a root device on the A/B layout (p5 = Slot A, p6 = Slot B).

    Args:
        root_dev (str): e.g. '/dev/mmcblk0p6'

    Returns:
        str or None: 'A', 'B' or None
    """
    if root_dev.endswith('5'):
        return 'A'
    if root_dev.endswith('6'):
        return 'B'
    return None


def current_root_device() -> str:
    """
    The device mounted at / (findmnt).

    Returns:
        str: device path, '' if unknown
    """
    try:
        return subprocess.run(['findmnt', '/', '-o', 'source', '-n'],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ''


def slot_boot_partition(slot: str) -> int:
    """
    Boot partition number of a slot (v3 layout: BOOT-A = 2, BOOT-B = 3).

    Args:
        slot (str): 'A' or 'B'

    Returns:
        int: partition number
    """
    return 2 if slot == 'A' else 3


def autoboot_default_partition(text: str) -> Optional[int]:
    """
    boot_partition of the [all] section of autoboot.txt: what a normal boot
    (without the tryboot flag) starts.

    Args:
        text (str): autoboot.txt contents

    Returns:
        int or None: partition number
    """
    section = 'all'
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip().lower()
            continue
        if section == 'all' and line.startswith('boot_partition='):
            try:
                return int(line.split('=', 1)[1].strip())
            except ValueError:
                return None
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def on_probation(config_dir: Path, slot: Optional[str], tryboot_flag: Optional[int]) -> bool:
    """
    Is this the unconfirmed first boot of a slot switch?

    True when a switch to this very slot is pending (target-slot), the slot is
    not confirmed yet, and the firmware did not say this was a normal boot.
    A slot reached by firmware fallback (tryboot flag 0) is never on
    probation: rolling it back could boot a broken slot again and loop.

    Args:
        config_dir (Path): the CONFIG partition (/boot/config)
        slot (str): the running slot
        tryboot_flag (int or None): chosen/bootloader/tryboot, None if unknown

    Returns:
        bool
    """
    if slot not in ('A', 'B'):
        return False
    if _read(config_dir / 'target-slot') != slot:
        return False
    if (config_dir / 'slot-confirmed').exists():
        return False
    if tryboot_flag == 0:
        return False
    return True


def rollback_target_exists(config_dir: Path, slot: str) -> bool:
    """
    Would a normal reboot start a DIFFERENT slot than this one?

    Args:
        config_dir (Path): the CONFIG partition
        slot (str): the running slot

    Returns:
        bool: False when autoboot.txt [all] already points at this slot (a
        reboot would come straight back - never reboot then)
    """
    default = autoboot_default_partition(_read(config_dir / 'autoboot.txt'))
    return default is not None and default != slot_boot_partition(slot)


def _read_kv(path: Path) -> dict:
    """key=value lines of a small CONFIG file ({} if there is none)."""
    kv = {}
    for line in _read(path).splitlines():
        key, sep, value = line.partition('=')
        if sep:
            kv[key.strip()] = value.strip()
    return kv


def now_epoch() -> float:
    """This slot's clock (a function, so tests can set it)."""
    return time.time()


def switch_request(config_dir: Path, slot: str) -> dict:
    """
    switch-requested, which rq_slot_manager.sh switch-to writes with the
    target-slot marker (slot=, time=, epoch=): when the switch to <slot> was
    asked for, by the clock of the slot that asked.

    Returns:
        dict: {} if there is none, or it is about another slot
    """
    request = _read_kv(config_dir / SWITCH_REQUEST)
    return request if request.get('slot') == slot else {}


def _request_epoch(request: dict) -> Optional[float]:
    try:
        return float(request['epoch'])
    except (KeyError, ValueError):
        pass
    try:
        return time.mktime(time.strptime(request.get('time', ''), TIME_FORMAT))
    except ValueError:
        return None


def failure_time(request: dict) -> Tuple[str, bool]:
    """
    When a switch failed, for time= in last-switch-failed ("When:").

    The clock of a slot on its trial boot is often not set yet when the
    health check runs: there is no RTC, and until NTP answers, fake-hwclock
    has it at that slot's last shutdown - hours or weeks before (rig,
    2026-10-04: 11:09 for a failure at 12:25). The slot that asked for the
    switch had a set clock and recorded the request (switch-requested), and
    a failure cannot come before its request. So: this clock when it is
    synchronised or not behind the request, else the request time.

    Args:
        request (dict): switch_request() ({} when the switch was asked for
            by a slot that does not record it)

    Returns:
        tuple: (time as "YYYY-MM-DD HH:MM:SS", True if this clock was behind
        and the request time was taken)
    """
    now = now_epoch()
    stamp = time.strftime(TIME_FORMAT, time.localtime(now))
    asked = _request_epoch(request)
    if asked is None or now >= asked or TIME_SYNCED.exists():
        return stamp, False
    # the request's own words: its slot's time zone is the one that shows it
    return request.get('time') or time.strftime(TIME_FORMAT, time.localtime(asked)), True


def record_failed_switch(config_dir: Path, slot: str, reason: str,
                         version: str = '', detail: str = '') -> None:
    """
    Leave a notice on the CONFIG partition (both slots and a PC can read it;
    rq_slot_manager.sh status shows it) and clear the pending switch, so
    rq_tryboot_retry.sh does not try the failed slot again.

    Args:
        config_dir (Path): the CONFIG partition
        slot (str): the slot that failed
        reason (str): one line for the user
        version (str): the failed slot's /etc/rasqberry-version, if known
            (else the version the update wrote, from slot-<X>-updated)
        detail (str): the technical message behind the reason, if any
    """
    # rq_update_slot.sh leaves slot-<X>-updated when it has written the slot
    # and the slot has not started well since: then this was an update ("The
    # update of Slot X to <version> didn't work"), else a plain switch
    # ("Switching to Slot X didn't work") - rq_slot_status.sh failure-notice
    hint = _read_kv(config_dir / f"slot-{slot}-updated")
    request = switch_request(config_dir, slot)
    when, clock_behind = failure_time(request)
    # time= is the failure's identity for the indicator, the login line and
    # the usage counts: written once here, never changed afterwards
    updated = (config_dir / f'slot-{slot}-updated').exists()
    lines = [f"slot={slot}", f"reason={reason}", f"time={when}",
             f"update={'yes' if updated else 'no'}"]
    if detail:
        lines.append(f"detail={detail}")
    version = version or hint.get('version', '')
    if version:
        lines.append(f"version={version}")
    if request.get('time'):
        lines.append(f"requested={request['time']}")
    if clock_behind:
        lines.append(f"clock={time.strftime(TIME_FORMAT, time.localtime(now_epoch()))}")
    try:
        (config_dir / FAILED_NOTICE).write_text('\n'.join(lines) + '\n')
    except OSError as e:
        logger.warning(f"Could not write {config_dir / FAILED_NOTICE}: {e}")
    # The update's one trial is over: a later switch to that slot is a plain
    # switch, not the update again (a plain switch-to after a failed update
    # was recorded as update=yes, rig test 2026-10-08)
    names = ['target-slot', 'switch-retries', SWITCH_REQUEST]
    if updated:
        names.append(f'slot-{slot}-updated')
    for name in names:
        try:
            (config_dir / name).unlink()
        except OSError:
            pass


def reboot_now() -> None:
    """Reboot without the tryboot flag (the firmware then starts autoboot.txt [all])."""
    if os.environ.get('RQ_HEALTH_NO_REBOOT') == '1':
        logger.info("(RQ_HEALTH_NO_REBOOT=1: not rebooting)")
        return
    subprocess.run(['sync'], check=False)
    subprocess.run(['systemctl', 'reboot'], check=False)


def fail_probation(config_dir: Path, slot: str, reason: str, detail: str = '') -> str:
    """
    A slot on probation failed: record it and go back to the slot that worked.

    Args:
        config_dir (Path): the CONFIG partition
        slot (str): the running (failed) slot
        reason (str): why

    Returns:
        str: 'rolled-back' or 'no-rollback-target'
    """
    version = _read(Path('/etc/rasqberry-version'))
    record_failed_switch(config_dir, slot, reason, version, detail)
    if not rollback_target_exists(config_dir, slot):
        logger.error("✗ autoboot.txt already starts this slot by default - "
                     "not rebooting (it would come straight back)")
        return 'no-rollback-target'
    other = 'B' if slot == 'A' else 'A'
    logger.error(f"✗ Slot {slot} failed on its trial boot ({detail or reason}). "
                 f"Rebooting into Slot {other}, the system that worked.")
    reboot_now()
    return 'rolled-back'


def wait_for_display_manager(timeout: int = DISPLAY_MANAGER_TIMEOUT,
                             poll: float = 5.0) -> Tuple[bool, str]:
    """
    On a desktop image, wait until the display manager is active.

    Not graphical.target itself: this service is part of multi-user.target,
    which graphical.target waits for, so that would never become active
    while we wait.

    Args:
        timeout (int): seconds
        poll (float): seconds between checks

    Returns:
        Tuple of (success, message)
    """
    try:
        default = subprocess.run(['systemctl', 'get-default'], capture_output=True,
                                 text=True, timeout=10).stdout.strip()
    except Exception:
        default = ''
    if default != 'graphical.target':
        return True, f"default target {default or 'unknown'} - no desktop to check"
    deadline = time.monotonic() + timeout
    state = ''
    while True:
        try:
            state = subprocess.run(['systemctl', 'is-active', 'display-manager.service'],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            state = 'unknown'
        if state == 'active':
            return True, "display manager active"
        if time.monotonic() >= deadline:
            return False, f"the desktop did not come up within {timeout} s (display-manager: {state})"
        time.sleep(poll)


def set_runtime_watchdog(seconds: int) -> bool:
    """
    Arm (seconds > 0) or disarm (0) systemd's hardware watchdog at runtime.

    Args:
        seconds (int): RuntimeWatchdogSec

    Returns:
        bool: success
    """
    try:
        r = subprocess.run(['busctl', 'set-property', 'org.freedesktop.systemd1',
                            '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager',
                            'RuntimeWatchdogUSec', 't', str(seconds * 1000000)],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def disarm_probation_watchdog() -> None:
    """Switch off the watchdog rq_tryboot_retry.sh armed for the trial boot."""
    if WATCHDOG_MARKER.exists():
        if set_runtime_watchdog(0):
            logger.info("✓ Trial-boot watchdog disarmed")
        try:
            WATCHDOG_MARKER.unlink()
        except OSError:
            pass


def wait_for_clock_sync(timeout: Optional[float] = None, active: Optional[bool] = None) -> bool:
    """
    A few seconds for NTP before the slot is confirmed: slot-confirmed keeps
    the time, and a freshly written slot runs on its build time until NTP
    answers (user test 2026-10-08 F3: the confirm came 7 s before the sync).
    Only while systemd-timesyncd runs; bounded, so the confirm is never late
    by more than <timeout>.

    Args:
        timeout (float): longest wait in seconds (None: CLOCK_SYNC_WAIT)
        active (bool, optional): systemd-timesyncd runs (None: ask systemctl)

    Returns:
        bool: the clock is synchronised
    """
    if TIME_SYNCED.exists():
        return True
    timeout = CLOCK_SYNC_WAIT if timeout is None else timeout
    if timeout <= 0:
        return False
    if active is None:
        try:
            active = subprocess.run(['systemctl', 'is-active', '--quiet', 'systemd-timesyncd'],
                                    capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            active = False
    if not active:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        if TIME_SYNCED.exists():
            return True
    logger.info("Clock not synchronised yet (NTP): slot-confirmed has the start-up time")
    return False


def confirm_boot_slot() -> bool:
    """
    Confirm the current boot slot to prevent rollback.

    This is done by calling the slot manager script.

    Returns:
        bool: Success
    """
    # Detect A/B boot layout
    is_ab, layout = detect_ab_layout()

    if not is_ab:
        logger.info("Standard (non-AB) boot system detected")
        return True  # Not an error, just not using A/B boot

    logger.info("A/B boot system detected")

    slot_manager = SLOT_MANAGER

    if not slot_manager.exists():
        logger.warning("Slot manager not found, cannot confirm slot")
        return True  # Don't fail health check

    # If a slot switch was requested, verify we actually booted the target
    # slot. Blindly confirming would mask a failed tryboot (system silently
    # kept running the old slot).
    target_file = BOOT_CONFIG_DIR / 'target-slot'
    switch_done = False
    if target_file.exists():
        try:
            target_slot = target_file.read_text().strip()
            root_dev = current_root_device()
            current_slot = slot_from_root(root_dev) or 'B'
            if target_slot in ('A', 'B') and target_slot != current_slot:
                # The target never got as far as this check, twice (the first
                # time rq_tryboot_retry.sh tried again): typically a kernel
                # that cannot start, which panic=10 turns into a reboot back
                # here. Say so where the user can see it, and keep THIS slot
                # - it works - as the confirmed default.
                logger.error(
                    f"✗ Slot switch FAILED: target was Slot {target_slot} "
                    f"but system booted Slot {current_slot} ({root_dev}). "
                    "Retry budget exhausted (see rq_tryboot_retry.sh)."
                )
                record_failed_switch(
                    BOOT_CONFIG_DIR, target_slot,
                    f"Slot {target_slot} was tried twice without success")
            else:
                switch_done = True
                logger.info(f"✓ Booted the requested target slot ({current_slot})")
        except Exception as e:
            logger.warning(f"Could not verify target slot: {e}")

    try:
        if not (BOOT_CONFIG_DIR / 'slot-confirmed').exists():
            wait_for_clock_sync()
        return _run_confirm(slot_manager)
    finally:
        # The switch markers go only now, after the confirm: until then the
        # taskbar shows "being checked" (target-slot = this slot, not
        # confirmed). Removed first, the up to 20 s wait for NTP showed
        # "restart pending" (rig test 2026-10-09, F2). Removed whether the
        # confirm worked or not, as before.
        if switch_done:
            for name in ('target-slot', 'switch-retries', SWITCH_REQUEST, FAILED_NOTICE):
                try:
                    (BOOT_CONFIG_DIR / name).unlink()
                except OSError:
                    pass


def _run_confirm(slot_manager: Path) -> bool:
    """
    rq_slot_manager.sh confirm: slot-confirmed, and autoboot.txt starts this slot.

    Returns:
        bool: Success
    """
    try:
        result = subprocess.run(
            [str(slot_manager), 'confirm'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info("✓ Boot slot confirmed")
            # Log the confirmation details from stdout
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
            return True
        else:
            logger.error(f"✗ Failed to confirm boot slot: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"✗ Error confirming boot slot: {e}")
        return False


def write_slot_status() -> None:
    """
    Refresh /run/rasqberry/slot-status for the taskbar indicator (#242): as
    root it can say what the other slot holds. Never fails the health check.
    """
    if not SLOT_STATUS.exists():
        return
    try:
        result = subprocess.run([str(SLOT_STATUS), 'write'], capture_output=True,
                                text=True, timeout=60)
        if result.returncode != 0:
            logger.warning(f"Could not write the slot status: {result.stderr.strip()}")
    except Exception as e:
        logger.warning(f"Could not write the slot status: {e}")


def report_status(success: bool, checks: dict):
    """
    Report health check status.

    This could be extended to post to GitHub API, send notifications, etc.

    Args:
        success: Overall health check success
        checks: Dictionary of check results
    """
    status_file = Path('/var/lib/rasqberry-health-check.status')
    try:
        status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(status_file, 'w') as f:
            f.write(f"timestamp: {time.time()}\n")
            f.write(f"success: {success}\n")
            for check_name, (check_success, message) in checks.items():
                f.write(f"{check_name}: {check_success} - {message}\n")
        logger.info(f"Status written to {status_file}")
    except OSError as e:
        logger.warning(f"Could not write {status_file}: {e}")


def probation_slot() -> Optional[str]:
    """
    The running slot if this boot is on probation, else None.

    Returns:
        str or None
    """
    if not (BOOT_CONFIG_DIR / 'autoboot.txt').exists():
        return None
    slot = slot_from_root(current_root_device())
    if on_probation(BOOT_CONFIG_DIR, slot, read_dt_u32('tryboot')):
        return slot
    return None


def run_deadline() -> int:
    """
    rasqberry-probation.timer, 15 minutes after boot: a trial boot that is
    still unconfirmed did not finish starting - roll it back.

    Returns:
        int: exit code
    """
    if BOOT_CONFIG_DIR.is_dir() and not (BOOT_CONFIG_DIR / 'autoboot.txt').exists():
        # emergency mode may have left the CONFIG partition unmounted
        subprocess.run(['mount', str(BOOT_CONFIG_DIR)], capture_output=True, check=False)
    slot = probation_slot()
    if slot is None:
        return 0
    fail_probation(BOOT_CONFIG_DIR, slot,
                   f"not confirmed {DEADLINE_MINUTES} minutes after start "
                   "(start-up hung or the health check could not run)")
    return 1


def counts_started(probation: Optional[str]) -> dict:
    """
    Usage counts, before the slot is confirmed (confirming writes the CONFIG
    markers that tell a new card from an updated slot, and removes the
    update hint). Never raises.

    Returns:
        dict: for counts_finished()
    """
    if usage_counts is None:
        return {}
    try:
        return usage_counts.boot_started(BOOT_CONFIG_DIR, probation)
    except Exception as e:  # noqa: BLE001
        logger.info(f"Usage counts skipped: {e}")
        return {}


def counts_finished(ctx: dict, confirmed: bool) -> None:
    """Usage counts at the end: queue what this start decided, send the queue. Never raises."""
    if usage_counts is None:
        return
    try:
        usage_counts.boot_finished(ctx, BOOT_CONFIG_DIR, slot_from_root(current_root_device()),
                                   confirmed)
    except Exception as e:  # noqa: BLE001
        logger.info(f"Usage counts skipped: {e}")


def main():
    """
    Main health check routine.

    Exits with 0 on success, non-zero on failure.
    """
    if '--deadline' in sys.argv[1:]:
        sys.exit(run_deadline())

    logger.info("=== RasQberry A/B Boot Health Check ===")
    probation = probation_slot()
    if probation:
        logger.info(f"Slot {probation} is on its trial boot (tryboot): a failed check rolls back")
    counts = counts_started(probation)
    logger.info("Starting health checks...")

    checks = {}

    def failed(reason: str, detail: str = ''):
        logger.error(f"✗ Health check FAILED: {detail or reason}")
        report_status(False, checks)
        if not probation or fail_probation(BOOT_CONFIG_DIR, probation, reason,
                                           detail) != 'rolled-back':
            write_slot_status()
        sys.exit(1)

    # Load environment
    logger.info("Loading environment configuration...")
    env = load_environment()
    logger.info(f"Environment: USER_HOME={env.get('USER_HOME')}, "
                f"REPO={env.get('REPO')}, STD_VENV={env.get('STD_VENV')}")

    # Check 1: Virtual environment exists
    logger.info("\n[1/3] Checking virtual environment...")
    success, message = check_venv_exists(env)
    checks['venv'] = (success, message)
    if not success:
        failed(REASON_VENV, "virtual environment missing")

    venv_path = message

    # Check 2: Qiskit installed
    logger.info("\n[2/3] Checking Qiskit installation...")
    success, message = check_qiskit_installed(venv_path)
    checks['qiskit'] = (success, message)
    if not success:
        failed(REASON_QISKIT, f"Qiskit check failed ({message})")

    # Check 3: the desktop came up (trial boots only)
    if probation:
        logger.info("\n[3/3] Waiting for the desktop (display manager)...")
        success, message = wait_for_display_manager()
        checks['desktop'] = (success, message)
        if not success:
            failed(REASON_DESKTOP, message)
        logger.info(f"✓ {message}")

    # All checks passed
    logger.info("\n=== All Health Checks Passed ===")
    logger.info("✓ Virtual environment exists")
    logger.info("✓ Qiskit is installed")
    logger.info("✓ SSH is accessible (implicit)")

    # Confirm boot slot
    logger.info("\nConfirming boot slot...")
    confirmed = confirm_boot_slot()
    if confirmed:
        logger.info("✓ Boot slot confirmed - no rollback will occur")
        disarm_probation_watchdog()
    else:
        logger.warning("⚠ Could not confirm boot slot")

    # Report success
    report_status(True, checks)
    write_slot_status()
    counts_finished(counts, confirmed)

    logger.info("\n=== Health Check Complete: SUCCESS ===")
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"✗ Health check FAILED with exception: {e}", exc_info=True)
        sys.exit(1)
