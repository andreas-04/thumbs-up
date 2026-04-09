# TerraCrate Architecture

## Overview

TerraCrate is a secure, portable Wi-Fi file sharing system designed for on-demand file access without reliance on cloud infrastructure. It runs as two Docker containers — a Flask REST API backend and a React SPA frontend served by Nginx — orchestrated via Docker Compose on a Raspberry Pi (or any Linux host). The system provides HTTPS file sharing with JWT authentication, mutual TLS (mTLS) for regular users, a three-tier folder permission model, SMTP email notifications with client certificate delivery, and mDNS service discovery.

## System Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                     Client Layer                        │
│         (Web Browsers, Mobile Devices)                  │
└────────────────┬────────────────────────────────────────┘
                 │ HTTPS (port 443)
                 │
┌────────────────▼────────────────────────────────────────┐
│           Nginx Reverse Proxy (Frontend Container)      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  TLS termination (server cert + optional mTLS)   │  │
│  │  Static SPA assets (/assets/*, /, /login, etc.)  │  │
│  │  API proxy: /api/* → backend:8443                │  │
│  │  mTLS enforcement on /files, /guest/files        │  │
│  │  Redirect to /cert-required on missing client    │  │
│  │  cert for protected routes                       │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────┘
                 │ HTTPS (port 8443, internal)
┌────────────────▼────────────────────────────────────────┐
│            Flask REST API (Backend Container)           │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐   │
│  │ JWT Auth    │ │ 3-Tier      │ │ Certificate    │   │
│  │ (bcrypt +   │ │ Permissions │ │ Generation     │   │
│  │  HS256)     │ │ Engine      │ │ (server+client)│   │
│  └─────────────┘ └─────────────┘ └────────────────┘   │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────────┐   │
│  │ File Ops    │ │ SMTP Email  │ │ QR Code        │   │
│  │ (CRUD)      │ │ + P12 Certs │ │ Generator      │   │
│  └─────────────┘ └─────────────┘ └────────────────┘   │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                   Storage Layer                         │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────────┐  │
│  │ File Volume  │ │ SQLite DB     │ │ TLS Certs    │  │
│  │ (bind mount) │ │ (named vol)   │ │ (named vol)  │  │
│  └──────────────┘ └───────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                Host Services (Raspberry Pi)             │
│  ┌──────────────┐ ┌────────────────┐                   │
│  │ Avahi mDNS   │ │ WiFi AP        │                   │
│  │ (host)       │ │ Fallback       │                   │
│  └──────────────┘ └────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

### Docker Compose Services

```
┌─────────────────────────────────────────────────────────┐
│              Systemd (thumbsup.service)                 │
│                 docker compose up -d                    │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                Docker Compose                           │
│                                                         │
│  ┌──────────────────┐     ┌──────────────────┐         │
│  │ backend          │     │ frontend         │         │
│  │ (python:3.11)    │     │ (nginx:alpine)   │         │
│  │ Port 8443        │     │ Port 443         │         │
│  │ network_mode:    │     │ network_mode:    │         │
│  │   host           │     │   host           │         │
│  └────────┬─────────┘     └────────┬─────────┘         │
│           │                         │                   │
│     ┌─────┴──────────┬──────────────┘                   │
│     │                │                                   │
│  ┌──▼────┐  ┌────────▼──────┐  ┌──────────────┐       │
│  │ files │  │ thumbsup-certs│  │ thumbsup-db  │       │
│  │(bind) │  │ (named vol)   │  │ (named vol)  │       │
│  └───────┘  └───────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────┘
```

Both containers use `network_mode: host` for direct access to host networking (required for mDNS and simplifies port mapping). The frontend container depends on the backend being healthy before starting.

## Core Components

### 1. Flask REST API (`backend/api/core/server.py`)

Flask 3.0.0 HTTPS server providing a versioned REST API (`/api/v1/*`) plus legacy HTML endpoints for backward compatibility.

**Configuration** (environment variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PIN` | *(required)* | Initial admin password |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8443` | HTTPS port |
| `STORAGE_PATH` | `/app/storage` | Root storage directory |
| `CERT_PATH` | `/app/certs/server_cert.pem` | Server TLS certificate |
| `KEY_PATH` | `/app/certs/server_key.pem` | Server TLS private key |
| `DATABASE_URI` | `sqlite:////app/data/thumbsup.db` | SQLAlchemy database URI |
| `TOKEN_EXPIRY_HOURS` | `24` | User JWT lifetime |
| `ENABLE_UPLOADS` | `true` | Allow file uploads |
| `ENABLE_DELETE` | `false` | Allow file/folder deletion |
| `MAX_UPLOAD_SIZE` | `104857600` | Upload limit (100 MB) |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `MDNS_HOSTNAME` | `socket.gethostname()` | mDNS hostname |
| `SERVICE_NAME` | `TerraCrate File Share` | Advertised service name |

**API Endpoints (`/api/v1/`)**:

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/login` | None | Email + password login → JWT |
| `POST` | `/auth/signup` | None | Self-registration (domain allowlist) |
| `POST` | `/auth/logout` | Auth | Logout (stateless) |
| `GET` | `/auth/me` | Auth | Current user info |
| `POST` | `/auth/refresh` | Auth | Refresh JWT token |
| `POST` | `/auth/change-password` | Auth | Change password |
| `GET` | `/settings` | None | Public system settings |
| `PUT` | `/settings` | Admin | Update system settings |
| `GET` | `/users` | Admin | List users (search + pagination) |
| `POST` | `/users` | Admin | Create/invite user |
| `GET` | `/users/<id>` | Admin | Get user |
| `PUT` | `/users/<id>` | Admin | Update user |
| `DELETE` | `/users/<id>` | Admin | Delete user |
| `GET` | `/users/<id>/permissions` | Admin | User's folder permissions |
| `PUT` | `/users/<id>/permissions` | Admin | Set user's folder permissions |
| `GET` | `/users/<id>/effective-permissions` | Admin | Resolved permissions with source |
| `PUT` | `/users/<id>/groups` | Admin | Assign user to groups |
| `GET` | `/folders` | Admin | List all storage folders |
| `GET` | `/domains` | Admin | List domain configs |
| `POST` | `/domains` | Admin | Create domain config |
| `GET` | `/domains/<id>` | Admin | Get domain config |
| `PUT` | `/domains/<id>` | Admin | Update domain config |
| `DELETE` | `/domains/<id>` | Admin | Delete domain config |
| `GET` | `/groups` | Admin | List groups |
| `POST` | `/groups` | Admin | Create group |
| `GET` | `/groups/<id>` | Admin | Get group with members/permissions |
| `PUT` | `/groups/<id>` | Admin | Update group |
| `DELETE` | `/groups/<id>` | Admin | Delete group |
| `PUT` | `/groups/<id>/permissions` | Admin | Replace group permissions |
| `PUT` | `/groups/<id>/members` | Admin | Replace group members |
| `GET` | `/files` | Auth | List files (filtered by permissions) |
| `POST` | `/files/upload` | Auth | Upload file (mTLS required for non-admin) |
| `GET` | `/files/download` | Auth | Download file |
| `POST` | `/files/mkdir` | Auth | Create directory |
| `DELETE` | `/files` | Auth | Delete file/directory |
| `GET` | `/stats/dashboard` | Admin | Dashboard statistics |

**Legacy HTML Endpoints** (backward compatibility):
- `/admin/login`, `/admin/first-setup`, `/register`, `/login`, `/logout`
- `/auth` (guest token → cookie), `/admin` (dashboard), `/` (file browser)
- `/download/<path>`, `/upload`, `/health`

**Startup Process**:
1. `start.sh` creates directories, generates SSL certs if missing, validates `ADMIN_PIN`
2. `core/server.py` initializes the database, runs schema migrations
3. Creates default `SystemSettings` if missing
4. Creates default admin user (`admin@<hostname>.local`) if no admin exists
5. Sets up mDNS advertising
6. Starts Flask with SSL context on port 8443

### 2. Authentication System (`backend/api/core/auth.py`)

JWT-based authentication with bcrypt password hashing and dual-role support.

**Roles**: `admin` and `user`

**Password Security**: bcrypt with auto-generated salt (via `bcrypt==5.0.0`)

**Token Architecture**:
- **Algorithm**: HS256 (HMAC-SHA256)
- **Secret**: Random 32-byte key generated at startup
- **Admin sessions**: 2-hour expiry
- **User sessions**: Configurable (`TOKEN_EXPIRY_HOURS`, default 24h)
- **Payload**: `user_id`, `email`, `role`, `iat`, `exp`, `jti` (unique ID)

**Token Extraction** (checked in order):
1. `Authorization: Bearer <token>` header
2. `auth_token` or `admin_token` cookie
3. `?token=` URL parameter

**Decorators**:
- `@require_auth` — validates token, attaches `request.user`, supports DB-backed and legacy payload-based auth
- `@require_admin` — requires `role == "admin"`, returns 403 otherwise

**Legacy Guest Token System** (deprecated): In-memory registry of time-limited guest tokens with revocation support. Still functional for backward compatibility.

### 3. Three-Tier Permission System (`backend/api/core/permissions.py`)

Layered folder access control with increasing specificity:

```
Tier 1: Domain Defaults (least specific)
    ↓ overridden by
Tier 2: Group Permissions
    ↓ overridden by
Tier 3: User Overrides (most specific)
```

**Tier 1 — Domain Defaults**: Applied to all users matching an email domain (e.g., `@company.com`). Configured via `DomainConfig` + `DomainPermission` models.

**Tier 2 — Group Permissions**: Applied via group membership. Multiple groups use OR logic (most permissive wins). Configured via `Group` + `GroupPermission` models.

**Tier 3 — User Overrides**: Per-user, per-folder tri-state permissions (`"allow"`, `"deny"`, or `null`). `"deny"` overrides all lower tiers. `null` defers to group/domain. Configured via `FolderPermission` model.

**Path Matching**: Longest-prefix match — a permission on `/docs` grants access to `/docs/sub/path`.

**Key Functions**:
- `resolve_permissions(user)` — returns merged permissions across all three tiers
- `resolve_permissions_detailed(user)` — returns per-path breakdown with source attribution
- `check_access(user, folder_path, require_write)` — boolean access check (admins bypass)
- `visible_paths(user)` — returns all paths the user can read
- `is_item_visible(item_path, item_is_folder, granted_paths)` — per-item visibility including navigation ancestors

### 4. Database Models (`backend/api/models.py`)

SQLAlchemy ORM with SQLite (configurable via `DATABASE_URI`).

**User**: `id`, `email` (unique), `password_hash`, `role` (admin/user), `is_default_pin`, `is_approved`, `created_at`, `last_login`. Many-to-many relationship with `Group` via `GroupMembership`.

**SystemSettings** (singleton): `auth_method` (email/email+password/username+password), `tls_enabled`, `https_port`, `device_name`, SMTP configuration (`smtp_enabled`, `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_from_email`, `smtp_use_tls`), `allowed_domains` (comma-separated domain allowlist for self-registration).

**FolderPermission**: `user_id` (FK), `folder_path`, `can_read` (allow/deny/null), `can_write` (allow/deny/null). Unique on `(user_id, folder_path)`.

**DomainConfig**: `domain` (unique). Has many `DomainPermission` rows.

**DomainPermission**: `domain_id` (FK), `folder_path`, `can_read` (bool), `can_write` (bool). Unique on `(domain_id, folder_path)`.

**Group**: `name` (unique), `description`. Has many `GroupPermission` rows and many-to-many `User` via `GroupMembership`.

**GroupPermission**: `group_id` (FK), `folder_path`, `can_read` (bool), `can_write` (bool). Unique on `(group_id, folder_path)`.

**GroupMembership**: Association table — `group_id` (FK), `user_id` (FK). Unique on `(group_id, user_id)`.

All foreign keys use `CASCADE` delete.

### 5. Certificate Management (`backend/api/utils/generate_certs.py`)

Self-signed X.509 certificate generation using the `cryptography` library.

**Server Certificate** (`generate_self_signed_cert`):
- RSA 2048-bit key, SHA256 signature
- Subject: `C=US, ST=California, L=San Francisco, O=TerraCrate, CN=<hostname>`
- SANs: hostname, hostname.local, localhost, host IP, 127.0.0.1
- BasicConstraints: CA=True (acts as CA to sign client certs)
- Validity: 365 days

**Client Certificate** (`generate_client_cert`):
- RSA 2048-bit, signed by the server CA
- Subject: `O=thumbsup, OU=member, CN=<user_email>`
- SANs: user email (RFC822Name)
- ExtendedKeyUsage: ClientAuth
- Validity: 365 days

**PKCS#12 Bundle** (`generate_client_p12`):
- Wraps client cert + key + CA chain into a `.p12` file
- Generated with random password for secure delivery via email

### 6. SMTP Email Service (`backend/api/utils/email_sender.py`)

Sends email notifications using `smtplib` with configuration from `SystemSettings`.

- `send_approval_email(user_email, ...)` — notifies user of account approval, optionally attaches a `.p12` client certificate
- `send_invite_email(user_email, ...)` — sends invitation with embedded P12 certificate and temporary password
- Supports TLS/STARTTLS, multipart emails (HTML + text + attachments)

### 7. mDNS Service Discovery (`backend/api/utils/mdns_advertiser.py`)

Platform-agnostic service advertisement for zero-configuration networking.

- **Linux**: Avahi via D-Bus API
- **macOS**: Zeroconf/Bonjour library
- **Windows**: Informational fallback

Advertises `_smb._tcp` service. On the host, Avahi also advertises `_https._tcp` on port 443 via a static service file.

### 8. QR Code Generator (`backend/api/utils/qr_generator.py`)

Generates QR codes embedding access URLs with authentication tokens for mobile device onboarding.

- Returns PIL Image, base64-encoded PNG, file output, or ASCII art
- URL format: `{base_url}/auth?token={token}`

## Frontend Application

### Technology Stack

- **React 19** with TypeScript (strict mode)
- **Vite** build tool with `@vitejs/plugin-react`
- **React Router v7** for client-side routing
- **Tailwind CSS 4** + shadcn/ui components (Radix UI primitives)
- **MUI (Material UI) 7** for additional components
- **Motion** (Framer Motion) for animations
- **Sonner** for toast notifications

### Architecture

```
src/
├── main.tsx                    # Entry point
├── config.ts                   # Environment config (VITE_API_BASE_URL)
├── app/
│   ├── App.tsx                 # AuthProvider → DataProvider → Router → Toaster
│   ├── routes.tsx              # Route definitions
│   ├── contexts/
│   │   ├── AuthContext.tsx      # Auth state, login/logout, token management
│   │   └── DataContext.tsx      # Global state: settings, users, domains, groups, files
│   ├── components/
│   │   ├── AdminLayout.tsx     # Sidebar navigation + responsive layout
│   │   ├── ProtectedRoute.tsx  # Redirects to /login if unauthenticated
│   │   ├── GuestRoute.tsx      # Redirects to /admin/dashboard if authenticated
│   │   ├── SystemStatus.tsx    # Dashboard stats cards
│   │   └── ui/                 # shadcn/ui component library
│   └── pages/
│       ├── AdminLogin.tsx      # Login form → admin to /admin, user to /files
│       ├── Signup.tsx          # Self-registration (if domains configured)
│       ├── PasswordReset.tsx   # Forced password change flow
│       ├── CertRequired.tsx    # Client cert installation instructions
│       ├── AdminDashboard.tsx  # File browser + system stats
│       ├── SystemSettings.tsx  # Domain allowlist + SMTP config
│       ├── UserManagement.tsx  # Approve/manage users
│       ├── FolderPermissions.tsx # Per-user permission overrides + effective view
│       ├── DomainConfig.tsx    # Domain-level permission defaults
│       ├── GroupManagement.tsx # Groups with members + permissions
│       ├── FileBrowser.tsx     # Admin file management
│       ├── UserFileBrowser.tsx # Authenticated user file browser
│       └── GuestFileBrowser.tsx # Legacy guest file browser
└── services/
    └── api.ts                  # ApiClient class wrapping all backend endpoints
```

### Routes

| Path | Component | Protection | Description |
|------|-----------|------------|-------------|
| `/`, `/login` | AdminLogin | Public | Login page |
| `/signup` | Signup | Public | Self-registration |
| `/reset-password` | PasswordReset | Public | Password change |
| `/cert-required` | CertRequired | Public | Certificate instructions |
| `/files` | UserFileBrowser | Auth + mTLS | User file browser |
| `/admin/dashboard` | AdminDashboard | Auth (JWT only) | Admin dashboard |
| `/admin/settings` | SystemSettings | Auth (JWT only) | System configuration |
| `/admin/users` | UserManagement | Auth (JWT only) | User management |
| `/admin/permissions` | FolderPermissions | Auth (JWT only) | Permission management |
| `/admin/domains` | DomainConfig | Auth (JWT only) | Domain config |
| `/admin/groups` | GroupManagement | Auth (JWT only) | Group management |

### State Management

**AuthContext**: Manages `isAuthenticated`, `user`, `loading` state. On mount, checks localStorage for existing token and validates via `/auth/me`. Provides `login()`, `logout()`, `updateUser()`.

**DataContext**: Manages global application state — `settings`, `users`, `domains`, `groups`, `files`, `currentPath`. On authentication change, loads all relevant data (settings always, admin-only resources fail silently for non-admins).

### Nginx Configuration

The frontend container runs Nginx on **port 443** with TLS:

- **API proxy**: `/api/*` → `https://127.0.0.1:8443` (JWT auth at backend, no client cert required)
- **Public pages**: `/`, `/login`, `/signup`, `/reset-password`, `/cert-required` — no client cert
- **Admin pages**: `/admin/*` — no client cert (JWT auth only)
- **Protected pages**: `/files`, `/guest/files` — **mTLS enforced**, redirects to `/cert-required` on failure
- **Static assets**: `/assets/*` — cached 1 year
- **Security headers**: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`
- Passes `X-SSL-Client-Verify` and `X-SSL-Client-S-DN` headers to backend for mTLS verification

## Security Model

### Transport Security
- **TLS 1.2/1.3**: All traffic encrypted — Nginx terminates TLS on port 443, backend uses self-signed cert on 8443
- **Mutual TLS (mTLS)**: Client certificates required for protected file access routes; Nginx verifies and passes CN to backend
- **Self-Signed CA**: Server cert acts as CA to sign client certificates

### Authentication
- **Admin/User**: Email + password with bcrypt hashing → JWT tokens
- **mTLS**: Client certificates (`.p12`) delivered via email, CN must match user email
- **Legacy**: PIN-based admin auth and guest token system (deprecated)

### Authorization
- **Admin**: Full system control — user management, settings, file operations bypass permission checks
- **User**: Three-tier permission system controls folder access (domain → group → user override)
- **Self-Registration**: Controlled by domain allowlist in `SystemSettings`

### Attack Surface Mitigation
- Self-hosted, no cloud dependencies
- Network-isolated (local WiFi, optional AP fallback)
- Time-limited JWT tokens (2h admin, 24h user)
- Upload size limits (100 MB default)
- File deletion disabled by default
- Path traversal prevention in file operations
- Security headers (XSS, clickjacking, MIME sniffing)

## Deployment

### Host Setup (`setup.sh`)

Run on the target Raspberry Pi (requires root):

1. **Generates `.env`** with `MDNS_HOSTNAME` and `AP_PASSPHRASE`
2. **Installs Avahi** daemon for mDNS (`thumbsup.local` discovery)
3. **Installs WiFi AP fallback** — hostapd + dnsmasq. If wpa_supplicant fails to associate within 10 seconds, switches wlan0 to Access Point mode:
   - SSID: `TerraCrate-AP`, WPA2-PSK
   - DHCP range: `192.168.4.10–50`
   - AP IP: `192.168.4.1`
4. **Installs systemd services**:
   - `thumbsup.service` — runs `docker compose up -d` on boot
   - `wifi-fallback.service` — runs wifi-check.sh after network target

### Docker Compose

```yaml
services:
  backend:
    image: python:3.11
    port: 8443 (HTTPS)
    volumes: storage (bind), thumbsup-db, thumbsup-certs
    healthcheck: urllib to https://localhost:8443/health

  frontend:
    image: nginx:alpine (multi-stage: node:22-slim build → nginx)
    port: 443 (HTTPS)
    volumes: thumbsup-certs (read-only)
    depends_on: backend (healthy)
    healthcheck: wget to https://localhost/
```

**Named volumes**: `thumbsup-db` (SQLite database), `thumbsup-certs` (shared TLS certificates)
**Bind mount**: `./backend/api/storage` → `/app/storage` (user files)

### Environment Variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PIN` | `1234` | Initial admin password |
| `MDNS_HOSTNAME` | `thumbsup` | mDNS hostname (→ `thumbsup.local`) |
| `AP_PASSPHRASE` | *(prompted)* | WiFi AP fallback passphrase |

## Data Flow

### User Registration & Access
```
1. Admin configures allowed domains in System Settings
2. User visits /signup → enters email + password
3. Backend validates email domain against allowlist
4. Account created → admin can approve + email P12 cert
5. User installs .p12 certificate in browser/OS
6. User visits /files → Nginx verifies client cert → file browser
```

### Admin Workflow
```
1. Admin logs in with email + password → JWT issued (2h)
2. Admin panel: manage users, groups, domain configs, permissions
3. Approve users → optional SMTP email with P12 certificate
4. File management via admin dashboard (no mTLS required)
```

### Permission Resolution
```
1. User requests /api/v1/files?path=/project/docs
2. Backend resolves permissions: domain → group → user overrides
3. Longest-prefix match determines access for requested path
4. File listing filtered to only show visible paths/folders
5. Write operations checked independently of read access
```

## Network Configuration

### Ports
| Port | Service | Description |
|------|---------|-------------|
| 443 | Nginx | HTTPS frontend + API reverse proxy |
| 8443 | Flask | HTTPS backend API (internal) |
| 5353 | Avahi | mDNS service discovery (UDP, host) |

### Discovery
- **Hostname**: `<MDNS_HOSTNAME>.local` (default: `thumbsup.local`)
- **Avahi service file** advertises `_https._tcp` on port 443
- **In-app mDNS** advertises `_smb._tcp` (legacy)

### WiFi AP Fallback
When no known WiFi network is available:
- SSID: `TerraCrate-AP` (WPA2-PSK)
- Gateway: `192.168.4.1`
- DHCP: `192.168.4.10–50`

## Technology Stack

### Backend
| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime |
| Flask | 3.0.0 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM (SQLite) |
| PyJWT | 2.8.0 | JWT authentication |
| bcrypt | 5.0.0 | Password hashing |
| cryptography | 41.0.7+ | Certificate generation |
| qrcode + Pillow | 7.4.2+ / 10.2.0+ | QR code generation |
| python-dotenv | 1.0.0 | Environment config |
| Ruff | — | Linting (configured in pyproject.toml) |
| pytest | — | Testing framework |

### Frontend
| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19 | UI framework |
| TypeScript | — | Type safety (strict) |
| Vite | — | Build tool + dev server |
| React Router | 7.13+ | Client-side routing |
| Tailwind CSS | 4.2+ | Utility-first styling |
| shadcn/ui (Radix) | — | Component library |
| MUI | 7.3+ | Additional components |
| Motion | 12.38+ | Animations |
| Sonner | 2.0+ | Toast notifications |
| Recharts | 3.7+ | Dashboard charts |

### Infrastructure
| Technology | Purpose |
|-----------|---------|
| Docker + Docker Compose | Containerization |
| Nginx | Reverse proxy, TLS termination, mTLS, static serving |
| Systemd | Service lifecycle (thumbsup.service, wifi-fallback.service) |
| Avahi | Host-level mDNS advertisement |
| hostapd + dnsmasq | WiFi Access Point fallback |

## Design Principles

1. **Zero Configuration**: mDNS eliminates manual IP management; WiFi AP fallback ensures connectivity
2. **Security by Default**: HTTPS-only, mTLS for file access, JWT for admin, uploads disabled by default for deletion
3. **Self-Contained**: No cloud dependencies, runs entirely on local hardware
4. **Layered Permissions**: Domain → Group → User override model with tri-state (allow/deny/inherit) semantics
5. **Certificate-Based Access**: Client certificates for non-admin users, delivered via email with P12 bundles

## Storage Structure

```
/app/storage/
└── files/              # All user-accessible files
    ├── [folders]/      # Folders with permission-controlled access
    └── [files]         # Individual files
/app/data/
└── thumbsup.db         # SQLite database
/app/certs/
├── server_cert.pem     # Server TLS certificate (also CA)
└── server_key.pem      # Server private key
```

## Testing Strategy

### Backend Unit Tests

Backend tests use **pytest** with an in-memory SQLite database. Test configuration is in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["."]`).

**Shared fixtures** (`conftest.py`): Flask test app, test client, admin/regular users, JWT tokens, temporary storage directory, seeded domain configs and groups.

| Test File | Coverage Area |
|-----------|--------------|
| `test_auth.py` | Password hashing (bcrypt), token generation/validation, session expiry (2h admin, configurable user), guest token tracking and revocation |
| `test_models.py` | Model serialization (`to_dict`), relationship integrity, cascade deletes, field defaults |
| `test_permissions.py` | Three-tier resolution (domain → group → user), `check_access` with longest-prefix matching, item visibility logic, tri-state `null` deferral, effective permissions with source attribution, domain API CRUD |
| `test_signup.py` | Domain allowlist enforcement, disallowed domain rejection, account claiming flow, multi-domain support, admin settings updates |
| `test_utils.py` | File listing (sort order, hidden file exclusion, macOS metadata filtering), path resolution, directory traversal prevention |
| `test_generate_certs.py` | Client cert generation, X.509 subject fields (CN, O, OU), SAN email, CA=False constraint, CLIENT_AUTH EKU, issuer/signature validation, custom validity periods |

### Frontend Static Analysis

The frontend does not currently have a runtime test suite. Quality is enforced through:
- **ESLint** — `@eslint/js` + `typescript-eslint` + `eslint-plugin-react-hooks` (strict rules, unused vars warned, no explicit `any`)
- **TypeScript strict mode** — full type checking via `npm run typecheck` (noEmit)
- **Build verification** — Vite production build catches import errors and type mismatches

## CI/CD Pipeline

Three GitHub Actions workflows run on push/PR to `main`, triggered by path-scoped filters:

### Backend CI (`.github/workflows/backend-ci.yml`)

Triggered by changes in `backend/**`, `docker-compose.yml`, or the workflow file itself.

**`validate` job** (ubuntu-latest, Python 3.11):
1. **Install dependencies** — pip install from `requirements.txt` + `ruff` + `pytest`
2. **Lint** — `ruff check .` (pycodestyle, pyflakes, isort, flake8-bugbear, pyupgrade)
3. **Format check** — `ruff format --check .`
4. **Unit tests** — `pytest tests/ -v`
5. **Certificate validation** — generates a test server cert and verifies the output files exist

**`docker` job** (depends on `validate`):
1. **Build backend image** — `docker/build-push-action` with GitHub Actions cache (`type=gha`), push disabled

### Frontend CI (`.github/workflows/frontend-ci.yml`)

Triggered by changes in `frontend/**` or the workflow file itself.

**`build` job** (ubuntu-latest, Node 20):
1. **Install dependencies** — `npm ci` (with package-lock cache)
2. **Lint** — `npm run lint` (ESLint)
3. **Type check** — `npm run typecheck` (TypeScript strict)
4. **Build** — `npm run build` (Vite production build)

**`docker` job** (depends on `build`):
1. **Build frontend image** — `docker/build-push-action` with GitHub Actions cache, push disabled

### Release (`.github/workflows/release.yml`)

Triggered by version tags (`v*`).

1. **Create source archive** — zips the repository excluding `.git`, `node_modules`, certificates, keys, databases, and `config.env`
2. **Create GitHub Release** — publishes the archive as a release asset via `softprops/action-gh-release`

### Pipeline Summary

```
Push/PR to main
├── backend/** changed → Backend CI
│   ├── validate (lint + format + test + cert check)
│   └── docker (build image, cached)
├── frontend/** changed → Frontend CI
│   ├── build (lint + typecheck + build)
│   └── docker (build image, cached)
└── Tag v* → Release (source archive + GitHub Release)
```

## Planned Features

### External LUKS Encrypted Storage

Support for mounting LUKS-encrypted external USB drives as the file storage backend. This would allow the shared files to reside on a removable, hardware-encrypted volume that is unreadable without the passphrase — even if the drive is physically removed from the device.

**Planned approach**:
- `setup.sh` detects attached block devices and offers to initialize a LUKS2 partition
- Passphrase stored securely (e.g., systemd-cryptsetup or TPM-backed keyslot on supported hardware)
- `thumbsup.service` gains a dependency on the LUKS mount unit, unlocking at boot
- `STORAGE_PATH` in Docker Compose points to the decrypted mount point
- Graceful degradation: if no encrypted drive is attached, falls back to local storage with a warning in the admin dashboard

### Frontend End-to-End Tests

Automated browser tests covering critical user flows to complement the existing backend unit tests and frontend static analysis.

**Planned approach**:
- Playwright test suite against a running Docker Compose stack
- Key flows to cover:
  - Admin login → dashboard → user management → approve user
  - Self-registration with domain allowlist → password change redirect
  - File upload/download/delete (admin)
  - Permission-gated file browsing (user with mTLS)
  - Certificate required redirect when client cert is missing
- CI integration: dedicated GitHub Actions job running after docker image builds, using the built images

### Certificate Revocation

Ability to revoke issued client certificates so that dismissed or compromised users lose mTLS access immediately, without waiting for certificate expiry.

**Planned approach**:
- Maintain a Certificate Revocation List (CRL) or OCSP responder backed by the SQLite database
- Admin UI action: "Revoke Certificate" on the user management page, recording the cert serial number
- Backend generates/updates a PEM-encoded CRL file on each revocation
- Nginx configured with `ssl_crl` directive to check the CRL on every mTLS handshake
- Optionally support short-lived certificates (e.g., 7-day validity) as a complementary measure to reduce the window of exposure

---

**Document Version**: 2.1
**Last Updated**: March 31, 2026
**Maintained By**: TerraCrate Development Team
