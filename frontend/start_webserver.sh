#!/bin/sh
set -e

CERT_SRC_DIR="/app/pki"
CERT_DST_DIR="/etc/nginx/certs"

echo "=========================================="
echo "Starting ThumbsUp Frontend"
echo "=========================================="
echo ""

# Copy certs from build context if not already present
if [ ! -f "$CERT_DST_DIR/cert.pem" ] && [ -f "$CERT_SRC_DIR/server_cert.pem" ]; then
  echo "Copying server certificate..."
  cp "$CERT_SRC_DIR/server_cert.pem" "$CERT_DST_DIR/cert.pem"
fi

if [ ! -f "$CERT_DST_DIR/key.pem" ] && [ -f "$CERT_SRC_DIR/server_key.pem" ]; then
  echo "Copying server key..."
  cp "$CERT_SRC_DIR/server_key.pem" "$CERT_DST_DIR/key.pem"
fi

# Ensure certificate files exist
if [ ! -f "$CERT_DST_DIR/cert.pem" ] || [ ! -f "$CERT_DST_DIR/key.pem" ]; then
  echo "ERROR: TLS certificate or key not found in $CERT_DST_DIR"
  exit 1
fi

echo "[OK] Certificates verified"
echo "[OK] Starting Nginx..."
echo ""

exec nginx -g 'daemon off;'
