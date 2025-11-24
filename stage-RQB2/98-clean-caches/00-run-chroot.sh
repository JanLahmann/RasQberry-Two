#!/bin/bash -e

echo "=== Cleaning caches and temporary files before export ==="

# APT cache cleanup
echo "Cleaning APT cache..."
echo "  Package cache size before: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"
if [ -f /etc/apt/apt.conf.d/01cache ]; then
    rm -f /etc/apt/apt.conf.d/01cache
fi
apt-get clean
echo "  Package cache size after: $(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1 || echo '0')"

# Python __pycache__ directories
echo "Cleaning Python __pycache__ directories..."
find /usr -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /home -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Python .pyc compiled files
echo "Cleaning Python .pyc files..."
find /usr -name "*.pyc" -delete 2>/dev/null || true
find /home -name "*.pyc" -delete 2>/dev/null || true

# Temporary directories
echo "Cleaning temporary directories..."
rm -rf /tmp/* /var/tmp/* 2>/dev/null || true

# Bash history
echo "Cleaning bash history..."
rm -f /root/.bash_history 2>/dev/null || true
rm -f /home/*/.bash_history 2>/dev/null || true

echo "=== Cache cleanup completed ==="
