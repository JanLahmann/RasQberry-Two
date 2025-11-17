# Stage: 00-firstboot-expansion

## Purpose

Install the RasQberry modular firstboot service that runs critical initialization tasks on the first boot, including filesystem expansion, A/B partition setup, and VNC enablement.

## What This Stage Does

This stage creates a flexible, modular firstboot framework that executes tasks sequentially on first boot. Tasks are self-contained scripts that run once and mark themselves as completed.

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
- Useful for A/B boot setups with fixed partition sizes
- File can be created from Mac/Windows on boot partition

#### 3. A/B Partition Expansion Task

**Task** (`/usr/local/lib/rasqberry-firstboot.d/02-expand-ab-partitions.sh`):

Expands A/B boot partitions to fill available SD card space (only on A/B images).

**Operations:**
1. Detects A/B layout by checking for `bootfs-cmn` label on p1
2. Verifies boot from Slot A (p5 - rootfs-a)
3. Calculates target sizes (splits remaining space equally)
4. Expands p4 (extended partition) to fill device
5. Expands p5 (rootfs-a) to half of available space
6. Expands p6 (rootfs-b) to fill remaining space
7. Resizes ext4 filesystems on both partitions

**Safety Checks:**
- Only runs on A/B images (detects `bootfs-cmn` label)
- Requires boot from Slot A (p5)
- Skips if already expanded (p5 > 20GB indicates expansion occurred)
- Requires at least 32GB SD card for A/B setup
- Leaves 1GB margin for alignment

**Partition Layout After Expansion:**
- p1: bootfs-common (~512MB, unchanged)
- p2: bootfs-a (~512MB, unchanged)
- p3: bootfs-b (~512MB, unchanged)
- p4: extended partition (fills device)
- p5: rootfs-a (half of remaining space, ~active slot)
- p6: rootfs-b (half of remaining space, ~update slot)

#### 4. VNC Enablement

**Desktop Login Script** (`/usr/local/bin/rasqberry-enable-vnc.sh`):
- Runs on every desktop login (not just first boot)
- Uses `raspi-config nonint do_vnc 0` to enable VNC
- Idempotent (safe to run multiple times)

**Autostart Entry** (`/etc/xdg/autostart/rasqberry-enable-vnc.desktop`):
- Launches VNC enablement script on graphical login
- Ensures VNC is always enabled even if disabled manually
- Non-intrusive (runs silently in background)

#### 5. Systemd Service

**Service File** (`/etc/systemd/system/rasqberry-firstboot.service`):
- Type: oneshot
- Runs very early: After systemd-remount-fs.service, boot-firmware.mount
- Before: rc-local.service, systemd-user-sessions.service
- Logs to journal+console for visibility
- Enabled to run at sysinit.target

## Files Installed

```
/usr/local/bin/rasqberry-firstboot.sh                      # Main runner
/usr/local/lib/rasqberry-firstboot.d/01-expand-filesystem.sh   # Expansion task
/usr/local/lib/rasqberry-firstboot.d/02-expand-ab-partitions.sh # A/B expansion
/usr/local/bin/rasqberry-enable-vnc.sh                      # VNC enablement
/etc/xdg/autostart/rasqberry-enable-vnc.desktop             # VNC autostart
/etc/systemd/system/rasqberry-firstboot.service             # Systemd service
/var/lib/rasqberry-firstboot/                               # Completion markers
```

## Configuration Variables

No configuration variables required. This stage is self-contained.

## Scripts

- `00-run-chroot.sh`: Creates all firstboot components and enables systemd service

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

### Second Boot (Standard Image)

1. **Runner checks Task 01**: Already complete (marker exists), skips
2. **Runner checks Task 02-expand-ab-partitions**: Not A/B image, exits 0
3. **No more tasks**, firstboot complete

### Second Boot (A/B Image)

1. **Runner checks Task 01**: Already complete, skips
2. **Runner executes Task 02-expand-ab-partitions**:
   - Detects A/B layout
   - Expands p5 and p6 to fill SD card
   - Marks complete
3. **Firstboot complete**, A/B system ready

### First Desktop Login

1. **Desktop autostart triggers rasqberry-enable-vnc**
2. **VNC enabled via raspi-config**
3. **VNC continues to run on every login** (ensures always enabled)

## Benefits

- **Modular Design**: Easy to add new firstboot tasks
- **Self-Tracking**: Completed tasks never re-run
- **Reboot Support**: Tasks can request reboot when needed
- **Conditional Execution**: A/B expansion only runs on A/B images
- **User-Controllable**: Skip expansion with boot partition marker
- **Robust**: Service logs to journal for troubleshooting

## Special Considerations

### Standard vs A/B Images

- **Standard Image**: Only Task 01 runs (filesystem expansion)
- **A/B Image**: Both tasks run (standard expansion, then A/B expansion)
- Detection is automatic (checks partition labels)

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

VNC enablement runs on **every desktop login**, not just first boot:
- Ensures VNC stays enabled even if manually disabled
- Uses raspi-config which is idempotent (safe to run repeatedly)
- Non-intrusive (no visible dialogs)

## Execution Context

- **Execution**: Inside chroot environment (creates files for runtime)
- **Service Runs**: At first boot on actual Raspberry Pi
- **User**: root (service), $FIRST_USER_NAME (VNC script via autostart)
- **Order**: Very early (00-prefix) to install framework used by other stages

## Troubleshooting

**Issue**: Filesystem not expanded on first boot
- **Cause**: Service failed or skip marker present
- **Check**: `systemctl status rasqberry-firstboot.service`
- **Logs**: `journalctl -u rasqberry-firstboot.service`
- **Marker**: Check if `/boot/firmware/skip-expansion` exists

**Issue**: A/B partitions not expanded
- **Cause**: Not booted from Slot A, or not detected as A/B image
- **Check**: `lsblk -o name,label` should show `bootfs-cmn` on p1
- **Verify**: `findmnt / -o source` should show p5 (Slot A)
- **Logs**: Check firstboot service logs for Task 02 output

**Issue**: VNC not enabled after first login
- **Cause**: Autostart script failed or VNC service issue
- **Check**: `systemctl status vncserver-x11-serviced.service`
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

- Works with [08-ab-boot-support](../08-ab-boot-support/README.md) for A/B boot setup
- Referenced by [99-enable-expansion](../99-enable-expansion/README.md) verification
- VNC enablement complements [07-enable-vnc](../07-enable-vnc/README.md) (skipped stage)

## Adding Custom Firstboot Tasks

To add a new firstboot task:

1. Create script in `/usr/local/lib/rasqberry-firstboot.d/`
2. Name with numeric prefix for ordering: `03-my-task.sh`
3. Make executable: `chmod +x`
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