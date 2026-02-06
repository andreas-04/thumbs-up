#!/bin/bash
# Docker entrypoint for ThumbsUp
# Directly starts the Flask web server

set -e

# Set defaults if not provided
export ADMIN_PIN=${ADMIN_PIN:-1234}
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8080}

# Change to apiv2 directory (where core.server.py expects to run)
cd ./backend/apiv2

# Ensure directories exist
mkdir -p ./certs
mkdir -p ./storage

echo "========================================"
echo "ThumbsUp Web Server"
echo "========================================"
echo "Port: $PORT"
echo "Admin PIN: $(echo $ADMIN_PIN | sed 's/./*/g')"
echo ""

# Generate certificates if missing
if [ ! -f "./certs/server_cert.pem" ] || [ ! -f "./certs/server_key.pem" ]; then
    echo "Generating SSL certificates..."
    python3 utils/generate_certs.py --cert-path ./certs/server_cert.pem --key-path ./certs/server_key.pem
    echo "Certificates generated"
    echo ""
fi

# Verify certs were created
if [ ! -f "./certs/server_cert.pem" ] || [ ! -f "./certs/server_key.pem" ]; then
    echo "ERROR: Failed to generate certificates!"
    exit 1
fi

# Set cert paths relative to current directory (apiv2)
export CERT_PATH=./certs/server_cert.pem
export KEY_PATH=./certs/server_key.pem

echo "Starting Flask server on port $PORT..."
echo ""

# Start the Flask web server
exec python3 -m core.server
