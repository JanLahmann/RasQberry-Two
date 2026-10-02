# 08-ab-boot-support

Checks that the image carries what an A/B image needs at runtime. The A/B
partition layout itself is created after the build by
[`files/convert-to-ab-boot-v3.sh`](files/convert-to-ab-boot-v3.sh), which the image
workflow runs on the finished standard image (see [docs/ab-boot.md](../../docs/ab-boot.md)).

## What it does (`00-run-chroot.sh`, chroot)

- Fails the build unless `rq_health_check.py`, `rq_slot_manager.sh`,
  `rq_common.sh`, `rq_update_slot.sh`, `rq_tryboot_retry.sh`, `rq_expand_ab.sh`
  and `rq_carry_over.sh` are in `/usr/bin` and `rasqberry-health-check.service`,
  `rasqberry-tryboot-retry.service`, `rasqberry-ab-layout.service`,
  `rasqberry-carry-over.service` and `rasqberry-probation.timer` are enabled.

## The A/B units (B4)

All in `RQB2-system/`, installed and enabled on every image; on a standard
image they find no `/boot/config` and do nothing.

| Unit | When | What |
|---|---|---|
| `rasqberry-ab-layout.service` | first start, after the fstab mounts, before `/data` is used | `rq_expand_ab.sh firstboot`: lays out a card whose CONFIG/`ab-layout` says `pending` - two systems on 58 GiB+, one system below; skipped with CONFIG/`no-auto-expand` |
| `rasqberry-carry-over.service` | every start, before NetworkManager, ssh and the desktop | `rq_carry_over.sh boot`: on a fresh slot copies password hash, hostname, locale, time zone, keyboard from the other slot; links `~/Shared`, `~/.qiskit` and the Wi-Fi profiles to `/data` |
| `rasqberry-tryboot-retry.service` | every start | re-issues a lost tryboot once; on the trial boot of a new slot arms systemd's 15 s hardware watchdog |
| `rasqberry-health-check.service` | every start | confirms the slot; on a trial boot a failed check rolls back (reboot into the old slot) |
| `rasqberry-probation.timer` | 15 min after every start | rolls back a trial boot that is still unconfirmed (survives emergency mode) |

## Files

- The scripts come from `RQB2-bin/` and the units from `RQB2-system/`, both
  installed (and the units enabled) by [01-deploy-files](../01-deploy-files/README.md).
- `files/convert-to-ab-boot-v3.sh` - used by the workflow, not by this stage.
  Since B4 it also writes `panic=10` into both `cmdline.txt` (a kernel that
  cannot start reboots instead of hanging), `nofail` on the `/data` fstab line
  of both slots (a missing `/data` must not stop the boot), CONFIG/`ab-layout`
  = `pending` (lets the first start lay out the card) and
  `/var/lib/rasqberry/carry-over-pending` in Slot A (a fresh slot takes over
  the other slot's settings). Lab-tested on a synthetic image; the real image
  needs a CI build.

## Notes

- `rasqberry-update-poller.timer` ships disabled: it installs new dev releases
  automatically and is a rig/dev tool. `rasqberry-update-check.timer` (enabled)
  only reports a newer release.
