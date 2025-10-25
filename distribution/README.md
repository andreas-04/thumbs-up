# ThumbsUp Client Installation Guide

Complete installation instructions for ThumbsUp Client on Linux and Windows.

---

## Table of Contents
1. [Linux (Debian/Ubuntu)](#linux-debianubuntu)
2. [Windows 10/11](#windows-1011)
3. [System Requirements](#system-requirements)
4. [Obtaining Certificates](#obtaining-certificates)
5. [Troubleshooting](#troubleshooting)

---

## Linux (Debian/Ubuntu)

### Installation

**Option 1: Using .deb Package (Recommended)**

```bash
# Download the package
wget https://github.com/andreas-04/thumbs-up/releases/latest/download/thumbsup-client_0.0.0-1_all.deb

# Install
sudo dpkg -i thumbsup-client_0.0.0-1_all.deb

# Fix dependencies if needed
sudo apt-get install -f
```

**Option 2: From Source**

```bash
# Install dependencies
sudo apt-get install python3 python3-pip avahi-utils nfs-common

# Install client
pip3 install thumbsup-client
```

### Setup Certificates

```bash
# Place certificates in user config directory
mkdir -p ~/.thumbsup/certs
cd ~/.thumbsup/certs

# Copy your certificates here
# - client_cert.pem
# - client_key.pem
# - server_cert.pem

# Set permissions
chmod 600 *.pem
```

### Usage

```bash
# Run with automatic discovery
sudo thumbsup-client

# Or connect to specific server
sudo thumbsup-client 192.168.1.100

# Short alias
sudo thumbsup
```

**Why sudo?** NFS mounting requires root privileges.

---

## Windows 10/11

### Installation

1. **Download Installer**
   - Download `ThumbsUp-Client-Setup.exe` from [Releases](https://github.com/andreas-04/thumbs-up/releases)

2. **Run Installer**
   - Right-click `ThumbsUp-Client-Setup.exe`
   - Select "Run as Administrator"
   - Follow the installation wizard
   - Accept default installation directory: `C:\Program Files\ThumbsUp Client\`

3. **NFS Client Feature**
   - The installer automatically enables Windows NFS Client feature
   - If it fails, enable manually:
     ```powershell
     # Run PowerShell as Administrator
     Enable-WindowsOptionalFeature -Online -FeatureName ClientForNFS-Infrastructure
     ```

### Setup Certificates

1. Open the certificate folder:
   - Start Menu → ThumbsUp Client → Certificate Folder
   - Or navigate to: `C:\Program Files\ThumbsUp Client\certs\`

2. Copy your certificate files:
   - `client_cert.pem`
   - `client_key.pem`
   - `server_cert.pem`

### Usage

```powershell
# Open Command Prompt as Administrator
# (Right-click Command Prompt → Run as Administrator)

# Run with automatic discovery
thumbsup-client

# Or connect to specific server
thumbsup-client 192.168.1.100
```

**Alternative:** Use Start Menu shortcut:
- Start Menu → ThumbsUp Client → ThumbsUp Client

---

## System Requirements

### Linux
- **OS:** Debian 10+, Ubuntu 20.04+, or compatible
- **Python:** 3.8 or later
- **Dependencies:**
  - `avahi-utils` - for mDNS service discovery
  - `nfs-common` - for NFS mounting
- **Privileges:** sudo/root access for NFS mounting
- **Network:** Same WiFi network as ThumbsUp server

### Windows
- **OS:** Windows 10 (version 1809+) or Windows 11
- **Features:**
  - NFS Client (enabled by installer)
- **Privileges:** Administrator access
- **Network:** Same WiFi network as ThumbsUp server

---

## Obtaining Certificates

You need three certificate files to connect to a ThumbsUp server:

1. **client_cert.pem** - Your unique client certificate
2. **client_key.pem** - Your private key (keep this secret!)
3. **server_cert.pem** - The server's certificate (for validation)

**How to get them:**
- Contact your ThumbsUp administrator
- They should provide all three files securely
- Or generate them yourself if you control the server

**For development/testing:**
```bash
# From the ThumbsUp repository
cd backend/pki
python3 gen_selfsigned.py

# Copy to client
cp client_cert.pem client_key.pem server_cert.pem ~/.thumbsup/certs/
```

---

## Troubleshooting

### Linux Issues

#### "No server found via mDNS"

**Cause:** Server not advertising or network issue

**Solutions:**
```bash
# Check if avahi is working
avahi-browse -a

# Check if you can see the ThumbsUp service
avahi-browse _thumbsup._tcp

# Verify network connectivity
ping <server-ip>

# Try connecting directly (bypass mDNS)
sudo thumbsup-client 192.168.1.100
```

#### "avahi-browse: command not found"

**Solution:**
```bash
sudo apt-get install avahi-utils
```

#### "mount.nfs: Permission denied"

**Solution:**
```bash
# Ensure you're running with sudo
sudo thumbsup-client

# Check if NFS client is installed
dpkg -l | grep nfs-common

# Install if missing
sudo apt-get install nfs-common
```

#### "Certificate verification failed"

**Solutions:**
```bash
# Check certificate files exist
ls -la ~/.thumbsup/certs/

# Verify you have all three files
# - client_cert.pem
# - client_key.pem
# - server_cert.pem

# Check file permissions (should be readable)
chmod 644 ~/.thumbsup/certs/*.pem

# Verify certificates are valid
openssl x509 -in ~/.thumbsup/certs/client_cert.pem -text -noout
```

### Windows Issues

#### "NFS Client feature not enabled"

**Solution:**
```powershell
# Run PowerShell as Administrator
Enable-WindowsOptionalFeature -Online -FeatureName ClientForNFS-Infrastructure

# Restart if required
Restart-Computer
```

#### "thumbsup-client: command not found"

**Solutions:**
1. Ensure you ran the installer as Administrator
2. Restart Command Prompt
3. Check PATH environment variable:
   ```powershell
   echo %PATH%
   # Should include: C:\Program Files\ThumbsUp Client
   ```
4. Use full path:
   ```powershell
   "C:\Program Files\ThumbsUp Client\thumbsup-client.exe"
   ```

#### "Certificate files not found"

**Solution:**
1. Place certificates in: `C:\Program Files\ThumbsUp Client\certs\`
2. Or: `%USERPROFILE%\.thumbsup\certs\`
3. Ensure file names match exactly (case-sensitive on some systems)

#### Firewall Blocking Connection

**Solution:**
```powershell
# Allow thumbsup-client through Windows Firewall
New-NetFirewallRule -DisplayName "ThumbsUp Client" -Direction Outbound -Program "C:\Program Files\ThumbsUp Client\thumbsup-client.exe" -Action Allow
```

### General Issues

#### Connection Timeout

**Possible causes:**
- Server not running or in DORMANT state
- Network connectivity issues
- Firewall blocking ports (8443, 2049)
- Wrong server IP/hostname

**Debug steps:**
```bash
# Test network connectivity
ping <server-ip>

# Test if mTLS port is open
telnet <server-ip> 8443

# Test if NFS port is open
telnet <server-ip> 2049
```

#### Slow Performance

**Solutions:**
- Ensure good WiFi signal strength
- Check server CPU/memory usage
- Verify network bandwidth
- Try wired connection if available

---

## Getting Help

- **GitHub Issues:** https://github.com/andreas-04/thumbs-up/issues
- **Documentation:** See README.md
- **Logs:** Check terminal output for detailed error messages

---

## Uninstallation

### Linux
```bash
sudo apt-get remove thumbsup-client
# Or
pip3 uninstall thumbsup-client
```

### Windows
- Start Menu → ThumbsUp Client → Uninstall
- Or: Settings → Apps → ThumbsUp Client → Uninstall
