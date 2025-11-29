# Stage: 03-desktop-autologin

## Purpose

Configure Raspberry Pi OS to boot directly to the graphical desktop environment with automatic login, eliminating the need for users to manually log in each time the system starts.

## What This Stage Does

This stage uses the `raspi-config` non-interactive interface to set the boot behavior to "B4" (Desktop Autologin):

```bash
SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_boot_behaviour B4
```

### Boot Behavior Options

Raspberry Pi OS supports several boot behaviors:
- **B1**: Console (text mode, requires login)
- **B2**: Console Autologin (text mode, automatic login)
- **B3**: Desktop (graphical mode, requires login)
- **B4**: Desktop Autologin (graphical mode, automatic login) ← **This stage**

## Files Modified

- `/etc/systemd/system/getty@tty1.service.d/autologin.conf` (or similar)
- Lightdisplayman (LightDM) or LXDM configuration files
- System boot configuration managed by raspi-config

## Configuration Variables

- `FIRST_USER_NAME`: Username to auto-login (from stage config, typically "rasqberry")

## Scripts

- `00-run.sh`: Uses pi-gen's `on_chroot` helper to execute command in chroot environment

## Benefits

- **User-Friendly**: System ready to use immediately after boot
- **Demo-Ready**: Perfect for educational/demonstration systems
- **Kiosk Mode**: Suitable for dedicated quantum computing stations
- **No Credentials Needed**: Users don't need to know username/password

## Special Considerations

### Security Trade-off

Autologin reduces security:
- **Pro**: Convenience, ease of use
- **Con**: Physical access = full system access
- **Use Case**: RasQberry is educational, not a security-critical system

### User Context

The `SUDO_USER` environment variable ensures raspi-config knows which user to auto-login:
- Uses `${FIRST_USER_NAME}` from stage configuration
- Typically "rasqberry" user
- Critical for proper desktop session initialization

### Desktop Environment

Requires graphical desktop environment installed:
- Raspberry Pi OS with Desktop (not Lite)
- LXDE desktop environment
- LightDM display manager

## Execution Context

- **Execution**: Inside chroot via `on_chroot` helper
- **User**: Executed as root, configures auto-login for `$FIRST_USER_NAME`
- **Order**: 03-prefix (after system basics, before desktop customization)
- **Dependencies**: Requires desktop environment already installed by base Pi OS

## Troubleshooting

**Issue**: System still prompts for login
- **Cause**: raspi-config command failed or wrong boot behavior set
- **Check**: `sudo raspi-config` → System Options → Boot / Auto Login
- **Manual Fix**: `sudo raspi-config nonint do_boot_behaviour B4`

**Issue**: Desktop starts but with wrong user
- **Cause**: FIRST_USER_NAME not set correctly
- **Check**: `/etc/lightdm/lightdm.conf` or `/etc/systemd/system/getty@tty1.service.d/autologin.conf`
- **Verify**: Should reference correct username

**Issue**: Black screen after boot
- **Cause**: Desktop environment issue, not autologin issue
- **Check**: Try B3 (Desktop with login) to isolate problem
- **Logs**: Check `/var/log/lightdm/lightdm.log`

## Related Stages

- Works with [06-desktop-integration](../06-desktop-integration/README.md) for complete desktop experience
- Enables immediate access to RasQberry menu and demos
- Part of user-friendly quantum computing education platform

## Verification

After boot, verify autologin:

```bash
# System should boot to desktop automatically
# No login prompt should appear

# Check current session user
whoami
# Should show: rasqberry (or configured FIRST_USER_NAME)

# Check boot configuration
sudo raspi-config nonint get_boot_behaviour
# Should output: B4
```

## Alternative Approaches

### Manual Login (B3)

For environments requiring authentication:
```bash
SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_boot_behaviour B3
```

### Console Mode (B1)

For headless or server use:
```bash
SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_boot_behaviour B1
```

## Documentation References

- [Raspberry Pi Documentation - raspi-config](https://www.raspberrypi.com/documentation/computers/configuration.html#raspi-config)
- [raspi-config Source](https://github.com/raspberrypi/documentation/blob/develop/documentation/asciidoc/computers/configuration/raspi-config.adoc)