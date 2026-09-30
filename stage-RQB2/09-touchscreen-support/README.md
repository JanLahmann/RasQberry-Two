# 09-touchscreen-support

Adds the `wvkbd` on-screen keyboard for touchscreens, with a toggle button in
the panel, in place of the default squeekboard.

## What it does

- `00-run-chroot.sh` (chroot):
  - `apt-get install -y wvkbd`;
  - renames `/etc/xdg/autostart/squeekboard.desktop` to `*.disabled`;
  - adds `launcher_NNNNNN=virtual-keyboard.desktop` to
    `/etc/skel/.config/wf-panel-pi.ini` and the first user's
    `~/.config/wf-panel-pi.ini` if not present. A missing skel file is created
    with browser, file manager, terminal and keyboard launchers; a missing user
    file is copied from skel.

## Files

From `RQB2-system/`, installed by [01-deploy-files](../01-deploy-files/README.md):

- `/usr/local/bin/toggle-keyboard.sh`
- `/usr/share/applications/virtual-keyboard.desktop` - the panel launcher,
  runs `toggle-keyboard.sh`

## Notes

- Touch mode files and state (`/usr/config/touch-mode/`,
  `/var/lib/rasqberry/touch-mode.conf`) and the labwc touch settings are set up
  in [06-desktop-integration](../06-desktop-integration/README.md).
