# ThumbsUp API v2 - Ad-Hoc File Sharing Server

A lightweight, secure HTTP file server for instant file sharing via QR codes.

## Features

- 🌐 **HTTP File Browser**: Access files from any web browser
- 🔒 **HTTPS Encryption**: Self-signed certificates for secure connections
- 🎫 **Token-based Access**: Time-limited tokens via QR codes
- 📱 **QR Code Generation**: Instant sharing with nearby users
- 🔍 **mDNS Discovery**: Automatic discovery on local networks
- 📤 **Upload/Download**: Full file management via web UI
- 🖥️ **Cross-Platform**: Works on Windows, macOS, Linux, iOS, Android
- 🗂️ **SMB Support**: Mount as network drive via SMB3 with NTLMv2 authentication

## Quick Start

### Prerequisites

- Python 3.8+
- Avahi daemon (for mDNS on Linux/macOS)
- Bonjour (built-in on macOS, install on Windows)

### Installation

```bash
cd backend/apiv2
pip install -r requirements.txt

# Generate self-signed certificates
python generate_certs.py

# Start the server
python server.py
```

### Access Methods

#### Web Browser (All Devices)
1. Scan the QR code displayed on server startup
2. Or navigate to: `https://<hostname>.local:8443`
3. Accept the self-signed certificate warning
4. Browse, upload, and download files

#### Network Drive (SMB)

For mounting as a network drive, use the SMB service (port 445) which will be advertised via mDNS.
SMB implementation coming soon with NTLMv2 authentication.

## Configuration

Edit `.env` file to customize:

```env
# Server Configuration
HOST=0.0.0.0
PORT=8443
STORAGE_PATH=./storage

# Security
TOKEN_EXPIRY_HOURS=24
ENABLE_UPLOADS=true
ENABLE_DELETE=false

# mDNS Service Name
SERVICE_NAME=ThumbsUp File Share
```

## Architecture

```
apiv2/
├── server.py              # Main Flask application
├── auth.py                # Token authentication
├── qr_generator.py        # QR code generation
├── mdns_advertiser.py     # Avahi/mDNS service advertisement
├── generate_certs.py      # SSL certificate generator
├── certs/                 # SSL certificates (auto-generated)
├── storage/               # Shared files directory
├── static/                # Web UI assets
└── templates/             # HTML templates
```

## API Endpoints

### HTTP File Server

- `GET /` - Web file browser UI
- `GET /files/<path>` - Download file
- `POST /upload` - Upload file (multipart/form-data)
- `DELETE /files/<path>` - Delete file (if enabled)
- `GET /qr` - Generate QR code for current access URL

### WebDAV

- `PROPFIND /webdav` - List directory
- `GET /webdav/<path>` - Download file
- `PUT /webdav/<path>` - Upload file
- `DELETE /webdav/<path>` - Delete file
- `MKCOL /webdav/<path>` - Create directory

All endpoints require valid access token (via URL parameter or Authorization header).

## Security Features

1. **HTTPS Only**: All traffic encrypted with TLS 1.2+
2. **Time-Limited Tokens**: JWT tokens with configurable expiry
3. **Access Logging**: All requests logged with timestamps
4. **IP Rate Limiting**: Prevent brute force attacks
5. **File Permissions**: Configurable read/write/delete access
6. **Network Isolation**: Bind to specific interface only

## Troubleshooting

### Certificate Warnings

Self-signed certificates will trigger browser warnings. This is expected. Click "Advanced" → "Proceed" to continue.

### mDNS Not Working

**Linux:**
```bash
sudo systemctl start avahi-daemon
sudo systemctl enable avahi-daemon
```

**macOS:**
mDNS (Bonjour) is built-in, no action needed.

**Windows:**
Install Bonjour Print Services or iTunes to get mDNS support.

### WebDAV Connection Issues

- Ensure you're using `https://` not `http://`
- Use the full path: `https://hostname:8443/webdav`
- Some older Windows versions only support HTTP WebDAV (use web UI instead)

## Development

### Run in Debug Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python server.py
```

### Run Tests

```bash
pytest tests/
```

## License

MIT License - See LICENSE file for details
