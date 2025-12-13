#!/usr/bin/env python3
"""
Barsys APK BLE Protocol Analyzer

This script analyzes decompiled APK source code to extract:
- BLE Service UUIDs
- Characteristic UUIDs
- Command structures
- API endpoints
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict

# Standard BLE Service UUIDs (16-bit)
STANDARD_SERVICES = {
    "1800": "Generic Access",
    "1801": "Generic Attribute",
    "1802": "Immediate Alert",
    "1803": "Link Loss",
    "1804": "Tx Power",
    "1805": "Current Time",
    "1806": "Reference Time Update",
    "1807": "Next DST Change",
    "1808": "Glucose",
    "1809": "Health Thermometer",
    "180A": "Device Information",
    "180D": "Heart Rate",
    "180E": "Phone Alert Status",
    "180F": "Battery",
    "1810": "Blood Pressure",
    "1811": "Alert Notification",
    "1812": "Human Interface Device",
    "1813": "Scan Parameters",
    "1814": "Running Speed and Cadence",
    "1815": "Automation IO",
    "1816": "Cycling Speed and Cadence",
    "1818": "Cycling Power",
    "1819": "Location and Navigation",
    "181A": "Environmental Sensing",
    "181B": "Body Composition",
    "181C": "User Data",
    "181D": "Weight Scale",
    "181E": "Bond Management",
    "181F": "Continuous Glucose Monitoring",
}


class BLEProtocolAnalyzer:
    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.results = {
            "uuids_128bit": set(),
            "uuids_16bit": set(),
            "bluetooth_classes": [],
            "write_operations": [],
            "read_operations": [],
            "byte_commands": [],
            "api_endpoints": set(),
            "service_definitions": [],
            "characteristic_definitions": [],
        }

    def find_java_files(self):
        """Find all Java source files in the decompiled directory."""
        return list(self.source_dir.rglob("*.java"))

    def extract_128bit_uuids(self, content: str, filepath: str):
        """Extract 128-bit UUIDs from source code."""
        pattern = r'["\']?([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})["\']?'
        matches = re.findall(pattern, content)
        for uuid in matches:
            self.results["uuids_128bit"].add(uuid.lower())

    def extract_16bit_uuids(self, content: str, filepath: str):
        """Extract 16-bit BLE service/characteristic UUIDs."""
        # Match patterns like 0x1800, "1800", UUID.fromString("00001800-...")
        patterns = [
            r'0x([0-9a-fA-F]{4})',
            r'fromString\s*\(\s*["\']0000([0-9a-fA-F]{4})-',
            r'UUID_([0-9a-fA-F]{4})',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for uuid in matches:
                uuid_upper = uuid.upper()
                if uuid_upper in STANDARD_SERVICES or uuid_upper.startswith("FF"):
                    self.results["uuids_16bit"].add(uuid_upper)

    def extract_bluetooth_operations(self, content: str, filepath: str):
        """Extract Bluetooth GATT operations."""
        # Write characteristic operations
        write_pattern = r'(writeCharacteristic|setValue)\s*\([^)]*\)'
        for match in re.finditer(write_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            self.results["write_operations"].append({
                "file": str(filepath),
                "line": line_num,
                "code": match.group(0)[:100]
            })

        # Read characteristic operations
        read_pattern = r'(readCharacteristic|getValue)\s*\([^)]*\)'
        for match in re.finditer(read_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            self.results["read_operations"].append({
                "file": str(filepath),
                "line": line_num,
                "code": match.group(0)[:100]
            })

    def extract_byte_commands(self, content: str, filepath: str):
        """Extract byte array commands that might be BLE protocol commands."""
        # Match byte array initializations
        patterns = [
            r'new\s+byte\s*\[\s*\]\s*\{([^}]+)\}',
            r'byteArrayOf\s*\(([^)]+)\)',
            r'\[\s*(0x[0-9a-fA-F]{1,2}(?:\s*,\s*0x[0-9a-fA-F]{1,2})+)\s*\]',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                bytes_str = match.group(1).strip()
                if len(bytes_str) > 3:  # Filter out trivial arrays
                    line_num = content[:match.start()].count('\n') + 1
                    self.results["byte_commands"].append({
                        "file": str(filepath),
                        "line": line_num,
                        "bytes": bytes_str[:200]
                    })

    def extract_api_endpoints(self, content: str, filepath: str):
        """Extract HTTP API endpoints."""
        pattern = r'https?://[a-zA-Z0-9.-]+(?:/[a-zA-Z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?'
        matches = re.findall(pattern, content)
        for url in matches:
            # Filter out common non-API URLs
            if not any(skip in url for skip in ['google.com/maps', 'android.com', 'googleapis.com/auth']):
                self.results["api_endpoints"].add(url)

    def extract_service_definitions(self, content: str, filepath: str):
        """Extract BLE service class definitions."""
        # Look for service-related class definitions
        pattern = r'class\s+(\w*(?:Service|Gatt|BLE|Bluetooth)\w*)\s*(?:extends|implements|\{)'
        matches = re.findall(pattern, content)
        for class_name in matches:
            if class_name not in self.results["bluetooth_classes"]:
                self.results["bluetooth_classes"].append(class_name)

    def analyze(self):
        """Run all analysis on the source code."""
        java_files = self.find_java_files()
        print(f"Found {len(java_files)} Java files to analyze...")

        for i, filepath in enumerate(java_files):
            if i % 100 == 0:
                print(f"Processing file {i}/{len(java_files)}...")

            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')

                self.extract_128bit_uuids(content, filepath)
                self.extract_16bit_uuids(content, filepath)
                self.extract_bluetooth_operations(content, filepath)
                self.extract_byte_commands(content, filepath)
                self.extract_api_endpoints(content, filepath)
                self.extract_service_definitions(content, filepath)

            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    def generate_report(self) -> str:
        """Generate a human-readable report."""
        report = []
        report.append("=" * 60)
        report.append("BARSYS APK BLE PROTOCOL ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")

        # 128-bit UUIDs
        report.append("## Custom 128-bit UUIDs (Likely Barsys Services)")
        report.append("-" * 40)
        if self.results["uuids_128bit"]:
            for uuid in sorted(self.results["uuids_128bit"]):
                report.append(f"  {uuid}")
        else:
            report.append("  None found")
        report.append("")

        # 16-bit UUIDs
        report.append("## Standard 16-bit Service UUIDs")
        report.append("-" * 40)
        if self.results["uuids_16bit"]:
            for uuid in sorted(self.results["uuids_16bit"]):
                service_name = STANDARD_SERVICES.get(uuid, "Custom/Vendor")
                report.append(f"  0x{uuid} - {service_name}")
        else:
            report.append("  None found")
        report.append("")

        # Bluetooth classes
        report.append("## Bluetooth-Related Classes")
        report.append("-" * 40)
        for class_name in self.results["bluetooth_classes"][:20]:
            report.append(f"  {class_name}")
        report.append("")

        # Write operations (potential command patterns)
        report.append("## BLE Write Operations (First 10)")
        report.append("-" * 40)
        for op in self.results["write_operations"][:10]:
            report.append(f"  {op['file']}:{op['line']}")
            report.append(f"    {op['code']}")
        report.append("")

        # Byte commands
        report.append("## Byte Array Commands (Potential Protocol Commands)")
        report.append("-" * 40)
        for cmd in self.results["byte_commands"][:15]:
            report.append(f"  {cmd['file']}:{cmd['line']}")
            report.append(f"    {cmd['bytes']}")
        report.append("")

        # API endpoints
        report.append("## API Endpoints")
        report.append("-" * 40)
        barsys_endpoints = [url for url in self.results["api_endpoints"] if 'barsys' in url.lower()]
        other_endpoints = [url for url in self.results["api_endpoints"] if 'barsys' not in url.lower()]

        report.append("  Barsys-specific:")
        for url in sorted(barsys_endpoints):
            report.append(f"    {url}")

        report.append("  Other:")
        for url in sorted(other_endpoints)[:10]:
            report.append(f"    {url}")
        report.append("")

        return "\n".join(report)

    def save_results(self, output_file: str):
        """Save results to JSON file."""
        # Convert sets to lists for JSON serialization
        json_results = {
            "uuids_128bit": list(self.results["uuids_128bit"]),
            "uuids_16bit": list(self.results["uuids_16bit"]),
            "bluetooth_classes": self.results["bluetooth_classes"],
            "write_operations": self.results["write_operations"][:50],
            "read_operations": self.results["read_operations"][:50],
            "byte_commands": self.results["byte_commands"][:50],
            "api_endpoints": list(self.results["api_endpoints"]),
        }

        with open(output_file, 'w') as f:
            json.dump(json_results, f, indent=2)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyze_ble_protocol.py <decompiled_source_dir>")
        print("Example: python analyze_ble_protocol.py ./barsys-decompiled/jadx")
        sys.exit(1)

    source_dir = sys.argv[1]

    if not os.path.exists(source_dir):
        print(f"Error: Directory '{source_dir}' does not exist")
        sys.exit(1)

    analyzer = BLEProtocolAnalyzer(source_dir)
    print("Starting BLE protocol analysis...")
    analyzer.analyze()

    # Generate and print report
    report = analyzer.generate_report()
    print(report)

    # Save detailed results
    output_json = os.path.join(os.path.dirname(source_dir), "ble_protocol_analysis.json")
    analyzer.save_results(output_json)
    print(f"\nDetailed results saved to: {output_json}")

    output_report = os.path.join(os.path.dirname(source_dir), "ble_protocol_report.txt")
    with open(output_report, 'w') as f:
        f.write(report)
    print(f"Report saved to: {output_report}")


if __name__ == "__main__":
    main()
