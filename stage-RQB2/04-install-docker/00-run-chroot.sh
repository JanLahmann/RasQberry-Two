#!/bin/bash -e

echo "Starting Docker Installation (memory-optimized)"

# Clean apt cache first
apt-get clean
rm -rf /var/lib/apt/lists/*

# Configure apt for low memory usage
cat > /etc/apt/apt.conf.d/99-low-memory <<EOF
APT::Cache-Start "50000000";
APT::Cache-Grow "2000000";
APT::Cache-Limit "100000000";
Acquire::http::Pipeline-Depth "0";
Acquire::http::No-Cache "true";
Acquire::BrokenProxy "true";
EOF

# Update package lists with minimal memory
apt-get update -o Acquire::GzipIndexes=false

# Install prerequisites
apt-get install -y --no-install-recommends ca-certificates curl

# Setup Docker repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Clear cache before Docker repo update
apt-get clean
sync

# Update with Docker repo - this is where it usually fails
echo "Updating package lists with Docker repository..."
apt-get update -o Acquire::GzipIndexes=false -o Acquire::Languages=none

# Install Docker components separately to reduce memory usage
echo "Installing Docker components..."
apt-get install -y --no-install-recommends docker-ce-cli
apt-get install -y --no-install-recommends containerd.io
apt-get install -y --no-install-recommends docker-ce

# Optional components (can be commented out to save memory)
# apt-get install -y --no-install-recommends docker-buildx-plugin
# apt-get install -y --no-install-recommends docker-compose-plugin

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -f /etc/apt/apt.conf.d/99-low-memory

echo "Docker Installation Complete"