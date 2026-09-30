# 08-ab-boot-support

Checks that the A/B boot tools are in the image. The A/B partition layout itself
is not built here: the workflow runs this stage's `files/convert-to-ab-boot-v3.sh`
on the finished standard image.

## What it does

- `00-run.sh` (host): copies the pi-gen `config` to `${ROOTFS_DIR}/tmp/stage-config`.
- `00-run-chroot.sh` (chroot):
  - sources `/tmp/stage-config` (falls back to JanLahmann/RasQberry-Two, `main`)
    and shallow-clones the repository to `/tmp/${RQB_REPO}` unless it exists;
  - fails if the clone has no `RQB2-bin/rq_health_check.py`;
  - warns for each of `rq_health_check.py`, `rq_slot_manager.sh`,
    `rq_common.sh`, `rq_update_poller.py`, `rq_update_slot.sh`,
    `rq_tryboot_retry.sh` missing from `/usr/bin`.

## Files

- `files/convert-to-ab-boot-v3.sh` - not used by the stage scripts. After the
  build, the workflow runs it (for `full` and `ab-only` builds) with
  `CONSOLE_TYPE` and `BOOT_VERBOSITY` to turn the standard image into a
  7-partition A/B image: CONFIG (`autoboot.txt` with `tryboot_a_b=1`), BOOT-A,
  BOOT-B, SYSTEM-A (10GB), SYSTEM-B and DATA (16MB placeholders). It writes
  `skip-expansion` to the boot partitions, rebuilds `cmdline.txt` per slot
  (keeping extra parameters) and disables initramfs. See
  [docs/ab-boot.md](../../docs/ab-boot.md).
- From `RQB2-system/`, installed and enabled by
  [01-deploy-files](../01-deploy-files/README.md):
  `rasqberry-health-check.service` and `rasqberry-tryboot-retry.service`.

## Notes

- The stage leaves `/tmp/stage-config` and the clone in place;
  [10-boot-config](../10-boot-config/README.md) reuses the clone and
  [98-clean-caches](../98-clean-caches/README.md) empties `/tmp`.
- The scripts in `/usr/bin` come from `RQB2-bin/` via 01-deploy-files.
