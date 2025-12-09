#!/bin/bash
set -e


# Start D-Bus (required for Avahi client tools)
mkdir -p /var/run/dbus
rm -f /var/run/dbus/pid
rm -f /var/run/dbus/system_bus_socket
dbus-daemon --system --fork

# Start Avahi daemon (required for mDNS service discovery)
avahi-daemon --daemonize --no-chroot

# Wait a moment for D-Bus and Avahi to initialize
sleep 2

# Start the client application
exec python3 /app/client.py "$@"
