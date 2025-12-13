#!/usr/bin/env python3
"""
Barsys APK Download and Analysis Script

This script downloads the Barsys APK and performs BLE protocol analysis.
Run this on a machine with unrestricted internet access.

Usage:
    python3 download_and_analyze.py
"""

import subprocess
import sys
import os
import zipfile
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Any

# Configuration
APK_PACKAGE = "com.app.barsys"
APK_NAME = "barsys.apk"
OUTPUT_DIR = "barsys-analysis"

# Known BLE UUIDs for reference
STANDARD_BLE_SERVICES = {
    "1800": "Generic Access",
    "1801": "Generic Attribute",
    "180A": "Device Information",
    "180F": "Battery Service",
    "FFE0": "Custom Service (Common)",
    "FFE1": "Custom Characteristic (Common)",
}


def install_dependencies():
    """Install required Python packages."""
    packages = ["requests", "pyaxmlparser"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


def download_apk_apkpure(package_name: str, output_path: str) -> bool:
    """Try to download APK from APKPure."""
    import requests

    print(f"Attempting to download {package_name} from APKPure...")

    # APKPure download URL pattern
    url = f"https://d.apkpure.com/b/APK/{package_name}?version=latest"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=60)
        if response.status_code == 200 and len(response.content) > 10000:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded APK to {output_path}")
            return True
    except Exception as e:
        print(f"APKPure download failed: {e}")

    return False


def download_apk_apkcombo(package_name: str, output_path: str) -> bool:
    """Try to download APK from APKCombo."""
    import requests

    print(f"Attempting to download {package_name} from APKCombo...")

    try:
        # First get the download page
        url = f"https://apkcombo.com/downloader/?package={package_name}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)

        # Look for download link in response
        # This is a simplified approach - real implementation would need to parse the page
        print("APKCombo requires manual download - visit:")
        print(f"  https://apkcombo.com/barsys-cocktail-crafting/{package_name}/download/apk")
        return False
    except Exception as e:
        print(f"APKCombo failed: {e}")

    return False


def download_apk_manual_instructions():
    """Provide manual download instructions."""
    print("\n" + "="*60)
    print("MANUAL APK DOWNLOAD INSTRUCTIONS")
    print("="*60)
    print("""
Option 1: APKPure (Recommended)
  1. Visit: https://apkpure.com/barsys-cocktail-crafting/com.app.barsys/download
  2. Click "Download APK"
  3. Save as: barsys.apk

Option 2: APKCombo
  1. Visit: https://apkcombo.com/barsys-cocktail-crafting/com.app.barsys/download/apk
  2. Select latest version
  3. Download and save as: barsys.apk

Option 3: From Android Device (if you have the app installed)
  adb shell pm path com.app.barsys
  adb pull <path_from_above> barsys.apk

Option 4: APK Extractor App
  1. Install "APK Extractor" from Play Store on your Android device
  2. Extract the Barsys app
  3. Transfer barsys.apk to this computer

After downloading, place barsys.apk in this directory and run:
  python3 download_and_analyze.py --analyze-only
""")


def extract_apk(apk_path: str, output_dir: str) -> bool:
    """Extract APK contents (APK is just a ZIP file)."""
    print(f"Extracting APK to {output_dir}...")

    try:
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        print(f"Extracted to {output_dir}")
        return True
    except Exception as e:
        print(f"Extraction failed: {e}")
        return False


def analyze_manifest(apk_dir: str) -> Dict[str, Any]:
    """Analyze AndroidManifest.xml for BLE permissions and services."""
    manifest_path = os.path.join(apk_dir, "AndroidManifest.xml")

    results = {
        "permissions": [],
        "services": [],
        "activities": [],
        "bluetooth_related": []
    }

    try:
        from pyaxmlparser import APK
        apk = APK(os.path.join(os.path.dirname(apk_dir), APK_NAME))

        # Get permissions
        results["permissions"] = apk.get_permissions()

        # Filter BLE-related permissions
        ble_permissions = [p for p in results["permissions"] if "BLUETOOTH" in p.upper()]
        results["bluetooth_related"].extend(ble_permissions)

        print("\n=== Bluetooth Permissions ===")
        for perm in ble_permissions:
            print(f"  {perm}")

    except Exception as e:
        print(f"Manifest analysis error: {e}")

        # Fallback: try to read raw manifest
        if os.path.exists(manifest_path):
            with open(manifest_path, 'rb') as f:
                content = f.read()
                # Search for bluetooth-related strings
                if b"bluetooth" in content.lower():
                    results["bluetooth_related"].append("BLUETOOTH references found in manifest")

    return results


def search_dex_for_ble(apk_dir: str) -> Dict[str, Any]:
    """Search DEX files for BLE-related strings."""
    results = {
        "uuids_128bit": set(),
        "uuids_16bit": set(),
        "bluetooth_strings": [],
        "api_endpoints": set(),
        "interesting_strings": []
    }

    print("\n=== Searching DEX files for BLE patterns ===")

    # Find all DEX files
    dex_files = list(Path(apk_dir).glob("*.dex"))

    for dex_path in dex_files:
        print(f"Analyzing {dex_path.name}...")

        try:
            with open(dex_path, 'rb') as f:
                content = f.read()

            # Convert to string for pattern matching (lossy but works for strings)
            text = content.decode('utf-8', errors='ignore')

            # Search for 128-bit UUIDs
            uuid_pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
            for match in re.finditer(uuid_pattern, text):
                results["uuids_128bit"].add(match.group(0).lower())

            # Search for Bluetooth-related strings
            bt_patterns = [
                r'BluetoothGatt\w*',
                r'BleManager\w*',
                r'writeCharacteristic',
                r'readCharacteristic',
                r'setNotification',
            ]
            for pattern in bt_patterns:
                for match in re.finditer(pattern, text):
                    if match.group(0) not in results["bluetooth_strings"]:
                        results["bluetooth_strings"].append(match.group(0))

            # Search for API endpoints
            url_pattern = r'https?://[a-zA-Z0-9.-]+(?:barsys)[a-zA-Z0-9./_-]*'
            for match in re.finditer(url_pattern, text, re.IGNORECASE):
                results["api_endpoints"].add(match.group(0))

            # Search for pump/dispense related strings
            pump_pattern = r'(?:pump|dispense|pour|station|volume|ingredient)\w*'
            for match in re.finditer(pump_pattern, text, re.IGNORECASE):
                if len(match.group(0)) > 4:
                    results["interesting_strings"].append(match.group(0))

        except Exception as e:
            print(f"  Error analyzing {dex_path.name}: {e}")

    # Convert sets to lists for JSON serialization
    results["uuids_128bit"] = list(results["uuids_128bit"])
    results["uuids_16bit"] = list(results["uuids_16bit"])
    results["api_endpoints"] = list(results["api_endpoints"])
    results["interesting_strings"] = list(set(results["interesting_strings"]))[:50]

    return results


def search_resources(apk_dir: str) -> Dict[str, Any]:
    """Search resource files for configuration."""
    results = {
        "config_files": [],
        "ble_config": []
    }

    print("\n=== Searching resource files ===")

    # Check for common config locations
    config_paths = [
        "res/raw",
        "res/xml",
        "assets",
    ]

    for config_path in config_paths:
        full_path = os.path.join(apk_dir, config_path)
        if os.path.exists(full_path):
            for root, dirs, files in os.walk(full_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    results["config_files"].append(filepath)

                    # Read and check for BLE content
                    try:
                        with open(filepath, 'rb') as f:
                            content = f.read().decode('utf-8', errors='ignore')
                            if 'bluetooth' in content.lower() or 'uuid' in content.lower():
                                results["ble_config"].append({
                                    "file": filepath,
                                    "preview": content[:500]
                                })
                    except:
                        pass

    return results


def generate_report(manifest_results: Dict, dex_results: Dict, resource_results: Dict) -> str:
    """Generate a comprehensive analysis report."""
    report = []
    report.append("=" * 70)
    report.append("BARSYS APK BLE PROTOCOL ANALYSIS REPORT")
    report.append("=" * 70)
    report.append("")

    # UUIDs Section
    report.append("## Discovered 128-bit UUIDs (Custom Services/Characteristics)")
    report.append("-" * 50)
    if dex_results.get("uuids_128bit"):
        for uuid in sorted(dex_results["uuids_128bit"]):
            report.append(f"  {uuid}")
            # Check if it's a standard BLE UUID format
            if uuid.startswith("0000") and uuid.endswith("-0000-1000-8000-00805f9b34fb"):
                short_uuid = uuid[4:8].upper()
                service_name = STANDARD_BLE_SERVICES.get(short_uuid, "Unknown Standard Service")
                report.append(f"    -> Standard BLE: 0x{short_uuid} ({service_name})")
    else:
        report.append("  No 128-bit UUIDs found in DEX")
    report.append("")

    # Bluetooth Strings
    report.append("## Bluetooth-Related Code References")
    report.append("-" * 50)
    for s in dex_results.get("bluetooth_strings", [])[:20]:
        report.append(f"  {s}")
    report.append("")

    # API Endpoints
    report.append("## API Endpoints")
    report.append("-" * 50)
    for url in sorted(dex_results.get("api_endpoints", [])):
        report.append(f"  {url}")
    report.append("")

    # Interesting Strings
    report.append("## Pump/Dispense Related Strings")
    report.append("-" * 50)
    for s in sorted(set(dex_results.get("interesting_strings", [])))[:30]:
        report.append(f"  {s}")
    report.append("")

    # Permissions
    report.append("## Bluetooth Permissions")
    report.append("-" * 50)
    for perm in manifest_results.get("bluetooth_related", []):
        report.append(f"  {perm}")
    report.append("")

    # Config Files
    report.append("## BLE Configuration Files")
    report.append("-" * 50)
    for config in resource_results.get("ble_config", []):
        report.append(f"  {config['file']}")
    report.append("")

    # Recommendations
    report.append("## Next Steps for Full Protocol Analysis")
    report.append("-" * 50)
    report.append("""
  1. Use JADX-GUI to decompile and view Java source code:
     jadx-gui barsys.apk

  2. Search for classes containing "Bluetooth", "BLE", "Gatt"

  3. Look for command byte arrays in pump/dispense control classes

  4. Use nRF Connect app to scan the actual device and verify UUIDs

  5. Capture BLE traffic with Wireshark + nRF Sniffer for command format
""")

    return "\n".join(report)


def main():
    """Main entry point."""
    print("Barsys APK Download and Analysis Tool")
    print("=" * 40)

    # Install dependencies
    install_dependencies()

    # Check if APK exists
    apk_exists = os.path.exists(APK_NAME)

    if not apk_exists and "--analyze-only" not in sys.argv:
        # Try to download
        if not download_apk_apkpure(APK_PACKAGE, APK_NAME):
            if not download_apk_apkcombo(APK_PACKAGE, APK_NAME):
                download_apk_manual_instructions()
                return

    if not os.path.exists(APK_NAME):
        print(f"\nError: {APK_NAME} not found!")
        print("Please download the APK manually and place it in this directory.")
        download_apk_manual_instructions()
        return

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Extract APK
    extract_dir = os.path.join(OUTPUT_DIR, "extracted")
    if not os.path.exists(extract_dir):
        extract_apk(APK_NAME, extract_dir)

    # Run analysis
    print("\nRunning analysis...")
    manifest_results = analyze_manifest(extract_dir)
    dex_results = search_dex_for_ble(extract_dir)
    resource_results = search_resources(extract_dir)

    # Generate report
    report = generate_report(manifest_results, dex_results, resource_results)
    print("\n" + report)

    # Save results
    report_path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")

    # Save JSON results
    json_results = {
        "manifest": manifest_results,
        "dex_analysis": dex_results,
        "resources": resource_results
    }
    json_path = os.path.join(OUTPUT_DIR, "analysis_results.json")
    with open(json_path, 'w') as f:
        json.dump(json_results, f, indent=2)
    print(f"JSON results saved to: {json_path}")


if __name__ == "__main__":
    main()
