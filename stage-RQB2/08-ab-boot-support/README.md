# 08-ab-boot-support

Checks that the image carries what an A/B image needs at runtime. The A/B
partition layout itself is created after the build by
[`files/convert-to-ab-boot-v3.sh`](files/convert-to-ab-boot-v3.sh), which the image
workflow runs on the finished standard image (see [docs/ab-boot.md](../../docs/ab-boot.md)).

## What it does (`00-run-chroot.sh`, chroot)

- Fails the build unless `rq_health_check.py`, `rq_slot_manager.sh`,
  `rq_common.sh`, `rq_update_slot.sh` and `rq_tryboot_retry.sh` are in `/usr/bin`
  and `rasqberry-health-check.service` and `rasqberry-tryboot-retry.service` are
  enabled.

## Files

- The scripts come from `RQB2-bin/` and the units from `RQB2-system/`, both
  installed (and the units enabled) by [01-deploy-files](../01-deploy-files/README.md).
- `files/convert-to-ab-boot-v3.sh` - used by the workflow, not by this stage.

## Notes

- `rasqberry-update-poller.timer` ships disabled: it installs new dev releases
  automatically and is a rig/dev tool. `rasqberry-update-check.timer` (enabled)
  only reports a newer release.
