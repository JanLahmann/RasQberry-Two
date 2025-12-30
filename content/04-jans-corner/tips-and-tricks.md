# Tips and Tricks from Jan
===

On this page, you will find various tips & tricks from Jan for building the 3D model (e.g. slightly modified STL files, useful tools), installing and using the SW stack and the quantum computing demos, and for modifications of the SW stack and adding new demos to the platform.

## 3D model

I have slightly modified some of the STL files to create a specific variant of the RasQberry Two model or to adjust them a bit to my environment (e.g. the specific 3D printer I use, etc).

*STL files will be added soon*

### Standalone model

The "standalone model" does not use the floor at all. The intention is to use multiple of these standalone models to resemble the modular structure of Quantum System Two, i.e. being able to rearrange the elements and build larger quantum computing structures. For that case, the holes for the screws have been removed. Also, we do not use the double wide version of the RTEs, but only the small RTEs, which then have four magents (two on each side). This allows more flexible configurations.

### LED Filter Screen

The bill-of-material mentions a "welding shield" than can be used in front of the LEDs. Instead, you can 3D print it - with the right material. Many black filaments will not work as they absorb too much light, but a screen printed with 0.6 mm Prusament PLA Galaxy Grey does just fine. STL file is here, and removes the need for a separate order of a welding shield and cutting it.

### Polarisation of the Magnets 

## SW Developer Infos

### Forking the repo 

If you fork the repository, you’ll need to update two files to reflect your GitHub user, branch, and repo name:

- The `on:` trigger in `.github/workflows/RQB-image.yaml` (around line 15).
- The `GIT_USER`, `GIT_BRANCH` (and optionally `REPO`) variables at the top of the pi-gen stage script at `stage-RQB2/01-install-qiskit/01-run-chroot.sh`.

### Iterative Development of RQB2_menu.sh

> **Note**: This is an experimental approach and has not been fully tested. Use with caution.

The complete GitHub Actions workflow to build a new SW image takes about 70 minutes. To speed up iterations when modifying RQB2_menu.sh (and related files) at run-time, the following approach can be used to "dynamically" update the files in RQB2-bin and RQB2-config in a running system:

```bash
# CUSTOMIZE: Set your development repository and branch
export GIT_REPO="https://github.com/JanLahmann/RasQberry-Two.git"  # Change to your fork if needed
export GIT_BRANCH="dev-JRL-features02"  # Change to your development branch

# System configuration (usually no need to change)
export CLONE_DIR="/tmp/RasQberry-Two"
export FIRST_USER_NAME="rasqberry"

# Clone your development branch
git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}

# Copy scripts to user's local bin directory (used when running as normal user)
cp ${CLONE_DIR}/RQB2-bin/* /home/${FIRST_USER_NAME}/.local/bin/

# Copy to system directories (used when running as root, e.g., from raspi-config)
sudo cp ${CLONE_DIR}/RQB2-bin/* /usr/bin
sudo cp -r ${CLONE_DIR}/RQB2-config/* /usr/config

# Clean up
rm -rf ${CLONE_DIR}

# Reload environment to pick up any changes
. /usr/config/rasqberry_env-config.sh
```

**Architecture Notes:**
- Configuration files (environment): Global only (`/usr/config/`)
- Script files: Both user-local (`~/.local/bin/`) and system (`/usr/bin/`) directories
- Scripts use `/usr/config/rasqberry_env-config.sh` for environment loading

## Build System

### Automated Image Building

The RasQberry-Two project uses GitHub Actions to automatically build custom Raspberry Pi OS images. 

#### Build Triggers
- **Automatic builds**: Push to any `dev*` branch
- **Manual builds**: Use the "Actions" tab → "RasQberry Pi Image Release" → "Run workflow"

#### Build Types
- **Development builds** (`dev*` branches): Use caching for faster iteration (~21 min)
- **Beta builds** (`beta` branch): Full clean build (~65 min)
- **Production builds** (`main` branch): Full clean build (~65 min)

#### Caching System
Development builds use a sophisticated caching mechanism:
- Base OS layers (stages 0-4) are cached monthly
- Only the RasQberry-specific stage is rebuilt
- Force refresh: Use `refresh_cache` option in manual workflow

#### Version Management
- **Main branch**: Requires semantic versioning (e.g., `1.2.3`)
- **Beta branch**: (tbd)
- **Dev branches**: Auto-generated as `branch-YYYY-MM-DD-HHMMSS`

## GitHub Actions Workflows

.github/workflows/RQB-image-v2.yaml - RasQberry Image Build Workflow

### Quick Start

#### Manual Build (Recommended for testing)
1. Go to Actions tab
2. Select "RasQberry Pi Image Release"
3. Click "Run workflow"
4. For dev branches:
   - Leave version blank (auto-generated)
   - Check "Force cache refresh" if needed
5. For main and beta branch:
   - Enter semantic version (e.g., "1.2.3")

### Build Performance

| Build Type | Cache | Typical Duration | When to Use |
|------------|-------|------------------|-------------|
| Dev (cached) | ✓ | ~21 minutes | Regular development |
| Dev (fresh) | ✗ | ~65 minutes | Monthly or forced refresh |
| Production | ✗ | ~65 minutes | Official releases |
