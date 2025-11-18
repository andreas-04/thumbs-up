# ThumbsUp 👍

[![Client Distribution CI/CD](https://github.com/andreas-04/thumbs-up/actions/workflows/distribution-ci.yml/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/distribution-ci.yml)

**Your files, your device, your network. No cloud required.**

ThumbsUp is a secure, portable Wi-Fi NAS that you control. Think of it as a smart USB drive that appears on your network when you need it and disappears when you don't.

## What is this?

Ever wish you could share files between your devices without uploading them to someone else's servers? That's ThumbsUp. It's a Raspberry Pi (or similar device) with a USB drive attached that creates a secure file-sharing hub on your local network.

## Why would I use this?

- **Privacy first** - Your files never leave your physical possession
- **No internet needed** - Works entirely on your local WiFi
- **Secure by design** - Certificate-based authentication (mutual TLS)
- **On-demand** - Only visible when you want it to be
- **Open source** - You can see exactly what it does

Perfect for:
- Sharing files between your own devices
- Backing up data without cloud services
- Field work where internet isn't available
- Anyone who wants control over their data

## How does it work?

1. **Dormant** - The device sits quietly, not advertising itself
2. **Activated** - You press the button (or send a signal)
3. **Discovered** - Your devices see it on the network via mDNS
4. **Authenticated** - Only devices with valid certificates can connect
5. **Access** - Mount and access files via NFS
6. **Done** - Disconnect when finished, device goes dormant again

All connections are secured with mutual TLS authentication, and a firewall ensures only authenticated clients can access your files.

## Quick Start

### Easy Web Access (No Installation!) 🌐

**The easiest way to access your files:**

1. Start the server:
   ```bash
   cd backend/api
   docker-compose up
   ```

2. Open any web browser and visit:
   ```
   http://<server-ip>:8080
   ```

3. That's it! Browse and download files instantly.

**Bonus:** Click "Show QR Code" in the web interface to generate a QR code for instant mobile access!

See [backend/WEB_ACCESS.md](backend/WEB_ACCESS.md) for detailed web access guide.

### For the Server (Raspberry Pi or similar)

```bash
cd backend/api
docker-compose up
```

See [backend/README.md](backend/README.md) for detailed setup.

### For the Client (Your devices)

We provide installers for:
- **Debian/Ubuntu** - `.deb` package
- **Windows** - `.exe` installer
- **macOS** - Python client (for now)

Check out [distribution/README.md](distribution/README.md) for installation instructions.

## Project Structure

```
thumbs-up/
├── backend/          # The NAS server that runs on the Pi
│   ├── api/          # Docker-based server and client
│   ├── config/       # mDNS and system configs
│   └── pki/          # Certificate management
├── distribution/     # Build scripts for client installers
├── frontend/         # Web UI (coming soon)
└── docs/             # Architecture and design docs
```

## Features

### Current (MVP)
- ✅ State machine architecture (dormant → active → shutdown)
- ✅ Mutual TLS authentication
- ✅ mDNS service discovery (Avahi)
- ✅ Dynamic firewall rules per client
- ✅ NFS file sharing
- ✅ Multi-client support
- ✅ Docker deployment

### Planned
- 🔲 Encrypted storage
- 🔲 Time-based access control
- 🔲 Certificate revocation
- 🔲 Web UI for management
- 🔲 Peer-to-peer sync between devices
- 🔲 Secure OTA updates

## Security

Security isn't an afterthought—it's the foundation:

- **Mutual TLS** - Both client and server authenticate each other
- **Certificate-based auth** - No passwords to steal or guess
- **Per-client firewall rules** - Dynamic iptables management
- **Local-only** - No external services or cloud dependencies
- **Transparent** - Open source, auditable code

See [docs/architecture.md](docs/architecture.md) for the full security model.

## Documentation

- [Architecture Overview](docs/architecture.md) - How everything fits together
- [System Design](docs/system-architecture.md) - Technical deep dive
- [Requirements](docs/requirements.md) - Original project specification
- [Build Instructions](distribution/BUILD.md) - Creating installers

## License

See [LICENSE](distribution/LICENSE) for details.

## Acknowledgments

Built as a capstone project exploring secure, user-controlled storage solutions. Inspired by the need for privacy-aware, infrastructure-independent file sharing.

---

**Note:** This is currently in MVP stage. It works, but it's designed for personal use and learning. Use in production environments at your own risk.
