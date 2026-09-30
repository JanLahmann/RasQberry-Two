#!/bin/bash
#
# rq_demo_generate_desktop.sh - Scaffold .desktop files from demo manifests
#
# This is a DEVELOPMENT tool. It is not run at build time, and it is NOT a sync
# tool: RQB2-config/desktop-bookmarks/ is the deployed source of truth and is
# maintained by hand. Use this to draft the icon for a NEW demo, then edit and
# commit the result yourself.
#
# It cannot reproduce the committed icons, which is why it must not write over
# them (the --update mode that did was removed):
#   - it derives filenames from the demo name, so it would add a SECOND icon
#     beside an existing one (grokking-the-bloch-sphere.desktop vs grok-bloch.desktop)
#   - it cannot express the terminal wrappers some icons need (qoffee-maker tees
#     its output to a log and waits for Enter, so a failed Docker build is
#     readable rather than a window that vanishes)
#   - it cannot express variants (fun-with-quantum readme vs coin-game)
#   - it does not know about icons that have no manifest (clear-leds, demo-loop,
#     touch-mode, ...)
#
# Use --diff to see how the committed icons differ from what the manifests imply.
# Differences are expected: treat it as a prompt to think, not a defect list.
#
# Usage:
#   rq_demo_generate_desktop.sh              # Generate to stdout (dry run)
#   rq_demo_generate_desktop.sh --output DIR # Generate to a scratch directory
#   rq_demo_generate_desktop.sh --diff       # Compare generated with committed
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
    local id name description keywords_json icon_type icon_path launcher browser_url script terminal

    id=$(jq -r '.id' "$file")
    name=$(jq -r '.name' "$file")
    description=$(jq -r '.description // ""' "$file")
    keywords_json=$(jq -c '.keywords // []' "$file")
    icon_type=$(jq -r '.icon.type // "system"' "$file")
    icon_path=$(jq -r '.icon.path // "applications-other"' "$file")
    launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
    browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")
    script=$(jq -r '.entrypoint.script // ""' "$file")
    terminal=$(jq -r '.desktop.terminal // true' "$file")

    # Skip only if there is no way to launch: no launcher, no browser_url, and
    # no runnable script. Demos with an entrypoint.script (and no dedicated
    # launcher) dispatch through the universal launcher rq_demo_run.sh below.
    if [ -z "$launcher" ] && [ -z "$browser_url" ] && [ -z "$script" ]; then
        echo "# Skipped $id: no launcher, browser_url, or script defined" >&2
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

    # Build Exec command.
    #
    # Everything with a manifest dispatches through the universal launcher
    # rq_demo_run.sh <id>: it installs-if-missing (at the manifest's pinned SHA),
    # then delegates to the demo's launcher if it declares one. Pointing an icon
    # straight at a launcher instead is what let the desktop bypass this engine -
    # such icons installed via their own unpinned path, or not at all.
    #
    # A pure browser_url demo is the one exception: there is nothing to install
    # or delegate, so the icon just opens the URL.
    local exec_cmd tryexec
    if [ -n "$browser_url" ] && [ -z "$launcher" ] && [ -z "$script" ]; then
        exec_cmd="chromium-browser --password-store=basic $browser_url"
        tryexec="chromium-browser"
    else
        exec_cmd="/usr/bin/rq_demo_run.sh $id"
        tryexec="/usr/bin/rq_demo_run.sh"
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

# Show help
show_help() {
    cat << 'EOF'
RasQberry Desktop File Scaffolder

Drafts .desktop files from demo manifests. DEVELOPMENT TOOL - not run at build.

RQB2-config/desktop-bookmarks/ is the deployed source of truth and is edited by
hand. This tool does not write there: it cannot reproduce those icons (it derives
its own filenames, and cannot express terminal wrappers, variants, or icons that
have no manifest). Use it to draft an icon for a NEW demo, then edit and commit.

Usage:
  rq_demo_generate_desktop.sh [command]

Commands:
  (no args)     Print generated desktop entries to stdout (dry run)
  --output DIR  Write drafts to a scratch directory for review
  --diff        Show how committed icons differ from what the manifests imply
  --help, -h    Show this help

Examples:
  # Preview what the manifests imply
  rq_demo_generate_desktop.sh

  # Draft icons into a scratch dir, then copy what you want by hand
  rq_demo_generate_desktop.sh --output /tmp/desktop-test

  # Inspect drift (differences are EXPECTED - a prompt to think, not a bug list)
  rq_demo_generate_desktop.sh --diff

Notes:
  - Only manifests with desktop.show=true are processed
  - Everything with a manifest dispatches through rq_demo_run.sh <id>, so the
    icon installs-if-missing at the pinned SHA and then delegates to any launcher
  - Icons with no manifest (clear-leds, demo-loop, touch-mode, ...) are not
    produced here at all

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
            # Removed deliberately. This wrote generated files straight into the
            # committed desktop-bookmarks/, but it cannot reproduce them: it would
            # add duplicate icons under different filenames and drop the terminal
            # wrappers and variants the committed icons rely on. See the header.
            cat >&2 << 'EOF'
--update has been removed: it silently clobbered the committed icons.

RQB2-config/desktop-bookmarks/ is the source of truth and is edited by hand.
This tool only scaffolds an icon for a NEW demo:

  rq_demo_generate_desktop.sh --output /tmp/scaffold   # draft, then edit + commit
  rq_demo_generate_desktop.sh --diff                   # see how committed differs

EOF
            exit 1
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
