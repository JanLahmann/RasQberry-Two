# 00-enable-serial-console

Sets the console (HDMI or serial) and the boot verbosity (splash or verbose) in
the boot partition's `config.txt` and `cmdline.txt`.

## What it does

`00-run.sh` (host), editing `${ROOTFS_DIR}/boot/firmware/`:

- `config.txt`: `CONSOLE_TYPE=serial` sets `enable_uart=1`; any other value
  removes the `enable_uart=` line.
- `cmdline.txt`, console: `serial` adds `console=serial0,115200` after
  `console=tty1` (serial last, so it is the primary console); otherwise any
  `console=serial0,...` is removed.
- `cmdline.txt`, verbosity: `BOOT_VERBOSITY=verbose` removes `quiet`, `splash`
  and `plymouth.ignore-serial-consoles`; otherwise it adds any of them that are
  missing.
- Fails the build if `config.txt` or `cmdline.txt` is missing.

`00-run-chroot.sh` (chroot) only checks that `serial-getty@.service` exists. It
enables nothing: at boot, `systemd-getty-generator` creates the serial getty from
the `console=` parameter.

## Notes

- `CONSOLE_TYPE` defaults to `hdmi`, `BOOT_VERBOSITY` to `splash`. The workflow
  writes both into `pi-gen-config`: `*_PROD` (hdmi/splash) for main and beta,
  `*_DEV` (serial/verbose) for other branches, unless set by workflow input.
- The A/B conversion (`convert-to-ab-boot-v3.sh`, see
  [08-ab-boot-support](../08-ab-boot-support/README.md)) receives the same two
  variables and writes its own cmdline for both slots.
