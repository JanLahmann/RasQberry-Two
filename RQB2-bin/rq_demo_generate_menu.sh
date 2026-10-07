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
. "${SCRIPT_DIR}/rq_common.sh"

# Soft-load the environment so USER_HOME resolves for the user manifest dir.
# Degrades silently in dev/CI where the installed config is absent -> the
# manifest search path falls back to the shipped directory only.
if [ -f "$RQ_CONFIG_FILE" ]; then
    load_rqb2_env
fi

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

# Check whether the universal launcher (rq_demo_run.sh) can dispatch this
# manifest without a variant argument: it needs a concrete entrypoint type,
# a launcher, or a browser_url. Demos that only define variants (e.g.
# led-demos) are launched via their own submenu, not the generic dispatch.
is_dispatchable() {
    local file="$1"
    local etype launcher browser_url
    etype=$(jq -r '.entrypoint.type // ""' "$file")
    launcher=$(jq -r '.entrypoint.launcher // ""' "$file")
    browser_url=$(jq -r '.entrypoint.browser_url // ""' "$file")

    case "$etype" in
        jupyter|docker|python|browser|web-static) return 0 ;;
    esac
    [ -n "$launcher" ] || [ -n "$browser_url" ]
}

# Demo ids go into the cache as shell code (menu tags and case patterns) that
# raspi-config sources, so only the ids the manifest schema allows
# (^[a-z0-9-]+$, not starting with "-") get in. A user manifest whose id held a
# quote produced a cache dash could not parse, and that took all of
# raspi-config down with it, at every boot (R-120).
valid_cache_id() {
    case "$1" in
        [a-z0-9]*) ;;
        *) echo "Skipping $2: id '$1' must start with a-z or 0-9" >&2; return 1 ;;
    esac
    case "$1" in
        *[!a-z0-9-]*) echo "Skipping $2: id '$1' may contain only a-z, 0-9 and -" >&2; return 1 ;;
    esac
    return 0
}

# Text for the cache: the menu eval's the items inside double quotes, so
# \ " $ ` are escaped (a name stays text and never runs), and the lists are
# single-quoted, so ' is closed, escaped and reopened.
cache_text() {
    printf '%s' "$1" | sed 's/[\\"$`]/\\&/g' | sed "s/'/'\\\\''/g"
}

# What a demo needs, as short tags for its menu entry ("internet, 32 GB"):
# the LED panel (outside the LED panel group, where all need it), internet,
# an IBM Quantum account, a Docker demo's 32 GB SD card.
# Usage: demo_needs MANIFEST GROUP
demo_needs() {
    jq -r --arg g "$2" '[
        (if .needs_hw.leds == true and $g != "led-panel" then "LED panel" else empty end),
        (if .needs_hw.network == true then "internet" else empty end),
        (if .needs_ibm_token == "required" then "IBM account" else empty end),
        (if .entrypoint.type == "docker" or (.install.docker_image_of // "") != ""
         then "32 GB" else empty end)
    ] | join(", ")' "$1" 2>/dev/null
}

# The groups (demo-groups.json next to the shipped manifests), in order:
# id <TAB> title <TAB> menu line
GROUPS_FILE="$MANIFEST_DIR/demo-groups.json"
list_groups() {
    [ -f "$GROUPS_FILE" ] || return 0
    jq -r '.groups[]? | [.id, .title, (.menu // "")] | @tsv' "$GROUPS_FILE" 2>/dev/null
}

# Get all manifests sorted by menu order.
# Reads across the manifest search path (shipped + user), shipped wins on id.
get_sorted_manifests() {
    rq_list_manifests "$MANIFEST_DIR" | \
    while IFS= read -r file; do
        [ -z "$file" ] && continue
        local order
        order=$(jq -r '.menu.order // 50' "$file" 2>/dev/null)
        local show
        # not `.menu.show // true`: jq's // treats false as missing
        show=$(jq -r 'if .menu.show == false then "false" else "true" end' "$file" 2>/dev/null)
        if [ "$show" = "true" ]; then
            echo "$order $file"
        fi
    done | sort -n | cut -d' ' -f2-
}

# List all demos in a table
list_demos() {
    echo "ID                        | Name                      | Group          | Order"
    echo "--------------------------|---------------------------|----------------|------"

    get_sorted_manifests | while read -r file; do
        local id name group order
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")
        group=$(rq_demo_group "$id" "$file")
        order=$(jq -r '.menu.order // 50' "$file")

        printf "%-25s | %-25s | %-14s | %s\n" "$id" "$name" "$group" "$order"
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

    # Build the cache in a temp file and rename it into place at the end.
    # Generating takes tens of seconds, and raspi-config sources this file:
    # read half-written at boot, it aborted with a syntax error before
    # running anything - which is why VNC stayed off on fresh slots (#288).
    local final_file="$cache_file"
    cache_file=$(mktemp "$cache_dir/.demo-menu-cache.XXXXXX") || {
        echo "Error: Cannot write to $cache_dir" >&2
        return 1
    }

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
        local id name
        id=$(jq -r '.id' "$file")
        name=$(jq -r '.name' "$file")

        # Skip demos the universal launcher cannot dispatch directly
        is_dispatchable "$file" || continue
        # ... and ids that would break the cache (see valid_cache_id)
        valid_cache_id "$id" "$file" || continue
        # New or less-tested demos carry a tag (item 36)
        [ -n "$(rq_demo_maturity "$id" "$file")" ] && name="$name (beta)"

        # The menu eval's these pairs inside double quotes: escape what is
        # special there (\ " $ `), so a name is text and never runs.
        name=$(printf '%s' "$name" | sed 's/[\\"$`]/\\&/g')
        # Escape single quotes in name (DEMO_MENU_ITEMS is single-quoted)
        name=$(printf '%s' "$name" | sed "s/'/'\\\\''/g")

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
        local id
        id=$(jq -r '.id' "$file")

        is_dispatchable "$file" || continue
        valid_cache_id "$id" "$file" 2>/dev/null || continue

        # All demos go through the universal launcher, which handles type
        # dispatch, auto-install, and privilege handling (browser as user,
        # LED scripts as root)
        echo "        \"$id\") /usr/bin/rq_demo_run.sh \"$id\" ;;" >> "$cache_file"
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
        local id
        id=$(jq -r '.id' "$file")

        is_dispatchable "$file" || continue
        valid_cache_id "$id" "$file" 2>/dev/null || continue

        echo "        \"$id\") echo \"/usr/bin/rq_demo_run.sh $id\" ;;" >> "$cache_file"
    done) || true

    echo "        *) return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # Demos whose manifest sets menu.variant_menu open a submenu of their
    # variants: "tag" "name" pairs, one per line, escaped like DEMO_MENU_ITEMS
    # because the menu eval's them the same way.
    echo "# Variant submenu items (menu.variant_menu)" >> "$cache_file"
    echo "# Usage: demo_variant_items <demo-id>" >> "$cache_file"
    echo "demo_variant_items() {" >> "$cache_file"
    echo "    case \"\$1\" in" >> "$cache_file"

    (get_sorted_manifests | while read -r file; do
        [ -z "$file" ] && continue
        local id items vid vname
        [ "$(jq -r '.menu.variant_menu // false' "$file")" = "true" ] || continue
        id=$(jq -r '.id' "$file")
        is_dispatchable "$file" || continue
        valid_cache_id "$id" "$file" 2>/dev/null || continue
        items=""
        while IFS=$'\t' read -r vid vname vmaturity; do
            valid_cache_id "$vid" "$file (variant)" || continue
            [ "$vmaturity" = "beta" ] && vname="$vname (beta)"
            vname=$(printf '%s' "$vname" | sed 's/[\\"$`]/\\&/g')
            vname=$(printf '%s' "$vname" | sed "s/'/'\\\\''/g")
            items="$items '\"$vid\" \"$vname\"'"
        done < <(jq -r '.variants[]? | [.id, .name, (.maturity // "")] | @tsv' "$file")
        [ -n "$items" ] && echo "        \"$id\") printf '%s\\n'$items ;;" >> "$cache_file"
    done) || true

    echo "        *) return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # Demo groups (demo-groups.json): the Quantum Demos menu shows one submenu
    # per group, in this order; demo_group_items lists a group's demos
    # ("tag" "name [needs]" pairs, by menu.order), escaped like DEMO_MENU_ITEMS.
    # A demo's group: rq_demo_group (known-demos.json, manifest, guess).
    echo "# Demo groups: \"id\" \"Title: what is in it\" pairs, in menu order" >> "$cache_file"
    echo "demo_group_list() {" >> "$cache_file"
    local gid gtitle gmenu glist="" gitems
    while IFS=$'\t' read -r gid gtitle gmenu; do
        valid_cache_id "$gid" "$GROUPS_FILE (group)" || continue
        glist="$glist '\"$gid\" \"$(cache_text "$gtitle${gmenu:+: $gmenu}")\"'"
    done < <(list_groups)
    if [ -n "$glist" ]; then
        echo "    printf '%s\\n'$glist" >> "$cache_file"
    else
        echo "    return 1" >> "$cache_file"
    fi
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    echo "# Title of a group (submenu and folder name)" >> "$cache_file"
    echo "demo_group_title() {" >> "$cache_file"
    echo "    case \"\$1\" in" >> "$cache_file"
    while IFS=$'\t' read -r gid gtitle gmenu; do
        valid_cache_id "$gid" "$GROUPS_FILE (group)" 2>/dev/null || continue
        echo "        \"$gid\") printf '%s\\n' '$(printf '%s' "$gtitle" | sed "s/'/'\\\\''/g")' ;;" >> "$cache_file"
    done < <(list_groups)
    echo "        *) return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # One pass over the manifests: group <TAB> id <TAB> menu text
    local grouped
    grouped=$( (get_sorted_manifests | while read -r file; do
        [ -z "$file" ] && continue
        local id name g needs
        id=$(jq -r '.id' "$file")
        is_dispatchable "$file" || continue
        valid_cache_id "$id" "$file" 2>/dev/null || continue
        name=$(jq -r '.name' "$file")
        [ -n "$(rq_demo_maturity "$id" "$file")" ] && name="$name (beta)"
        g=$(rq_demo_group "$id" "$file")
        needs=$(demo_needs "$file" "$g")
        [ -n "$needs" ] && name="$name [$needs]"
        printf '%s\t%s\t%s\n' "$g" "$id" "$(printf '%s' "$name" | tr '\t' ' ')"
    done) || true)

    echo "# A group's demos (\"tag\" \"name [needs]\" pairs)" >> "$cache_file"
    echo "# Usage: demo_group_items <group-id>" >> "$cache_file"
    echo "demo_group_items() {" >> "$cache_file"
    echo "    case \"\$1\" in" >> "$cache_file"
    while IFS=$'\t' read -r gid gtitle gmenu; do
        valid_cache_id "$gid" "$GROUPS_FILE (group)" 2>/dev/null || continue
        gitems=""
        while IFS=$'\t' read -r g id name; do
            [ "$g" = "$gid" ] || continue
            gitems="$gitems '\"$id\" \"$(cache_text "$name")\"'"
        done <<< "$grouped"
        [ -n "$gitems" ] && echo "        \"$gid\") printf '%s\\n'$gitems ;;" >> "$cache_file"
    done < <(list_groups)
    echo "        *) return 1 ;;" >> "$cache_file"
    echo "    esac" >> "$cache_file"
    echo "}" >> "$cache_file"
    echo "" >> "$cache_file"

    # Generate demo count by counting dispatch entries. Match ONLY the
    # dispatch_demo_by_id case lines (they run the launcher directly:
    # `"id") /usr/bin/rq_demo_run.sh ...`); the get_demo_launcher block has the
    # same indentation (`"id") echo ...`) and would otherwise double the count.
    local count
    count=$(grep -c '^        "[a-z0-9][a-z0-9-]*") /usr/bin/rq_demo_run' "$cache_file" 2>/dev/null) || count=0

    echo "" >> "$cache_file"
    echo "# Total demos: $count" >> "$cache_file"
    echo "DEMO_COUNT=$count" >> "$cache_file"

    chmod 644 "$cache_file"
    mv -f "$cache_file" "$final_file"
    echo "Cache written to: $final_file" >&2
    echo "$final_file"
}

# Get demo info by ID
get_demo_info() {
    local demo_id="$1"
    local manifest
    manifest=$(rq_find_manifest "$MANIFEST_DIR" "$demo_id") || {
        echo "Error: Demo '$demo_id' not found" >&2
        return 1
    }

    jq '.' "$manifest"
}

# Get specific field from demo manifest
get_demo_field() {
    local demo_id="$1"
    local field="$2"
    local manifest
    manifest=$(rq_find_manifest "$MANIFEST_DIR" "$demo_id") || {
        echo "Error: Demo '$demo_id' not found" >&2
        return 1
    }

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
  - demo_group_list(), demo_group_title(), demo_group_items(): the demo
    groups (demo-groups.json) and each group's demos, for the submenus
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
