# Boot Configuration System

This stage installs the RasQberry boot-time configuration system, which allows users to configure LED hardware settings **before first boot** by editing a simple text file on the boot partition.

## What it does

1. **Installs boot config template**: Copies `rasqberry_boot.env` to `/boot/firmware/` (accessible from any OS)
2. **Loader script**: `/usr/local/bin/rasqberry-load-boot-config.sh` comes from `RQB2-system/usr/local/bin/`, installed by [01-deploy-files](../01-deploy-files/README.md) (#294)
3. **Systemd service**: `rasqberry-boot-config.service` comes from `RQB2-system/etc/systemd/system/` and is enabled by 01-deploy-files (`RQB2-system/enabled-units.txt`)
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

### LED panel layout
- `LED_LAYOUT` - the one layout setting (a name from `led-layouts.json`:
  `single-24x8`, `quad-4x12`, `triple-8x8`, `single-8x32`); it also sets the
  LED count
- `LED_LAYOUT_VERIFIED` - `true` skips the LED panel check of the setup
  checklist, `skipped` means no panel
- The retired `LED_MATRIX_LAYOUT=single|quad` becomes `LED_LAYOUT=single-24x8`
  or `quad-4x12`; the other `LED_MATRIX_*` keys are ignored (Q22)

### LED wiring and output
- `LED_GPIO_PIN` - GPIO pin (default: 18)
- `LED_PIXEL_ORDER` - RGB/GRB/RGBW/GRBW
- `LED_DEFAULT_BRIGHTNESS` - 0.0-1.0
- `LED_PHYSICAL`, `LED_VIRTUAL`, `LED_WEB` - panel, on-screen view, browser view

### Advanced Settings
- `LED_FREQ_HZ`, `LED_DMA`, `LED_CHANNEL` - Expert settings
- `LED_INVERT` - Signal inversion
- `RASQ_LED_DISPLAY_TIMEOUT` - Demo timeouts

## User Workflow

1. Write RasQberry image to SD card
2. **Before removing** SD card from computer:
   - Mount boot partition (labeled "bootfs"; BOOT-A on the A/B image)
   - Edit `rasqberry_boot.env`
   - Uncomment and modify desired LED settings
   - Save changes
3. Insert SD card into Raspberry Pi
4. Boot → Configuration automatically applied!

## Files Installed

- `/boot/firmware/rasqberry_boot.env` - Boot configuration template (world-readable)
- `/usr/local/bin/rasqberry-load-boot-config.sh` - Configuration loader script (from `RQB2-system/`, via 01-deploy-files)
- `/etc/systemd/system/rasqberry-boot-config.service` - Systemd service unit (from `RQB2-system/`, via 01-deploy-files)
- `/usr/config/rasqberry_environment.env.original` - Backup of original config (created on first boot)

## Validation

The loader script validates all configuration values:
- LED_COUNT must be positive integer
- LED_GPIO_PIN must be 0-27
- LED_PIXEL_ORDER must be RGB/GRB/RGBW/GRBW
- LED_DEFAULT_BRIGHTNESS must be 0.0-1.0
- LED_LAYOUT must be a layout name; LED_LAYOUT_VERIFIED true/false/skipped
- Booleans must be true/false

Values the boot file changed are also saved to `/data` on the A/B image
(`rq_device_settings.sh save`), so the next slot gets them after an update.

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
- `RQB2-system/usr/local/bin/rasqberry-load-boot-config.sh` - Loader script source