#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ============================================================================
# RasQberry: Desktop entry for a catalog (external) demo
# ============================================================================
# Description: Write a .desktop file for one demo manifest so an externally
#   added demo gets a desktop icon like the shipped ones (issue #287).
#   Everything dispatches through the universal launcher rq_demo_run.sh <id>.
#   Shipped demos keep their hand-maintained icons in desktop-bookmarks/; this
#   is only for manifests that arrive at runtime via rq_demo_add_external.sh.
# Usage: rq_demo_desktop_entry.sh <manifest.json> <output.desktop> [demo-dir]
#   demo-dir resolves a relative icon.path for icon.type "custom".
# Exit: 0 written, 3 skipped because desktop.show is false, 1 on error.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/rq_common.sh"

[ $# -ge 2 ] || die "Usage: $(basename "$0") <manifest.json> <output.desktop> [demo-dir]"
MANIFEST="$1"
OUTPUT="$2"
DEMO_DIR="${3:-}"

[ -f "$MANIFEST" ] || die "Manifest not found: $MANIFEST"
command -v jq >/dev/null 2>&1 || die "jq is required"

# jq's // treats false as absent, so test the boolean explicitly
show=$(jq -r 'if .desktop.show == false then "false" else "true" end' "$MANIFEST")
if [ "$show" != "true" ]; then
    info "desktop.show is false for $(jq -r '.id' "$MANIFEST") - no desktop entry"
    exit 3
fi

id=$(jq -r '.id // empty' "$MANIFEST")
name=$(jq -r '.name // empty' "$MANIFEST")
[ -n "$id" ] && [ -n "$name" ] || die "Manifest needs id and name: $MANIFEST"
description=$(jq -r '.description // ""' "$MANIFEST")
terminal=$(jq -r 'if .desktop.terminal == false then "false" else "true" end' "$MANIFEST")
keywords=$(jq -r '(.keywords // []) | join(";")' "$MANIFEST")
icon_type=$(jq -r '.icon.type // "system"' "$MANIFEST")
icon_path=$(jq -r '.icon.path // "applications-science"' "$MANIFEST")

# A custom icon is a file inside the demo checkout; a system icon is a theme
# name. The external validator does not cover icon.path, so keep custom paths
# relative and inside the checkout here: anything absolute or containing ".."
# falls back to a theme icon rather than pointing outside the demo directory.
icon="$icon_path"
if [ "$icon_type" = "custom" ]; then
    case "/$icon_path/" in
        //*|*/../*)
            warn "icon.path '$icon_path' must be relative to the demo directory - using a system icon"
            icon="applications-science" ;;
        *)
            [ -n "$DEMO_DIR" ] && icon="$DEMO_DIR/$icon_path" ;;
    esac
fi

mkdir -p "$(dirname "$OUTPUT")"
cat > "$OUTPUT" << EOF
[Desktop Entry]
Version=1.1
Name=$name
Comment=$description
Icon=$icon
Type=Application
Categories=RasQberry;
Exec=/usr/bin/rq_demo_run.sh $id
Terminal=$terminal
StartupNotify=true
Keywords=${keywords:+$keywords;}
TryExec=/usr/bin/rq_demo_run.sh
NoDisplay=false
X-RasQberry-External=true
EOF
chmod 755 "$OUTPUT"
info "Desktop entry written: $OUTPUT"
