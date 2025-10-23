# mTLS Docker Setup

This directory contains Docker configurations for running the mTLS client and server in containers using Ubuntu as the base image.

## Prerequisites

- Docker installed on your system
- Docker Compose installed
- SSL certificates generated (run `python gen_selfsigned.py` from the parent directory if not already done)

## Files

- `Dockerfile.server` - Docker configuration for the mTLS server
- `Dockerfile.client` - Docker configuration for the mTLS client
- `docker-compose.yml` - Orchestration configuration for both containers
- `.dockerignore` - Files to exclude from Docker build context

## Quick Start

### 1. Generate Certificates (if not already done)

From the `internal/pki` directory:
```bash
cd ..
python3 gen_selfsigned.py
cd example
```

### 2. Build and Run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Build both server and client images
- Start the mTLS server on port 8443 with Avahi mDNS support
- Start the client which connects to the server
- Display the mTLS handshake and message exchange
- Broadcast mDNS announcements when clients successfully connect

### 3. Stop the Containers

```bash
docker-compose down
```

## Running Containers Individually

### Build the Server Image
```bash
docker build -f Dockerfile.server -t mtls-server .
```

### Build the Client Image
```bash
docker build -f Dockerfile.client -t mtls-client .
```

### Run the Server Container
```bash
docker run -p 8443:8443 --name mtls-server mtls-server
```

### Run the Client Container
```bash
docker run --network container:mtls-server --name mtls-client mtls-client
```

Or with custom host:
```bash
docker run --name mtls-client mtls-client python3 -c "from mtls_client import run_mtls_client; run_mtls_client(host='<server-ip>', port=8443)"
```

## Network Configuration

The containers use a custom bridge network (`mtls-network`) that allows the client to connect to the server using the service name `mtls-server` as the hostname.

## mDNS/Avahi Support

The server broadcasts mDNS announcements using Avahi when a client successfully connects:
- Service type: `_mtls._tcp`
- Service name: `mTLS-Connection-{ClientCN}`
- TXT record includes: client CN and connection timestamp
- Port 5353/UDP is exposed for mDNS traffic

### Discovering mDNS Services

From the host machine (if Avahi is installed):
```bash
avahi-browse -r _mtls._tcp
```

From another container on the same network:
```bash
docker run --rm --network pki_example_mtls-network alpine/avahi avahi-browse -r _mtls._tcp
```

## Troubleshooting

### Certificate Issues
Make sure all certificate files exist in the parent directory:
- `server_cert.pem`
- `server_key.pem`
- `client_cert.pem`
- `client_key.pem`

### Connection Issues
- Ensure the server container is running before starting the client
- Check that port 8443 is not already in use
- Verify the certificates are valid and not expired

### View Container Logs
```bash
docker-compose logs mtls-server
docker-compose logs mtls-client
```

### mDNS Not Broadcasting
- Ensure port 5353/UDP is not blocked by firewall
- Check Avahi daemon is running: `docker exec mtls-server ps aux | grep avahi`
- Verify D-Bus is running: `docker exec mtls-server ps aux | grep dbus`
- Check logs: `docker exec mtls-server journalctl -u avahi-daemon` (if available)

## Security Notes

⚠️ These are self-signed certificates for testing purposes only. In production:
- Use proper CA-signed certificates
- Enable hostname verification
- Use secure key storage
- Regularly rotate certificates
