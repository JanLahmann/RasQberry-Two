# A/B Images: Two Systems, One Card

Alongside the standard image we publish an **A/B image** (`-ab.img.xz`). It puts
**two complete systems on one SD card** — Slot A and Slot B. You update the slot
you are not using, boot into it, and if it misbehaves the Pi falls back to the
one that worked.

That makes it safe to try a new release on real hardware without losing a working
system. If you just want a RasQberry that works, take the standard image — you do
not need this page.

## Expand the partitions first

**A freshly flashed A/B card cannot do A/B until you expand it**, and this is the
step people miss.

To keep the download around 12GB instead of 120GB, the image ships with Slot B and
the data partition as **16MB placeholders**. There is no room for a second system
in 16MB, so nothing A/B-related works until they grow to fit your card:

```bash
sudo raspi-config   →   RasQberry   →   AB_BOOT   →   EXPAND
```

You need a **64GB or larger card** (expansion refuses below ~63GB). It asks once,
shows the sizes it proposes, takes a few minutes, and needs no reboot.

**If you skip this**, here is what you will see — none of it looks like "you
forgot to expand", which is exactly why it is worth doing first:

- The disk is ~95% full the moment you boot. The system is ~9.3GB and the
  unexpanded Slot A is 10GB. That is simply all the space there is.
- Demos that build a Docker image (Quantum-Mixer, Qoffee-Maker) fill the disk and
  fail. ~500MB of headroom is not enough for a build.
- Updating a slot fails with *"Not enough free space … 15GB needed"* — it stages
  the download on the 10GB root, so no amount of tidying up will help.
- Most of your SD card sits unpartitioned.

### What you get

Fixed partitions take 1.5GB; the rest is split **45% Slot A / 45% Slot B /
10% shared data**. Measured on real cards:

| Your card | Slot A | Slot B | Data |
|---|---|---|---|
| 64GB | ~26GB | ~26GB | ~6GB |
| 128GB | 52.9GB | 52.9GB | 11.8GB |
| 256GB | 106.6GB | 106.6GB | 23.7GB |

Slot A keeps everything you already have — it grows in place. Slot B and the data
partition are created fresh and formatted, so **anything already in `/data` is
lost**. On a card you just flashed there is nothing there to lose.

To check where you stand:

```bash
sudo rq_slot_manager.sh status
```

It tells you the slot you booted, the partition sizes, and warns you if Slot B is
still a placeholder.

## Using the second slot

Put a system in the slot you are not running (use the **`-ab`** image — the
standard one has no A/B layout):

```bash
sudo rq_update_slot.sh <ab-image-url> <release-tag>
```

It refuses to overwrite the slot you are booted from, so you cannot saw off the
branch you are sitting on.

Then try it:

```bash
sudo rq_slot_manager.sh switch-to B --reboot
```

A slot booted this way is **on probation**: unless it is confirmed, the next
reboot returns you to the slot you came from. A healthy system confirms itself
automatically. That is the whole point — a broken image cannot strand you.

```bash
sudo rq_slot_manager.sh confirm                # keep this slot
sudo rq_slot_manager.sh rollback && sudo reboot   # go back now
```

Slot A is the **stable** slot, Slot B the **testing** slot. Once a system in Slot B
has earned it:

```bash
sudo rq_slot_manager.sh promote     # copy tested Slot B → stable Slot A
```

## Which image am I running?

```bash
cat /etc/rasqberry-version
```

That is the build marker. (`/etc/rpi-issue` only records the pi-gen tool commit
and does not change between RasQberry builds — it will not tell images apart.)

## Details

Layout, the boot mechanism, and the reasoning are in
[docs/ab-boot.md](https://github.com/JanLahmann/RasQberry-Two/blob/development/docs/ab-boot.md)
in the repository.
