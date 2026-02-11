#!/bin/sh
set -e

echo "=========================================="
echo "Starting ThumbsUp Web Server"
echo "=========================================="
echo ""

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
