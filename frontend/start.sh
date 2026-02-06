#!/bin/sh
# Start script for ThumbsUp Frontend container
# 1. Generate certificates if not present
# 2. Place certs in /app/certs
# 3. Start the frontend server (adjust as needed)

set -e

CERT_DIR="/app/certs"
mkdir -p "$CERT_DIR"

# Generate certs if missing
if [ ! -f "$CERT_DIR/server_cert.pem" ] || [ ! -f "$CERT_DIR/server_key.pem" ]; then
    echo "Generating self-signed certificates..."
    python gen_selfsigned.py --output-dir "$CERT_DIR"
fi

echo "Certificates ready in $CERT_DIR"

# Start the frontend server (adjust as needed)
# Example: Flask app (uncomment and edit if you have app.py)
# exec python app.py

# Default: serve static files
exec python -m http.server 8080
