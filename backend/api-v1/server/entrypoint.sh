#!/bin/bash
set -e

# Initialize demo storage if volume is empty
if [ ! "$(ls -A /app/demo_storage)" ]; then
    cp -r /app/demo_data_template/* /app/demo_storage/
fi
# Clean up any stale D-Bus files
rm -f /var/run/dbus/pid
rm -f /var/run/dbus/system_bus_socket

# Start D-Bus
mkdir -p /var/run/dbus
dbus-daemon --system --fork

# Start Avahi daemon
avahi-daemon --daemonize --no-chroot

# Start RPC services for NFS
rpcbind
rpc.statd
rpc.nfsd
rpc.mountd

# Initialize empty exports file (will be managed by Python server)
> /etc/exports
exportfs -ra

# Wait a moment for services to initialize
sleep 2

# Start the Secure NAS server
exec python3 /app/server.py
