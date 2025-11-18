# Protocol Comparison for Ad-Hoc File Sharing

## Executive Summary

For an ad-hoc file sharing system where users can quickly share files with nearby people via QR code/link, we need to balance ease of access, security, and cross-platform compatibility.

---

## Protocol Analysis

### 1. **SMB/CIFS (Server Message Block)**

#### Portability
- ✅ **Windows**: Native support, appears as network drive
- ✅ **macOS**: Native support via Finder → Go → Connect to Server (`smb://`)
- ⚠️ **Linux**: Requires `cifs-utils` or file manager with SMB support
- ⚠️ **Mobile (iOS/Android)**: Requires third-party apps (Documents by Readdle, Solid Explorer, etc.)
- ❌ **Web Browsers**: No direct browser access

**Verdict**: Good for desktop, poor for mobile web access

#### Security
- ✅ SMB 3.x supports encryption (AES-128-CCM/GCM)
- ✅ User authentication (username/password)
- ⚠️ SMB 2.x and below have known vulnerabilities
- ✅ Can use guest access for ad-hoc scenarios
- ⚠️ Discovery via NetBIOS/mDNS can be a security concern on untrusted networks

**Security Level**: Medium to High (depending on version and configuration)

#### Discovery
- Uses **NetBIOS** and **mDNS** (Bonjour) for service discovery
- Appears automatically in network neighborhood on Windows/macOS
- QR code would contain: `smb://hostname/share` or `smb://192.168.x.x/share`
- Users need to manually mount or use file manager

**Discovery Rating**: Good for local networks, requires app support on mobile

---

### 2. **WebDAV (Web Distributed Authoring and Versioning)**

#### Portability
- ✅ **Windows**: Native support, can map as network drive
- ✅ **macOS**: Native support via Finder → Connect to Server (`http://`)
- ✅ **Linux**: Native support via file managers (Nautilus, Dolphin)
- ✅ **Mobile (iOS)**: Native Files app support for WebDAV
- ⚠️ **Mobile (Android)**: Most file managers support it, not all
- ⚠️ **Web Browsers**: Limited - needs specialized web client, not drag-and-drop

**Verdict**: Excellent cross-platform network drive support

#### Security
- ✅ HTTPS support for encryption
- ✅ Digest or Basic authentication
- ✅ Can integrate with OAuth for modern auth
- ⚠️ Basic auth over HTTP is insecure (must use HTTPS)
- ✅ Access control per directory/file

**Security Level**: Medium to High (HTTPS + auth required)

#### Discovery
- No automatic discovery mechanism
- QR code would contain: `https://hostname:port/webdav`
- Users click link → authenticate → mount in file manager
- Can provide simple instructions overlay

**Discovery Rating**: Manual but straightforward across platforms

---

### 3. **FTP/FTPS/SFTP**

#### Portability
- ✅ **Windows**: Can map as network drive (third-party tools or Windows 10+ FTP mounting)
- ✅ **macOS**: Requires third-party apps (Cyberduck, Transmit)
- ✅ **Linux**: Native CLI support, GUI clients available
- ⚠️ **Mobile**: Requires dedicated FTP client apps
- ❌ **Web Browsers**: Read-only in some browsers, generally poor support

**Verdict**: Traditional/legacy approach, requires client software

#### Security
- ❌ **FTP**: Unencrypted, credentials in plaintext
- ✅ **FTPS**: TLS/SSL encryption
- ✅ **SFTP**: SSH-based, very secure
- ⚠️ SFTP and FTPS require certificate/key management
- ✅ User authentication

**Security Level**: Low (FTP) to High (SFTP/FTPS)

#### Discovery
- No discovery protocol
- QR code would contain: `ftp://hostname` or `sftp://hostname`
- Requires FTP client on most platforms
- Not seamless for non-technical users

**Discovery Rating**: Poor - requires technical knowledge

---

### 4. **HTTP File Server (Simple Web Interface)**

#### Portability
- ✅ **All Platforms**: Works in any web browser
- ✅ **Windows/macOS/Linux**: Universal access
- ✅ **Mobile (iOS/Android)**: Perfect browser support
- ❌ **Network Drive**: Cannot mount as network drive natively
- ⚠️ Download-only model (unless using WebDAV extensions)

**Verdict**: Maximum compatibility for access, no mounting capability

#### Security
- ✅ HTTPS for encryption
- ⚠️ Various auth mechanisms (basic, token, session)
- ✅ Easy to implement temporary access tokens
- ✅ Can use one-time QR codes with expiring links
- ✅ CORS and CSP for web security

**Security Level**: Medium to High (depends on implementation)

#### Discovery
- QR code contains: `https://hostname:port` or `https://short-url`
- Click link → opens in browser → browse/download files
- Most intuitive for non-technical users
- Can embed auth token in URL for temporary access

**Discovery Rating**: Excellent - zero friction

---

### 5. **NFS (Network File System)**

#### Portability
- ✅ **Linux**: Native support
- ⚠️ **macOS**: Native support but requires manual mounting
- ⚠️ **Windows**: Requires "Client for NFS" feature (Windows Pro/Enterprise)
- ❌ **Mobile**: No native support
- ❌ **Web Browsers**: No support

**Verdict**: Limited to Unix-like systems, poor for general use

#### Security
- ❌ NFSv3: Very weak security (IP-based, no encryption)
- ⚠️ NFSv4: Kerberos support, but complex setup
- ❌ Not designed for untrusted networks
- ⚠️ Typically relies on network-level security

**Security Level**: Low to Medium (not suitable for ad-hoc sharing)

#### Discovery
- Uses **mDNS/Avahi** for discovery
- QR code would need custom protocol handler
- Requires mounting via command line or system tools
- Very technical for average users

**Discovery Rating**: Poor for ad-hoc scenarios

---

### 6. **Samba + HTTP Hybrid**

#### Portability
- Offers best of both worlds:
  - HTTP interface for mobile/web access
  - SMB share for desktop network drive mounting
- Can serve both from same backend storage

**Verdict**: Maximum flexibility

#### Security
- HTTP: Token-based authentication, HTTPS encryption
- SMB: Standard SMB 3.x encryption
- Can use same credential system for both

**Security Level**: High (if properly configured)

#### Discovery
- HTTP: QR code → instant browser access
- SMB: Advertised via mDNS for automatic discovery
- Best user experience across all scenarios

**Discovery Rating**: Excellent

---

## Comparison Matrix

| Protocol | Portability | Security | Discovery | Network Drive | Web Access | Mobile |
|----------|-------------|----------|-----------|---------------|------------|--------|
| **SMB** | 3/5 | 4/5 | 4/5 | ✅ Yes | ❌ No | ⚠️ App needed |
| **WebDAV** | 4/5 | 4/5 | 3/5 | ✅ Yes | ⚠️ Limited | ✅ iOS native |
| **FTP/SFTP** | 3/5 | 2-4/5 | 2/5 | ⚠️ Limited | ❌ No | ⚠️ App needed |
| **HTTP** | 5/5 | 4/5 | 5/5 | ❌ No | ✅ Yes | ✅ Yes |
| **NFS** | 2/5 | 2/5 | 2/5 | ✅ Linux/Unix | ❌ No | ❌ No |
| **Hybrid** | 5/5 | 4/5 | 5/5 | ✅ Yes | ✅ Yes | ✅ Yes |

---

## Recommended Approach

### **Option 1: HTTP-First with WebDAV (Recommended)**

**Implementation**: 
- Primary: HTTPS file browser interface (like Filebrowser, FileBrowser.org)
- Secondary: WebDAV endpoint for those who want network drive mounting
- Same authentication backend

**Advantages**:
- ✅ QR code → instant access in any browser
- ✅ Optional network drive for power users
- ✅ Works on all platforms without additional software
- ✅ Can implement temporary access tokens
- ✅ Easy to add features (upload, permissions, etc.)

**User Flow**:
1. Host scans QR code
2. Opens browser to `https://thumbsup.local:8443?token=xyz`
3. Immediately sees file listing
4. Can browse, download, upload via web UI
5. (Optional) Can mount as WebDAV drive for drag-and-drop

**Security Features**:
- HTTPS with self-signed or Let's Encrypt cert
- Time-limited access tokens in QR code
- Optional password protection
- Rate limiting and access logging

---

### **Option 2: Samba + HTTP Hybrid**

**Implementation**:
- Samba server for network drive functionality
- Lightweight HTTP server for web access
- Both point to same storage directory

**Advantages**:
- ✅ Native network drive experience on desktop
- ✅ Web fallback for all other devices
- ✅ Automatic discovery via mDNS for Samba
- ✅ QR code directs to web interface

**User Flow**:
1. Desktop users: Auto-discover via network neighborhood OR QR code
2. Mobile/web users: Scan QR → browser access
3. Power users can mount SMB share

**Complexity**: Medium - requires running two servers

---

### **Option 3: HTTP Only (Simplest)**

**Implementation**:
- Single HTTP(S) server with file browser UI
- Modern web interface (drag-and-drop, preview, etc.)

**Advantages**:
- ✅ Simplest to implement
- ✅ Works everywhere
- ✅ Zero client-side configuration
- ✅ Can be very polished UX

**Disadvantages**:
- ❌ No network drive mounting
- ❌ Must use web UI for all operations

**Best for**: Quick, temporary sharing scenarios

---

## Technical Implementation Recommendations

### For HTTP/WebDAV Solution:

**Software Options**:
1. **Filebrowser** (Go-based, single binary)
   - Built-in WebDAV support
   - Modern UI, user management
   - Easy to deploy
   
2. **Caddy** + **file-server** + WebDAV plugin
   - Automatic HTTPS
   - Very lightweight
   - Simple configuration

3. **Nginx** + **nginx-dav-ext-module**
   - Production-grade
   - Highly configurable
   - Requires more setup

### For Hybrid Solution:

**Software Stack**:
- **Samba** for SMB/CIFS
- **Filebrowser** or **Caddy** for HTTP
- **Avahi** for mDNS discovery
- **Shared storage backend**

### Security Considerations:

1. **HTTPS**: Always use TLS
   - Self-signed cert with clear warning bypass instructions
   - Or use mDNS + automatic cert generation
   
2. **Authentication**:
   - Time-limited tokens embedded in QR code
   - Optional password for extended access
   - IP-based rate limiting

3. **Access Control**:
   - Read-only vs read-write modes
   - Per-share permissions
   - Audit logging

4. **Network Isolation**:
   - Bind only to WiFi interface
   - Firewall rules to prevent WAN exposure
   - Auto-shutdown after inactivity

---

## Conclusion

**For your ad-hoc sharing use case, I recommend Option 1: HTTP-First with WebDAV**

This provides:
- ✅ Universal access via QR code (no app installation)
- ✅ Network drive mounting for those who need it
- ✅ Simple implementation and maintenance
- ✅ Excellent security options (tokens, HTTPS, access control)
- ✅ Best user experience across all device types

The HTTP interface handles 95% of use cases (mobile, casual sharing), while WebDAV provides the "network drive" experience for power users without requiring separate infrastructure.

**Next Steps**:
1. Choose HTTP server implementation (Filebrowser recommended)
2. Set up HTTPS with self-signed certs
3. Implement token-based access via QR codes
4. Add WebDAV endpoint for network drive mounting
5. Configure mDNS for easy local discovery
6. Build frontend with clear "How to Connect" instructions
