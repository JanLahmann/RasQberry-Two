#!/bin/bash
#
# rq_demo_generate_menu.sh - Generate menu entries from demo manifests
#
# Usage:
#   rq_demo_generate_menu.sh              # Print menu entries to stdout
#   rq_demo_generate_menu.sh --list       # List demos in table format
#   rq_demo_generate_menu.sh --whiptail   # Generate whiptail menu array
#
# Requires: jq
#

set -euo pipefail

# Find script directory and manifest directory
# When installed: /usr/bin → /usr/config/demo-manifests
# When in repo: RQB2-bin → RQB2-config/demo-manifests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$SCRIPT_DIR" = "/usr/bin" ]; then
    # Installed system: config is at /usr/config (see issue #246 for global vars)
    MANIFEST_DIR="/usr/config/demo-manifests"
else
    # Development: relative to repo structure
    REPO_DIR="$(dirname "$SCRIPT_DIR")"
    MANIFEST_DIR="$REPO_DIR/RQB2-config/demo-manifests"
fi

# Check if jq is available
check_jq() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed." >&2
        echo "Install with: sudo apt-get install jq" >&2
        exit 1
    fi
}

# Get all manifests sorted by menu order
get_sorted_manifests() {
    find "$MANIFEST_DIR" -name 'rq_demo_*.json' -not -name '*schema*' -print0 2>/dev/null | \
    while IFS= read -r -d '' file; do
        local order
        order=$(jq -r '.menu.order // 50' "$file" 2>/dev/null)
        local show
        show=$(jq -r '.menu.show // true' "$file" 2>/dev/null)
        if [ "$show" = "true" ]; then
            echo "$order $file"
        fi
    done | sort -n | cut -d' ' -f2-
}

# List all demos in a table
list_demos() {
    echo "ID                        | Name                      | Category       | Order"
    echo "--------------------------|---------------------------|----------------|------"

    get_sorted_manifests | while read -r file; do
        local id name category order
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")
        category=$(jq -r '.category' "$file")
        order=$(jq -r '.menu.order // 50' "$file")

        printf "%-25s | %-25s | %-14s | %s\n" "$id" "$name" "$category" "$order"
    done
}

# Generate whiptail menu array format
# Output: "tag" "description" pairs
generate_whiptail_menu() {
    get_sorted_manifests | while read -r file; do
        local id name description
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")
        description=$(jq -r '.description' "$file" | cut -c1-60)

        # Output as whiptail expects: "tag" "description"
        echo "\"$id\" \"$name: $description\""
    done
}

# Generate shell function for each demo launcher
generate_launcher_functions() {
    echo "# Auto-generated demo launcher functions from manifests"
    echo "# Generated: $(date -Iseconds)"
    echo ""

    get_sorted_manifests | while read -r file; do
        local id name launcher entrypoint_type
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")
        launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
        entrypoint_type=$(jq -r '.entrypoint.type' "$file")

        # Create function name from ID (replace hyphens with underscores)
        local func_name
        func_name="run_$(echo "$id" | tr '-' '_')_demo"

        echo "# $name"
        echo "$func_name() {"
        if [ -n "$launcher" ]; then
            echo "    /usr/bin/$launcher"
        else
            echo "    echo \"No launcher defined for $id\""
        fi
        echo "}"
        echo ""
    done
}

# Generate menu items for RQB2_menu.sh
generate_menu_items() {
    echo "# Auto-generated menu items from manifests"
    echo "# Add these to the quantum demo menu array in RQB2_menu.sh"
    echo ""
    echo "# Format for whiptail menu: \"tag\" \"description\""
    echo "DEMO_MENU_ITEMS=("

    get_sorted_manifests | while read -r file; do
        local id name
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")

        echo "    \"$id\" \"$name\""
    done

    echo ")"
}

# Generate cache file for menu integration
# Output: A sourceable shell script with menu arrays and dispatch function
generate_cache() {
    # Default to /usr/config on installed system (TODO: use global var per issue #246)
    local cache_file="${1:-/usr/config/demo-menu-cache.sh}"
    local cache_dir
    cache_dir=$(dirname "$cache_file")

    # Create cache directory if needed
    if [ ! -d "$cache_dir" ]; then
        mkdir -p "$cache_dir" 2>/dev/null || {
            echo "Error: Cannot create cache directory $cache_dir" >&2
            return 1
        }
    fi

    cat > "$cache_file" << 'CACHE_HEADER'
#!/bin/sh
# Auto-generated demo menu cache from manifests
# DO NOT EDIT - regenerate with: rq_demo_generate_menu.sh --cache
#
CACHE_HEADER

    echo "# Generated: $(date -Iseconds)" >> "$cache_file"
    echo "# Manifest directory: $MANIFEST_DIR" >> "$cache_file"
    echo "" >> "$cache_file"

    # Generate menu items array (POSIX-compatible format for whiptail)
    echo "# Demo menu items for whiptail (tag description pairs)" >> "$cache_file"
    echo "# Usage: eval \"set -- \$DEMO_MENU_ITEMS\"; show_menu \"\$@\"" >> "$cache_file"
    echo "DEMO_MENU_ITEMS='" >> "$cache_file"

    # Use subshell to avoid pipefail issues with read at end of input
    (get_sorted_manifests | while read -r file; do
        [ -z "$file" ] && continue
        local id name launcher browser_url
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")
        launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
        browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")

        # Skip demos without launchers or browser_url
        [ -z "$launcher" ] && [ -z "$browser_url" ] && continue

        # Escape single quotes in name
        name=$(echo "$name" | sed "s/'/'\\\\''/g")

        echo "\"$id\" \"$name\"" >> "$cache_file"
    done) || true

    echo "'" >> "$cache_file"
    echo "" >> "$cache_file"

    # Generate dispatch function
    echo "# Dispatch function: run demo by ID" >> "$cache_file"
    echo "# Usage: dispatch_demo_by_id <demo-id>" >> "$cache_file"
    echo "dispatch_demo_by_id() {" >> "$cache_file"
    echo "    case \"\$1\" in" >> "$cache_file"

    (get_sorted_manifests | while read -r file; do
        [ -z "$file" ] && continue
        local id launcher browser_url
        id=$(jq -r '.id' "$file")
        launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
        browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")

        # Skip demos without launchers or browser_url
        [ -z "$launcher" ] && [ -z "$browser_url" ] && continue

        if [ -n "$launcher" ]; then
            echo "        \"$id\") /usr/bin/$launcher ;;" >> "$cache_file"
        elif [ -n "$browser_url" ]; then
            echo "        \"$id\") chromium-browser --password-store=basic $browser_url ;;" >> "$cache_file"
        fi
    done) || true

    echo "        *) echo \"Unknown demo: \$1\" >&2; return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # Generate launcher lookup function
    echo "# Get launcher script for demo ID" >> "$cache_file"
    echo "# Usage: get_demo_launcher <demo-id>" >> "$cache_file"
    echo "get_demo_launcher() {" >> "$cache_file"
    echo "    case \"\$1\" in" >> "$cache_file"

    (get_sorted_manifests | while read -r file; do
        [ -z "$file" ] && continue
        local id launcher browser_url
        id=$(jq -r '.id' "$file")
        launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
        browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")

        [ -z "$launcher" ] && [ -z "$browser_url" ] && continue

        if [ -n "$launcher" ]; then
            echo "        \"$id\") echo \"/usr/bin/$launcher\" ;;" >> "$cache_file"
        elif [ -n "$browser_url" ]; then
            echo "        \"$id\") echo \"chromium-browser --password-store=basic $browser_url\" ;;" >> "$cache_file"
        fi
    done) || true

    echo "        *) return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # Generate demo count by counting dispatch entries (launchers and browser entries)
    local count
    count=$(grep -c '^        "[a-z].*) ' "$cache_file" 2>/dev/null) || count=0

    echo "" >> "$cache_file"
    echo "# Total demos: $count" >> "$cache_file"
    echo "DEMO_COUNT=$count" >> "$cache_file"

    echo "Cache written to: $cache_file" >&2
    echo "$cache_file"
}

# Get demo info by ID
get_demo_info() {
    local demo_id="$1"
    local manifest="$MANIFEST_DIR/rq_demo_${demo_id}.json"

    if [ ! -f "$manifest" ]; then
        echo "Error: Demo '$demo_id' not found" >&2
        return 1
    fi

    jq '.' "$manifest"
}

# Get specific field from demo manifest
get_demo_field() {
    local demo_id="$1"
    local field="$2"
    local manifest="$MANIFEST_DIR/rq_demo_${demo_id}.json"

    if [ ! -f "$manifest" ]; then
        echo "Error: Demo '$demo_id' not found" >&2
        return 1
    fi

    jq -r ".$field // empty" "$manifest"
}

# Show help
show_help() {
    cat << 'EOF'
RasQberry Demo Menu Generator

Usage:
  rq_demo_generate_menu.sh [command] [options]

Commands:
  --list              List all demos in table format
  --whiptail          Generate whiptail menu array entries
  --functions         Generate shell launcher functions
  --menu-items        Generate menu items array for RQB2_menu.sh
  --cache [path]      Generate sourceable cache file (default: /usr/config/demo-menu-cache.sh)
  --info <id>         Show full manifest for a demo
  --field <id> <fld>  Get specific field from manifest
  --help, -h          Show this help

Examples:
  # List all demos
  rq_demo_generate_menu.sh --list

  # Get launcher for a demo
  rq_demo_generate_menu.sh --field quantum-lights-out entrypoint.launcher

  # Show full info for a demo
  rq_demo_generate_menu.sh --info grok-bloch

  # Generate menu cache for RQB2_menu.sh
  rq_demo_generate_menu.sh --cache

  # Generate cache to custom location
  rq_demo_generate_menu.sh --cache /tmp/demo-menu.sh

Cache File Usage:
  The cache file can be sourced by RQB2_menu.sh and provides:
  - DEMO_MENU_ITEMS: Menu entries for whiptail
  - dispatch_demo_by_id(): Function to run a demo by ID
  - get_demo_launcher(): Function to get launcher path for a demo ID
  - DEMO_COUNT: Total number of demos with launchers

EOF
}

# Main
main() {
    check_jq

    case "${1:-}" in
        --list)
            list_demos
            ;;
        --whiptail)
            generate_whiptail_menu
            ;;
        --functions)
            generate_launcher_functions
            ;;
        --menu-items)
            generate_menu_items
            ;;
        --cache)
            generate_cache "${2:-}"
            ;;
        --info)
            if [ -z "${2:-}" ]; then
                echo "Error: Demo ID required" >&2
                exit 1
            fi
            get_demo_info "$2"
            ;;
        --field)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                echo "Error: Demo ID and field required" >&2
                exit 1
            fi
            get_demo_field "$2" "$3"
            ;;
        --help|-h|"")
            show_help
            ;;
        *)
            echo "Unknown command: $1" >&2
            show_help
            exit 1
            ;;
    esac
}

main "$@"
