# Stage: 02-system-integration

## Purpose

Configure system-level integrations that run automatically at boot, including raspi-config patching for the RasQberry menu and hardware detection.

## What This Stage Does

This stage adds two critical cron jobs to root's crontab that run at every system boot:

### 1. RasQberry Menu Integration (`@reboot`)

Patches `/usr/bin/raspi-config` to integrate the RasQberry menu system.

**Cron Entry:**
```bash
@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh
```

**What it does:**
- Sleeps 2 seconds to ensure filesystem is mounted
- Executes `rq_patch_raspiconfig.sh`
- Applies `raspi-config.diff` patch to `/usr/bin/raspi-config`
- Adds "0 RasQberry" menu option to raspi-config
- Sources `~/.local/config/RQB2_menu.sh` for menu implementation

**Result:**
Users can access RasQberry demos and tools through the standard Raspberry Pi configuration utility:
```bash
sudo raspi-config  # Shows "0 RasQberry" option in main menu
```

### 2. Hardware Detection (`@reboot`)

Detects Raspberry Pi hardware model and updates environment configuration.

**Cron Entry:**
```bash
@reboot /usr/bin/rq_detect_hardware.sh
```

**What it does:**
- Runs at every boot (before user login)
- Detects current Raspberry Pi model from `/proc/cpuinfo` or `/proc/device-tree/`
- Determines optimal LED driver (PWM for Pi 4, PIO for Pi 5)
- Updates `/usr/config/rasqberry_environment.env` with `PI_MODEL` variable
- Ensures configuration matches actual hardware

**Why every boot?**
SD cards may be moved between different Pi models. This ensures `PI_MODEL` is always accurate for the current hardware.

## Files Modified

- `/var/spool/cron/crontabs/root` - Root user's crontab
- `/usr/bin/raspi-config` - Patched by rq_patch_raspiconfig.sh (at runtime)
- `/usr/config/rasqberry_environment.env` - Updated by rq_detect_hardware.sh (at runtime)

## Configuration Variables

No configuration variables required. Uses scripts deployed by [01-deploy-files](../01-deploy-files/README.md).

## Scripts

- `00-run-chroot.sh`: Adds cron jobs to root crontab

## Cron Job Management

### Installation Method

Uses atomic cron update pattern:
```bash
bash -c 'CRON="<cron entry>"; \
  crontab -l 2>/dev/null | grep -Fqx "$CRON" || \
  ( crontab -l 2>/dev/null; printf "%s\n" "$CRON" ) | crontab -'
```

**Benefits:**
- Checks if entry already exists (idempotent)
- Preserves existing crontab entries
- Atomic update (all-or-nothing)
- Safe for multiple runs

### Cron Timing: `@reboot`

Both jobs use `@reboot` timing:
- Executes once per boot
- Runs as root before user login
- Perfect for system initialization tasks

## Execution Flow

### Boot Sequence

1. **System boots**
2. **Cron daemon starts**
3. **@reboot jobs triggered**

**Job 1** (rq_patch_raspiconfig.sh):
- Waits 2 seconds for filesystem stability
- Checks if patch already applied
- Applies raspi-config patch if needed
- Logs to syslog

**Job 2** (rq_detect_hardware.sh):
- Reads hardware information
- Determines Pi model
- Updates environment file
- Logs detection results

4. **User login available**

## raspi-config Integration Details

### Why Patching?

RasQberry menu integrates into the standard Raspberry Pi configuration tool rather than being a separate command:

**Advantages:**
- Familiar interface for Pi users
- Single entry point for all configuration
- Leverages raspi-config's existing functionality
- Professional integration feel

### Patch Persistence

- Patch applied at every boot (idempotent)
- Survives raspi-config updates
- Original `/usr/bin/raspi-config` is from Debian package
- Patch is non-destructive (can be reverted)

### Patch Location

The patch file itself is embedded in `rq_patch_raspiconfig.sh`:
- Not a separate `.diff` file
- Applied programmatically using sed or patch command
- Sources user's `~/.local/config/RQB2_menu.sh` for menu logic

## Hardware Detection Details

### Why Detect at Boot?

SD cards are portable between Raspberry Pi models:
- User may image on Pi 4, boot on Pi 5
- Development on one model, deployment on another
- Hardware upgrades without re-imaging

### Detection Method

Checks multiple sources:
1. `/proc/cpuinfo` - CPU information
2. `/proc/device-tree/model` - Device tree model string
3. Raspberry Pi revision codes

### Variables Set

Updates `PI_MODEL` in `/usr/config/rasqberry_environment.env`:
- `PI_MODEL=4` - Raspberry Pi 4 (uses PWM LED driver)
- `PI_MODEL=5` - Raspberry Pi 5 (uses PIO LED driver)
- `PI_MODEL=3` - Raspberry Pi 3 or earlier

## Execution Context

- **Execution**: Inside chroot environment (adds cron jobs)
- **Cron jobs run**: At boot time on actual Raspberry Pi
- **User**: root (cron jobs run as root)
- **Order**: 02-prefix (after file deployment in 01-*)

## Benefits

- **Automatic Integration**: No manual configuration needed
- **Hardware Agnostic**: Adapts to any Pi model automatically
- **Persistent**: Survives system updates
- **Non-Intrusive**: Uses standard Raspberry Pi tools
- **Portable**: SD card works on different Pi models

## Special Considerations

### Root Crontab

Jobs run as root because:
- raspi-config patching requires write access to `/usr/bin/`
- Hardware detection updates system configuration
- Boot-time execution happens before user sessions

### Sleep Delay

2-second sleep in patch script ensures:
- Filesystem fully mounted
- System services initialized
- Reduces race conditions

### Idempotency

Both scripts are idempotent:
- Safe to run multiple times
- Check current state before making changes
- No harmful effects from re-execution

## Troubleshooting

**Issue**: RasQberry menu not appearing in raspi-config
- **Cause**: Patch script failed or didn't run
- **Check**: `sudo crontab -l` should show patch job
- **Logs**: Check syslog: `sudo grep rq_patch /var/log/syslog`
- **Manual**: Run `sudo /usr/bin/rq_patch_raspiconfig.sh`

**Issue**: Wrong PI_MODEL detected
- **Cause**: Detection script failed or hardware unrecognized
- **Check**: `grep PI_MODEL /usr/config/rasqberry_environment.env`
- **Manual**: Run `sudo /usr/bin/rq_detect_hardware.sh`
- **Verify**: `cat /proc/device-tree/model`

**Issue**: Cron jobs not executing at boot
- **Cause**: Cron daemon not running or jobs not installed
- **Check**: `systemctl status cron`
- **Verify**: `sudo crontab -l` shows both @reboot entries
- **Logs**: `sudo grep CRON /var/log/syslog`

**Issue**: raspi-config patch conflicts with system updates
- **Cause**: Debian package update overwrote patched file
- **Resolution**: Reboot to re-apply patch (automatic)
- **Alternative**: Run patch script manually

## Related Stages

- **Requires**: [01-deploy-files](../01-deploy-files/README.md) - deploys scripts used by cron jobs
- **Enables**: [RQB2_menu.sh](../../RQB2-config/RQB2_menu.sh) - menu system accessed via raspi-config
- **Used by**: All interactive RasQberry operations (accessed through raspi-config)

## Security Considerations

- Cron jobs run as root (required for system modification)
- Scripts should be trusted (deployed from official repository)
- Patch modifies system binary (raspi-config)
- No user input processed by boot-time scripts (no injection risk)

## Verification

After system boots, verify integration:

```bash
# Check cron jobs installed
sudo crontab -l | grep -E "rq_patch|rq_detect"

# Check raspi-config patched
sudo raspi-config
# Should show "0 RasQberry" option

# Check hardware detected
grep PI_MODEL /usr/config/rasqberry_environment.env
# Should show correct model number

# Check execution logs
sudo grep -E "rq_patch|rq_detect" /var/log/syslog | tail -20
```

All checks should pass after first boot.