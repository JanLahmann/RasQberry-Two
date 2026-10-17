# Stage: 02-system-integration

## Purpose

`00-run-chroot.sh` installs wifi-connect for the setup hotspot (section 3)
and adds two `@reboot` jobs to root's crontab, idempotently:

```bash
@reboot sleep 2; /usr/bin/rq_patch_raspiconfig.sh
@reboot /usr/bin/rq_detect_hardware.sh
```

The scripts are deployed by [01-deploy-files](../01-deploy-files/README.md).

## 1. raspi-config patch (`rq_patch_raspiconfig.sh`)

Applies `/usr/config/raspi-config.diff` to `/usr/bin/raspi-config`. The patch
sources `/usr/config/RQB2_menu.sh`, adds the "0 RasQberry" menu item and its
dispatch line, and sends "9 About raspi-config" to `do_rasqberry_about`.

- The patch is tried with `--dry-run` first; nothing changes unless all of it
  applies, and the result is checked for all four markers (R-117).
- The diff is made against Trixie's raspi-config and also fits Bookworm's.
- Besides the reboot job, apt runs the script right after it installs a new
  raspi-config (`/etc/apt/apt.conf.d/99-rasqberry-raspi-config`), so an update
  does not remove the entry until the next reboot.

## 2. Hardware detection (`rq_detect_hardware.sh`)

Reads `/proc/device-tree/model` at every boot (a card may move between Pis) and
sets `PI_MODEL` in `/usr/config/rasqberry_environment.env`:

- `PI_MODEL=Pi4`: Raspberry Pi 4 (LED driver: PWM/DMA, rpi_ws281x)
- `PI_MODEL=Pi5`: Raspberry Pi 5, and any other model (LED driver: PIO on RP1)

## 3. wifi-connect (setup hotspot)

Downloads [balena wifi-connect](https://github.com/balena-os/wifi-connect)
(Apache-2.0), release `v4.11.90`, aarch64 build, and installs it as
`/usr/local/sbin/wifi-connect`. `rq_setup_hotspot.sh` runs it on a new Pi
without a network: the Pi opens a Wi-Fi whose page joins the user's Wi-Fi.
The page is RasQberry's own, `/usr/share/rasqberry/setup-portal` (from
RQB2-system).

Pinned by version and SHA-256 (`WIFI_CONNECT_VERSION`, `WIFI_CONNECT_SHA256`
in the script): a download that does not match stops the build.

- `curl` retries a failed download.
- Its Apache-2.0 licence text ships as `/usr/share/doc/wifi-connect/copyright`
  (from RQB2-system, with the version and checksum).
- A new version: change `WIFI_CONNECT_VERSION` and `WIFI_CONNECT_SHA256`
  together, and the version and checksum lines in that copyright file.

## Troubleshooting

- **No "0 RasQberry" in raspi-config:** run `sudo /usr/bin/rq_patch_raspiconfig.sh`;
  it says why the patch does not fit. If raspi-config is only partly patched and
  has no clean backup: `sudo apt install --reinstall raspi-config`.
- **Wrong `PI_MODEL`:** compare `grep PI_MODEL /usr/config/rasqberry_environment.env`
  with `cat /proc/device-tree/model`; run `sudo /usr/bin/rq_detect_hardware.sh`.
- **Jobs installed?** `sudo crontab -l | grep -E "rq_patch|rq_detect"`
- **wifi-connect there?** `ls -l /usr/local/sbin/wifi-connect`
