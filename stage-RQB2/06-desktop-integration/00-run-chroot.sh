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

# Copy all icons from desktop-icons directory (PNG and SVG)
if [ -d "${CLONE_DIR}/desktop-icons" ]; then
    for icon_file in "${CLONE_DIR}/desktop-icons"/*.png "${CLONE_DIR}/desktop-icons"/*.svg; do
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
    if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|qoffee-maker|quantum-mixer|led-ibm-demo|led-painter|clear-leds|rasq-led|demo-loop|fun-with-quantum|quantum-coin-game|touch-mode)\.desktop$ ]]; then
        cp "$desktop_file" /etc/skel/Desktop/
        chmod 755 "/etc/skel/Desktop/$(basename "$desktop_file")"
        echo "Added to new user template: $(basename "$desktop_file")"
    fi
done

# Install to current user desktop using desktop files
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    USER_DESKTOP="/home/${FIRST_USER_NAME}/Desktop"
    mkdir -p "$USER_DESKTOP"
    
    for desktop_file in /usr/share/applications/*.desktop; do
        if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|grok-bloch-web|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|qoffee-maker|quantum-mixer|led-ibm-demo|led-painter|clear-leds|rasq-led|demo-loop|fun-with-quantum|quantum-coin-game|touch-mode)\.desktop$ ]]; then
            cp "$desktop_file" "$USER_DESKTOP/"
            chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_DESKTOP/$(basename "$desktop_file")"
            chmod 755 "$USER_DESKTOP/$(basename "$desktop_file")"
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
show_trash=0
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
[qoffee-maker.desktop]
x=10
y=230
trusted=true
[quantum-mixer.desktop]
x=120
y=230
trusted=true
[led-ibm-demo.desktop]
x=230
y=120
trusted=true
[clear-leds.desktop]
x=340
y=120
trusted=true
[rasq-led.desktop]
x=230
y=230
trusted=true
[led-painter.desktop]
x=10
y=340
trusted=true
[fun-with-quantum.desktop]
x=120
y=340
trusted=true
[quantum-coin-game.desktop]
x=230
y=340
trusted=true
[demo-loop.desktop]
x=340
y=230
trusted=true
[touch-mode.desktop]
x=340
y=340
trusted=true
EOF

    chown "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_CONFIG_DIR/desktop-items-0.conf"

    # Also copy to /etc/skel so new users get the trusted desktop icons
    SKEL_CONFIG_DIR="/etc/skel/.config/pcmanfm/LXDE-pi"
    mkdir -p "$SKEL_CONFIG_DIR"
    cp "$USER_CONFIG_DIR/desktop-items-0.conf" "$SKEL_CONFIG_DIR/desktop-items-0.conf"
    echo "Desktop configuration copied to /etc/skel for new users"

    # Configure libfm to skip executable file dialog (Bookworm security feature)
    # Setting quick_exec=1 prevents "Execute File" dialog for .desktop files
    LIBFM_CONFIG_DIR="/home/${FIRST_USER_NAME}/.config/libfm"
    mkdir -p "$LIBFM_CONFIG_DIR"
    cat > "$LIBFM_CONFIG_DIR/libfm.conf" << 'EOF'
[config]
single_click=0
use_trash=1
confirm_del=1
terminal=x-terminal-emulator %s
thumbnail_local=1
thumbnail_max=2048
cutdown_menus=1
real_expanders=1
quick_exec=1

[ui]
big_icon_size=48
small_icon_size=24
thumbnail_size=80
pane_icon_size=24
show_thumbnail=1

[places]
places_home=1
places_desktop=0
places_root=1
places_computer=0
places_trash=0
places_applications=0
places_network=0
places_unmounted=1
places_volmounts=1
EOF

    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$LIBFM_CONFIG_DIR"
    echo "libfm configuration created with quick_exec=1"

    # Also create libfm config for new users in /etc/skel
    SKEL_LIBFM_DIR="/etc/skel/.config/libfm"
    mkdir -p "$SKEL_LIBFM_DIR"
    cp "$LIBFM_CONFIG_DIR/libfm.conf" "$SKEL_LIBFM_DIR/libfm.conf"
    echo "libfm configuration copied to /etc/skel for new users"
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

# Install touch mode configuration files
echo "Installing touch mode configuration..."
mkdir -p /usr/config/touch-mode
if [ -d "${CLONE_DIR}/RQB2-config/touch-mode" ]; then
    for touch_file in "${CLONE_DIR}/RQB2-config/touch-mode"/*; do
        if [ -f "$touch_file" ]; then
            cp "$touch_file" /usr/config/touch-mode/
            chmod 644 "/usr/config/touch-mode/$(basename "$touch_file")"
            echo "Installed touch mode file: $(basename "$touch_file")"
        fi
    done
else
    echo "WARNING: Touch mode config directory not found"
fi

# Create state directory for touch mode
mkdir -p /var/lib/rasqberry
echo "TOUCH_MODE=disabled" > /var/lib/rasqberry/touch-mode.conf
chmod 644 /var/lib/rasqberry/touch-mode.conf
echo "Created touch mode state directory"

# Install on-screen keyboard package for touch mode
echo "Installing on-screen keyboard (onboard)..."
apt-get update -qq
apt-get install -y -qq onboard || echo "Warning: Failed to install onboard package"

# Update desktop database to recognize custom categories
echo "Updating desktop database..."
update-desktop-database /usr/share/applications || echo "Warning: Failed to update desktop database"

# Update icon cache for custom icons
echo "Updating icon cache..."
gtk-update-icon-cache -f -t /usr/share/icons || echo "Warning: Failed to update icon cache"

# Customize LXPanel main menu icon (Raspberry Pi icon in top-left corner)
echo "Configuring main panel menu icon..."
PANEL_CONFIG="/etc/xdg/lxpanel/LXDE-pi/panels/panel"
if [ -f "$PANEL_CONFIG" ]; then
    # Backup original panel config
    cp "$PANEL_CONFIG" "${PANEL_CONFIG}.orig"

    # Replace the menu icon in the panel configuration
    # Look for the menu plugin section and change its icon
    # The default uses "raspberrypi-logo" or similar
    sed -i 's|icon=raspberrypi.*|icon=/usr/share/icons/rasqberry/rasqberry-menu-icon.png|g' "$PANEL_CONFIG"
    sed -i 's|icon=/usr/share/pixmaps/raspberrypi.*|icon=/usr/share/icons/rasqberry/rasqberry-menu-icon.png|g' "$PANEL_CONFIG"

    echo "Panel menu icon updated to RasQberry logo"
else
    echo "Warning: Panel config not found at $PANEL_CONFIG"
fi

# Update menu cache for LXDE
echo "Updating menu cache..."
lxpanelctl reload || echo "Warning: Failed to reload lxpanel"

# Create first-login script to configure libfm and GNOME Keyring
# This runs when the user first logs in and has a proper desktop session
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    AUTOSTART_DIR="/home/${FIRST_USER_NAME}/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"

    # Create the first-login setup script
    cat > "/usr/local/bin/trust-rasqberry-desktop-files.sh" << 'EOF'
#!/bin/bash
# Configure RasQberry desktop on first login
# - Configure GNOME Keyring to avoid password prompts
# - Verify libfm quick_exec setting
# This runs once and then removes itself

LOG_FILE="$HOME/.rasqberry-desktop-trust.log"

echo "$(date): Running RasQberry first-login setup..." >> "$LOG_FILE"

# Wait for desktop environment to be ready
sleep 3

# Configure GNOME Keyring with blank password to avoid Chromium password prompts
echo "$(date): Configuring GNOME Keyring..." >> "$LOG_FILE"
if command -v python3 >/dev/null 2>&1; then
    # Create default keyring directory if it doesn't exist
    mkdir -p "$HOME/.local/share/keyrings" 2>> "$LOG_FILE"

    # Create 'Default' keyring with blank password using Python
    # This prevents the "Enter password to unlock keyring" dialog in Chromium
    python3 - 2>> "$LOG_FILE" << 'PYEOF' || true
import os
keyring_dir = os.path.expanduser("~/.local/share/keyrings")
default_keyring = os.path.join(keyring_dir, "Default.keyring")

# Only create if it doesn't exist
if not os.path.exists(default_keyring):
    try:
        # Create a minimal keyring file with no password
        keyring_content = """[keyring]
display-name=Default
ctime=0
mtime=0
lock-on-idle=false
lock-timeout=0
"""
        os.makedirs(keyring_dir, exist_ok=True)
        with open(default_keyring, 'w') as f:
            f.write(keyring_content)
        os.chmod(default_keyring, 0o600)
        print(f"Created default keyring at {default_keyring}")
    except Exception as e:
        print(f"Failed to create keyring: {e}")
PYEOF
    echo "$(date): GNOME Keyring configured" >> "$LOG_FILE"
fi

# Configure libfm to skip executable file dialog (Bookworm security feature)
echo "$(date): Configuring libfm quick_exec..." >> "$LOG_FILE"
LIBFM_CONFIG="$HOME/.config/libfm/libfm.conf"
if [ -f "$LIBFM_CONFIG" ]; then
    # Check if quick_exec is already set to 1
    if ! grep -q "^quick_exec=1" "$LIBFM_CONFIG"; then
        # Try to update existing quick_exec line
        if grep -q "^quick_exec=" "$LIBFM_CONFIG"; then
            sed -i 's/^quick_exec=.*/quick_exec=1/' "$LIBFM_CONFIG" 2>> "$LOG_FILE" && \
                echo "$(date): Updated quick_exec=1 in libfm.conf" >> "$LOG_FILE" || \
                echo "$(date): Failed to update quick_exec in libfm.conf" >> "$LOG_FILE"
        else
            # Add quick_exec=1 to [config] section
            sed -i '/^\[config\]/a quick_exec=1' "$LIBFM_CONFIG" 2>> "$LOG_FILE" && \
                echo "$(date): Added quick_exec=1 to libfm.conf" >> "$LOG_FILE" || \
                echo "$(date): Failed to add quick_exec to libfm.conf" >> "$LOG_FILE"
        fi
    else
        echo "$(date): quick_exec=1 already set in libfm.conf" >> "$LOG_FILE"
    fi
else
    echo "$(date): libfm config not found at $LIBFM_CONFIG" >> "$LOG_FILE"
fi

echo "$(date): First-login setup completed" >> "$LOG_FILE"

# Remove autostart entry so this doesn't run again
rm -f "$HOME/.config/autostart/trust-rasqberry-desktop.desktop"
EOF

    chmod 755 "/usr/local/bin/trust-rasqberry-desktop-files.sh"

    # Create autostart .desktop file
    cat > "$AUTOSTART_DIR/trust-rasqberry-desktop.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=RasQberry First Login Setup
Comment=Configure desktop settings on first login (runs once)
Exec=/usr/local/bin/trust-rasqberry-desktop-files.sh
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$AUTOSTART_DIR"
    echo "Created first-login desktop configuration script"
fi

# Clean up cloned repository to save space
if [ -d "${CLONE_DIR}" ]; then
    echo "Cleaning up cloned repository..."
    rm -rf "${CLONE_DIR}"
fi

echo "Desktop bookmarks installation completed"