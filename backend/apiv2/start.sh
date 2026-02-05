#!/bin/sh
# Start script for ThumbsUp backend API v2 webserver
# 1. Install dependencies
# 2. Generate certificates if not present
# 3. Start the Flask server on port 8443 (HTTPS)

set -e

CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

# Install dependencies
echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Generate certs if missing
if [ ! -f "$CERT_DIR/server_cert.pem" ] || [ ! -f "$CERT_DIR/server_key.pem" ]; then
    echo "Generating SSL certificates..."
    python gen_selfsigned.py --output-dir "$CERT_DIR" --server-cn "thumbsup"
fi

echo "Certificates ready in $CERT_DIR"
echo ""

# Verify ADMIN_PIN is set (should be set by Docker env or caller)
if [ -z "$ADMIN_PIN" ]; then
    echo "ERROR: ADMIN_PIN environment variable not set"
    exit 1
fi

echo "Starting ThumbsUp Web Server..."
echo "ADMIN_PIN configured"
echo ""

# Start the Flask server
exec python -m core.server
