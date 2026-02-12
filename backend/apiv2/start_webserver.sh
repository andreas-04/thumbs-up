#!/bin/sh
set -e

echo "=========================================="
echo "Starting ThumbsUp Web Server"
echo "=========================================="
echo ""

# Make certs directory if it doesn't exist
mkdir -p certs

# Generate SSL certificates if they don't exist
if [ ! -f "certs/server_cert.pem" ] || [ ! -f "certs/server_key.pem" ]; then
    echo "Generating SSL certificates..."
    python3 gen_selfsigned.py --output-dir certs --server-cn localhost
    echo "   [OK] Certificates generated"
    echo ""
fi

echo "[OK] Flask server starting on https://localhost:8443"
echo ""
echo "=========================================="
echo "Access the web interface:"
echo "  https://localhost:8443"
echo "=========================================="
echo "Admin PIN: 1234"
echo ""

exec python3 -m core.server 
