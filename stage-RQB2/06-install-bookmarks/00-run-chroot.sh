#!/bin/bash -e

echo "Installing desktop bookmarks"

# Source the configuration file
if [ -f "/tmp/stage-config" ]; then
    . /tmp/stage-config
    rm -f /tmp/stage-config
    
    # Map the RQB_ prefixed variables to local names
    REPO="${RQB_REPO}"
    GIT_USER="${RQB_GIT_USER}"
    GIT_BRANCH="${RQB_GIT_BRANCH}"
    GIT_REPO="${RQB_GIT_REPO}"
    # Use FIRST_USER_NAME from pi-gen config, with fallback to rasqberry
    FIRST_USER_NAME="${FIRST_USER_NAME:-rasqberry}"
    
    echo "Configuration loaded successfully"
else
    echo "ERROR: config file not found"
    exit 1
fi

export CLONE_DIR="/tmp/${REPO}"

# Clone the Git repository for bookmark installation
if [ ! -d "${CLONE_DIR}" ]; then
    echo "Cloning repository ${GIT_REPO} (branch: ${GIT_BRANCH}) to ${CLONE_DIR}"
    git clone --branch ${GIT_BRANCH} ${GIT_REPO} ${CLONE_DIR}
else
    echo "Repository already exists at ${CLONE_DIR}"
fi

echo "Installing desktop bookmarks for user: ${FIRST_USER_NAME}"

# Create icon directory
mkdir -p /usr/share/icons/rasqberry

# Copy all icons from desktop-icons directory
if [ -d "${CLONE_DIR}/desktop-icons" ]; then
    for icon_file in "${CLONE_DIR}/desktop-icons"/*.png; do
        if [ -f "$icon_file" ]; then
            cp "$icon_file" /usr/share/icons/rasqberry/
            chmod 644 "/usr/share/icons/rasqberry/$(basename "$icon_file")"
            echo "Installed icon: $(basename "$icon_file")"
        fi
    done
else
    echo "WARNING: Desktop icons directory not found"
fi

# Install desktop files to system applications menu
mkdir -p /usr/share/applications

# Install launcher scripts to /usr/bin
mkdir -p /usr/bin
if [ -d "${CLONE_DIR}/RQB2-bin" ]; then
    for launcher_script in "${CLONE_DIR}/RQB2-bin"/*.sh; do
        if [ -f "$launcher_script" ] && [[ "$(basename "$launcher_script")" =~ ^rq_.*\.sh$ ]]; then
            cp "$launcher_script" /usr/bin/
            chmod 755 "/usr/bin/$(basename "$launcher_script")"
            echo "Installed launcher: $(basename "$launcher_script")"
        fi
    done
else
    echo "WARNING: RQB2-bin directory not found"
fi

# Install custom category definition
mkdir -p /usr/share/desktop-directories
if [ -d "${CLONE_DIR}/RQB2-config/desktop-categories" ]; then
    for category_file in "${CLONE_DIR}/RQB2-config/desktop-categories"/*.directory; do
        if [ -f "$category_file" ]; then
            cp "$category_file" /usr/share/desktop-directories/
            chmod 644 "/usr/share/desktop-directories/$(basename "$category_file")"
            echo "Installed category: $(basename "$category_file")"
        fi
    done
else
    echo "WARNING: Desktop categories directory not found"
fi

# Copy desktop bookmark files
if [ -d "${CLONE_DIR}/RQB2-config/desktop-bookmarks" ]; then
    for desktop_file in "${CLONE_DIR}/RQB2-config/desktop-bookmarks"/*.desktop; do
        if [ -f "$desktop_file" ]; then
            cp "$desktop_file" /usr/share/applications/
            chmod 755 "/usr/share/applications/$(basename "$desktop_file")"
            echo "Installed: $(basename "$desktop_file")"
        fi
    done
else
    echo "WARNING: Desktop bookmarks directory not found"
fi

# Create shell script launchers in /etc/skel for new users
echo "Creating desktop launchers for new users..."
mkdir -p /etc/skel/Desktop

# Create launchers in skel
for launcher in "IBM Quantum Composer:composer" \
                "Grok Bloch Sphere:grok-bloch" \
                "Grok Bloch Web:grok-bloch-web" \
                "Quantum Fractals:quantum-fractals" \
                "Quantum Lights Out:quantum-lights-out" \
                "Quantum Raspberry Tie:quantum-raspberry-tie" \
                "LED IBM Demo:led-ibm-demo" \
                "Clear All LEDs:clear-leds"; do
    IFS=':' read -r name desktop <<< "$launcher"
    cat > "/etc/skel/Desktop/$name" << EOF
#!/bin/bash
gtk-launch $desktop.desktop
EOF
    chmod +x "/etc/skel/Desktop/$name"
done

# Install to current user desktop using shell script launchers
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    USER_DESKTOP="/home/${FIRST_USER_NAME}/Desktop"
    mkdir -p "$USER_DESKTOP"
    
    # Create shell script launchers instead of copying desktop files
    echo "Creating desktop launchers..."
    
    # IBM Quantum Composer
    cat > "$USER_DESKTOP/IBM Quantum Composer" << 'EOF'
#!/bin/bash
gtk-launch composer.desktop
EOF
    chmod +x "$USER_DESKTOP/IBM Quantum Composer"
    
    # Grok Bloch local
    cat > "$USER_DESKTOP/Grok Bloch Sphere" << 'EOF'
#!/bin/bash
gtk-launch grok-bloch.desktop
EOF
    chmod +x "$USER_DESKTOP/Grok Bloch Sphere"
    
    # Grok Bloch web
    cat > "$USER_DESKTOP/Grok Bloch Web" << 'EOF'
#!/bin/bash
gtk-launch grok-bloch-web.desktop
EOF
    chmod +x "$USER_DESKTOP/Grok Bloch Web"
    
    # Quantum Fractals
    cat > "$USER_DESKTOP/Quantum Fractals" << 'EOF'
#!/bin/bash
gtk-launch quantum-fractals.desktop
EOF
    chmod +x "$USER_DESKTOP/Quantum Fractals"
    
    # Quantum Lights Out
    cat > "$USER_DESKTOP/Quantum Lights Out" << 'EOF'
#!/bin/bash
gtk-launch quantum-lights-out.desktop
EOF
    chmod +x "$USER_DESKTOP/Quantum Lights Out"
    
    # Quantum Raspberry Tie
    cat > "$USER_DESKTOP/Quantum Raspberry Tie" << 'EOF'
#!/bin/bash
gtk-launch quantum-raspberry-tie.desktop
EOF
    chmod +x "$USER_DESKTOP/Quantum Raspberry Tie"
    
    # LED IBM Demo
    cat > "$USER_DESKTOP/LED IBM Demo" << 'EOF'
#!/bin/bash
gtk-launch led-ibm-demo.desktop
EOF
    chmod +x "$USER_DESKTOP/LED IBM Demo"
    
    # Clear All LEDs
    cat > "$USER_DESKTOP/Clear All LEDs" << 'EOF'
#!/bin/bash
gtk-launch clear-leds.desktop
EOF
    chmod +x "$USER_DESKTOP/Clear All LEDs"
    
    # Set ownership for all launchers
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP"
    
    # Configure PCManFM for wallpaper and desktop appearance
    USER_CONFIG_DIR="/home/${FIRST_USER_NAME}/.config/pcmanfm/LXDE-pi"
    mkdir -p "$USER_CONFIG_DIR"
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "/home/${FIRST_USER_NAME}/.config"
    
    # Create desktop configuration (wallpaper and appearance only)
    cat > "$USER_CONFIG_DIR/desktop-items-0.conf" << 'EOF'
[*]
wallpaper_mode=fit
wallpaper_common=1
wallpaper=/usr/share/rpd-wallpaper/RasQberry 2 Wallpaper 4K.png
desktop_bg=#FFFFFF
desktop_fg=#000000
desktop_shadow=#FFFFFF
desktop_font=PibotoLt 12
show_wm_menu=0
sort=mtime;ascending;
show_documents=0
show_trash=1
show_mounts=0
EOF
    
    chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_CONFIG_DIR/desktop-items-0.conf"
fi

# Create custom menu configuration for LXDE to recognize RasQberry category
echo "Creating LXDE menu configuration for RasQberry category..."
mkdir -p /etc/xdg/menus/applications-merged
cat > /etc/xdg/menus/applications-merged/rasqberry.menu << 'EOF'
<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
 "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">
<Menu>
  <Name>Applications</Name>
  <Menu>
    <Name>RasQberry</Name>
    <Directory>rasqberry.directory</Directory>
    <Include>
      <Category>RasQberry</Category>
    </Include>
  </Menu>
</Menu>
EOF

# Update desktop database to recognize custom categories
echo "Updating desktop database..."
update-desktop-database /usr/share/applications || echo "Warning: Failed to update desktop database"

# Update icon cache for custom icons
echo "Updating icon cache..."
gtk-update-icon-cache -f -t /usr/share/icons || echo "Warning: Failed to update icon cache"

# Update menu cache for LXDE
echo "Updating menu cache..."
lxpanelctl reload || echo "Warning: Failed to reload lxpanel"

# Clean up cloned repository to save space
if [ -d "${CLONE_DIR}" ]; then
    echo "Cleaning up cloned repository..."
    rm -rf "${CLONE_DIR}"
fi

echo "Desktop bookmarks installation completed"