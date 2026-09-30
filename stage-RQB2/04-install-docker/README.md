# 04-install-docker

Installs Docker Engine from Docker's apt repository and enables memory cgroups,
for the Docker-based demos and the doQumentation Workshop Server.

## What it does

- `00-run-chroot.sh` (chroot):
  - installs `ca-certificates` and `curl`, downloads Docker's GPG key to
    `/etc/apt/keyrings/docker.asc` and adds
    `/etc/apt/sources.list.d/docker.list` (download.docker.com, Debian, the
    image's codename);
  - installs `docker-ce`, `docker-ce-cli`, `containerd.io`,
    `docker-buildx-plugin`, `docker-compose-plugin`;
  - if `${FIRST_USER_NAME}` exists, adds it to the `docker` group (creating
    the group if needed).
- `01-run.sh` (host): appends `cgroup_enable=memory cgroup_memory=1` to
  `${ROOTFS_DIR}/boot/firmware/cmdline.txt` if missing. Without them the
  kernel ignores Docker's `--memory` limits.

## Notes

- The cmdline edit runs after [00-enable-serial-console](../00-enable-serial-console/README.md)
  and before the A/B conversion, which copies the extra cmdline parameters into
  both slots (see [08-ab-boot-support](../08-ab-boot-support/README.md)).
