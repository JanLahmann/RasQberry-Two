#!/bin/bash
# ============================================================================
# RasQberry: Import Browser Bookmarks from Bootfs
# ============================================================================
# Description: Imports bookmarks from /boot/firmware/rasqberry_bookmarks.txt
#              into Chromium's bookmark bar on first desktop login.
#
# File Format (rasqberry_bookmarks.txt):
#   # Comments start with #
#   Name | URL
#   IBM Quantum | https://quantum.ibm.com
#
# Usage: Called automatically via autostart on desktop login
# ============================================================================

set -euo pipefail

# Configuration
BOOKMARKS_SOURCE="/boot/firmware/rasqberry_bookmarks.txt"
CHROMIUM_DIR="$HOME/.config/chromium/Default"
BOOKMARKS_FILE="$CHROMIUM_DIR/Bookmarks"
MARKER_FILE="/var/lib/rasqberry/bookmarks-imported.done"
LOG_FILE="$HOME/.rasqberry-bookmarks-import.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $*" >> "$LOG_FILE"
}

error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): ERROR: $*" >> "$LOG_FILE"
}

# Check if already imported
if [ -f "$MARKER_FILE" ]; then
    exit 0
fi

log "Starting bookmark import check"

# Check if source file exists on bootfs
if [ ! -f "$BOOKMARKS_SOURCE" ]; then
    log "No bookmarks file found at $BOOKMARKS_SOURCE - nothing to import"
    exit 0
fi

log "Found bookmarks file: $BOOKMARKS_SOURCE"

# Ensure Chromium profile directory exists
# If not, launch Chromium briefly to create it
if [ ! -d "$CHROMIUM_DIR" ]; then
    log "Chromium profile not found, launching Chromium to create profile..."

    # Launch Chromium in background, wait briefly, then close it
    chromium-browser --no-first-run --disable-sync about:blank &
    CHROMIUM_PID=$!
    sleep 3
    kill $CHROMIUM_PID 2>/dev/null || true
    sleep 1

    # Check again
    if [ ! -d "$CHROMIUM_DIR" ]; then
        error "Failed to create Chromium profile directory"
        exit 1
    fi
    log "Chromium profile created"
fi

# Parse bookmarks from TXT file and generate JSON
parse_bookmarks() {
    local source_file="$1"
    local bookmark_entries=""
    local id=1

    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue

        # Parse "Name | URL" format
        if [[ "$line" =~ \| ]]; then
            name=$(echo "$line" | cut -d'|' -f1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            url=$(echo "$line" | cut -d'|' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            # Validate URL (basic check)
            if [[ "$url" =~ ^https?:// ]]; then
                # Escape special characters for JSON
                name=$(echo "$name" | sed 's/\\/\\\\/g; s/"/\\"/g')
                url=$(echo "$url" | sed 's/\\/\\\\/g; s/"/\\"/g')

                # Add comma separator if not first entry
                if [ -n "$bookmark_entries" ]; then
                    bookmark_entries="$bookmark_entries,"
                fi

                bookmark_entries="$bookmark_entries
         {
            \"date_added\": \"$(date +%s)000000\",
            \"date_last_used\": \"0\",
            \"guid\": \"$(cat /proc/sys/kernel/random/uuid)\",
            \"id\": \"$id\",
            \"name\": \"$name\",
            \"type\": \"url\",
            \"url\": \"$url\"
         }"
                ((id++))
                log "Parsed bookmark: $name -> $url"
            else
                log "Skipping invalid URL: $url"
            fi
        fi
    done < "$source_file"

    echo "$bookmark_entries"
}

# Create or merge bookmarks
import_bookmarks() {
    local new_bookmarks
    new_bookmarks=$(parse_bookmarks "$BOOKMARKS_SOURCE")

    if [ -z "$new_bookmarks" ]; then
        log "No valid bookmarks found in source file"
        return 1
    fi

    # Check if Bookmarks file exists
    if [ -f "$BOOKMARKS_FILE" ]; then
        log "Merging with existing bookmarks"

        # Use Python for reliable JSON manipulation
        python3 << PYEOF
import json
import sys

bookmarks_file = "$BOOKMARKS_FILE"
new_entries_json = '''[$new_bookmarks
]'''

try:
    # Load existing bookmarks
    with open(bookmarks_file, 'r') as f:
        bookmarks = json.load(f)

    # Parse new entries
    new_entries = json.loads(new_entries_json)

    # Find highest existing ID
    def find_max_id(node):
        max_id = 0
        if isinstance(node, dict):
            if 'id' in node:
                try:
                    max_id = max(max_id, int(node['id']))
                except:
                    pass
            if 'children' in node:
                for child in node['children']:
                    max_id = max(max_id, find_max_id(child))
        return max_id

    max_id = find_max_id(bookmarks)

    # Update IDs for new entries
    for entry in new_entries:
        max_id += 1
        entry['id'] = str(max_id)

    # Get bookmark bar
    bookmark_bar = bookmarks.get('roots', {}).get('bookmark_bar', {})
    if 'children' not in bookmark_bar:
        bookmark_bar['children'] = []

    # Check for duplicates by URL
    existing_urls = set()
    for child in bookmark_bar.get('children', []):
        if 'url' in child:
            existing_urls.add(child['url'])

    # Add new bookmarks (skip duplicates)
    added = 0
    for entry in new_entries:
        if entry.get('url') not in existing_urls:
            bookmark_bar['children'].append(entry)
            existing_urls.add(entry['url'])
            added += 1

    # Save updated bookmarks
    with open(bookmarks_file, 'w') as f:
        json.dump(bookmarks, f, indent=3)

    print(f"Added {added} new bookmarks")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
    else
        log "Creating new bookmarks file"

        # Create new Bookmarks file with proper structure
        cat > "$BOOKMARKS_FILE" << JSONEOF
{
   "checksum": "",
   "roots": {
      "bookmark_bar": {
         "children": [$new_bookmarks
         ],
         "date_added": "$(date +%s)000000",
         "date_last_used": "0",
         "date_modified": "$(date +%s)000000",
         "guid": "$(cat /proc/sys/kernel/random/uuid)",
         "id": "1",
         "name": "Bookmarks bar",
         "type": "folder"
      },
      "other": {
         "children": [  ],
         "date_added": "$(date +%s)000000",
         "date_last_used": "0",
         "date_modified": "0",
         "guid": "$(cat /proc/sys/kernel/random/uuid)",
         "id": "2",
         "name": "Other bookmarks",
         "type": "folder"
      },
      "synced": {
         "children": [  ],
         "date_added": "$(date +%s)000000",
         "date_last_used": "0",
         "date_modified": "0",
         "guid": "$(cat /proc/sys/kernel/random/uuid)",
         "id": "3",
         "name": "Mobile bookmarks",
         "type": "folder"
      }
   },
   "version": 1
}
JSONEOF
    fi

    return 0
}

# Main execution
log "Beginning bookmark import"

if import_bookmarks; then
    log "Bookmark import successful"

    # Create marker file (requires sudo for /var/lib)
    sudo mkdir -p /var/lib/rasqberry
    sudo touch "$MARKER_FILE"
    sudo chmod 644 "$MARKER_FILE"

    # Archive the source file (move to user's home)
    mkdir -p "$HOME/.rasqberry"
    cp "$BOOKMARKS_SOURCE" "$HOME/.rasqberry/imported_bookmarks.txt"
    sudo rm -f "$BOOKMARKS_SOURCE"
    log "Source file archived to $HOME/.rasqberry/imported_bookmarks.txt"

    log "Bookmark import completed successfully"
else
    error "Bookmark import failed"
    exit 1
fi
