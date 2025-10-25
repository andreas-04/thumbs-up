# Building ThumbsUp Client Installers

This directory contains the packaging and distribution setup for the ThumbsUp Client.

## Prerequisites

### For .deb (Linux/Debian/Ubuntu)
```bash
sudo apt-get install dpkg-dev debhelper dh-python python3-all python3-setuptools
```

### For .exe (Windows)
- Python 3.8 or later
- PyInstaller: `pip install pyinstaller`
- NSIS (Nullsoft Scriptable Install System): https://nsis.sourceforge.io/Download

## Building

### Linux .deb Package

```bash
# On Linux (Debian/Ubuntu)
./build-deb.sh
```

Output: `dist/thumbsup-client_0.0.0-1_all.deb`

### Windows .exe Installer

```bash
# On Windows
build-windows.bat
```

Output: `dist/ThumbsUp-Client-Setup.exe`

## Testing

### Test .deb in Docker

```bash
# Build the package first
./build-deb.sh

# Test in Ubuntu container
docker run --rm -v $(pwd)/dist:/dist -it ubuntu:22.04 bash

# Inside container:
apt-get update
apt-get install -y /dist/thumbsup-client_0.0.0-1_all.deb
thumbsup-client --help
```

### Test .exe on Windows

1. Build the installer: `build-windows.bat`
2. Run `dist\ThumbsUp-Client-Setup.exe` as Administrator
3. Place test certificates in `C:\Program Files\ThumbsUp Client\certs\`
4. Open Command Prompt as Administrator
5. Run: `thumbsup-client`

## Directory Structure

```
client-dist/
├── src/
│   └── thumbsup_client/
│       ├── __init__.py
│       └── client.py           # Main client code
├── debian/
│   ├── control                 # Package metadata
│   ├── rules                   # Build rules
│   ├── changelog               # Version history
│   ├── compat                  # Debhelper compatibility
│   └── postinst                # Post-installation script
├── setup.py                    # Python package setup
├── README.md                   # User documentation
├── LICENSE                     # MIT License
├── thumbsup-client.spec        # PyInstaller specification
├── installer.nsi               # NSIS installer script
├── version_info.txt            # Windows version info
├── build-deb.sh                # Linux build script
├── build-windows.bat           # Windows build script
└── BUILD.md                    # This file
```

## Distributing

### Linux
Upload the .deb to:
- GitHub Releases
- Personal package repository (PPA)
- Direct download from website

### Windows
Upload the .exe to:
- GitHub Releases
- Direct download from website
- Microsoft Store (future)

## CI/CD

See `../.github/workflows/` for automated build pipelines using GitHub Actions.
