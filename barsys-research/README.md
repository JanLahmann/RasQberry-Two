# Barsys 360 APK Decompilation & Protocol Analysis

This directory contains tools for reverse engineering the Barsys 360 cocktail machine's BLE protocol.

## Quick Start

### Option 1: Automated (Linux)

```bash
# Make script executable
chmod +x decompile-apk.sh

# Run everything (install tools, download APK, decompile, analyze)
./decompile-apk.sh all

# Or run steps individually:
./decompile-apk.sh install    # Install jadx and apktool
./decompile-apk.sh download   # Download the APK
./decompile-apk.sh decompile  # Decompile with jadx + apktool
./decompile-apk.sh analyze    # Extract BLE protocol info
```

### Option 2: Manual Steps

#### 1. Install Tools

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y openjdk-17-jdk unzip wget

# Install JADX
wget https://github.com/skylot/jadx/releases/download/v1.5.0/jadx-1.5.0.zip
unzip jadx-1.5.0.zip -d jadx
export PATH=$PATH:$(pwd)/jadx/bin

# Install apktool
wget https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar -O apktool.jar
wget https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool
chmod +x apktool
```

**macOS:**
```bash
brew install jadx apktool
```

**Windows:**
- Download JADX: https://github.com/skylot/jadx/releases
- Download apktool: https://apktool.org/docs/install

#### 2. Download the APK

Download from APKPure:
- https://apkpure.com/barsys-cocktail-crafting/com.app.barsys/download

Or use a downloader tool:
```bash
pip install apkeep
apkeep -a com.app.barsys .
```

#### 3. Decompile the APK

**With JADX (Java source code):**
```bash
jadx -d barsys-source barsys.apk
```

**With apktool (Resources + Smali):**
```bash
apktool d barsys.apk -o barsys-resources
```

**Using JADX GUI (visual exploration):**
```bash
jadx-gui barsys.apk
```

#### 4. Analyze the Protocol

```bash
python3 analyze_ble_protocol.py ./barsys-source
```

## What to Look For

### BLE UUIDs
Look in files containing "Bluetooth", "BLE", "GATT":
```bash
# Find BLE-related files
find barsys-source -name "*.java" | xargs grep -l "BluetoothGatt\|BleManager"

# Extract UUIDs
grep -rhoE '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' barsys-source | sort -u
```

### Command Structures
```bash
# Find byte array commands
grep -rn "new byte\[\]" barsys-source | head -50

# Find write operations
grep -rn "writeCharacteristic" barsys-source
```

### API Endpoints
```bash
grep -rhoE 'https?://[^"'\''[:space:]]+barsys[^"'\''[:space:]]*' barsys-source | sort -u
```

## Expected Protocol Structure

Based on similar devices, expect something like:

```
BLE Service Structure:
├── Generic Access (0x1800) - Standard
├── Device Information (0x180A) - Standard
└── Barsys Custom Service (128-bit UUID)
    ├── Command Characteristic (Write)
    │   - Pump control commands
    │   - Recipe execution
    │   - Calibration
    ├── Status Characteristic (Notify)
    │   - Dispensing progress
    │   - Error codes
    └── Config Characteristic (Read/Write)
        - Ingredient levels
        - Machine settings
```

### Typical Command Format
```
[CMD_TYPE][STATION][VOLUME_MSB][VOLUME_LSB][DURATION_MSB][DURATION_LSB][CHECKSUM]

Example:
0x01 0x02 0x00 0x1E 0x00 0x64 0xXX
│    │    │         │         │
│    │    │         │         └── Checksum
│    │    │         └── Duration: 100ms
│    │    └── Volume: 30ml
│    └── Station 2
└── Dispense command
```

## Files in This Directory

| File | Description |
|------|-------------|
| `decompile-apk.sh` | Automated decompilation script (Linux) |
| `analyze_ble_protocol.py` | Python BLE protocol analyzer (for decompiled source) |
| `download_and_analyze.py` | **NEW**: All-in-one download + analyze script |
| `BARSYS_PROTOCOL_FINDINGS.md` | Comprehensive protocol research findings |
| `README.md` | This file |

## Quickest Method (Python only)

```bash
# Just run this - it handles everything
python3 download_and_analyze.py
```

This script will:
1. Attempt to download the APK
2. Extract and analyze the contents
3. Search for BLE UUIDs and commands
4. Generate a detailed report

## Alternative: Live BLE Sniffing

If APK analysis doesn't reveal enough, try live sniffing:

1. **nRF Connect** (Android/iOS app)
   - Scan for "Barsys" device
   - Connect and explore services
   - Note all UUIDs

2. **Wireshark + nRF Sniffer**
   - Capture actual BLE traffic
   - See real command/response patterns

3. **Android HCI Snoop Log**
   ```bash
   # Enable in Android Developer Options
   adb pull /sdcard/btsnoop_hci.log
   # Open in Wireshark
   ```

## Resources

- [JADX Documentation](https://github.com/skylot/jadx)
- [apktool Documentation](https://apktool.org/)
- [Reverse Engineering BLE Devices](https://reverse-engineering-ble-devices.readthedocs.io/)
- [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
