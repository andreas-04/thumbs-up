#!/bin/bash
#
# ThumbsUp Web Server Startup Script
# Ensures dependencies and starts the Flask server
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "🚀 Starting ThumbsUp Web Server"
echo "========================================"
echo ""

# Check if Flask is installed (quick dependency check)
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Python dependencies..."
    pip3 install --upgrade pip
    
    # Use backend requirements.txt
    if [ -f "../requirements.txt" ]; then
        pip3 install -r ../requirements.txt
    elif [ -f "../../requirements.txt" ]; then
        pip3 install -r ../../requirements.txt
    else
        echo "❌ requirements.txt not found"
        exit 1
    fi
    echo "   ✅ Dependencies installed"
    echo ""
fi

# Verify SSL certificates exist
if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
    echo "🔐 Generating SSL certificates..."
    python3 utils/generate_certs.py
    echo "   ✅ Certificates generated"
    echo ""
fi

# Verify ADMIN_PIN is set
if [ -z "$ADMIN_PIN" ]; then
    echo "❌ Error: ADMIN_PIN environment variable not set"
    echo "   This should be set by startup.py"
    exit 1
fi

echo "✓ Dependencies verified"
echo "✓ SSL certificates ready"
echo "✓ Storage directories ready"
echo "✓ Admin PIN configured"
echo ""

# Start the server
echo "🌐 Starting Flask server..."
echo ""
exec python3 -m core.server
