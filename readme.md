# Thumbs Up File Share

Thumbs up is a self hosted file sharing NAS solution for a Raspberry Pi

## Quick Start

`chmod +x setup.sh`

`sudo ./setup.sh`

This installs avahi-daemon and applies the avahi service config, enabling your NAS to be discoverable on your LAN via mDNS over a `.local` domain. A default `.env` file is generated with `MDNS_HOSTNAME=thumbsup` if one does not already exist.

`docker compose up -d`

Navigate to `https://thumbsup.local`

Login via:
- **username**: admin@thumbsup.local
- **password**: 1234

You will be asked to change your password after initial login.

## Customizing the mDNS Hostname

By default, your device is advertised as `thumbsup.local`. To use a different hostname:

1. Edit the `.env` file in the project root and update the `MDNS_HOSTNAME` value:
   ```
   MDNS_HOSTNAME=mydevice
   ```
2. Update your system hostname to match:
   ```bash
   sudo hostnamectl set-hostname mydevice
   ```
3. Update `/etc/hosts` so that `127.0.1.1` resolves to the new hostname:

4. Restart the services:
   ```bash
   sudo systemctl restart avahi-daemon
   docker compose up -d
   ```

Your device will then be discoverable at `https://mydevice.local`.

