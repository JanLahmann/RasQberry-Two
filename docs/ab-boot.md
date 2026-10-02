# A/B Boot: Setup and Use

The A/B image carries **two complete systems** on one SD card: Slot A and Slot B.
You update the slot you are not using, boot into it, and if it misbehaves the Pi
falls back to the slot that worked. That makes it safe to test an image on real
hardware without losing a working one.

For validation history and the fixes behind it, see
[ab-boot-validation.md](ab-boot-validation.md). This page is how to use it.

---

## First start: the card sets itself up

The A/B image ships small so the download stays ~12 GB: Slot A is 10 GiB, Slot B
and the data partition are placeholders (16 MB and 28 MB). On its **first start**
the card is laid out to fit, before the desktop comes up
(`rasqberry-ab-layout.service` -> [`rq_expand_ab.sh`](../RQB2-bin/rq_expand_ab.sh) `firstboot`):

| Card | What the first start does | Result (measured on loop-device copies of the real image) |
|---|---|---|
| **64 GB or larger** (58 GiB or more - a genuine "64GB" card is ~59.5 GiB) | **two systems**: Slot A grows in place, Slot B and DATA are created | 64 GB card: Slot A 28.0 GB, Slot B 28.0 GB, DATA 6.2 GB |
| **smaller** (16 GB, 32 GB) | **one system**: Slot A grows to the card minus DATA; Slot B stays a 16 MB placeholder | 32 GB: Slot A 27.3 GB, DATA 3.0 GB; 16 GB: Slot A 12.9 GB, DATA 1.4 GB |

It takes seconds to a few minutes and shows "Preparing the SD card (n/7) - do
not switch off" on the splash screen. The split for two systems is 45% / 45% /
10% of the space after the boot partitions, as the manual expansion always was.
DATA is 10% of the card in both cases (it holds the user data that survives
updates, see below). A log is written to `/var/log/rasqberry-expand.log`.

This reverses the earlier "the user decides" rule of #142 (Jan, 2026-10-02).
It only happens on a card written from an image that says so: the converter
writes `ab-layout` = `pending` onto the CONFIG partition. Cards written from
older images are never repartitioned by themselves.

### Opting out: `no-auto-expand`

To keep a new card **exactly as written**, create an empty file named
**`no-auto-expand`** (`no-auto-expand.txt` works too, for Windows) on the
**CONFIG** partition before its first start - that is the first FAT partition
a PC shows when the card is inserted, next to `autoboot.txt` and `ab-layout`.
The card then stays at Slot A 10 GiB with placeholders until you set it up
from the menu, or delete the file (the next start then does it).

### By hand

    sudo raspi-config  ->  0 RasQberry  ->  Software & Image Updates

shows "Prepare the card for A/B updates" (64GB+ card) or "Use the whole card"
(smaller card) whenever a card is still in its shipped layout, e.g. after the
opt-out or on a card written from an older image. From a shell:

    sudo rq_expand_ab.sh status            # mode, sizes, state
    sudo rq_expand_ab.sh plan --text       # what it would do
    sudo rq_expand_ab.sh apply --yes       # do it (--dual / --single to choose)

Slot A keeps its contents - it is grown in place. Slot B and DATA are created
fresh; the little that is on the 28 MB placeholder DATA (the LED settings) is
copied aside first and put back. If the set-up is cut off (power), `ab-layout`
says `resume-dual` or `resume-single` and the next start finishes it.
The partition table is written in one `sfdisk` call; `parted` is not used
any more, because `parted -s` refuses to resize the extended partition while
Slot A is mounted (on the Pi it only worked because the root shows up as
`/dev/root` and parted could not tell it was busy).

### Small cards: one system

A card under 64 GB runs **one system** ("single-system mode"): it uses the
whole card, but there is no second slot to install an update into. The menu
says so instead of offering dead ends: "Software & Image Updates" shows
"Why there are no A/B updates on this card" instead of the Slot Manager, and
"Check for a newer image" says to write the new image to a card (copy your
files first - that erases the card). `rq_update_slot.sh` explains the same
instead of "run partition expansion first". A small card cannot become a
two-system card later (that would need Slot A to shrink); use a 64 GB card.

### Requirements and checks

- The Pi boots normally (the set-up runs on the live system, no reboot).
- `sudo rq_slot_manager.sh status` explains what the card can do whenever Slot
  B is a placeholder. If `SYSTEM-B` is over 1 GB, the card has two systems.

---

## What survives an update

Each slot has its own root filesystem, so a slot written by an update starts
with the image's defaults. Since B4 ([`rq_carry_over.sh`](../RQB2-bin/rq_carry_over.sh),
`rasqberry-carry-over.service`, before the network and the desktop start):

| | How |
|---|---|
| `~/Shared` (a folder for your files) | lives on DATA (`/data/home/<user>/Shared`), linked from the home folder in both slots |
| `~/.qiskit` (IBM Quantum account) | lives on DATA (`/data/home/<user>/.qiskit`), linked |
| Wi-Fi networks (NetworkManager profiles) | live on DATA (`/data/rasqberry/system-connections`), bind-mounted over `/etc/NetworkManager/system-connections` |
| LED panel settings | on DATA (`rq_device_settings.sh`, #290) |
| password of the desktop user, hostname, time zone, locale, keyboard layout, "Browser at login", the checklist's "Don't ask again" | copied once from the other slot on the first start of a freshly written slot (the image carries `/var/lib/rasqberry/carry-over-pending`) |
| SSH host keys and `authorized_keys` | copied at update time (`rq_carry_ssh_identity.sh`, #275) |

**Not kept** (they stay in the old slot): other files in the home folder,
installed demos, Docker images, Python packages you added. Put files you want
to keep in `~/Shared`.

The new image pulls these from the old slot rather than the old updater pushing
them, so even the first update from a release that knows nothing about it
carries everything over; a slot that predates DATA also has its `~/.qiskit` and
Wi-Fi profiles moved onto DATA then.

**The password** is carried over (its hash from `/etc/shadow`, never the plain
text; only the desktop user's entry, system accounts come from the new image).
Otherwise every update would silently put the published default password back on
a device whose owner had changed it, with SSH and VNC on - and the owner's own
password would stop working.

---

## Then: put a system in Slot B

The model: **Slot A is the stable system, Slot B the testing slot.** Updates
always go into Slot B; a Slot B that has proven itself is copied to Slot A
with PROMOTE.

From the menu: `sudo raspi-config` → 0 RasQberry → Software & Image Updates →
Slot Manager → *Install an update into Slot B*. It first checks whether Slot B
can take an update, then offers the latest A/B image of the image's own
channel (beta, dev or stable; other releases and channels behind *Other*),
and runs the update in the terminal with its progress.

From a terminal, use the **AB image** (`-ab.img.xz`), not the standard image —
the standard image has no A/B layout and will not boot as a slot.

    sudo rq_update_slot.sh --preflight                 # can Slot B be updated? (nothing is downloaded)
    rq_ab_releases.sh latest                           # newest A/B image of this image's channel
    sudo rq_update_slot.sh <ab-image-url> <release-tag>

It refuses to overwrite the slot you are booted from, so you cannot saw off the
branch you are sitting on. Running Slot B, first PROMOTE it (or switch back to
Slot A), then update. The refusals have their own exit codes (20 running
slot, 21 Slot B not set up - card not prepared yet, or one system on a small
card, 22 not enough space, 23 no A/B layout, 24 another update running), which
is what the menu explains.

While a slot is being written (or copied by PROMOTE),
`/boot/config/slot-<A|B>-incomplete` exists; the slot counts as unusable
until the write has finished.

## Switching, confirming, rolling back

    sudo rq_slot_manager.sh switch-to B --reboot   # boot Slot B next (tryboot)
    sudo rq_slot_manager.sh status                 # where am I, what does each slot hold?
    sudo rq_slot_manager.sh confirm                # keep this slot
    sudo rq_slot_manager.sh rollback && sudo reboot

`switch-to` and `rollback` refuse a slot that holds no system (exit code 25):
the placeholder, a freshly expanded Slot B, or an interrupted update. Starting
an empty slot halts the kernel and the Pi hangs until it is switched off and
on; a rollback into one is permanent. `--force` skips the check.
`rq_slot_manager.sh summary` prints the state as `key=value` lines
(`current`, `confirmed`, `default`, `slot_a`, `slot_b`, `expanded`,
`card_mode`, ...); `card_mode` is what `rq_expand_ab.sh mode` says: `dual`,
`dual-pending`, `single` or `single-pending`.

A slot booted with `switch-to` is **on probation** (the firmware starts it once
with the tryboot flag): unless it is confirmed, the next reboot returns to the
previous slot. The health check confirms a healthy slot automatically. Since B4
the return needs nobody at the Pi (R-054):

- **The kernel cannot start**: `panic=10` in both slots' `cmdline.txt` reboots
  after 10 s, and the reboot starts the old slot. `rq_tryboot_retry.sh` tries
  the new slot once more (the tryboot flag is sometimes lost after a big
  write), then gives up; the old slot records the failure.
- **The new slot starts but a check fails** (venv, Qiskit, and - on a desktop
  image - the display manager within 5 minutes): the health check records it
  and reboots into the old slot at once, without retrying.
- **Start-up hangs** (a service never finishes, emergency mode):
  `rasqberry-probation.timer` reboots into the old slot 15 minutes after boot
  if the trial boot is still unconfirmed. A kernel or PID 1 hang is caught by
  systemd's hardware watchdog (15 s), armed for the trial boot only.

A failed switch leaves `/boot/config/last-switch-failed` (slot, reason, time),
which `rq_slot_manager.sh status` shows.

**If the Pi still hangs after a switch** (black screen, no desktop): switch it
off and on. A tryboot is tried once, so the next start returns to the previous
slot; if the switch is retried automatically, a second power cycle is needed.
**If it hangs at every start** (a rollback made an empty slot the default, on
images before the empty-slot check): put the card into another computer, open
the `CONFIG` partition and set `boot_partition=2` (Slot A) under `[all]` in
`autoboot.txt` (`3` is Slot B).

Slot A is the **stable** slot and Slot B is the **testing** slot. When a system
in Slot B has proven itself:

    sudo rq_slot_manager.sh promote     # copy tested Slot B → stable Slot A

`promote` asks for a typed `PROMOTE` in a terminal; the menu asks in its own
dialog and passes `--yes`. Afterwards restart: the Pi starts from Slot A, and
Slot B is free for the next update.

## Partition layout

| Partition | Label | Mount | Purpose | As shipped |
|---|---|---|---|---|
| p1 | CONFIG | /boot/config | Shared boot config (autoboot.txt) | 512MB |
| p2 | BOOT-A | /boot/firmware (on A) | Boot files, Slot A | 512MB |
| p3 | boot-b | /boot/firmware (on B) | Boot files, Slot B | 512MB |
| p5 | SYSTEM-A | / (on A) | Root filesystem, Slot A | 10GB |
| p6 | SYSTEM-B | / (on B) | Root filesystem, Slot B | **16MB placeholder** (set up on first start on 64GB+ cards) |
| p7 | DATA | /data | Shared user data (see "What survives an update") | **28MB placeholder** (10% of the card after the first start) |

The CONFIG partition also holds `ab-layout` (`pending` / `dual` / `single` /
`resume-*`, see above), the opt-out file `no-auto-expand` if you made one, and
`last-switch-failed` after a rolled-back switch.

`/boot/config` (p1) is shared by both slots and holds `autoboot.txt` — that is
what the firmware reads to decide which slot boots. `/usr/config` is *not*
shared: it lives on each slot's own root.

## Quick reference

```bash
sudo rq_expand_ab.sh status                       # two systems, one, or not set up yet
sudo raspi-config     # -> 0 RasQberry -> Software & Image Updates (set up by hand)

sudo rq_slot_manager.sh status                    # current slot, slot contents, sizes, warnings
sudo rq_update_slot.sh --preflight                # can Slot B take an update?
sudo rq_update_slot.sh <ab-image-url> <tag>       # write a system into Slot B
sudo rq_slot_manager.sh switch-to B --reboot      # try Slot B
sudo rq_slot_manager.sh confirm                   # keep it
sudo rq_slot_manager.sh rollback && sudo reboot   # go back
sudo rq_slot_manager.sh promote                   # Slot B -> Slot A (stable)
```

## Which image am I running?

    cat /etc/rasqberry-version

That is the authoritative build marker. `/etc/rpi-issue` records only the pi-gen
tool commit and does **not** change between RasQberry builds — do not use it to
tell images apart.
