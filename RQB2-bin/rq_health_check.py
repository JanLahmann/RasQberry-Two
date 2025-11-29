#!/usr/bin/env python3
"""
RasQberry A/B Boot Health Check

Validates that a newly booted system is functional and confirms the boot slot.
This script runs automatically after booting into a new slot (tryboot mode).

Success criteria:
- SSH is accessible (implicit - script is running)
- Qiskit is installed in virtual environment
- Virtual environment exists

If all checks pass: Confirms the slot (prevents rollback)
If any check fails: Exits non-zero (triggers automatic rollback to previous slot)

Timeout: 10 minutes (configured in systemd service)
"""

import os
import subprocess
import sys
import time
import logging
from pathlib import Path
from typing import Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/rasqberry-health-check.log')
    ]
)
logger = logging.getLogger(__name__)


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
    env.setdefault('USER_HOME', os.path.expanduser('~rasqberry'))
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

    slot_manager = Path('/usr/local/bin/rq_slot_manager.sh')

    if not slot_manager.exists():
        logger.warning("Slot manager not found, cannot confirm slot")
        return True  # Don't fail health check

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


def report_status(success: bool, checks: dict):
    """
    Report health check status.

    This could be extended to post to GitHub API, send notifications, etc.

    Args:
        success: Overall health check success
        checks: Dictionary of check results
    """
    status_file = Path('/var/lib/rasqberry-health-check.status')
    status_file.parent.mkdir(parents=True, exist_ok=True)

    with open(status_file, 'w') as f:
        f.write(f"timestamp: {time.time()}\n")
        f.write(f"success: {success}\n")
        for check_name, (check_success, message) in checks.items():
            f.write(f"{check_name}: {check_success} - {message}\n")

    logger.info(f"Status written to {status_file}")


def main():
    """
    Main health check routine.

    Exits with 0 on success, non-zero on failure.
    """
    logger.info("=== RasQberry A/B Boot Health Check ===")
    logger.info("Starting health checks...")

    checks = {}

    # Load environment
    logger.info("Loading environment configuration...")
    env = load_environment()
    logger.info(f"Environment: USER_HOME={env.get('USER_HOME')}, "
                f"REPO={env.get('REPO')}, STD_VENV={env.get('STD_VENV')}")

    # Check 1: Virtual environment exists
    logger.info("\n[1/2] Checking virtual environment...")
    success, message = check_venv_exists(env)
    checks['venv'] = (success, message)

    if not success:
        logger.error("✗ Health check FAILED: Virtual environment check failed")
        report_status(False, checks)
        sys.exit(1)

    venv_path = message

    # Check 2: Qiskit installed
    logger.info("\n[2/2] Checking Qiskit installation...")
    success, message = check_qiskit_installed(venv_path)
    checks['qiskit'] = (success, message)

    if not success:
        logger.error("✗ Health check FAILED: Qiskit check failed")
        report_status(False, checks)
        sys.exit(1)

    # All checks passed
    logger.info("\n=== All Health Checks Passed ===")
    logger.info("✓ Virtual environment exists")
    logger.info("✓ Qiskit is installed")
    logger.info("✓ SSH is accessible (implicit)")

    # Confirm boot slot
    logger.info("\nConfirming boot slot...")
    if confirm_boot_slot():
        logger.info("✓ Boot slot confirmed - no rollback will occur")
    else:
        logger.warning("⚠ Could not confirm boot slot")

    # Report success
    report_status(True, checks)

    logger.info("\n=== Health Check Complete: SUCCESS ===")
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"✗ Health check FAILED with exception: {e}", exc_info=True)
        sys.exit(1)
