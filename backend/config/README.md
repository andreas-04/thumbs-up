# Configuration Files

This directory contains configuration files used by the Secure NAS Docker containers.

## Files

### `avahi-daemon.conf`
Avahi daemon configuration for mDNS service discovery.

**Purpose:** Configures the Avahi daemon that broadcasts the `_thumbsup._tcp` mDNS service.

**Key settings:**
- `use-ipv6`: Enable/disable IPv6 support
- `allow-interfaces`: Restrict Avahi to specific network interfaces
- `publish-aaaa-on-ipv4`: Publish IPv6 addresses on IPv4

**Used by:** Server container

---

### `dbus-system.conf`
D-Bus system bus configuration.

**Purpose:** Configures the D-Bus system message bus that Avahi and other services use for inter-process communication.

**Key settings:**
- `type`: System bus type
- `auth`: Authentication method (EXTERNAL for socket credentials)
- `allow_anonymous`: Allow connections without authentication (for containerized environment)

**Security note:** This configuration is permissive for the containerized demo environment. In production, you should restrict D-Bus policies appropriately.

**Used by:** Both server and client containers

---

### `exports.template`
NFS exports template file.

**Purpose:** Provides a template/documentation for the NFS exports format. The actual `/etc/exports` file is dynamically managed by the Python server application.

**Note:** The server application (`secure_nas_server.py`) adds and removes NFS export entries dynamically based on mTLS-authenticated clients. This template file is for reference only.

**Used by:** Server container (reference only)

---

## Usage in Docker

These configuration files are copied into the containers during the Docker build process:

```dockerfile
# In Dockerfile.server
COPY conf/avahi-daemon.conf /etc/avahi/avahi-daemon.conf
COPY conf/dbus-system.conf /etc/dbus-1/system.conf
COPY conf/exports.template /etc/exports.template

# In Dockerfile.client
COPY conf/dbus-system.conf /etc/dbus-1/system.conf
```

## Customization

To modify these configurations:

1. Edit the files in this directory
2. Rebuild the Docker containers:
   ```bash
   docker-compose down
   docker-compose up --build -d
   ```

## Configuration Hierarchy

```
Container Startup
    ↓
D-Bus System Bus (dbus-system.conf)
    ↓
Avahi Daemon (avahi-daemon.conf)
    ↓
mDNS Service Broadcasting
    ↓
NFS Exports (managed dynamically, not by exports.template)
```
