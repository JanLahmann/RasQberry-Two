# export-image

Holds one sub-stage, `04-restore-initramfs/`, written to undo the initramfs
diversions just before pi-gen's own export stage generates the final initramfs,
and to add a script that waits for the SD card during early boot.

## What it does

`04-restore-initramfs/00-run-chroot.sh` (chroot):

- If `SKIP_INITRAMFS` (from the environment) is `1`, exits and leaves the
  diversions in place: the image gets no initramfs.
- Otherwise removes the `dpkg-divert` of `update-initramfs` and `mkinitramfs`
  if the `*.real` files exist, and copies `/files/wait-for-mmc` to
  `/etc/initramfs-tools/scripts/local-block/` (warning if it is missing).

## Files

- `04-restore-initramfs/files/wait-for-mmc` - initramfs `local-block` script:
  waits up to 30 s for `/dev/mmcblk0` and its partitions, then continues
  (never panics).

## Notes

- This directory does not appear to run. pi-gen treats `export-image/` as a
  sub-stage of `stage-RQB2` and runs only scripts at its top level, where there
  are none; the export stage pi-gen runs is its own `pi-gen/export-image/`, and
  nothing in the workflow copies `04-restore-initramfs/` there.
- If it did run: `00-configure-initramfs` reads `SKIP_INITRAMFS` from the
  config file it copies into the chroot, while this script reads it from the
  environment; and `/files/wait-for-mmc` is a path inside the chroot, where the
  sub-stage's `files/` directory is not copied.
- The image file name comes from `stage-RQB2/EXPORT_IMAGE` (`IMG_FILENAME`),
  not from this directory.
