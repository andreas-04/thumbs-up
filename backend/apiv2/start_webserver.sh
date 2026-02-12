#!/bin/sh
set -e

echo "=========================================="
echo "Starting ThumbsUp Web Server"
echo "=========================================="
echo ""

PYTHON="python3"
PIP="python3 -m pip"

# Make certs directory if it doesn't exist
mkdir -p certs


# TODO: Installs handled in Dockerfile now - consider removing this entire dependency check block
# Check if Flask is installed (quick dependency check)
if ! $PYTHON -c "import flask" 2>/dev/null; then
    echo "Installing Python dependencies..."
    
    # Use backend requirements.txt
    if [ -f "../requirements.txt" ]; then
        $PIP install -r ../requirements.txt
    elif [ -f "../../requirements.txt" ]; then
        $PIP install -r ../../requirements.txt
    else
        echo "ERROR: requirements.txt not found"
        exit 2
    fi
    echo "   [OK] Dependencies installed"
    echo ""
fi

# Verify SSL certificates exist
if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
    echo "ERROR: SSL certificates not found in certs/ directory"
    exit 1
fi

if [ -z "" ]; then
    echo "ERROR: ADMIN_PIN environment variable not set"
    exit 1
fi

echo "[OK] SSL certificates verified"
echo "[OK] Admin PIN configured"
echo ""

echo "Starting Flask server..."
echo ""

exec python3 -m core.server
