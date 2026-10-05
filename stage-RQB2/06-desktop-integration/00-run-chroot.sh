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

# (Launcher scripts in RQB2-bin are installed to /usr/bin by 01-deploy-files.)

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
    if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|qoffee-maker|quantum-mixer|led-ibm-demo|led-painter|clear-leds|rasq-led|demo-loop|fun-with-quantum|quantum-coin-game|quantum-paradoxes|touch-mode|rasqberry-setup|rasqberry-menu|ibm-quantum-tutorials|ibm-quantum-courses|quantum-lab|qiskit-tutorials|doqumentation|my-quantum-programs|learning-paths)\.desktop$ ]]; then
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
        if [ -f "$desktop_file" ] && [[ "$(basename "$desktop_file")" =~ ^(composer|grok-bloch|quantum-fractals|quantum-lights-out|quantum-raspberry-tie|qoffee-maker|quantum-mixer|led-ibm-demo|led-painter|clear-leds|rasq-led|demo-loop|fun-with-quantum|quantum-coin-game|quantum-paradoxes|touch-mode|rasqberry-setup|rasqberry-menu|ibm-quantum-tutorials|ibm-quantum-courses|quantum-lab|qiskit-tutorials|doqumentation|my-quantum-programs|learning-paths)\.desktop$ ]]; then
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
EOF
    # Icon positions for a 1920x1080 screen, RasQberry Setup first. At every
    # login rq_desktop_session.py lays them out again for the actual screen
    # (small screens, touch mode) - R-008, R-035.
    python3 "${CLONE_DIR}/RQB2-bin/rq_desktop_session.py" --layout 1920x1080 "$USER_CONFIG_DIR/desktop-items-0.conf" \
        || echo "WARNING: could not write the desktop icon positions"

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
# /etc/xdg/menus/applications-merged/rasqberry.menu is installed from RQB2-system/ by 01-deploy-files (#294)

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

# Note: Virtual keyboard (wvkbd) is installed separately in stage 09-touchscreen-support
# and toggled manually via panel icon - no autostart needed

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
# Note: We put the autostart in /etc/skel so it gets copied on first boot,
# not in user's home during build (which could run prematurely in chroot)
if [ -n "${FIRST_USER_NAME}" ] && [ "${FIRST_USER_NAME}" != "root" ]; then
    AUTOSTART_DIR="/etc/skel/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"

    # Create the first-login setup script
    # /usr/local/bin/trust-rasqberry-desktop-files.sh is installed from RQB2-system/ by 01-deploy-files (#294)


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

    # Note: Don't chown - /etc/skel is owned by root, copied to user on first boot
    echo "Created first-login desktop configuration script in /etc/skel"
fi

# Clean up cloned repository to save space
if [ -d "${CLONE_DIR}" ]; then
    echo "Cleaning up cloned repository..."
    rm -rf "${CLONE_DIR}"
fi

# =============================================================================
# Chromium Configuration for RasQberry Homepage (Issue #189)
# =============================================================================
echo "Configuring Chromium browser settings..."

# Create Chromium managed policy for homepage and settings
mkdir -p /etc/chromium/policies/managed
cat > /etc/chromium/policies/managed/rasqberry.json << 'EOF'
{
  "HomepageLocation": "https://rasqberry.org",
  "HomepageIsNewTabPage": false,
  "NewTabPageLocation": "https://rasqberry.org",
  "RestoreOnStartup": 4,
  "RestoreOnStartupURLs": ["https://rasqberry.org"],
  "PasswordManagerEnabled": false,
  "ShowHomeButton": true,
  "PromotionalTabsEnabled": false,
  "WelcomePagesEnabled": false,
  "BookmarkBarEnabled": true,
  "ManagedBookmarks": [
    { "toplevel_name": "Quantum Links" },
    {
      "name": "Fun with Quantum family",
      "children": [
        { "name": "Fun with Quantum", "url": "https://fun-with-quantum.org" },
        { "name": "RasQberry One", "url": "https://rasqberry.one" },
        { "name": "Quantego", "url": "https://quantego.org" },
        { "name": "Qutie", "url": "https://qutie.org" },
        { "name": "doQumentation", "url": "https://doqumentation.org" },
        { "name": "QuBins", "url": "https://qubins.org" },
        { "name": "QAMPoser games", "url": "https://qamposer.org" }
      ]
    },
    {
      "name": "IBM Quantum",
      "children": [
        { "name": "IBM Quantum Learning", "url": "https://quantum.cloud.ibm.com/learning" }
      ]
    }
  ]
}
EOF
chmod 644 /etc/chromium/policies/managed/rasqberry.json
echo "Created Chromium policy for RasQberry homepage"

# Chromium flags (no keyring dialog, no "Restore pages?", maximised on small
# screens, touch mode) are in /etc/chromium.d/rasqberry from RQB2-system/, so
# that a Chromium update keeps them (R-141); chromium.desktop stays as shipped.

# =============================================================================
# Autostart Chromium browser on login (with delay for time sync)
# =============================================================================
echo "Creating Chromium autostart entry with startup delay..."
# /etc/xdg/autostart/rasqberry-browser.desktop is installed from RQB2-system/ by 01-deploy-files (#294)
echo "Chromium will start automatically on login (10s delay for time sync)"

# =============================================================================
# Configure labwc window positioning for Chromium
# =============================================================================
echo "Configuring labwc window rules for Chromium..."

# Create labwc config directory in skel for new users
SKEL_LABWC_DIR="/etc/skel/.config/labwc"
mkdir -p "$SKEL_LABWC_DIR"

# Create rc.xml with touch config and window rules (Chromium, on-screen LED view)
# Note: Empty deviceName applies mouseEmulation to ALL touch devices (universal fallback)
cat > "${SKEL_LABWC_DIR}/rc.xml" << 'EOF'
<?xml version="1.0"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <!-- Enable mouse emulation for all USB/HDMI touch screens (enables double-tap) -->
  <touch deviceName="" mouseEmulation="yes" />
  <windowRules>
    <!-- Chromium to the right of the desktop icons; rq_desktop_session.py
         switches this rule off on small screens, where Chromium opens maximised -->
    <windowRule identifier="chromium">
      <action name="MoveTo" x="480" y="45"/>
    </windowRule>
    <!-- The on-screen LED view in the bottom right corner, not over the demo's terminal -->
    <windowRule title="RasQberry Virtual LED*">
      <action name="MoveToEdge" direction="right" snapWindows="no"/>
      <action name="MoveToEdge" direction="down" snapWindows="no"/>
    </windowRule>
  </windowRules>
</openbox_config>
EOF
echo "Created labwc window rules: ${SKEL_LABWC_DIR}/rc.xml"

# Also create for first user if exists
if [ -n "${FIRST_USER_NAME}" ]; then
    USER_LABWC_DIR="/home/${FIRST_USER_NAME}/.config/labwc"
    mkdir -p "$USER_LABWC_DIR"
    cp "${SKEL_LABWC_DIR}/rc.xml" "${USER_LABWC_DIR}/rc.xml"
    chown -R "${FIRST_USER_NAME}:${FIRST_USER_NAME}" "$USER_LABWC_DIR"
    echo "Created user labwc config: ${USER_LABWC_DIR}/rc.xml"
fi

# =============================================================================
# Disable GNOME Keyring secrets component to prevent password dialogs
# =============================================================================
echo "Disabling GNOME Keyring secrets component..."

# Disable XDG autostart for gnome-keyring-secrets
# dpkg-divert, not mv: a gnome-keyring update would put a moved file back (R-141)
if [ -f "/etc/xdg/autostart/gnome-keyring-secrets.desktop" ]; then
    dpkg-divert --local --rename --divert /etc/xdg/autostart/gnome-keyring-secrets.desktop.disabled \
        --add /etc/xdg/autostart/gnome-keyring-secrets.desktop
    echo "Disabled gnome-keyring-secrets autostart"
fi

# Disable D-Bus activation for gnome-keyring (these auto-start keyring when apps request secrets)
for dbus_service in \
    "/usr/share/dbus-1/services/org.freedesktop.secrets.service" \
    "/usr/share/dbus-1/services/org.gnome.keyring.service" \
    "/usr/share/dbus-1/services/org.freedesktop.impl.portal.Secret.service"; do
    if [ -f "$dbus_service" ]; then
        dpkg-divert --local --rename --divert "${dbus_service}.disabled" --add "$dbus_service"
        echo "Disabled D-Bus service: $(basename "$dbus_service")"
    fi
done

# Mask gnome-keyring systemd user service (for all users via skel)
mkdir -p /etc/skel/.config/systemd/user
ln -sf /dev/null /etc/skel/.config/systemd/user/gnome-keyring-daemon.socket
ln -sf /dev/null /etc/skel/.config/systemd/user/gnome-keyring-daemon.service
echo "Masked gnome-keyring systemd services in /etc/skel"

echo "Chromium and keyring configuration completed"

# Clean up any PCManFM 'default' profile configs that might have been created during build
# These can override the correct LXDE-pi profile configs and cause wallpaper/icon issues
# (PCManFM on Wayland creates output-specific configs like desktop-items-HDMI-A-2.conf)
if [ -n "${FIRST_USER_NAME}" ] && [ -d "/home/${FIRST_USER_NAME}/.config/pcmanfm/default" ]; then
    echo "Cleaning up PCManFM default profile configs created during build..."
    rm -rf "/home/${FIRST_USER_NAME}/.config/pcmanfm/default"
fi

echo "Desktop bookmarks installation completed"