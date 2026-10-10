# 09-touchscreen-support

The on-screen keyboard for touchscreens.

## What it does

- `00-run-chroot.sh` (chroot):
  - trixie (`/etc/xdg/wf-panel-pi/wf-panel-pi.ini` exists): nothing to change.
    Raspberry Pi OS's own keyboard, squeekboard, stays on (autostart
    `/usr/bin/sbtest`: only with a touchscreen). It starts only when a
    touchscreen is present at login: one plugged in later needs a new login
    or a reboot. It opens by itself in text
    fields, the Wi-Fi password popup included, and the panel's keyboard icon
    (`squeek` widget) shows or hides it. raspi-config -> Display Options ->
    On-screen Keyboard switches it. wvkbd and its launcher are not installed:
    tapping the launcher closed the Wi-Fi password popup.
  - bookworm: `apt-get install -y wvkbd`; renames
    `/etc/xdg/autostart/squeekboard.desktop` to `*.disabled`; adds
    `launcher_NNNNNN=virtual-keyboard.desktop` to
    `/etc/skel/.config/wf-panel-pi.ini` and the first user's
    `~/.config/wf-panel-pi.ini` if not present. A missing skel file is created
    with browser, file manager, terminal and keyboard launchers; a missing user
    file is copied from skel.

## Files

From `RQB2-system/`, installed by [01-deploy-files](../01-deploy-files/README.md),
used on bookworm only:

- `/usr/local/bin/toggle-keyboard.sh` - shows or hides wvkbd
- `/usr/share/applications/virtual-keyboard.desktop` - the panel launcher,
  runs `toggle-keyboard.sh` (`TryExec`: hidden where wvkbd is not installed)

## Notes

- A/B updates write the new slot from the image, and each slot has its own
  `/home`, so an updated card has no wvkbd launcher either.
- Touch mode files and state (`/usr/config/touch-mode/`,
  `/var/lib/rasqberry/touch-mode.conf`) and the labwc touch settings are set up
  in [06-desktop-integration](../06-desktop-integration/README.md).
