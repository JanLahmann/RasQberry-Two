# RasQberry A/B Boot Remote Testing System

## Overview

Automated remote testing system for RasQberry images using A/B boot partitions with automatic rollback.

## Strategy

**Slot A: STABLE** - Protected baseline, only updated manually
**Slot B: TESTING** - Receives automatic updates from dev* branch releases

## Architecture

```
┌────────────────────────────────────────────────────────┐
│ GitHub Actions (dev-remote01 branch)                   │
│  - Builds new image                                    │
│  - Creates GitHub release                              │
│  - Uploads image_*.img.xz                              │
└────────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ Test Raspberry Pi 5 (Home network)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Update Poller (runs every 30 seconds)            │  │
│  │  - Checks GitHub for new dev* releases           │  │
│  │  - Downloads image when found                    │  │
│  │  - Writes to Slot B                              │  │
│  │  - Reboots to test                               │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌────────────────┐  ┌────────────────┐                │
│  │ Slot A (p2)    │  │ Slot B (p3)    │                │
│  │ STABLE         │  │ TESTING        │                │
│  │ 12GB           │  │ 12GB           │                │
│  │ Protected      │  │ Auto-updated   │                │
│  └────────────────┘  └────────────────┘                │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Health Check (runs on boot)                      │  │
│  │  ✓ SSH accessible                                │  │
│  │  ✓ Qiskit installed (pip list)                   │  │
│  │  ✓ Virtual environment exists                    │  │
│  │                                                   │  │
│  │  Success → Confirm slot                          │  │
│  │  Failure → Auto-rollback to Slot A               │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

## Workflow

### Automatic Testing (Default)

1. **Developer pushes to dev-remote01**
2. **GitHub Actions builds image**
3. **Creates release** with tag `dev-remote01-2025-10-25-HHMMSS`
4. **Test Pi polls GitHub** (every 30 seconds)
5. **Detects new release**
6. **Downloads to Slot B** (overwrites previous test image)
7. **Reboots into Slot B**
8. **Health check runs** (10 min timeout)
   - If **PASS**: Confirms Slot B, stays running
   - If **FAIL**: Auto-rollback to Slot A on next boot
9. **Repeat** for next release

### Manual Operations

```bash
# View current status
sudo rq_slot_manager.sh status

# Manually switch to Slot B for testing
sudo rq_slot_manager.sh switch-to B
sudo reboot

# Promote tested Slot B to become new Slot A
sudo rq_slot_manager.sh promote

# Manually update Slot A with specific image (requires confirmation)
sudo rq_slot_manager.sh update-stable <url> <tag>

# Force rollback to Slot A
sudo rq_slot_manager.sh rollback
sudo reboot
```

## Files

### Scripts
- `RQB2-bin/rq_health_check.py` - Boot validation (SSH + Qiskit check)
- `RQB2-bin/rq_slot_manager.sh` - Manual slot management
- `RQB2-bin/rq_update_poller.py` - Polls GitHub for new releases
- `RQB2-bin/rq_update_slot.sh` - Downloads and installs images
- `tools/setup-ab-boot.sh` - One-time partition setup

### System Services
- `rasqberry-health-check.service` - Runs on boot
- `rasqberry-update-poller.timer` - Runs every 30 seconds
- `rasqberry-update-poller.service` - Triggered by timer

### Boot Configuration
- `/boot/firmware/autoboot.txt` - Controls tryboot mode
- `/boot/firmware/tryboot.txt` - Defines slot behavior
- `/boot/firmware/current-slot` - Tracks active slot (A or B)
- `/boot/firmware/slot-confirmed` - Prevents rollback when present

## Setup

### Prerequisites
- Raspberry Pi 4 or 5 (tryboot required)
- 32GB+ SD card or NVMe drive
- Working RasQberry installation

### One-Time Setup

1. **Install stable image to SD card** (standard process)

2. **Boot and configure A/B partitions:**
   ```bash
   cd ~/RasQberry-Two
   sudo tools/setup-ab-boot.sh
   ```

3. **Verify setup:**
   ```bash
   sudo rq_slot_manager.sh status
   ```

4. **Services are automatically enabled:**
   - Health check runs on every boot
   - Update poller checks GitHub every 30 seconds

### Testing the System

1. **Make a change to dev-remote01 branch**
2. **Push to GitHub** (triggers build)
3. **Wait for release** (~2-3 hours for full build)
4. **Update poller detects it** (within 30 seconds)
5. **Watch logs:**
   ```bash
   tail -f /var/log/rasqberry-update-poller.log
   tail -f /var/log/rasqberry-health-check.log
   ```

## Safety Features

1. **Protected Slot A** - Cannot be auto-updated
2. **Automatic rollback** - Failed boots return to Slot A
3. **Health validation** - Tests run before confirmation
4. **Manual confirmation** - Required for Slot A updates
5. **No data loss** - Slot A always available

## Troubleshooting

### Update not detected
```bash
# Check poller service
systemctl status rasqberry-update-poller.timer
journalctl -u rasqberry-update-poller.service -f

# Manually check GitHub
python3 /usr/local/bin/rq_update_poller.py
```

### Boot stuck in Slot B
```bash
# System will auto-rollback after 10 min if health check fails
# Or manually force rollback:
sudo rq_slot_manager.sh rollback
sudo reboot
```

### Health check failing
```bash
# Check logs
cat /var/log/rasqberry-health-check.log

# Manually run health check
python3 /usr/local/bin/rq_health_check.py
```

## Configuration

### Change polling interval
Edit `/etc/systemd/system/rasqberry-update-poller.timer`:
```ini
[Timer]
OnUnitActiveSec=30s  # Change this value
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart rasqberry-update-poller.timer
```

### Disable auto-updates
```bash
sudo systemctl stop rasqberry-update-poller.timer
sudo systemctl disable rasqberry-update-poller.timer
```

### Target different branches
Edit `rq_update_poller.py`:
```python
TARGET_BRANCH_PATTERN = "dev"  # Change to "beta", "main", etc.
```

## Future Enhancements

- [ ] Email/Slack notifications on update success/failure
- [ ] Web dashboard showing test status
- [ ] Manifest.json with checksums
- [ ] Delta updates (only changed files)
- [ ] Multiple test Pis reporting to central dashboard