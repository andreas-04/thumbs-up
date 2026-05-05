<img width="560" height="96" alt="terracrate-dark" src="https://github.com/user-attachments/assets/53240f26-19ef-42ab-9069-6626e3f46075" />

### TerraCrate is a secure, self hosted file sharing solution for a Raspberry Pi

#### University of Idaho Capstone Project

## Quick Start

```bash
chmod +x setup.sh
sudo ./setup.sh
```

The setup script will:

1. Generate a `.env` file if one does not already exist.
2. Prompt for the **mDNS hostname** — defaults to the current system hostname, or lets you enter a new one.
3. Prompt for the **initial admin password** (stored as `ADMIN_PIN` in `.env`).
4. Prompt for a **WiFi AP passphrase** (8–63 characters). This is used if the Pi cannot join a known network on boot — it will fall back to broadcasting a `TerraCrate-AP` access point.
5. Install `avahi-daemon`, `hostapd`, and `dnsmasq`, and configure mDNS so the device is discoverable on your LAN at `https://<hostname>.local`.
6. Update the system hostname if you chose a new one.
7. Optionally **LUKS-encrypt** a secondary storage drive (you will be prompted if additional drives are detected). The drive auto-unlocks on boot via a keyfile stored on the SD card.
8. Install and start `terracrate.service` — a systemd unit that automatically manages `docker compose` on boot. No need to run `docker compose` manually.

Once setup completes, navigate to:

```
https://<hostname>.local
```

Login via:
- **username**: `admin@<hostname>.local`
- **password**: the `ADMIN_PIN` you set during setup

You will be asked to change your password after initial login.
