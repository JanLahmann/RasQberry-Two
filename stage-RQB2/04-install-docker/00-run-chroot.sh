#!/bin/bash -e

echo "Starting Docker Installation"

apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update

apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add the default user to the docker group at build time so docker-based demos
# work out of the box, without requiring any manual setup step at runtime just
# for group membership. Guarded so the build cannot fail if the user
# or group is not present at this stage (docker-ce's install creates the group).
if getent passwd "${FIRST_USER_NAME}" >/dev/null 2>&1; then
  getent group docker >/dev/null 2>&1 || groupadd docker
  usermod -aG docker "${FIRST_USER_NAME}"
  echo "Added user '${FIRST_USER_NAME}' to the docker group"
fi

echo "Ending Docker Installation"
