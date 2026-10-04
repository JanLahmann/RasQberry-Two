# A/B Boot: How It Works

The A/B image holds two complete systems on one SD card, Slot A and Slot B. This
page is for developers: layout, first boot, updates, the boot mechanism and the
command-line tools. The user guide is on the website:
[rasqberry.org/02-software/03-ab-boot](https://rasqberry.org/02-software/03-ab-boot/).
Validation history: [ab-boot-validation.md](ab-boot-validation.md).

Update model: **ping-pong.** An update always goes into the slot that is not
running, A or B alike. The Pi tries it once (tryboot); when the health check
confirms it, it becomes the **start slot**. The other slot keeps the previous
system as the way back. Neither slot is special.

## Partition layout

| Partition | Label | Mount | Purpose | As shipped | After the first start |
|---|---|---|---|---|---|
| p1 | CONFIG | /boot/config | `autoboot.txt` and state files, shared by both slots | 512MB | same |
| p2 | BOOT-A | /boot/firmware (on A) | Boot files, Slot A | 512MB | same |
| p3 | boot-b | /boot/firmware (on B) | Boot files, Slot B | 512MB | same |
| p5 | SYSTEM-A | / (on A) | Root filesystem, Slot A | 10GiB | 45% (two systems), or the card minus DATA (one system) |
| p6 | SYSTEM-B | / (on B) | Root filesystem, Slot B | 16MB placeholder | 45%, or still the placeholder (one system) |
| p7 | DATA | /data | User data kept across updates | placeholder (~28MB) | 10% of the card |

The image is not built by pi-gen directly: CI runs
[`convert-to-ab-boot-v3.sh`](../stage-RQB2/08-ab-boot-support/files/convert-to-ab-boot-v3.sh)
over the finished standard image (`.github/workflows/RQB-image-v2.yaml`). That
script is the source of truth for the layout. The placeholders keep the download
small: the `-ab.img.xz` is about 1.7 GB (12.4 GB extracted), the same as the
standard image. A fresh Slot A has about 7.2GiB of its 10GiB in use.

CONFIG also holds `ab-layout` (`pending` / `dual` / `single` / `resume-*`), the
opt-out file `no-auto-expand` if someone made one, `slot-<A|B>-incomplete`
while a slot is written, and `last-switch-failed` after a rolled-back switch.
`/usr/config` is not shared: it lives on each slot's root.

## First boot

The standard image grows its root partition at first boot
(`rasqberry-firstboot.d/01-expand-filesystem.sh`). On the A/B image the converter
writes `/boot/firmware/skip-expansion` on BOOT-A (and so on boot-b), so that
task stands down: `do_expand_rootfs` cannot grow a root that is not the last
partition anyway.

Instead `rasqberry-ab-layout.service` runs
[`rq_expand_ab.sh`](../RQB2-bin/rq_expand_ab.sh) `firstboot` after the fstab
mounts and before anything reads `/data`. It acts only when CONFIG/`ab-layout`
says `pending` (the converter writes it), so cards written from older images
never change by themselves:

- **Card of 58GiB or more** (a "64 GB" card is about 59.6GiB): two systems.
  Fixed partitions take 1.5 GB; the rest is split 45% Slot A / 45% Slot B / 10%
  DATA. Slot A grows in place; Slot B and DATA are created. Measured on
  loop-device copies of the real image: 64 GB card 28.0 / 28.0 / 6.2 GB.
- **Card under 58GiB:** single-system mode. Slot A grows to the card minus DATA
  (10%), Slot B stays the 16MB placeholder, so partition numbers and every fstab
  stay the same; `ab-layout` becomes `single`. Measured: 32 GB card Slot A
  27.3 GB, DATA 3.0 GB. A small card cannot become a two-system card later (Slot A
  would have to shrink).
- **Opt-out:** an empty file `no-auto-expand` (`no-auto-expand.txt` works too)
  on the CONFIG partition keeps the card as written.
- **Interrupted** (power): `ab-layout` says `resume-dual` or `resume-single` and
  the next start finishes the job, whatever the opt-out says.

The new partition table is written in one `sfdisk` call and the kernel is told
per partition (`partx`): `parted -s` refuses to resize the extended partition
while Slot A is mounted. The little on the placeholder DATA (LED settings) is
copied aside and put back. Progress shows on the splash screen; the log is
`/var/log/rasqberry-expand.log`.

**Raspberry Pi Imager's OS customisation** (Wi-Fi, keyboard, SSH key, password)
lands on CONFIG, the first FAT partition, which the Pi does not boot from.
`rasqberry-imager-firstrun.service` moves it to BOOT-A before the layout runs and
restarts once; the next start applies it and restarts again
([00-firstboot-setup](../stage-RQB2/00-firstboot-setup/README.md)). This happens
on the first start of a newly written card only. A card that has run before
(`target-slot`, `slot-confirmed` or `current-slot` on CONFIG) - e.g. the trial
start of an updated slot - never applies a leftover `firstrun.sh` and never
restarts for it: it goes to `/var/lib/rasqberry/imager-ignored/` (root only).

What the card can do is `rq_expand_ab.sh mode`: `dual`, `dual-pending`, `single`,
`single-pending` (or `standard`). The menu follows it: **Software & Image
Updates** shows the **Slot Manager** only with two systems, **Prepare the card
for A/B updates** or **Use the whole card** while a card is still in its shipped
layout, and **Why there are no A/B updates on this card** in single-system mode.
By hand:

    sudo rq_expand_ab.sh status            # mode, sizes, state
    sudo rq_expand_ab.sh plan --text       # what it would do
    sudo rq_expand_ab.sh apply --yes       # do it (--dual / --single to choose)

## What survives an update

Each slot has its own root, so a freshly written slot starts with the image's
defaults. [`rq_carry_over.sh`](../RQB2-bin/rq_carry_over.sh)
(`rasqberry-carry-over.service`, before the network and the desktop) keeps what
makes the Pi yours (`rq_carry_over.sh list` prints it):

| What | How |
|---|---|
| `~/Shared`, `~/My-Quantum-Programs`, `~/.qiskit` (IBM Quantum account) | live on DATA (`/data/home/<user>/…`), symlinked from the home folder in both slots; a new slot's starter files do not overwrite the learner's |
| Wi-Fi networks | live on DATA (`/data/rasqberry/system-connections`), bind-mounted over `/etc/NetworkManager/system-connections` |
| LED panel settings | on DATA (`rq_device_settings.sh`) |
| desktop user's password (hash), hostname, time zone, locale, keyboard, "Browser at login", the checklist's "Don't ask again" | copied once from the other slot on the first start of a freshly written slot (marker `/var/lib/rasqberry/carry-over-pending`) |
| SSH host keys, `authorized_keys` | copied at update time (`rq_carry_ssh_identity.sh`) |

Not kept: other files in the home folder, installed demos, Docker images, added
Python packages. Docker images stay in each slot (`/var/lib/docker` is part of
the system): after an update the Docker demos download again, and their
consent dialog says so. All four take about 15 GB: a slot of a 64 GB card
(28 GB) holds them, but then lacks the 15GiB an update stages on the running
slot, which is why the website recommends 128 GB for all Docker demos. A 16 GB
card has room for one (not the Workshop & Qiskit Server). The new image pulls
from the old slot instead of the old updater pushing, so even the first update
from an older release carries everything over. The password is carried over
because otherwise an update would put the published default password back on a
device whose owner changed it, with SSH and VNC on. Without a real DATA
partition (standard image, or the placeholder) nothing is linked.

## Updating a slot

Menu: **Software & Image Updates** → **Slot Manager** → **Install an update into
the other system (Slot X)**. It runs the preflight first, offers the latest A/B
image of the image's own channel (others behind **Other release or channel...**),
applies the guard below and runs the update in the terminal with its progress.
From a shell:

    sudo rq_update_slot.sh --preflight                 # can the other slot be updated? (no download)
    rq_ab_releases.sh latest                           # newest A/B image of this channel
    sudo rq_slot_manager.sh plan-update <release-tag>  # what it would replace, and the guard
    sudo rq_update_slot.sh <ab-image-url> <release-tag>

- Use the `-ab.img.xz` image; the standard image cannot fill a slot.
- The target is always the slot that is not running; `--slot` can only name it.
- Refusals have their own exit codes: 20 the target is the running slot, 21 the
  target is the placeholder (card not prepared yet, or single-system mode; the
  message says which), 22 not enough space, 23 no A/B layout, 24 another update
  running, 25 no checksum, 26 an unconfirmed downgrade, 27 an unconfirmed
  overwrite of the last beta or stable system, 28 the running slot is still on
  trial (or a restart would start the other slot).
- It stages the download in `/var/tmp/rasqberry-updates` on the running slot
  and needs 15GiB free there.
- It verifies the image against `ab_extract_sha256` (and `ab_image_sha256`) of
  the release in [RQB-releases.json](https://rasqberry.org/RQB-releases.json).
  These fields are written by `.github/scripts/consolidate_json.py` on main.
- While it writes, `/boot/config/slot-<A|B>-incomplete` marks the slot as
  unusable. A target that stays mounted stops the update.
- It keeps `quiet splash` and adds `panic=10` to the new slot's `cmdline.txt`,
  `nofail` to its `/data` line, copies the SSH identity and sets the carry-over
  marker, then restarts into the new slot with tryboot.

**The guard (Jan): at least one slot keeps a beta or stable system.** The
stream comes from the version or tag: `development-*`/`dev-*` dev (rank 0),
`beta-*` beta (1), `v1.2.3`/`1.2.3`/`stable-*` stable (2).

- **Downgrade:** a lower stream than the target holds, or an older release of
  the same beta or stable stream. Always a warning (default: Cancel).
- **Last safe slot:** the target holds beta or stable, the running slot does
  not. A strong warning with a typed `REPLACE`; the menu offers the safer way
  first: switch to the target slot, then install into the other one.
- No warning for an empty target or a dev build over a dev build.

`rq_slot_manager.sh plan-update <tag>` is the one place that decides; the menu
and `rq_update_slot.sh` both use it. It prints key=value lines:

    target=B
    running=A
    target_holds=beta beta-2026-10-03-095636      # <stream> <version>; none empty / none unfinished
    running_holds=dev development-2026-10-04-014357
    new=dev development-2026-10-05-010101
    downgrade=stream                              # none | stream | older
    last_safe_slot=yes                            # yes | no
    advice=Slot B holds the only beta or stable system on this card. Safer: ...

`rq_update_slot.sh` asks in a terminal (y/N, a typed `REPLACE`); without one it
refuses (26, 27) unless `--allow-downgrade` / `--force-replace-safe-slot` say
so. The menu asks in its own dialogs and passes these options.

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
boot only. The new slot is **on probation**: `rasqberry-health-check.service`
(`rq_health_check.py`) checks the venv and Qiskit (and on a desktop image the
display manager within 5 minutes), then runs `confirm`, which makes the slot the
`[all]` default. Without anyone at the Pi, a failed trial returns to the old
slot:

- **The kernel cannot start:** `panic=10` reboots after 10s into the old slot.
  `rasqberry-tryboot-retry.service` re-issues the tryboot once (the flag is
  sometimes lost after a big write), then the old slot records the failure.
- **A check fails:** the health check records it and reboots into the old slot
  at once.
- **Start-up hangs:** `rasqberry-probation.timer` reboots into the old slot 15
  minutes after boot if the trial is still unconfirmed; systemd's hardware
  watchdog (15s, armed for the trial boot only) catches a kernel or PID 1 hang.

After a confirmed start, `confirm` writes `[all]` for the running slot, A or B:
that slot is now the start slot. A failed switch leaves
`/boot/config/last-switch-failed`, which `rq_slot_manager.sh status` shows. `switch-to` and `rollback` refuse a slot that
holds no system (exit 25): the placeholder, a freshly expanded Slot B, or an
interrupted write. Starting one halts the kernel; a rollback into one is
permanent. `--force` skips the check.

## Going back

The previous system stays in the other slot until the next update replaces it:

    sudo rq_slot_manager.sh switch-to A --reboot      # try it once; a good start makes it the start slot
    sudo rq_slot_manager.sh rollback && sudo reboot   # make it the start slot without a trial

## Recovery

If the Pi hangs after a switch (black screen), switch it off and on: the next
start returns to the previous slot (a second power cycle if the switch was
retried). If neither slot starts: put the card in a computer, open CONFIG and
set `boot_partition=2` under `[all]` in `autoboot.txt` (Slot A; `3` is Slot B).

## Command reference

```bash
sudo rq_expand_ab.sh status                       # two systems, one, or not set up yet
sudo rq_slot_manager.sh status                    # booted slot, slot contents, sizes, warnings
sudo rq_slot_manager.sh summary                   # key=value for scripts (current, slot_a, slot_b, expanded, card_mode, ...)
sudo rq_update_slot.sh --preflight                # can the other slot take an update?
sudo rq_slot_manager.sh plan-update <tag>         # what an update would replace (the guard)
sudo rq_update_slot.sh <ab-image-url> <tag>       # write a system into the other slot
sudo rq_slot_manager.sh switch-to B --reboot      # try Slot B (probation)
sudo rq_slot_manager.sh confirm                   # keep the booted slot
sudo rq_slot_manager.sh rollback && sudo reboot   # back to the other slot
cat /etc/rasqberry-version                        # build marker of this slot
```

`/etc/rpi-issue` records only the pi-gen commit and does not change between
RasQberry builds: do not use it to tell images apart.
