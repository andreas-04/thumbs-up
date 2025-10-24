#!/bin/bash
set -e

echo "Starting Secure NAS Server services..."

# Initialize demo storage if volume is empty
if [ ! "$(ls -A /app/demo_storage)" ]; then
    echo "Initializing demo storage with sample files..."
    cp -r /app/demo_data_template/* /app/demo_storage/
    echo "✓ Demo files copied to storage volume"
else
    echo "✓ Demo storage already initialized"
fi

# Clean up any stale D-Bus files
rm -f /var/run/dbus/pid
rm -f /var/run/dbus/system_bus_socket

# Start D-Bus
echo "Starting D-Bus..."
mkdir -p /var/run/dbus
dbus-daemon --system --fork

# Start Avahi daemon
echo "Starting Avahi daemon..."
avahi-daemon --daemonize --no-chroot

# Start RPC services for NFS
echo "Starting RPC services..."
rpcbind
rpc.statd
rpc.nfsd
rpc.mountd

# Initialize empty exports file (will be managed by Python server)
echo "Initializing NFS exports..."
> /etc/exports
exportfs -ra

# Wait a moment for services to initialize
sleep 2

echo "All services started successfully!"
echo "Starting Secure NAS server application..."

# Start the Secure NAS server
exec python3 /app/server.py
