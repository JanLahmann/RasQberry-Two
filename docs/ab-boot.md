# A/B Boot: Setup and Use

The A/B image carries **two complete systems** on one SD card: Slot A and Slot B.
You update the slot you are not using, boot into it, and if it misbehaves the Pi
falls back to the slot that worked. That makes it safe to test an image on real
hardware without losing a working one.

For validation history and the fixes behind it, see
[ab-boot-validation.md](ab-boot-validation.md). This page is how to use it.

---

## First: expand the partitions

**A freshly flashed A/B image cannot do A/B until you expand it.** The image
ships with Slot B and the data partition as **16MB placeholders** — there is no
room to put a system in Slot B, so every A/B operation fails until they grow:

| Symptom on an unexpanded card | What you are actually seeing |
|---|---|
| `SYSTEM-B` is 16MB in `lsblk` | The placeholder. This is the giveaway. |
| Root filesystem sits at ~95% full when idle | The image is ~9.3GB and the unexpanded Slot A is 10GB. That is all the space there is. |
| `rq_update_slot.sh` dies with "Not enough free space … 15GB needed" | It stages the download in `/var/tmp`, on the 10GB root. The requirement cannot be met on an unexpanded slot, no matter how much you clean up. |
| Docker demos (quantum-mixer, Qoffee-Maker) fill the disk and die | ~500MB of headroom cannot hold an image build. |
| Most of the SD card is unpartitioned | e.g. a 238GB card with only ~11.5GB in use. |

The placeholders are deliberate. The A/B image is not built by pi-gen directly:
CI takes the finished standard image and runs
[`stage-RQB2/08-ab-boot-support/files/convert-to-ab-boot-v3.sh`](../stage-RQB2/08-ab-boot-support/files/convert-to-ab-boot-v3.sh)
over it (`.github/workflows/RQB-image-v2.yaml`), which rewrites 2 partitions into
the 7-partition A/B layout. That script is the source of truth for the layout,
and its own header states the strategy:

> Key improvements over v2:
>   - Small initial image (~12GB) for fast download
>   - Partitions expand via raspi-config on 64GB+ SD cards

So Slot B and data are 16MB **so that the download stays ~12GB instead of ~120GB**
— the image ships minimal and grows to fit the card it lands on. The expansion
percentages (data 10%, system-a 45%, system-b 45%) are specified in that header
and implemented in `do_expand_ab_partitions`; if you change one, change both.

### Why isn't it automatic, like the standard image?

Because it was made manual on purpose. The two images expand differently:

| | Standard image | A/B image |
|---|---|---|
| Expands | automatically, on first boot | **only when you ask** |
| By | `/usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh`, run by `rasqberry-firstboot.service` → `raspi-config nonint do_expand_rootfs` | `raspi-config` → RasQberry → AB_BOOT → EXPAND (`do_expand_ab_partitions` in `RQB2-config/RQB2_menu.sh`) |
| Decides sizes | grow root to fill the card | you confirm a 45/45/10 split first |

There is **no standalone A/B expansion script, by design.** One existed
(`stage-RQB2/00-firstboot-expansion/files/02-expand-ab-partitions.sh`) and was
removed in `54f6a3f` (2025-11-23, issue #142): *"Replace automatic firstboot
expansion with manual raspi-config approach for A/B boot images. This gives
users control over partition sizing."* Splitting a card in half is not a
decision to make behind the user's back, so A/B asks. The trade is that a fresh
A/B card does nothing until someone knows to ask — which is what this page is
for.

The firstboot task is generated into the image at build time (a heredoc in
`stage-RQB2/00-firstboot-setup/00-run-chroot.sh`), so it exists on the running
Pi but not as a file in this repo — grepping the source for its filename finds
nothing.

It is meant to stand down on A/B images via a `/boot/firmware/skip-expansion`
marker ("typically used for A/B boot setup"). **That marker is not actually on
the A/B images we ship** — checked on two rig Pis, neither had it — so the
standard task does run on an A/B card. In practice it is harmless: it marks
itself done without expanding, because `raspi-config nonint do_expand_rootfs`
will not grow a root partition that is not last on the disk (p6 and p7 sit after
it). It leaves `01-expand-filesystem.sh.done` behind and no expansion, which is
one more reason a fresh A/B card looks like it "already expanded" when it has
not. Worth either shipping the marker or teaching the task to recognise an A/B
layout.

### Requirements

- **A 64GB or larger SD card.** Expansion refuses to run below ~63GB. On a
  smaller card you keep the single 10GB Slot A and simply do not use A/B.
- The Pi boots normally (expansion runs on the live system).

### How to expand

    sudo raspi-config   →   RasQberry   →   AB_BOOT   →   EXPAND

It shows the proposed sizes, asks once, then takes a few minutes. **Do not power
off during it.** No reboot is needed afterwards. A log is written to
`/var/log/rasqberry-expand.log`.

### What you get

Fixed partitions (config + boot-a + boot-b = 1.5GB) come off the top; the rest is
split **45% Slot A / 45% Slot B / 10% data**. Measured on real cards:

| SD card | System-A | System-B | Data | |
|---|---|---|---|---|
| 119GB | 52.9GB | 52.9GB | 11.8GB | validated 2025-12-31 |
| 238GB | 106.6GB | 106.6GB | 23.7GB | validated 2026-07-17 |

A 64GB card lands near 26GB / 26GB / 6GB.

Slot A keeps its contents — it is grown in place, not rewritten. Slot B and data
are created fresh and formatted, so **anything in `/data` is destroyed**. On a
newly flashed card there is nothing there to lose. The operation cannot be
undone, so if `/data` holds anything you care about, copy it off first.

### Checking

    sudo rq_slot_manager.sh status

`status` warns you when Slot B is still a placeholder. If `SYSTEM-B` is over 1GB,
you are expanded.

---

## Then: put a system in Slot B

Use the **AB image** (`-ab.img.xz`), not the standard image — the standard image
has no A/B layout and will not boot as a slot.

    sudo rq_update_slot.sh <ab-image-url> <release-tag>

It refuses to overwrite the slot you are booted from, so you cannot saw off the
branch you are sitting on.

## Switching, confirming, rolling back

    sudo rq_slot_manager.sh switch-to B --reboot   # boot Slot B next (tryboot)
    sudo rq_slot_manager.sh status                 # where am I?
    sudo rq_slot_manager.sh confirm                # keep this slot
    sudo rq_slot_manager.sh rollback && sudo reboot

A slot booted with `switch-to` is **on probation**: unless it is confirmed, the
next reboot returns to the previous slot. The health check confirms a healthy
slot automatically. That is the safety net — a slot that cannot boot cannot trap
you.

Slot A is the **stable** slot and Slot B is the **testing** slot. When a system
in Slot B has proven itself:

    sudo rq_slot_manager.sh promote     # copy tested Slot B → stable Slot A

## Partition layout

| Partition | Label | Mount | Purpose | As shipped |
|---|---|---|---|---|
| p1 | CONFIG | /boot/config | Shared boot config (autoboot.txt) | 512MB |
| p2 | BOOT-A | /boot/firmware (on A) | Boot files, Slot A | 512MB |
| p3 | boot-b | /boot/firmware (on B) | Boot files, Slot B | 512MB |
| p5 | SYSTEM-A | / (on A) | Root filesystem, Slot A | 10GB |
| p6 | SYSTEM-B | / (on B) | Root filesystem, Slot B | **16MB placeholder** |
| p7 | data | /data | Shared user data | **16MB placeholder** |

`/boot/config` (p1) is shared by both slots and holds `autoboot.txt` — that is
what the firmware reads to decide which slot boots. `/usr/config` is *not*
shared: it lives on each slot's own root.

## Quick reference

```bash
# One time, on a 64GB+ card - REQUIRED before anything else works
sudo raspi-config     # -> RasQberry -> AB_BOOT -> EXPAND

sudo rq_slot_manager.sh status                    # current slot, sizes, warnings
sudo rq_update_slot.sh <ab-image-url> <tag>       # write a system into the other slot
sudo rq_slot_manager.sh switch-to B --reboot      # try the other slot
sudo rq_slot_manager.sh confirm                   # keep it
sudo rq_slot_manager.sh rollback && sudo reboot   # go back
sudo rq_slot_manager.sh promote                   # Slot B -> Slot A (stable)
```

## Which image am I running?

    cat /etc/rasqberry-version

That is the authoritative build marker. `/etc/rpi-issue` records only the pi-gen
tool commit and does **not** change between RasQberry builds — do not use it to
tell images apart.
