# Stage: 01-deploy-files

## Purpose

Deploy RasQberry configuration files, scripts, and utilities from the repository to their system locations in the image. This stage is the main deployment mechanism for all RasQberry-specific files.

## What This Stage Does

This stage clones the RasQberry-Two repository and deploys files to standard Linux system locations:

### Phase 1: Repository Cloning

1. Clones RasQberry-Two repository to `/tmp/${REPO}`
2. Uses branch specified in `GIT_BRANCH` variable (from stage config)
3. Shallow clone (`--depth 1`) to minimize download size

### Phase 2: File Deployment

**Configuration Files** → `/usr/config/`:
- `rasqberry_environment.env` - Central environment configuration
- `env-config.sh` - Environment loader script
- `setup_qiskit_env.sh` - Qiskit environment setup

**Executable Scripts** → `/usr/bin/`:
- All scripts from `RQB2-bin/` directory
- Includes LED control, demo launchers, installation scripts
- Made executable (`chmod +x`)

**User Configuration** → `/home/${FIRST_USER_NAME}/.local/config/`:
- `RQB2_menu.sh` - Interactive menu system
- Owned by `${FIRST_USER_NAME}:${FIRST_USER_NAME}`
- Also copied to `/etc/skel/.local/config/` for new users

**Artwork** → `/usr/share/rasqberry/artwork/`:
- Logo images, wallpapers, icons
- Preserves directory structure

### Phase 3: Cleanup

- Removes cloned repository from `/tmp/` to save space

## Files Deployed

### `/usr/config/` (System Configuration)
```
rasqberry_environment.env    # Central configuration with all variables
env-config.sh                # Loads environment from multiple locations
setup_qiskit_env.sh          # Sets up Qiskit virtual environment
```

### `/usr/bin/` (Executable Scripts)
```
rq_*.sh                      # RasQberry utility scripts
neopixel_*.py                # LED control scripts
turn_off_LEDs.py             # LED management
rq_install_Qiskit*.sh        # Qiskit installation scripts
rq_set_qiskit_ibm_token.py   # IBM Quantum token management
rq_detect_hardware.sh        # Hardware detection
rq_patch_raspiconfig.sh      # raspi-config integration
rasqberry-load-boot-config.sh # Boot configuration loader
# ... and many more
```

### `~/.local/config/` (User Configuration)
```
RQB2_menu.sh                 # Interactive menu (patched into raspi-config)
```

### `/usr/share/rasqberry/artwork/` (Graphics Assets)
```
Logo-Wallpaper/              # Wallpapers and logo images
desktop-icons/               # Application icons
# ... complete artwork directory structure
```

## Configuration Variables

From stage `config` file:

- `RQB_REPO` - Repository name (e.g., "RasQberry-Two")
- `RQB_PIGEN` - Pi-gen directory path
- `GIT_REPO` - Full repository URL
- `GIT_BRANCH` - Branch to clone (default: "main")
- `FIRST_USER_NAME` - Username for file ownership

### Example Configuration

```bash
RQB_REPO="RasQberry-Two"
GIT_REPO="https://github.com/JanLahmann/RasQberry-Two.git"
GIT_BRANCH="main"
FIRST_USER_NAME="rasqberry"
```

## Scripts

- `00-run.sh`: Copies stage configuration to chroot
- `00-run-chroot.sh`: Clones repository and deploys all files

## Deployment Logic

### Repository Cloning

```bash
if [ ! -d "${CLONE_DIR}" ]; then
    git clone --depth 1 --branch "${GIT_BRANCH:-main}" "${GIT_REPO}" "${CLONE_DIR}"
fi
```

Conditional cloning allows multiple stages to use same clone.

### File Installation Pattern

```bash
# Configuration files
install -v -m 644 "${CLONE_DIR}/RQB2-config/file.env" /usr/config/

# Executable scripts
install -v -m 755 "${CLONE_DIR}/RQB2-bin/script.sh" /usr/bin/

# User files with ownership
install -v -o ${FIRST_USER_NAME} -g ${FIRST_USER_NAME} -m 755 \
  "${CLONE_DIR}/RQB2-config/RQB2_menu.sh" \
  "/home/${FIRST_USER_NAME}/.local/config/"
```

## File Permissions

- **Configuration files**: 644 (rw-r--r--)
- **Executable scripts**: 755 (rwxr-xr-x)
- **User files**: 755, owned by $FIRST_USER_NAME

## Directory Structure Created

```
/usr/
├── bin/                     # RasQberry executables
├── config/                  # System configuration
└── share/
    └── rasqberry/
        └── artwork/         # Graphics assets

/home/${FIRST_USER_NAME}/
└── .local/
    └── config/
        └── RQB2_menu.sh    # User menu

/etc/skel/                   # Template for new users
└── .local/
    └── config/
        └── RQB2_menu.sh
```

## Execution Context

- **Phase 1**: `00-run.sh` runs on host to copy configuration
- **Phase 2**: `00-run-chroot.sh` runs inside chroot as root
- **Order**: 01-prefix (after 00-* base system configuration)
- **Network**: Requires internet access for git clone

## Benefits

- **Centralized Deployment**: Single stage deploys all RasQberry files
- **Version Control**: Files come from specific git branch
- **Reproducible**: Same commit = same files
- **Efficient**: Shallow clone minimizes download
- **Clean**: Temporary clone removed after deployment

## Special Considerations

### Build Cache

The cloned repository in `/tmp/${REPO}` may be reused by multiple stages:
- First stage to need it clones
- Subsequent stages check if already cloned
- Reduces build time and network usage

### Artwork Directory

Complete artwork directory copied to preserve:
- Subdirectory structure
- File relationships
- Future expandability

### User Files

RQB2_menu.sh deployed to both:
- Current user's home (`~/.local/config/`)
- Template for new users (`/etc/skel/.local/config/`)

Ensures all users get RasQberry menu system.

## Troubleshooting

**Issue**: Git clone fails
- **Cause**: Network connectivity or branch doesn't exist
- **Resolution**: Check `GIT_REPO` and `GIT_BRANCH` in config
- **Verify**: Test git clone manually with same URL/branch

**Issue**: Files not found in target locations
- **Cause**: Install commands failed or paths incorrect
- **Resolution**: Check build logs for install command errors
- **Verify**: Examine `/tmp/${REPO}` structure matches expected paths

**Issue**: Permission denied on deployed scripts
- **Cause**: Scripts not made executable
- **Resolution**: Verify `chmod +x` or `install -m 755` used
- **Test**: `ls -la /usr/bin/rq_*` should show execute permission

**Issue**: User files owned by root
- **Cause**: install command missing `-o` and `-g` options
- **Resolution**: Check user file installation uses proper ownership flags
- **Fix**: `chown -R ${FIRST_USER_NAME}:${FIRST_USER_NAME} ~/.local/config/`

## Related Stages

- **Provides files for**: All subsequent stages
- **Used by**: [02-system-integration](../02-system-integration/README.md) - patches deployed by this stage
- **Artwork used by**: [05-wallpapers](../05-wallpapers/README.md), [06-desktop-integration](../06-desktop-integration/README.md)
- **Scripts used by**: All runtime operations and demos

## Deployment Verification

After this stage completes, verify deployments:

```bash
# Configuration files
ls -la /usr/config/
ls -la ~/.local/config/

# Executable scripts
ls -la /usr/bin/rq_*
ls -la /usr/bin/*pixel*

# Artwork
ls -la /usr/share/rasqberry/artwork/
```

All files should exist with correct permissions.

## Future Enhancements

Potential improvements:
- Verify file checksums after deployment
- Add deployment manifest for verification
- Support multiple repository sources
- Implement differential deployment (only changed files)