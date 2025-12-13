# Barsys 360 Protocol Research Findings

## Executive Summary

The Barsys 360 is a smart cocktail dispenser that uses **Bluetooth 5.0** for communication with mobile apps. No public API documentation exists, requiring reverse engineering to control the device programmatically.

---

## Device Specifications

| Specification | Value |
|---------------|-------|
| **Connectivity** | Bluetooth 5.0, WiFi (for cloud sync) |
| **Power** | 5V, 2A via USB-C |
| **Stations** | 6 ingredient stations |
| **Capacity** | 750ml (26oz) per station |
| **Dimensions** | 44cm x 20cm x 43cm |
| **Pump Type** | Likely peristaltic (based on similar devices) |

---

## App Information

### Android Apps

| App Name | Package | Purpose |
|----------|---------|---------|
| Barsys: Cocktail Crafting | `com.app.barsys` | Main app for 360 & Coaster 2.0 |
| Barsys Coaster | `com.llc.barsyscoaster` | Legacy coaster app |
| Barsys - Automated Cocktail Ma | `io.barsys.app.barsyseliten` | Business/commercial version |

### iOS Apps

| App ID | Purpose |
|--------|---------|
| `id6511230498` | Main Barsys app |
| `id1279140665` | Legacy app |

---

## Known API Endpoints

Based on web research:

```
api.barsys.com      - Main API (Laravel-based)
api.barsys.ai       - AI/ML features
dashboard.barsys.ai - Business dashboard
```

---

## BLE Protocol Analysis (Hypothetical)

Based on analysis of similar ESP32-based cocktail dispensers:

### Expected GATT Structure

```
Barsys 360 BLE Device
├── Generic Access Service (0x1800)
│   ├── Device Name Characteristic (0x2A00)
│   └── Appearance Characteristic (0x2A01)
│
├── Device Information Service (0x180A)
│   ├── Manufacturer Name (0x2A29) = "Barsys LLC"
│   ├── Model Number (0x2A24) = "360"
│   └── Firmware Revision (0x2A26)
│
└── Barsys Custom Service (128-bit UUID)
    ├── Command Characteristic (Write)
    │   └── Send dispense commands
    ├── Status Characteristic (Notify)
    │   └── Receive progress updates
    ├── Config Characteristic (Read/Write)
    │   └── Machine settings
    └── Ingredient Level Characteristic (Read/Notify)
        └── Current fill levels
```

### Probable Command Format

Based on similar pump-control devices:

```
Byte Structure:
┌──────────┬──────────┬───────────┬───────────┬──────────┐
│ Command  │ Station  │ Volume    │ Speed/    │ Checksum │
│ Type     │ Number   │ (ml)      │ Duration  │          │
│ (1 byte) │ (1 byte) │ (2 bytes) │ (2 bytes) │ (1 byte) │
└──────────┴──────────┴───────────┴───────────┴──────────┘

Example Commands:
0x01 - Start dispense
0x02 - Stop dispense
0x03 - Query status
0x04 - Set ingredient info
0x05 - Calibrate pump
0x10 - Start recipe
0x11 - Pause recipe
0x12 - Resume recipe
0xFF - Emergency stop
```

### Example Dispense Command

```python
# Hypothetical command to dispense 30ml from station 2
command = bytes([
    0x01,       # Command: Dispense
    0x02,       # Station: 2
    0x00, 0x1E, # Volume: 30ml (little-endian)
    0x00, 0x64, # Duration: 100ms per ml (little-endian)
    0x8F        # Checksum (XOR or sum)
])
```

---

## Reverse Engineering Approach

### Step 1: APK Analysis

```bash
# Download APK
# Visit: https://apkpure.com/barsys-cocktail-crafting/com.app.barsys/download

# Decompile with JADX
jadx -d barsys-source barsys.apk

# Search for BLE code
grep -r "BluetoothGatt" barsys-source/
grep -r "UUID" barsys-source/ | grep -i service
grep -rE "[0-9a-f]{8}-[0-9a-f]{4}" barsys-source/
```

### Step 2: Live BLE Scanning

```bash
# Use nRF Connect app on Android/iOS
# 1. Turn on Barsys 360
# 2. Scan for devices
# 3. Connect to "Barsys" device
# 4. Explore services and characteristics
# 5. Note all UUIDs
```

### Step 3: Traffic Capture

```bash
# Android HCI Snoop Log
# 1. Enable in Developer Options → Enable Bluetooth HCI snoop log
# 2. Use the Barsys app to dispense
# 3. Pull the log
adb pull /sdcard/btsnoop_hci.log

# Open in Wireshark
wireshark btsnoop_hci.log
# Filter: btatt (Bluetooth ATT protocol)
```

### Step 4: MITM Proxy for Cloud API

```bash
# Install mitmproxy
pip install mitmproxy

# Start proxy
mitmproxy -p 8080

# Configure Android to use proxy
# Install mitmproxy CA cert on device
# Capture app traffic to api.barsys.com
```

---

## Open Source Alternatives

These projects provide reference implementations for similar devices:

| Project | Hardware | Connectivity | Link |
|---------|----------|--------------|------|
| ESP32CocktailVendingMachine | ESP32 | Bluetooth | [GitHub](https://github.com/maxmacstn/ESP32CocktailVendingMachine) |
| Arduino_Cocktail_NANO | Arduino Nano + HC-05 | Bluetooth | [GitHub](https://github.com/Malte007/Arduino_Cocktail_NANO) |
| DIY Bar - Cocktail Machine | Various | WiFi/App | [Hackaday](https://hackaday.io/project/164892-diy-bar-cocktail-machine) |
| Bar Assistant | Web Server | REST API | [GitHub](https://github.com/karlomikus/bar-assistant) |

---

## ESP32 BLE Server Template

If building a compatible controller:

```cpp
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// Custom UUIDs (replace with actual Barsys UUIDs after discovery)
#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define COMMAND_CHAR_UUID   "12345678-1234-1234-1234-123456789abd"
#define STATUS_CHAR_UUID    "12345678-1234-1234-1234-123456789abe"

BLECharacteristic *pCommandChar;
BLECharacteristic *pStatusChar;

class CommandCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
        std::string value = pCharacteristic->getValue();
        if (value.length() > 0) {
            uint8_t cmd = value[0];
            uint8_t station = value[1];
            uint16_t volume = (value[3] << 8) | value[2];

            // Process command
            dispense(station, volume);
        }
    }
};

void setup() {
    BLEDevice::init("Barsys Clone");
    BLEServer *pServer = BLEDevice::createServer();

    BLEService *pService = pServer->createService(SERVICE_UUID);

    pCommandChar = pService->createCharacteristic(
        COMMAND_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    pCommandChar->setCallbacks(new CommandCallbacks());

    pStatusChar = pService->createCharacteristic(
        STATUS_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pStatusChar->addDescriptor(new BLE2902());

    pService->start();
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->start();
}
```

---

## Next Steps

1. **Download and analyze the APK** using tools in this directory
2. **Use nRF Connect** to scan the actual device
3. **Capture BLE traffic** during app usage
4. **Document discovered UUIDs** and command formats
5. **Build a test client** to verify protocol understanding

---

## Resources

- [Barsys Official](https://barsys.com/)
- [JADX Decompiler](https://github.com/skylot/jadx)
- [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-mobile)
- [Reverse Engineering BLE Devices](https://reverse-engineering-ble-devices.readthedocs.io/)
- [ESP32 BLE Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_gatts.html)

---

*Document generated: 2025-12-13*
*Status: Preliminary research - APK analysis pending*
