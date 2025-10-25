# RasQberry Common Library (rq_common.sh)

Shared utilities library for all RasQberry-Two scripts. This library provides standardized functions for error handling, environment management, dialogs, and more.

## Table of Contents

- [Quick Start](#quick-start)
- [Function Reference](#function-reference)
  - [1. Error Handling & Logging](#1-error-handling--logging)
  - [2. Environment Management](#2-environment-management)
  - [3. Virtual Environment](#3-virtual-environment-management)
  - [4. Whiptail Dialogs](#4-whiptail-dialogs)
  - [5. Git Operations](#5-git-operations)
  - [6. LED Control](#6-led-control)
  - [7. Dependency Checking](#7-dependency-checking)
  - [8. Process Management](#8-process-management)
  - [9. Path & Directory Helpers](#9-path--directory-helpers)
  - [10. User Context](#10-user-context-helpers)
  - [11. Browser Launching](#11-browser-launching)
  - [12. Demo Installation](#12-demo-installation-helpers)
- [Script Template](#script-template)
- [Examples](#examples)

---

## Quick Start

### Basic Usage

```bash
#!/bin/bash
set -euo pipefail

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load RQB2 environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

# Your script logic here...
```

### With Debug Mode

```bash
# Enable debug output
export RQ_DEBUG=1

# Now all debug() calls will print
. "${SCRIPT_DIR}/rq_common.sh"
```

---

## Function Reference

### 1. Error Handling & Logging

#### `die "message"`
Print error message to stderr and exit with code 1.

```bash
[ -f "$config_file" ] || die "Config file not found: $config_file"
```

#### `warn "message"`
Print warning message to stderr (doesn't exit).

```bash
warn "Using default configuration"
```

#### `info "message"`
Print informational message to stdout.

```bash
info "Starting demo installation..."
```

#### `debug "message"`
Print debug message to stderr (only if `RQ_DEBUG=1`).

```bash
debug "Using venv: $venv_path"
```

---

### 2. Environment Management

#### `load_rqb2_env`
Load RasQberry environment configuration. **This is the canonical way to load environment.**

```bash
load_rqb2_env
# Now REPO, USER_HOME, STD_VENV, etc. are available
```

**Replaces patterns like:**
```bash
# OLD - Don't do this anymore
if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
    . "/usr/config/rasqberry_env-config.sh"
else
    echo "Error: config not found"
    exit 1
fi

# NEW - Use this instead
load_rqb2_env
```

#### `verify_env_vars VAR1 VAR2 ...`
Verify required variables are set (dies if any missing).

```bash
verify_env_vars REPO USER_HOME STD_VENV
# Script continues only if all three are set
```

#### `update_env_var "NAME" "value"`
Update or add variable in environment file and reload.

```bash
update_env_var "LED_PAINTER_INSTALLED" "true"
```

---

### 3. Virtual Environment Management

#### `find_venv [venv_name]`
Find virtual environment in standard locations (returns path or fails).

```bash
venv_path=$(find_venv) || die "Venv not found"
venv_path=$(find_venv "custom-venv")
```

#### `activate_venv [venv_name]`
Activate virtual environment (tries multiple locations).

```bash
activate_venv  # Uses $STD_VENV
activate_venv "RQB2"  # Specific venv
```

**Replaces:**
```bash
# OLD
if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
    . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
fi

# NEW
activate_venv || warn "Venv not available"
```

#### `ensure_venv [venv_name] [packages...]`
Ensure venv exists and optionally verify packages are installed.

```bash
ensure_venv RQB2 qiskit numpy
# Dies if venv missing or packages not importable
```

---

### 4. Whiptail Dialogs

#### `show_yesno "Title" "Text" [height] [width]`
Show yes/no dialog (returns 0 for yes, 1 for no).

```bash
if show_yesno "Confirm" "Install demo?"; then
    info "User confirmed"
else
    info "User cancelled"
    exit 0
fi
```

#### `show_msgbox "Title" "Text" [height] [width]`
Show message box (waits for OK).

```bash
show_msgbox "Success" "Demo installed successfully!"
```

#### `show_infobox "Title" "Text" [height] [width]`
Show info box (doesn't wait for user).

```bash
show_infobox "Installing" "Please wait..."
```

#### `show_menu "Title" "Prompt" "key1" "label1" "key2" "label2" ...`
Show menu and return selected key.

```bash
choice=$(show_menu "Select Demo" "Choose:" \
    "1" "Quantum Lights Out" \
    "2" "Raspberry Tie" \
    "3" "Exit")

case "$choice" in
    1) run_lights_out ;;
    2) run_rasp_tie ;;
    3) exit 0 ;;
esac
```

---

### 5. Git Operations

#### `clone_demo "url" "dest_dir" [depth]`
Clone repository with ownership fixing (default shallow clone).

```bash
clone_demo "$GIT_REPO_DEMO_QLO" "$DEMO_DIR"
clone_demo "https://github.com/user/repo.git" "/path/to/dest" 999
```

**Replaces:**
```bash
# OLD
if git clone --depth 1 "$GIT_URL" "$DEST_DIR"; then
    if [ "$(stat -c '%U' "$DEST_DIR")" = "root" ]; then
        sudo chown -R "$USER:$USER" "$DEST_DIR"
    fi
fi

# NEW
clone_demo "$GIT_URL" "$DEST_DIR"
```

#### `update_demo "/path/to/demo" [branch]`
Update existing demo repository (git pull).

```bash
update_demo "$DEMO_DIR"
update_demo "$DEMO_DIR" "develop"
```

#### `fix_root_ownership "/path/to/file"`
Fix ownership if file/dir was created as root.

```bash
fix_root_ownership "$DEMO_DIR"
```

---

### 6. LED Control

#### `find_led_script [script_name]`
Find LED control script in standard locations.

```bash
led_script=$(find_led_script) || die "LED script not found"
python3 "$led_script"
```

#### `clear_leds`
Turn off all LEDs (finds and runs turn_off_LEDs.py).

```bash
clear_leds  # Silent if script not found
```

**Replaces:**
```bash
# OLD
python3 "$BIN_DIR/turn_off_LEDs.py" 2>/dev/null || true

# NEW
clear_leds
```

---

### 7. Dependency Checking

#### `require_command cmd [error_message]`
Require command to be available (dies if not found).

```bash
require_command docker "Docker is required. Please install Docker first."
require_command git
```

#### `check_docker`
Check if Docker is available (returns 0 if found).

```bash
check_docker || die "Docker required"

if check_docker; then
    info "Docker available"
fi
```

#### `check_display`
Check if GUI display is available.

```bash
check_display || die "This demo requires a graphical display"
```

---

### 8. Process Management

#### `cleanup_demo_processes "pattern1" "pattern2" ...`
Kill processes matching patterns.

```bash
cleanup_demo_processes "QuantumLightsOut" "RasQ-LED"
```

**Replaces:**
```bash
# OLD
pkill -f "QuantumLightsOut" 2>/dev/null || true
pkill -f "RasQ-LED" 2>/dev/null || true

# NEW
cleanup_demo_processes "QuantumLightsOut" "RasQ-LED"
```

#### `setup_cleanup_trap function_name`
Setup EXIT/INT/TERM trap to call cleanup function.

```bash
cleanup() {
    clear_leds
    cleanup_demo_processes "MyDemo"
}

setup_cleanup_trap cleanup
# Now cleanup() runs on script exit or Ctrl+C
```

---

### 9. Path & Directory Helpers

#### `get_demo_dir "demo-name"`
Get full path to demo directory.

```bash
demo_dir=$(get_demo_dir "Quantum-Lights-Out")
# Returns: /home/user/RasQberry-Two/demos/Quantum-Lights-Out
```

**Replaces:**
```bash
# OLD
DEMO_DIR="$USER_HOME/$REPO/demos/Quantum-Lights-Out"

# NEW
DEMO_DIR=$(get_demo_dir "Quantum-Lights-Out")
```

#### `ensure_demo_dir "demo-name"`
Verify demo directory exists (dies if not).

```bash
demo_dir=$(ensure_demo_dir "Quantum-Lights-Out") || die "Demo not installed"
cd "$demo_dir" || die "Cannot change directory"
```

---

### 10. User Context Helpers

#### `get_user_name`
Get non-root user name (handles sudo context).

```bash
user=$(get_user_name)
# Returns "rasqberry" even if script running as root via sudo
```

#### `run_as_user command args...`
Run command as non-root user (if we're root).

```bash
run_as_user pip install PySide6
# Runs as rasqberry if we're root, otherwise runs normally
```

**Replaces:**
```bash
# OLD
if [ "$(whoami)" = "root" ] && [ -n "$SUDO_USER" ]; then
    sudo -u "$SUDO_USER" -H -- pip install PySide6
else
    pip install PySide6
fi

# NEW
run_as_user pip install PySide6
```

---

### 11. Browser Launching

#### `open_browser "url"`
Open URL in available browser (handles root context).

```bash
open_browser "http://localhost:8080"
```

**Replaces:**
```bash
# OLD
if command -v chromium-browser &> /dev/null; then
    if [ "$(whoami)" = "root" ]; then
        su - "$USER" -c "DISPLAY=:0 chromium-browser '$URL' &"
    else
        chromium-browser "$URL" &
    fi
fi

# NEW
open_browser "$URL"
```

---

### 12. Demo Installation Helpers

#### `ask_demo_install "name" "download" "install"`
Ask user to install demo with size information.

```bash
ask_demo_install "LED-Painter" "5MB" "500MB" || exit 0
# Shows whiptail dialog, returns 0 if user confirms
```

#### `install_demo_raspiconfig function_name`
Install demo using raspi-config nonint function.

```bash
install_demo_raspiconfig do_qlo_install || die "Installation failed"
```

---

## Script Template

Use this template for new demo scripts:

```bash
#!/bin/bash
# RasQberry: [Demo Name] Launcher
# [Description]

set -euo pipefail

# ============================================================================
# SETUP
# ============================================================================

# Load common library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

# Load and verify environment
load_rqb2_env
verify_env_vars REPO USER_HOME STD_VENV

# ============================================================================
# CONFIGURATION
# ============================================================================

DEMO_NAME="Demo-Name"
DEMO_DIR=$(get_demo_dir "$DEMO_NAME")
GIT_URL="${GIT_REPO_DEMO_NAME:-https://github.com/user/repo.git}"

# ============================================================================
# FUNCTIONS
# ============================================================================

# Cleanup function
cleanup() {
    clear_leds
    cleanup_demo_processes "MyDemo"
}

# Check and install if needed
check_and_install() {
    if ! ensure_demo_dir "$DEMO_NAME" >/dev/null 2>&1; then
        ask_demo_install "$DEMO_NAME" "5MB" "10MB" || return 1
        clone_demo "$GIT_URL" "$DEMO_DIR"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

# Setup cleanup
setup_cleanup_trap cleanup

# Check dependencies
check_display || die "This demo requires a graphical display"

# Install if needed
check_and_install || die "Demo not installed"

# Activate venv
activate_venv || die "Virtual environment not found"

# Run demo
cd "$DEMO_DIR" || die "Cannot change to demo directory"
info "Launching $DEMO_NAME..."
exec python3 main.py "$@"
```

---

## Examples

### Example 1: Simple Demo Launcher

```bash
#!/bin/bash
set -euo pipefail

. "$(dirname "$0")/rq_common.sh"
load_rqb2_env

DEMO_DIR=$(get_demo_dir "Quantum-Lights-Out")
ensure_demo_dir "Quantum-Lights-Out" >/dev/null || die "Demo not installed"

activate_venv
cd "$DEMO_DIR" || die "Cannot change directory"
exec python3 lights_out.py
```

### Example 2: Demo with Installation

```bash
#!/bin/bash
set -euo pipefail

. "$(dirname "$0")/rq_common.sh"
load_rqb2_env

DEMO_DIR=$(get_demo_dir "LED-Painter")

# Check if installed
if ! ensure_demo_dir "LED-Painter" >/dev/null 2>&1; then
    # Ask user to install
    ask_demo_install "LED-Painter" "5MB" "500MB" || exit 0

    # Clone repository
    clone_demo "$GIT_REPO_DEMO_LED_PAINTER" "$DEMO_DIR"

    # Install dependencies
    activate_venv
    run_as_user pip install PySide6

    update_env_var "LED_PAINTER_INSTALLED" "true"
fi

# Run demo
activate_venv
cd "$DEMO_DIR" || die "Cannot change directory"
exec python3 LED_painter.py
```

### Example 3: Docker-based Demo

```bash
#!/bin/bash
set -euo pipefail

. "$(dirname "$0")/rq_common.sh"
load_rqb2_env

# Check Docker
check_docker || die "Docker is required. Please run qoffee-setup.sh first."

# Start container
CONTAINER_NAME="qoffee"
PORT=8887

info "Starting Qoffee-Maker container..."
docker run -d --name "$CONTAINER_NAME" -p "$PORT:8888" \
    ghcr.io/janlahmann/qoffee-maker || die "Failed to start container"

# Wait for startup
sleep 5

# Open browser
JUPYTER_URL="http://localhost:$PORT"
open_browser "$JUPYTER_URL"

info "Qoffee-Maker running at $JUPYTER_URL"
```

### Example 4: Demo with Cleanup

```bash
#!/bin/bash
set -euo pipefail

. "$(dirname "$0")/rq_common.sh"
load_rqb2_env

# Cleanup function
cleanup() {
    info "Cleaning up..."
    cleanup_demo_processes "MyDemo"
    clear_leds
}

# Register cleanup
setup_cleanup_trap cleanup

# Run demo
activate_venv
python3 "$BIN_DIR/my_demo.py"
```

---

## Migration Guide

### Migrating Existing Scripts

1. **Add library sourcing**:
   ```bash
   # At top of script, after shebang
   . "$(dirname "$0")/rq_common.sh"
   ```

2. **Replace environment loading**:
   ```bash
   # OLD
   if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
       . "/usr/config/rasqberry_env-config.sh"
   else
       echo "Error: config not found"
       exit 1
   fi

   # NEW
   load_rqb2_env
   ```

3. **Replace error handling**:
   ```bash
   # OLD
   if [ ! -d "$DEMO_DIR" ]; then
       echo "Error: demo not found"
       exit 1
   fi

   # NEW
   ensure_demo_dir "Quantum-Lights-Out" || die "Demo not installed"
   ```

4. **Replace venv activation**:
   ```bash
   # OLD
   if [ -f "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate" ]; then
       . "$USER_HOME/$REPO/venv/$STD_VENV/bin/activate"
   fi

   # NEW
   activate_venv || warn "Venv not available"
   ```

5. **Replace whiptail dialogs**:
   ```bash
   # OLD
   whiptail --title "Confirm" --yesno "Continue?" 10 60
   if [ $? -eq 0 ]; then
       echo "Continuing..."
   fi

   # NEW
   if show_yesno "Confirm" "Continue?"; then
       info "Continuing..."
   fi
   ```

---

## Best Practices

1. **Always verify environment variables**:
   ```bash
   load_rqb2_env
   verify_env_vars REPO USER_HOME STD_VENV
   ```

2. **Use `die` for fatal errors, `warn` for warnings**:
   ```bash
   [ -f "$config" ] || die "Config not found"
   [ -f "$cache" ] || warn "Cache missing, will recreate"
   ```

3. **Register cleanup handlers**:
   ```bash
   cleanup() {
       clear_leds
       cleanup_demo_processes "MyDemo"
   }
   setup_cleanup_trap cleanup
   ```

4. **Use `run_as_user` for user-context operations**:
   ```bash
   run_as_user pip install package
   run_as_user git clone "$URL" "$DEST"
   ```

5. **Enable debug mode during development**:
   ```bash
   export RQ_DEBUG=1
   ./my_script.sh
   ```

---

## Compatibility

- **Shell**: Requires Bash 4.0+ (uses arrays, string manipulation)
- **Platform**: Linux (Raspberry Pi OS), macOS (development)
- **Dependencies**:
  - Core: bash, git
  - Optional: whiptail (fallback to `read` if missing)
  - Python: python3 (for venv functions)

---

## Version History

- **v1.0** (2024-01-22): Initial release with 12 function categories
  - Error handling & logging
  - Environment management
  - Virtual environment support
  - Whiptail dialogs
  - Git operations
  - LED control
  - Dependency checking
  - Process management
  - Path helpers
  - User context
  - Browser launching
  - Demo installation
