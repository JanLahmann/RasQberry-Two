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

# Install to new user template (so new users get desktop shortcuts)
mkdir -p /etc/skel/Desktop

# Copy desktop files to skel for new users
for desktop_file in /usr/share/applications/*.desktop; do
    if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|led-ibm-demo|clear-leds)\.desktop$ ]]; then
        cp "$desktop_file" /etc/skel/Desktop/
        chmod 755 "/etc/skel/Desktop/$(basename "$desktop_file")"
        # Mark desktop file as trusted by adding metadata
        gio set "/etc/skel/Desktop/$(basename "$desktop_file")" metadata::trusted true 2>/dev/null || true
        echo "Added to new user template: $(basename "$desktop_file")"
    fi
done

# Install to current user desktop using desktop files
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    USER_DESKTOP="/home/${FIRST_USER_NAME}/Desktop"
    mkdir -p "$USER_DESKTOP"
    
    for desktop_file in /usr/share/applications/*.desktop; do
        if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|led-ibm-demo|clear-leds)\.desktop$ ]]; then
            cp "$desktop_file" "$USER_DESKTOP/"
            chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP/$(basename "$desktop_file")"
            chmod 755 "$USER_DESKTOP/$(basename "$desktop_file")"
            # Mark desktop file as trusted by adding metadata (run as user)
            su - "${FIRST_USER_NAME}" -c "gio set '$USER_DESKTOP/$(basename \"$desktop_file\")' metadata::trusted true" 2>/dev/null || true
            echo "Added to ${FIRST_USER_NAME} desktop: $(basename "$desktop_file")"
        fi
    done
    
    # Set ownership for all desktop files
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP"
    
    # Configure PCManFM for wallpaper and desktop appearance
    USER_CONFIG_DIR="/home/${FIRST_USER_NAME}/.config/pcmanfm/LXDE-pi"
    mkdir -p "$USER_CONFIG_DIR"
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "/home/${FIRST_USER_NAME}/.config"
    
    # Create desktop configuration with wallpaper and icon positions
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
[composer.desktop]
x=10
y=10
trusted=true
[grok-bloch.desktop]
x=120
y=10
trusted=true
[grok-bloch-web.desktop]
x=230
y=10
trusted=true
[quantum-fractals.desktop]
x=340
y=10
trusted=true
[quantum-lights-out.desktop]
x=10
y=120
trusted=true
[quantum-raspberry-tie.desktop]
x=120
y=120
trusted=true
[led-ibm-demo.desktop]
x=230
y=120
trusted=true
[clear-leds.desktop]
x=340
y=120
trusted=true
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