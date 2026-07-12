#!/bin/bash
#
# rq_demo_generate_desktop.sh - Generate .desktop files from demo manifests
#
# Usage:
#   rq_demo_generate_desktop.sh              # Generate to stdout (dry run)
#   rq_demo_generate_desktop.sh --output DIR # Generate to specified directory
#   rq_demo_generate_desktop.sh --diff       # Compare generated with existing
#   rq_demo_generate_desktop.sh --update     # Update desktop-bookmarks/ directory
#
# Requires: jq
#

set -euo pipefail

# Find script directory and manifest directory
# When installed: /usr/bin → /usr/config/...
# When in repo: RQB2-bin → RQB2-config/...
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    # Installed system: config is at /usr/config (see issue #246 for global vars)
    MANIFEST_DIR="/usr/config/demo-manifests"
    DESKTOP_DIR="/usr/config/desktop-bookmarks"
else
    # Development: relative to repo structure
    REPO_DIR="$(dirname "$SCRIPT_DIR")"
    MANIFEST_DIR="$REPO_DIR/RQB2-config/demo-manifests"
    DESKTOP_DIR="$REPO_DIR/RQB2-config/desktop-bookmarks"
fi

# Check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed." >&2
        echo "Install with: sudo apt-get install jq" >&2
        exit 1
    fi
}

# Sanitize name for use as filename
# - Convert to lowercase
# - Replace spaces with hyphens
# - Remove special characters (keep only alphanumeric and hyphens)
# - Collapse multiple hyphens
sanitize_name() {
    local name="$1"
    echo "$name" | \
        tr '[:upper:]' '[:lower:]' | \
        sed 's/ /-/g' | \
        sed 's/[^a-z0-9-]//g' | \
        sed 's/--*/-/g' | \
        sed 's/^-//; s/-$//'
}

# Generate a single .desktop file content
# Arguments: $1 = manifest file path
generate_desktop_entry() {
    local file="$1"

    # Read manifest fields
    local id name description keywords_json icon_type icon_path launcher browser_url terminal

    id=$(jq -r '.id' "$file")
    name=$(jq -r '.name' "$file")
    description=$(jq -r '.description // ""' "$file")
    keywords_json=$(jq -c '.keywords // []' "$file")
    icon_type=$(jq -r '.icon.type // "system"' "$file")
    icon_path=$(jq -r '.icon.path // "applications-other"' "$file")
    launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
    browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")
    terminal=$(jq -r '.desktop.terminal // true' "$file")

    # Skip if no launcher and no browser_url defined
    if [ -z "$launcher" ] && [ -z "$browser_url" ]; then
        echo "# Skipped $id: no launcher or browser_url defined" >&2
        return 1
    fi

    # Convert keywords array to semicolon-separated string
    local keywords
    keywords=$(echo "$keywords_json" | jq -r 'join(";")')
    if [ -n "$keywords" ]; then
        keywords="${keywords};"
    fi

    # Handle icon path
    local icon
    if [ "$icon_type" = "custom" ]; then
        icon="$icon_path"
    else
        # System icon - just the name
        icon="$icon_path"
    fi

    # Handle terminal setting
    local terminal_value
    if [ "$terminal" = "true" ]; then
        terminal_value="true"
    else
        terminal_value="false"
    fi

    # Build Exec command
    local exec_cmd tryexec
    if [ -n "$launcher" ]; then
        exec_cmd="/usr/bin/$launcher"
        tryexec="$exec_cmd"
    elif [ -n "$browser_url" ]; then
        exec_cmd="chromium-browser --password-store=basic $browser_url"
        tryexec="chromium-browser"
    fi

    # Generate the desktop entry
    cat << EOF
[Desktop Entry]
Version=1.1
Name=$name
Comment=$description
Icon=$icon
Type=Application
Categories=RasQberry;
Exec=$exec_cmd
Terminal=$terminal_value
StartupNotify=true
Keywords=$keywords
X-GNOME-TextColor=#000000
TryExec=$tryexec
NoDisplay=false
EOF
}

# Get all manifests with desktop.show=true (or missing/null, which defaults to true)
get_desktop_manifests() {
    find "$MANIFEST_DIR" -name 'rq_demo_*.json' -not -name '*schema*' -print0 2>/dev/null | \
    while IFS= read -r -d '' file; do
        local show
        # Note: // is alternative operator which treats false as falsy, so use explicit null check
        show=$(jq -r 'if .desktop.show == null then true else .desktop.show end' "$file" 2>/dev/null)
        if [ "$show" = "true" ]; then
            echo "$file"
        fi
    done
}

# Generate all desktop files
generate_all() {
    local output_dir="${1:-}"
    local count=0
    local skipped=0

    while read -r file; do
        [ -z "$file" ] && continue

        local name
        name=$(jq -r '.name' "$file")
        local filename
        filename="$(sanitize_name "$name").desktop"

        if [ -n "$output_dir" ]; then
            # Write to file
            if generate_desktop_entry "$file" > "$output_dir/$filename" 2>/dev/null; then
                echo "Generated: $filename"
                count=$((count + 1))
            else
                rm -f "$output_dir/$filename"
                skipped=$((skipped + 1))
            fi
        else
            # Write to stdout
            echo "=== $filename ==="
            if ! generate_desktop_entry "$file" 2>/dev/null; then
                echo "# (skipped - no launcher)"
                skipped=$((skipped + 1))
            else
                count=$((count + 1))
            fi
            echo ""
        fi
    done < <(get_desktop_manifests)

    echo "Generated $count desktop files, skipped $skipped" >&2
}

# Compare generated files with existing ones
diff_desktop_files() {
    local temp_dir
    temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT

    echo "Generating desktop files to temp directory..."
    generate_all "$temp_dir" 2>/dev/null

    echo ""
    echo "Comparing with existing files in $DESKTOP_DIR:"
    echo "================================================"

    local differences=0
    local missing_in_generated=0
    local missing_in_existing=0

    # Compare generated files with existing
    for generated in "$temp_dir"/*.desktop; do
        [ -f "$generated" ] || continue
        local filename
        filename=$(basename "$generated")
        local existing="$DESKTOP_DIR/$filename"

        if [ -f "$existing" ]; then
            if ! diff -q "$generated" "$existing" > /dev/null 2>&1; then
                echo ""
                echo "DIFFERS: $filename"
                diff -u "$existing" "$generated" || true
                differences=$((differences + 1))
            fi
        else
            echo "NEW (not in existing): $filename"
            missing_in_existing=$((missing_in_existing + 1))
        fi
    done

    # Check for existing files not generated from manifests
    for existing in "$DESKTOP_DIR"/*.desktop; do
        [ -f "$existing" ] || continue
        local filename
        filename=$(basename "$existing")
        local generated="$temp_dir/$filename"

        if [ ! -f "$generated" ]; then
            echo "EXTRA (not from manifest): $filename"
            missing_in_generated=$((missing_in_generated + 1))
        fi
    done

    echo ""
    echo "Summary:"
    echo "  Files that differ: $differences"
    echo "  New from manifest: $missing_in_existing"
    echo "  Extra (not from manifest): $missing_in_generated"
}

# Update desktop-bookmarks directory with generated files
update_desktop_files() {
    local backup_dir="$DESKTOP_DIR.backup.$(date +%Y%m%d_%H%M%S)"

    echo "Creating backup in $backup_dir..."
    cp -r "$DESKTOP_DIR" "$backup_dir"

    echo "Generating desktop files..."
    generate_all "$DESKTOP_DIR"

    echo ""
    echo "Desktop files updated. Backup saved to: $backup_dir"
}

# Show help
show_help() {
    cat << 'EOF'
RasQberry Desktop File Generator

Generates .desktop files from demo manifest files.

Usage:
  rq_demo_generate_desktop.sh [command]

Commands:
  (no args)     Print generated desktop entries to stdout (dry run)
  --output DIR  Generate desktop files to specified directory
  --diff        Compare generated files with existing desktop-bookmarks/
  --update      Update desktop-bookmarks/ with generated files (creates backup)
  --help, -h    Show this help

Examples:
  # Preview what would be generated
  rq_demo_generate_desktop.sh

  # Generate to a temp directory for review
  rq_demo_generate_desktop.sh --output /tmp/desktop-test

  # See differences between manifests and existing files
  rq_demo_generate_desktop.sh --diff

  # Update desktop-bookmarks/ (creates timestamped backup)
  rq_demo_generate_desktop.sh --update

Notes:
  - Only manifests with desktop.show=true are processed
  - Manifests without entrypoint.launcher are skipped
  - Existing desktop files not generated from manifests are preserved

EOF
}

# Main
main() {
    check_jq

    case "${1:-}" in
        --output)
            if [ -z "${2:-}" ]; then
                echo "Error: Output directory required" >&2
                exit 1
            fi
            mkdir -p "$2"
            generate_all "$2"
            ;;
        --diff)
            diff_desktop_files
            ;;
        --update)
            update_desktop_files
            ;;
        --help|-h)
            show_help
            ;;
        "")
            generate_all
            ;;
        *)
            echo "Unknown command: $1" >&2
            show_help
            exit 1
            ;;
    esac
}

main "$@"
