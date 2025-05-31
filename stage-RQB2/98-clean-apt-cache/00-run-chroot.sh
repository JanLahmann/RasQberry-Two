#!/bin/bash -e

echo "=== Cleaning APT cache and settings before export ==="
echo "Package cache size before cleaning: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"

# 1. Remove the keep-downloaded-packages setting if it exists
if [ -f /etc/apt/apt.conf.d/01cache ]; then
    echo "Removing keep-downloaded-packages setting..."
    rm -f /etc/apt/apt.conf.d/01cache
fi

# 2. Clean all downloaded packages to free disk and memory
echo "Cleaning downloaded packages..."
apt-get clean
echo "Package cache size after cleaning: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"


echo "=== APT cache and settings cleaned ==="