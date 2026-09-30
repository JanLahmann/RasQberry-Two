# 08-ip-display

Shows the device's IP address on the LED panel for a minute after boot, so a
headless RasQberry can be found on the network.

## What it does (`00-run-chroot.sh`, chroot)

- Installs `netifaces` into the RQB2 venv of `${FIRST_USER_NAME}` and gives the
  venv back to the user afterwards (pip runs as root here).

## Files

- `rasqberry-ip-display.service` comes from `RQB2-system/` and is enabled by
  [01-deploy-files](../01-deploy-files/README.md); it runs
  `/usr/bin/rq_display_ip.py` with the venv python.

## Notes

- The service holds the LED GPIO while it runs (about 60 s after boot); LED demos
  started in that window report the GPIO as busy.
