#!/bin/bash -e

echo "=== Configuring system for arm64 only to reduce disk & RAM requirements ==="

# Check current architectures
echo "Current architectures:"
echo "Primary: $(dpkg --print-architecture)"
echo "Foreign: $(dpkg --print-foreign-architectures || echo 'none')"

# First, update package lists to ensure we have current info
apt-get update || true

# Check if any armhf packages are installed
ARMHF_PACKAGES=$(dpkg -l | grep ":armhf" | awk '{print $2}' || true)
if [ -n "$ARMHF_PACKAGES" ]; then
    echo "WARNING: Found installed armhf packages:"
    echo "$ARMHF_PACKAGES"
    echo "These would need to be removed before removing armhf architecture"
    # For now, we'll leave them and just prevent new armhf packages
else
    echo "No armhf packages installed"
fi

# Try to remove armhf architecture
if dpkg --print-foreign-architectures | grep -q armhf; then
    echo "Attempting to remove armhf architecture..."
    # This might fail if armhf packages are installed
    if dpkg --remove-architecture armhf 2>/dev/null; then
        echo "✓ armhf architecture removed successfully"
        
        # Clean package lists to remove armhf entries
        echo "Cleaning package lists..."
        rm -rf /var/lib/apt/lists/*
        apt-get clean
        
        # Update with only arm64
        echo "Updating package lists (arm64 only)..."
        apt-get update
    else
        echo "⚠ Could not remove armhf architecture (likely due to installed packages)"
        echo "Configuring apt to prefer arm64..."
        
        # Configure apt to ignore armhf packages
        cat > /etc/apt/preferences.d/99-no-armhf <<EOF
# Prevent installation of armhf packages
Package: *:armhf
Pin: release *
Pin-Priority: -1
EOF
        echo "✓ Configured apt to avoid armhf packages"
    fi
else
    echo "armhf is not configured as a foreign architecture"
fi

# Verify final configuration
echo ""
echo "Final architecture configuration:"
echo "Primary: $(dpkg --print-architecture)"
echo "Foreign: $(dpkg --print-foreign-architectures || echo 'none')"

# Show the reduction in package list size
echo ""
echo "Package list sizes:"
apt-cache stats | grep "Total package names\|Total distinct versions"

echo "=== Architecture configuration complete ==="