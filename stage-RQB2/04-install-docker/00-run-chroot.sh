#!/bin/bash -e

echo "Starting Docker Installation"

sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add the default user to the docker group at build time so docker-based demos
# work out of the box, instead of requiring docker-setup.sh to be run manually
# first just for group membership. Guarded so the build cannot fail if the user
# or group is not present at this stage (docker-ce's install creates the group).
if getent passwd rasqberry >/dev/null 2>&1; then
  getent group docker >/dev/null 2>&1 || sudo groupadd docker
  sudo usermod -aG docker rasqberry
  echo "Added user 'rasqberry' to the docker group"
fi

echo "Ending Docker Installation"
