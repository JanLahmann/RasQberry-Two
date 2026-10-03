# 07-splash-screen

Installs the RasQberry Plymouth boot splash (cube logo on a white background,
the logo's own colour) and makes it the default theme.

## What it does

- `00-run.sh` (host): installs into
  `${ROOTFS_DIR}/usr/share/plymouth/themes/rasqberry/`:
  - `files/images/RasQberry Cube Logo 1000x1000.png` as `rasqberry-logo.png`;
  - `files/plymouth/rasqberry.plymouth` and `files/plymouth/rasqberry.script`.
- `00-run-chroot.sh` (chroot): runs `plymouth-set-default-theme rasqberry` and
  `update-initramfs -u`; fails if the theme file is missing.

## Files

- `files/images/RasQberry Cube Logo 1000x1000.png`
- `files/plymouth/rasqberry.plymouth` - theme definition (script module)
- `files/plymouth/rasqberry.script` - centred logo with fade-in, scaled to 45%
  of the screen height (so it fits the 800x480 display), progress percentage
  below it and boot messages, both in dark grey

## Notes

- `quiet splash` is on the kernel command line only with
  `BOOT_VERBOSITY=splash` (see [00-enable-serial-console](../00-enable-serial-console/README.md)).
- With `SKIP_INITRAMFS=1`, `update-initramfs` is a no-op (see
  [00-configure-initramfs](../00-configure-initramfs/README.md)).
