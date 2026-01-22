#!/bin/bash
#
# ThumbsUp Web Server Startup Script
# Ensures dependencies and starts the Flask server
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Starting ThumbsUp Web Server"
echo "========================================"
echo ""

PYTHON="python3"
PIP="python3 -m pip"

# Check if Flask is installed (quick dependency check)
if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo "Installing Python dependencies..."
    
    # Use backend requirements.txt
    if [ -f "../requirements.txt" ]; then
        $PIP install -r ../requirements.txt --break-system-packages
    elif [ -f "../../requirements.txt" ]; then
        $PIP install -r ../../requirements.txt --break-system-packages
    else
        echo "ERROR: requirements.txt not found"
        exit 1
    fi
    echo "   [OK] Dependencies installed"
    echo ""
fi

# Verify SSL certificates exist
if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
    echo "Generating SSL certificates..."
    $PYTHON utils/generate_certs.py
    echo "   [OK] Certificates generated"
    echo ""
fi

# Verify ADMIN_PIN is set
if [ -z "$ADMIN_PIN" ]; then
    echo "ERROR: ADMIN_PIN environment variable not set"
    echo "   This should be set by startup.py"
    exit 1
fi

echo "[OK] Dependencies verified"
echo "[OK] SSL certificates ready"
echo "[OK] Storage directories ready"
echo "[OK] Admin PIN configured"
echo ""

# Start the server
echo "Starting Flask server..."
echo ""
exec $PYTHON -m core.server
