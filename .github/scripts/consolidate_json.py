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
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "JanLahmann/RasQberry-Two")

# A/B default (on since beta round 4, Jan 2026-10-03). True: the A/B image is
# the recommended entry, for every card size (two systems from 64 GB, one
# system below), and the standard image is listed as "single system". False
# (RQB_AB_DEFAULT=false): the standard image leads again and the A/B image is
# listed for 64 GB+ cards. Keep AB_DEFAULT in the website's
# src/app/latest/page.tsx in step.
AB_DEFAULT = os.environ.get("RQB_AB_DEFAULT", "true").lower() in ("1", "true", "yes")

# Raspberry Pi Imager OS customisation (Wi-Fi, localisation, SSH key) needs
# init_format in the entry; without it Imager 2.x skips the customisation step.
# The images are Bookworm, so the format is "systemd": Imager writes
# firstrun.sh and a systemd.run entry in cmdline.txt on the FIRST FAT
# partition. On the standard image that is the boot partition, so it works. On
# the A/B image it is CONFIG, which the firmware reads only for autoboot.txt:
# the firmware alone would ignore it (no cmdline.txt there). Since the beta of
# October 2026 the A/B image applies CONFIG/firstrun.sh itself, on the first
# start of a newly written card, so A/B entries carry init_format too.
# RQB_AB_CUSTOMISATION=false switches it off again.
AB_IMAGER_CUSTOMISATION = os.environ.get("RQB_AB_CUSTOMISATION", "true").lower() in ("1", "true", "yes")

# The developer folder lists the development branch and the newest few other
# branches (standard and A/B image each); older branch builds stay in
# RQB-images-all.json and on the releases page.
DEV_BRANCHES_SHOWN = int(os.environ.get("RQB_DEV_BRANCHES_SHOWN", "3"))

# Imager shows the description under the name: the login is the one thing a
# user who never visits the website cannot find out. It is the default: the
# user name and password set in Imager replace it.
LOGIN = "Default login rasqberry / Qiskit1!"

# Raspberry Pi Connect in Imager's customisation: images from this date on
# send Imager's Connect token to the right user (tested 2026-10-07). Older
# builds would give it to a user that does not exist.
CONNECT_SINCE = "2026-10-07"
ICON = "https://rasqberry.org/Artwork/RasQberry 2 Logo Cube 64x64.png"
DEV_FOLDER_NAME = "RasQberry developer builds"
SINGLE = " \u2014 single system"   # "RasQberry Two Beta — single system"


def imager_entry(entry, is_ab):
    """Set init_format as Imager customisation allows for this image type."""
    if is_ab and not AB_IMAGER_CUSTOMISATION:
        entry.pop('init_format', None)
    else:
        entry.setdefault('init_format', 'systemd')
    if 'init_format' in entry and str(entry.get('release_date', ''))[:10] >= CONNECT_SINCE:
        caps = entry.setdefault('capabilities', [])
        if 'rpi_connect' not in caps:
            caps.append('rpi_connect')
    return entry

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

# Collect entries by category. Each list holds (published, branch, entry).
main_std = []      # Stable (main) standard image
main_ab = []       # Stable (main) A/B image
beta_std = []      # Beta standard image
beta_ab = []       # Beta A/B image
dev_std = []       # Dev stream candidates (development branch) for RQB-releases.json
dev_all = []       # dev-* branch standard images (dev stream fallback)
ab_all = []        # Every A/B image, to look up a release's ab_image_url
dev_builds = []    # Everything for the developer folder: (published, branch, is_ab, entry)

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

json_dir = Path(os.environ.get("RQB_RELEASE_JSON_DIR", "/tmp/release-json"))

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

            # Classify by BRANCH NAME. Names and descriptions of the stable
            # and beta entries are set when the list is built (AB_DEFAULT).
            is_ab = image_type == 'ab' or 'A/B' in name
            if is_ab:
                ab_all.append((published, branch_name, entry_clean))

            if branch_name == 'main' and 'Dev' not in name:
                (main_ab if is_ab else main_std).append((published, branch_name, entry_clean))
                print(f"  → Stable{' A/B' if is_ab else ''}")
            elif branch_name == 'beta':
                (beta_ab if is_ab else beta_std).append((published, branch_name, entry_clean))
                print(f"  → Beta{' A/B' if is_ab else ''}")
            else:
                # development, dev-* branches, a dev build on main, unknown
                # branches: all in the developer folder, never at the top.
                timestamp = extract_timestamp(url)
                stamp = f" {timestamp}" if timestamp else ""
                kind = "Dev A/B" if is_ab else "Dev"
                entry_clean['name'] = f"RasQberry Two {kind} ({branch_name}{stamp})"
                entry_clean['description'] = (
                    f"{'A/B image' if is_ab else 'Build'} from the {branch_name} branch. "
                    f"Untested, for developers. {LOGIN}")
                dev_builds.append((published, branch_name, is_ab, entry_clean))
                if not is_ab:
                    if branch_name.startswith('dev') and branch_name != 'development':
                        dev_all.append((published, branch_name, entry_clean))
                    else:
                        dev_std.append((published, branch_name, entry_clean))
                print(f"  → Developer folder: {entry_clean['name']}")

    except Exception as e:
        print(f"  Error loading {json_file}: {e}")

# Sort each category by release_date (newest first)
for category in (main_std, main_ab, beta_std, beta_ab, dev_std, dev_all, ab_all):
    category.sort(key=lambda x: x[0], reverse=True)
# Developer folder: the development branch first, then the newest
# DEV_BRANCHES_SHOWN other branches, newest first, each standard image before
# its A/B image.
dev_builds.sort(key=lambda x: x[2])
dev_builds.sort(key=lambda x: x[0], reverse=True)
dev_builds.sort(key=lambda x: x[1] != 'development')
shown_branches = []
for _, branch, _, _ in dev_builds:
    if branch != 'development' and branch not in shown_branches:
        shown_branches.append(branch)
hidden_branches = shown_branches[DEV_BRANCHES_SHOWN:]
dev_builds = [b for b in dev_builds if b[1] not in hidden_branches]
if hidden_branches:
    print(f"\nDeveloper folder: older branch builds left out: {', '.join(hidden_branches)}")


def release_entries(std_list, ab_list, label, recommended):
    """The top-level entries of one release stream (stable or beta).

    Only the newest image of each type. With AB_DEFAULT the A/B image is the
    main entry and the standard image is "single system"; without it, the
    other way round. Returns the entries in display order.
    """
    std = std_list[0][2] if std_list else None
    ab = ab_list[0][2] if ab_list else None
    lead = "Recommended. " if recommended else "Newest features, for testing. "
    if AB_DEFAULT:
        if ab:
            ab['name'] = label
            ab['description'] = (f"{lead}Two systems with safe updates on 64 GB+ cards, one "
                                 f"system on smaller ones. Best: 128 GB A2/U3. Pi 4/5. {LOGIN}")
        if std:
            std['name'] = f"{label}{SINGLE}"
            std['description'] = (f"One system, no updates in place. 16 GB+ card, 32 GB+ for "
                                  f"Docker demos. Pi 4/5. {LOGIN}")
        order = [ab, std]
    else:
        if std:
            std['name'] = label
            std['description'] = (f"{lead}Pi 4/5, 16 GB+ card (128 GB A2/U3 recommended). "
                                  f"{LOGIN}")
        if ab:
            ab['name'] = f"{label} A/B (64 GB+ card)"
            ab['description'] = (f"Two systems on one card: updates install in place and you "
                                 f"can go back. Needs a 64 GB+ card. {LOGIN}")
        order = [std, ab]
    if std:
        imager_entry(std, is_ab=False)
    if ab:
        imager_entry(ab, is_ab=True)
    return [e for e in order if e]


# Build the os_list: stable, beta, the developer folder, stock Pi OS last.
os_list = []
has_stable = bool(main_std or main_ab)
for entry in release_entries(main_std, main_ab, "RasQberry Two", recommended=True):
    os_list.append(entry)
    print(f"\n✓ Added stable: {entry['name']}")
for entry in release_entries(beta_std, beta_ab, "RasQberry Two Beta", recommended=not has_stable):
    os_list.append(entry)
    print(f"✓ Added beta: {entry['name']}")

if dev_builds:
    os_list.append({
        "name": DEV_FOLDER_NAME,
        "description": "Development and the newest branch builds. Untested: not for classrooms or events.",
        "icon": ICON,
        "subitems": [imager_entry(entry, is_ab) for _, _, is_ab, entry in dev_builds]
    })
    print(f"✓ Added developer folder with {len(dev_builds)} images")

# Build final consolidated structure
consolidated = {
    "imager": {
        "latest_version": "1.8.5",
        "url": "https://www.raspberrypi.com/software/"
    },
    "os_list": os_list
}

print(f"\n=== Built hierarchical structure with {len(os_list)} top-level entries ===")

# Stock Raspberry Pi OS stays in the list (the custom repository replaces
# Imager's own list), but last and labelled: upstream calls it
# "(Recommended)", which in a RasQberry list sent teachers to an OS without
# RasQberry.
def stock_name(name):
    return f"{name} \u2014 without RasQberry"


def stock_description(description):
    base = re.sub(r'\s*\(Recommended\)', '', description).strip().rstrip('.')
    return f"Plain Raspberry Pi OS, no RasQberry software. {base}."


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
            "name": stock_name(raspios_entry.get('name', 'Raspberry Pi OS (64-bit)')),
            "description": stock_description(raspios_entry.get('description', 'Official Raspberry Pi OS')),
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
        "name": stock_name("Raspberry Pi OS (64-bit)"),
        "description": stock_description("A port of Debian Bookworm with the Raspberry Pi Desktop"),
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

# ================================================================
# rpi-imager.json: the sublist for the official Raspberry Pi Imager
# ================================================================
# Newest beta (later: stable) release only, checked against Imager's schema
# and the image URLs before it is written. When that fails, the previous
# rpi-imager.json stays; the files above are still committed, and the
# workflow fails the run afterwards (sublist=failed).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rpi_imager_list  # noqa: E402

if not rpi_imager_list.write_sublist(json_dir, Path('public/rpi-imager.json')):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write("sublist=failed\n")
