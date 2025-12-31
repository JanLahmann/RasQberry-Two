# AB Boot Validation Results

## Validation Complete (2025-12-31)

### Test Results
| Test | Result | Notes |
|------|--------|-------|
| Partition expansion (119GB SD) | PASS | 52.9GB/52.9GB/11.8GB for A/B/data |
| Populate Slot B via rq_update_slot.sh | PASS | AB image written successfully |
| Switch A->B with tryboot | PASS | Host key change confirmed different system |
| Health check + auto-confirm on Slot B | PASS | Slot confirmed automatically |
| Switch B->A with tryboot | PASS | Returned to Slot A successfully |
| Health check + auto-confirm on Slot A | PASS | Slot confirmed automatically |

---

## Fixes Applied

### 1. Tryboot Reboot Fix
**File**: `RQB2-bin/rq_update_slot.sh`
Changed `reboot` to `reboot '0 tryboot'` in `reboot_system()` to trigger the tryboot mechanism.

### 2. Terminal-Aware Progress Indicators
**File**: `RQB2-bin/rq_update_slot.sh`
Added `is_terminal()` check to show progress bars for wget, dd, and xz when running interactively.

### 3. --reboot Flag for switch-to
**File**: `RQB2-bin/rq_slot_manager.sh`
Added `--reboot` flag to combine configuration and reboot in one command.

### 4. Non-Empty config.txt
**File**: `stage-RQB2/08-ab-boot-support/files/convert-to-ab-boot-v3.sh`
CONFIG partition config.txt must be non-empty for Pi 5 bootloader to process autoboot.txt.

---

## Important: Use AB Image

When populating Slot B, use the **AB image** (`-ab.img.xz`), not the standard image.

---

## Partition Layout

| Partition | Label | Mount Point | Purpose |
|-----------|-------|-------------|---------|
| p1 | CONFIG | /boot/config | Shared boot config (autoboot.txt) |
| p2 | BOOT-A | /boot/firmware (on A) | Boot files for Slot A |
| p3 | boot-b | /boot/firmware (on B) | Boot files for Slot B |
| p5 | SYSTEM-A | / (on A) | Root filesystem for Slot A |
| p6 | SYSTEM-B | / (on B) | Root filesystem for Slot B |
| p7 | data | /data | Shared user data |

---

## Quick Reference

```bash
# Check status
sudo rq_slot_manager.sh status

# Expand partitions (first time on 64GB+ SD)
sudo raspi-config  # -> RasQberry -> AB_BOOT -> EXPAND

# Populate Slot B with AB image
sudo rq_update_slot.sh <ab-image-url> <release-tag>

# Switch slot (with rollback protection)
sudo rq_slot_manager.sh switch-to B --reboot

# Confirm current slot
sudo rq_slot_manager.sh confirm

# Force rollback
sudo rq_slot_manager.sh rollback && sudo reboot
```
