# Tips and Tricks from Jan
===

On this page, you will find various tips & tricks from Jan for building the 3D model (e.g. slightly modified STL files, useful tools), installing and using the SW stack and the quantum computing demos, and for modifications of the SW stack and adding new demos to the platform.

## 3D model

I have slightly modified some of the STL files to create a specific variant of the RasQberry Two model or to adjust them a bit to my environment (e.g. the specific 3D printer I use, etc).

Modified STL files are available in the [3D Model modifications folder](https://github.com/JanLahmann/RasQberry-Two/tree/3D-model/3D%20Model/3D%20Model%20-%20modifications%20-%20Jan).

### Standalone model

The "standalone model" does not use the floor at all. The intention is to use multiple of these standalone models to resemble the modular structure of Quantum System Two, i.e. being able to rearrange the elements and build larger quantum computing structures. For that case, the holes for the screws have been removed. Also, we do not use the double wide version of the RTEs, but only the small RTEs, which then have four magents (two on each side). This allows more flexible configurations.

### LED Filter Screen

The bill-of-material mentions a "welding shield" than can be used in front of the LEDs. Instead, you can 3D print it - with the right material. Many black filaments will not work as they absorb too much light, but a screen printed with 0.6 mm Prusament PLA Galaxy Grey does just fine. The [STL file](https://github.com/JanLahmann/RasQberry-Two/blob/3D-model/3D%20Model/3D%20Model%20-%20modifications%20-%20Jan/October%202025/wall/RQB2-WallPanel-jrl02-2.stl) removes the need for a separate order of a welding shield and cutting it.

## SW Developer Infos

### Forking the Repository

The GitHub Actions workflow automatically detects your repository and username from the GitHub context. In most cases, forking should work without any changes.

If you need to customize the build configuration, edit `pi-gen-config` which contains the `RQB_GIT_USER`, `RQB_GIT_BRANCH`, and `RQB_REPO` variables.

### Iterative Development

The full GitHub Actions workflow takes ~21-65 minutes. For faster iteration when modifying scripts (like `RQB2_menu.sh`) on a running system, use the built-in update script:

```bash
# Update from a specific branch (auto-detects repository)
sudo rq_update_from_branch.sh --branch dev-features05

# Update from a different repository
sudo rq_update_from_branch.sh --repo YourUser/RasQberry-Two --branch main

# Preview changes without applying them
sudo rq_update_from_branch.sh --branch dev --dry-run
```

This updates scripts in `/usr/bin/` and config files in `/usr/config/` from the specified branch. For full system updates (kernel, packages, partition layout), use A/B boot slot updates instead.

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
