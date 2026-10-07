# 00-configure-initramfs

Turns initramfs generation off or on for the image, depending on `SKIP_INITRAMFS`
in the pi-gen config.

## What it does

- `00-run.sh` (host): copies the pi-gen `config` to `${ROOTFS_DIR}/tmp/stage-config`.
- `00-run-chroot.sh` (chroot): sources and deletes `/tmp/stage-config`.
  - `SKIP_INITRAMFS=1`:
    - writes `INITRD=No` to `/etc/default/raspberrypi-kernel`;
    - adds the kernel hook `/etc/kernel/postinst.d/00-skip-initramfs`, which
      deletes `/boot/initrd*`, `/boot/initramfs*` and `/boot/firmware/initramfs*`
      when `INITRD=No` (its `exit 0` ends only this hook; run-parts runs the
      others);
    - writes `INITRAMFS=no` and `SKIP_INITRAMFS_GEN=yes` (trixie's raspi-firmware;
      bookworm's ignores it) to `/etc/default/raspi-firmware` (if `/boot/firmware`
      or `/usr/lib/raspi-firmware/update` exists);
    - diverts `update-initramfs` and `mkinitramfs` (`dpkg-divert`, originals kept
      as `*.real`) and replaces them with no-op scripts;
    - deletes any existing `/boot/initrd*`, `/boot/initramfs*` and
      `/boot/firmware/initramfs*` (pi-gen's kernel install puts `initramfs8` /
      `initramfs_2712` there before this stage), and drops `auto_initramfs=` and
      `initramfs` lines from `/boot/firmware/config.txt`, as
      `convert-to-ab-boot-v3.sh` step 10 does for the A/B image. Before, the
      standard image loaded that stale initramfs at every start (feedback 37/41).
      [98-clean-caches](../98-clean-caches/README.md) checks again at the end.
  - any other value: removes the `INITRD=No` line and the two diversions, so
    initramfs is generated normally.

## Notes

- If `/tmp/stage-config` is missing, `SKIP_INITRAMFS` defaults to `0`.
- `pi-gen-config` sets `SKIP_INITRAMFS=1` for every stream (dev, beta, main).
- The GitHub workflow also injects a `stage0/00-disable-initramfs` hook into
  pi-gen that diverts both tools from the start of the build. With
  `SKIP_INITRAMFS=0` this stage removes those diversions, so later calls
  (e.g. `update-initramfs -u` in [07-splash-screen](../07-splash-screen/README.md))
  generate a real initramfs.
- No stream builds an initramfs any more (`SKIP_INITRAMFS=1` everywhere); the
  unused `export-image/04-restore-initramfs` was removed (#301).
- Raspberry Pi OS trixie moved more into the initramfs: growing the root
  partition (the `resize` word pi-gen puts in `cmdline.txt`), the PARTUUID
  change and `imager_fixup`. Without an initramfs none of it runs: the image
  grows its root itself (`01-expand-filesystem.sh`, A/B: `rq_expand_ab.sh`),
  keeps the PARTUUID of the build (as the A/B image always did), and
  `00-enable-serial-console` / `convert-to-ab-boot-v3.sh` drop `resize`.
- Raspberry Pi OS bookworm's initramfs carried one thing the image needs:
  `imager_fixup`, which makes Raspberry Pi Imager's OS customisation
  (`firstrun.sh`) run. Without an initramfs `rasqberry-imager-firstrun.service`
  does that instead, for the standard and the A/B image (see
  [00-firstboot-setup](../00-firstboot-setup/README.md)).
