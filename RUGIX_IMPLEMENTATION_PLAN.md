# Rugix A/B Boot - Implementation Plan

## Phase 1: MVP with Stock Raspberry Pi OS

**Goal:** Validate the Rugix approach works before integrating with pi-gen.

### Tasks

1. **Create rugix directory structure**
   ```
   mkdir -p rugix/layers
   ```

2. **Create rugix/run-bakery** (make executable)
   ```bash
   #!/bin/bash
   set -euo pipefail
   RUGIX_VERSION="${RUGIX_VERSION:-v0.8}"
   RUGIX_BAKERY_IMAGE="ghcr.io/silitics/rugix-bakery:$RUGIX_VERSION"
   docker run --rm --privileged \
       -v "$(pwd):/project" \
       -v rugix-build-cache:/run/rugix/bakery/cache \
       -v /dev:/dev \
       "$RUGIX_BAKERY_IMAGE" "$@"
   ```

3. **Create rugix/rugix-bakery.toml**
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-project.schema.json

   [systems.test-pi5]
   layer = "test"
   architecture = "arm64"
   target = "rpi-tryboot"
   ```

4. **Create rugix/layers/test-base.toml** (stock RaspOS)
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

   url = "https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz"
   name = "Raspberry Pi OS Lite"
   ```

5. **Create rugix/layers/test.toml**
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

   parent = "test-base"

   recipes = [
       "core/rpi-raspios-setup",
   ]
   ```

6. **Build and test**
   ```bash
   cd rugix
   chmod +x run-bakery
   ./run-bakery bake image test-pi5
   ```

7. **Validate output**
   - Check `rugix/build/test-pi5/system.img` exists
   - Verify partition layout with `fdisk -l system.img`
   - Flash to SD card and boot on Pi 5

### Success Criteria
- [x] Rugix builds without errors
- [x] Output image has correct partition layout
- [x] Image boots successfully on Pi 5

### Status: ✅ COMPLETED (2025-11-22)
- Built test-pi5 image with stock Raspberry Pi OS Lite
- Successfully booted on Pi 5 hardware
- Validated A/B boot partition structure

---

## Phase 2: Import Pi-Gen Image

**Goal:** Replace stock RaspOS with actual RasQberry pi-gen image.

### Tasks

1. **Build pi-gen image** (use existing workflow or manual build)

2. **Upload to GitHub releases**
   - Tag: `base-v1.0.0` or similar
   - Asset: `rasqberry-base.img.xz`

3. **Create rugix/layers/rasqberry-base.toml**
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

   url = "https://github.com/JanLahworker/RasQberry-Two-ABboot10/releases/download/base-v1.0.0/rasqberry-base.img.xz"
   name = "RasQberry Base Image"
   ```

4. **Create rugix/layers/rasqberry.toml**
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

   parent = "rasqberry-base"

   recipes = [
       "core/rpi-raspios-setup",
   ]
   ```

5. **Update rugix/rugix-bakery.toml**
   ```toml
   [systems.rasqberry-pi5]
   layer = "rasqberry"
   architecture = "arm64"
   target = "rpi-tryboot"
   ```

6. **Build and test**
   ```bash
   ./run-bakery bake image rasqberry-pi5
   ```

7. **Validate**
   - Boot image on Pi 5
   - Verify RasQberry software is present and functional

### Success Criteria
- [x] Image builds with pi-gen base
- [ ] RasQberry applications work correctly
- [ ] A/B partition structure intact

### Status: 🔄 IN PROGRESS (2025-11-22)
- Created rasqberry-base.toml pointing to beta-2025-10-29-155618 release
- Created rasqberry.toml layer with rpi-raspios-setup recipe
- Image built successfully (7.9GB)
- **Issue**: Image did not boot correctly on Pi 5
- **Next**: Debug boot issues, possibly need additional recipes or configuration

---

## Phase 3: Add Pi 4 Support

**Goal:** Support both Pi 4 and Pi 5 with appropriate firmware.

### Tasks

1. **Create rugix/layers/rasqberry-pi4.toml**
   ```toml
   #:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

   parent = "rasqberry"

   recipes = [
       "core/rpi-include-firmware",
   ]

   [parameters."core/rpi-include-firmware"]
   model = "pi4"
   ```

2. **Update rugix/rugix-bakery.toml**
   ```toml
   [systems.rasqberry-pi5]
   layer = "rasqberry"
   architecture = "arm64"
   target = "rpi-tryboot"

   [systems.rasqberry-pi4]
   layer = "rasqberry-pi4"
   architecture = "arm64"
   target = "rpi-tryboot"
   ```

3. **Build Pi 4 image**
   ```bash
   ./run-bakery bake image rasqberry-pi4
   ```

4. **Test on Pi 4 hardware**
   - Ensure bootloader is version 2023-05-11+
   - Update if needed: `sudo rpi-eeprom-update -a`

### Success Criteria
- [ ] Pi 4 image builds successfully
- [ ] Image boots on Pi 4 with updated bootloader
- [ ] Both Pi 4 and Pi 5 images work correctly

---

## Phase 4: GitHub Actions Integration

**Goal:** Automate Rugix builds in CI/CD.

### Tasks

1. **Create .github/workflows/build-rugix.yml**
   ```yaml
   name: Build Rugix A/B Image

   on:
     workflow_dispatch:
     push:
       tags:
         - 'v*'

   jobs:
     build:
       runs-on: ubuntu-latest
       strategy:
         fail-fast: false
         matrix:
           system:
             - rasqberry-pi5
             - rasqberry-pi4

       steps:
         - uses: actions/checkout@v4

         - name: Set up QEMU
           run: docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

         - name: Build image
           working-directory: rugix
           run: |
             chmod +x run-bakery
             ./run-bakery bake image ${{ matrix.system }}

         - name: Compress image
           run: xz -T0 -9 rugix/build/${{ matrix.system }}/system.img

         - name: Build update bundle
           working-directory: rugix
           run: ./run-bakery bake bundle ${{ matrix.system }}

         - name: Upload artifacts
           uses: actions/upload-artifact@v4
           with:
             name: ${{ matrix.system }}
             path: |
               rugix/build/${{ matrix.system }}/system.img.xz
               rugix/build/${{ matrix.system }}/system.rugixb
   ```

2. **Test workflow**
   - Run manually via workflow_dispatch
   - Verify artifacts are uploaded

3. **Add release publishing** (optional)
   - Add step to create GitHub release on tags

### Success Criteria
- [ ] Workflow runs successfully
- [ ] Both Pi 4 and Pi 5 images built
- [ ] Artifacts downloadable from Actions

---

## Phase 5: OTA Update Testing

**Goal:** Verify update bundles work with rugix-ctrl.

### Tasks

1. **Build update bundle**
   ```bash
   ./run-bakery bake bundle rasqberry-pi5
   # Output: build/rasqberry-pi5/system.rugixb
   ```

2. **Install rugix-ctrl on device**
   - Follow Rugix documentation for installation

3. **Deploy update**
   ```bash
   # On the device
   rugix-ctrl update install /path/to/system.rugixb
   rugix-ctrl system reboot
   ```

4. **Verify A/B switching**
   - Confirm system boots from new partition
   - Check `rugix-ctrl system info`

5. **Test rollback**
   - Simulate failed update
   - Verify automatic rollback works

### Success Criteria
- [ ] Update bundle installs successfully
- [ ] System switches to new partition on reboot
- [ ] Rollback works when update fails

---

## Notes

- Start with Phase 1 to validate the approach before investing in full integration
- Each phase should be tested on actual hardware before proceeding
- Keep test layers (test-base.toml, test.toml) for debugging