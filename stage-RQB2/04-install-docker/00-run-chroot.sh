#!/bin/bash -e

echo "Starting Docker Installation"

# Clean apt cache before starting
apt-get clean
rm -rf /var/lib/apt/lists/*

# Update with memory-efficient options
apt-get update -o Acquire::GzipIndexes=false

# Install prerequisites
apt-get install -y --no-install-recommends ca-certificates curl

# Create keyrings directory
install -m 0755 -d /etc/apt/keyrings

# Download Docker GPG key
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Clean cache again before Docker update
apt-get clean

# Update with reduced memory usage
apt-get update -o Acquire::GzipIndexes=false -o Acquire::CompressionTypes::Order::=gz

# Install Docker with minimal dependencies
apt-get install -y --no-install-recommends \
  docker-ce-cli \
  containerd.io

# Optionally install full Docker later if needed
# apt-get install -y docker-ce docker-buildx-plugin docker-compose-plugin

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*

echo "Docker Installation Complete"