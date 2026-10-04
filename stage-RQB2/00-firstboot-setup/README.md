# Stage: 00-firstboot-setup

## Purpose

Install the RasQberry modular firstboot service that runs critical initialization tasks on the first boot, including filesystem expansion and VNC enablement.

**Note:** an A/B card is not expanded by this framework. Since B4 it is laid out on its first start by its own unit, `rasqberry-ab-layout.service` (`rq_expand_ab.sh firstboot`): two systems on a 64GB+ card, one system using the whole card on a smaller one, opt-out file `no-auto-expand` on the CONFIG partition. It is a separate unit, not a task here, because it must run after the fstab mounts (it unmounts the placeholder `/data` and mounts the new one) and before anything reads `/data`; this runner starts before the mounts are done. See [08-ab-boot-support](../08-ab-boot-support/README.md) and [docs/ab-boot.md](../../docs/ab-boot.md).

## What This Stage Does

This stage creates a flexible, modular firstboot framework that executes tasks sequentially on first boot. Tasks are self-contained scripts that run once and mark themselves as completed.

The stage script itself only creates `/usr/local/lib/rasqberry-firstboot.d/` and `/var/lib/rasqberry-firstboot/`. The components below live in `RQB2-system/` (at their install paths) and are installed, and the service enabled via `RQB2-system/enabled-units.txt`, by [01-deploy-files](../01-deploy-files/README.md) (#294).

### Components Installed

#### 1. Firstboot Framework

**Main Runner** (`/usr/local/bin/rasqberry-firstboot.sh`):
- Discovers and executes tasks from `/usr/local/lib/rasqberry-firstboot.d/`
- Runs tasks in alphanumeric order (01-, 02-, etc.)
- Tracks completion with marker files in `/var/lib/rasqberry-firstboot/`
- Supports reboot requests (exit code 99)
- Skips already-completed tasks
- Logs to systemd journal

#### 2. Filesystem Expansion Task

**Task** (`/usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh`):

Automatically expands the root filesystem to fill the entire SD card on first boot.

**Operations:**
1. Checks for skip marker (`/boot/firmware/skip-expansion`)
2. Detects root partition and device
3. Calculates available space
4. Calls `raspi-config nonint do_expand_rootfs`
5. Requests reboot (exit 99)

**Skip Mechanism:**
- Create `/boot/firmware/skip-expansion` file to disable
- Useful for custom partition setups
- File can be created from Mac/Windows on boot partition

#### 3. VNC Enablement

**Desktop Login Script** (`/usr/local/bin/rasqberry-enable-vnc.sh`):
- Runs at the first desktop login only: it writes `/var/lib/rasqberry/vnc-auto-enabled`
  once VNC is on, and does nothing after that (Jan, Q17; R-014)
- Uses `raspi-config nonint do_vnc 0` to enable VNC (wayvnc), with retries (#288)

**Autostart Entry** (`/etc/xdg/autostart/rasqberry-enable-vnc.desktop`):
- Launches VNC enablement script on graphical login
- VNC switched off later (raspi-config, or the RasQberry menu's Remote Access & Security) stays off
- Non-intrusive (runs silently in background)

#### 4. Systemd Service

**Service File** (`/etc/systemd/system/rasqberry-firstboot.service`):
- Type: oneshot
- Runs very early: After systemd-remount-fs.service, boot-firmware.mount
- Before: rc-local.service, systemd-user-sessions.service
- Logs to journal+console for visibility
- Enabled to run at sysinit.target (listed in `RQB2-system/enabled-units.txt`)

#### 5. Raspberry Pi Imager's OS customisation

Imager (`init_format` `systemd`) writes `firstrun.sh` - Wi-Fi, keyboard and time
zone, SSH key, password, hostname - into the FIRST FAT partition and appends
`systemd.run=/boot/firstrun.sh ... systemd.unit=kernel-command-line.target` to its
`cmdline.txt`. Raspberry Pi OS bookworm makes that path work in its initramfs
(`imager_fixup`); RasQberry images have no initramfs, and on the A/B image the
first FAT partition is CONFIG, which the Pi does not boot from.

**Service** `rasqberry-imager-firstrun.service` (early, before `sysinit.target`, only
when a `firstrun.sh` is on `/boot/firmware` or `/boot/config`) runs
`/usr/bin/rq_imager_firstrun.sh boot`:
- A/B: moves `CONFIG/firstrun.sh` to the slot's boot partition, adds Imager's
  Wi-Fi country and the one-time `systemd.run` entry to its `cmdline.txt`, and restarts.
  First start of a newly written card only: once the card has run (`target-slot`,
  `slot-confirmed` or `current-slot` on CONFIG), a leftover `firstrun.sh` is moved to
  `/var/lib/rasqberry/imager-ignored/` (root only) and not applied. A restart during a
  tryboot trial uses `0 tryboot`, never a plain restart (that would end the trial).
- Both: points `firstrun.sh` at `/boot/firmware`, and gives the start that runs it a
  self-removing `/boot/firstrun.sh`. `kernel-command-line.service` runs it once; it
  removes itself and its `cmdline.txt` entries and restarts the Pi.
- The user stays `rasqberry`: Imager's call to `userconf` goes to
  `/usr/bin/rq_imager_userconf.sh`, which sets the password for `rasqberry` instead of
  renaming the user (Imager renames to `pi` when it has an SSH key but no user name),
  logs a different requested name (`/var/lib/rasqberry/imager-user-requested`,
  `/var/log/rasqberry-imager.log`) and keeps the desktop autologin.

The first-boot runner skips its tasks in that start (`systemd.run=` on the kernel
command line): the root expansion's restart would cut `firstrun.sh` off.

## Files Installed

```
/usr/local/bin/rasqberry-firstboot.sh                      # Main runner
/usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh   # Expansion task
/usr/local/bin/rasqberry-enable-vnc.sh                      # VNC enablement
/etc/xdg/autostart/rasqberry-enable-vnc.desktop             # VNC autostart
/etc/systemd/system/rasqberry-firstboot.service             # Systemd service
/etc/systemd/system/rasqberry-imager-firstrun.service       # Imager customisation
/usr/bin/rq_imager_firstrun.sh, rq_imager_userconf.sh       # (from RQB2-bin)
/var/lib/rasqberry-firstboot/                               # Completion markers
```

## Configuration Variables

No configuration variables required. This stage is self-contained.

## Scripts

- `00-run-chroot.sh`: Creates the task and marker directories; the components and the service come from `RQB2-system/` via [01-deploy-files](../01-deploy-files/README.md)

## Task Exit Codes

Firstboot tasks can use special exit codes:

- **Exit 0**: Task completed successfully
- **Exit 99**: Task completed, reboot required
- **Exit non-zero**: Task failed (framework stops, service fails)

## Execution Flow

### First Boot Sequence

1. **Systemd starts rasqberry-firstboot.service**
2. **Runner discovers tasks** in `/usr/local/lib/rasqberry-firstboot.d/`
3. **Task 01-expand-filesystem** executes:
   - Checks for skip marker
   - Expands root filesystem
   - Marks complete: `/var/lib/rasqberry-firstboot/01-expand-filesystem.sh.done`
   - Requests reboot (exit 99)
4. **Runner triggers reboot**

### Second Boot

1. **Runner checks Task 01**: Already complete (marker exists), skips
2. **No more tasks**, firstboot complete

**Note:** On A/B images Task 01 stands down (`skip-expansion` marker); the card is
laid out by `rasqberry-ab-layout.service` instead (see the note at the top).

### First Desktop Login

1. **Desktop autostart triggers rasqberry-enable-vnc**
2. **VNC enabled via raspi-config**
3. **Marker written**: later logins leave VNC as the user set it

## Benefits

- **Modular Design**: Easy to add new firstboot tasks
- **Self-Tracking**: Completed tasks never re-run
- **Reboot Support**: Tasks can request reboot when needed
- **User-Controllable**: Skip expansion with boot partition marker
- **Robust**: Service logs to journal for troubleshooting

## Special Considerations

### Standard vs A/B Images

- **Standard Image**: Task 01 runs (filesystem expansion to fill SD card)
- **A/B Image**: Task 01 skipped (`skip-expansion` on BOOT-A/BOOT-B); the card is
  laid out on its first start by `rasqberry-ab-layout.service` (two systems on
  64GB+ cards, one system on smaller ones)

### Skip Expansion

Users can disable expansion by creating file on boot partition:

```bash
# From Mac/Windows/Linux, create this file on boot partition:
touch /Volumes/bootfs/skip-expansion     # macOS
touch /media/$USER/bootfs/skip-expansion # Linux
# (Create empty file "skip-expansion" on bootfs drive in Windows)
```

**Use case**: Pre-configured images for specific SD card sizes

### VNC Auto-Enablement

VNC is switched on **once**, at the first desktop login:
- Switched off later, it stays off; an A/B update carries the choice over (`rq_carry_over.sh`)
- To have it switched on again: `sudo rm /var/lib/rasqberry/vnc-auto-enabled`
- Non-intrusive (no visible dialogs)

## Execution Context

- **Execution**: Inside chroot environment (creates the task and marker directories)
- **Service Runs**: At first boot on actual Raspberry Pi
- **User**: root (service), $FIRST_USER_NAME (VNC script via autostart)
- **Order**: 00-prefix; the framework files themselves are installed by 01-deploy-files

## Troubleshooting

**Issue**: Filesystem not expanded on first boot
- **Cause**: Service failed or skip marker present
- **Check**: `systemctl status rasqberry-firstboot.service`
- **Logs**: `journalctl -u rasqberry-firstboot.service`
- **Marker**: Check if `/boot/firmware/skip-expansion` exists

**Issue**: A/B card still at 10GB / Slot B a 16MB placeholder
- **Cause**: `no-auto-expand` on the CONFIG partition, or a card written from an image before B4
- **Check**: `sudo rq_expand_ab.sh status`, `journalctl -u rasqberry-ab-layout`, `/var/log/rasqberry-expand.log`
- **Solution**: `sudo raspi-config` -> 0 RasQberry -> Software & Image Updates

**Issue**: VNC not enabled after first login
- **Cause**: Autostart script failed or VNC service issue
- **Check**: `systemctl status wayvnc.service`, `journalctl -t rasqberry-enable-vnc`
- **Verify**: `/usr/local/bin/rasqberry-enable-vnc.sh` exists and is executable
- **Test**: Run manually: `sudo raspi-config nonint do_vnc 0`

**Issue**: Task runs every boot instead of once
- **Cause**: Completion marker not created
- **Check**: `ls -la /var/lib/rasqberry-firstboot/`
- **Fix**: Verify task script creates marker (framework should do this)

**Issue**: Reboot loop
- **Cause**: Task requests reboot (exit 99) but fails to create marker
- **Fix**: Boot to recovery, create marker manually, or debug task script

## Related Stages

- Works with [08-ab-boot-support](../08-ab-boot-support/) for A/B boot setup

## Adding Custom Firstboot Tasks

To add a new firstboot task:

1. Add the script to `RQB2-system/usr/local/lib/rasqberry-firstboot.d/` in the repository (installed to `/usr/local/lib/rasqberry-firstboot.d/`)
2. Name with numeric prefix for ordering: `03-my-task.sh`
3. Make executable: `chmod +x` (the installer keeps the file mode)
4. Implement task logic
5. Exit 0 (success), 99 (reboot needed), or non-zero (failure)
6. Framework automatically discovers and runs it

Example task:
```bash
#!/bin/bash
# 03-my-custom-task.sh
echo "Running custom firstboot task..."
# Do something...
exit 0  # Success, no reboot needed
```