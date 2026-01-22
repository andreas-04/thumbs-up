#!/bin/bash
#
# ThumbsUp SMB Server Startup Script
# Ensures Samba dependencies and starts the SMB service
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Starting ThumbsUp SMB Server"
echo "========================================"
echo ""

PYTHON="python3"
PIP="python3 -m pip"

# Check if running on Linux (Raspberry Pi)
OS="$(uname -s)"
if [ "$OS" != "Linux" ]; then
    echo "ERROR: This script only supports Linux (Raspberry Pi)"
    echo "   Detected OS: $OS"
    exit 1
fi

echo "Detected OS: Linux (Raspberry Pi)"
echo ""

# Check if Samba is installed
if ! command -v smbd &> /dev/null; then
    echo "Samba not found. Installing..."
    echo ""
    
    # Detect Linux distribution
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian|raspbian)
                echo "Installing Samba on Debian/Ubuntu/Raspbian..."
                sudo apt-get update
                sudo apt-get install -y samba samba-common-bin
                ;;
            *)
                echo "WARNING: Unsupported Linux distribution: $ID"
                echo "   This script is designed for Raspberry Pi OS (Debian-based)"
                echo "   Please install Samba manually:"
                echo "   sudo apt-get install samba samba-common-bin"
                exit 1
                ;;
        esac
    else
        echo "WARNING: Cannot detect Linux distribution"
        echo "   Attempting Debian/Ubuntu installation..."
        sudo apt-get update
        sudo apt-get install -y samba samba-common-bin || {
            echo "ERROR: Installation failed"
            echo "   Please install Samba manually"
            exit 1
        }
    fi
    
    echo ""
    echo "[OK] Samba installed successfully"
    echo ""
else
    echo "[OK] Samba already installed"
    echo ""
fi

# Check if smbpasswd is available
if ! command -v smbpasswd &> /dev/null; then
    echo "WARNING: smbpasswd command not found"
    echo "   SMB user creation may fail"
fi

# Check Python dependencies
if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo "Installing Python dependencies..."
    
    # Use parent requirements.txt if available
    if [ -f "../requirements.txt" ]; then
        $PIP install -r ../requirements.txt --break-system-packages
    elif [ -f "requirements.txt" ]; then
        $PIP install -r requirements.txt --break-system-packages
    else
        echo "WARNING: requirements.txt not found"
        echo "   Installing minimal dependencies..."
        $PIP install flask flask-cors --break-system-packages
    fi
    echo "   [OK] Dependencies installed"
    echo ""
fi

# Verify storage directory exists
if [ ! -d "$SCRIPT_DIR/storage" ]; then
    echo "Creating storage directory..."
    mkdir -p "$SCRIPT_DIR/storage/documents"
    mkdir -p "$SCRIPT_DIR/storage/music"
    echo "   [OK] Storage directories created"
    echo ""
fi

# Verify SMB config directory will be created
mkdir -p "$SCRIPT_DIR/services/smb_config"

# Check for required environment variables
if [ -z "$SMB_GUEST_USER" ]; then
    export SMB_GUEST_USER="guest"
fi

if [ -z "$SMB_GUEST_PASSWORD" ]; then
    export SMB_GUEST_PASSWORD="guest"
fi

echo "[OK] Samba installed and ready"
echo "[OK] Python dependencies verified"
echo "[OK] Storage directories ready"
echo "[OK] SMB credentials configured"
echo "   Username: $SMB_GUEST_USER"
echo "   Password: $SMB_GUEST_PASSWORD"
echo ""

# Check if running with appropriate permissions
if [ "$OS" = "Linux" ] && [ "$EUID" -ne 0 ]; then
    echo "NOTE: SMB server may require sudo on Linux"
    echo "   If you encounter permission errors, run with:"
    echo "   sudo -E bash $0"
    echo ""
fi

echo "[OK] Samba installed and ready"
echo "[OK] Python dependencies verified"
echo "[OK] Storage directories ready"
echo "[OK] SMB credentials configured"
echo "   Username: $SMB_GUEST_USER"
echo "   Password: $SMB_GUEST_PASSWORD"
echo ""

# Check if running with appropriate permissions
if [ "$EUID" -ne 0 ]; then
    echo "NOTE: SMB server may require sudo for port 445"
    echo "   If you encounter permission errors, run with:"
    echo "   sudo -E bash $0"
    echo ""
fi

# Start the SMB service
echo "Starting SMB service..."
echo ""
exec $PYTHON -m services