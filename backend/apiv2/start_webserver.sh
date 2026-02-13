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

# Make necessary directories if they don't exist
mkdir -p certs data storage


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
    echo "Generating SSL certificates..."
    $PYTHON utils/generate_certs.py 2>&1
    
    # Check if generation succeeded
    if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
        echo "ERROR: Certificate generation failed!"
        echo "Trying alternative method..."
        $PYTHON gen_selfsigned.py --output-dir certs 2>&1
        
        # Final check
        if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
            echo "ERROR: Could not generate certificates"
            exit 1
        fi
    fi
    
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
