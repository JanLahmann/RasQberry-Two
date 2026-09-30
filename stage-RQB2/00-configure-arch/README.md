# 00-configure-arch

Stops the image from carrying the 32-bit `armhf` foreign architecture, so apt
package lists (and the disk and RAM they use) cover `arm64` only.

## What it does

`00-run-chroot.sh` (chroot):

- Runs `apt-get update` (failure is ignored) and lists any installed `:armhf` packages.
- If `armhf` is a foreign architecture, tries `dpkg --remove-architecture armhf`:
  - on success: deletes `/var/lib/apt/lists/*`, runs `apt-get clean` and `apt-get update`;
  - on failure (armhf packages still installed): writes
    `/etc/apt/preferences.d/99-no-armhf`, which pins `*:armhf` to priority -1.
- Prints the final architecture setup and `apt-cache stats`.

## Notes

- Installed armhf packages are only reported, never removed.
- Nothing happens if `armhf` is not configured as a foreign architecture.
