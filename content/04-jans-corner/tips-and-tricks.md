# Tips and Tricks from Jan

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

`pi-gen-config` holds the rest of the build configuration. Its `RQB_GIT_USER`, `RQB_GIT_BRANCH` and `RQB_REPO` are filled in by the workflow, so there is no need to edit them.

### Iterative Development

A full image build takes a while. For faster iteration when modifying scripts (like `RQB2_menu.sh`) on a running system, use the built-in update script:

```bash
# Update from a specific branch (auto-detects repository)
sudo rq_update_from_branch.sh --branch dev-features05

# Update from a different repository
sudo rq_update_from_branch.sh --repo YourUser/RasQberry-Two --branch development

# Preview changes without applying them
sudo rq_update_from_branch.sh --branch dev --dry-run
```

This updates scripts in `/usr/bin/`, config files in `/usr/config/` and system files (systemd units, autostart entries) from the specified branch. Device settings in `rasqberry_environment.env`, such as the LED layout, are kept: new keys arrive, existing values stay. The same function is in `sudo raspi-config` → **0 RasQberry** → **Software & Image Updates** → **Update from GitHub Branch**. For full system updates (kernel, packages, partition layout), write a new image or use an A/B slot update.

## Build System

Images are built by GitHub Actions (`.github/workflows/RQB-image-v2.yaml`, "Rasqberry Pi Image Release v2"):

- **Automatic:** every push to a `dev*` branch (this includes `development`).
- **Manual:** Actions tab → "Rasqberry Pi Image Release v2" → "Run workflow". Inputs: `version` (required for `main`), `build_scope` (`ab-only`, `standard-image`, `full`, `no-release`), `console_type` and `boot_verbosity`.
- By default every build produces both the standard and the A/B image.
