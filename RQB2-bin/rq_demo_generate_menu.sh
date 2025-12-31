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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST_DIR="$REPO_DIR/RQB2-config/demo-manifests"

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
