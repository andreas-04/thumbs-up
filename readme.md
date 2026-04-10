# TerraCrate File Share

TerraCrate is a self-hosted file sharing NAS solution for Raspberry Pi.

## Quick Start

**1. Run the host setup script**

```bash
chmod +x setup.sh
sudo ./setup.sh
```

The script will:
- Prompt for a **WiFi AP passphrase** (8–63 characters) if one isn't already in `.env` — this is used for the fallback hotspot when no known network is in range
- Generate a default `.env` file with `MDNS_HOSTNAME=terracrate`
- Install and configure avahi-daemon (mDNS), hostapd, and dnsmasq
- Set the system hostname to match `MDNS_HOSTNAME`
- Install and enable the `terracrate` systemd service so Docker Compose starts on boot

**2. Set a secure admin PIN**

Edit the generated `.env` file and set `ADMIN_PIN` before starting the containers:

```
ADMIN_PIN=your-secure-pin
```

This PIN becomes both the initial admin password and is used to derive the admin account on first boot. If omitted the containers will refuse to start.

**3. Start the containers**

```bash
docker compose up -d
```

**4. Open the web UI**

Navigate to `https://terracrate.local` (accept the self-signed certificate warning).

Default admin credentials:
- **email**: `admin@terracrate.local`
- **password**: the value of `ADMIN_PIN` from your `.env`

You will be prompted to change your password on first login.

> **Note:** The admin email is derived from `MDNS_HOSTNAME` — if you change the hostname the email becomes `admin@<hostname>.local`.

## Guest Access

Unauthenticated users can browse and download files at `https://terracrate.local/guest`.

To expose files publicly, upload them to the `guest/` folder using the admin file browser (the **files / guest** toggle in the Files tab).

## Customizing the mDNS Hostname

By default your device is advertised as `terracrate.local`. To use a different hostname:

1. Edit `.env` and set `MDNS_HOSTNAME`:
   ```
   MDNS_HOSTNAME=mydevice
   ```

2. Update `/etc/hosts` so `127.0.1.1` resolves to the new hostname:
   ```bash
   sudo sed -i "s/127.0.1.1.*/127.0.1.1\tmydevice/" /etc/hosts
   ```

3. Restart services:
   ```bash
   sudo systemctl restart avahi-daemon
   docker compose up -d
   ```

Your device will then be discoverable at `https://mydevice.local`.

