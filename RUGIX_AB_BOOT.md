# Rugix A/B Boot Implementation

## Approach

Use Rugix to create A/B bootable images by importing existing pi-gen images via URL. This avoids reimplementing pi-gen stages as Rugix recipes.

**Workflow:**
```
Pi-gen image → GitHub Releases → Rugix imports via URL → A/B image with tryboot
```

## Partition Layout (rpi-tryboot)

| Partition | Size | Purpose |
|-----------|------|---------|
| config | 256M | Shared configuration |
| boot-a | 128M | Boot partition A |
| boot-b | 128M | Boot partition B |
| system-a | Dynamic | Root filesystem A |
| system-b | Dynamic | Root filesystem B |
| data | Remaining | Persistent data |

## Project Structure

```
rugix/
├── rugix-bakery.toml
├── run-bakery
└── layers/
    ├── rasqberry-base.toml    # Imports pi-gen image
    ├── rasqberry.toml         # Pi 5 (adds boot recipes)
    └── rasqberry-pi4.toml     # Pi 4 (adds firmware)
```

## Configuration Files

### rugix-bakery.toml

```toml
#:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-project.schema.json

[systems.rasqberry-pi5]
layer = "rasqberry"
architecture = "arm64"
target = "rpi-tryboot"

[systems.rasqberry-pi4]
layer = "rasqberry-pi4"
architecture = "arm64"
target = "rpi-tryboot"
```

### layers/rasqberry-base.toml

```toml
#:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

url = "https://github.com/JanLahworker/RasQberry-Two-ABboot10/releases/download/v1.0.0/rasqberry-base.img.xz"
name = "RasQberry Base Image"
```

### layers/rasqberry.toml

```toml
#:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

parent = "rasqberry-base"

recipes = [
    "core/rpi-raspios-setup",
]
```

### layers/rasqberry-pi4.toml

```toml
#:schema https://raw.githubusercontent.com/silitics/rugix/refs/tags/v0.8.0/schemas/rugix-bakery-layer.schema.json

parent = "rasqberry"

recipes = [
    "core/rpi-include-firmware",
]

[parameters."core/rpi-include-firmware"]
model = "pi4"
```

### run-bakery

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

## Build Commands

```bash
cd rugix

# Build image
./run-bakery bake image rasqberry-pi5

# Build update bundle
./run-bakery bake bundle rasqberry-pi5

# Output files
# build/rasqberry-pi5/system.img     - Bootable A/B image
# build/rasqberry-pi5/system.rugixb  - OTA update bundle
```

## Requirements

- Docker with privileged access
- Pi 4: Bootloader version 2023-05-11+ (for tryboot support)
- Pi 5: Works out of box

## References

- [Rugix Documentation](https://oss.silitics.com/rugix/)
- [Rugix Layers](https://oss.silitics.com/rugix/docs/bakery/layers/)
- [Raspberry Pi Target](https://oss.silitics.com/rugix/docs/bakery/devices/raspberry-pi/)
- [thin-edge/tedge-rugix-image](https://github.com/thin-edge/tedge-rugix-image) - Reference implementation