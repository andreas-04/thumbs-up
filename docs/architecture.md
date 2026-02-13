# ThumbsUp Architecture

## Overview

ThumbsUp is a secure, portable Wi-Fi file sharing system designed for on-demand, ephemeral file access without reliance on cloud infrastructure. Built on Flask with containerization support, it provides both web-based and SMB file sharing with JWT authentication, TLS encryption, and mDNS service discovery.

## System Architecture

### High-Level Design (Current)

```
┌─────────────────────────────────────────────────────────┐
│                     Client Layer                        │
│  (Web Browsers, SMB Clients, Mobile Devices)           │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ HTTPS/SMB
                 │
┌────────────────▼────────────────────────────────────────┐
│              Network Services                           │
│  ┌──────────────┐         ┌────────────────┐          │
│  │ mDNS/Avahi   │         │  TLS/SSL       │          │
│  │ Advertiser   │         │  Encryption    │          │
│  └──────────────┘         └────────────────┘          │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│              Application Layer                          │
│  ┌─────────────────┐      ┌─────────────────┐         │
│  │  Flask Web API  │      │   SMB Manager   │         │
│  │  (HTTPS/8443)   │      │   (Port 445)    │         │
│  └────────┬────────┘      └────────┬────────┘         │
│           │                         │                   │
│  ┌────────▼────────┐      ┌────────▼────────┐         │
│  │  JWT Auth       │      │  Samba Config   │         │
│  │  System         │      │  Generator      │         │
│  └─────────────────┘      └─────────────────┘         │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│              Storage Layer                              │
│           Shared File Storage                           │
│     (Documents, Music, User Files)                      │
└─────────────────────────────────────────────────────────┘
```

### Planned: Containerized Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Systemd Service                       │
│              (thumbsup.service)                         │
└────────────────┬────────────────────────────────────────┘
                 │ manages
┌────────────────▼────────────────────────────────────────┐
│                Docker Compose                           │
│  ┌─────────────────┐      ┌─────────────────┐         │
│  │ Flask Container │      │  SMB Container  │         │
│  │   (Port 8443)   │      │  (Port 445)     │         │
│  └────────┬────────┘      └────────┬────────┘         │
│           │                         │                   │
│           └──────────┬──────────────┘                   │
│                      │                                   │
│           ┌──────────▼──────────┐                      │
│           │   Shared Volume     │                      │
│           │  (Persistent Data)  │                      │
│           └─────────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Web Server (`core/server.py`)

**Purpose**: Flask-based HTTPS server providing RESTful API and web interface for file operations.

**Key Features**:
- HTTPS-only (port 8443) with self-signed certificates
- JWT token-based authentication
- File browsing, upload, download, and deletion
- Admin dashboard with token management
- QR code generation for mobile access
- CORS support for cross-origin requests

**Endpoints**:
- `/` - File browser interface
- `/api/v2/files` - File listing and operations
- `/api/v2/upload` - File upload handler
- `/api/v2/download/<path>` - File download
- `/admin` - Admin dashboard
- `/admin/login` - PIN-based admin authentication

### 2. Authentication System (`core/auth.py`)

**Purpose**: JWT-based token authentication with dual-role support (admin/guest).

**Architecture**:
- **Admin Role**: PIN-protected, 2-hour session tokens, full system access
- **Guest Role**: Time-limited tokens (24hr default), file access only
- **Token Storage**: In-memory for guest tokens, cookie-based for admin sessions
- **Security**: SHA256 PIN hashing, HS256 JWT signing

**Token Lifecycle**:
1. Admin authenticates with PIN → receives session cookie
2. Admin generates guest token → stored in active token registry
3. Guest uses token → validated against registry and expiry
4. Admin can revoke tokens → removed from registry

### 3. SMB Manager (`services/smb_manager.py`)

**Purpose**: Manages Samba server configuration and lifecycle for native file sharing.

**Key Features**:
- Dynamic `smb.conf` generation
- Guest user account management
- SMB3 protocol with optional encryption
- Port auto-detection (445 for Linux, 4450 for WSL)
- Integrated recycle bin
- mDNS service advertisement

**Configuration**:
- Workgroup: `WORKGROUP`
- Share name: `thumbsup`
- Security: User-level authentication
- Default credentials: `guest:guest` (overridable via env vars)

### 4. mDNS Service Discovery (`services/mdns_advertiser.py`)

**Purpose**: Platform-agnostic service advertisement for zero-configuration networking.

**Platform Support**:
- **Linux**: Avahi via D-Bus
- **macOS**: Bonjour/Zeroconf
- **Windows**: Fallback to manual IP/hostname

**Service Types**:
- Web: `_https._tcp`
- SMB: `_smb._tcp`

### 5. Certificate Management (`utils/generate_certs.py`, `gen_selfsigned.py`)

**Purpose**: Self-signed X.509 certificate generation for TLS encryption.

**Features**:
- RSA 2048-bit keys
- Server certificates with SERVER_AUTH extension
- Client certificates with CLIENT_AUTH extension
- Subject Alternative Name (SAN) support
- Automatic certificate lifecycle (365-day validity)

### 6. QR Code Generator (`utils/qr_generator.py`)

**Purpose**: Generate scannable QR codes embedding access URLs with authentication tokens.

**Use Case**: Mobile device onboarding without manual URL entry.

## Data Flow

### Web Access Flow
```
1. User → Admin Login (PIN)
2. Admin Dashboard → Generate Guest Token
3. QR Code → Mobile Device Scan
4. Token Validation → Cookie Set
5. File Browser → Authenticated File Operations
```

### SMB Access Flow
```
1. SMB Client → Network Browse
2. mDNS Discovery → thumbsup.local
3. Credential Prompt → guest:guest
4. Mount Share → Direct File System Access
```

## Security Model

### Transport Security
- **TLS 1.2+**: All web traffic encrypted (HTTPS)
- **SMB3 Encryption**: Optional for SMB connections
- **Self-Signed Certificates**: Bootstrap trust model (suitable for closed networks)

### Authentication
- **Admin**: PIN-based (SHA256 hashed)
- **Guest**: JWT tokens (HMAC-SHA256 signed)
- **SMB**: Samba user authentication (tdbsam backend)

### Authorization
- **Admin**: Full system control, token management, file operations
- **Guest**: Read/write file access only (no token management)
- **Token Revocation**: In-memory registry allows immediate invalidation

### Attack Surface Mitigation
- No external dependencies (self-hosted)
- Network-isolated (local WiFi only)
- Ephemeral tokens (time-limited access)
- Admin session timeout (2 hours)
- Upload size limits (100MB default)

## Deployment Architecture

### Current Deployment
- **Standalone Mode**: Direct Python execution
- **Configuration**: `startup.py` interactive wizard
- **Storage**: Local file system directories
- **Status**: Currently implemented and functional

### Planned: Docker Compose Deployment (In Progress)

**Architecture**:
```yaml
services:
  web:
    # Flask Web Server
    - Port 8443 (HTTPS)
    - Certificate auto-generation
    
  smb:
    # Samba File Sharing
    - Port 445/4450
    - Dynamic configuration
    
  storage:
    # Shared volume across services
    - Persistent data volume
    - Mounted to both web and SMB containers
```

**Systemd Integration**:
- `thumbsup.service`: Systemd unit file to manage docker-compose
- Automatic startup on boot
- Lifecycle management (start/stop/restart)

**Environment Variables** (planned):
- `ADMIN_PIN`: Required, admin authentication
- `STORAGE_PATH`: Storage directory path
- `PORT`: HTTPS port (default 8443)
- `TOKEN_EXPIRY_HOURS`: Guest token lifetime
- `ENABLE_UPLOADS`, `ENABLE_DELETE`: Feature flags
- `SMB_GUEST_USER`, `SMB_GUEST_PASSWORD`: SMB credentials

## Storage Structure

```
storage/
├── documents/          # Document files
│   ├── README.txt
│   └── bee-movie-script.txt
├── music/              # Media files
└── [dynamic uploads]   # User-uploaded content
```

## Network Configuration

### Ports
- **8443**: HTTPS web server
- **445/4450**: SMB file sharing
- **5353**: mDNS service discovery (UDP)

### Discovery
- **Hostname**: `<hostname>.local` (mDNS)
- **Service**: Auto-advertised via Avahi/Bonjour
- **Fallback**: Direct IP access

## Extensibility Points

### Current Extension Mechanisms
1. **Service Abstraction**: Modular services (`services/` directory)
2. **Template System**: Flask Jinja2 templates for UI customization
3. **Environment Configuration**: Runtime behavior via env vars
4. **Plugin-ready**: Services can be toggled (web, SMB, or both)

### Future Enhancement Opportunities
- P2P synchronization (per SRS vision)
- Attribute-based access control (ABE)
- Encrypted storage at rest (LUKS integration)
- Activity monitoring and anomaly detection
- Certificate Authority (CA) integration for mutual TLS

## Technology Stack

### Backend
- **Python 3.11+**: Core language
- **Flask**: Web framework
- **PyJWT**: Token authentication
- **Cryptography**: Certificate generation
- **Samba**: SMB file sharing

### Frontend
- **HTML/Jinja2**: Templates
- **Bootstrap**: UI framework (assumed from admin templates)

### Infrastructure
- **Docker** (planned): Containerization via docker-compose
- **Systemd** (planned): Service lifecycle management
- **Avahi/Bonjour**: Service discovery
- **TLS/SSL**: Transport encryption

## Design Principles

1. **Zero Configuration**: mDNS eliminates manual IP management
2. **Security by Default**: HTTPS-only, authenticated access
3. **Platform Agnostic**: Linux, macOS, Windows support
4. **Ephemeral by Design**: On-demand activation, time-limited tokens
5. **Self-Contained**: No external cloud dependencies
6. **Open Standards**: SMB, HTTPS, mDNS, JWT, X.509

## Operational Modes

### Mode 1: Web Only
- Environment: `PREFERENCE=web`
- Services: Flask server + mDNS
- Use Case: Browser-based access, mobile devices

### Mode 2: SMB Only
- Environment: `PREFERENCE=smb`
- Services: Samba server + mDNS
- Use Case: Native file system integration

### Mode 3: Hybrid (Both)
- Environment: `PREFERENCE=both`
- Services: Flask + Samba + mDNS
- Use Case: Maximum compatibility, all device types

## Performance Considerations

- **Concurrent Access**: Flask built-in server (single-threaded), suitable for personal use
- **File Size**: 100MB upload limit (configurable)
- **Token Overhead**: In-memory storage, O(1) validation
- **SMB Performance**: Optimized socket options (TCP_NODELAY, buffer tuning)

## Monitoring & Logging

- **SMB Logs**: `services/smb_config/smb.log`
- **Flask Logs**: Stdout/stderr (containerized)
- **Log Rotation**: 1000KB max per Samba log
- **Log Level**: Configurable per service

## Compliance & Standards

- **SMB3**: Microsoft file sharing protocol
- **JWT (RFC 7519)**: Token format
- **X.509**: Certificate standard
- **mDNS (RFC 6762)**: Service discovery
- **TLS 1.2+**: Transport security

---

**Document Version**: 1.0  
**Last Updated**: February 10, 2026  
**Maintained By**: ThumbsUp Development Team
