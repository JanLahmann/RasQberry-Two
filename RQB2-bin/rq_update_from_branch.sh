#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Update from GitHub Branch
# ============================================================================
# Description: Update RasQberry scripts and configs from a GitHub branch
# Usage: rq_update_from_branch.sh [--repo user/repo] [--branch branch_name]
#        rq_update_from_branch.sh --restore    put back what the last update replaced
#
# This script updates:
#   - Scripts in /usr/bin/ (from RQB2-bin/)
#   - Config files in /usr/config/ (from RQB2-config/); device settings in
#     rasqberry_environment.env are kept (merged), see RQB2-config/CONFIG_FILES.md
#
# This does NOT update:
#   - System packages (kernel, bootloader)
#   - Python virtual environment packages
#   - Partition layout changes
#
# For full system updates, use A/B boot slot update instead.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source common library if available
if [ -f "${SCRIPT_DIR}/rq_common.sh" ]; then
    . "${SCRIPT_DIR}/rq_common.sh"
elif [ -f "/usr/bin/rq_common.sh" ]; then
    . "/usr/bin/rq_common.sh"
else
    # Minimal fallback functions
    die() { echo "ERROR: $*" >&2; exit 1; }
    warn() { echo "WARNING: $*" >&2; }
    info() { echo "INFO: $*"; }
fi

# Configuration
WORK_DIR="/var/tmp/rasqberry-branch-update"
LOG_FILE="/var/log/rasqberry-branch-update.log"
DEFAULT_REPO="JanLahmann/RasQberry-Two"
DEFAULT_BRANCH="beta"   # main holds the website only, no RQB2-bin
BACKUP_POINTER="/var/tmp/rasqberry-last-backup"
KEEP_BACKUPS=3

# Paths to update
TARGET_BIN="/usr/bin"
TARGET_CONFIG="/usr/config"

# ============================================================================
# Helper Functions
# ============================================================================

log_message() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$LOG_FILE"
}

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        die "This script must be run as root (use sudo)"
    fi
}

detect_current_repo() {
    # Try to detect repository from installed system
    local repo=""

    # Method 1: Check git remote in user's repo directory
    local user_home="${USER_HOME:-/home/pi}"
    local repo_name="${REPO:-RasQberry-Two}"
    local git_config="${user_home}/${repo_name}/.git/config"

    if [ -f "$git_config" ]; then
        # Extract origin URL from git config
        local origin_url
        origin_url=$(grep -A2 '\[remote "origin"\]' "$git_config" 2>/dev/null | grep 'url' | sed 's/.*= //' | head -1)

        if [ -n "$origin_url" ]; then
            # Parse GitHub URL (handles both https and git@ formats)
            if echo "$origin_url" | grep -q "github.com"; then
                repo=$(echo "$origin_url" | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|')
                # Remove .git suffix if present
                repo="${repo%.git}"
                log_message "Detected repository from git config: $repo"
            fi
        fi
    fi

    # Method 2: Use environment variables
    if [ -z "$repo" ]; then
        local git_user="${RQB_GIT_USER:-}"
        local git_repo="${REPO:-}"
        if [ -n "$git_user" ] && [ -n "$git_repo" ]; then
            repo="${git_user}/${git_repo}"
            log_message "Using repository from environment: $repo"
        fi
    fi

    # Method 3: Default fallback
    if [ -z "$repo" ]; then
        repo="$DEFAULT_REPO"
        log_message "Using default repository: $repo"
    fi

    echo "$repo"
}

clone_branch() {
    local repo="$1"
    local branch="$2"
    local dest="$3"

    log_message "Cloning $repo (branch: $branch) to $dest..."

    # Clean up any existing work directory
    rm -rf "$dest"
    mkdir -p "$dest"

    # Clone with depth 1 for faster download
    local git_url="https://github.com/${repo}.git"

    if git clone --depth 1 --branch "$branch" "$git_url" "$dest" 2>&1 | tee -a "$LOG_FILE"; then
        log_message "Clone successful"
        return 0
    else
        log_message "Clone failed"
        return 1
    fi
}

backup_current() {
    # Create timestamped backup of the files an update replaces: the
    # RasQberry Two scripts in /usr/bin (rq_*) and /usr/config. --restore
    # puts them back (R-115: the backup used to hold /usr/config only, and
    # nothing could restore it).
    local timestamp
    timestamp=$(date '+%Y%m%d-%H%M%S')
    local backup_dir="/var/tmp/rasqberry-backup-${timestamp}"

    log_message "Creating backup in $backup_dir..."
    mkdir -p "$backup_dir/bin"

    if [ -d "$TARGET_CONFIG" ]; then
        cp -a "$TARGET_CONFIG" "$backup_dir/config" 2>/dev/null || true
    fi
    cp -a "$TARGET_BIN"/rq_* "$backup_dir/bin/" 2>/dev/null || true

    # Store backup location for --restore
    echo "$backup_dir" > "$BACKUP_POINTER"

    # Keep only the newest few backups
    local old
    for old in $(ls -1d /var/tmp/rasqberry-backup-* 2>/dev/null | sort -r | tail -n +$((KEEP_BACKUPS + 1))); do
        rm -rf "$old"
    done

    log_message "Backup created"
}

restore_backup() {
    # Put back the scripts and configuration saved by the last update.
    # Files the update added (new scripts) stay; system files from
    # RQB2-system/ are not part of the backup.
    local backup_dir
    backup_dir=$(cat "$BACKUP_POINTER" 2>/dev/null || true)
    [ -n "$backup_dir" ] && [ -d "$backup_dir" ] \
        || die "No saved scripts and configuration found (nothing to undo)"
    log_message "Restoring from $backup_dir..."
    if [ -d "$backup_dir/bin" ] && compgen -G "$backup_dir/bin/rq_*" >/dev/null; then
        cp -a "$backup_dir"/bin/rq_* "$TARGET_BIN/" || die "Could not restore the scripts in $TARGET_BIN"
    fi
    if [ -d "$backup_dir/config" ]; then
        cp -a "$backup_dir/config/." "$TARGET_CONFIG/" || die "Could not restore $TARGET_CONFIG"
    fi
    regenerate_menu_cache
    log_message "Restored scripts and configuration from $backup_dir"
    info "Restored the scripts and configuration saved on $(basename "$backup_dir" | sed 's/^rasqberry-backup-//')."
}

copy_bin_files() {
    local source_dir="$1/RQB2-bin"

    if [ ! -d "$source_dir" ]; then
        warn "No RQB2-bin directory found in source"
        return 0
    fi

    log_message "Copying scripts to $TARGET_BIN..."

    local count=0
    for file in "$source_dir"/*; do
        if [ -f "$file" ]; then
            local filename
            filename=$(basename "$file")
            cp "$file" "$TARGET_BIN/$filename"
            chmod +x "$TARGET_BIN/$filename" 2>/dev/null || true
            count=$((count + 1))
        fi
    done

    log_message "Copied $count files to $TARGET_BIN"
}

copy_config_files() {
    local source_dir="$1/RQB2-config"

    if [ ! -d "$source_dir" ]; then
        warn "No RQB2-config directory found in source"
        return 0
    fi

    log_message "Copying config files to $TARGET_CONFIG..."

    # Copy all files and directories, preserving structure
    local count=0

    # Copy regular files. See RQB2-config/CONFIG_FILES.md for which files are
    # shipped defaults (replaced), device state (merged) or generated
    # (rebuilt after the copy) - issue #290.
    for file in "$source_dir"/*; do
        if [ -f "$file" ]; then
            local filename
            filename=$(basename "$file")
            case "$filename" in
                rasqberry_environment.env)
                    merge_env_file "$file" "$1/RQB2-bin/rq_env_merge.py"
                    ;;
                demo-menu-cache.sh)
                    : # generated from the manifests on this device, see regenerate_menu_cache
                    ;;
                rasqberry-firstlogin.profile.sh|rasqberry-led-verify.profile.sh)
                    : # installed elsewhere by the image build, not used from here
                    ;;
                *)
                    cp "$file" "$TARGET_CONFIG/$filename"
                    ;;
            esac
            count=$((count + 1))
        fi
    done

    # Copy subdirectories (like demo-patches, LED-Logos)
    for dir in "$source_dir"/*/; do
        if [ -d "$dir" ]; then
            local dirname
            dirname=$(basename "$dir")
            mkdir -p "$TARGET_CONFIG/$dirname"
            cp -a "$dir"* "$TARGET_CONFIG/$dirname/" 2>/dev/null || true
            count=$((count + 1))
        fi
    done

    log_message "Copied $count items to $TARGET_CONFIG"
}

# The env file holds shipped defaults AND device state (LED layout from the
# first-login wizard, *_INSTALLED flags, ...). Merge: new keys and comments
# come from the branch, every key the device already has keeps its value.
merge_env_file() {
    local new_env="$1" merger="$2" current="$TARGET_CONFIG/rasqberry_environment.env"
    local merged="$WORK_DIR/rasqberry_environment.env.merged"

    if [ ! -f "$current" ]; then
        cp "$new_env" "$current"
        return 0
    fi
    [ -f "$merger" ] || merger="$TARGET_BIN/rq_env_merge.py"
    if command -v python3 >/dev/null 2>&1 && [ -f "$merger" ] \
        && python3 "$merger" "$new_env" "$current" "$merged" 2>&1 | tee -a "$LOG_FILE"; then
        install -m 644 "$merged" "$current"
        log_message "Merged rasqberry_environment.env (device settings kept)"
    else
        warn "Could not merge rasqberry_environment.env - kept the device's file unchanged"
    fi
}

# demo-menu-cache.sh is generated from the shipped manifests plus the user's
# catalog demos, so it is rebuilt here rather than copied from the branch.
regenerate_menu_cache() {
    local generator="$TARGET_BIN/rq_demo_generate_menu.sh"
    if [ -x "$generator" ] && "$generator" --cache "$TARGET_CONFIG/demo-menu-cache.sh" >/dev/null 2>&1; then
        chmod 644 "$TARGET_CONFIG/demo-menu-cache.sh"
        log_message "Demo menu cache regenerated"
    else
        warn "Could not regenerate the demo menu cache"
    fi
}

# Installed catalog demos keep their checkout; point out the ones whose pin
# in the updated known-demos.json has moved, and the ones installed under a
# name the catalogue has since changed (an entry's "replaces").
report_catalog_pins() {
    local registry="$TARGET_CONFIG/known-demos.json" home="${USER_HOME:-}"
    local manifest id dir ref head new
    # Run from raspi-config as root, USER_HOME can resolve to /root
    [ -d "$home/.local/config/demo-manifests" ] || home=$(getent passwd 1000 | cut -d: -f6)
    [ -f "$registry" ] && [ -n "$home" ] && command -v jq >/dev/null 2>&1 || return 0
    for manifest in "$home"/.local/config/demo-manifests/rq_demo_*.json; do
        [ -f "$manifest" ] || continue
        id=$(jq -r '.id // empty' "$manifest")
        dir=$(jq -r '.entrypoint.working_dir // empty' "$manifest")
        ref=$(jq -r --arg id "$id" '.demos[] | select(.id == $id) | .ref // empty' "$registry")
        [ -n "$id" ] && [ -n "$dir" ] || continue
        new=$(jq -r --arg id "$id" '[.demos[] | select(any(.replaces[]?; . == $id)) | .id][0] // empty' "$registry")
        if [ -z "$ref" ] && [ -n "$new" ]; then
            info "Catalog demo '$id' is now called '$new' - move it with: sudo rq_demo_add_external.sh --update $id"
            continue
        fi
        if [ -z "$ref" ]; then
            info "Catalog demo '$id' was withdrawn - remove with: sudo rq_demo_add_external.sh --remove $id"
            continue
        fi
        head=$(git -C "$home/${REPO:-RasQberry-Two}/demos/$dir" rev-parse HEAD 2>/dev/null || true)
        if [ -n "$head" ] && [ "$head" != "$ref" ]; then
            info "Catalog demo '$id' has a new pin - update with: sudo rq_demo_add_external.sh --update $id"
        fi
    done
}

# Boot scripts, systemd units, autostart entries etc. live in RQB2-system/ and
# are installed by the same script the image build uses (#294). New units are
# enabled; existing ones keep their state, so a unit turned off stays off.
install_system_files() {
    local tree="$1/RQB2-system" installer="$1/RQB2-bin/rq_install_system_files.sh"
    if [ ! -d "$tree" ] || [ ! -f "$installer" ]; then
        log_message "Branch has no RQB2-system/ - system files not updated"
        return 0
    fi
    log_message "Installing system files (boot scripts, services, autostart)..."
    bash "$installer" "$tree" --update 2>&1 | tee -a "$LOG_FILE" \
        || warn "Some system files could not be installed - see $LOG_FILE"
}

reload_environment() {
    log_message "Reloading environment configuration..."

    # Source the environment config to pick up changes
    if [ -f "/usr/config/rasqberry_env-config.sh" ]; then
        # shellcheck disable=SC1091
        . /usr/config/rasqberry_env-config.sh 2>/dev/null || true
        log_message "Environment reloaded"
    else
        warn "Environment config file not found"
    fi
}

cleanup() {
    log_message "Cleaning up work directory..."
    rm -rf "$WORK_DIR"
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Update RasQberry scripts and configuration from a GitHub branch.

Options:
  --repo USER/REPO    GitHub repository (default: auto-detect or $DEFAULT_REPO)
  --branch BRANCH     Branch name to pull from (default: $DEFAULT_BRANCH)
  --dry-run           Show what would be updated without making changes
  --no-backup         Skip creating backup of current files
  --restore           Put back the scripts and configuration saved before
                      the last update
  --from-dir DIR      Internal: continue on an existing clone (used when the
                      branch ships a newer updater and this one hands over)
  -h, --help          Show this help message

Examples:
  # Update from the beta branch (auto-detect repository)
  sudo $0 --branch beta

  # Update from specific branch
  sudo $0 --branch dev-features05

  # Update from different repository
  sudo $0 --repo JanLahmann/RasQberry-Two --branch development

  # Undo the last update
  sudo $0 --restore

  # Dry run to see what would be updated
  sudo $0 --branch dev --dry-run

Note: This updates scripts and configs only. For full system updates
including kernel and packages, use A/B boot slot update.
EOF
}

# ============================================================================
# Main
# ============================================================================

main() {
    local repo=""
    local branch="$DEFAULT_BRANCH"
    local dry_run=false
    local skip_backup=false
    local from_dir=""
    local restore=false

    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            --repo)
                repo="$2"
                shift 2
                ;;
            --branch)
                branch="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --no-backup)
                skip_backup=true
                shift
                ;;
            --from-dir)
                from_dir="$2"
                shift 2
                ;;
            --restore)
                restore=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                warn "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    check_root

    # Initialize log
    mkdir -p "$(dirname "$LOG_FILE")"

    if [ "$restore" = true ]; then
        log_message "=== RasQberry Branch Update: restore ==="
        restore_backup
        exit 0
    fi

    log_message "=== RasQberry Branch Update Started ==="

    # Detect repository if not specified
    if [ -z "$repo" ]; then
        repo=$(detect_current_repo)
    fi

    log_message "Repository: $repo"
    log_message "Branch: $branch"
    log_message "Dry run: $dry_run"

    if [ "$dry_run" = true ]; then
        info "DRY RUN MODE - No changes will be made"
        info ""
        info "Would update from: https://github.com/$repo (branch: $branch)"
        info "Would copy:"
        info "  RQB2-bin/*     -> $TARGET_BIN/"
        info "  RQB2-config/*  -> $TARGET_CONFIG/"
        info "  RQB2-system/*  -> / (boot scripts, services, autostart)"
        info ""
        info "Run without --dry-run to apply changes."
        exit 0
    fi

    # Clone the branch (unless re-executed on an existing clone, see below)
    if [ -n "$from_dir" ]; then
        [ "$from_dir" = "$WORK_DIR" ] || die "--from-dir must be $WORK_DIR"
        log_message "Continuing with the branch's own updater on $from_dir"
    else
        if ! clone_branch "$repo" "$branch" "$WORK_DIR"; then
            die "Failed to clone repository. Check internet connection and branch name."
        fi
        # A branch without the scripts (main is the website only) would
        # "succeed" while updating nothing (R-115)
        if [ ! -d "$WORK_DIR/RQB2-bin" ]; then
            rm -rf "$WORK_DIR"
            die "Branch '$branch' of $repo has no RasQberry Two scripts (no RQB2-bin/). Use beta or development."
        fi
        # Hand over to the updater from the branch, so a fix to the update
        # logic itself (such as keeping device settings, #290) applies to
        # this update and not only to the next one.
        local new_updater="$WORK_DIR/RQB2-bin/rq_update_from_branch.sh"
        if [ -f "$new_updater" ] && ! cmp -s "$new_updater" "$0" \
            && grep -q -- '--from-dir' "$new_updater"; then
            log_message "Branch ships a different updater - running it"
            local pass=(--repo "$repo" --branch "$branch" --from-dir "$WORK_DIR")
            [ "$skip_backup" = true ] && pass+=(--no-backup)
            exec bash "$new_updater" "${pass[@]}"
        fi
    fi

    # Create backup (unless skipped)
    if [ "$skip_backup" != true ]; then
        backup_current
    fi

    # Copy files
    copy_bin_files "$WORK_DIR"
    copy_config_files "$WORK_DIR"

    install_system_files "$WORK_DIR"
    regenerate_menu_cache

    # Reload environment
    reload_environment
    report_catalog_pins

    # Cleanup
    cleanup

    log_message "=== Update Complete ==="

    info ""
    info "Update completed successfully!"
    info ""
    info "Updated from: https://github.com/$repo (branch: $branch)"
    info ""
    info "Changes applied:"
    info "  - Scripts updated in $TARGET_BIN/"
    info "  - Config files updated in $TARGET_CONFIG/"
    info "  - Boot scripts, services and autostart entries updated"
    info "  - Environment reloaded"
    info ""
    info "Note: You may need to restart raspi-config or reboot for"
    info "all changes to take effect in the menu system."
}

main "$@"
