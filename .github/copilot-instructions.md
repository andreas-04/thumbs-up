# AI Instructions for ThumbsUp Repository

## Project Overview

ThumbsUp is a capstone project implementing a portable, certificate-based NAS system for Raspberry Pi. The system provides secure file sharing over local networks using NFS with mutual TLS authentication and dynamic firewall rules.

**License:** BSD 3-Clause  
**Copyright:** Thumbs-Up Team  
**Status:** MVP / Educational Project

## Core Architecture

### Technology Stack
- **Backend:** Python 3, Docker, Ubuntu 22.04
- **Authentication:** Mutual TLS (mTLS) with X.509 certificates
- **Service Discovery:** Avahi mDNS
- **File Sharing:** NFS (Network File System)
- **Firewall:** iptables with dynamic per-client rules
- **Frontend:** React + TypeScript + Vite (not integrated with backend)

### State Machine (4 States)
1. **DORMANT** - No services running, waiting for activation
2. **ADVERTISING** - mDNS broadcasting, listening for mTLS connections, storage unlocked
3. **ACTIVE** - Clients connected, NFS accessible with per-client firewall rules
4. **SHUTDOWN** - Graceful cleanup and resource deallocation

### Key Components (backend/api/server/pkg/)
- `state_machine.py` - State management with callback-based transitions
- `firewall.py` - iptables management with context managers
- `nfs.py` - Dynamic NFS export management
- `mdns_service.py` - Avahi service discovery integration
- `storage.py` - Storage operations (currently demo mode, LUKS planned)

## Code Style & Standards

### Language Guidelines
- **Technical, not marketing** - Avoid words like "clean", "powerful", "amazing", "seamless"
- **Factual documentation** - State what the code does, not how great it is
- **Academic tone** - This is a capstone project, keep it professional

### Python Code Standards
- Type hints required for function parameters and return values
- Docstrings for all classes and public methods
- Use context managers for resource management (firewall, NFS)
- Logging with structured messages and emojis for state changes
- Error handling with specific exceptions, not broad try-except

### File Organization
```
backend/api/server/
├── server.py              # Main server orchestration
├── __init__.py            # Package exports
├── pkg/                   # Core modules
│   ├── __init__.py
│   ├── state_machine.py
│   ├── firewall.py
│   ├── nfs.py
│   ├── mdns_service.py
│   └── storage.py
├── demo_luks/             # Demo storage files
└── tests/                 # Unit tests
```

## Implementation Status

### ✅ Implemented (MVP)
- State machine with 4 states
- mTLS authentication
- mDNS service discovery
- Dynamic per-client firewall rules
- NFS exports with dynamic configuration
- Multi-client concurrent connections
- Docker deployment
- Session tracking

### 🔲 Planned (Not Yet Implemented)
- Physical button activation (currently simulated via activate() method)
- LUKS encrypted storage (currently demo mode with unencrypted files)
- Time-based access control
- Certificate revocation checking
- Web-based management UI
- Peer-to-peer synchronization
- Secure OTA updates
- ADVERTISING → DORMANT timeout

## Important Constraints

### Security Model
- Uses self-signed certificates (MVP only, not production-ready)
- No CA hierarchy
- No certificate revocation
- mTLS handshake required for all client connections
- Firewall rules are IP-based (extracted from certificate)

### Current Limitations
- Storage is NOT encrypted (storage.py is in demo mode)
- Button activation is simulated, not hardware-integrated
- No automatic timeout from ADVERTISING to DORMANT
- Frontend exists but is not integrated with backend
- Self-signed certificates only

## When Making Changes

### Adding Features
1. Check if feature is in "Planned" list
2. Update both code AND documentation
3. Maintain state machine integrity
4. Add appropriate tests
5. Update README.md implementation status

### Modifying Documentation
- Keep technical, avoid marketing language
- Verify accuracy against actual code
- Update all affected files (README, docs/architecture.md, etc.)
- Be concise - academic project, not sales pitch

### Code Modifications
- Maintain copyright headers: `Copyright (c) 2025 Thumbs-Up Team`
- Include SPDX license identifier: `SPDX-License-Identifier: BSD-3-Clause`
- Use context managers for cleanup (firewall, NFS exports)
- Log state transitions with appropriate emoji indicators
- Keep modules in `pkg/` subdirectory

### Testing
- Unit tests go in `backend/api/server/tests/`
- Test state transitions thoroughly
- Mock external dependencies (iptables, NFS, Avahi)
- Verify cleanup on state exits

## Common Tasks

### State Transitions
State changes MUST go through the state machine:
```python
self.state_machine.transition_to(DeviceState.ACTIVE)
```

Register callbacks using decorators:
```python
@self.state_machine.on_enter(DeviceState.ACTIVE)
def enter_active():
    # Setup code
    
@self.state_machine.on_exit(DeviceState.ACTIVE)
def exit_active():
    # Cleanup code
```

### Client Session Management
Use context managers for automatic cleanup:
```python
with self._client_session(client_ip, cert_cn) as session:
    # Firewall and NFS automatically configured
    # Cleanup automatic on exit
```

### Firewall Rules
Always use context managers:
```python
with self.firewall.allow_client(client_ip):
    # Client can access NFS
# Rule automatically removed
```

### NFS Exports
Use context managers for per-client exports:
```python
with self.nfs.export_to_client(client_ip, self.storage.path):
    # Client can mount NFS
# Export automatically removed
```

## Documentation Files

- `README.md` - Main project overview
- `docs/architecture.md` - Detailed technical architecture
- `docs/system-architecture.md` - Sequence and state diagrams
- `docs/architectural-review.md` - Security analysis and assessment
- `docs/requirements.md` - Original capstone specifications
- `backend/README.md` - Setup and deployment instructions
- `distribution/README.md` - Client installation guide

## Key Principles

1. **Accuracy over completeness** - Document what IS implemented, not what could be
2. **Security transparency** - Be clear about limitations (self-signed certs, no encryption)
3. **Educational value** - Code should teach, be readable and well-documented
4. **State machine first** - All operations flow through state transitions
5. **Resource cleanup** - Use context managers, no resource leaks
6. **Technical language** - This is academic work, not a product

## Questions to Ask Before Changes

- Does this match the current MVP implementation?
- Is the state machine integrity maintained?
- Are resources properly cleaned up?
- Is documentation updated to match code changes?
- Does this use technical, not marketing language?
- Is this feature actually implemented or just planned?
- Are copyright headers present and correct?

## Contact & Context

This is a capstone project exploring secure, user-controlled storage with certificate-based authentication. The focus is on learning system architecture, network security, and proper state management rather than building a production system.
