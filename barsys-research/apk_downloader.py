#!/usr/bin/env python3
"""
Barsys APK Multi-Source Downloader

This script attempts to download the Barsys APK from multiple sources.
Run this on a machine with unrestricted internet access.

Sources tried (in order):
1. APKPure CDN direct link
2. APKCombo
3. Evozi APK Downloader
4. APKMirror search

Usage:
    python3 apk_downloader.py
"""

import os
import sys
import re
import time
import hashlib
from urllib.parse import urljoin, urlparse

# Check and install dependencies
def install_deps():
    try:
        import requests
        from bs4 import BeautifulSoup
        from tqdm import tqdm
    except ImportError:
        print("Installing dependencies...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                             "requests", "beautifulsoup4", "tqdm", "-q"])
        print("Dependencies installed. Please run the script again.")
        sys.exit(0)

install_deps()

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Configuration
PACKAGE_NAME = "com.app.barsys"
APK_OUTPUT = "barsys.apk"
USER_AGENT = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}


def download_file(url: str, output_path: str, headers: dict = None) -> bool:
    """Download a file with progress bar."""
    try:
        headers = headers or HEADERS.copy()
        response = requests.get(url, headers=headers, stream=True, timeout=120, allow_redirects=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        # Check if it's actually an APK (should be > 1MB)
        if total_size > 0 and total_size < 1_000_000:
            print(f"  Warning: File too small ({total_size} bytes), likely not an APK")
            return False

        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # Verify it's a valid APK (ZIP file starting with PK)
        with open(output_path, 'rb') as f:
            magic = f.read(2)
            if magic != b'PK':
                print("  Warning: Downloaded file is not a valid APK/ZIP")
                os.remove(output_path)
                return False

        file_size = os.path.getsize(output_path)
        print(f"  Downloaded: {output_path} ({file_size / 1_000_000:.2f} MB)")
        return True

    except Exception as e:
        print(f"  Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def try_apkpure_direct():
    """Try direct APKPure CDN download."""
    print("\n[1/5] Trying APKPure direct CDN...")

    # APKPure CDN URL pattern
    url = f"https://d.apkpure.com/b/APK/{PACKAGE_NAME}?version=latest"

    headers = HEADERS.copy()
    headers["Referer"] = f"https://apkpure.com/barsys-cocktail-crafting/{PACKAGE_NAME}/download"

    return download_file(url, APK_OUTPUT, headers)


def try_apkpure_scrape():
    """Try to scrape APKPure download page."""
    print("\n[2/5] Trying APKPure page scrape...")

    try:
        # Get the download page
        url = f"https://apkpure.com/barsys-cocktail-crafting/{PACKAGE_NAME}/download"
        response = requests.get(url, headers=HEADERS, timeout=30)

        if response.status_code != 200:
            print(f"  Failed to load page: {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for download links
        download_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '.apk' in href.lower() or 'd.apkpure.com' in href:
                download_links.append(href)

        # Also look for data attributes
        for elem in soup.find_all(attrs={"data-dt-url": True}):
            download_links.append(elem["data-dt-url"])

        for link in download_links:
            if not link.startswith('http'):
                link = urljoin(url, link)
            print(f"  Found link: {link[:80]}...")
            if download_file(link, APK_OUTPUT):
                return True

        print("  No valid download links found")
        return False

    except Exception as e:
        print(f"  Scrape failed: {e}")
        return False


def try_apkcombo():
    """Try APKCombo download."""
    print("\n[3/5] Trying APKCombo...")

    try:
        # Search for the app
        search_url = f"https://apkcombo.com/search/{PACKAGE_NAME}"
        response = requests.get(search_url, headers=HEADERS, timeout=30)

        if response.status_code != 200:
            print(f"  Failed to search: {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find app link
        app_link = None
        for a in soup.find_all('a', href=True):
            if PACKAGE_NAME in a['href'] or 'barsys' in a['href'].lower():
                app_link = a['href']
                break

        if app_link:
            if not app_link.startswith('http'):
                app_link = urljoin("https://apkcombo.com", app_link)

            # Get download page
            download_url = app_link.rstrip('/') + "/download/apk"
            print(f"  Trying: {download_url}")

            response = requests.get(download_url, headers=HEADERS, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find download button/link
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'download' in href.lower() and ('apk' in href.lower() or 'cdn' in href.lower()):
                    if download_file(href, APK_OUTPUT):
                        return True

        print("  No download found on APKCombo")
        return False

    except Exception as e:
        print(f"  APKCombo failed: {e}")
        return False


def try_evozi():
    """Try Evozi APK Downloader."""
    print("\n[4/5] Trying Evozi APK Downloader...")

    try:
        url = f"https://apps.evozi.com/apk-downloader/?id={PACKAGE_NAME}"

        # Evozi uses JavaScript, so we need to make an API call
        api_url = "https://api-apk.evozi.com/download"

        data = {
            "package": PACKAGE_NAME,
            "fetch": "false"
        }

        headers = HEADERS.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = url

        response = requests.post(api_url, data=data, headers=headers, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if "url" in result:
                print(f"  Found download URL")
                if download_file(result["url"], APK_OUTPUT):
                    return True

        print("  Evozi didn't return a download link")
        return False

    except Exception as e:
        print(f"  Evozi failed: {e}")
        return False


def try_apkmirror():
    """Try APKMirror search."""
    print("\n[5/5] Trying APKMirror...")

    try:
        search_url = f"https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=barsys"
        response = requests.get(search_url, headers=HEADERS, timeout=30)

        if response.status_code != 200:
            print(f"  Failed to search: {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find matching results
        for a in soup.find_all('a', href=True, class_='fontBlack'):
            if 'barsys' in a.text.lower() or 'barsys' in a['href'].lower():
                app_url = urljoin("https://www.apkmirror.com", a['href'])
                print(f"  Found: {a.text.strip()}")
                print(f"  Visit: {app_url}")
                # APKMirror has captcha protection, so we just provide the link
                return False

        print("  Barsys not found on APKMirror")
        return False

    except Exception as e:
        print(f"  APKMirror failed: {e}")
        return False


def manual_instructions():
    """Show manual download instructions."""
    print("\n" + "="*60)
    print("AUTOMATIC DOWNLOAD FAILED - MANUAL INSTRUCTIONS")
    print("="*60)
    print(f"""
All automatic download methods failed. Please download manually:

Option 1: APKPure (Most Reliable)
  1. Visit: https://apkpure.com/barsys-cocktail-crafting/com.app.barsys/download
  2. Click the green "Download APK" button
  3. Save the file as: {APK_OUTPUT}

Option 2: Google Play (Requires Android Device)
  1. Install on your Android device from Play Store
  2. Use ADB to extract:
     adb shell pm path {PACKAGE_NAME}
     adb pull <path> {APK_OUTPUT}

Option 3: APK Extractor App
  1. Install "APK Extractor" on your Android device
  2. Extract the Barsys app
  3. Transfer to this computer

Option 4: Use APKPure App
  1. Install APKPure app on Android from apkpure.com
  2. Search and download Barsys
  3. APK will be saved to Download folder

After downloading, place the APK file in this directory as:
  {os.path.abspath(APK_OUTPUT)}

Then run the analysis:
  python3 download_and_analyze.py --analyze-only
""")


def verify_apk():
    """Verify the downloaded APK."""
    if not os.path.exists(APK_OUTPUT):
        return False

    file_size = os.path.getsize(APK_OUTPUT)

    # Check file size (Barsys app is ~41 MB)
    if file_size < 10_000_000:
        print(f"Warning: APK seems too small ({file_size / 1_000_000:.2f} MB)")
        return False

    # Check ZIP magic bytes
    with open(APK_OUTPUT, 'rb') as f:
        magic = f.read(4)
        if magic[:2] != b'PK':
            print("Error: File is not a valid APK (ZIP) file")
            return False

    # Calculate hash
    with open(APK_OUTPUT, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    print(f"\nAPK Verification:")
    print(f"  File: {APK_OUTPUT}")
    print(f"  Size: {file_size / 1_000_000:.2f} MB")
    print(f"  SHA256: {sha256}")

    return True


def main():
    print("="*60)
    print("BARSYS APK MULTI-SOURCE DOWNLOADER")
    print("="*60)
    print(f"Target: {PACKAGE_NAME}")
    print(f"Output: {APK_OUTPUT}")

    # Check if already downloaded
    if os.path.exists(APK_OUTPUT):
        print(f"\nAPK already exists: {APK_OUTPUT}")
        if verify_apk():
            print("APK verified successfully!")
            return True
        else:
            print("Existing APK is invalid, re-downloading...")
            os.remove(APK_OUTPUT)

    # Try each download method
    methods = [
        try_apkpure_direct,
        try_apkpure_scrape,
        try_apkcombo,
        try_evozi,
        try_apkmirror,
    ]

    for method in methods:
        try:
            if method():
                if verify_apk():
                    print("\n" + "="*60)
                    print("SUCCESS! APK downloaded and verified.")
                    print("="*60)
                    print(f"\nNext step: Run the analysis")
                    print(f"  python3 download_and_analyze.py --analyze-only")
                    return True
        except Exception as e:
            print(f"  Method failed with error: {e}")

        time.sleep(1)  # Be nice to servers

    # All methods failed
    manual_instructions()
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
