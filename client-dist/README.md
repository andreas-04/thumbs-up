# ThumbsUp Client

Secure NAS client for connecting to ThumbsUp devices using mDNS discovery and mTLS authentication.

## Features

- **Automatic Discovery**: Find ThumbsUp NAS devices on your network using mDNS/Avahi
- **Secure Authentication**: Mutual TLS (mTLS) certificate-based authentication
- **NFS File Sharing**: Mount and access files securely over NFS
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Installation

### Linux (Debian/Ubuntu)

```bash
# Download and install the .deb package
sudo dpkg -i thumbsup-client_1.0.0_amd64.deb

# Or install dependencies manually
sudo apt-get install python3 avahi-utils nfs-common
pip3 install thumbsup-client
```

### Windows

1. Download `ThumbsUp-Client-Setup.exe`
2. Run the installer
3. Follow the installation wizard
4. The NFS client feature will be enabled automatically

### macOS

```bash
# Coming soon
pip3 install thumbsup-client
```

## Usage

### Quick Start

```bash
# Discover and connect to ThumbsUp server automatically
thumbsup-client

# Or connect to specific host
thumbsup-client <hostname-or-ip> [port]
```

### What Happens

1. Client discovers ThumbsUp server via mDNS
2. Authenticates using client certificate
3. Server grants access and exports NFS share
4. Client mounts the share at `/mnt/nas` (Linux/macOS) or `Z:` (Windows)
5. You can browse and access files
6. On disconnect, share is unmounted and access is revoked

## System Requirements

### Linux
- Python 3.8+
- avahi-utils (for mDNS discovery)
- nfs-common (for NFS mounting)
- Root/sudo access (for mounting NFS shares)

### Windows
- Windows 10/11
- NFS Client feature (enabled automatically by installer)
- Administrator access (for NFS mounting)

### macOS
- macOS 10.15+
- Python 3.8+
- Avahi/Bonjour (built-in)
- NFS client (built-in)

## Certificates

The client requires three certificate files:
- `client_cert.pem` - Your client certificate
- `client_key.pem` - Your client private key
- `server_cert.pem` - Server's certificate (for validation)

These are bundled with the installer or can be obtained from your ThumbsUp administrator.

## Troubleshooting

### "No server found via mDNS"
- Ensure you're on the same network as the ThumbsUp server
- Check that the server is in ADVERTISING or ACTIVE state
- Verify mDNS/Avahi is working: `avahi-browse -a` (Linux)

### "avahi-browse not found"
- Install avahi-utils: `sudo apt-get install avahi-utils`

### "Permission denied" when mounting
- Ensure you're running with sudo: `sudo thumbsup-client`

### "Certificate verification failed"
- Ensure you have the correct server certificate
- Check certificate validity dates

## Development

```bash
# Clone the repository
git clone https://github.com/andreas-04/thumbs-up.git
cd thumbs-up/client-dist

# Install in development mode
pip install -e .

# Run from source
python -m thumbsup_client.client
```

## License

MIT License - see LICENSE file for details
