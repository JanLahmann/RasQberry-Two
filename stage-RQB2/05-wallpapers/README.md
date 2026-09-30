# 05-wallpapers

Installs the RasQberry wallpaper and makes it the system-wide default desktop
background.

## What it does

`00-run.sh` (host):

- Installs `files/RasQberry 2 Wallpaper 4K.png` to
  `${ROOTFS_DIR}/usr/share/rpd-wallpaper/`.
- For `desktop-items-0.conf` and `desktop-items-1.conf` in
  `${ROOTFS_DIR}/etc/xdg/pcmanfm/LXDE-pi/`: updates an existing file (wallpaper
  path, black text, white background and shadow, shadow offset 1) or creates a
  new one with `wallpaper_mode=fit`; the files are owned by root.

## Files

- `files/RasQberry 2 Wallpaper 4K.png`

## Notes

- This sets the global PCManFM defaults only. The first user's and
  `/etc/skel`'s own `desktop-items-0.conf` (wallpaper plus icon positions) are
  written by [06-desktop-integration](../06-desktop-integration/README.md).
