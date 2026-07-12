#!/usr/bin/env python3
"""
RasQberry A/B Boot Update Poller

Polls GitHub releases for new RasQberry images and triggers automatic updates.

This script runs periodically (every 30 seconds via systemd timer) to check for
new releases in dev* branches. When a new release is found, it triggers the
update process which downloads and installs the image to the inactive boot slot.

Target branches: dev* (dev-remote01, dev-JRL-features02, etc.)
Poll interval: 30 seconds (configured in systemd timer)
"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/rasqberry-update-poller.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
GITHUB_API_URL = "https://api.github.com"
GITHUB_REPO = "JanLahmann/RasQberry-Two"
TARGET_BRANCH_PATTERN = "dev"  # Matches dev*, dev-remote01, dev-JRL-features02, etc.
STATE_FILE = Path("/var/lib/rasqberry-update-poller/state.json")
UPDATE_SCRIPT = Path("/usr/bin/rq_update_slot.sh")
CHECK_INTERVAL_SECONDS = 30  # How often this script runs (via systemd timer)

class UpdatePoller:
    """Polls GitHub for new releases and triggers updates."""

    def __init__(self):
        """Initialize the update poller."""
        self.state_file = STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self.load_state()

    def load_state(self) -> Dict:
        """
        Load the poller state from disk.

        Returns:
            dict: State containing last checked release info
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")

        return {
            'last_release_tag': None,
            'last_release_url': None,
            'last_check_time': None,
            'update_in_progress': False
        }

    def save_state(self):
        """Save the poller state to disk."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state file: {e}")

    def fetch_github_releases(self) -> Optional[List[Dict]]:
        """
        Fetch releases from GitHub API.

        Returns:
            list: List of release objects, or None on error
        """
        url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/releases"

        try:
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/vnd.github.v3+json')

            # Add GitHub token if available (increases rate limit)
            github_token = os.environ.get('GITHUB_TOKEN')
            if github_token:
                req.add_header('Authorization', f'token {github_token}')

            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
                releases = json.loads(data.decode('utf-8'))
                return releases

        except urllib.error.HTTPError as e:
            logger.error(f"GitHub API HTTP error: {e.code} {e.reason}")
            return None
        except urllib.error.URLError as e:
            logger.error(f"GitHub API network error: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"GitHub API error: {e}")
            return None

    def filter_dev_releases(self, releases: List[Dict]) -> List[Dict]:
        """
        Filter releases to only include dev* branches.

        Args:
            releases: List of all releases

        Returns:
            list: Filtered list of dev* branch releases
        """
        dev_releases = []

        for release in releases:
            tag_name = release.get('tag_name', '')
            # Check if tag contains dev branch pattern
            # Tags look like: dev-remote01-2025-10-25-123456
            if TARGET_BRANCH_PATTERN in tag_name:
                dev_releases.append(release)

        return dev_releases

    def get_latest_dev_release(self) -> Optional[Dict]:
        """
        Get the latest dev* branch release.

        Returns:
            dict: Latest release object, or None if not found
        """
        logger.info("Checking GitHub for new releases...")

        releases = self.fetch_github_releases()
        if not releases:
            logger.warning("No releases found or API error")
            return None

        dev_releases = self.filter_dev_releases(releases)
        if not dev_releases:
            logger.info(f"No {TARGET_BRANCH_PATTERN}* releases found")
            return None

        # Get the most recent one (they're already sorted by created_at desc)
        latest = dev_releases[0]
        logger.info(f"Latest {TARGET_BRANCH_PATTERN}* release: {latest.get('tag_name')}")

        return latest

    def is_new_release(self, release: Dict) -> bool:
        """
        Check if this is a new release we haven't seen before.

        Args:
            release: Release object from GitHub

        Returns:
            bool: True if this is a new release
        """
        tag_name = release.get('tag_name')
        last_tag = self.state.get('last_release_tag')

        if not last_tag:
            logger.info("No previous release recorded, this is new")
            return True

        if tag_name != last_tag:
            logger.info(f"New release detected: {tag_name} (previous: {last_tag})")
            return True

        logger.debug(f"Release {tag_name} already processed")
        return False

    def find_image_asset(self, release: Dict) -> Optional[Dict]:
        """
        Find the .img.xz asset in the release.

        Args:
            release: Release object from GitHub

        Returns:
            dict: Asset object, or None if not found
        """
        assets = release.get('assets', [])

        for asset in assets:
            name = asset.get('name', '')
            if name.endswith('.img.xz'):
                logger.info(f"Found image asset: {name}")
                return asset

        logger.warning("No .img.xz asset found in release")
        return None

    def find_manifest_asset(self, release: Dict) -> Optional[Dict]:
        """
        Find the manifest.json asset in the release.

        Args:
            release: Release object from GitHub

        Returns:
            dict: Asset object, or None if not found
        """
        assets = release.get('assets', [])

        for asset in assets:
            name = asset.get('name', '')
            if name == 'manifest.json':
                logger.info(f"Found manifest asset: {name}")
                return asset

        logger.warning("No manifest.json asset found in release")
        return None

    def trigger_update(self, release: Dict):
        """
        Trigger the update process for a new release.

        Args:
            release: Release object from GitHub
        """
        tag_name = release.get('tag_name')
        logger.info(f"Triggering update for release: {tag_name}")

        # Find image asset
        image_asset = self.find_image_asset(release)
        if not image_asset:
            logger.error("Cannot trigger update: no image asset found")
            return

        # Get download URL
        download_url = image_asset.get('browser_download_url')
        if not download_url:
            logger.error("Cannot trigger update: no download URL")
            return

        # Check if update script exists
        if not UPDATE_SCRIPT.exists():
            logger.error(f"Update script not found: {UPDATE_SCRIPT}")
            return

        # Mark update in progress
        self.state['update_in_progress'] = True
        self.state['update_release_tag'] = tag_name
        self.save_state()

        try:
            # Call update script with download URL and tag name
            logger.info(f"Executing: {UPDATE_SCRIPT} {download_url} {tag_name}")

            result = subprocess.run(
                [str(UPDATE_SCRIPT), download_url, tag_name],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout for download and write
            )

            if result.returncode == 0:
                logger.info("Update script completed successfully")
                logger.info(f"STDOUT: {result.stdout}")

                # Update state
                self.state['last_release_tag'] = tag_name
                self.state['last_release_url'] = download_url
                self.state['last_update_time'] = time.time()
                self.state['update_in_progress'] = False
                self.save_state()

            else:
                logger.error(f"Update script failed with code {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")
                self.state['update_in_progress'] = False
                self.save_state()

        except subprocess.TimeoutExpired:
            logger.error("Update script timed out after 1 hour")
            self.state['update_in_progress'] = False
            self.save_state()
        except Exception as e:
            logger.error(f"Error executing update script: {e}")
            self.state['update_in_progress'] = False
            self.save_state()

    def check_for_updates(self):
        """Main update check routine."""
        logger.info("=== RasQberry Update Poller Check ===")

        # Check if update already in progress
        if self.state.get('update_in_progress', False):
            logger.info("Update already in progress, skipping check")
            return

        # Get latest dev release
        latest_release = self.get_latest_dev_release()
        if not latest_release:
            logger.info("No applicable releases found")
            self.state['last_check_time'] = time.time()
            self.save_state()
            return

        # Check if it's a new release
        if not self.is_new_release(latest_release):
            logger.info("No new releases")
            self.state['last_check_time'] = time.time()
            self.save_state()
            return

        # Trigger update
        self.trigger_update(latest_release)


def main():
    """Main entry point."""
    logger.info("RasQberry Update Poller starting...")

    try:
        poller = UpdatePoller()
        poller.check_for_updates()
        logger.info("Update check complete")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Update poller failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
