#!/bin/bash
set -e

echo "Starting Secure NAS Client..."

# Start D-Bus (required for Avahi client tools)
echo "Starting D-Bus..."
mkdir -p /var/run/dbus
rm -f /var/run/dbus/pid
rm -f /var/run/dbus/system_bus_socket
dbus-daemon --system --fork

# Start Avahi daemon (required for mDNS service discovery)
echo "Starting Avahi daemon..."
avahi-daemon --daemonize --no-chroot

# Wait a moment for D-Bus and Avahi to initialize
sleep 2

echo "D-Bus and Avahi started successfully!"
echo "Starting client application..."

# Start the client application
exec python3 /app/client.py "$@"
