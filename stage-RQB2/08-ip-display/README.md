# 08-ip-display

Prepares the boot-time service that scrolls the Pi's IP address across the LED
matrix.

## What it does

`00-run-chroot.sh` (chroot):

- Installs `netifaces` into `/home/rasqberry/RasQberry-Two/venv/RQB2`, from
  `/tmp/wheels` if that holds wheels, otherwise from PyPI. If the venv is
  missing it only prints a warning.

## Files

From `RQB2-system/`, installed and enabled by
[01-deploy-files](../01-deploy-files/README.md):

- `/etc/systemd/system/rasqberry-ip-display.service` - after
  `network-online.target`, runs `/usr/bin/rq_display_ip.py --duration 60` with
  the venv's Python as root; restarts on failure.

## Notes

- The venv path is hard-coded, here and in the unit, not derived from
  `FIRST_USER_NAME`, `RQB_REPO` or `RQB_STD_VENV`.
- `/tmp/wheels` is already deleted by `03-install-qiskit/02-run.sh`, so the
  PyPI path is the one that runs.
