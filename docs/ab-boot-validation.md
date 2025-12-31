# AB Boot Validation Results

## Validation Complete (2025-12-31)

### Test Results
| Test | Result | Notes |
|------|--------|-------|
| Partition expansion (119GB SD) | ✅ PASS | 52GB/52GB/11GB for A/B/data |
| Populate Slot B via rq_update_slot.sh | ✅ PASS | 6.6GB image written successfully |
| Switch A→B with tryboot | ✅ PASS | Booted to Slot B successfully |
| Health check + auto-confirm on Slot B | ✅ PASS | Slot confirmed automatically |
| Switch B→A with tryboot | ✅ PASS | Returned to Slot A successfully |
| Health check + auto-confirm on Slot A | ✅ PASS | Slot confirmed automatically |

---

## Improvements Made

### `--reboot` flag for switch-to command
Added `--reboot` flag to `rq_slot_manager.sh switch-to` command to combine configuration and reboot into a single reliable command:
```bash
sudo rq_slot_manager.sh switch-to B --reboot
```
This avoids issues where running `switch-to` and `reboot` as separate SSH commands could fail if the connection is interrupted between commands.

---

## Critical Fix Applied

**Problem**: The CONFIG partition (p1) had an **empty config.txt** file. The Pi 5 bootloader requires a non-empty config.txt to recognize a partition as bootable and process autoboot.txt.

**Solution**: Added content to `/boot/config/config.txt`:
```
# RasQberry CONFIG partition
# This file enables the Pi 5 bootloader to recognize this partition
# and process autoboot.txt for A/B boot partition switching.
```

**Code Fix**: Updated `convert-to-ab-boot-v3.sh` line 219 to create non-empty config.txt.

---

## Partition Layout (7-partition AB boot)

| Partition | Size | Label | Mount Point | Purpose |
|-----------|------|-------|-------------|---------|
| p1 | 512M | CONFIG | /boot/config | Shared boot config (autoboot.txt) |
| p2 | 512M | BOOT-A | /boot/firmware (on A) | Boot files for Slot A |
| p3 | 512M | boot-b | /boot/firmware (on B) | Boot files for Slot B |
| p4 | 1K | - | - | Extended partition container |
| p5 | ~53G | SYSTEM-A | / (on A) | Root filesystem for Slot A |
| p6 | ~53G | SYSTEM-B | / (on B) | Root filesystem for Slot B |
| p7 | ~12G | data | /data | Shared user data |

---

## Key Files

| File | Purpose |
|------|---------|
| `/boot/config/autoboot.txt` | Boot partition switching with tryboot_a_b=1 |
| `/boot/config/config.txt` | **Must be non-empty** for Pi 5 bootloader |
| `/boot/config/slot-confirmed` | Confirmation marker (timestamp) |
| `/usr/bin/rq_slot_manager.sh` | Slot management commands |
| `/usr/bin/rq_update_slot.sh` | Image update to inactive slot |
| `/usr/bin/rq_health_check.py` | Boot validation service |

---

## Partition Expansion (Required for 64GB+ SD Cards)

The AB boot image uses a two-step process:

### Step 1: Build Time (convert-to-ab-boot-v3.sh)
Creates a small ~12GB image with placeholder partitions:
- p5 (SYSTEM-A): 10GB - contains the rootfs
- p6 (SYSTEM-B): 16MB - placeholder
- p7 (DATA): 16MB - placeholder

This keeps the downloadable image small and fast to flash.

### Step 2: Runtime Expansion (raspi-config)
After booting on a 64GB+ SD card, expand partitions via:
```bash
sudo raspi-config → 0 RasQberry → AB_BOOT → EXPAND
```

This runs `do_expand_ab_partitions()` which:
1. Expands p4 (extended) to fill the SD card
2. Resizes p5 (SYSTEM-A) to 45% of available space
3. Recreates p6 (SYSTEM-B) at 45% of available space
4. Recreates p7 (DATA) at 10% of available space

**Note**: Expansion must be done before using `rq_update_slot.sh` to populate Slot B, as the 16MB placeholder cannot hold an 8GB+ rootfs image.

---

## Quick Reference

```bash
# Check current status
sudo rq_slot_manager.sh status

# Switch to other slot (with rollback protection)
sudo rq_slot_manager.sh switch-to B --reboot  # or A
# Or separately:
# sudo rq_slot_manager.sh switch-to B
# sudo reboot '0 tryboot'

# Confirm current slot
sudo rq_slot_manager.sh confirm

# Force rollback
sudo rq_slot_manager.sh rollback
sudo reboot
```
