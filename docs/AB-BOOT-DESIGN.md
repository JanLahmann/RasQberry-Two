# A/B Boot Native Pi-gen Build Design

## Overview

This document describes the architecture for building A/B boot images directly in pi-gen, rather than post-processing a standard image.

## Key Principles (from Rugix analysis)

1. **Partition layout baked at build time** - no post-build conversion
2. **Deterministic UUIDs** - set explicitly during mkfs, not discovered after
3. **No firstboot partition resizing** - expansion only for data partition
4. **Proper initramfs handling** - either fully embrace or fully disable

## Partition Layout

```
p1: config        256MB   FAT32   (autoboot.txt, config.txt, bootcode.bin)
p2: boot-a        256MB   FAT32   (kernel, dtb, cmdline.txt for slot A)
p3: boot-b        256MB   FAT32   (kernel, dtb, cmdline.txt for slot B)
p4: extended      (rest)
  p5: system-a    4GB     ext4    (rootfs slot A - fixed size, no expansion)
  p6: system-b    4GB     ext4    (rootfs slot B - fixed size, no expansion)
  p7: data        16MB    ext4    (user data - expands to fill SD)
```

### Why This Layout

- **Smaller boot partitions** (256MB vs 512MB) - matches Rugix, sufficient for kernel+dtb
- **Fixed rootfs sizes** (4GB each) - no expansion needed, fits on 16GB+ cards
- **Separate data partition** - only this expands, isolates user data from system
- **p7 for data** - survives A/B slot switches

## Deterministic UUIDs

### MBR Disk Signature
Set explicitly when creating partition table:
```bash
# Use fixed disk ID for PARTUUID base
DISK_ID="deadbeef"
sfdisk --disk-id "$IMAGE" "0x${DISK_ID}"
```

### Filesystem UUIDs
Set explicitly during mkfs:
```bash
# p1 config - FAT32 volume ID
mkfs.vfat -F 32 -n "config" -i DEADBEE1 "${LOOP}p1"

# p5 system-a - ext4 UUID
mkfs.ext4 -F -L "system-a" -U "deadbeef-0000-0000-0000-000000000005" "${LOOP}p5"

# p6 system-b - ext4 UUID
mkfs.ext4 -F -L "system-b" -U "deadbeef-0000-0000-0000-000000000006" "${LOOP}p6"

# p7 data - ext4 UUID
mkfs.ext4 -F -L "data" -U "deadbeef-0000-0000-0000-000000000007" "${LOOP}p7"
```

### PARTUUID Values
With disk ID `deadbeef`:
- p1: `deadbeef-01`
- p2: `deadbeef-02`
- p3: `deadbeef-03`
- p5: `deadbeef-05`
- p6: `deadbeef-06`
- p7: `deadbeef-07`

## Boot Configuration

### autoboot.txt (on p1)
```
[all]
tryboot_a_b=1
boot_partition=2

[tryboot]
boot_partition=3
```

### cmdline.txt (on p2 - slot A)
```
console=serial0,115200 console=tty1 root=PARTUUID=deadbeef-05 rootfstype=ext4 fsck.repair=yes rootwait
```

### cmdline.txt (on p3 - slot B)
```
console=serial0,115200 console=tty1 root=PARTUUID=deadbeef-06 rootfstype=ext4 fsck.repair=yes rootwait
```

### fstab (on p5 - slot A)
```
proc                    /proc           proc    defaults          0   0
PARTUUID=deadbeef-01    /boot/config    vfat    defaults          0   2
PARTUUID=deadbeef-02    /boot/firmware  vfat    defaults          0   2
PARTUUID=deadbeef-05    /               ext4    defaults,noatime  0   1
PARTUUID=deadbeef-07    /data           ext4    defaults,noatime  0   2
```

### fstab (on p6 - slot B)
```
proc                    /proc           proc    defaults          0   0
PARTUUID=deadbeef-01    /boot/config    vfat    defaults          0   2
PARTUUID=deadbeef-03    /boot/firmware  vfat    defaults          0   2
PARTUUID=deadbeef-06    /               ext4    defaults,noatime  0   1
PARTUUID=deadbeef-07    /data           ext4    defaults,noatime  0   2
```

## Initramfs Strategy

### Option A: Disable Completely (Simpler)
- Remove initramfs from boot partitions
- Remove initramfs lines from config.txt
- Kernel must support direct boot with PARTUUID
- Works because we use PARTUUID (kernel understands this without initramfs)

### Option B: Include Proper Initramfs (More Robust)
- Let pi-gen generate initramfs normally
- Ensure mkinitramfs includes necessary modules
- Initramfs understands PARTUUID and can find root
- More compatible with future kernel updates

**Recommendation**: Start with Option A (simpler), move to Option B if issues arise.

## Implementation Plan

### Phase 1: Create Custom Export Script

Create `stage-RQB2/EXPORT_AB_IMAGE/` with:
- `EXPORT_AB_IMAGE` marker file
- Custom image creation script

This runs instead of standard `export-image` when building A/B variant.

### Phase 2: Modify Workflow

Add workflow parameter to select build type:
- `image_type: standard` - normal 2-partition build
- `image_type: ab-boot` - 6-partition A/B build

### Phase 3: Update Firstboot

Modify `02-expand-ab-partitions.sh`:
- Only expand p7 (data partition)
- Never touch p5/p6 (system partitions)
- Skip entirely if not A/B layout

### Phase 4: Test and Iterate

1. Build A/B image
2. Flash to SD card
3. Test boot on Pi 5
4. Verify slot switching
5. Test OTA updates

## File Structure

```
stage-RQB2/
├── EXPORT_AB_IMAGE/
│   ├── EXPORT_AB_IMAGE           # Marker file
│   └── 00-export-ab-image.sh     # Custom image builder
├── 08-ab-boot-support/
│   ├── 00-run.sh                 # Install systemd services
│   ├── 00-run-chroot.sh          # Install scripts
│   └── files/
│       ├── ab-boot-config/       # Boot config templates
│       │   ├── autoboot.txt
│       │   ├── cmdline-a.txt
│       │   ├── cmdline-b.txt
│       │   ├── fstab-a
│       │   └── fstab-b
│       └── systemd/              # Existing services
└── 00-firstboot-expansion/
    └── files/
        └── 02-expand-ab-partitions.sh  # Modified: only expand p7
```

## Comparison with Current Approach

| Aspect | Current (Post-process) | New (Native Build) |
|--------|------------------------|-------------------|
| Partition creation | After pi-gen, in converter script | During pi-gen export |
| UUIDs | Random, discovered after | Deterministic, set explicitly |
| Firstboot expansion | Expand p5 and p6 | Only expand p7 (data) |
| cmdline.txt | Modified after partitioning | Generated with correct UUIDs |
| Complexity | Two-stage process | Single integrated build |
| Reliability | Fragile (many moving parts) | Robust (single source of truth) |

## Next Steps

1. Create `EXPORT_AB_IMAGE` stage with custom export script
2. Implement deterministic UUID setting
3. Generate boot configs with correct PARTUUIDs
4. Test on Pi 5
5. Update workflow for dual build paths