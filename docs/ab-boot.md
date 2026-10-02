# A/B Boot: How It Works

The A/B image holds two complete systems on one SD card, Slot A and Slot B. This
page is for developers: layout, first boot, updates, the boot mechanism and the
command-line tools. The user guide is on the website:
[rasqberry.org/02-software/03-ab-boot](https://rasqberry.org/02-software/03-ab-boot/).
Validation history: [ab-boot-validation.md](ab-boot-validation.md).

Update model: **Slot A is stable, Slot B is for testing.** Updates are written
to Slot B, the Pi tries Slot B, and **promote** copies a tested Slot B to Slot A.

## Partition layout

| Partition | Label | Mount | Purpose | As shipped |
|---|---|---|---|---|
| p1 | CONFIG | /boot/config | `autoboot.txt`, shared by both slots | 512MB |
| p2 | BOOT-A | /boot/firmware (on A) | Boot files, Slot A | 512MB |
| p3 | boot-b | /boot/firmware (on B) | Boot files, Slot B | 512MB |
| p5 | SYSTEM-A | / (on A) | Root filesystem, Slot A | 10GiB |
| p6 | SYSTEM-B | / (on B) | Root filesystem, Slot B | 16MB placeholder |
| p7 | data | /data | Data kept across updates | 16MB placeholder |

The image is not built by pi-gen directly: CI runs
[`convert-to-ab-boot-v3.sh`](../stage-RQB2/08-ab-boot-support/files/convert-to-ab-boot-v3.sh)
over the finished standard image (`.github/workflows/RQB-image-v2.yaml`). That
script is the source of truth for the layout. The placeholders keep the download
small: the `-ab.img.xz` is about 1.7GB (12.4GB extracted), the same as the
standard image. A fresh Slot A has about 7.2GiB of its 10GiB in use.

`/usr/config` is not shared: it lives on each slot's root.

## First boot

<!-- Depends on batch B4 (dev-ab-firstboot). Names marked <...> are placeholders. -->

The standard image grows its root partition at first boot
(`rasqberry-firstboot.d/01-expand-filesystem.sh`). On the A/B image the converter
writes `/boot/firmware/skip-expansion` on BOOT-A (and so on boot-b), so that
task stands down: `do_expand_rootfs` cannot grow a root that is not the last
partition anyway.

Instead, a first-boot task runs `rq_expand_ab.sh` (split out of
`do_expand_ab_partitions` in `RQB2_menu.sh`):

- **Card of 58GiB or more** (a "64GB" card is about 59.6GiB): Slot A, Slot B and
  data are expanded automatically. Fixed partitions take 1.5GB; the rest is
  split 45% Slot A / 45% Slot B / 10% data. Measured: 64GB card about
  26/26/6GB, 119GB card 52.9/52.9/11.8GB, 238GB card 106.6/106.6/23.7GB. Slot A
  grows in place; Slot B and data are formatted.
- **Opt-out:** an empty file `<opt-out marker>` on the CONFIG partition keeps
  the card as it is.
- **Card under 58GiB:** single-system mode. Slot A and data grow to fill the
  card, Slot B stays a placeholder, `<single-mode marker>` is written, and the
  menu hides the A/B entries.

The manual entry stays in the menu (**Software & Image Updates** → **Expand A/B
Partitions**). The log is `/var/log/rasqberry-expand.log`.

## Updating a slot

    sudo rq_update_slot.sh <ab-image-url> <release-tag> --slot B

Menu: **Software & Image Updates** → **Slot Manager** → **Update Slot B with
new image**.

- It refuses to write the slot it is running from, and a placeholder slot.
- It stages the download in `/var/tmp/rasqberry-updates` on the running slot
  and needs 15GiB free there, so an unexpanded card cannot update.
- It verifies the image against `ab_extract_sha256` (and `ab_image_sha256`) of
  the release in [RQB-releases.json](https://rasqberry.org/RQB-releases.json).
  These fields are written by `.github/scripts/consolidate_json.py` on main.
- Carry-over into the new slot: SSH host keys and `authorized_keys`
  (`rq_carry_ssh_identity.sh`), and through `/data` the LED settings
  (`rq_device_settings.sh`), Wi-Fi profiles, `~/.qiskit` and the Shared folder
  (`<carry-over hook>`, batch B4). Installed demos are per slot.
- It then reboots into Slot B with tryboot.

`rasqberry-update-poller.timer` (automatic updates of dev builds, for the rig)
ships disabled.

## Boot mechanism

The firmware reads `autoboot.txt` on CONFIG:

```
[all]
tryboot_a_b=1
boot_partition=2
boot_partition_fallback=3

[tryboot]
boot_partition=3
boot_partition_fallback=2
```

`boot_partition=2` boots Slot A, `3` Slot B. A switch (`switch-to B --reboot`)
reboots once with the tryboot flag, so the `[tryboot]` section applies to that
boot only. The new slot is **on probation**:

- `rasqberry-tryboot-retry.service` re-issues the tryboot reboot once if the
  firmware dropped the flag.
- `rasqberry-health-check.service` (`rq_health_check.py`) checks the venv and
  Qiskit, then runs `confirm`, which makes the slot the `[all]` default.
- If the slot is not confirmed, the next boot returns to the previous slot.
  Automatic recovery from a hang (kernel `panic=`, watchdog, reboot on a failed
  health check) is batch B4.

## Promote

    sudo rq_slot_manager.sh promote

Runs from Slot B only. It copies Slot B to Slot A (`rsync -aAX --delete`, so
user files in Slot A are replaced), copies the boot partition and fixes
`root=` in Slot A's `cmdline.txt`, then makes Slot A the default. Reboot to
start Slot A. The next update goes into Slot B again.

## Recovery

If neither slot starts: put the card in a computer, open CONFIG and set
`boot_partition=2` under `[all]` in `autoboot.txt` (Slot A).

## Command reference

```bash
sudo rq_slot_manager.sh status                    # booted slot, sizes, warnings
sudo rq_update_slot.sh <ab-image-url> <tag> --slot B   # write a system into Slot B
sudo rq_slot_manager.sh switch-to B --reboot      # try Slot B (probation)
sudo rq_slot_manager.sh confirm                   # keep the booted slot
sudo rq_slot_manager.sh rollback && sudo reboot   # back to the other slot
sudo rq_slot_manager.sh promote                   # Slot B -> Slot A
cat /etc/rasqberry-version                        # build marker of this slot
```

`/etc/rpi-issue` records only the pi-gen commit and does not change between
RasQberry builds: do not use it to tell images apart.
