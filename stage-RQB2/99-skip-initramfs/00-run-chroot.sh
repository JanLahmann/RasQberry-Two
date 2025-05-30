#!/bin/bash -e

if [ "${DISABLE_INITRAMFS}" = "1" ]; then
    echo "Disabling initramfs..."
    # Prevent initramfs generation
    touch /etc/initramfs-tools/conf.d/skip-initramfs
    echo "MODULES=none" > /etc/initramfs-tools/conf.d/skip-modules
    
    # Make update-initramfs a no-op
    cat > /usr/local/bin/update-initramfs <<'EOF'
#!/bin/sh
echo "Skipping initramfs update (disabled for faster builds)"
exit 0
EOF
    chmod +x /usr/local/bin/update-initramfs
fi