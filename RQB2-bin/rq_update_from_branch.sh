#!/bin/bash
set -euo pipefail

# ============================================================================
# RasQberry: Update from GitHub Branch
# ============================================================================
# Description: Update RasQberry scripts and configs from a GitHub branch
# Usage: rq_update_from_branch.sh [--repo user/repo] [--branch branch_name]
#
# This script updates:
#   - Scripts in /usr/bin/ (from RQB2-bin/)
#   - Config files in /usr/config/ (from RQB2-config/)
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
DEFAULT_BRANCH="main"

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
    # Create timestamped backup of current files
    local timestamp
    timestamp=$(date '+%Y%m%d-%H%M%S')
    local backup_dir="/var/tmp/rasqberry-backup-${timestamp}"

    log_message "Creating backup in $backup_dir..."
    mkdir -p "$backup_dir"

    # Backup key files (not everything, just what we're updating)
    if [ -d "$TARGET_CONFIG" ]; then
        cp -a "$TARGET_CONFIG" "$backup_dir/config" 2>/dev/null || true
    fi

    # Store backup location for potential rollback
    echo "$backup_dir" > /var/tmp/rasqberry-last-backup

    log_message "Backup created"
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

    # Copy regular files
    for file in "$source_dir"/*; do
        if [ -f "$file" ]; then
            local filename
            filename=$(basename "$file")
            cp "$file" "$TARGET_CONFIG/$filename"
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
  -h, --help          Show this help message

Examples:
  # Update from main branch (auto-detect repository)
  sudo $0 --branch main

  # Update from specific branch
  sudo $0 --branch dev-features05

  # Update from different repository
  sudo $0 --repo JanLahmann/RasQberry-Two --branch main

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
        info ""
        info "Run without --dry-run to apply changes."
        exit 0
    fi

    # Clone the branch
    if ! clone_branch "$repo" "$branch" "$WORK_DIR"; then
        die "Failed to clone repository. Check internet connection and branch name."
    fi

    # Create backup (unless skipped)
    if [ "$skip_backup" != true ]; then
        backup_current
    fi

    # Copy files
    copy_bin_files "$WORK_DIR"
    copy_config_files "$WORK_DIR"

    # Reload environment
    reload_environment

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
    info "  - Environment reloaded"
    info ""
    info "Note: You may need to restart raspi-config or reboot for"
    info "all changes to take effect in the menu system."
}

main "$@"
