# 00-configure-initramfs

Turns initramfs generation off or on for the image, depending on `SKIP_INITRAMFS`
in the pi-gen config.

## What it does

- `00-run.sh` (host): copies the pi-gen `config` to `${ROOTFS_DIR}/tmp/stage-config`.
- `00-run-chroot.sh` (chroot): sources and deletes `/tmp/stage-config`.
  - `SKIP_INITRAMFS=1`:
    - writes `INITRD=No` to `/etc/default/raspberrypi-kernel`;
    - adds the kernel hook `/etc/kernel/postinst.d/00-skip-initramfs`, which
      deletes `/boot/initrd*` and `/boot/initramfs*` when `INITRD=No`;
    - writes `INITRAMFS=no` to `/etc/default/raspi-firmware` (if `/boot/firmware`
      or `/usr/lib/raspi-firmware/update` exists);
    - diverts `update-initramfs` and `mkinitramfs` (`dpkg-divert`, originals kept
      as `*.real`) and replaces them with no-op scripts;
    - deletes any existing `/boot/initrd*` and `/boot/initramfs*`.
  - any other value: removes the `INITRD=No` line and the two diversions, so
    initramfs is generated normally.

## Notes

- If `/tmp/stage-config` is missing, `SKIP_INITRAMFS` defaults to `0`.
- `pi-gen-config` sets `SKIP_INITRAMFS=1`. For main and beta the workflow
  replaces it with `SKIP_INITRAMFS_PROD` from `pi-gen-config`; that variable is
  not defined there, so the value becomes empty and this stage treats it as `0`.
- The GitHub workflow also injects a `stage0/00-disable-initramfs` hook into
  pi-gen that diverts both tools from the start of the build. With
  `SKIP_INITRAMFS=0` this stage removes those diversions, so later calls
  (e.g. `update-initramfs -u` in [07-splash-screen](../07-splash-screen/README.md))
  generate a real initramfs.
- [export-image/04-restore-initramfs](../export-image/README.md) was meant to
  restore the tools at the end; see the note there.
