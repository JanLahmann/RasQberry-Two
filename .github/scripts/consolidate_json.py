#!/usr/bin/env python3
"""
Merge the RQB-images.json / RQB-releases.json release assets into the files
served from rasqberry.org (Raspberry Pi Imager list and /latest/ redirects).

Run by .github/workflows/consolidate-json.yaml. Moved out of the workflow
because the inline script exceeded GitHub's 21000-character expression limit.
"""
import json
import os
import re
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "JanLahmann/RasQberry-Two")

print("=== Merging RQB-images.json files into hierarchical structure ===")

# Fetch manual highlights from gh-pages
manual_highlights = {'stable': [], 'beta': []}
try:
    url = f"https://raw.githubusercontent.com/{REPO}/gh-pages/public/highlights.json"
    req = urllib.request.Request(url, headers={"User-Agent": "RasQberry-Workflow"})
    with urllib.request.urlopen(req, timeout=10) as response:
        manual_highlights = json.loads(response.read().decode())
        print(f"Loaded manual highlights: stable={len(manual_highlights.get('stable', []))}, beta={len(manual_highlights.get('beta', []))}")
except Exception as e:
    print(f"Could not fetch highlights.json: {e} - using empty highlights")

# Collect entries by category
main_std = []      # Main stable standard images (top-level)
beta_std = []      # Beta standard images (top-level)
dev_std = []       # Development branch images (top-level)
dev_all = []       # All dev-* branches (flat folder)
ab_all = []        # All A/B images (flat folder)

# Collect ALL releases for RQB-images-all.json
all_releases = []  # All releases from all branches

# Helper to extract timestamp from URL filename
# URL format: .../rasqberry-branch-YYYY-MM-DD-HHMMSS.img.xz
def extract_timestamp(url):
    if not url:
        return None
    filename = url.split('/')[-1].replace('.img.xz', '').replace('-ab', '')
    # Match YYYY-MM-DD-HHMMSS or YYYY-MM-DD at end of filename
    match = re.search(r'(\d{4}-\d{2}-\d{2}(?:-\d{6})?)$', filename)
    return match.group(1) if match else None

json_dir = Path("/tmp/release-json")

# First pass: group releases by branch and keep only the latest per branch
branch_releases = {}  # branch -> (published_date, tag, json_file)

for json_file in json_dir.glob("*.json"):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        branch = data.get('_branch', '')
        published = data.get('_published', '')
        tag = data.get('_release_tag', json_file.stem)

        if not branch:
            print(f"  ⚠ Skipping {json_file.name}: no branch metadata")
            continue

        # Keep only the latest release per branch
        if branch not in branch_releases or published > branch_releases[branch][0]:
            branch_releases[branch] = (published, tag, json_file)
            print(f"Found: {tag} (branch: {branch}, published: {published})")

    except Exception as e:
        print(f"  Error reading {json_file}: {e}")

print(f"\n=== Latest release per branch ===")
for branch, (published, tag, _) in sorted(branch_releases.items()):
    print(f"  {branch}: {tag}")

# Collect ALL releases for RQB-images-all.json (not just latest per branch)
print(f"\n=== Collecting ALL releases for RQB-images-all.json ===")
for json_file in sorted(json_dir.glob("*.json"), reverse=True):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        tag = data.get('_release_tag', json_file.stem)
        branch = data.get('_branch', '')
        published = data.get('_published', '')

        for entry in data.get('os_list', []):
            name = entry.get('name', '')
            if 'RasQberry' not in name:
                continue

            # Create entry with release metadata
            entry_with_meta = {k: v for k, v in entry.items()
                               if k not in ('_release_tag', '_branch', '_published')}
            entry_with_meta['_release_tag'] = tag
            entry_with_meta['_branch'] = branch
            entry_with_meta['_published'] = published
            all_releases.append(entry_with_meta)

    except Exception as e:
        print(f"  Error reading {json_file}: {e}")

print(f"  Collected {len(all_releases)} total release entries")

# Second pass: process only the latest release per branch
for branch_name, (published, tag, json_file) in branch_releases.items():
    print(f"\nProcessing: {tag} (branch: {branch_name})")

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        for entry in data.get('os_list', []):
            name = entry.get('name', '')
            image_type = entry.get('image_type', 'standard')
            url = entry.get('url', '')

            # Only include RasQberry entries
            if 'RasQberry' not in name:
                continue

            # Remove internal fields before adding to output
            entry_clean = {k: v for k, v in entry.items()
                           if k not in ('image_type', '_release_tag', '_branch', '_published')}

            # Classify by BRANCH NAME for proper categorization
            # Dev and AB images: include branch name AND full timestamp for Pi Imager
            if image_type == 'ab' or 'A/B' in name:
                # A/B images: include branch name + timestamp
                timestamp = extract_timestamp(entry.get('url', ''))
                if timestamp:
                    entry_clean['name'] = f"RasQberry Two A/B ({branch_name} {timestamp})"
                else:
                    entry_clean['name'] = f"RasQberry Two A/B ({branch_name})"
                entry_clean['description'] = f"A/B boot image from {branch_name}"
                ab_all.append((published, branch_name, entry_clean))
                print(f"  → A/B folder: {entry_clean['name']}")
            elif branch_name == 'development':
                # Development integration branch → top-level dev entry
                entry_clean['name'] = "RasQberry Two Dev (64-bit)"
                entry_clean['description'] = "Development integration branch with latest features"
                dev_std.append((published, branch_name, entry_clean))
                print(f"  → Top-level Dev: {entry_clean['name']}")
            elif branch_name.startswith('dev'):
                # Dev images: include branch name + timestamp
                timestamp = extract_timestamp(entry.get('url', ''))
                if timestamp:
                    entry_clean['name'] = f"RasQberry Two Dev ({branch_name} {timestamp})"
                else:
                    entry_clean['name'] = f"RasQberry Two Dev ({branch_name})"
                entry_clean['description'] = f"Development build from {branch_name}"
                dev_all.append((published, branch_name, entry_clean))
                print(f"  → Dev folder: {entry_clean['name']}")
            elif branch_name == 'beta':
                # Beta branch → top-level beta entry
                entry_clean['name'] = "RasQberry Two Beta (64-bit)"
                entry_clean['description'] = "Beta release with new features for testing"
                beta_std.append((published, branch_name, entry_clean))
                print(f"  → Top-level Beta: {entry_clean['name']}")
            elif branch_name == 'main':
                # Main branch: only stable if name doesn't contain "Dev"
                if 'Dev' in name:
                    # Main has dev image - put in dev folder
                    entry_clean['name'] = f"RasQberry Two Dev ({branch_name})"
                    entry_clean['description'] = f"Development build from {branch_name}"
                    dev_std.append((published, branch_name, entry_clean))
                    print(f"  → Dev folder (main has dev): {entry_clean['name']}")
                else:
                    # Main has stable release
                    entry_clean['name'] = "RasQberry Two (64-bit)"
                    entry_clean['description'] = "Stable release for Raspberry Pi 4/5 (Recommended)"
                    main_std.append((published, branch_name, entry_clean))
                    print(f"  → Top-level Main: {entry_clean['name']}")
            else:
                # Unknown branch pattern - treat as dev
                entry_clean['name'] = f"RasQberry Two ({branch_name})"
                dev_std.append((published, branch_name, entry_clean))
                print(f"  → Dev folder (unknown): {entry_clean['name']}")

    except Exception as e:
        print(f"  Error loading {json_file}: {e}")

# Sort each category by release_date (newest first)
main_std.sort(key=lambda x: x[0], reverse=True)
beta_std.sort(key=lambda x: x[0], reverse=True)
dev_std.sort(key=lambda x: x[0], reverse=True)
dev_all.sort(key=lambda x: x[0], reverse=True)
ab_all.sort(key=lambda x: x[0], reverse=True)

# Build hierarchical os_list
os_list = []

# 1. Add main stable images (top-level) - only latest
if main_std:
    os_list.append(main_std[0][2])
    print(f"\n✓ Added main stable: {main_std[0][2].get('name')}")

# 2. Add beta images (top-level) - only latest
if beta_std:
    os_list.append(beta_std[0][2])
    print(f"✓ Added beta: {beta_std[0][2].get('name')}")

# 3. Add development images (top-level) - only latest
if dev_std:
    os_list.append(dev_std[0][2])
    print(f"✓ Added development: {dev_std[0][2].get('name')}")

# 5. Add Development Images folder (flat list of all dev-* branches)
if dev_all:
    dev_folder = {
        "name": "RasQberry Development Images",
        "description": "Development builds with cutting-edge features (unstable)",
        "icon": "https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png",
        "subitems": [entry for _, _, entry in dev_all]
    }
    os_list.append(dev_folder)
    print(f"✓ Added Development folder with {len(dev_all)} images")

# 6. Add A/B Test Images folder (flat list of all A/B images)
if ab_all:
    ab_folder = {
        "name": "RasQberry A/B Boot Images",
        "description": "Images with A/B partition support for safer updates (experimental)",
        "icon": "https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png",
        "subitems": [entry for _, _, entry in ab_all]
    }
    os_list.append(ab_folder)
    print(f"✓ Added A/B folder with {len(ab_all)} images")

# Build final consolidated structure
consolidated = {
    "imager": {
        "latest_version": "1.8.5",
        "url": "https://www.raspberrypi.com/software/"
    },
    "os_list": os_list
}

print(f"\n=== Built hierarchical structure with {len(os_list)} top-level entries ===")

# Fetch official Raspberry Pi OS entry from their JSON
try:
    with open('/tmp/rpi-official.json', 'r') as f:
        rpi_data = json.load(f)

    # Navigate the structure to find Raspberry Pi OS (64-bit)
    # The official JSON has nested structure with os_list containing subitems
    def find_raspios_64bit(items):
        for item in items:
            name = item.get('name', '')
            # Look for the recommended 64-bit desktop version
            if 'Raspberry Pi OS' in name and '64-bit' in name and 'Lite' not in name and 'Full' not in name:
                # Check if it has direct download info or subitems
                if 'url' in item:
                    return item
                if 'subitems' in item:
                    # Look in subitems for the main desktop version
                    for sub in item['subitems']:
                        sub_name = sub.get('name', '')
                        if 'Desktop' in sub_name or ('64-bit' in sub_name and 'Lite' not in sub_name):
                            if 'url' in sub:
                                return sub
            # Recurse into subitems
            if 'subitems' in item:
                result = find_raspios_64bit(item['subitems'])
                if result:
                    return result
        return None

    raspios_entry = find_raspios_64bit(rpi_data.get('os_list', []))

    if raspios_entry:
        # Clean up the entry to match our schema
        clean_entry = {
            "name": raspios_entry.get('name', 'Raspberry Pi OS (64-bit)'),
            "description": raspios_entry.get('description', 'Official Raspberry Pi OS'),
            "icon": raspios_entry.get('icon', 'https://downloads.raspberrypi.com/raspios_armhf/Raspberry_Pi_OS_(32-bit).png'),
            "url": raspios_entry.get('url'),
            "extract_size": raspios_entry.get('extract_size'),
            "extract_sha256": raspios_entry.get('extract_sha256'),
            "image_download_size": raspios_entry.get('image_download_size'),
            "release_date": raspios_entry.get('release_date'),
            "init_format": raspios_entry.get('init_format', 'systemd'),
            "devices": raspios_entry.get('devices', ['pi5-64bit', 'pi4-64bit'])
        }
        # Remove None values
        clean_entry = {k: v for k, v in clean_entry.items() if v is not None}
        consolidated['os_list'].append(clean_entry)
        print(f"\n✓ Added official Raspberry Pi OS entry: {clean_entry.get('name')}")
        print(f"  Release date: {clean_entry.get('release_date')}")
    else:
        print("\n⚠ Could not find Raspberry Pi OS (64-bit) in official JSON")
        raise Exception("Fallback needed")

except Exception as e:
    print(f"\n⚠ Error fetching official Raspberry Pi OS: {e}")
    print("  Using fallback entry (may be outdated)")
    # Fallback to a known working entry
    consolidated['os_list'].append({
        "name": "Raspberry Pi OS (64-bit)",
        "description": "A port of Debian Bookworm with the Raspberry Pi Desktop (Recommended)",
        "icon": "https://downloads.raspberrypi.com/raspios_armhf/Raspberry_Pi_OS_(32-bit).png",
        "url": "https://downloads.raspberrypi.com/raspios_arm64/images/raspios_arm64-2024-10-28/2024-10-22-raspios-bookworm-arm64.img.xz",
        "extract_size": 6102712320,
        "extract_sha256": "88093218a66cf20e8669963902a949c4c23b73309c2fc3331d09fa6ee2134417",
        "image_download_size": 1238664180,
        "release_date": "2024-10-22",
        "init_format": "systemd",
        "devices": ["pi5-64bit", "pi4-64bit"]
    })

# Note: Pi Imager has built-in "Use custom" option, no need to add our own

# Write consolidated JSON to public folder (where website serves from)
with open('public/RQB-images.json', 'w') as f:
    json.dump(consolidated, f, indent=2)

print("\n=== Final RQB-images.json ===")
print(json.dumps(consolidated, indent=2))

# ================================================================
# Generate RQB-releases.json for website /latest/ redirects
# ================================================================

def extract_highlights_from_release(tag, repo):
    """Extract highlights from GitHub release body for dev releases."""
    highlights = []
    try:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RasQberry-Workflow"
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            release_data = json.loads(response.read().decode())
            body = release_data.get('body', '')

            # Extract bullet points from release body (lines starting with - or *)
            for line in body.split('\n'):
                line = line.strip()
                if line.startswith(('- ', '* ', '• ')):
                    highlight = re.sub(r'^[-*•]\s*', '', line).strip()
                    # Skip links-only, empty, or very short items
                    if highlight and len(highlight) > 10 and not highlight.startswith('http'):
                        highlights.append(highlight)
                        if len(highlights) >= 5:
                            break
        print(f"Extracted {len(highlights)} highlights from release {tag}")
    except Exception as e:
        print(f"Could not fetch release highlights for {tag}: {e}")
    return highlights

def build_stream_entry(entries, stream_type):
    """Build a stream entry from the first (newest) entry in the list."""
    if not entries:
        # No release available - return placeholder
        messages = {
            'stable': 'No stable release yet. Please use beta or dev.',
            'beta': 'No beta release yet. Please use dev.',
            'dev': 'No development release available.'
        }
        return {
            'tag': None,
            'name': None,
            'message': messages.get(stream_type, 'No release available.'),
            'release_url': f'https://github.com/{REPO}/releases'
        }

    # Get the newest entry (already sorted by date)
    _, branch_name, entry = entries[0]

    # Extract tag from release_url or url
    tag = None
    release_url = entry.get('release_url', '')
    if '/releases/tag/' in release_url:
        tag = release_url.split('/releases/tag/')[-1]
    elif '/releases/download/' in entry.get('url', ''):
        # Extract from download URL: .../releases/download/TAG/filename
        parts = entry.get('url', '').split('/releases/download/')
        if len(parts) > 1:
            tag = parts[1].split('/')[0]

    # Build the stream entry
    stream_entry = {
        'tag': tag,
        'name': entry.get('url', '').split('/')[-1].replace('.img.xz', '') if entry.get('url') else None,
        'image_url': entry.get('url'),
        'release_url': release_url or f"https://github.com/{REPO}/releases/tag/{tag}" if tag else f"https://github.com/{REPO}/releases",
        'release_date': entry.get('release_date'),
        'image_download_size': entry.get('image_download_size'),
    }

    # Add optional fields if present
    if entry.get('extract_size'):
        stream_entry['extract_size'] = entry.get('extract_size')
    if entry.get('extract_sha256'):
        stream_entry['extract_sha256'] = entry.get('extract_sha256')

    # The A/B image of the same release. rq_update_slot.sh verifies an
    # A/B-slot update against ab_extract_sha256; without these fields
    # every rebuild of this file silently dropped them again.
    if tag:
        for _, _, ab in ab_all:
            if f"/releases/download/{tag}/" in ab.get('url', ''):
                stream_entry['ab_image_url'] = ab.get('url')
                for src, dst in (('extract_sha256', 'ab_extract_sha256'),
                                 ('image_sha256', 'ab_image_sha256'),
                                 ('extract_size', 'ab_extract_size'),
                                 ('image_download_size', 'ab_image_download_size')):
                    if ab.get(src):
                        stream_entry[dst] = ab.get(src)
                break

    # Add highlights based on stream type
    if stream_type in ('stable', 'beta') and manual_highlights.get(stream_type):
        # Use manually curated highlights from highlights.json
        stream_entry['highlights'] = manual_highlights[stream_type]
    elif stream_type == 'dev' and tag:
        # Auto-extract from release body for dev releases
        highlights = extract_highlights_from_release(tag, REPO)
        stream_entry['highlights'] = highlights if highlights else ['Development build - see release notes for details']
    else:
        # Fallback
        stream_entry['highlights'] = []

    return stream_entry

# Build RQB-releases.json
# Use development branch for dev stream if available, otherwise fallback to dev-featuresXX
if dev_std:
    all_dev = dev_std  # Use the permanent development integration branch
else:
    # Fallback: use dev_all for the dev stream (newest overall)
    all_dev = dev_all
releases_json = {
    'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'streams': {
        'stable': build_stream_entry(main_std, 'stable'),
        'beta': build_stream_entry(beta_std, 'beta'),
        'dev': build_stream_entry(all_dev, 'dev'),
    }
}

# Write RQB-releases.json
with open('public/RQB-releases.json', 'w') as f:
    json.dump(releases_json, f, indent=2)

print("\n=== Final RQB-releases.json ===")
print(json.dumps(releases_json, indent=2))

# ================================================================
# Generate RQB-images-all.json with ALL releases
# ================================================================
# Sort all_releases by published date (newest first)
all_releases.sort(key=lambda x: x.get('_published', ''), reverse=True)

all_images_json = {
    "generated": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    "description": "All RasQberry image versions for development and testing",
    "count": len(all_releases),
    "releases": all_releases
}

with open('public/RQB-images-all.json', 'w') as f:
    json.dump(all_images_json, f, indent=2)

print(f"\n=== RQB-images-all.json: {len(all_releases)} entries ===")
