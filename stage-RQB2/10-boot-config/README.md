# Boot Configuration System

This stage installs the RasQberry boot-time configuration system, which allows users to configure LED hardware settings **before first boot** by editing a simple text file on the boot partition.

## What it does

1. **Installs boot config template**: Copies `rasqberry_boot.env` to `/boot/firmware/` (accessible from any OS)
2. **Installs loader script**: Installs `rasqberry-load-boot-config.sh` to `/usr/local/bin/`
3. **Installs systemd service**: Creates and enables `rasqberry-boot-config.service`
4. **Runs at boot**: Service executes early in boot sequence to merge boot config with global config

## How it works

### Two-Layer Configuration Hierarchy

1. **Boot Partition** (`/boot/firmware/rasqberry_boot.env`) - Highest priority
   - User-editable from Windows/Mac/Linux
   - Only LED configuration variables allowed
   - All entries commented out by default (must be explicitly uncommented)

2. **Global Environment** (`/usr/config/rasqberry_environment.env`) - Default values
   - System configuration file
   - Contains all RasQberry environment variables
   - Updated at boot time with overrides from boot config

### Boot Sequence

```
1. Systemd starts (after local-fs.target)
2. rasqberry-boot-config.service runs
3. rasqberry-load-boot-config.sh executes:
   - Reads /boot/firmware/rasqberry_boot.env
   - Validates LED configuration values
   - Merges with /usr/config/rasqberry_environment.env
   - Applies overrides (boot config wins)
   - Updates global environment file
4. System continues booting with updated configuration
```

## Configurable Variables

### LED Strip Configuration
- `LED_COUNT` - Number of LEDs
- `LED_GPIO_PIN` - GPIO pin (default: 18)
- `LED_PIXEL_ORDER` - RGB/GRB/RGBW/GRBW
- `LED_DEFAULT_BRIGHTNESS` - 0.0-1.0

### LED Matrix Layout
- `LED_MATRIX_LAYOUT` - single/quad
- `LED_MATRIX_WIDTH`, `LED_MATRIX_HEIGHT` - Dimensions
- `LED_MATRIX_Y_FLIP` - Orientation flip
- `LED_MATRIX_PANEL_WIDTH`, `LED_MATRIX_PANEL_HEIGHT` - Quad panel dimensions

### Advanced Settings
- `LED_FREQ_HZ`, `LED_DMA`, `LED_CHANNEL` - Expert settings
- `LED_INVERT` - Signal inversion
- `RASQ_LED_DISPLAY_TIMEOUT` - Demo timeouts

## User Workflow

1. Write RasQberry image to SD card
2. **Before removing** SD card from computer:
   - Mount boot partition (labeled "bootfs")
   - Edit `rasqberry_boot.env`
   - Uncomment and modify desired LED settings
   - Save changes
3. Insert SD card into Raspberry Pi
4. Boot → Configuration automatically applied!

## Files Installed

- `/boot/firmware/rasqberry_boot.env` - Boot configuration template (world-readable)
- `/usr/local/bin/rasqberry-load-boot-config.sh` - Configuration loader script
- `/etc/systemd/system/rasqberry-boot-config.service` - Systemd service unit
- `/usr/config/rasqberry_environment.env.original` - Backup of original config (created on first boot)

## Validation

The loader script validates all configuration values:
- LED_COUNT must be positive integer
- LED_GPIO_PIN must be 0-27
- LED_PIXEL_ORDER must be RGB/GRB/RGBW/GRBW
- LED_DEFAULT_BRIGHTNESS must be 0.0-1.0
- LED_MATRIX_LAYOUT must be single/quad
- Booleans must be true/false

Invalid values are logged and skipped (system uses defaults).

## Troubleshooting

Check service status:
```bash
systemctl status rasqberry-boot-config.service
```

View logs:
```bash
journalctl -u rasqberry-boot-config -b
```

Verify applied configuration:
```bash
cat /usr/config/rasqberry_environment.env | grep LED_
```

Check original defaults:
```bash
cat /usr/config/rasqberry_environment.env.original | grep LED_
```

## Implementation Details

- **Safety**: Invalid config won't break boot - falls back to defaults
- **Idempotent**: Can run multiple times safely
- **Logging**: All actions logged to systemd journal
- **No raspi-config integration**: Users must edit file directly (intentional design choice)

## Related

- Issue #123: Boot-time configuration system enhancement
- `RQB2-config/rasqberry_environment.env` - Global configuration file
- `RQB2-bin/rasqberry-load-boot-config.sh` - Loader script source