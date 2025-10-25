# ThumbsUp 👍

[![Client Distribution CI/CD](https://github.com/andreas-04/thumbs-up/actions/workflows/distribution-ci.yml/badge.svg)](https://github.com/andreas-04/thumbs-up/actions/workflows/distribution-ci.yml)

A portable, certificate-based network-attached storage system for local file sharing.

## Overview

ThumbsUp is a network-attached storage (NAS) implementation designed for Raspberry Pi or similar single-board computers. The system provides file sharing over local networks using NFS, with mutual TLS authentication and dynamic firewall rules.

## Features

The system implements:
- State-based operation (dormant, advertising, active, shutdown)
- mDNS service discovery via Avahi
- Mutual TLS (mTLS) authentication
- Per-client iptables firewall rules
- NFS file sharing with dynamic exports
- Multi-client concurrent access

## Operation

The system operates in four states:

1. **DORMANT** - Services inactive, device not discoverable on network
2. **ADVERTISING** - mDNS broadcast active, listening for mTLS connections
3. **ACTIVE** - Storage accessible via NFS to authenticated clients
4. **SHUTDOWN** - Graceful shutdown, cleaning up resources

Activation is triggered by calling the activate() method (physical button integration planned). Only clients presenting valid X.509 certificates can establish connections. The firewall restricts NFS access to authenticated client IP addresses.

## Quick Start

### For the Server

```bash
cd backend/api
docker-compose up
```

See [backend/README.md](backend/README.md) for detailed setup.

### For the Client (Your devices)

Client packages available:
- **Debian/Ubuntu** - `.deb` package
- **Windows** - `.exe` installer
- **macOS** - Python client

See [distribution/README.md](distribution/README.md) for installation instructions.

## Project Structure

```
thumbs-up/
├── backend/          # Server implementation for Raspberry Pi
│   ├── api/          # Docker-based server and client
│   ├── config/       # mDNS and system configuration
│   └── pki/          # Certificate management
├── distribution/     # Client installer build scripts
├── frontend/         # Web UI
└── docs/             # Architecture and design documentation
```

## Implementation Status

### Implemented
- ✅ State machine architecture (DORMANT → ADVERTISING → ACTIVE → SHUTDOWN)
- ✅ Mutual TLS authentication
- ✅ mDNS service discovery (Avahi)
- ✅ Dynamic firewall rules per client
- ✅ NFS file sharing with dynamic exports
- ✅ Multi-client support
- ✅ Docker deployment

### Planned
- 🔲 Physical button activation (currently simulated via activate() method)
- 🔲 LUKS encrypted storage (currently demo mode with unencrypted storage)
- 🔲 Time-based access control
- 🔲 Certificate revocation checking
- 🔲 Web-based management interface
- 🔲 Peer-to-peer synchronization
- 🔲 Secure OTA updates

## Security Model

The system implements the following security mechanisms:

- **Mutual TLS** - Client and server authenticate each other using X.509 certificates
- **Certificate-based authentication** - No password-based authentication
- **Per-client firewall rules** - Dynamic iptables management restricts NFS access to authenticated client IPs
- **Local operation** - No external network dependencies or cloud services
- **Open source** - Code available for security review

See [docs/architecture.md](docs/architecture.md) for detailed security architecture.

## Documentation

- [Architecture Overview](docs/architecture.md) - How everything fits together
- [System Design](docs/diagrams.md) - Technical deep dive
- [Requirements](docs/requirements.md) - Original project specification
- [Build Instructions](distribution/BUILD.md) - Creating installers

## License

BSD 3-Clause License. See [LICENSE](LICENSE) for details.

## Project Context

Capstone project investigating secure, user-controlled storage systems with certificate-based authentication and local network file sharing.

---

**Note:** This project is in active development. Intended for educational and personal use.
