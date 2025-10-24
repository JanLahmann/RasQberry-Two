# RasQberry Pi Imager Launcher Installer for Windows
#
# This script creates a Windows desktop shortcut with the RasQberry icon that opens
# Raspberry Pi Imager with the RasQberry custom image repository pre-loaded.
#
# USAGE:
#
#   OPTION 1 - One-line install (recommended):
#     Run this command in PowerShell (as Administrator):
#
#       Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://rasqberry.org/install-rpi-imager-launcher.ps1'))
#
#   OPTION 2 - Download, inspect, then run:
#     1. Download this script from:
#        https://rasqberry.org/install-rpi-imager-launcher.ps1
#
#     2. Right-click the file and select "Run with PowerShell"
#        (or run in PowerShell: .\install-rpi-imager-launcher.ps1)
#
# The installer will:
#   - Check if Raspberry Pi Imager is installed
#   - Download the RasQberry cube logo icon
#   - Create "Pi Imager for RasQberry" shortcut on your Desktop
#   - Apply the custom icon
#
# You can then pin the shortcut to Start Menu or Taskbar.
#
# REQUIREMENTS:
#   - Windows 10 or later
#   - Raspberry Pi Imager installed
#     Download from: https://www.raspberrypi.com/software/
#

Write-Host "Installing RasQberry Pi Imager Launcher..." -ForegroundColor Cyan
Write-Host ""

# Check for common installation paths
$imagerPaths = @(
    "${env:ProgramFiles(x86)}\Raspberry Pi Imager\rpi-imager.exe",
    "${env:ProgramFiles}\Raspberry Pi Imager\rpi-imager.exe",
    "${env:LOCALAPPDATA}\Programs\Raspberry Pi Imager\rpi-imager.exe"
)

$imagerPath = $null
foreach ($path in $imagerPaths) {
    if (Test-Path $path) {
        $imagerPath = $path
        break
    }
}

if (-not $imagerPath) {
    Write-Host "Error: Raspberry Pi Imager not found!" -ForegroundColor Red
    Write-Host "Please install it first from https://www.raspberrypi.com/software/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Checked locations:" -ForegroundColor Gray
    foreach ($path in $imagerPaths) {
        Write-Host "  - $path" -ForegroundColor Gray
    }
    exit 1
}

Write-Host "Found Raspberry Pi Imager at: $imagerPath" -ForegroundColor Green

# Create temporary directory
$tempDir = Join-Path $env:TEMP "rasqberry-installer-$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    # Download the RasQberry icon
    Write-Host "Downloading RasQberry icon..." -ForegroundColor Cyan
    $iconUrl = "https://rasqberry.org/Artwork/RasQberry%202%20Logo%20Cube%2064x64.png"
    $iconPath = Join-Path $tempDir "rasqberry-icon.png"

    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($iconUrl, $iconPath)
        $useCustomIcon = Test-Path $iconPath
    } catch {
        Write-Host "Warning: Could not download icon, using default" -ForegroundColor Yellow
        $useCustomIcon = $false
    }

    # Convert PNG to ICO if we have the icon
    $icoPath = $null
    if ($useCustomIcon) {
        Write-Host "Converting icon to Windows format..." -ForegroundColor Cyan

        # Try to use ImageMagick if available, otherwise use .NET
        $icoPath = Join-Path $tempDir "rasqberry-icon.ico"

        try {
            # Load the image using .NET
            Add-Type -AssemblyName System.Drawing
            $img = [System.Drawing.Image]::FromFile($iconPath)

            # Create icon from image
            $icon = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]$img).GetHicon())

            # Save as ICO
            $iconStream = [System.IO.FileStream]::new($icoPath, [System.IO.FileMode]::Create)
            $icon.Save($iconStream)
            $iconStream.Close()

            $img.Dispose()
            $icon.Dispose()
        } catch {
            Write-Host "Warning: Could not convert icon format" -ForegroundColor Yellow
            $useCustomIcon = $false
            $icoPath = $null
        }
    }

    # Create the desktop shortcut
    Write-Host "Creating desktop shortcut..." -ForegroundColor Cyan

    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "Pi Imager for RasQberry.lnk"

    $WScriptShell = New-Object -ComObject WScript.Shell
    $shortcut = $WScriptShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $imagerPath
    $shortcut.Arguments = "--repo https://RasQberry.org/RQB-images.json"
    $shortcut.Description = "Raspberry Pi Imager with RasQberry custom image repository"
    $shortcut.WorkingDirectory = Split-Path $imagerPath

    if ($useCustomIcon -and $icoPath -and (Test-Path $icoPath)) {
        $shortcut.IconLocation = $icoPath + ",0"
    } else {
        $shortcut.IconLocation = $imagerPath + ",0"
    }

    $shortcut.Save()

    # If using custom icon, copy it to a permanent location
    if ($useCustomIcon -and $icoPath -and (Test-Path $icoPath)) {
        $permanentIconDir = Join-Path $env:LOCALAPPDATA "RasQberry"
        New-Item -ItemType Directory -Path $permanentIconDir -Force | Out-Null
        $permanentIconPath = Join-Path $permanentIconDir "rasqberry-icon.ico"
        Copy-Item $icoPath $permanentIconPath -Force

        # Update shortcut to use permanent icon location
        $shortcut = $WScriptShell.CreateShortcut($shortcutPath)
        $shortcut.IconLocation = $permanentIconPath + ",0"
        $shortcut.Save()
    }

    Write-Host ""
    Write-Host "✓ Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The 'Pi Imager for RasQberry' shortcut has been created on your Desktop." -ForegroundColor White
    Write-Host "You can:" -ForegroundColor White
    Write-Host "  - Double-click it to launch Raspberry Pi Imager with RasQberry images" -ForegroundColor White
    Write-Host "  - Right-click and 'Pin to Start' for Start Menu access" -ForegroundColor White
    Write-Host "  - Right-click and 'Pin to taskbar' for Taskbar access" -ForegroundColor White
    Write-Host ""

    if (-not $useCustomIcon) {
        Write-Host "Note: Custom icon could not be applied. The shortcut uses the default Pi Imager icon." -ForegroundColor Yellow
        Write-Host ""
    }

} finally {
    # Cleanup temporary directory
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
