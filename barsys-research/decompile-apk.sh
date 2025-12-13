#!/bin/bash
# Barsys APK Decompilation Script
# This script helps decompile the Barsys app to extract BLE protocol information

set -e

APK_NAME="barsys.apk"
OUTPUT_DIR="barsys-decompiled"
PACKAGE_NAME="com.app.barsys"

echo "=== Barsys APK Decompilation Script ==="
echo ""

# Step 1: Install required tools
install_tools() {
    echo "[1/5] Installing decompilation tools..."

    # Check if running as root or with sudo
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y openjdk-17-jdk unzip wget curl

        # Install JADX (Java Decompiler)
        if [ ! -f /usr/local/bin/jadx ]; then
            echo "Installing JADX..."
            JADX_VERSION="1.5.0"
            wget -q "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" -O /tmp/jadx.zip
            sudo unzip -o /tmp/jadx.zip -d /opt/jadx
            sudo ln -sf /opt/jadx/bin/jadx /usr/local/bin/jadx
            sudo ln -sf /opt/jadx/bin/jadx-gui /usr/local/bin/jadx-gui
            rm /tmp/jadx.zip
        fi

        # Install apktool
        if [ ! -f /usr/local/bin/apktool ]; then
            echo "Installing apktool..."
            sudo wget -q "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool" -O /usr/local/bin/apktool
            sudo wget -q "https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar" -O /usr/local/bin/apktool.jar
            sudo chmod +x /usr/local/bin/apktool
        fi

        echo "Tools installed successfully!"
    else
        echo "Please install jadx and apktool manually"
        exit 1
    fi
}

# Step 2: Download APK
download_apk() {
    echo "[2/5] Downloading Barsys APK..."

    if [ -f "$APK_NAME" ]; then
        echo "APK already exists, skipping download"
        return
    fi

    # Try using apkeep if available
    if command -v apkeep &> /dev/null; then
        apkeep -a "$PACKAGE_NAME" . && mv "${PACKAGE_NAME}"*.apk "$APK_NAME"
    else
        echo ""
        echo "Please download the APK manually from:"
        echo "  https://apkpure.com/barsys-cocktail-crafting/com.app.barsys/download"
        echo ""
        echo "Save it as: $APK_NAME"
        echo "Then run this script again."
        exit 1
    fi
}

# Step 3: Decompile with JADX (Java source)
decompile_jadx() {
    echo "[3/5] Decompiling APK with JADX (Java source)..."

    if [ ! -f "$APK_NAME" ]; then
        echo "Error: $APK_NAME not found!"
        exit 1
    fi

    mkdir -p "${OUTPUT_DIR}/jadx"
    jadx -d "${OUTPUT_DIR}/jadx" "$APK_NAME" --show-bad-code 2>/dev/null || true

    echo "Java source extracted to: ${OUTPUT_DIR}/jadx"
}

# Step 4: Decompile with apktool (resources + smali)
decompile_apktool() {
    echo "[4/5] Decompiling APK with apktool (resources)..."

    mkdir -p "${OUTPUT_DIR}/apktool"
    apktool d -f "$APK_NAME" -o "${OUTPUT_DIR}/apktool" 2>/dev/null || true

    echo "Resources extracted to: ${OUTPUT_DIR}/apktool"
}

# Step 5: Extract BLE-related information
extract_ble_info() {
    echo "[5/5] Extracting BLE protocol information..."

    REPORT_FILE="${OUTPUT_DIR}/ble-analysis-report.txt"

    echo "=== Barsys BLE Protocol Analysis ===" > "$REPORT_FILE"
    echo "Generated: $(date)" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for UUIDs (128-bit format)
    echo "--- 128-bit UUIDs Found ---" >> "$REPORT_FILE"
    grep -rhoE '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}' "${OUTPUT_DIR}/jadx" 2>/dev/null | sort -u >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for 16-bit UUIDs (BLE standard services)
    echo "--- 16-bit Service UUIDs (0x####) ---" >> "$REPORT_FILE"
    grep -rhoE '0x1[89a-fA-F][0-9a-fA-F]{2}' "${OUTPUT_DIR}/jadx" 2>/dev/null | sort -u >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for Bluetooth-related classes
    echo "--- Bluetooth Classes Used ---" >> "$REPORT_FILE"
    grep -rhl "BluetoothGatt\|BluetoothDevice\|BluetoothAdapter" "${OUTPUT_DIR}/jadx" 2>/dev/null | head -20 >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for characteristic operations
    echo "--- Write/Read Characteristic Operations ---" >> "$REPORT_FILE"
    grep -rn "writeCharacteristic\|readCharacteristic\|setCharacteristicNotification" "${OUTPUT_DIR}/jadx" 2>/dev/null | head -50 >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for command-like byte arrays
    echo "--- Command Byte Arrays ---" >> "$REPORT_FILE"
    grep -rnoE 'new byte\[\]\s*\{[^}]+\}' "${OUTPUT_DIR}/jadx" 2>/dev/null | head -30 >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for API endpoints
    echo "--- API Endpoints ---" >> "$REPORT_FILE"
    grep -rhoE 'https?://[^"'\''[:space:]]+' "${OUTPUT_DIR}/jadx" 2>/dev/null | sort -u >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Search for BLE service names
    echo "--- BLE Service/Characteristic Names ---" >> "$REPORT_FILE"
    grep -rinE 'service.*uuid|characteristic.*uuid|gatt.*service' "${OUTPUT_DIR}/jadx" 2>/dev/null | head -30 >> "$REPORT_FILE" || echo "None found" >> "$REPORT_FILE"

    echo ""
    echo "Analysis report saved to: $REPORT_FILE"
    cat "$REPORT_FILE"
}

# Main execution
main() {
    mkdir -p "$(dirname "$OUTPUT_DIR")"
    cd "$(dirname "$0")"

    case "${1:-all}" in
        install)
            install_tools
            ;;
        download)
            download_apk
            ;;
        decompile)
            decompile_jadx
            decompile_apktool
            ;;
        analyze)
            extract_ble_info
            ;;
        all)
            install_tools
            download_apk
            decompile_jadx
            decompile_apktool
            extract_ble_info
            ;;
        *)
            echo "Usage: $0 {install|download|decompile|analyze|all}"
            exit 1
            ;;
    esac
}

main "$@"
