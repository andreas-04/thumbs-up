# Thumbs Up File Share

Thumbs up is a self hosted file sharing NAS solution for a Raspberry Pi

## Quick Start

`chmod +x setup.sh`

`sudo ./setup.sh`

This sets up your desired hostname as well as installing avahi and applying our avahi config.
The hostname is applied system wide and is used to advertise your NAS over https via a `.local` domain. Avahi allows you to multicast DNS advertise your NAS on your LAN.

`docker compose up -d`

Navigate to `https://{hostname}.local`

Login via:
- **username**: admin@{hostname}.local
- **password**: 1234

You will be asked to change your password after initial login.

