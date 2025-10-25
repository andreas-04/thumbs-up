# Architecture Documentation
## ThumbsUp - Secure On-Demand Wireless NAS

**Last Updated:** October 24, 2025  
**Version:** 1.0 (MVP)

---

## Overview

ThumbsUp is a portable Wi-Fi-enabled NAS system that provides on-demand file sharing using mutual TLS authentication and dynamic access control. The system operates through a state machine that manages service lifecycle, client connections, and file access.

### Implementation Details

- **State Machine Architecture** - Four-state lifecycle (DORMANT → ADVERTISING → ACTIVE → SHUTDOWN)
- **Mutual TLS Authentication** - Certificate-based client authentication
- **Service Discovery** - Avahi mDNS for device discovery
- **Dynamic Access Control** - Per-client iptables firewall rules
- **NFS File Sharing** - Dynamic per-client NFS exports
- **Multi-Client Support** - Concurrent authenticated sessions
- **Container Deployment** - Docker-based with Linux capabilities

---

## Architecture Overview

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Local WiFi Network                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐              ┌─────────────────────┐   │
│  │  ThumbsUp Client │              │  ThumbsUp NAS Device│   │
│  │  (User Device)   │              │  (Raspberry Pi)     │   │
│  │                  │              │                     │   │
│  │  • mDNS          │ ◄──────────► │  • State Machine    │   │
│  │    Discovery     │   Discover   │  • mTLS Server      │   │
│  │  • mTLS          │   & Connect  │  • Avahi mDNS       │   │
│  │    Client Auth   │              │  • Firewall         │   │
│  │  • NFS           │   Secure     │    (iptables)       │   │
│  │    Mount Client  │   Access     │  • NFS Server       │   │
│  │                  │              │  • USB Storage      │   │
│  │  Examples:       │              │    (Encrypted)      │   │
│  │  - Laptop        │              │                     │   │
│  │  - Phone         │              │  ┌───────────────┐  │   │
│  │  - Desktop       │              │  │ Encrypted USB │  │   │
│  │  - Another Pi    │              │  │ Storage Drive │  │   │
│  └─────────────────┘              │  └──────────────┘  │   │
│                                    └────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Server Components:**
- **Language:** Python 3
- **OS:** Ubuntu 22.04 (containerized)
- **Service Discovery:** Avahi daemon
- **Authentication:** SSL/TLS (Python ssl module)
- **Firewall:** iptables
- **File Sharing:** NFS kernel server (NFSv3)
- **Orchestration:** Docker Compose
- **PKI:** Python cryptography library

**Client Components:**
- **Language:** Python 3
- **OS:** Ubuntu 22.04 (containerized)
- **Discovery:** avahi-browse
- **Mount:** NFS client utilities
- **Authentication:** SSL/TLS

**Frontend Auth Client :**
- **Framework:** React + TypeScript
- **Build:** Vite
- **Status:** Not integrated (default Vite template)

### Code Structure

```
backend/
| api/
| ├─ client/
| │ ├─ client.py            # Client application
| │ └─ Dockerfile           # Client container image
| ├─ server/
| │ ├─ server.py            # Main server implementation
| │ ├─ __init__.py          # Package initialization
| │ ├─ Dockerfile           # Server container image
| │ ├─ pkg/                 # Core server modules
| │ │ ├─ __init__.py        # Package initialization
| │ │ ├─ state_machine.py   # State machine logic
| │ │ ├─ firewall.py        # iptables management
| │ │ ├─ nfs.py             # NFS export management
| │ │ ├─ mdns_service.py    # Avahi mDNS integration
| │ │ └─ storage.py         # Storage lock/unlock (demo mode)
| │ ├─ demo_luks/           # Demo storage files
| │ └─ tests/               # Unit tests
| │ ├─ Dockerfile           # Server container image
| │ └─ demo_data/           # Sample files for testing
| ├─ docker-compose.yml     # Container orchestration
| |
| ├─ pki/
| | ├─ gen_selfsigned.py    # Certificate generation script
| | ├─ server_cert.pem      # Server certificate
| | ├─ server_key.pem       # Server private key
| | ├─ client_cert.pem      # Client certificate
| | └─ client_key.pem       # Client private key
| |
| ├─ config/
| | ├─ avahi-daemon.conf    # mDNS daemon configuration
| | └─ dbus-system.conf     # D-Bus system configuration
| |
| └─ scripts/
|   ├─ entrypoint_server.sh # Server container entrypoint
|   └─ entrypoint_client.sh # Client container entrypoint
| 
docs/
├─ requirements.md        # Capstone specification
├─ diagrams.md # Mermaid diagrams
└─ architecture.md        # This document

frontend/
└─ src/                   # React app (not integrated)
```

### State Machine Implementation

The server implements a state machine with 4 states:

1. **DORMANT** (Initial)
   - No services running
   - Storage locked
   - Minimal network presence
   - Waiting for activation signal

2. **ADVERTISING** (Post-activation)
   - Firewall initialized
   - Storage unlocked (demo mode)
   - mTLS server listening
   - mDNS broadcasting service
   - Waiting for first client

3. **ACTIVE** (Client connected)
   - Multiple clients supported
   - Per-client firewall rules
   - Per-client NFS exports
   - Session tracking
   - Connection monitoring

4. **SHUTDOWN** (Graceful cleanup)
   - All clients disconnected
   - Firewall rules removed
   - NFS exports cleared
   - Storage locked
   - Services stopped

**State Transitions:**
```
DORMANT → ADVERTISING     (activate() method call)
ADVERTISING → ACTIVE      (First client authenticates)
ACTIVE → ADVERTISING      (Last client disconnects)
ANY → SHUTDOWN            (SIGINT/SIGTERM signal)
SHUTDOWN → DORMANT        (Cleanup complete)
```

Note: ADVERTISING → DORMANT timeout is planned but not yet implemented.

### Security Implementation

#### Authentication Flow

1. **Client Discovery**
   - Client runs `avahi-browse` to find `_thumbsup._tcp` service
   - Server advertises hostname, IP, port, and status via TXT records

2. **mTLS Handshake**
   - Client connects to server on port 8443
   - Server requests client certificate
   - Client verifies server certificate against CA
   - Server verifies client certificate against CA
   - Both sides validate certificate chains

3. **Access Grant**
   - Server extracts client IP and Common Name from certificate
   - Server adds iptables rule allowing client IP → NFS port 2049
   - Server adds `/etc/exports` entry for client IP
   - Server runs `exportfs -ra` to refresh NFS exports
   - Client can now mount NFS share at `/app/demo_storage`

4. **Session Management**
   - Server tracks active clients in dictionary
   - Each client has session object with metadata
   - Per-connection inactivity timeout (300 seconds default)
   - Connection closed on timeout

5. **Cleanup**
   - On disconnect: remove firewall rule, remove NFS export
   - On last client disconnect: transition to ADVERTISING state

#### Certificate Structure

**Server Certificate:**
- Common Name: `localhost`
- Extended Key Usage: `SERVER_AUTH`
- Self-signed (for MVP)
- Validity: 365 days

**Client Certificate:**
- Common Name: `python-client`
- Extended Key Usage: `CLIENT_AUTH`
- Self-signed (for MVP)
- Validity: 365 days

**Production Concerns:**
- No proper CA hierarchy
- No certificate revocation mechanism
- No certificate renewal process
- Self-signed certs unsuitable for production

### Network Architecture

**Container Networking:**
```
Docker Bridge Network (nas-network)
│
├─ Server Container (secure-nas-server)
│   ├─ Port 8443 → mTLS
│   ├─ Port 2049 → NFS
│   ├─ Port 5353/udp → mDNS (mapped to 5354 to avoid macOS conflict)
│   └─ Capabilities: NET_ADMIN, SYS_ADMIN
│
└─ Client Container (secure-nas-client)
    ├─ No port mappings
    ├─ Capabilities: SYS_ADMIN (for NFS mount)
    └─ Profile: client (manual start)
```

**Firewall Rules (iptables):**
```bash
# Default policies
ESTABLISHED,RELATED → ACCEPT
lo → ACCEPT

# mTLS always accessible
tcp/8443 → ACCEPT (comment: NAS_mTLS_Port)

# NFS per-client (dynamically added)
tcp/2049 -s <client_ip> → ACCEPT (comment: NAS_Client_<ip>)
```

### Data Flow

**File Access Flow:**
```
1. Client mounts NFS: mount -t nfs <server>:/app/demo_storage /mnt/nas
2. Client reads file: cat /mnt/nas/document1.txt
3. NFS request → Server NFS daemon
4. iptables checks source IP against rules
5. If allowed, NFS serves file from /app/demo_storage
6. Response → Client
7. Server logs access in Python application
```

**Current Logging:**
- Authentication events (success/failure)
- Client connection/disconnection
- Firewall rule changes
- NFS export modifications
- State transitions
- Command execution

---

## Component Details

### Server Components

**State Machine (`SecureNASServer`)**
- Manages four states: DORMANT, ADVERTISING, ACTIVE, SHUTDOWN
- Handles state transitions based on events
- Coordinates all server subsystems

**Storage Management**
- Placeholder methods for LUKS encryption (`_lock_storage()`, `_unlock_storage()`)
- Currently simulated with log messages
- Storage path: `/app/demo_storage`

**Firewall (`iptables`)**
- Default ACCEPT policy for established connections
- Port 8443 always open for mTLS
- Port 2049 restricted per-client using source IP rules
- Rules tagged with comments for identification

**NFS Server**
- NFSv3 implementation
- Dynamic exports via `/etc/exports`
- Exports refreshed with `exportfs -ra`
- One export entry per authenticated client

**mDNS Service (`avahi-daemon`)**
- Service type: `_thumbsup._tcp`
- Publishes hostname, IP, port, and status
- Started in ADVERTISING state
- Stopped in DORMANT state

**Session Management**
- Tracks active clients in dictionary
- Stores client IP, Common Name, connection time
- Monitors last activity timestamp
- 300-second inactivity timeout

### Client Components

**Discovery**
- Uses `avahi-browse` to find `_thumbsup._tcp` services
- Parses service records for connection details

**Authentication**
- Initiates mTLS connection to server port 8443
- Presents client certificate
- Validates server certificate

**File Access**
- Mounts NFS share after successful authentication
- Mount point: `/mnt/nas` (configurable)
- Uses standard NFS mount command

---

## Implementation Notes

### Certificate Details

Self-signed certificates used for MVP:
- **Server**: CN=localhost, 365-day validity
- **Client**: CN=python-client, 365-day validity
- Generated using `cryptography` library in Python
- No certificate revocation mechanism
- No CA hierarchy (single-level trust)

### Container Configuration

**Docker Compose Network**: `nas-network` (bridge mode)

**Server Container Capabilities**:
- `NET_ADMIN` - For iptables firewall management
- `SYS_ADMIN` - For NFS server operations

**Client Container Capabilities**:
- `SYS_ADMIN` - For NFS mount operations

**Port Mappings**:
- 8443 → mTLS server
- 2049 → NFS server
- 5354 → mDNS (avoiding macOS conflict on 5353)

### Known Limitations

**Security**:
- Storage encryption is simulated (no actual LUKS)
- No certificate revocation checking
- No persistent audit logging
- Hostname verification disabled in client
- NFS traffic not encrypted

**Architecture**:
- Single-threaded client handling
- No persistent state across restarts
- Hardcoded configuration values
- Limited error recovery
- No rate limiting
- No health monitoring endpoints

---

## Usage Example

**Starting the Server:**
```bash
docker-compose up server
```
Server transitions: DORMANT → ADVERTISING (waits for clients)

**Connecting a Client:**
```bash
docker-compose run --rm client
```
Client discovers service, authenticates, mounts NFS, accesses files

**State Transitions:**
- First client connects: ADVERTISING → ACTIVE
- Last client disconnects: ACTIVE → ADVERTISING
- Inactivity timeout (300s): ADVERTISING → DORMANT
- SIGTERM/SIGINT: ANY → SHUTDOWN

---

## File Organization

```
backend/api/
├─ server/
│   ├─ server.py          # Main server implementation
│   ├─ state_machine.py   # State machine logic
│   ├─ firewall.py        # iptables management
│   ├─ nfs.py             # NFS export management
│   ├─ mdns_service.py    # Avahi mDNS integration
│   └─ storage.py         # Storage lock/unlock (simulated)
├─ client/
│   └─ client.py          # Client application
└─ docker-compose.yml     # Container orchestration

backend/pki/
├─ gen_selfsigned.py      # Certificate generation script
├─ server_cert.pem        # Server certificate
├─ server_key.pem         # Server private key
├─ client_cert.pem        # Client certificate
└─ client_key.pem         # Client private key

backend/config/
├─ avahi-daemon.conf      # mDNS daemon configuration
└─ dbus-system.conf       # D-Bus system configuration

backend/scripts/
├─ entrypoint_server.sh   # Server container entrypoint
└─ entrypoint_client.sh   # Client container entrypoint
```

---

## Summary

ThumbsUp is a working MVP that demonstrates on-demand file sharing over Wi-Fi using industry-standard protocols (mTLS, NFS, mDNS). The state machine architecture provides lifecycle management, and the per-client access control implements security through dynamic firewall rules and NFS exports. The system is containerized for deployment and testing.


